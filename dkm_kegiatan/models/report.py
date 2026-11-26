# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class DkmActivityReport(models.Model):
    """Posted income and expense lines recorded for an activity."""
    _name = 'dkm.activity.report'
    _description = "Laporan Kegiatan"
    _auto = False
    _order = 'date desc, id desc'

    date = fields.Date("Tanggal", readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    activity_id = fields.Many2one('dkm.activity', string="Kegiatan", readonly=True)
    budget_id = fields.Many2one('dkm.activity.budget', string="Pos Anggaran", readonly=True)
    fund_id = fields.Many2one('dkm.fund', string="Sumber Dana", readonly=True)
    account_id = fields.Many2one('account.account', string="Akun", readonly=True)
    product_id = fields.Many2one('product.product', string="Kategori", readonly=True)
    move_id = fields.Many2one('account.move', string="Dokumen", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Donatur/Vendor", readonly=True)
    name = fields.Char("Keterangan", readonly=True)
    type = fields.Selection([('income', "Penerimaan"), ('expense', "Pengeluaran")],
                            string="Jenis", readonly=True)
    income = fields.Monetary("Penerimaan", readonly=True)
    expense = fields.Monetary("Pengeluaran", readonly=True)
    balance = fields.Monetary("Selisih", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        fields_ = self.env['account.move.line']._fields
        label = 'label' if 'label' in fields_ and fields_['label'].store else 'name'
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
                SELECT aml.id, aml.date, aml.company_id, aml.dkm_activity_id AS activity_id,
                       aml.dkm_activity_budget_id AS budget_id, aml.dkm_fund_id AS fund_id,
                       aml.account_id, aml.product_id, aml.move_id, aml.partner_id,
                       aml.{label} AS name,
                       CASE WHEN acc.account_type LIKE 'income%' THEN 'income'
                            ELSE 'expense' END AS type,
                       CASE WHEN acc.account_type LIKE 'income%' THEN -aml.balance ELSE 0 END AS income,
                       CASE WHEN acc.account_type LIKE 'expense%' THEN aml.balance ELSE 0 END AS expense,
                       -aml.balance AS balance
                  FROM account_move_line aml
                  JOIN account_account acc ON acc.id = aml.account_id
                 WHERE aml.parent_state = 'posted'
                   AND aml.dkm_activity_id IS NOT NULL
                   AND (acc.account_type LIKE 'income%' OR acc.account_type LIKE 'expense%')
            )""")
