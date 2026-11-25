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

    def _salary_bill(self, gross=2000000.0):
        return self.env['account.move'].with_company(self.company).create({
            'move_type': 'in_invoice', 'company_id': self.company.id,
            'partner_id': self.employee.work_contact_id.id,
            'invoice_date': '2026-11-25',
            'invoice_line_ids': [(0, 0, {'name': "Gaji November", 'price_unit': gross,
                                         'tax_ids': [(6, 0, [])]})],
        })

    def test_kasbon_paid_through_salary(self):
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
            bill = self._salary_bill()
            self.assertTrue(bill.dkm_kasbon_available)
            bill.action_dkm_add_kasbon_deduction()
            self.assertFalse(bill.dkm_kasbon_available)
            self.assertEqual(bill.amount_total, 1500000.0)
            bill.action_post()
            self.assertEqual(kasbon.paid_count, month + 1)
        self.assertEqual(kasbon.residual, 0.0)
        self.assertEqual(kasbon.state, 'paid')

        # Paid off: a new kasbon is allowed.
        self._kasbon(300000.0, 1).action_submit()

    def test_reset_salary_bill_restores_kasbon(self):
        kasbon = self._kasbon(1000000.0, 2)
        kasbon.action_submit()
        kasbon.action_disburse()
        bill = self._salary_bill()
        bill.action_dkm_add_kasbon_deduction()
        bill.action_post()
        self.assertEqual(kasbon.residual, 500000.0)
        bill.button_draft()
        self.assertEqual(kasbon.residual, 1000000.0)

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
