# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class DkmDivision(models.Model):
    """A DKM division (Dakwah, Rumah Tangga, ...). Its head approves the
    vendor bills recorded for it."""
    _name = 'dkm.division'
    _description = "Divisi DKM"
    _order = 'sequence, name'

    name = fields.Char("Divisi", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    head_id = fields.Many2one(
        'res.users', string="Kepala Divisi", required=True,
        domain="[('share', '=', False)]",
        help="Menyetujui tagihan divisi ini yang memerlukan persetujuan.")

    _name_unique = models.Constraint('UNIQUE (name)', "Nama divisi sudah ada.")


class AccountMove(models.Model):
    _inherit = 'account.move'

    dkm_division_id = fields.Many2one(
        'dkm.division', string="Divisi", tracking=True, index='btree_not_null',
        help="Divisi yang memakai dana ini. Kepala divisinya yang menyetujui "
             "tagihan di atas batas persetujuan.")

    def _dkm_approval_exempt(self, policy):
        """Amounts below the policy's lowest band need no approval (e.g. bills
        up to Rp 250.000 when the only band starts above it)."""
        self.ensure_one()
        if not policy or not policy.rule_ids:
            return False
        currency = policy.company_id.currency_id
        lowest = min(policy.rule_ids.mapped('min_amount'))
        amount = currency.round(abs(self._eh_amount_for_approval()))
        return (currency.compare_amounts(amount, currency.round(lowest)) < 0
                and not policy.find_matching_rule(amount))

    def _eh_check_approval_gate(self):
        self.ensure_one()
        policy = self.env['eh.approval.policy'].find_for_move(self)
        if self._dkm_approval_exempt(policy.sudo()):
            return
        return super()._eh_check_approval_gate()

    @api.depends('amount_total', 'dkm_division_id')
    def _compute_requires_approval(self):
        super()._compute_requires_approval()
        for move in self.filtered(lambda m: m.eh_requires_approval):
            policy = self.env['eh.approval.policy'].find_for_move(move)
            if move._dkm_approval_exempt(policy.sudo()):
                move.eh_requires_approval = False

    def action_eh_request_approval(self):
        missing = self.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund')
                                and not m.dkm_division_id)
        if missing:
            raise UserError("Pilih Divisi pada tagihan terlebih dahulu, supaya "
                            "persetujuannya dikirim ke kepala divisi yang tepat.")
        return super().action_eh_request_approval()


class EhApprovalRequest(models.Model):
    _inherit = 'eh.approval.request'

    def _eh_manager_user(self):
        """A step with "Kepala Divisi transaksi" (inject_manager) goes to the
        head of the bill's division."""
        head = self.move_id.dkm_division_id.head_id
        if head:
            return head
        return super()._eh_manager_user()
