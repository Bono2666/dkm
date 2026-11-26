# -*- coding: utf-8 -*-
{
    'name': 'DKM - Penggajian & Kasbon Pegawai',
    'summary': 'Penggajian bulanan dengan satu persetujuan, dan kasbon pegawai yang dicicil dari gaji.',
    'description': """
Kasbon Pegawai
==============

* Menu Pengeluaran > Kasbon Pegawai: pegawai, jumlah, jumlah cicilan dan
  sumber dana (Tunai/Bank). Satu pegawai hanya boleh punya satu kasbon
  aktif.
* Kasbon dicatat sebagai entri di jurnal "Kasbon Pegawai" (Debit Piutang
  Kasbon Pegawai, Kredit Kas/Bank), sehingga kebijakan persetujuan ERP
  Heritage untuk jurnal itu berlaku sebelum dana dicairkan.
* Menu Pengeluaran > Penggajian: satu penggajian per bulan berisi gaji,
  tunjangan dan potongan kasbon setiap pegawai. Totalnya diajukan sekali
  ke kebijakan persetujuan jurnal "Penggajian"; setelah disetujui dan
  dikonfirmasi (Debit Gaji/Tunjangan, Kredit Piutang Kasbon dan Hutang Gaji
  Pegawai), gaji dibayar per pegawai dengan tombol "Bayar Gaji".
* Potongan kasbon melunasi sebagian kasbon saat penggajian dikonfirmasi.
  Sisa kasbon dan status Lunas terhitung otomatis.
* Tagihan ke pegawai dengan akun gaji ditolak: gaji wajib lewat Penggajian.
""",
    'author': 'DKM',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '20.0.1.2.0',
    'depends': ['dkm_masjid', 'hr', 'eh_account_approval'],
    'data': [
        'security/ir.access.csv',
        'data/sequence.xml',
        'views/kasbon_views.xml',
        'views/payroll_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
