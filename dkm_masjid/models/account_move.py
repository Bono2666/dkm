# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, fields, models
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


# Receipts and refunds are money that changes hands on the spot: posting
# one also records the cash or bank movement (no separate "Bayar" step).
RECEIPT_TYPES = ('out_invoice', 'out_refund')
# Chatter of a receipt: no payment status ("Faktur lunas", Belum Lunas ->
# Lunas), no number/reference lines; the confirmation message names it.
RECEIPT_UNTRACKED = {'name', 'payment_reference', 'payment_state', 'status_in_payment'}
# Journal item fields Odoo fills in by itself when a receipt is posted.
RECEIPT_LINE_UNTRACKED = {'name', 'label', 'date_maturity'}


class AccountMove(models.Model):
    _inherit = 'account.move'

    dkm_receipt_journal_id = fields.Many2one(
        'account.journal', string="Diterima di",
        compute='_compute_dkm_receipt_journal_id', store=True, readonly=False,
        check_company=True,
        domain="[('type', 'in', ('cash', 'bank'))]",
        help="Kas atau rekening bank tempat uang diterima (atau dikembalikan). "
             "Uangnya tercatat saat nota dikonfirmasi.")

    @api.depends('move_type', 'company_id')
    def _compute_dkm_receipt_journal_id(self):
        for move in self:
            if move.move_type not in RECEIPT_TYPES:
                move.dkm_receipt_journal_id = False
            elif move.dkm_receipt_journal_id.company_id != move.company_id:
                journals = self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(move.company_id),
                    ('type', 'in', ('cash', 'bank')),
                ])
                move.dkm_receipt_journal_id = (
                    journals.filtered(lambda j: j.type == 'cash')[:1] or journals[:1])

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        for move in posted.filtered(lambda m: (
                m.move_type in RECEIPT_TYPES and m.dkm_receipt_journal_id
                and m.payment_state == 'not_paid'
                and not m.currency_id.is_zero(m.amount_residual))):
            payments = self.env['account.payment.register'].with_context(
                active_model='account.move', active_ids=move.ids,
                dont_redirect_to_payments=True,
            ).create({
                'journal_id': move.dkm_receipt_journal_id.id,
                'payment_date': move.invoice_date or move.date,
            })._create_payments()
            payments.dkm_auto_receipt = True
        return posted

    def _mail_track(self, tracked_fields_get, initial_values):
        changes, tracking_values = super()._mail_track(tracked_fields_get, initial_values)
        if self.move_type in RECEIPT_TYPES:
            changes = {fname for fname in changes if fname not in RECEIPT_UNTRACKED}
            tracking_values = [vals for vals in tracking_values
                               if vals.get('field_name') not in RECEIPT_UNTRACKED]
        return changes, tracking_values

    # A confirmed receipt shows its subtype, "Nota Penerimaan dikonfirmasi".
    # Refunds share that sale subtype, so they log their own line instead.
    def _track_log_get_default_subtype(self, track_init_values):
        if (self.move_type == 'out_refund' and 'state' in track_init_values
                and self.state == 'posted'):
            return self.env['mail.message.subtype']
        return super()._track_log_get_default_subtype(track_init_values)

    def _track_log_get_default_body(self, track_init_values):
        if (self.move_type == 'out_refund' and 'state' in track_init_values
                and self.state == 'posted'):
            return "Pengembalian Dana dikonfirmasi"
        return super()._track_log_get_default_body(track_init_values)

    def _track_record(self, records, track_fnames, initial_values=None,
                      end_values=None, author=None, body=None):
        if records._name == 'account.move.line' and self and all(
                move.move_type in RECEIPT_TYPES for move in self):
            track_fnames = [fname for fname in track_fnames
                            if fname not in RECEIPT_LINE_UNTRACKED]
            if not track_fnames:
                return
        return super()._track_record(records, track_fnames, initial_values=initial_values,
                                     end_values=end_values, author=author, body=body)

    def button_draft(self):
        # A receipt back in draft has not received anything yet: cancel the
        # payment its posting made, so posting again does not count it twice.
        receipts = self.filtered(lambda m: m.move_type in RECEIPT_TYPES and m.state == 'posted')
        auto = receipts._get_reconciled_payments().filtered(
            lambda p: p.dkm_auto_receipt and p.state != 'canceled')
        for payment in auto:
            payment.action_draft()
            payment.action_cancel()
        return super().button_draft()

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

    dkm_auto_receipt = fields.Boolean(
        copy=False, readonly=True,
        help="Made when its Nota Penerimaan or Pengembalian Dana was confirmed.")

    def _compute_display_name(self):
        super()._compute_display_name()
        if is_indonesian(self.env):
            for payment in self:
                payment.display_name = draf_wording(payment.display_name)

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """Pembayaran Masuk/Keluar are a history: payments come from
        confirming a Nota Penerimaan or the "Bayar" button of a Tagihan, which
        also record the income or expense. Only the admin creates payments
        directly."""
        result = super().get_view(view_id, view_type, **options)
        if (view_type in ('list', 'kanban', 'form')
                and not self.env.user.has_group('account.group_account_manager')):
            node = etree.fromstring(result['arch'])
            node.set('create', '0')
            result['arch'] = etree.tostring(node, encoding='unicode')
        return result
