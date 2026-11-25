# -*- coding: utf-8 -*-
import re

from odoo import api, models
from odoo.tools.translate import code_translations

# Customer invoices are used to record mosque receipts.
TYPE_NAMES = {
    'out_invoice': "Nota Penerimaan",
    'out_refund': "Pengembalian Dana",
}
# The committee writes "Draf" (KBBI), not "Draft".
DRAFT_WORD = re.compile(r'\b([Dd])raft\b')
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

    def _get_mail_template(self):
        for move_type, xmlid in (('out_invoice', 'dkm_masjid.mail_template_receipt'),
                                 ('out_refund', 'dkm_masjid.mail_template_refund')):
            if self and all(move.move_type == move_type for move in self):
                template = self.env.ref(xmlid, raise_if_not_found=False)
                if template:
                    return template
        return super()._get_mail_template()

    def _get_move_display_name(self, show_ref=False):
        name = super()._get_move_display_name(show_ref=show_ref)
        source = DRAFT_SOURCES.get(self.move_type)
        if self.state == 'draft' and source:
            translated = code_translations.get_python_translations(
                'account', self.env.lang or 'en_US').get(source, source)
            if name.startswith(translated):
                name = f"{TYPE_NAMES[self.move_type]} Draf{name[len(translated):]}"
        if (self.env.lang or '').startswith('id'):
            # "Draft Entry", "Draft Nota Kredit", ... come from account's code.
            name = DRAFT_WORD.sub(r"\1raf", name)
        return name
