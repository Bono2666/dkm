# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

KASBON_ACCOUNT_CODE = '11210060'
KASBON_JOURNAL_CODE = 'KSB'


def line_label_field(env):
    """Newer Odoo 20 builds call the journal item description "label"."""
    return 'label' if 'label' in env['account.move.line']._fields else 'name'


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _dkm_kasbon_account(self):
        """Piutang Kasbon Pegawai: a reconcilable current asset, per company."""
        self.ensure_one()
        Account = self.env['account.account'].sudo().with_company(self)
        account = Account.search([
            *Account._check_company_domain(self), ('code', '=', KASBON_ACCOUNT_CODE),
        ], limit=1)
        if not account:
            account = Account.create({
                'code': KASBON_ACCOUNT_CODE,
                'name': "Piutang Kasbon Pegawai",
                'account_type': 'asset_current',
                'reconcile': True,
                'company_ids': [(6, 0, self.ids)],
            })
        return account

    def _dkm_kasbon_journal(self):
        """Jurnal "Kasbon Pegawai": approval policies can target it alone."""
        self.ensure_one()
        Journal = self.env['account.journal'].sudo()
        journal = Journal.search([
            ('company_id', '=', self.id), ('code', '=', KASBON_JOURNAL_CODE),
        ], limit=1)
        if not journal:
            journal = Journal.create({
                'name': "Kasbon Pegawai",
                'code': KASBON_JOURNAL_CODE,
                'type': 'general',
                'company_id': self.id,
            })
        return journal


class DkmKasbon(models.Model):
    _name = 'dkm.kasbon'
    _description = "Kasbon Pegawai"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char("Nomor", readonly=True, copy=False, default="Baru")
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    employee_id = fields.Many2one(
        'hr.employee', string="Pegawai", required=True, tracking=True,
        check_company=True)
    partner_id = fields.Many2one(
        related='employee_id.work_contact_id', store=True, string="Kontak Pegawai")
    date = fields.Date("Tanggal", required=True, default=fields.Date.context_today,
                       tracking=True)
    amount = fields.Monetary("Jumlah Kasbon", required=True, tracking=True)
    installments = fields.Integer("Jumlah Cicilan", required=True, default=1,
                                  tracking=True,
                                  help="Berapa kali penggajian kasbon ini dipotong.")
    installment_amount = fields.Monetary(
        "Potongan per Gaji", compute='_compute_installment_amount', store=True)
    journal_id = fields.Many2one(
        'account.journal', string="Dibayar dari", required=True,
        default=lambda self: self._default_journal(), check_company=True,
        domain="[('type', 'in', ('cash', 'bank'))]",
        help="Kas atau rekening bank tempat uang kasbon diambil.")
    note = fields.Text("Keperluan")
    move_id = fields.Many2one('account.move', string="Entri Jurnal", readonly=True,
                              copy=False)
    move_line_id = fields.Many2one('account.move.line', readonly=True, copy=False)
    approval_state = fields.Selection(related='move_id.eh_approval_state',
                                      string="Status Persetujuan")
    requires_approval = fields.Boolean(related='move_id.eh_requires_approval')
    residual = fields.Monetary("Sisa Kasbon", compute='_compute_state', store=True)
    paid_count = fields.Integer("Cicilan Terbayar", compute='_compute_paid_count')
    state = fields.Selection([
        ('draft', "Draf"),
        ('to_approve', "Menunggu Persetujuan"),
        ('active', "Berjalan"),
        ('paid', "Lunas"),
        ('cancel', "Dibatalkan"),
    ], string="Status", compute='_compute_state', store=True, tracking=True)
    is_cancelled = fields.Boolean(copy=False, readonly=True)
    deduction_line_ids = fields.One2many(
        'account.move.line', 'dkm_kasbon_id', string="Potongan Gaji", readonly=True)

    _check_amount = models.Constraint('CHECK (amount > 0)', "Jumlah kasbon harus lebih dari 0.")
    _check_installments = models.Constraint('CHECK (installments >= 1)',
                                            "Jumlah cicilan minimal 1.")

    @api.model
    def _default_journal(self):
        journals = self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.env.company),
            ('type', 'in', ('cash', 'bank')),
        ])
        return journals.filtered(lambda j: j.type == 'cash')[:1] or journals[:1]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', "Baru") == "Baru":
                vals['name'] = self.env['ir.sequence'].next_by_code('dkm.kasbon') or "Baru"
        return super().create(vals_list)

    @api.depends('amount', 'installments', 'currency_id')
    def _compute_installment_amount(self):
        for kasbon in self:
            count = max(kasbon.installments, 1)
            kasbon.installment_amount = kasbon.currency_id.round(kasbon.amount / count) \
                if kasbon.currency_id else kasbon.amount / count

    @api.depends('move_id.state', 'move_line_id.amount_residual', 'amount', 'is_cancelled')
    def _compute_state(self):
        for kasbon in self:
            move = kasbon.move_id
            if kasbon.is_cancelled and not (move and move.state == 'posted'):
                kasbon.state, kasbon.residual = 'cancel', 0.0
            elif not move:
                kasbon.state, kasbon.residual = 'draft', kasbon.amount
            elif move.state == 'cancel':
                kasbon.state, kasbon.residual = 'cancel', 0.0
            elif move.state == 'draft':
                kasbon.state, kasbon.residual = 'to_approve', kasbon.amount
            else:
                residual = kasbon.move_line_id.amount_residual
                kasbon.residual = residual
                kasbon.state = 'paid' if kasbon.currency_id.is_zero(residual) else 'active'

    @api.depends('deduction_line_ids.parent_state')
    def _compute_paid_count(self):
        for kasbon in self:
            kasbon.paid_count = len(kasbon.deduction_line_ids.filtered(
                lambda line: line.parent_state == 'posted'))

    def _dkm_check_one_active(self):
        for kasbon in self:
            other = self.search([
                ('employee_id', '=', kasbon.employee_id.id), ('id', '!=', kasbon.id),
                ('state', 'in', ('to_approve', 'active')),
            ], limit=1)
            if other:
                raise UserError(
                    f"{kasbon.employee_id.name} masih punya kasbon {other.name} yang "
                    f"belum lunas. Kasbon baru bisa diajukan setelah kasbon itu lunas.")

    def action_submit(self):
        """Record the disbursement as a draft entry and ask for approval."""
        for kasbon in self.filtered(lambda k: k.state == 'draft'):
            kasbon._dkm_check_one_active()
            if not kasbon.partner_id:
                raise UserError("Pegawai ini belum punya kontak kerja.")
            company = kasbon.company_id
            account = company._dkm_kasbon_account()
            cash_account = kasbon.journal_id.default_account_id
            label = f"Kasbon {kasbon.employee_id.name} ({kasbon.name})"
            fname = line_label_field(self.env)
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': company._dkm_kasbon_journal().id,
                'date': kasbon.date,
                'ref': label,
                'company_id': company.id,
                'line_ids': [
                    (0, 0, {'account_id': account.id, 'partner_id': kasbon.partner_id.id,
                            'debit': kasbon.amount, fname: label}),
                    (0, 0, {'account_id': cash_account.id, 'partner_id': kasbon.partner_id.id,
                            'credit': kasbon.amount, fname: label}),
                ],
            })
            kasbon.write({
                'move_id': move.id,
                'move_line_id': move.line_ids.filtered(lambda l: l.account_id == account).id,
            })
            if move.eh_requires_approval:
                move.action_eh_request_approval()
        return True

    def action_disburse(self):
        """Post the entry once approved: the money leaves the cash/bank."""
        for kasbon in self.filtered(lambda k: k.state == 'to_approve'):
            kasbon._dkm_check_one_active()
            kasbon.move_id.action_post()
        return True

    def action_cancel(self):
        for kasbon in self:
            if kasbon.state in ('active', 'paid'):
                raise UserError("Kasbon yang sudah dicairkan tidak bisa dibatalkan.")
            if kasbon.move_id and kasbon.move_id.state == 'draft':
                request = kasbon.move_id.eh_active_approval_request_id
                if request and request.state in ('pending', 'in_review'):
                    request.action_withdraw("Kasbon dibatalkan")
                kasbon.move_id.button_cancel()
            kasbon.is_cancelled = True
        return True

    def action_view_approval(self):
        self.ensure_one()
        return self.move_id.action_eh_view_approval_request()

    def unlink(self):
        if any(kasbon.move_id for kasbon in self):
            raise UserError("Kasbon yang sudah diajukan tidak bisa dihapus; batalkan saja.")
        return super().unlink()
