# -*- coding: utf-8 -*-
{
    'name': 'DKM - Kegiatan',
    'summary': 'Dana masuk dan keluar per kegiatan (Qurban, Ramadhan, ...), '
               'anggaran vs realisasi dan laporan kegiatan untuk jamaah.',
    'description': """
Kegiatan
========

* Menu Keuangan > Kegiatan: nama, periode, divisi penanggung jawab dan
  anggaran per pos (penerimaan dan pengeluaran).
* Isian Kegiatan pada Nota Penerimaan dan Tagihan, serta kolom Pos
  Anggaran per baris. Kategori penerimaan "Donasi Kegiatan" (akun
  41000050) menambah Sumber Dana "Dana Kegiatan"; tagihan kegiatan
  otomatis memakai Dana Kegiatan dan bisa diganti (subsidi dari Dana Umum).
* Laporan > Laporan Kegiatan (pivot/daftar) dan PDF Laporan Kegiatan:
  ringkasan, anggaran vs realisasi, rincian transaksi dan tanda tangan.
""",
    'author': 'DKM',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '20.0.1.0.0',
    'depends': ['dkm_masjid'],
    'data': [
        'security/ir.access.csv',
        'data/funds.xml',
        'data/setup.xml',
        'views/activity_views.xml',
        'views/account_move_views.xml',
        'views/report_views.xml',
        'report/activity_report.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
