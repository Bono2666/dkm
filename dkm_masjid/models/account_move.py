# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.tools.translate import code_translations

# Customer invoices are used to record mosque receipts.
TYPE_NAMES = {
    'out_invoice': "Nota Penerimaan",
    'out_refund': "Pengembalian Dana",
}
DRAFT_SOURCES = {
    'out_invoice': 'Draft Invoice',
    'out_refund': 'Draft Credit Note',
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('move_type')
    def _compute_type_name(self):
        super()._compute_type_name()
        for move in self:
            if move.move_type in TYPE_NAMES:
                move.type_name = TYPE_NAMES[move.move_type]

    def _get_move_display_name(self, show_ref=False):
        name = super()._get_move_display_name(show_ref=show_ref)
        source = DRAFT_SOURCES.get(self.move_type)
        if self.state == 'draft' and source:
            translated = code_translations.get_python_translations(
                'account', self.env.lang or 'en_US').get(source, source)
            if name.startswith(translated):
                name = f"{TYPE_NAMES[self.move_type]} Draft{name[len(translated):]}"
        return name
