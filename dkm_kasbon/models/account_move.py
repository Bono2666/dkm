# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError

# Gaji, Bonus/Tunjangan, Lembur and Kompensasi Karyawan (Indonesian chart).
SALARY_ACCOUNT_CODES = ('61100010', '61100020', '61100030', '61100040')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    dkm_kasbon_id = fields.Many2one('dkm.kasbon', string="Kasbon", index='btree_not_null',
                                    copy=False, readonly=True)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _dkm_is_salary_bill(self):
        """A vendor bill to an employee on a salary account."""
        self.ensure_one()
        if self.move_type not in ('in_invoice', 'in_refund') or not self.partner_id:
            return False
        if not any(code in SALARY_ACCOUNT_CODES
                   for code in self.invoice_line_ids.account_id.mapped('code')):
            return False
        return bool(self.env['hr.employee'].sudo().with_context(active_test=False).search_count([
            ('work_contact_id', '=', self.partner_id.commercial_partner_id.id),
            ('company_id', 'in', (self.company_id.id, False)),
        ], limit=1))

    def _post(self, soft=True):
        salary_bills = self.filtered(lambda m: m.state == 'draft' and m._dkm_is_salary_bill())
        if salary_bills:
            raise UserError(
                "Gaji pegawai dicatat lewat menu Pengeluaran > Penggajian, supaya "
                "total gaji bulanan disetujui sekaligus dan kasbon terpotong otomatis.")
        posted = super()._post(soft=soft)
        # A posted salary deduction pays off part of the kasbon.
        for line in posted.line_ids.filtered('dkm_kasbon_id'):
            kasbon_line = line.dkm_kasbon_id.move_line_id
            if kasbon_line and not kasbon_line.reconciled and not line.reconciled:
                (line | kasbon_line).reconcile()
        return posted

    def button_draft(self):
        deductions = self.line_ids.filtered(lambda l: l.dkm_kasbon_id and l.reconciled)
        if deductions:
            deductions.remove_move_reconcile()
        return super().button_draft()
