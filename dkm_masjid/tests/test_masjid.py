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
            "Vendor")
        self.assertEqual(
            self._name_id(self.env.ref('base.menu_action_res_company_form')),
            "Masjid")
        assets = self.env.ref(
            'base_accounting_kit.account_financial_report_assets0')
        self.assertEqual(self._name_id(assets), "Aset")

    def test_sales_menus_admin_only(self):
        manager = self.env.ref('account.group_account_manager')
        for xmlid in ('account.product_product_menu_sellable',
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
        bendahara = self._bendahara('bendahara_uji')
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

    def _bendahara(self, login):
        return self.env['res.users'].create({
            'name': "Bendahara " + login, 'login': login,
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('account.group_account_user').id,
            ])],
        })

    def test_receipts_available_to_treasurer(self):
        """Nota Penerimaan (customer invoices) is the mosque receipt form:
        the treasurer sees its menu and the New button on the card."""
        from lxml import etree
        bendahara = self._bendahara('bendahara_nota')
        visible = self.env['ir.ui.menu'].with_user(bendahara)._visible_menu_ids()
        for xmlid in ('account.menu_action_move_out_invoice_type',
                      'account.menu_action_move_out_refund_type'):
            self.assertIn(self.env.ref(xmlid).id, visible, xmlid)
        self.assertEqual(self._name_id(self.env.ref(
            'account.menu_action_move_out_invoice_type')), "Nota Penerimaan")
        view = self.env.ref('account.account_journal_dashboard_kanban_view')
        arch = etree.fromstring(self.env['account.journal'].with_user(
            bendahara).get_views([(view.id, 'kanban')])['views']['kanban']['arch'])
        self.assertTrue(arch.xpath(
            "//div[@name='kanban_primary_left']"
            "/t[@t-if=\"journal_type == 'sale'\"]"
            "/button[@name='action_create_new']"))

    def _category(self, name):
        return self.cenv['product.template'].search([
            ('name', '=', name), ('company_id', '=', self.company.id)])

    def test_receipt_categories(self):
        Product = self.cenv['product.template']
        for name, account_code in (("Infaq & Sedekah", '41000010'),
                                   ("Zakat", '41000020'),
                                   ("Wakaf", '41000030'),
                                   ("Sewa Fasilitas", '41000040')):
            product = self._category(name)
            self.assertEqual(len(product), 1, name)
            self.assertEqual(product.property_account_income_id.code,
                             account_code, name)
            self.assertFalse(product.taxes_id, name)
            self.assertFalse(product.default_code, name)
        self.env['dkm.masjid.setup']._setup_receipt_categories(self.company)
        self.assertEqual(len(self._category("Zakat")), 1)

    def test_receipt_form(self):
        from lxml import etree
        Move = self.cenv['account.move'].with_context(
            lang='id_ID', default_move_type='out_invoice')
        arch = etree.fromstring(Move.get_views([(False, 'form')])
                                ['views']['form']['arch'])
        self.assertTrue(arch.xpath("//label[@for='partner_id'][@string='Donatur']"))
        self.assertFalse(arch.xpath("//label[@for='partner_id'][@string='Customer']"))
        self.assertTrue(arch.xpath(
            "//label[@for='invoice_date'][@string='Tanggal Penerimaan']"))
        self.assertTrue(arch.xpath(
            "//field[@name='product_id'][@string='Kategori']"))
        self.assertTrue(arch.xpath("//page[@id='invoice_tab'][@string='Rincian']"))
        out = "parent.move_type in ('out_invoice', 'out_refund')"
        lines = arch.xpath("//field[@name='invoice_line_ids']/list")[0]
        self.assertEqual(lines.xpath("field[@name='quantity']")[0]
                         .get('column_invisible'), out)
        inv = "parent.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')"
        for fname in ('discount', 'tax_ids'):
            self.assertEqual(lines.xpath(f"field[@name='{fname}']")[0]
                             .get('column_invisible'), inv, fname)
        self.assertTrue(lines.xpath("field[@name='price_unit'][@string='Nominal']"))
        self.assertTrue(arch.xpath("//span[text()='Nota Penerimaan']"))
        out_only = "move_type in ('out_invoice', 'out_refund')"
        self.assertEqual(arch.xpath("//div[label[@for='amount_residual']]")[0]
                         .get('invisible'),
                         "move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')")
        self.assertEqual(arch.xpath("//group[@name='accounting_info_group']")[0]
                         .get('invisible'), out_only)
        sale_info = arch.xpath("//group[@name='sale_info_group']")[0]
        shown = [f.get('name') for f in sale_info.xpath('field')
                 if f.get('invisible') not in ('1', 'True')]
        self.assertEqual(shown, ['ref', 'invoice_user_id'])
        self.assertTrue(arch.xpath(
            "//group[field[@name='l10n_id_coretax_document']][@invisible='1']"))
        self.assertTrue(arch.xpath(
            "//field[@name='line_ids']/list/field[@name='tax_tag_ids'][@column_invisible='True']"))

        zakat = self._category("Zakat").product_variant_id
        donor = self.cenv['res.partner'].create({'name': "Donatur Uji"})
        move = self.cenv['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': donor.id,
            'invoice_line_ids': [(0, 0, {'product_id': zakat.id,
                                         'price_unit': 2500000.0})],
        })
        self.assertEqual(move.invoice_line_ids.account_id.code, '41000020')
        self.assertEqual(move.amount_total, 2500000.0)
        self.assertEqual(move.type_name, "Nota Penerimaan")
        self.assertTrue(move.with_context(lang='id_ID').display_name
                        .startswith("Nota Penerimaan Draf"))
        self.assertEqual(
            self.env.ref('account.mt_invoice_created').with_context(
                lang='id_ID').description, "Nota Penerimaan Dibuat")

    def test_bill_form(self):
        from lxml import etree
        Move = self.cenv['account.move'].with_context(
            lang='id_ID', default_move_type='in_invoice')
        arch = etree.fromstring(Move.get_views([(False, 'form')])
                                ['views']['form']['arch'])
        self.assertTrue(arch.xpath("//span[text()='Tagihan Vendor']"))
        self.assertTrue(arch.xpath("//div[@name='dkm_bill_residual']/field[@name='amount_residual']"))
        lines = arch.xpath("//field[@name='invoice_line_ids']/list")[0]
        self.assertTrue(lines.xpath("field[@name='price_unit'][@string='Harga Satuan']"))
        self.assertEqual(lines.xpath("field[@name='asset_category_id']")[0]
                         .get('optional'), 'hide')
        header = arch.xpath("//group[@id='header_right_group']")[0]
        for fname in ('payment_reference', 'partner_bank_id'):
            self.assertEqual(header.xpath(f"field[@name='{fname}']")[0]
                             .get('invisible'), '1', fname)
        self.assertIn('in_invoice', arch.xpath("//page[@id='other_tab']")[0]
                      .get('invisible'))

        vendor = self.cenv['res.partner'].create({'name': "PLN"})
        bill = self.cenv['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_date': '2026-11-25',
            'invoice_line_ids': [(0, 0, {'name': "Listrik November",
                                         'quantity': 1,
                                         'price_unit': 450000.0})],
        })
        self.assertEqual(bill.invoice_line_ids.account_id.code, '61200010')
        self.assertEqual(bill.amount_total, 450000.0)
        self.assertEqual(bill.date, bill.invoice_date)

    def test_list_pages(self):
        from lxml import etree
        Move = self.env['account.move'].with_context(lang='id_ID')
        out = Move.with_context(default_move_type='out_invoice')
        lst = etree.fromstring(out.get_views([(False, 'list')])['views']['list']['arch'])
        self.assertEqual(lst.xpath("//field[@name='amount_untaxed_in_currency_signed']")[0]
                         .get('column_invisible'), 'True')
        self.assertIn('out_invoice', lst.xpath("//field[@name='invoice_date_due']")[0]
                      .get('column_invisible'))
        search = etree.fromstring(out.get_views([(False, 'search')])['views']['search']['arch'])
        self.assertTrue(search.xpath("//filter[@name='out_invoice'][@string='Nota Penerimaan']"))
        self.assertTrue(search.xpath("//filter[@name='out_receipt'][@invisible='1']"))
        bill_search = self.env.ref('account.view_account_bill_filter')
        arch = etree.fromstring(Move.get_view(bill_search.id, 'search')['arch'])
        self.assertTrue(arch.xpath("//filter[@name='in_invoice'][@string='Tagihan Vendor']"))

        action = self.env.ref('account.action_move_out_invoice')
        self.assertNotIn('search_default_out_receipt', action.context)
        self.assertIn('search_default_out_invoice', action.context)
        self.assertIn("Catat penerimaan dana",
                      action.with_context(lang='id_ID').help)
        self.assertNotIn("Catat penerimaan dana",
                         action.with_context(lang='en_US').help)
        donors = self.env.ref('account.res_partner_action_customer')
        self.assertIn("Hamba Allah", donors.with_context(lang='id_ID').help)

        Payment = self.env['account.payment'].with_context(lang='id_ID')
        plist = etree.fromstring(Payment.get_views([(False, 'list')])['views']['list']['arch'])
        self.assertTrue(plist.xpath("//field[@name='partner_id'][@string='Donatur']"))
        bulk = self.env.ref('base_accounting_kit.menu_account_bulk_payment')
        self.assertEqual(bulk.group_ids, self.env.ref('account.group_account_manager'))

    def test_accounting_menu_pages(self):
        def label(xmlid):
            return self.env.ref(xmlid).with_context(lang='id_ID').name
        self.assertEqual(label('base_accounting_kit.action_account_asset_asset_form'), "Aset Tetap")
        self.assertEqual(label('base_accounting_kit.management_menu'), "Aset")
        self.assertEqual(label('base_accounting_kit.menu_lock_dates'), "Tanggal Kunci")
        Asset = self.env['account.asset.asset'].with_context(lang='id_ID')
        fields = Asset.fields_get(['name', 'value', 'value_residual', 'state'],
                                  ['string', 'selection'])
        self.assertEqual(fields['name']['string'], "Nama Aset")
        self.assertEqual(fields['value']['string'], "Nilai Perolehan")
        self.assertEqual(dict(fields['state']['selection'])['open'], "Berjalan")
        action = self.env.ref('base_accounting_kit.action_account_asset_asset_form')
        self.assertIn("Catat aset tetap masjid", action.with_context(lang='id_ID').help)
        from lxml import etree
        arch = etree.fromstring(self.env['account.move'].with_context(lang='id_ID').get_view(
            self.env.ref('account.view_move_tree').id, 'list')['arch'])
        self.assertTrue(arch.xpath("//field[@name='partner_id'][@string='Donatur/Vendor']"))

    def test_review_and_report_pages(self):
        from lxml import etree
        def label(xmlid):
            return self.env.ref(xmlid).with_context(lang='id_ID').name
        self.assertEqual(label('base_accounting_kit.menu_general_ledger'), "Buku Besar")
        self.assertEqual(label('base_accounting_kit.menu_Balance_report'), "Neraca Saldo")
        self.assertEqual(label('account.action_account_invoice_report_all'),
                         "Analisis Penerimaan & Tagihan")
        manager = self.env.ref('account.group_account_manager')
        self.assertEqual(self.env.ref('base_accounting_kit.menu_tax_report').group_ids, manager)
        Report = self.env['account.invoice.report'].with_context(lang='id_ID')
        search = etree.fromstring(Report.get_views([(False, 'search')])['views']['search']['arch'])
        self.assertTrue(search.xpath("//filter[@name='customer'][@string='Donatur']"))
        graph = etree.fromstring(Report.get_views([(False, 'graph')])['views']['graph']['arch'])
        self.assertTrue(graph.xpath("//field[@name='product_id']"))
        self.assertEqual(Report.fields_get(['price_subtotal'], ['string'])['price_subtotal']['string'],
                         "Jumlah")
        Line = self.env['account.move.line'].with_context(lang='id_ID')
        lst = etree.fromstring(Line.get_view(self.env.ref('account.view_move_line_tree').id,
                                             'list')['arch'])
        self.assertTrue(lst.xpath("//field[@name='partner_id'][@string='Donatur/Vendor']"))
        AssetReport = self.env['asset.asset.report'].with_context(lang='id_ID')
        self.assertEqual(AssetReport.fields_get(['unposted_value'], ['string'])
                         ['unposted_value']['string'], "Belum Dibukukan")

    def test_configuration_pages(self):
        def label(xmlid):
            return self.env.ref(xmlid).with_context(lang='id_ID').name
        self.assertEqual(label('base_accounting_kit.menu_action_account_asset_asset_list_normal_purchase'),
                         "Kategori Aset")
        self.assertEqual(label('base_accounting_kit.account_financial_report_operation0'),
                         "Aktivitas Operasi")
        Journal = self.env['account.journal'].with_context(lang='id_ID')
        types = dict(Journal.fields_get(['type'], ['selection'])['type']['selection'])
        self.assertEqual(types['sale'], "Penerimaan")
        self.assertEqual(types['purchase'], "Pengeluaran")
        Category = self.env['account.asset.category'].with_context(lang='id_ID')
        fields = Category.fields_get(['method'], ['string', 'selection'])['method']
        self.assertEqual(fields['string'], "Metode Penyusutan")
        self.assertEqual(dict(fields['selection'])['linear'], "Garis Lurus")
        self.env['dkm.masjid.setup']._apply_labels()
        caba = self.env['account.journal'].with_context(lang='id_ID', active_test=False).search(
            [('code', '=', 'CABA'), ('company_id', '=', self.company.id)])
        if caba:
            self.assertEqual(caba.name, "Pajak Basis Kas")

    def test_report_translations(self):
        report = self.env.ref('base_accounting_kit.action_report_trial_balance')
        self.assertEqual(report.with_context(lang='id_ID').name, "Neraca Saldo")
        Wizard = self.env['account.balance.report'].with_context(lang='id_ID')
        fields = Wizard.fields_get(['target_move'], ['string', 'selection'])['target_move']
        self.assertEqual(fields['string'], "Entri yang Disertakan")
        self.assertEqual(dict(fields['selection'])['posted'], "Semua Entri Terekam")
        view = self.env.ref('base_accounting_kit.report_trial_balance')
        arch = view.with_context(lang='id_ID').arch_db
        self.assertIn("Neraca Saldo", arch)
        self.assertIn("Sampai tanggal", arch)

    def test_xlsx_export_translated(self):
        import json
        wizard = self.env['account.balance.report'].with_context(lang='id_ID').create({})
        table = {
            'title': 'Trial Balance',
            'meta': [['Company', 'Masjid Uji'], ['Target Moves', 'All Posted Entries']],
            'columns': [{'label': 'Code'}, {'label': 'Account'}, {'label': 'Debit', 'num': True},
                        {'label': 'Credit', 'num': True}, {'label': 'Balance', 'num': True}],
            'rows': [{'cells': ['', 'Total', 1.0, 1.0, 0.0], 'bold': True}],
        }
        action = wizard._xlsx_action('Trial Balance', table)
        self.assertEqual(action['data']['report_name'], "Neraca Saldo")
        data = json.loads(action['data']['options'])
        self.assertEqual(data['title'], "Neraca Saldo")
        self.assertEqual(data['meta'], [["Masjid", "Masjid Uji"],
                                        ["Entri yang Disertakan", "Semua Entri Terekam"]])
        self.assertEqual([c['label'] for c in data['columns']],
                         ["Kode", "Akun", "Debit", "Kredit", "Saldo"])
        self.assertEqual(data['rows'][0]['cells'][1], "Total")
        english = self.env['account.balance.report'].with_context(lang='en_US').create({})
        self.assertEqual(english._xlsx_action('Trial Balance', table)['data']['report_name'],
                         "Trial Balance")

    def test_aged_balance_xlsx_without_entries(self):
        import json
        wizard = self.env['account.aged.trial.balance'].with_company(self.company).with_context(
            lang='id_ID', allowed_company_ids=self.company.ids).create({})
        action = wizard.action_print_xlsx()
        self.assertEqual(action['data']['report_name'], "Umur Piutang & Utang")
        data = json.loads(action['data']['options'])
        self.assertEqual(data['rows'][-1]['cells'][0], "Total Akun")
        self.assertEqual(data['columns'][0]['label'], "Donatur/Vendor")

    def test_heritage_journal_entry_pdf(self):
        view = self.env.ref('eh_account_base.report_eh_account_move', raise_if_not_found=False)
        if not view:
            self.skipTest("eh_account_base not installed")
        # As on a module upgrade: reload the vendor id.po, then our wording.
        setup = self.env['dkm.masjid.setup']
        setup._apply_labels()
        setup._apply_vendor_wording()
        arch = view.with_context(lang='id_ID').arch_db
        self.assertIn("Donatur/Vendor", arch)
        self.assertIn("Keterangan", arch)
        self.assertIn(">Status<", arch)
        self.assertNotIn("Statu<", arch)
        self.assertNotIn("Rekanan", arch)

    def test_draf_everywhere(self):
        setup = self.env['dkm.masjid.setup']
        setup._apply_labels()
        setup._apply_vendor_wording()
        setup._apply_draf_wording()
        Move = self.env['account.move'].with_context(lang='id_ID')
        states = dict(Move.fields_get(['state'], ['selection'])['state']['selection'])
        self.assertEqual(states['draft'], "Draf")
        cron = self.env['ir.actions.server'].with_context(lang='id_ID').search(
            [('name', 'ilike', 'raf')])
        self.assertFalse([n for n in cron.mapped('name') if 'draft' in n.lower()])
        from lxml import etree
        search = Move.get_views([(False, 'search')])['views']['search']['arch']
        self.assertNotIn('"Draft"', search)
        entry = self.cenv['account.move'].with_context(lang='id_ID').create({
            'move_type': 'entry',
            'line_ids': [(0, 0, {'name': 'a', 'account_id': self._category("Zakat").property_account_income_id.id,
                                 'debit': 10.0}),
                         (0, 0, {'name': 'b', 'account_id': self._category("Zakat").property_account_income_id.id,
                                 'credit': 10.0})],
        })
        self.assertNotIn("Draft", entry.with_context(lang='id_ID').display_name)
        from odoo.addons.dkm_masjid.models.masjid_setup import draf_wording
        self.assertEqual(draf_wording("Rancangan Tagihan (INV/1)"), "Tagihan Draf (INV/1)")
        self.assertEqual(draf_wording("Rancangan Pembayaran"), "Pembayaran Draf")
        self.assertEqual(draf_wording("Reset ke Draft"), "Reset ke Draf")
        vendor = self.cenv['res.partner'].create({'name': "Vendor"})
        bill = self.cenv['account.move'].with_context(lang='id_ID').create({
            'move_type': 'in_invoice', 'partner_id': vendor.id, 'invoice_date': '2026-11-25',
            'invoice_line_ids': [(0, 0, {'name': 'Listrik', 'price_unit': 10.0})],
        })
        self.assertTrue(bill.with_context(lang='id_ID').display_name.startswith("Tagihan Draf"),
                        bill.with_context(lang='id_ID').display_name)
        pdf_view = self.env.ref('eh_account_base.report_eh_account_move')
        arch = etree.tostring(pdf_view._get_combined_arch(), encoding='unicode')
        self.assertIn("move.name or 'Draf'", arch)

    def test_receipt_numbering_pdf_and_email(self):
        sale = self.chart.ref('sale')
        self.assertEqual(sale.code, 'PNR')
        infaq = self._category("Infaq & Sedekah").product_variant_id
        donor = self.cenv['res.partner'].create({'name': "Hamba Allah"})
        move = self.cenv['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': donor.id,
            'invoice_line_ids': [(0, 0, {'product_id': infaq.id,
                                         'price_unit': 150000.0})],
        })
        move.action_post()
        self.assertTrue(move.name.startswith('PNR/'), move.name)

        html = str(self.cenv['ir.actions.report'].with_context(lang='id_ID')
                   ._render_qweb_html('account.account_invoices', move.ids)[0])
        self.assertIn("Kuitansi Penerimaan", html)
        self.assertIn("Jazakumullahu khairan", html)
        self.assertIn("Tanggal Penerimaan", html)
        table = html.split("Keterangan", 1)[1].split("Total", 1)[0]
        self.assertNotIn("Kuantitas", table)
        self.assertNotIn("Harga", table)
        self.assertNotIn("1,00", table)
        self.assertIn("Jumlah", table)
        self.assertNotIn("[", html.split("Keterangan", 1)[1].split("Total", 1)[0])

        template = move._get_mail_template()
        self.assertEqual(template, self.env.ref('dkm_masjid.mail_template_receipt'))
        subject = template._render_field('subject', move.ids)[move.id]
        self.assertTrue(subject.startswith("Kuitansi PNR/"), subject)
        body = template._render_field('body_html', move.ids)[move.id]
        self.assertIn("Infaq &amp; Sedekah", str(body))

    def test_vendor_wording(self):
        help_text = self.env['res.partner'].with_context(
            lang='id_ID').fields_get(['debit'], ['help'])['debit']['help']
        self.assertIn("vendor", help_text)
        self.assertNotIn("pemasok", help_text)

    def test_payment_form(self):
        from lxml import etree
        self.env['dkm.masjid.setup']._apply_labels()
        Pay = self.cenv['account.payment'].with_context(lang='id_ID')
        arch = etree.fromstring(Pay.get_views([(False, 'form')])['views']['form']['arch'])
        self.assertTrue(arch.xpath("//field[@name='partner_id'][@string='Donatur']"))
        self.assertTrue(arch.xpath("//field[@name='memo'][@string='Keterangan']"))
        self.assertEqual(arch.xpath("//button[@name='mark_as_sent']")[0].get('invisible'), '1')
        self.assertIn('pdc', arch.xpath("//field[@name='cheque_reference']")[0].get('invisible'))
        self.assertIn('partner_bank_id', arch.xpath(
            "//field[@name='partner_bank_id'][@string='Rekening Masjid']")[0].get('invisible'))
        fields = Pay.fields_get(['payment_type', 'memo'], ['string', 'selection'])
        self.assertEqual(dict(fields['payment_type']['selection']),
                         {'inbound': "Masuk", 'outbound': "Keluar"})
        self.assertEqual(fields['memo']['string'], "Keterangan")

        Reg = self.cenv['account.payment.register'].with_context(lang='id_ID')
        reg = etree.fromstring(Reg.get_views([(False, 'form')])['views']['form']['arch'])
        self.assertTrue(reg.xpath("//button[@string='Catat Pembayaran']"))
        self.assertEqual(reg.xpath("//field[@name='effective_date']")[0].get('invisible'),
                         "payment_method_code != 'pdc'")

        # Journals of the new company, made in English: Indonesian method names.
        bank = self.cenv['account.journal'].search([
            ('company_id', '=', self.company.id), ('type', '=', 'bank')], limit=1)
        manual = bank.inbound_payment_method_line_ids.filtered(
            lambda l: l.payment_method_id.code == 'manual')
        self.assertEqual(manual.name, "Tunai/Transfer")

        donor = self.cenv['res.partner'].create({'name': "Hamba Allah"})
        pay = self.cenv['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer',
            'partner_id': donor.id, 'amount': 50000.0, 'journal_id': bank.id,
            'memo': "Infaq Jumat",
        })
        pay.action_post()
        self.assertEqual(pay.payment_method_line_id.name, "Tunai/Transfer")
        self.assertEqual(pay.state, 'paid')

    def test_payment_lists_are_history(self):
        from lxml import etree
        treasurer = self.env['res.users'].create({
            'name': "Bendahara Uji", 'login': 'bendahara_uji',
            'group_ids': [(6, 0, [self.env.ref('account.group_account_user').id])],
            'company_ids': [(6, 0, self.company.ids)], 'company_id': self.company.id,
        })
        self.assertFalse(treasurer.has_group('account.group_account_manager'))
        Pay = self.cenv['account.payment'].with_user(treasurer)
        for view_type in ('list', 'kanban', 'form'):
            arch = etree.fromstring(Pay.get_view(view_type=view_type)['arch'])
            self.assertEqual(arch.get('create'), '0', view_type)
        admin_arch = etree.fromstring(self.cenv['account.payment'].get_view(view_type='list')['arch'])
        self.assertNotEqual(admin_arch.get('create'), '0')
        # Confirming a receipt still records the payment for the treasurer.
        donor = self.cenv['res.partner'].create({'name': "Hamba Allah"})
        receipt = self.cenv['account.move'].with_user(treasurer).create({
            'move_type': 'out_invoice', 'partner_id': donor.id,
            'invoice_line_ids': [(0, 0, {'name': "Infaq", 'price_unit': 75000.0})],
        })
        receipt.action_post()
        self.assertIn(receipt.payment_state, ('paid', 'in_payment'))

    def test_receipt_received_on_confirm(self):
        from lxml import etree
        Move = self.cenv['account.move'].with_context(lang='id_ID', default_move_type='out_invoice')
        arch = etree.fromstring(Move.get_views([(False, 'form')])['views']['form']['arch'])
        self.assertTrue(arch.xpath("//field[@name='dkm_receipt_journal_id'][@string='Diterima di']"))
        self.assertIn('dkm_receipt_journal_id', arch.xpath(
            "//button[@id='account_invoice_payment_btn']")[0].get('invisible'))

        cash = self.cenv['account.journal'].search([
            ('company_id', '=', self.company.id), ('type', '=', 'cash')], limit=1)
        bank = self.cenv['account.journal'].search([
            ('company_id', '=', self.company.id), ('type', '=', 'bank')], limit=1)
        donor = self.cenv['res.partner'].create({'name': "Hamba Allah"})
        receipt = self.cenv['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': donor.id,
            'invoice_date': '2026-11-20',
            'invoice_line_ids': [(0, 0, {'name': "Infaq Jumat", 'price_unit': 125000.0})],
        })
        self.assertEqual(receipt.dkm_receipt_journal_id, cash)
        receipt.action_post()
        self.assertIn(receipt.payment_state, ('paid', 'in_payment'))
        payment = receipt._get_reconciled_payments()
        self.assertEqual(len(payment), 1)
        self.assertTrue(payment.dkm_auto_receipt)
        self.assertEqual((payment.journal_id, payment.amount, payment.payment_type, str(payment.date)),
                         (cash, 125000.0, 'inbound', '2026-11-20'))

        # Chatter: the confirmation names the receipt; no payment status.
        self.assertEqual(receipt._track_log_get_default_subtype({'state': 'draft'}),
                         self.env.ref('account.mt_invoice_validated'))
        self.assertFalse(receipt._track_log_get_default_body({'state': 'draft'}))
        info = receipt._track_get_fields_info(['payment_state', 'state'])
        changes, values = receipt._mail_track(info, {'payment_state': 'not_paid', 'state': 'draft'})
        self.assertEqual(changes, {'state'})
        self.assertEqual([v['field_name'] for v in values], ['state'])

        html = str(self.cenv['ir.actions.report'].with_context(lang='id_ID')
                   ._render_qweb_html('account.account_invoices', receipt.ids)[0])
        self.assertNotIn("Dibayar pada", html)
        self.assertNotIn("Paid on", html)

        # Back to draft: nothing received yet; confirming again counts once.
        receipt.button_draft()
        self.assertEqual(payment.state, 'canceled')
        receipt.dkm_receipt_journal_id = bank
        receipt.action_post()
        active = receipt._get_reconciled_payments().filtered(lambda p: p.state != 'canceled')
        self.assertEqual(len(active), 1)
        self.assertEqual(active.journal_id, bank)

        refund = self.cenv['account.move'].create({
            'move_type': 'out_refund', 'partner_id': donor.id,
            'invoice_line_ids': [(0, 0, {'name': "Salah catat", 'price_unit': 25000.0})],
        })
        refund.action_post()
        self.assertIn(refund.payment_state, ('paid', 'in_payment'))
        self.assertEqual(refund._get_reconciled_payments().payment_type, 'outbound')
        self.assertFalse(refund._track_log_get_default_subtype({'state': 'draft'}))
        self.assertEqual(refund._track_log_get_default_body({'state': 'draft'}),
                         "Pengembalian Dana dikonfirmasi")
