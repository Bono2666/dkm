# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, models
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# The committee writes "Draf" (KBBI): Draft/draft -> Draf/draf, and Odoo's
# "Rancangan Tagihan/Faktur/Pembayaran" (Draft Bill/Invoice/Payment) ->
# "Tagihan/Faktur/Pembayaran Draf".
DRAFT_WORD = re.compile(r'\b([Dd])raft\b')
RANCANGAN = re.compile(r'\bRancangan (Tagihan|Faktur|Pembayaran)\b')
DRAF_SQL = r'\m[Dd]raft\M|\mRancangan (Tagihan|Faktur|Pembayaran)\M'


def is_indonesian(env):
    """The language code translations use: the context's, else the request's
    (RPC calls without a context still get Indonesian messages)."""
    lang = env.lang
    if not lang:
        from odoo.http import request
        lang = request and request.env and request.env.lang
    return (lang or '').startswith('id')


def draf_wording(text):
    if not text:
        return text
    return RANCANGAN.sub(r'\1 Draf', DRAFT_WORD.sub(r'\1raf', text))

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
    # Akuntansi menu
    'account.account_closing_menu': "Tutup Buku",
    'account.menu_action_analytic_lines_tree': "Item Analitik",
    'analytic.account_analytic_line_action_entries': "Item Analitik",
    'base_account_budget.menu_act_budget_view': "Anggaran",
    'base_account_budget.act_budget_view': "Anggaran",
    'base_accounting_kit.management_menu': "Aset",
    'base_accounting_kit.menu_action_account_asset_asset_form': "Aset Tetap",
    'base_accounting_kit.action_account_asset_asset_form': "Aset Tetap",
    'base_accounting_kit.actions_menu': "Tindakan",
    'base_accounting_kit.menu_lock_dates': "Tanggal Kunci",
    'base_accounting_kit.account_update_lock_date_act_window': "Tanggal Kunci",
    'analytic.analytic_plan_projects': "Program",
    # Tinjauan menu
    'account.account_audit_trail_menu': "Jejak Audit",
    'account.action_account_audit_trail_report': "Jejak Audit",
    # Laporan menu
    'base_accounting_kit.account_reports_generic_statements': "Laporan Keuangan",
    'base_accounting_kit.menu_account_cash_flow_report': "Laporan Arus Kas",
    'base_accounting_kit.action_cash_flow_report': "Laporan Arus Kas",
    'base_accounting_kit.account_reports_daily_reports': "Laporan Harian",
    'base_accounting_kit.account_bank_book_menu': "Buku Bank",
    'base_accounting_kit.action_account_bank_book_view': "Buku Bank",
    'base_accounting_kit.account_cash_book_menu': "Buku Kas",
    'base_accounting_kit.action_account_cash_book_view': "Buku Kas",
    'base_accounting_kit.account_day_book_menu': "Buku Harian",
    'base_accounting_kit.action_account_day_book_view': "Buku Harian",
    'base_accounting_kit.menu_aged_trial_balance': "Umur Piutang & Utang",
    'base_accounting_kit.action_account_aged_balance_view': "Umur Piutang & Utang",
    'base_accounting_kit.account_reports_partner': "Laporan Donatur & Vendor",
    'base_accounting_kit.menu_partner_ledger': "Buku Besar Donatur & Vendor",
    'base_accounting_kit.action_partner_leadger': "Buku Besar Donatur & Vendor",
    'base_accounting_kit.account_reports_audit': "Laporan Audit",
    'base_accounting_kit.menu_general_ledger': "Buku Besar",
    'base_accounting_kit.action_account_general_ledger_menu': "Buku Besar",
    'base_accounting_kit.menu_Balance_report': "Neraca Saldo",
    'base_accounting_kit.action_account_balance_menu': "Neraca Saldo",
    'base_accounting_kit.menu_tax_report': "Laporan Pajak",
    'base_accounting_kit.action_account_tax_report': "Laporan Pajak",
    'base_accounting_kit.menu_print_journal': "Audit Jurnal",
    'base_accounting_kit.action_account_print_journal_menu': "Audit Jurnal",
    'base_accounting_kit.menu_account_fx_revaluation': "Revaluasi Mata Uang",
    'base_accounting_kit.action_account_fx_revaluation': "Revaluasi Mata Uang",
    'account.menu_action_account_invoice_report_all': "Analisis Penerimaan & Tagihan",
    'account.action_account_invoice_report_all': "Analisis Penerimaan & Tagihan",
    'base_account_budget.menu_act_crossovered_budget_lines_view': "Realisasi Anggaran",
    'base_account_budget.act_budget_lines_view': "Realisasi Anggaran",
    'base_accounting_kit.menu_action_asset_asset_report': "Analisis Aset",
    'base_accounting_kit.action_asset_asset_report': "Analisis Aset",
    # Konfigurasi menu
    'account_payment.payment_provider_menu': "Pembayaran Online",
    'account.account_invoicing_menu': "Penerimaan & Tagihan",
    'base_accounting_kit.account_followup_menu': "Tingkat Pengingat",
    'base_accounting_kit.action_account_followup_definition_form': "Pengingat Pembayaran",
    'base_account_budget.menu_budget_post_form': "Pos Anggaran",
    'base_account_budget.open_budget_post_form': "Pos Anggaran",
    'base_accounting_kit.menu_finance_config_assets': "Aset",
    'base_accounting_kit.menu_action_account_asset_asset_list_normal_purchase': "Kategori Aset",
    'base_accounting_kit.action_account_asset_asset_list_normal_purchase': "Kategori Aset",
    'base_accounting_kit.menu_account_financial_reports_tree': "Struktur Laporan",
    'base_accounting_kit.action_account_financial_report_tree': "Struktur Laporan Keuangan",
    # Cash flow statement lines (also printed on the report)
    'base_accounting_kit.account_financial_report_cash_flow0': "Laporan Arus Kas",
    'base_accounting_kit.account_financial_report_operation0': "Aktivitas Operasi",
    'base_accounting_kit.account_financial_report_investing_activity0': "Aktivitas Investasi",
    'base_accounting_kit.account_financial_report_financing_activity1': "Aktivitas Pendanaan",
    'base_accounting_kit.cash_in_from_operation0': "Kas Masuk",
    'base_accounting_kit.cash_out_operation1': "Kas Keluar",
    'base_accounting_kit.cash_in_investing0': "Kas Masuk",
    'base_accounting_kit.cash_out_investing1': "Kas Keluar",
    'base_accounting_kit.cash_in_financial0': "Kas Masuk",
    'base_accounting_kit.cash_out_financial1': "Kas Keluar",
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
        "Pembayaran masuk tercatat otomatis saat Nota Penerimaan "
        "dikonfirmasi. Halaman ini adalah riwayatnya."),
    'account.action_account_payments_payable': _help(
        "Belum ada pembayaran keluar",
        "Pembayaran ke vendor tercatat otomatis saat Tagihan Vendor dibayar "
        "dengan tombol Bayar. Halaman ini adalah riwayatnya."),
    'account.res_partner_action_customer': _help(
        "Tambahkan donatur",
        "Simpan data donatur agar penerimaan dari mereka mudah dicatat dan "
        "dilacak. Donatur yang tidak ingin disebut namanya bisa dicatat "
        "sebagai \"Hamba Allah\"."),
    'base_account_budget.act_budget_view': (
        "Buat anggaran masjid",
        "Anggaran berisi rencana penerimaan dan pengeluaran masjid untuk satu "
        "periode, misalnya satu tahun (RAPB).",
        "Bandingkan rencana dengan realisasinya agar pengeluaran tetap "
        "terkendali dan program masjid berjalan sesuai rencana."),
    'account.action_account_invoice_report_all': (
        "Dari laporan ini terlihat jumlah penerimaan dari donatur dan tagihan "
        "dari vendor per bulan dan per kategori. Gunakan filter dan "
        "pengelompokan untuk menyesuaikan analisis.",),
    'account.action_account_audit_trail_report': ("Jejak Audit",),
    'eh_account_approval.action_eh_approval_request': (
        "Belum ada permintaan persetujuan",
        "Di sini tampil tagihan yang menunggu persetujuan Bendahara atau Ketua. "
        "Permintaan dibuat otomatis saat tagihan diajukan dengan tombol Minta "
        "Persetujuan."),
    'base_accounting_kit.action_asset_asset_report': (
        "Dari laporan ini terlihat nilai perolehan serta penyusutan yang sudah "
        "dan belum dibukukan untuk seluruh aset tetap masjid.",),
    'account.res_partner_action_supplier': _help(
        "Tambahkan vendor",
        "Simpan data vendor (toko, penyedia jasa, PLN, PDAM, dan lainnya) agar "
        "tagihan dan pembayarannya mudah dicatat."),
}

# Actions that ship without any help text: Indonesian HTML, set once.
ACTION_HELPS_NEW = {
    'base_accounting_kit.action_account_asset_asset_form':
        '<p class="o_view_nocontent_smiling_face">Catat aset tetap masjid</p>'
        '<p>Catat aset seperti sound system, karpet, AC, atau kendaraan agar '
        'nilai dan penyusutannya tercatat.</p>',
    'base_account_budget.act_budget_lines_view':
        '<p class="o_view_nocontent_smiling_face">Belum ada realisasi anggaran</p>'
        '<p>Baris anggaran dari menu Akuntansi &gt; Anggaran tampil di sini, '
        'lengkap dengan rencana, realisasi, dan persentase pencapaiannya.</p>',
}

# Default filters that would add "atau Penerimaan" (sale/purchase receipts,
# which mosques do not use) to the receipt and bill lists.
ACTION_DEFAULT_FILTERS_DROPPED = {
    'account.action_move_out_invoice': 'search_default_out_receipt',
    'account.action_move_out_invoice_type': 'search_default_out_receipt',
    'account.action_move_in_invoice': 'search_default_in_receipt',
    'account.action_move_in_invoice_type': 'search_default_in_receipt',
}

PAYMENT_METHOD_HELP = (
    "Tunai/Transfer: uang diterima atau dibayarkan tunai atau lewat transfer bank.\n"
    "Cek: pembayaran dengan cek. Cek Mundur: cek yang baru bisa dicairkan "
    "pada tanggal efektifnya."
)

# Other translated texts: xmlid -> {field: Indonesian text}.
FIELD_TEXTS = {
    # Budgets (base_account_budget, English only).
    'base_account_budget.field_budget_budget__name': {'field_description': "Nama Anggaran"},
    'base_account_budget.field_budget_budget__date_from': {'field_description': "Tanggal Mulai"},
    'base_account_budget.field_budget_budget__date_to': {'field_description': "Tanggal Selesai"},
    'base_account_budget.field_budget_budget__creating_user_id': {'field_description': "Penanggung Jawab"},
    'base_account_budget.selection__budget_budget__state__draft': {'name': "Draf"},
    'base_account_budget.selection__budget_budget__state__cancel': {'name': "Dibatalkan"},
    'base_account_budget.selection__budget_budget__state__confirm': {'name': "Dikonfirmasi"},
    'base_account_budget.selection__budget_budget__state__validate': {'name': "Disetujui"},
    'base_account_budget.selection__budget_budget__state__done': {'name': "Selesai"},
    'base_account_budget.field_budget_lines__budget_id': {'field_description': "Anggaran"},
    'base_account_budget.field_budget_lines__general_budget_id': {'field_description': "Pos Anggaran"},
    'base_account_budget.field_budget_lines__analytic_account_id': {'field_description': "Akun Analitik"},
    'base_account_budget.field_budget_lines__date_from': {'field_description': "Tanggal Mulai"},
    'base_account_budget.field_budget_lines__date_to': {'field_description': "Tanggal Selesai"},
    'base_account_budget.field_budget_lines__planned_amount': {'field_description': "Rencana"},
    'base_account_budget.field_budget_lines__practical_amount': {'field_description': "Realisasi"},
    'base_account_budget.field_budget_lines__theoretical_amount': {'field_description': "Target s.d. Hari Ini"},
    'base_account_budget.field_budget_lines__percentage': {'field_description': "Pencapaian"},
    # Asset analysis (base_accounting_kit, English only).
    'base_accounting_kit.field_asset_asset_report__name': {'field_description': "Tahun"},
    'base_accounting_kit.field_asset_asset_report__asset_id': {'field_description': "Aset"},
    'base_accounting_kit.field_asset_asset_report__asset_category_id': {'field_description': "Kategori Aset"},
    'base_accounting_kit.field_asset_asset_report__depreciation_date': {'field_description': "Tanggal Penyusutan"},
    'base_accounting_kit.field_asset_asset_report__partner_id': {'field_description': "Vendor"},
    'base_accounting_kit.field_asset_asset_report__depreciation_value': {'field_description': "Nilai Penyusutan"},
    'base_accounting_kit.field_asset_asset_report__gross_value': {'field_description': "Nilai Perolehan"},
    'base_accounting_kit.field_asset_asset_report__posted_value': {'field_description': "Sudah Dibukukan"},
    'base_accounting_kit.field_asset_asset_report__unposted_value': {'field_description': "Belum Dibukukan"},
    'base_accounting_kit.selection__asset_asset_report__state__draft': {'name': "Draf"},
    'base_accounting_kit.selection__asset_asset_report__state__open': {'name': "Berjalan"},
    'base_accounting_kit.selection__asset_asset_report__state__close': {'name': "Selesai"},
    # Konfigurasi lists (English-only modules and leftovers).
    'base_accounting_kit.field_account_financial_report__name': {'field_description': "Nama Laporan"},
    'base_accounting_kit.field_account_financial_report__parent_id': {'field_description': "Induk"},
    'base_accounting_kit.field_account_financial_report__type': {'field_description': "Jenis"},
    'base_accounting_kit.field_account_financial_report__account_report_id': {'field_description': "Nilai Laporan"},
    'base_accounting_kit.selection__account_financial_report__type__sum': {'name': "Tampilan"},
    'base_accounting_kit.selection__account_financial_report__type__accounts': {'name': "Akun"},
    'base_accounting_kit.selection__account_financial_report__type__account_type': {'name': "Jenis Akun"},
    'base_accounting_kit.selection__account_financial_report__type__account_report': {'name': "Nilai Laporan"},
    'base_accounting_kit.field_account_asset_category__name': {'field_description': "Kategori Aset"},
    'base_accounting_kit.field_account_asset_category__journal_id': {'field_description': "Jurnal"},
    'base_accounting_kit.field_account_asset_category__method': {'field_description': "Metode Penyusutan"},
    'base_accounting_kit.selection__account_asset_category__method__linear': {'name': "Garis Lurus"},
    'base_accounting_kit.selection__account_asset_category__method__degressive': {'name': "Saldo Menurun"},
    'base_accounting_kit.field_account_followup__company_id': {'field_description': "Masjid"},
    'base_account_budget.field_account_budget_post__name': {'field_description': "Nama"},
    'account.field_account_journal_group__name': {'field_description': "Kelompok Ledger"},
    'analytic.field_account_analytic_account__partner_id': {'field_description': "Donatur/Vendor"},
    # Journal types: the sale/purchase journals are receipts and spending.
    'account.selection__account_journal__type__sale': {'name': "Penerimaan"},
    'account.selection__account_journal__type__purchase': {'name': "Pengeluaran"},
    # Invoice analysis: no taxes, so the untaxed amount is the amount.
    'account.field_account_invoice_report__price_subtotal': {'field_description': "Jumlah"},
    # Fixed assets (base_accounting_kit, English only).
    'base_accounting_kit.field_account_asset_asset__name': {'field_description': "Nama Aset"},
    'base_accounting_kit.field_account_asset_asset__category_id': {'field_description': "Kategori Aset"},
    'base_accounting_kit.field_account_asset_asset__date': {'field_description': "Tanggal"},
    'base_accounting_kit.field_account_asset_asset__value': {'field_description': "Nilai Perolehan"},
    'base_accounting_kit.field_account_asset_asset__value_residual': {'field_description': "Nilai Sisa"},
    'base_accounting_kit.field_account_asset_asset__currency_id': {'field_description': "Mata Uang"},
    'base_accounting_kit.selection__account_asset_asset__state__draft': {'name': "Draf"},
    'base_accounting_kit.selection__account_asset_asset__state__open': {'name': "Berjalan"},
    'base_accounting_kit.selection__account_asset_asset__state__paused': {'name': "Dijeda"},
    'base_accounting_kit.selection__account_asset_asset__state__close': {'name': "Selesai"},
    'base_accounting_kit.selection__account_asset_asset__state__cancelled': {'name': "Dibatalkan"},
    # Payments: donors/vendors, money in/out, a note instead of a memo.
    'account.field_account_payment__partner_id': {'field_description': "Donatur/Vendor"},
    'account.field_account_payment__payment_type': {'field_description': "Jenis Pembayaran"},
    'account.selection__account_payment__payment_type__inbound': {'name': "Masuk"},
    'account.selection__account_payment__payment_type__outbound': {'name': "Keluar"},
    'account.field_account_payment__memo': {'field_description': "Keterangan"},
    'account.field_account_payment_register__communication': {'field_description': "Keterangan"},
    'account.field_account_payment__payment_method_line_id': {'help': PAYMENT_METHOD_HELP},
    'account.field_account_payment_register__payment_method_line_id': {'help': PAYMENT_METHOD_HELP},
    'account.field_account_payment_register__group_payment': {
        'field_description': "Gabungkan Pembayaran",
        'help': "Satu pembayaran per donatur/vendor, bukan satu per tagihan."},
    'base_accounting_kit.field_account_payment__effective_date': {
        'field_description': "Tanggal Efektif", 'help': "Tanggal cek mundur bisa dicairkan."},
    'base_accounting_kit.field_account_payment_register__effective_date': {
        'field_description': "Tanggal Efektif", 'help': "Tanggal cek mundur bisa dicairkan."},
    'account.field_account_payment_register__partner_bank_id': {'field_description': "Rekening Penerima"},
    'base_accounting_kit.field_account_payment_register__bank_reference': {'field_description': "No. Referensi Bank"},
    'base_accounting_kit.field_account_payment_register__cheque_reference': {'field_description': "No. Cek"},
    'base_accounting_kit.field_account_payment__bank_reference': {'field_description': "No. Referensi Bank"},
    'base_accounting_kit.field_account_payment__cheque_reference': {'field_description': "No. Cek"},
    # Chatter line on a new Nota Penerimaan ("Faktur Dibuat").
    'account.mt_invoice_created': {
        'name': "Nota Penerimaan Dibuat",
        'description': "Nota Penerimaan Dibuat",
    },
}

# Payment methods by code: the method itself (translated name) and the
# journal lines already created from it (plain copies of the English name).
PAYMENT_METHOD_NAMES = {
    'manual': "Tunai/Transfer",
    'check_printing': "Cek",
    'pdc': "Cek Mundur",
}
PAYMENT_METHOD_OLD_NAMES = ["Manual Payment", "Pembayaran Manual", "Checks", "PDC"]

# Vendored modules that ship an i18n/id.po added for the mosque (PDF reports
# and their print wizards). Reloaded with overwrite on every upgrade, before
# the labels below, because the module itself is rarely upgraded.
TRANSLATED_MODULES = ['base_accounting_kit', 'eh_account_base']

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
    # ERP Heritage journal entry PDF: mosque wording on top of its own id.po.
    'eh_account_base.report_eh_account_move': {
        'Status': "Status",
        'Ledger': "Buku",
        '/ Document': "/ Dokumen",
        'Partner': "Donatur/Vendor",
        'Label': "Keterangan",
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
        self.env['ir.module.module'].sudo().search([
            ('name', 'in', TRANSLATED_MODULES), ('state', '=', 'installed'),
        ])._update_translations('id_ID', overwrite=True)
        for xmlid, label in LABELS.items():
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                self._set_name(record.sudo(), label, langs=['id_ID'])
        # The chart's cash-basis tax journal keeps its English name.
        caba = self.env['account.journal'].sudo().with_context(active_test=False).search(
            [('code', '=', 'CABA'), ('name', '=', "Cash Basis Taxes")])
        if caba:
            self._set_name(caba, "Pajak Basis Kas", langs=['id_ID'])
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
        for xmlid, html in ACTION_HELPS_NEW.items():
            action = self.env.ref(xmlid, raise_if_not_found=False)
            if action and not action.help:
                action.sudo().with_context(lang='id_ID').help = html
        for xmlid, texts in FIELD_TEXTS.items():
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                for fname, text in texts.items():
                    record.sudo().update_field_translations(fname, {'id_ID': text})
        for code, name in PAYMENT_METHOD_NAMES.items():
            methods = self.env['account.payment.method'].sudo().search([('code', '=', code)])
            for method in methods:
                method.update_field_translations('name', {'id_ID': name})
            self.env['account.payment.method.line'].sudo().search([
                ('payment_method_id', 'in', methods.ids),
                ('name', 'in', PAYMENT_METHOD_OLD_NAMES),
            ]).write({'name': name})

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
    def _apply_draf_wording(self):
        """Called from data/labels.xml on every install and upgrade: write
        "Draf"/"draf" (KBBI) instead of "Draft"/"draft" in every Indonesian translation
        stored in the database (states, filters, buttons, views, ...)."""
        if 'id_ID' not in dict(self.env['res.lang'].get_installed()):
            return
        cr = self.env.cr
        for model_name in list(self.env.registry):
            Model = self.env[model_name]
            if Model._abstract or Model._transient or not Model._auto:
                continue
            for fname, field in Model._fields.items():
                if not (field.translate and field.store and field.column_type) \
                        or field.model_name != model_name:
                    continue
                column = SQL.identifier(Model._table, fname)
                if field.translate is True:
                    condition = SQL("%s->>'id_ID' ~ %s OR (NOT %s ? 'id_ID' AND %s->>'en_US' = 'Draft')",
                                    column, DRAF_SQL, column, column)
                else:
                    condition = SQL("%s->>'id_ID' ~ %s OR %s->>'en_US' ~ %s",
                                    column, DRAF_SQL, column, r'\mDraft\M')
                cr.execute(SQL("SELECT id FROM %s WHERE %s",
                               SQL.identifier(Model._table), condition))
                ids = [row[0] for row in cr.fetchall()]
                if not ids:
                    continue
                records = Model.browse(ids).sudo().with_context(
                    lang='id_ID', active_test=False)
                for record in records:
                    if field.translate is True:
                        value = record[fname] or ''
                        if draf_wording(value) != value:
                            record.update_field_translations(
                                fname, {'id_ID': draf_wording(value)})
                        continue
                    translations, _context = record.get_field_translations(
                        fname, langs=['id_ID'])
                    mapping = {}
                    for term in translations:
                        value = term['value'] or ''
                        # Untranslated terms stay English, except a bare "Draft".
                        if not value and term['source'].strip() == 'Draft':
                            value = term['source']
                        if draf_wording(value) != value:
                            mapping[term['source']] = draf_wording(value)
                    if mapping:
                        record.update_field_translations(fname, {'id_ID': mapping})

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
