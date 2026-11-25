# -*- coding: utf-8 -*-
{
    'name': 'DKM - Kasbon Pegawai',
    'summary': 'Kasbon pegawai masjid yang dicicil lewat potongan gaji.',
    'description': """
Kasbon Pegawai
==============

* Menu Pengeluaran > Kasbon Pegawai: pegawai, jumlah, jumlah cicilan dan
  sumber dana (Tunai/Bank). Satu pegawai hanya boleh punya satu kasbon
  aktif.
* Kasbon dicatat sebagai entri di jurnal "Kasbon Pegawai" (Debit Piutang
  Kasbon Pegawai, Kredit Kas/Bank), sehingga kebijakan persetujuan ERP
  Heritage untuk jurnal itu berlaku sebelum dana dicairkan.
* Tagihan gaji pegawai: tombol "Potong Kasbon" menambahkan baris potongan
  cicilan (ke akun Piutang Kasbon Pegawai); saat tagihan dibukukan,
  potongan itu melunasi sebagian kasbon. Sisa kasbon dan status Lunas
  terhitung otomatis.
""",
    'author': 'DKM',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '20.0.1.0.0',
    'depends': ['dkm_masjid', 'hr', 'eh_account_approval'],
    'data': [
        'security/ir.access.csv',
        'data/sequence.xml',
        'views/kasbon_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
