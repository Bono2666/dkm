# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .kasbon import line_label_field

MONTHS = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
          "Agustus", "September", "Oktober", "November", "Desember")

PAYROLL_JOURNAL_CODE = 'GAJI'
SALARY_ACCOUNT_CODE = '61100010'        # Gaji Karyawan
ALLOWANCE_ACCOUNT_CODE = '61100020'     # Bonus / Tunjangan Karyawan
SALARY_PAYABLE_CODE = '21100041'        # Hutang Gaji Pegawai


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _dkm_account_by_code(self, code):
        self.ensure_one()
        Account = self.env['account.account'].sudo().with_company(self)
        account = Account.search([*Account._check_company_domain(self), ('code', '=', code)],
                                 limit=1)
        if not account:
            raise UserError(f"Akun {code} tidak ditemukan di bagan akun.")
        return account

    def _dkm_salary_payable_account(self):
        """Hutang Gaji Pegawai: the approved net salary until it is paid."""
        self.ensure_one()
        Account = self.env['account.account'].sudo().with_company(self)
        account = Account.search([
            *Account._check_company_domain(self), ('code', '=', SALARY_PAYABLE_CODE),
        ], limit=1)
        if not account:
            account = Account.create({
                'code': SALARY_PAYABLE_CODE,
                'name': "Hutang Gaji Pegawai",
                'account_type': 'liability_payable',
                'reconcile': True,
                'company_ids': [(6, 0, self.ids)],
            })
        return account

    def _dkm_payroll_journal(self):
        """Jurnal "Penggajian": the monthly payroll approval policy targets it."""
        self.ensure_one()
        Journal = self.env['account.journal'].sudo()
        journal = Journal.search([
            ('company_id', '=', self.id), ('code', '=', PAYROLL_JOURNAL_CODE),
        ], limit=1)
        if not journal:
            journal = Journal.create({
                'name': "Penggajian",
                'code': PAYROLL_JOURNAL_CODE,
                'type': 'general',
                'company_id': self.id,
            })
        return journal


class DkmPayroll(models.Model):
    """One month of salaries, approved once as a total and then paid per
    employee. Kasbon installments are deducted automatically."""
    _name = 'dkm.payroll'
    _description = "Penggajian"
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char("Nama", required=True, compute="_compute_name", store=True, precompute=True,
                       readonly=False, tracking=True)
    date = fields.Date("Tanggal Gaji", required=True, default=fields.Date.context_today,
                       tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    journal_id = fields.Many2one(
        'account.journal', string="Dibayar dari", required=True,
        default=lambda self: self.env['dkm.kasbon']._default_journal(),
        check_company=True, domain="[('type', 'in', ('cash', 'bank'))]",
        help="Kas atau rekening bank yang dipakai saat gaji dibayarkan.")
    line_ids = fields.One2many('dkm.payroll.line', 'payroll_id', string="Pegawai",
                               copy=True)
    note = fields.Text("Catatan")
    employee_count = fields.Integer("Jumlah Pegawai", compute='_compute_amounts', store=True)
    amount_gross = fields.Monetary("Total Biaya Gaji", compute='_compute_amounts', store=True)
    amount_deduction = fields.Monetary("Potongan Kasbon", compute='_compute_amounts',
                                       store=True)
    amount_net = fields.Monetary("Total Dibayarkan", compute='_compute_amounts', store=True)
    move_id = fields.Many2one('account.move', string="Entri Jurnal", readonly=True,
                              copy=False)
    approval_state = fields.Selection(related='move_id.eh_approval_state',
                                      string="Status Persetujuan")
    requires_approval = fields.Boolean(related='move_id.eh_requires_approval')
    last_approval_state = fields.Char(compute='_compute_last_approval_state')
    editable = fields.Boolean(compute='_compute_editable')
    is_cancelled = fields.Boolean(copy=False, readonly=True)
    state = fields.Selection([
        ('draft', "Draf"),
        ('to_approve', "Menunggu Persetujuan"),
        ('posted', "Siap Dibayar"),
        ('paid', "Lunas"),
        ('cancel', "Dibatalkan"),
    ], string="Status", compute='_compute_state', store=True, tracking=True)

    @api.depends('date')
    def _compute_name(self):
        for payroll in self:
            if payroll.date:
                payroll.name = f"Gaji {MONTHS[payroll.date.month - 1]} {payroll.date.year}"
            elif not payroll.name:
                payroll.name = "Gaji"

    @api.depends('line_ids.gross', 'line_ids.deduction', 'line_ids.net')
    def _compute_amounts(self):
        for payroll in self:
            payroll.employee_count = len(payroll.line_ids)
            payroll.amount_gross = sum(payroll.line_ids.mapped('gross'))
            payroll.amount_deduction = sum(payroll.line_ids.mapped('deduction'))
            payroll.amount_net = sum(payroll.line_ids.mapped('net'))

    @api.depends('move_id.state', 'move_id.line_ids.amount_residual', 'is_cancelled')
    def _compute_state(self):
        for payroll in self:
            move = payroll.move_id
            if payroll.is_cancelled and not (move and move.state == 'posted'):
                payroll.state = 'cancel'
            elif not move:
                payroll.state = 'draft'
            elif move.state == 'cancel':
                payroll.state = 'cancel'
            elif move.state == 'draft':
                payroll.state = 'to_approve'
            else:
                unpaid = payroll._dkm_payable_lines().filtered(lambda l: not l.reconciled)
                payroll.state = 'posted' if unpaid else 'paid'

    @api.depends('move_id')
    def _compute_last_approval_state(self):
        for payroll in self:
            requests = payroll.move_id.sudo().eh_approval_request_ids.sorted('id')
            payroll.last_approval_state = requests[-1:].state or False

    @api.depends('state', 'approval_state')
    def _compute_editable(self):
        for payroll in self:
            payroll.editable = payroll.state == 'draft' or (
                payroll.state == 'to_approve' and not payroll.approval_state)

    def _dkm_payable_lines(self):
        self.ensure_one()
        if not self.move_id:
            return self.env['account.move.line']
        payable = self.company_id._dkm_salary_payable_account()
        return self.move_id.line_ids.filtered(lambda l: l.account_id == payable)

    # ---- actions ----

    def action_fill_employees(self):
        """Add every active employee not yet listed (gaji from the employee's
        wage or their last payroll)."""
        for payroll in self.filtered('editable'):
            employees = self.env['hr.employee'].search([
                ('company_id', 'in', (payroll.company_id.id, False)),
            ]) - payroll.line_ids.employee_id
            payroll.write({'line_ids': [(0, 0, {'employee_id': e.id}) for e in employees]})
        return True

    def _dkm_check_lines(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError("Tambahkan pegawai yang digaji terlebih dahulu.")
        for line in self.line_ids:
            if not line.employee_id.work_contact_id:
                raise UserError(f"{line.employee_id.name} belum punya kontak kerja.")
            if line.gross <= 0:
                raise UserError(f"Isi gaji {line.employee_id.name}.")
            if line.kasbon_id and line.currency_id.compare_amounts(
                    line.deduction, line.kasbon_id.residual) > 0:
                raise UserError(
                    f"Potongan kasbon {line.employee_id.name} melebihi sisa kasbon "
                    f"{line.kasbon_id.name}.")

    def _dkm_sync_move(self):
        """Write the payroll as one entry in the Penggajian journal:
        Dr Gaji/Tunjangan, Cr Piutang Kasbon (potongan), Cr Hutang Gaji (netto)."""
        self.ensure_one()
        company = self.company_id
        salary = company._dkm_account_by_code(SALARY_ACCOUNT_CODE)
        payable = company._dkm_salary_payable_account()
        fname = line_label_field(self.env)
        items = []
        for line in self.line_ids:
            partner = line.employee_id.work_contact_id.id
            label = f"{self.name} - {line.employee_id.name}"
            items.append((0, 0, {'account_id': salary.id, 'partner_id': partner,
                                 'debit': line.wage, fname: label}))
            if line.allowance:
                allowance = company._dkm_account_by_code(ALLOWANCE_ACCOUNT_CODE)
                items.append((0, 0, {'account_id': allowance.id, 'partner_id': partner,
                                     'debit': line.allowance,
                                     fname: f"Tunjangan {label}"}))
            if line.deduction:
                kasbon = line.kasbon_id
                items.append((0, 0, {
                    'account_id': company._dkm_kasbon_account().id, 'partner_id': partner,
                    'credit': line.deduction, 'dkm_kasbon_id': kasbon.id,
                    fname: f"Potongan kasbon {kasbon.name} (cicilan "
                           f"{kasbon.paid_count + 1} dari {kasbon.installments})",
                }))
            if line.net:
                items.append((0, 0, {'account_id': payable.id, 'partner_id': partner,
                                     'credit': line.net, fname: label}))
        vals = {'date': self.date, 'ref': self.name}
        if self.move_id:
            self.move_id.write({**vals, 'line_ids': [(5, 0, 0)] + items})
        else:
            self.move_id = self.env['account.move'].create({
                **vals, 'move_type': 'entry', 'company_id': company.id,
                'journal_id': company._dkm_payroll_journal().id, 'line_ids': items,
            })

    def action_submit(self):
        """Ask for approval of the month's total (again, after a rejection)."""
        for payroll in self.filtered('editable'):
            payroll.line_ids._dkm_refresh_kasbon()
            payroll._dkm_check_lines()
            payroll._dkm_sync_move()
            if payroll.move_id.eh_requires_approval:
                payroll.move_id.action_eh_request_approval()
        return True

    def action_post(self):
        """Book the approved payroll; kasbon deductions are settled."""
        for payroll in self.filtered(lambda p: p.state == 'to_approve'):
            if payroll.editable:
                payroll._dkm_check_lines()
                payroll._dkm_sync_move()
            payroll.move_id.action_post()
        return True

    def action_pay(self):
        """Pay every employee's net salary (one payment per employee)."""
        self.ensure_one()
        lines = self._dkm_payable_lines().filtered(lambda l: not l.reconciled)
        if not lines:
            raise UserError("Semua gaji pada penggajian ini sudah dibayar.")
        return lines.action_register_payment(ctx={
            'default_journal_id': self.journal_id.id,
            'dont_redirect_to_payments': True,
        })

    def action_cancel(self):
        for payroll in self:
            if payroll.state in ('posted', 'paid'):
                raise UserError("Penggajian yang sudah dikonfirmasi tidak bisa dibatalkan.")
            move = payroll.move_id
            if move and move.state == 'draft':
                request = move.eh_active_approval_request_id
                if request and request.state in ('pending', 'in_review'):
                    request.action_withdraw("Penggajian dibatalkan")
                move.button_cancel()
            payroll.is_cancelled = True
        return True

    def action_view_approval(self):
        self.ensure_one()
        return self.move_id.action_eh_view_approval_request()

    def action_view_payments(self):
        self.ensure_one()
        payments = self._dkm_payable_lines().matched_debit_ids.debit_move_id.payment_id
        return {
            'type': 'ir.actions.act_window', 'name': "Pembayaran Gaji",
            'res_model': 'account.payment', 'view_mode': 'list,form',
            'domain': [('id', 'in', payments.ids)],
        }

    def unlink(self):
        if any(payroll.move_id for payroll in self):
            raise UserError("Penggajian yang sudah diajukan tidak bisa dihapus; batalkan saja.")
        return super().unlink()


class DkmPayrollLine(models.Model):
    _name = 'dkm.payroll.line'
    _description = "Gaji Pegawai"
    _order = 'payroll_id, id'

    payroll_id = fields.Many2one('dkm.payroll', required=True, ondelete='cascade',
                                 index=True)
    company_id = fields.Many2one(related='payroll_id.company_id', store=True)
    currency_id = fields.Many2one(related='payroll_id.currency_id')
    employee_id = fields.Many2one('hr.employee', string="Pegawai", required=True,
                                  check_company=True)
    wage = fields.Monetary("Gaji", compute='_compute_wage', store=True, readonly=False,
                           precompute=True)
    allowance = fields.Monetary("Tunjangan")
    gross = fields.Monetary("Jumlah", compute='_compute_net', store=True)
    kasbon_id = fields.Many2one('dkm.kasbon', string="Kasbon", compute='_compute_kasbon',
                                store=True, readonly=False, precompute=True,
                                domain="[('employee_id', '=', employee_id), "
                                       "('state', '=', 'active')]")
    deduction = fields.Monetary("Potongan Kasbon", compute='_compute_kasbon', store=True,
                                readonly=False, precompute=True)
    net = fields.Monetary("Diterima", compute='_compute_net', store=True)

    _employee_unique = models.Constraint('UNIQUE (payroll_id, employee_id)',
                                         "Pegawai ini sudah ada di penggajian.")

    @api.depends('employee_id')
    def _compute_wage(self):
        for line in self:
            employee = line.employee_id.sudo()
            if not employee:
                continue
            last = self.search([
                ('employee_id', '=', employee.id), ('payroll_id.state', '!=', 'cancel'),
                ('id', 'not in', line._origin.ids),
            ], order='id desc', limit=1)
            line.wage = employee.wage or last.wage or line.wage

    @api.depends('employee_id')
    def _compute_kasbon(self):
        for line in self:
            kasbon = line._dkm_active_kasbon()
            line.kasbon_id = kasbon
            line.deduction = min(kasbon.installment_amount, kasbon.residual) if kasbon else 0.0

    @api.depends('wage', 'allowance', 'deduction')
    def _compute_net(self):
        for line in self:
            line.gross = line.wage + line.allowance
            line.net = line.gross - line.deduction

    @api.constrains('wage', 'allowance', 'deduction')
    def _check_amounts(self):
        for line in self:
            if line.wage < 0 or line.allowance < 0 or line.deduction < 0:
                raise ValidationError("Jumlah gaji, tunjangan dan potongan tidak boleh negatif.")
            if line.deduction > line.wage + line.allowance:
                raise ValidationError(
                    f"Potongan kasbon {line.employee_id.name} melebihi gajinya.")

    def _dkm_active_kasbon(self):
        self.ensure_one()
        if not self.employee_id:
            return self.env['dkm.kasbon']
        return self.env['dkm.kasbon'].search([
            ('employee_id', '=', self.employee_id.id), ('state', '=', 'active'),
        ], limit=1)

    def _dkm_refresh_kasbon(self):
        """A kasbon disbursed after the line was added is picked up on submit."""
        for line in self.filtered(lambda l: not l.kasbon_id):
            kasbon = line._dkm_active_kasbon()
            if kasbon:
                line.write({'kasbon_id': kasbon.id,
                            'deduction': min(kasbon.installment_amount, kasbon.residual)})
