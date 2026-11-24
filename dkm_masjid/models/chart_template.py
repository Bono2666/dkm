# -*- coding: utf-8 -*-
from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    def _post_load_data(self, template_code, company, template_data):
        res = super()._post_load_data(template_code, company, template_data)
        if template_code == 'id':
            self.env['dkm.masjid.setup']._setup_accounting(
                company or self.env.company)
        return res
