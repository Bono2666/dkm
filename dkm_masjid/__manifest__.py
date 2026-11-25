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
  Nomor PNR/2026/00001; PDF menjadi Kuitansi Penerimaan (dengan ucapan
  terima kasih dan tanda tangan Bendahara) dan email kirimnya memakai
  template berbahasa Indonesia.
* Istilah "pemasok" di teks bantuan Odoo diganti "vendor".
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
    'version': '20.0.1.15.0',
    'depends': ['account', 'l10n_id', 'l10n_id_efaktur_coretax', 'sale',
                'base_accounting_kit'],
    'data': [
        'views/menus.xml',
        'views/journal_dashboard_views.xml',
        'views/account_move_views.xml',
        'views/list_views.xml',
        'data/labels.xml',
        'data/mail_templates.xml',
        'report/receipt_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dkm_masjid/static/src/invoice_guide/invoice_guide.xml',
            'dkm_masjid/static/src/tax_totals/tax_totals.xml',
            'dkm_masjid/static/src/upload_button/upload_button.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
