# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

ACTIVITY_DOMAIN = "[('state', 'in', ('draft', 'open')), ('company_id', '=', company_id)]"


class AccountMove(models.Model):
    _inherit = 'account.move'

    dkm_activity_id = fields.Many2one(
        'dkm.activity', string="Kegiatan", tracking=True, index='btree_not_null',
        domain=ACTIVITY_DOMAIN, copy=False,
        help="Kegiatan yang menerima atau memakai dana ini (mis. Qurban, Ramadhan).")

    @api.onchange('dkm_activity_id')
    def _onchange_dkm_activity_fund(self):
        """A bill for an activity is paid from Dana Kegiatan by default; it can
        be changed to Dana Umum/Operasional when the DKM subsidises it."""
        if not self.is_purchase_document(include_receipts=True):
            return
        fund = self.env.ref('dkm_kegiatan.fund_kegiatan', raise_if_not_found=False)
        if self.dkm_activity_id and fund:
            self.dkm_fund_id = fund
        elif fund and self.dkm_fund_id == fund:
            self.dkm_fund_id = self.env['dkm.fund']._dkm_default()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    dkm_activity_id = fields.Many2one(
        'dkm.activity', string="Kegiatan", index='btree_not_null',
        compute='_compute_dkm_activity_id', store=True, readonly=False, precompute=True,
        domain=ACTIVITY_DOMAIN)
    dkm_activity_budget_id = fields.Many2one(
        'dkm.activity.budget', string="Pos Anggaran", index='btree_not_null',
        domain="[('activity_id', '=', dkm_activity_id)]")

    @api.depends('move_id.dkm_activity_id', 'display_type')
    def _compute_dkm_activity_id(self):
        for line in self:
            move = line.move_id
            if line.display_type == 'product' and move.is_invoice(include_receipts=True):
                line.dkm_activity_id = move.dkm_activity_id
            else:
                line.dkm_activity_id = line.dkm_activity_id

    @api.onchange('dkm_activity_id')
    def _onchange_dkm_activity_budget(self):
        if self.dkm_activity_budget_id.activity_id != self.dkm_activity_id:
            self.dkm_activity_budget_id = False

    @api.constrains('dkm_activity_id', 'dkm_activity_budget_id')
    def _check_dkm_activity_budget(self):
        for line in self.filtered('dkm_activity_budget_id'):
            if line.dkm_activity_budget_id.activity_id != line.dkm_activity_id:
                raise ValidationError(
                    f"Pos anggaran {line.dkm_activity_budget_id.name} bukan milik "
                    f"kegiatan {line.dkm_activity_id.name or '-'}.")
