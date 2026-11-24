# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """20.0.1.5.0 gave the receipt categories internal references
    (DKM-INFAQ...), which were printed on receipts: drop them."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['product.template'].with_context(active_test=False).search([
        ('default_code', 'in', ['DKM-INFAQ', 'DKM-ZAKAT', 'DKM-WAKAF', 'DKM-SEWA']),
    ]).write({'default_code': False})
