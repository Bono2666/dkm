# -*- coding: utf-8 -*-
from odoo import models

# base_accounting_kit builds its XLSX exports from plain English strings
# (not marked for translation), so they are translated here, on the table
# every export goes through, for Indonesian users.
XLSX_TERMS_ID = {
    # Report titles and file names
    "Aged Partner Balance": "Umur Piutang & Utang",
    "Bank Book": "Buku Bank",
    "Cash Book": "Buku Kas",
    "Cash Flow Report": "Laporan Arus Kas",
    "Day Book": "Buku Harian",
    "Financial Report": "Laporan Keuangan",
    "General Ledger": "Buku Besar",
    "Journal Audit": "Audit Jurnal",
    "Partner Ledger": "Buku Besar Donatur & Vendor",
    "Report": "Laporan",
    "Tax Report": "Laporan Pajak",
    "Trial Balance": "Neraca Saldo",
    # Heading rows
    "Company": "Masjid",
    "Period": "Periode",
    "Target Moves": "Entri yang Disertakan",
    "All Posted Entries": "Semua Entri Terekam",
    "All Entries": "Semua Entri",
    # Column headers
    "Account": "Akun",
    "Balance": "Saldo",
    "Code": "Kode",
    "Comparison": "Pembanding",
    "Comparison Balance": "Saldo Pembanding",
    "Credit": "Kredit",
    "Date": "Tanggal",
    "Date / Account": "Tanggal / Akun",
    "Debit": "Debit",
    "Entry": "Entri",
    "JRNL": "Jurnal",
    "Label": "Keterangan",
    "Move": "Entri",
    "Name": "Nama",
    "Net": "Neto",
    "Not Due": "Belum Jatuh Tempo",
    "Partner": "Donatur/Vendor",
    "Ref": "Ref",
    "Tax": "Pajak",
    "Tax Amount": "Jumlah Pajak",
    "Total": "Total",
    "Variance": "Selisih",
    # Row labels
    "Purchases": "Pembelian",
    "Sales": "Penjualan",
}


def _translate(value):
    if isinstance(value, str):
        return XLSX_TERMS_ID.get(value, value)
    return value


class ReportXlsxMixin(models.AbstractModel):
    _inherit = 'account.report.xlsx.mixin'

    def _xlsx_action(self, report_name, table):
        if (self.env.lang or '').startswith('id'):
            report_name = _translate(report_name)
            table = dict(table)
            table['title'] = _translate(table.get('title'))
            table['meta'] = [[_translate(label), _translate(value)]
                             for label, value in table.get('meta', [])]
            table['columns'] = [dict(col, label=_translate(col.get('label')))
                                for col in table.get('columns', [])]
            table['rows'] = [dict(row, cells=[_translate(c) for c in row.get('cells', [])])
                             for row in table.get('rows', [])]
        return super()._xlsx_action(report_name, table)
