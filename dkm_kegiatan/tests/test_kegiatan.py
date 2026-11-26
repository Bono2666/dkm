# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestKegiatan(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('id_ID')
        cls.company = cls.env['res.company'].create({
            'name': "Masjid Kegiatan",
            'country_id': cls.env.ref('base.id').id,
            'currency_id': cls.env.ref('base.IDR').id,
        })
        cls.env.user.company_ids |= cls.company
        cls.env['account.chart.template'].try_loading('id', cls.company, install_demo=False)
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.company = cls.company
        cls.fund_kegiatan = cls.env.ref('dkm_kegiatan.fund_kegiatan')
        cls.fund_umum = cls.env.ref('dkm_masjid.fund_umum')
        cls.division = cls.env['dkm.division'].create({
            'name': "Dakwah Kegiatan", 'head_id': cls.env.user.id})
        cls.activity = cls.env['dkm.activity'].create({
            'name': "Qurban 1447 H", 'company_id': cls.company.id,
            'date_start': '2026-05-01', 'date_end': '2026-05-31',
            'division_id': cls.division.id,
            'budget_line_ids': [
                (0, 0, {'type': 'income', 'name': "Donasi Sapi", 'planned_amount': 21000000.0}),
                (0, 0, {'type': 'expense', 'name': "Hewan Qurban", 'planned_amount': 20000000.0}),
                (0, 0, {'type': 'expense', 'name': "Konsumsi Panitia", 'planned_amount': 1000000.0}),
            ],
        })
        cls.activity.action_open()
        cls.donor = cls.env['res.partner'].create({'name': "Hamba Allah"})
        cls.vendor = cls.env['res.partner'].create({'name': "Peternak Uji"})

    def _category(self, name):
        return self.env['product.product'].search([
            ('name', '=', name), ('company_id', '=', self.company.id)])

    def _budget(self, name):
        return self.activity.budget_line_ids.filtered(lambda b: b.name == name)

    def _receipt(self, amount, budget=None):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.donor.id,
            'dkm_activity_id': self.activity.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self._category("Donasi Kegiatan").id, 'price_unit': amount,
                'dkm_activity_budget_id': budget.id if budget else False})],
        })
        move.action_post()
        return move

    def _bill(self, amount, budget, fund=None):
        form = Form(self.env['account.move'].with_context(default_move_type='in_invoice'))
        form.partner_id = self.vendor
        form.invoice_date = fields.Date.today()
        form.dkm_division_id = self.division
        form.dkm_activity_id = self.activity
        self.assertEqual(form.dkm_fund_id, self.fund_kegiatan)   # default for activities
        if fund:
            form.dkm_fund_id = fund
        with form.invoice_line_ids.new() as line:
            line.name = budget.name
            line.price_unit = amount
            line.dkm_activity_budget_id = budget
        bill = form.save()
        bill.action_post()
        return bill

    def test_category_and_fund(self):
        category = self._category("Donasi Kegiatan")
        self.assertEqual(category.property_account_income_id.code, '41000050')
        self.assertEqual(category.dkm_fund_id, self.fund_kegiatan)
        self.env['dkm.masjid.setup']._setup_activity_category()     # idempotent
        self.assertEqual(len(self._category("Donasi Kegiatan")), 1)

    def test_activity_budget_and_report(self):
        receipt = self._receipt(15000000.0, self._budget("Donasi Sapi"))
        self.assertEqual(receipt.invoice_line_ids.dkm_activity_id, self.activity)
        self.assertEqual(receipt.invoice_line_ids.dkm_fund_id, self.fund_kegiatan)
        self._receipt(500000.0)         # no pos: "Donasi Kegiatan" row in the PDF
        self._bill(18000000.0, self._budget("Hewan Qurban"))
        # The DKM tops up the snacks from Dana Umum.
        subsidy = self._bill(1200000.0, self._budget("Konsumsi Panitia"), fund=self.fund_umum)
        self.assertEqual(subsidy.invoice_line_ids.dkm_fund_id, self.fund_umum)
        self.env.flush_all()

        activity = self.activity
        self.assertEqual(activity.amount_income, 15500000.0)
        self.assertEqual(activity.amount_expense, 19200000.0)
        self.assertEqual(activity.amount_balance, -3700000.0)
        self.assertEqual(activity.transaction_count, 4)
        self.assertEqual(activity.budget_expense, 21000000.0)
        sapi, hewan, konsumsi = (self._budget(n) for n in
                                 ("Donasi Sapi", "Hewan Qurban", "Konsumsi Panitia"))
        self.assertEqual(sapi.actual_amount, 15000000.0)
        self.assertEqual(hewan.actual_amount, 18000000.0)
        self.assertEqual(hewan.difference, 2000000.0)
        self.assertEqual(konsumsi.progress, 120.0)

        data = activity._dkm_report_data()
        self.assertEqual([(r['name'], r['actual']) for r in data['income_rows']],
                         [("Donasi Sapi", 15000000.0), ("Donasi Kegiatan", 500000.0)])
        self.assertEqual(len(data['expense_lines']), 2)

        html = str(self.env['ir.actions.report'].with_context(lang='id_ID')._render_qweb_html(
            'dkm_kegiatan.action_report_activity', activity.ids)[0])
        for text in ("Laporan Kegiatan", "Qurban 1447 H", "Hewan Qurban", "Kekurangan Dana",
                     "Divisi Dakwah Kegiatan", "Ketua DKM", "Peternak Uji"):
            self.assertIn(text, html)
        self.assertNotIn("Hamba Allah", html)   # donors are not listed

    def test_budget_belongs_to_activity(self):
        other = self.env['dkm.activity'].create({
            'name': "Ramadhan 1447 H", 'company_id': self.company.id,
            'budget_line_ids': [(0, 0, {'type': 'expense', 'name': "Takjil"})],
        })
        with self.assertRaises(ValidationError):
            self._receipt(100000.0, other.budget_line_ids)

    def test_cancel_and_done(self):
        self._receipt(100000.0)
        with self.assertRaises(UserError):
            self.activity.action_cancel()
        self.activity.action_done()
        self.assertEqual(self.activity.state, 'done')
        self.activity.action_draft()
        self.assertEqual(self.activity.state, 'open')

    def _transfer(self, user=None, **vals):
        Wizard = self.env['dkm.activity.transfer']
        if user:
            Wizard = Wizard.with_user(user)
        wizard = Wizard.with_context(default_activity_id=self.activity.id).create(vals)
        wizard.action_confirm()
        return wizard

    def test_transfer_remainder_to_dana_umum(self):
        self._receipt(1000000.0)
        self._bill(700000.0, self._budget("Hewan Qurban"))
        self._bill(200000.0, self._budget("Konsumsi Panitia"), fund=self.fund_umum)  # subsidy
        activity = self.activity
        self.assertEqual(activity.amount_balance, 100000.0)
        self.assertEqual(activity.fund_remainder, 300000.0)     # subsidy is not Dana Kegiatan

        with self.assertRaises(UserError):
            self._transfer(amount=400000.0)
        activity.action_done()
        treasurer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': "Bendahara Kegiatan", 'login': 'bdh_kegiatan',
            'company_ids': [(6, 0, self.company.ids)], 'company_id': self.company.id,
            'group_ids': [(6, 0, self.env.ref('account.group_account_invoice').ids)],
        })
        wizard = self._transfer(user=treasurer)
        self.assertEqual(wizard.amount, 300000.0)               # defaults to the remainder
        self.assertEqual(activity.fund_remainder, 0.0)
        self.assertEqual(activity.amount_transfer, -300000.0)
        self.assertEqual(activity.amount_balance, -200000.0)
        self.env.flush_all()

        Report = self.env['dkm.fund.report']
        balances = dict(Report._read_group([('company_id', '=', self.company.id)],
                                           ['fund_id'], ['balance:sum']))
        self.assertEqual(balances[self.fund_kegiatan], 0.0)
        self.assertEqual(balances[self.fund_umum], 100000.0)    # +300.000 - 200.000

        html = str(self.env['ir.actions.report'].with_context(lang='id_ID')._render_qweb_html(
            'dkm_kegiatan.action_report_activity', activity.ids)[0])
        self.assertIn("Sisa Dana yang Dipindahkan", html)

    def test_transfer_remainder_to_next_activity(self):
        self._receipt(500000.0)
        nxt = self.env['dkm.activity'].create({'name': "Qurban 1448 H",
                                               'company_id': self.company.id})
        self._transfer(target='activity', target_activity_id=nxt.id, amount=200000.0)
        self.assertEqual(self.activity.fund_remainder, 300000.0)
        self.assertEqual(nxt.amount_transfer, 200000.0)
        self.assertEqual(nxt.fund_remainder, 200000.0)
        self.assertEqual(nxt.amount_balance, 200000.0)
