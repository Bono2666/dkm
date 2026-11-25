# -*- coding: utf-8 -*-
from odoo import api, models

from .masjid_setup import PAYMENT_METHOD_NAMES, PAYMENT_METHOD_OLD_NAMES


class AccountPaymentMethodLine(models.Model):
    _inherit = 'account.payment.method.line'

    @api.depends('payment_method_id.name')
    def _compute_name(self):
        """New journals (also those made by code in English) get the
        Indonesian method name, e.g. "Tunai/Transfer" for manual payments."""
        super()._compute_name()
        for line in self:
            name = PAYMENT_METHOD_NAMES.get(line.payment_method_id.code)
            if name and line.name in PAYMENT_METHOD_OLD_NAMES:
                line.name = name
