# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """Receipt numbering (PNR/...) was added in 20.0.1.6.0."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([('chart_template', '=', 'id')])
    env['dkm.masjid.setup']._setup_receipt_numbering(companies)
