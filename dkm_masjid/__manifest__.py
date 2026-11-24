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
  "Masjid". Faktur, Nota Kredit dan Produk dijual hanya terlihat oleh
  Accounting Administrator.
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
    'version': '20.0.1.0.0',
    'depends': ['account', 'l10n_id', 'base_accounting_kit'],
    'data': [
        'views/menus.xml',
        'data/labels.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
