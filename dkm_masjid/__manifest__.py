# -*- coding: utf-8 -*-
{
    'name': 'DKM - Penyesuaian Masjid',
    'summary': 'Istilah, menu, laporan dan bagan akun disesuaikan untuk '
               'keuangan masjid (nirlaba, ISAK 35).',
    'description': """
Penyesuaian Odoo untuk keuangan masjid
======================================

* Menu: "Pelanggan" menjadi "Penerimaan" (daftar kontak menjadi
  "Donatur"), "Vendor" menjadi "Pengeluaran", "Perusahaan" menjadi
  "Masjid", aplikasi "Penagihan" menjadi "Keuangan". Kategori Penerimaan,
  Laporan Penagihan, Faktur Berulang, Template Jurnal Berulang dan Produk
  dibeli hanya untuk Accounting Administrator; aplikasi Kontak, Dashboard
  dan Aplikasi hanya untuk admin (Settings).
* Faktur pelanggan dipakai sebagai Nota Penerimaan: label Donatur,
  Tanggal Penerimaan, kolom Kategori (Infaq & Sedekah, Zakat, Wakaf, Sewa
  Fasilitas, masing-masing ke akun pendapatannya); jatuh tempo, pengiriman
  dan incoterm disembunyikan. Nota Kredit menjadi Pengembalian Dana.
* Dashboard: kartu angka, keterangan jurnal dan panduan awal memakai
  istilah masjid (tanpa "Faktur" dan "Perusahaan").
* Laporan base_accounting_kit memakai istilah nirlaba: Laporan
  Penghasilan Komprehensif, Laporan Posisi Keuangan, Aset Neto,
  Surplus (Defisit).
* Saat bagan akun Indonesia dimuat (dan saat modul dipasang pada
  perusahaan yang sudah memakainya): PPN dimatikan, jurnal dan akun
  penjualan diganti menjadi penerimaan dana masjid, akun infaq, zakat,
  wakaf dan sewa fasilitas dibuat, dan akun modal diganti menjadi aset
  neto.
""",
    'author': 'DKM',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '20.0.1.5.0',
    'depends': ['account', 'l10n_id', 'base_accounting_kit'],
    'data': [
        'views/menus.xml',
        'views/journal_dashboard_views.xml',
        'views/account_move_views.xml',
        'data/labels.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dkm_masjid/static/src/invoice_guide/invoice_guide.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
