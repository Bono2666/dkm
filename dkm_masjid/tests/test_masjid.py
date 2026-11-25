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
                        .startswith("Nota Penerimaan Draft"))
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
