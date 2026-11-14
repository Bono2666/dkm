# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class EhApprovalRequest(models.Model):
    _inherit = 'eh.approval.request'

    dkm_token_ids = fields.One2many(
        'dkm.approval.token', 'request_id', string="Link WhatsApp",
        readonly=True,
    )

    # ---- hooks into the approval engine ----

    def _eh_schedule_step_activity(self):
        result = super()._eh_schedule_step_activity()
        self._dkm_notify_whatsapp()
        return result

    def _eh_escalate_to_group(self, target_group, manual=False):
        result = super()._eh_escalate_to_group(target_group, manual=manual)
        self._dkm_notify_whatsapp()
        return result

    # ---- recipients ----

    def _dkm_whatsapp_recipients(self):
        """Approvers who can sign an open step and have not voted yet."""
        self.ensure_one()
        users = self.env['res.users']
        if self.state != 'in_review':
            return users
        for index in self._eh_open_step_indexes():
            users |= self._eh_step_eligible_users(index)
        users = users.filtered('active')
        snapshot = self._eh_snapshot_payload_safe() or {}
        if not snapshot.get('allow_self_approval'):
            users -= self.requested_by_id
        users -= self.vote_ids.filtered(
            lambda vote: vote.cycle == self.approval_cycle).mapped('user_id')
        return users

    def _dkm_notify_whatsapp(self, force=False):
        """Issue WhatsApp links to open-step approvers.

        Without ``force``, approvers who still hold a live link for this
        cycle and step are skipped, so parallel steps and escalations do not
        spam. A new sequential step always issues fresh links.
        A delivery problem never breaks the approval transition.
        """
        Token = self.env['dkm.approval.token'].sudo()
        if not Token._dkm_is_enabled():
            return Token
        tokens = Token
        now = fields.Datetime.now()
        for rec in self.sudo():
            try:
                with self.env.cr.savepoint():
                    users = rec._dkm_whatsapp_recipients()
                    if not force:
                        users -= Token.search([
                            ('request_id', '=', rec.id),
                            ('cycle', '=', rec.approval_cycle),
                            ('step_index', '=', rec.current_step),
                            ('state', '=', 'active'),
                            ('expires_at', '>', now),
                        ]).mapped('user_id')
                    tokens |= Token._dkm_issue_for_users(rec, users)
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "Approval %s: could not issue WhatsApp approval links",
                    rec.name)
        return tokens

    # ---- button ----

    def action_dkm_resend_whatsapp(self):
        self.ensure_one()
        user = self.env.user
        self.check_access('read')
        if (
            self.requested_by_id != user
            and not user.has_group('eh_account_base.group_eh_manager')
        ):
            raise AccessError(_(
                "Hanya pengaju atau EH Accounting Manager yang dapat "
                "mengirim ulang link WhatsApp."))
        if self.state != 'in_review':
            raise UserError(_(
                "Link hanya bisa dikirim untuk pengajuan yang sedang "
                "menunggu persetujuan."))
        if not self.env['dkm.approval.token']._dkm_is_enabled():
            raise UserError(_(
                "Approval via WhatsApp belum diaktifkan. Aktifkan di "
                "Pengaturan > Invoicing > Approval via WhatsApp."))
        tokens = self._dkm_notify_whatsapp(force=True)
        if not tokens:
            message = _("Tidak ada approver yang perlu dikirimi link.")
            kind = 'warning'
        else:
            skipped = tokens.filtered(lambda t: t.send_state == 'skipped')
            message = _(
                "%(n)s link dibuat dan akan dikirim via WhatsApp.",
                n=len(tokens) - len(skipped))
            if skipped:
                message += " " + _(
                    "Tanpa nomor WA: %s.",
                    ", ".join(skipped.mapped('user_id.name')))
            kind = 'success' if not skipped else 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Link WhatsApp"),
                'message': message,
                'type': kind,
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
