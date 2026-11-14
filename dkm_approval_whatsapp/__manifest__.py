# -*- coding: utf-8 -*-
{
    'name': 'DKM - Approval via WhatsApp',
    'summary': 'Kirim link persetujuan ke WhatsApp pengurus (Fonnte) dan '
               'setujui/tolak dari HP dengan PIN pribadi.',
    'description': """
Approval via WhatsApp untuk DKM
===============================

* Setiap kali sebuah tahap approval membutuhkan tanda tangan, setiap
  approver yang berhak menerima pesan WhatsApp (via Fonnte) berisi
  ringkasan pengajuan dan link unik.
* Link membuka halaman ringan yang ramah HP: rincian pengeluaran,
  riwayat persetujuan, lalu tombol Setujui / Tolak.
* Keputusan memerlukan PIN 6 digit milik approver. PIN disimpan
  ter-hash; 5x salah PIN mengunci sementara.
* Link berlaku satu kali, kadaluarsa otomatis, dan hanya untuk approver
  yang dituju. Keputusan dijalankan sebagai user approver tersebut,
  sehingga semua aturan approval (urutan tahap, pemisahan tugas, N-of-M)
  dan log audit tetap berlaku.
""",
    'author': 'DKM',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'version': '20.0.1.0.0',
    'depends': ['eh_account_approval'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.access.csv',
        'wizards/pin_wizard_views.xml',
        'views/res_users_views.xml',
        'views/approval_request_views.xml',
        'views/res_config_settings_views.xml',
        'views/mobile_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
