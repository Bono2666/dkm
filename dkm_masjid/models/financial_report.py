# -*- coding: utf-8 -*-
from odoo import models

# base_accounting_kit widens these balance-sheet lines by comparing
# report.name with "Assets" / "Liability". dkm_masjid relabels them in
# Indonesian, and on a database without en_US that also replaces the source
# term, so select the accounts by xmlid instead.
WIDENED_LINES = {
    'base_accounting_kit.account_financial_report_assets0': [
        'asset_receivable', 'asset_cash', 'asset_current',
        'asset_non_current', 'asset_prepayments', 'asset_fixed',
    ],
    'base_accounting_kit.account_financial_report_liability0': [
        'liability_payable', 'equity', 'liability_current',
        'liability_non_current',
    ],
}
FIELDS = ('credit', 'debit', 'balance')


class FinancialReport(models.TransientModel):
    _inherit = 'financial.report'

    def _compute_report_balance(self, reports):
        widened = {}
        for xmlid, account_types in WIDENED_LINES.items():
            line = self.env.ref(xmlid, raise_if_not_found=False)
            if line:
                widened[line.id] = account_types

        res = {}
        rest = reports.browse()
        for report in reports:
            account_types = widened.get(report.id)
            if report.type != 'account_type' or not account_types:
                rest |= report
                continue
            accounts = self.env['account.account'].search([
                ('account_type', 'in', account_types),
            ])
            balances = self._compute_account_balance(accounts)
            res[report.id] = {fname: 0.0 for fname in FIELDS}
            res[report.id]['account'] = balances
            for value in balances.values():
                for fname in FIELDS:
                    res[report.id][fname] += value.get(fname)
        if rest:
            res.update(super()._compute_report_balance(rest))
        return res
