# -*- coding: utf-8 -*-
"""One-time WhatsApp approval links.

The raw token only ever lives in the WhatsApp message (and in memory until
the post-commit send). The database keeps its SHA-256, so a database read
does not reveal working links.

A link authorizes nothing on its own: the decision runs as the bound
approver through the regular ``action_approve`` / ``action_reject`` path,
after the approver's personal PIN is verified. All approval rules (step
order, segregation of duties, N-of-M, snapshot integrity) and the audit log
therefore apply unchanged.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.registry import Registry
from odoo.tools.misc import format_amount

from . import fonnte

_logger = logging.getLogger(__name__)

PARAM_ENABLED = 'dkm_approval_whatsapp.enabled'
PARAM_TOKEN = 'dkm_approval_whatsapp.fonnte_token'
PARAM_VALIDITY = 'dkm_approval_whatsapp.link_validity_hours'
DEFAULT_VALIDITY_HOURS = 72
DEFAULT_APPROVE_COMMENT = "Disetujui melalui link WhatsApp."
LINK_PATH = '/dkm/approval/'


def _hash_token(raw):
    return hashlib.sha256((raw or '').encode('utf-8')).hexdigest()


class DkmApprovalToken(models.Model):
    _name = 'dkm.approval.token'
    _description = "Link persetujuan WhatsApp"
    _order = 'create_date desc, id desc'

    request_id = fields.Many2one(
        'eh.approval.request', string="Pengajuan", required=True,
        ondelete='cascade', index=True, readonly=True,
    )
    company_id = fields.Many2one(
        related='request_id.company_id', store=True, readonly=True,
    )
    user_id = fields.Many2one(
        'res.users', string="Approver", required=True, ondelete='cascade',
        index=True, readonly=True,
    )
    cycle = fields.Integer(readonly=True)
    step_index = fields.Integer(
        readonly=True,
        help="Step pointer of the request when the link was issued; a new "
             "step issues fresh links.",
    )
    token_hash = fields.Char(
        required=True, readonly=True, index=True, copy=False,
        groups='base.group_system',
    )
    expires_at = fields.Datetime(string="Berlaku sampai", readonly=True)
    state = fields.Selection(
        [('active', "Aktif"), ('used', "Sudah dipakai"),
         ('revoked', "Dibatalkan")],
        default='active', required=True, readonly=True,
    )
    is_expired = fields.Boolean(
        string="Kadaluarsa", compute='_compute_is_expired')
    used_at = fields.Datetime(string="Dipakai pada", readonly=True)
    decision = fields.Selection(
        [('approve', "Disetujui"), ('reject', "Ditolak")], readonly=True,
    )
    send_state = fields.Selection(
        [('queued', "Dalam antrian"), ('sent', "Terkirim"),
         ('failed', "Gagal"), ('skipped', "Tidak dikirim")],
        string="Status WA", default='queued', readonly=True,
    )
    sent_at = fields.Datetime(string="Dikirim pada", readonly=True)
    send_detail = fields.Char(string="Keterangan", readonly=True)

    _token_hash_unique = models.Constraint(
        'UNIQUE(token_hash)', "Token link persetujuan harus unik.",
    )

    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for token in self:
            token.is_expired = bool(
                token.expires_at and token.expires_at < now)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @api.model
    def _dkm_is_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_bool(PARAM_ENABLED)

    @api.model
    def _dkm_validity_hours(self):
        hours = self.env['ir.config_parameter'].sudo().get_int(PARAM_VALIDITY)
        return hours if hours > 0 else DEFAULT_VALIDITY_HOURS

    @api.model
    def _dkm_api_token(self):
        return self.env['ir.config_parameter'].sudo().get_str(PARAM_TOKEN)

    # ------------------------------------------------------------------
    # Issuing and sending
    # ------------------------------------------------------------------

    @api.model
    def _dkm_issue_for_users(self, request, users):
        """Create a fresh link per user and queue the WhatsApp messages.

        Revokes any earlier active link of the same user for the request so
        only the newest message works.
        """
        Token = self.sudo()
        if not users:
            return Token
        Token.search([
            ('request_id', '=', request.id),
            ('user_id', 'in', users.ids),
            ('state', '=', 'active'),
        ]).write({'state': 'revoked'})
        expires_at = fields.Datetime.now() + timedelta(
            hours=self._dkm_validity_hours())
        payloads = []
        tokens = Token
        for user in users:
            raw = secrets.token_urlsafe(32)
            token = Token.create({
                'request_id': request.id,
                'user_id': user.id,
                'cycle': request.approval_cycle,
                'step_index': request.current_step,
                'token_hash': _hash_token(raw),
                'expires_at': expires_at,
            })
            tokens |= token
            target = user._dkm_whatsapp_target()
            if not target:
                token.write({
                    'send_state': 'skipped',
                    'send_detail': _(
                        "Nomor WhatsApp %s belum diisi atau tidak valid.",
                        user.name),
                })
                continue
            payloads.append({
                'token_id': token.id,
                'target': target,
                'message': token._dkm_compose_message(raw),
            })
        if payloads:
            self._dkm_queue_send(payloads)
        return tokens

    def _dkm_compose_message(self, raw):
        self.ensure_one()
        request = self.request_id.sudo()
        move = request.move_id
        user = self.user_id
        tz_env = self.with_context(tz=user.tz or 'Asia/Jakarta')
        expires_local = fields.Datetime.context_timestamp(
            tz_env, self.expires_at)
        amount = format_amount(
            self.with_context(lang=user.lang or 'id_ID').env,
            request.submitted_amount, request.currency_id)
        step_label = ''
        if request.total_steps > 1:
            step_label = "\n• Tahap: %s dari %s" % (
                request.current_step + 1, request.total_steps)
        partner = move.partner_id.display_name or request.request_partner_id.display_name
        lines = [
            "Assalamu'alaikum %s," % user.name,
            "",
            "Ada pengajuan %s yang menunggu persetujuan Anda:" % (
                request.company_id.name),
            "• No: %s" % request.name,
            "• Dokumen: %s" % (move.name if move.name != '/' else (move.ref or '-')),
        ]
        if partner:
            lines.append("• Kepada: %s" % partner)
        lines += [
            "• Jumlah: %s" % amount,
            "• Diajukan oleh: %s%s" % (request.requested_by_id.name, step_label),
            "",
            "Buka link berikut untuk menyetujui atau menolak:",
            "%s%s%s" % (request.get_base_url(), LINK_PATH, raw),
            "",
            "Berlaku sampai %s. Persetujuan memerlukan PIN pribadi Anda; "
            "jangan teruskan pesan ini." % expires_local.strftime('%d/%m/%Y %H:%M'),
        ]
        return "\n".join(lines)

    @api.model
    def _dkm_queue_send(self, payloads):
        """Send after commit, so a rolled-back transition never messages."""
        dbname = self.env.cr.dbname

        @self.env.cr.postcommit.add
        def _dkm_send_whatsapp_after_commit():
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                env['dkm.approval.token']._dkm_send_now(payloads)

    @api.model
    def _dkm_send_now(self, payloads):
        api_token = self._dkm_api_token()
        for payload in payloads:
            ok, detail = fonnte.send_message(
                api_token, payload['target'], payload['message'])
            token = self.sudo().browse(payload['token_id']).exists()
            if not token:
                continue
            token.write({
                'send_state': 'sent' if ok else 'failed',
                'sent_at': fields.Datetime.now() if ok else False,
                'send_detail': (detail or '')[:250],
            })
            if not ok:
                _logger.warning(
                    "WhatsApp approval link for %s (request %s) not sent: %s",
                    token.user_id.login, token.request_id.name, detail)

    # ------------------------------------------------------------------
    # Using a link
    # ------------------------------------------------------------------

    @api.model
    def _dkm_find(self, raw):
        if not raw or len(raw) > 128:
            return self.sudo().browse()
        return self.sudo().search(
            [('token_hash', '=', _hash_token(raw))], limit=1)

    def _dkm_unusable_reason(self):
        """Why this link cannot record a decision now; '' when it can."""
        self.ensure_one()
        token = self.sudo()
        request = token.request_id
        if token.state == 'used':
            return _("Link ini sudah dipakai untuk memberikan keputusan.")
        if token.state == 'revoked':
            return _("Link ini sudah diganti dengan link yang lebih baru. "
                     "Gunakan pesan WhatsApp terbaru.")
        if token.is_expired:
            return _("Link ini sudah kadaluarsa. Minta bendahara mengirim "
                     "ulang link persetujuan.")
        if token.cycle != request.approval_cycle:
            return _("Pengajuan ini sudah diajukan ulang. Gunakan link "
                     "terbaru.")
        if request.state != 'in_review':
            return _("Pengajuan ini tidak lagi menunggu persetujuan "
                     "(status: %s).",
                     dict(request._fields['state'].selection).get(
                         request.state, request.state))
        if token.user_id.id not in request.pending_group_user_ids.ids:
            return _("Anda bukan approver untuk tahap yang sedang berjalan.")
        voted = request.vote_ids.filtered(
            lambda v: v.cycle == request.approval_cycle
            and v.user_id == token.user_id)
        if voted:
            return _("Anda sudah memberikan keputusan untuk pengajuan ini.")
        return ''

    def _dkm_decide(self, decision, comment, pin):
        """Record the approver's decision. Returns ``(ok, message)``.

        Never raises for user-facing problems: a wrong PIN must still commit
        its failure counter.
        """
        self.ensure_one()
        token = self.sudo()
        if decision not in ('approve', 'reject'):
            return False, _("Keputusan tidak dikenal.")
        comment = (comment or '').strip()
        if decision == 'reject' and not comment:
            return False, _("Tuliskan alasan penolakan.")
        if len(comment) > 2000:
            return False, _("Komentar terlalu panjang (maksimal 2000 "
                            "karakter).")
        # Serialize double taps / two open tabs on the same link.
        self.env.cr.execute(
            "SELECT id FROM dkm_approval_token WHERE id = %s FOR UPDATE",
            [token.id])
        token.invalidate_recordset()
        reason = token._dkm_unusable_reason()
        if reason:
            return False, reason
        user = token.user_id
        ok, message = user._dkm_check_approval_pin(pin)
        if not ok:
            return False, message
        request = token.request_id.with_user(user).with_context(
            allowed_company_ids=[token.request_id.company_id.id],
        )
        try:
            with self.env.cr.savepoint():
                if decision == 'approve':
                    request.action_approve(
                        comment=comment or DEFAULT_APPROVE_COMMENT)
                else:
                    request.action_reject(reason=comment)
        except (UserError, AccessError, ValidationError) as exc:
            self.env.invalidate_all()
            return False, str(exc.args[0] if exc.args else exc)
        self.env.invalidate_all()
        token.write({
            'state': 'used',
            'used_at': fields.Datetime.now(),
            'decision': decision,
        })
        if decision == 'approve':
            return True, _("Terima kasih. Persetujuan Anda sudah tercatat.")
        return True, _("Pengajuan sudah ditolak. Alasan Anda tercatat.")
