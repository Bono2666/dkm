# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Receipt categories were added in 20.0.1.5.0; the chart setup that
    creates them already ran on existing databases."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([('chart_template', '=', 'id')])
    env['dkm.masjid.setup']._setup_receipt_categories(companies)
