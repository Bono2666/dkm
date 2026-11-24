# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    """Apply the mosque chart adjustments to companies that already run the
    Indonesian chart; new ones get them when the chart is loaded."""
    companies = env['res.company'].search([('chart_template', '=', 'id')])
    env['dkm.masjid.setup']._setup_accounting(companies)
