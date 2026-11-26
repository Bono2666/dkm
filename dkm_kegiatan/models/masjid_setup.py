# -*- coding: utf-8 -*-
from odoo import api, models

ACTIVITY_ACCOUNT = ('41000050', "Penerimaan Donasi Kegiatan (Dana Terikat)")
ACTIVITY_CATEGORY = "Donasi Kegiatan"


class DkmMasjidSetup(models.AbstractModel):
    _inherit = 'dkm.masjid.setup'

    @api.model
    def _setup_activity_category(self, companies=None):
        """The "Donasi Kegiatan" receipt category (account 41000050, fund
        Dana Kegiatan) for every company on the mosque chart."""
        fund = self.env.ref('dkm_kegiatan.fund_kegiatan', raise_if_not_found=False)
        code, account_name = ACTIVITY_ACCOUNT
        for company in companies or self.env['res.company'].search([]):
            env = self.with_company(company).env
            Account = env['account.account'].with_context(active_test=False)
            if not Account.search([('code', '=', '41000010'),
                                   ('company_ids', 'in', company.id)], limit=1):
                continue    # not the mosque chart
            account = Account.search([('code', '=', code),
                                      ('company_ids', 'in', company.id)], limit=1)
            if not account:
                account = Account.create({'code': code, 'name': account_name,
                                          'account_type': 'income',
                                          'company_ids': [(6, 0, company.ids)]})
                self._set_name(account, account_name)
            Product = env['product.template'].with_context(active_test=False)
            if Product.search([('name', '=', ACTIVITY_CATEGORY), ('sale_ok', '=', True),
                               ('company_id', '=', company.id)], limit=1):
                continue
            product = Product.create({
                'name': ACTIVITY_CATEGORY, 'type': 'service',
                'sale_ok': True, 'purchase_ok': False, 'list_price': 0.0,
                'taxes_id': [(5, 0, 0)], 'supplier_taxes_id': [(5, 0, 0)],
                'company_id': company.id,
                'property_account_income_id': account.id,
                'dkm_fund_id': fund.id if fund else False,
            })
            self._set_name(product, ACTIVITY_CATEGORY)

    def _setup_accounting(self, companies):
        res = super()._setup_accounting(companies)
        self._setup_activity_category(companies)
        return res
