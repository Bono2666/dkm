# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

from .kasbon import line_label_field

# Gaji, Bonus/Tunjangan, Lembur and Kompensasi Karyawan (Indonesian chart).
SALARY_ACCOUNT_CODES = ('61100010', '61100020', '61100030', '61100040')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    dkm_kasbon_id = fields.Many2one('dkm.kasbon', string="Kasbon", index='btree_not_null',
                                    copy=False, readonly=True)


class AccountMove(models.Model):
    _inherit = 'account.move'

    dkm_kasbon_available = fields.Boolean(compute='_compute_dkm_kasbon_available')

    def _dkm_open_kasbons(self):
        self.ensure_one()
        if not self.partner_id:
            return self.env['dkm.kasbon']
        return self.env['dkm.kasbon'].search([
            ('partner_id', '=', self.partner_id.commercial_partner_id.id),
            ('state', '=', 'active'),
            ('company_id', '=', self.company_id.id),
        ])

    @api.depends('partner_id', 'state', 'move_type', 'invoice_line_ids.dkm_kasbon_id')
    def _compute_dkm_kasbon_available(self):
        for move in self:
            move.dkm_kasbon_available = bool(
                move.move_type == 'in_invoice' and move.state == 'draft'
                and (move._dkm_open_kasbons() - move.invoice_line_ids.dkm_kasbon_id))

    def _dkm_is_salary_bill(self):
        """A bill to an employee whose lines are only salary accounts (plus the
        kasbon deduction). Salaries are fixed, so they skip the bill approval."""
        self.ensure_one()
        if self.move_type != 'in_invoice' or not self.partner_id:
            return False
        lines = self.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        if not lines:
            return False
        employee = self.env['hr.employee'].sudo().with_context(active_test=False).search([
            ('work_contact_id', '=', self.partner_id.commercial_partner_id.id),
            ('company_id', 'in', (self.company_id.id, False)),
        ], limit=1)
        if not employee:
            return False
        kasbon_account = self.company_id._dkm_kasbon_account()
        return all(line.account_id.code in SALARY_ACCOUNT_CODES
                   or (line.dkm_kasbon_id and line.account_id == kasbon_account)
                   for line in lines)

    def _dkm_approval_exempt(self, policy):
        return self._dkm_is_salary_bill() or super()._dkm_approval_exempt(policy)

    @api.depends('partner_id', 'invoice_line_ids.account_id')
    def _compute_requires_approval(self):
        return super()._compute_requires_approval()

    def action_dkm_add_kasbon_deduction(self):
        """Salary bill: deduct this month's installment of the employee's
        kasbon (a negative line on Piutang Kasbon Pegawai)."""
        fname = line_label_field(self.env)
        for move in self:
            if move.move_type != 'in_invoice' or move.state != 'draft':
                continue
            kasbons = move._dkm_open_kasbons() - move.invoice_line_ids.dkm_kasbon_id
            if not kasbons:
                raise UserError("Tidak ada kasbon berjalan untuk pegawai ini.")
            lines = []
            for kasbon in kasbons:
                amount = min(kasbon.installment_amount, kasbon.residual)
                number = kasbon.paid_count + 1
                lines.append((0, 0, {
                    fname: f"Potongan kasbon {kasbon.name} (cicilan {number} dari "
                           f"{kasbon.installments})",
                    'account_id': kasbon.company_id._dkm_kasbon_account().id,
                    'quantity': 1,
                    'price_unit': -amount,
                    'tax_ids': [(6, 0, [])],
                    'dkm_kasbon_id': kasbon.id,
                }))
            move.write({'invoice_line_ids': lines})
        return True

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        # A posted salary deduction pays off part of the kasbon.
        for line in posted.line_ids.filtered(
                lambda l: l.dkm_kasbon_id and l.move_id.move_type == 'in_invoice'):
            kasbon_line = line.dkm_kasbon_id.move_line_id
            if kasbon_line and not kasbon_line.reconciled and not line.reconciled:
                (line | kasbon_line).reconcile()
        return posted

    def button_draft(self):
        deductions = self.line_ids.filtered(lambda l: l.dkm_kasbon_id and l.reconciled)
        if deductions:
            deductions.remove_move_reconcile()
        return super().button_draft()
