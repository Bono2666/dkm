# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)

# Indonesian UI labels, written for id_ID. On a database where en_US is not
# installed Odoo also stores them as the source term, which is why
# models/financial_report.py no longer relies on the English line names.
LABELS = {
    # Invoicing menus
    'account.menu_finance': "Keuangan",
    'account.menu_finance_receivables': "Penerimaan",
    'account.menu_account_customer': "Donatur",
    'account.res_partner_action_customer': "Donatur",
    'account.menu_finance_payables': "Pengeluaran",
    'account.menu_action_move_out_invoice_type': "Nota Penerimaan",
    'account.action_move_out_invoice': "Nota Penerimaan",
    'account.action_move_out_invoice_type': "Nota Penerimaan",
    'account.menu_action_move_out_refund_type': "Pengembalian Dana",
    'account.action_move_out_refund_type_non_legacy': "Pengembalian Dana",
    'account.product_product_menu_sellable': "Kategori Penerimaan",
    'account.menu_account_supplier': "Vendor",
    'account.res_partner_action_supplier': "Vendor",
    'account.account_invoices': "Kuitansi / Faktur PDF",
    'account.action_account_payments': "Pembayaran Masuk",
    'account.action_account_payments_payable': "Pembayaran Keluar",
    'base_accounting_kit.customer_statements_menu': "Laporan Penagihan",
    'base_accounting_kit.menu_account_recurring_invoice': "Faktur Berulang",
    'base_accounting_kit.account_recurring_payments_child1':
        "Template Jurnal Berulang",
    'base_accounting_kit.menu_account_bulk_payment': "Pembayaran Massal",
    # Company -> Masjid
    'base.menu_users': "Pengguna & Masjid",
    'base.menu_action_res_company_form': "Masjid",
    'base.action_res_company_form': "Masjid",
    # Nonprofit report names (ISAK 35)
    'base_accounting_kit.account_financial_reports_profit_loss':
        "Laporan Penghasilan Komprehensif",
    'base_accounting_kit.action_profit_and_loss_report':
        "Laporan Penghasilan Komprehensif",
    'base_accounting_kit._account_financial_reports_balance_sheet':
        "Laporan Posisi Keuangan",
    'base_accounting_kit.action_balance_sheet_report':
        "Laporan Posisi Keuangan",
    'base_accounting_kit.account_financial_report_profitandloss0':
        "Laporan Penghasilan Komprehensif",
    'base_accounting_kit.account_financial_report_income0': "Pendapatan",
    'base_accounting_kit.account_financial_report_other_income0':
        "Pendapatan Lain-lain",
    'base_accounting_kit.financial_report_gross_profit':
        "Penerimaan Bersih",
    'base_accounting_kit.financial_report_cost_of_revenue':
        "Beban Langsung",
    'base_accounting_kit.account_financial_report_operating_income0':
        "Penerimaan Operasional",
    'base_accounting_kit.account_financial_report_expense0': "Beban",
    'base_accounting_kit.account_financial_report_balancesheet0':
        "Laporan Posisi Keuangan",
    'base_accounting_kit.account_financial_report_assets0': "Aset",
    'base_accounting_kit.account_financial_report_liabilitysum0':
        "Liabilitas & Aset Neto",
    'base_accounting_kit.account_financial_report_liability0':
        "Liabilitas & Aset Neto",
    'base_accounting_kit.account_financial_report_profitloss_toreport0':
        "Surplus (Defisit) Tahun Berjalan",
}

# Empty-list help of the receipt, bill, payment and contact lists: Indonesian
# for the help's terms in order (title, then explanation).
def _help(title, text):
    return (title, text)


RECEIPT_HELP = _help(
    "Catat penerimaan dana",
    "Buat Nota Penerimaan untuk setiap infaq, sedekah, zakat, wakaf, atau "
    "sewa fasilitas yang diterima masjid. Kuitansinya bisa langsung dicetak "
    "atau dikirim ke donatur.")
BILL_HELP = _help(
    "Catat tagihan vendor",
    "Catat tagihan dari toko, penyedia jasa, PLN, PDAM, dan lainnya, lalu "
    "ajukan persetujuan sebelum dibayar.")
ACTION_HELPS = {
    'account.action_move_out_invoice': RECEIPT_HELP,
    'account.action_move_out_invoice_type': RECEIPT_HELP,
    'account.action_move_out_refund_type': _help(
        "Belum ada pengembalian dana",
        "Pengembalian dana paling mudah dibuat langsung dari Nota Penerimaan "
        "yang bersangkutan."),
    'account.action_move_out_refund_type_non_legacy': _help(
        "Belum ada pengembalian dana",
        "Pengembalian dana paling mudah dibuat langsung dari Nota Penerimaan "
        "yang bersangkutan."),
    'account.action_move_in_invoice': BILL_HELP,
    'account.action_move_in_invoice_type': BILL_HELP,
    'account.action_move_in_refund_type': _help(
        "Belum ada pengembalian dari vendor",
        "Pengembalian dari vendor paling mudah dibuat langsung dari Tagihan "
        "Vendor yang bersangkutan."),
    'account.action_account_payments': _help(
        "Belum ada pembayaran masuk",
        "Pembayaran masuk tercatat saat Nota Penerimaan dibayar, atau bisa "
        "dicatat langsung di sini."),
    'account.action_account_payments_payable': _help(
        "Belum ada pembayaran keluar",
        "Pembayaran ke vendor tercatat saat Tagihan Vendor dibayar, atau bisa "
        "dicatat langsung di sini."),
    'account.res_partner_action_customer': _help(
        "Tambahkan donatur",
        "Simpan data donatur agar penerimaan dari mereka mudah dicatat dan "
        "dilacak. Donatur yang tidak ingin disebut namanya bisa dicatat "
        "sebagai \"Hamba Allah\"."),
    'account.res_partner_action_supplier': _help(
        "Tambahkan vendor",
        "Simpan data vendor (toko, penyedia jasa, PLN, PDAM, dan lainnya) agar "
        "tagihan dan pembayarannya mudah dicatat."),
}

# Default filters that would add "atau Penerimaan" (sale/purchase receipts,
# which mosques do not use) to the receipt and bill lists.
ACTION_DEFAULT_FILTERS_DROPPED = {
    'account.action_move_out_invoice': 'search_default_out_receipt',
    'account.action_move_out_invoice_type': 'search_default_out_receipt',
    'account.action_move_in_invoice': 'search_default_in_receipt',
    'account.action_move_in_invoice_type': 'search_default_in_receipt',
}

# Other translated texts: xmlid -> {field: Indonesian text}.
FIELD_TEXTS = {
    # Chatter line on a new Nota Penerimaan ("Faktur Dibuat").
    'account.mt_invoice_created': {
        'name': "Nota Penerimaan Dibuat",
        'description': "Nota Penerimaan Dibuat",
    },
}

# Top-level apps the treasurer and chairman do not need: donors and vendors
# are under Keuangan > Penerimaan / Pengeluaran. Admin (Settings) only. These
# modules are not dependencies, so the menus are looked up softly.
ADMIN_ONLY_MENUS = [
    'contacts.menu_contacts',
    'spreadsheet_dashboard.spreadsheet_dashboard_menu_root',
    'base.menu_management',
]

# Chart template journal ids -> name, None = archive.
JOURNALS = {
    'sale': "Penerimaan Dana",
    'purchase': "Pengeluaran / Tagihan",
    'inventory_valuation': None,
}

# l10n_id chart account ids -> name, None = archive.
ACCOUNTS = {
    'l10n_id_41000010': "Penerimaan Infaq & Sedekah",
    'l10n_id_42000060': None,   # Pengembalian Penjualan
    'l10n_id_42000070': None,   # Diskon Penjualan
    'l10n_id_51000010': None,   # Harga Pokok Penjualan
    'l10n_id_31100010': None,   # Modal Disahkan
    'l10n_id_31100020': "Aset Neto Tidak Terikat",
    'l10n_id_31100030': None,   # Modal Belum Disetor
    'l10n_id_31100040': None,   # Prive
    'l10n_id_31210010': "Aset Neto Terikat",
    'l10n_id_31510010': "Akumulasi Surplus (Defisit)",
    'l10n_id_31510020': None,   # Laba & Rugi Berjalan (manual duplicate)
    'l10n_id_99999900': "Surplus (Defisit) Tahun Berjalan",
}

# Mosque receipts are numbered PNR/2026/00001 (refunds RPNR/...).
RECEIPT_JOURNAL_CODE = 'PNR'

# Odoo's Indonesian texts that say "pemasok": the committee knows "vendor".
VENDOR_FIELD_HELP = {
    'account.field_res_partner__debit':
        "Jumlah total yang harus Anda bayar pada vendor ini.",
    'account.field_res_users__debit':
        "Jumlah total yang harus Anda bayar pada vendor ini.",
    'product.field_product_supplierinfo__sequence':
        "Tetapkan prioritas untuk daftar vendor produk.",
    'product.field_product_supplierinfo__date_end':
        "Tanggal berakhir untuk harga vendor ini",
    'product.field_product_supplierinfo__date_start':
        "Tanggal mulai untuk harga vendor ini",
}
VENDOR_VIEW_TERMS = {
    'account.res_config_settings_view_form': {
        'Print checks to pay your vendors':
            "Cetak cek untuk membayar vendor Anda",
    },
}

# Receipt categories (sellable services) -> income account code. Chosen in the
# Kategori column of a Nota Penerimaan, they post to the right account.
# No internal reference: it would be printed on the receipt.
RECEIPT_CATEGORIES = [
    ("Infaq & Sedekah", '41000010'),
    ("Zakat", '41000020'),
    ("Wakaf", '41000030'),
    ("Sewa Fasilitas", '41000040'),
]

NEW_ACCOUNTS = [
    ('41000020', "Penerimaan Zakat (Dana Terikat)", 'income'),
    ('41000030', "Penerimaan Wakaf (Dana Terikat)", 'income'),
    ('41000040', "Penerimaan Sewa Fasilitas", 'income'),
    ('61200010', "Beban Operasional Masjid", 'expense'),
]
DEFAULT_EXPENSE_CODE = '61200010'


class DkmMasjidSetup(models.AbstractModel):
    _name = 'dkm.masjid.setup'
    _description = "Penyesuaian Odoo untuk masjid"

    @api.model
    def _set_name(self, records, name, langs=None):
        if langs is None:
            langs = [code for code, _name in self.env['res.lang'].get_installed()]
        for lang in langs:
            records.with_context(lang=lang).write({'name': name})

    @api.model
    def _apply_labels(self):
        """Called from data/labels.xml on every install and upgrade."""
        if 'id_ID' not in dict(self.env['res.lang'].get_installed()):
            return
        for xmlid, label in LABELS.items():
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                self._set_name(record.sudo(), label, langs=['id_ID'])
        help_field = self.env['ir.actions.act_window']._fields['help']
        for xmlid, texts in ACTION_HELPS.items():
            action = self.env.ref(xmlid, raise_if_not_found=False)
            if not action:
                continue
            source = action.with_context(lang='en_US').help or ''
            terms = []
            help_field.translate(lambda term: terms.append(term) or term, source)
            if len(terms) < len(texts):
                continue
            mapping = dict(zip(terms, texts))
            action.sudo().update_field_translations('help', {'id_ID': mapping})
        for xmlid, texts in FIELD_TEXTS.items():
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                for fname, text in texts.items():
                    record.sudo().update_field_translations(fname, {'id_ID': text})

    @api.model
    def _apply_vendor_wording(self):
        """Called from data/labels.xml on every install and upgrade."""
        if 'id_ID' not in dict(self.env['res.lang'].get_installed()):
            return
        for xmlid, text in VENDOR_FIELD_HELP.items():
            field = self.env.ref(xmlid, raise_if_not_found=False)
            if field:
                field.sudo().update_field_translations('help', {'id_ID': text})
        for xmlid, terms in VENDOR_VIEW_TERMS.items():
            view = self.env.ref(xmlid, raise_if_not_found=False)
            if view:
                view.sudo().update_field_translations('arch_db', {'id_ID': terms})

    @api.model
    def _apply_list_defaults(self):
        """Called from data/labels.xml on every install and upgrade (an
        upgrade of account restores the original contexts)."""
        for xmlid, key in ACTION_DEFAULT_FILTERS_DROPPED.items():
            action = self.env.ref(xmlid, raise_if_not_found=False)
            if not action or key not in (action.context or ''):
                continue
            action.sudo().context = re.sub(
                r"\s*'%s'\s*:\s*1\s*,?" % key, '', action.context)

    @api.model
    def _apply_menu_restrictions(self):
        """Called from data/labels.xml on every install and upgrade."""
        admin = self.env.ref('base.group_system')
        for xmlid in ADMIN_ONLY_MENUS:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                menu.sudo().group_ids = admin

    @api.model
    def _setup_accounting(self, companies):
        """Turn the Indonesian commercial chart into a mosque chart.

        Run once per company (chart load or module install), not on
        upgrades, so later manual renames by the treasurer stick.
        """
        for company in companies:
            env = self.with_company(company).env
            chart = env['account.chart.template']
            Account = env['account.account'].with_context(active_test=False)

            # 1. Mosques are not PKP: no VAT by default anywhere.
            company.write({
                'account_sale_tax_id': False,
                'account_purchase_tax_id': False,
            })
            taxed = Account.search([
                ('company_ids', 'in', company.id), ('tax_ids', '!=', False),
            ])
            taxed.write({'tax_ids': [(5, 0, 0)]})
            env['account.tax'].search([
                ('company_id', '=', company.id),
            ]).write({'active': False})

            # 2. Accounts: new mosque accounts first, so the purchase journal
            # and company default can move off Harga Pokok Penjualan before it
            # is archived.
            for code, name, account_type in NEW_ACCOUNTS:
                account = Account.search([
                    ('code', '=', code), ('company_ids', 'in', company.id),
                ], limit=1)
                if not account:
                    account = Account.create({
                        'code': code,
                        'name': name,
                        'account_type': account_type,
                        'company_ids': [(6, 0, company.ids)],
                    })
                    self._set_name(account, name)
            expense = Account.search([
                ('code', '=', DEFAULT_EXPENSE_CODE),
                ('company_ids', 'in', company.id),
            ], limit=1)
            company.expense_account_id = expense

            # 3. Journals.
            for key, name in JOURNALS.items():
                journal = chart.ref(key, raise_if_not_found=False)
                if not journal or journal.company_id != company:
                    continue
                if name is None:
                    if company.account_stock_journal_id == journal:
                        company.account_stock_journal_id = False
                    journal.active = False
                else:
                    self._set_name(journal, name)
                    if key == 'purchase':
                        journal.default_account_id = expense

            for key, name in ACCOUNTS.items():
                account = chart.ref(key, raise_if_not_found=False)
                if not account:
                    continue
                if name is None:
                    account.active = False
                else:
                    self._set_name(account, name)
            self._setup_receipt_categories(company)
            self._setup_receipt_numbering(company)
            _logger.info("dkm_masjid: mosque chart applied to %s", company.name)

    @api.model
    def _setup_receipt_numbering(self, companies):
        """Give the receipt journal the PNR code (the sequence prefix), as
        long as nothing has been numbered in it yet."""
        for company in companies:
            journal = self.with_company(company).env['account.chart.template'].ref(
                'sale', raise_if_not_found=False)
            if not journal or journal.company_id != company \
                    or journal.code == RECEIPT_JOURNAL_CODE:
                continue
            if self.env['account.move'].with_context(active_test=False).search_count(
                    [('journal_id', '=', journal.id)], limit=1):
                continue
            journal.code = RECEIPT_JOURNAL_CODE

    @api.model
    def _setup_receipt_categories(self, companies):
        for company in companies:
            env = self.with_company(company).env
            Account = env['account.account']
            Product = env['product.template'].with_context(active_test=False)
            for name, account_code in RECEIPT_CATEGORIES:
                if Product.search([('name', '=', name), ('sale_ok', '=', True),
                                   ('company_id', '=', company.id)], limit=1):
                    continue
                account = Account.search([
                    ('code', '=', account_code),
                    ('company_ids', 'in', company.id),
                ], limit=1)
                product = Product.create({
                    'name': name,
                    'type': 'service',
                    'sale_ok': True,
                    'purchase_ok': False,
                    'list_price': 0.0,
                    'taxes_id': [(5, 0, 0)],
                    'supplier_taxes_id': [(5, 0, 0)],
                    'company_id': company.id,
                    'property_account_income_id': account.id,
                })
                self._set_name(product, name)
