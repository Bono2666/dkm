# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKasbon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('id_ID')
        cls.company = cls.env['res.company'].create({
            'name': "Masjid Kasbon",
            'country_id': cls.env.ref('base.id').id,
            'currency_id': cls.env.ref('base.IDR').id,
        })
        cls.env.user.company_ids |= cls.company
        cls.env['account.chart.template'].try_loading('id', cls.company, install_demo=False)
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.company = cls.company
        cls.employee = cls.env['hr.employee'].create({'name': "Pak Marbot", 'company_id': cls.company.id})
        cls.cash = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id), ('type', '=', 'cash')], limit=1)

    def _kasbon(self, amount=1500000.0, installments=3):
        return self.env['dkm.kasbon'].with_company(self.company).create({
            'employee_id': self.employee.id, 'amount': amount,
            'installments': installments, 'journal_id': self.cash.id,
            'company_id': self.company.id,
        })

    def _payroll(self, wage=2000000.0, employees=None):
        employees = employees or self.employee
        return self.env['dkm.payroll'].with_company(self.company).create({
            'date': '2026-11-25', 'company_id': self.company.id,
            'journal_id': self.cash.id,
            'line_ids': [(0, 0, {'employee_id': e.id, 'wage': wage}) for e in employees],
        })

    def _pay(self, payroll):
        action = payroll.action_pay()
        self.env['account.payment.register'].with_context(**action['context']).create(
            {}).action_create_payments()

    def test_kasbon_paid_through_payroll(self):
        kasbon = self._kasbon()
        self.assertEqual(kasbon.installment_amount, 500000.0)
        self.assertTrue(kasbon.name.startswith('KASBON/'))
        kasbon.action_submit()
        self.assertEqual(kasbon.state, 'to_approve')   # no policy: disburse directly
        kasbon.action_disburse()
        self.assertEqual(kasbon.state, 'active')
        self.assertEqual(kasbon.residual, 1500000.0)
        account = self.company._dkm_kasbon_account()
        self.assertEqual(kasbon.move_line_id.account_id, account)
        self.assertEqual(kasbon.move_id.journal_id.code, 'KSB')

        # Only one running kasbon per employee.
        with self.assertRaises(UserError):
            self._kasbon(300000.0, 1).action_submit()

        for month in range(3):
            payroll = self._payroll()
            self.assertEqual(payroll.name, "Gaji November 2026")
            line = payroll.line_ids
            self.assertEqual(line.kasbon_id, kasbon)
            self.assertEqual(line.deduction, 500000.0)
            self.assertEqual(payroll.amount_gross, 2000000.0)
            self.assertEqual(payroll.amount_net, 1500000.0)
            payroll.action_submit()
            self.assertEqual(payroll.state, 'to_approve')
            self.assertEqual(payroll.move_id.journal_id.code, 'GAJI')
            payroll.action_post()
            self.assertEqual(payroll.state, 'posted')
            self.assertEqual(kasbon.paid_count, month + 1)
            self._pay(payroll)
            self.assertEqual(payroll.state, 'paid')
        self.assertEqual(kasbon.residual, 0.0)
        self.assertEqual(kasbon.state, 'paid')

        # Paid off: no deduction any more, and a new kasbon is allowed.
        self.assertFalse(self._payroll().line_ids.kasbon_id)
        self._kasbon(300000.0, 1).action_submit()

    def test_reset_payroll_restores_kasbon(self):
        kasbon = self._kasbon(1000000.0, 2)
        kasbon.action_submit()
        kasbon.action_disburse()
        payroll = self._payroll()
        payroll.action_submit()
        payroll.action_post()
        self.assertEqual(kasbon.residual, 500000.0)
        payroll.move_id.button_draft()
        self.assertEqual(kasbon.residual, 1000000.0)

    def test_fill_employees(self):
        other = self.env['hr.employee'].create({'name': "Pak Imam", 'company_id': self.company.id})
        payroll = self._payroll()
        payroll.action_fill_employees()
        self.assertEqual(payroll.line_ids.employee_id, self.employee | other)
        with self.assertRaises(UserError):     # Pak Imam has no gaji yet
            payroll.action_submit()
        payroll.line_ids.filtered(lambda l: l.employee_id == other).wage = 1000000.0
        payroll.action_submit()
        payroll.action_post()
        # Next month starts from last month's amounts.
        nxt = self.env['dkm.payroll'].create({'date': '2026-12-25', 'company_id': self.company.id})
        nxt.action_fill_employees()
        self.assertEqual(nxt.name, "Gaji Desember 2026")
        wages = {l.employee_id: l.wage for l in nxt.line_ids}
        self.assertEqual(wages, {self.employee: 2000000.0, other: 1000000.0})

    def test_payroll_approved_once(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        groups = (self.env.ref('account.group_account_invoice')
                  | self.env.ref('eh_account_base.group_eh_user'))
        common = {'company_ids': [(6, 0, self.company.ids)], 'company_id': self.company.id,
                  'group_ids': [(6, 0, groups.ids)]}
        heads = Users.browse()
        for login in ('gkadiv1', 'gketua1'):
            heads |= Users.create({'name': login, 'login': login, **common})
        self.env['eh.approval.policy'].create({
            'name': "Persetujuan Penggajian", 'company_id': self.company.id,
            'document_type': 'entry', 'entry_origin': 'manual',
            'journal_ids': [(6, 0, self.company._dkm_payroll_journal().ids)],
            'rule_ids': [(0, 0, {'name': "Semua", 'min_amount': 0.0, 'max_amount': 0.0,
                                 'step_ids': [(0, 0, {'approver_ids': [(6, 0, heads.ids)],
                                                      'approval_minimum': len(heads)})]})],
        })
        other = self.env['hr.employee'].create({'name': "Pak Imam", 'company_id': self.company.id})
        payroll = self._payroll(1500000.0, self.employee | other)
        payroll.action_submit()
        request = payroll.move_id.eh_active_approval_request_id
        self.assertEqual(payroll.approval_state, 'in_review')
        self.assertEqual(request.submitted_amount, 3000000.0)   # one request, the total
        self.assertFalse(payroll.editable)
        with self.assertRaises(UserError):
            payroll.action_post()

        # Rejected: fix the amounts and submit again.
        request.with_user(heads[0]).action_reject("Gaji imam belum naik")
        self.assertTrue(payroll.editable)
        self.assertEqual(payroll.last_approval_state, 'rejected')
        payroll.line_ids.filtered(lambda l: l.employee_id == other).wage = 2000000.0
        payroll.action_submit()
        request = payroll.move_id.eh_active_approval_request_id
        self.assertEqual(request.submitted_amount, 3500000.0)
        for head in heads:
            request.with_user(head).action_approve("Setuju")
        self.assertEqual(payroll.approval_state, 'approved')
        payroll.action_post()
        self.assertEqual(payroll.state, 'posted')
        self._pay(payroll)
        self.assertEqual(payroll.state, 'paid')

    def test_salary_bill_blocked(self):
        Account = self.env['account.account'].with_company(self.company)
        domain = Account._check_company_domain(self.company)
        salary = Account.search([*domain, ('code', '=', '61100010')], limit=1)
        supplies = Account.search([*domain, ('code', '=', '66110000')], limit=1)

        def bill(account):
            return self.env['account.move'].with_company(self.company).create({
                'move_type': 'in_invoice', 'company_id': self.company.id,
                'partner_id': self.employee.work_contact_id.id,
                'invoice_date': '2026-11-25',
                'invoice_line_ids': [(0, 0, {'name': "Uji", 'price_unit': 100000.0,
                                             'account_id': account.id,
                                             'tax_ids': [(6, 0, [])]})],
            })
        with self.assertRaises(UserError):
            bill(salary).action_post()
        reimburse = bill(supplies)     # other expenses for an employee are fine
        reimburse.action_post()
        self.assertEqual(reimburse.state, 'posted')

    def test_approval_by_all_heads(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        groups = (self.env.ref('account.group_account_invoice')
                  | self.env.ref('eh_account_base.group_eh_user'))
        common = {'company_ids': [(6, 0, self.company.ids)], 'company_id': self.company.id,
                  'group_ids': [(6, 0, groups.ids)]}
        heads = Users.browse()
        for login in ('kadiv1', 'kadiv2', 'ketua1'):
            heads |= Users.create({'name': login, 'login': login, **common})
        self.env['eh.approval.policy'].create({
            'name': "Persetujuan Kasbon", 'company_id': self.company.id,
            'document_type': 'entry', 'entry_origin': 'manual',
            'journal_ids': [(6, 0, self.company._dkm_kasbon_journal().ids)],
            'rule_ids': [(0, 0, {'name': "Semua", 'min_amount': 0.0, 'max_amount': 0.0,
                                 'step_ids': [(0, 0, {'approver_ids': [(6, 0, heads.ids)],
                                                      'approval_minimum': len(heads)})]})],
        })
        kasbon = self._kasbon()
        kasbon.action_submit()
        self.assertTrue(kasbon.requires_approval)
        self.assertEqual(kasbon.approval_state, 'in_review')
        with self.assertRaises(UserError):
            kasbon.action_disburse()
        request = kasbon.move_id.eh_active_approval_request_id
        for head in heads[:-1]:
            request.with_user(head).action_approve("Setuju")
        self.assertNotEqual(request.state, 'approved')
        request.with_user(heads[-1]).action_approve("Setuju")
        self.assertEqual(request.state, 'approved')
        kasbon.action_disburse()
        self.assertEqual(kasbon.state, 'active')

    def test_payroll_spends_from_fund(self):
        umum = self.env.ref('dkm_masjid.fund_umum')
        payroll = self._payroll()
        self.assertEqual(payroll.fund_id, self.env.ref('dkm_masjid.fund_operasional'))
        payroll.fund_id = umum
        payroll.action_submit()
        payroll.action_post()
        expense = payroll.move_id.line_ids.filtered(lambda l: l.debit)
        self.assertEqual(expense.dkm_fund_id, umum)
