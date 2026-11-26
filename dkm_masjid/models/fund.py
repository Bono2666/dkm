# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class DkmFund(models.Model):
    """Sumber Dana: Operasional, Dana Umum, Zakat, Wakaf. Receipts add to a
    fund (by their category), bills spend from one; Saldo Dana shows what is
    left in each."""
    _name = 'dkm.fund'
    _description = "Sumber Dana"
    _order = 'sequence, id'

    name = fields.Char("Sumber Dana", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Text("Keterangan", translate=True)

    _name_unique = models.Constraint('UNIQUE (name)', "Sumber dana sudah ada.")

    @api.model
    def _dkm_default(self):
        return self.env.ref('dkm_masjid.fund_operasional', raise_if_not_found=False) \
            or self.search([], limit=1)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dkm_fund_id = fields.Many2one(
        'dkm.fund', string="Sumber Dana",
        help="Dana yang bertambah saat kategori penerimaan ini dicatat.")


class AccountMove(models.Model):
    _inherit = 'account.move'

    dkm_fund_id = fields.Many2one(
        'dkm.fund', string="Sumber Dana", tracking=True, index='btree_not_null',
        compute='_compute_dkm_fund_id', store=True, readonly=False, precompute=True,
        help="Dana yang dipakai untuk membayar tagihan ini.")

    @api.depends('move_type')
    def _compute_dkm_fund_id(self):
        for move in self:
            if move.is_purchase_document(include_receipts=True):
                move.dkm_fund_id = move.dkm_fund_id or self.env['dkm.fund']._dkm_default()
            else:
                move.dkm_fund_id = move.dkm_fund_id


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    dkm_fund_id = fields.Many2one(
        'dkm.fund', string="Sumber Dana", index='btree_not_null',
        compute='_compute_dkm_fund_id', store=True, readonly=False, precompute=True)

    @api.depends('product_id', 'move_id.dkm_fund_id', 'display_type')
    def _compute_dkm_fund_id(self):
        for line in self:
            move = line.move_id
            if line.display_type != 'product':
                line.dkm_fund_id = line.dkm_fund_id
            elif move.is_purchase_document(include_receipts=True):
                line.dkm_fund_id = move.dkm_fund_id
            elif move.is_sale_document(include_receipts=True):
                line.dkm_fund_id = line.product_id.dkm_fund_id or line.dkm_fund_id
            else:
                line.dkm_fund_id = line.dkm_fund_id


class DkmFundReport(models.Model):
    """Posted income, expense and opening (Aset Neto) amounts per fund."""
    _name = 'dkm.fund.report'
    _description = "Saldo Dana"
    _auto = False
    _order = 'date desc, id desc'

    date = fields.Date("Tanggal", readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    fund_id = fields.Many2one('dkm.fund', string="Sumber Dana", readonly=True)
    account_id = fields.Many2one('account.account', string="Akun", readonly=True)
    move_id = fields.Many2one('account.move', string="Dokumen", readonly=True)
    partner_id = fields.Many2one('res.partner', string="Donatur/Vendor", readonly=True)
    name = fields.Char("Keterangan", readonly=True)
    opening = fields.Monetary("Saldo Awal", readonly=True)
    income = fields.Monetary("Penerimaan", readonly=True)
    expense = fields.Monetary("Pengeluaran", readonly=True)
    balance = fields.Monetary("Saldo", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        fields_ = self.env['account.move.line']._fields
        label = 'label' if 'label' in fields_ and fields_['label'].store else 'name'
        self.env.cr.execute(f"""
            CREATE VIEW {self._table} AS (
                SELECT aml.id, aml.date, aml.company_id, aml.dkm_fund_id AS fund_id,
                       aml.account_id, aml.move_id, aml.partner_id, aml.{label} AS name,
                       CASE WHEN acc.account_type LIKE 'equity%' THEN -aml.balance ELSE 0 END AS opening,
                       CASE WHEN acc.account_type LIKE 'income%' THEN -aml.balance ELSE 0 END AS income,
                       CASE WHEN acc.account_type LIKE 'expense%' THEN aml.balance ELSE 0 END AS expense,
                       -aml.balance AS balance
                  FROM account_move_line aml
                  JOIN account_account acc ON acc.id = aml.account_id
                 WHERE aml.parent_state = 'posted'
                   AND aml.dkm_fund_id IS NOT NULL
                   AND (acc.account_type LIKE 'income%' OR acc.account_type LIKE 'expense%'
                        OR (acc.account_type LIKE 'equity%'
                            AND acc.account_type != 'equity_unaffected'))
            )""")
