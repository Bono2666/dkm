# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, models
from odoo.tools.translate import code_translations

from .masjid_setup import draf_wording, is_indonesian

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
        if is_indonesian(self.env):
            # "Draft Entry", "Rancangan Tagihan", ... come from account's code.
            name = draf_wording(name)
        return name


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _compute_display_name(self):
        super()._compute_display_name()
        if is_indonesian(self.env):
            for payment in self:
                payment.display_name = draf_wording(payment.display_name)

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """Pembayaran Masuk/Keluar are a history: payments come from the
        "Bayar" button of a Nota Penerimaan or Tagihan, which also records the
        income or expense. Only the admin creates payments directly."""
        result = super().get_view(view_id, view_type, **options)
        if (view_type in ('list', 'kanban', 'form')
                and not self.env.user.has_group('account.group_account_manager')):
            node = etree.fromstring(result['arch'])
            node.set('create', '0')
            result['arch'] = etree.tostring(node, encoding='unicode')
        return result
