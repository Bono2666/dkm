# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMasjid(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('id_ID')
        cls.env['dkm.masjid.setup']._apply_labels()
        cls.company = cls.env['res.company'].create({
            'name': "Masjid Uji",
            'country_id': cls.env.ref('base.id').id,
            'currency_id': cls.env.ref('base.IDR').id,
        })
        cls.env.user.company_ids |= cls.company
        cls.env['account.chart.template'].try_loading(
            'id', cls.company, install_demo=False)
        cls.cenv = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.chart = cls.cenv['account.chart.template']

    def _account(self, code):
        return self.cenv['account.account'].with_context(active_test=False).search([
            ('code', '=', code), ('company_ids', 'in', self.company.id),
        ])

    def _name_id(self, record):
        return record.with_context(lang='id_ID').name

    def test_no_vat(self):
        self.assertFalse(self.company.account_sale_tax_id)
        self.assertFalse(self.company.account_purchase_tax_id)
        self.assertFalse(self.cenv['account.tax'].search([
            ('company_id', '=', self.company.id)]))
        self.assertFalse(self.cenv['account.account'].search([
            ('company_ids', 'in', self.company.id), ('tax_ids', '!=', False)]))

    def test_journals(self):
        sale = self.chart.ref('sale')
        purchase = self.chart.ref('purchase')
        self.assertEqual(self._name_id(sale), "Penerimaan Dana")
        self.assertEqual(self._name_id(purchase), "Pengeluaran / Tagihan")
        self.assertEqual(purchase.default_account_id.code, '61200010')
        self.assertFalse(self.chart.ref('inventory_valuation').active)

    def test_accounts(self):
        for code in ('41000020', '41000030', '41000040', '61200010'):
            self.assertEqual(len(self._account(code)), 1, code)
        self.assertEqual(self._name_id(self._account('41000010')),
                         "Penerimaan Infaq & Sedekah")
        self.assertEqual(self._name_id(self._account('99999900')),
                         "Surplus (Defisit) Tahun Berjalan")
        self.assertEqual(self._name_id(self._account('31100020')),
                         "Aset Neto Tidak Terikat")
        for code in ('51000010', '42000060', '42000070', '31100040'):
            self.assertFalse(self._account(code).active, code)
        company = self.company.with_company(self.company)
        self.assertEqual(company.expense_account_id.code, '61200010')

    def test_setup_is_idempotent(self):
        self.env['dkm.masjid.setup']._setup_accounting(self.company)
        for code in ('41000020', '61200010'):
            self.assertEqual(len(self._account(code)), 1, code)

    def test_indonesian_labels(self):
        menu = self.env.ref('account.menu_finance_receivables')
        self.assertEqual(self._name_id(menu), "Penerimaan")
        self.assertEqual(
            self._name_id(self.env.ref('account.menu_account_supplier')),
            "Pemasok")
        self.assertEqual(
            self._name_id(self.env.ref('base.menu_action_res_company_form')),
            "Masjid")
        assets = self.env.ref(
            'base_accounting_kit.account_financial_report_assets0')
        self.assertEqual(self._name_id(assets), "Aset")

    def test_sales_menus_admin_only(self):
        manager = self.env.ref('account.group_account_manager')
        for xmlid in ('account.menu_action_move_out_invoice_type',
                      'account.menu_action_move_out_refund_type',
                      'account.product_product_menu_sellable',
                      'account.product_product_menu_purchasable',
                      'base_accounting_kit.customer_statements_menu',
                      'base_accounting_kit.menu_account_recurring_invoice',
                      'base_accounting_kit.account_recurring_payments_child1'):
            self.assertEqual(self.env.ref(xmlid).group_ids, manager, xmlid)

    def test_balance_sheet_with_indonesian_labels(self):
        """base_accounting_kit picks balance-sheet accounts by the English
        line names; Indonesian labels (which replace the source term when
        en_US is not installed) must not empty the Assets line."""
        cash = self._account('11110001')
        income = self._account('41000010')
        move = self.cenv['account.move'].create({
            'journal_id': self.chart.ref('general').id,
            'line_ids': [
                (0, 0, {'account_id': cash.id, 'debit': 1000000.0}),
                (0, 0, {'account_id': income.id, 'credit': 1000000.0}),
            ],
        })
        move.action_post()
        self.env.flush_all()  # the report reads move lines with raw SQL

        report = self.env.ref(
            'base_accounting_kit.account_financial_report_balancesheet0')
        assets = self.env.ref(
            'base_accounting_kit.account_financial_report_assets0')
        wizard = self.cenv['financial.report'].with_context(
            lang='id_ID', company_id=self.company.id, state='posted')
        res = wizard._compute_report_balance(report._get_children_by_order())
        self.assertAlmostEqual(res[assets.id]['balance'], 1000000.0)

    def test_dashboard_labels(self):
        Journal = self.cenv['account.journal'].with_context(lang='id_ID')
        names = {card['id']: card['name']
                 for card in Journal.get_account_dashboard_kpis()}
        self.assertEqual(names.get('invoices'), "Penerimaan")
        self.assertNotIn("Faktur", " ".join(names.values()))
        sale = self.chart.ref('sale')
        self.assertEqual(sale._get_onboarding_action_data()['title'],
                         "Pengaturan Keuangan")
        arch = Journal.get_views(
            [(self.env.ref('account.account_journal_dashboard_kanban_view').id,
              'kanban')])['views']['kanban']['arch']
        self.assertIn("Catat penerimaan dana masjid", arch)
        self.assertNotIn("electronic invoices", arch)
        self.assertEqual(
            self._name_id(self.env.ref('account.menu_finance')), "Keuangan")

    def test_admin_only_apps(self):
        admin = self.env.ref('base.group_system')
        for xmlid in ('contacts.menu_contacts',
                      'spreadsheet_dashboard.spreadsheet_dashboard_menu_root',
                      'base.menu_management'):
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                self.assertEqual(menu.group_ids, admin, xmlid)
        bendahara = self.env['res.users'].create({
            'name': "Bendahara Uji", 'login': 'bendahara_uji',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('account.group_account_user').id,
            ])],
        })
        visible = self.env['ir.ui.menu'].with_user(bendahara)._visible_menu_ids()
        self.assertIn(self.env.ref('account.menu_finance').id, visible)
        for xmlid in ('account.menu_action_account_payments_receivable',
                      'account.menu_account_customer',
                      'account.menu_action_move_in_invoice_type'):
            self.assertIn(self.env.ref(xmlid).id, visible, xmlid)
        for xmlid in ('base_accounting_kit.customer_statements_menu',
                      'account.product_product_menu_purchasable'):
            self.assertNotIn(self.env.ref(xmlid).id, visible, xmlid)
        contacts = self.env.ref('contacts.menu_contacts', raise_if_not_found=False)
        if contacts:
            self.assertNotIn(contacts.id, visible)
