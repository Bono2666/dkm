# -*- coding: utf-8 -*-
from odoo import api, models

# Dashboard header cards (account.journal.get_account_dashboard_kpis), by id.
KPI_LABELS = {
    'invoices': "Penerimaan",
    'expenses': "Pengeluaran",
    'cash': "Kas",
    'receivable': "Piutang",
    'payable': "Utang",
    'invoice_layout': "Atur Kop Laporan",
}


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    @api.model
    def get_account_dashboard_kpis(self):
        cards = super().get_account_dashboard_kpis()
        for card in cards:
            card['name'] = KPI_LABELS.get(card.get('id'), card['name'])
        return cards

    def _get_onboarding_action_data(self):
        data = super()._get_onboarding_action_data()
        if data and data.get('title'):
            data = dict(data, title="Pengaturan Keuangan")
        return data
