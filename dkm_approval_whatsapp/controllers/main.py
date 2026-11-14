# -*- coding: utf-8 -*-
"""Public mobile pages behind the WhatsApp approval link.

GET shows the request; POST records a decision after PIN verification.
Both run as the public user and reach data only through the token, which
is resolved by its hash. The decision itself runs as the bound approver.
"""

from odoo import fields, http
from odoo.http import request
from odoo.tools.misc import format_amount, format_date, format_datetime

MAX_LINES = 30

STATE_LABELS = {
    'pending': "Draf",
    'in_review': "Menunggu persetujuan",
    'approved': "Disetujui penuh",
    'rejected': "Ditolak",
    'withdrawn': "Ditarik",
    'archived': "Selesai (diposting)",
}

SECURITY_HEADERS = [
    ('Cache-Control', 'no-store'),
    ('Referrer-Policy', 'no-referrer'),
    ('X-Robots-Tag', 'noindex, nofollow'),
    ('X-Frame-Options', 'DENY'),
]


class DkmApprovalController(http.Controller):

    def _render(self, template, values, status=200):
        return request.render(template, values, headers=SECURITY_HEADERS,
                              status=status)

    def _error(self, message, status=404):
        return self._render('dkm_approval_whatsapp.mobile_message', {
            'title': "Link tidak dapat digunakan",
            'message': message,
            'ok': False,
            'approval': None,
        }, status=status)

    def _page_values(self, token, raw, error=None, comment=''):
        approval = token.request_id
        move = approval.move_id
        user = token.user_id
        env = request.env(context=dict(
            request.env.context, lang=user.lang or 'id_ID',
            tz=user.tz or 'Asia/Jakarta'))
        currency = approval.currency_id

        def money(amount, cur=None):
            return format_amount(env, amount or 0.0, cur or currency)

        if move.is_invoice(include_receipts=True):
            lines = [{
                'label': line.name or line.product_id.display_name or '-',
                'detail': '%s × %s' % (
                    ('%g' % line.quantity), money(line.price_unit, move.currency_id)),
                'amount': money(line.price_total, move.currency_id),
            } for line in move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product')[:MAX_LINES]]
            total = money(move.amount_total, move.currency_id)
        else:
            lines = [{
                'label': '%s %s' % (line.account_id.code or '',
                                    line.account_id.name or ''),
                'detail': line.name or '',
                'amount': (money(line.debit) + ' D') if line.debit
                else (money(line.credit) + ' K'),
            } for line in move.line_ids[:MAX_LINES]]
            total = money(approval.submitted_amount)

        decision_labels = {'approve': "Disetujui", 'reject': "Ditolak"}
        votes = [{
            'name': vote.user_id.name,
            'decision': vote.decision,
            'decision_label': decision_labels.get(vote.decision, vote.decision),
            'comment': vote.comment or '',
            'when': format_datetime(env, vote.voted_at, tz=env.context['tz'], dt_format='short')
            if vote.voted_at else '',
            'step': vote.step_index + 1,
        } for vote in approval.vote_ids.filtered(
            lambda v: v.cycle == approval.approval_cycle
        ).sorted(lambda v: (v.voted_at or fields.Datetime.now(), v.id))]

        return {
            'token_raw': raw,
            'company': approval.company_id,
            'approver': user,
            'approval': approval,
            'move': move,
            'partner_name': move.partner_id.display_name
            or approval.request_partner_id.display_name or '',
            'doc_name': move.name if move.name and move.name != '/'
            else (move.ref or '-'),
            'doc_date': format_date(env, move.invoice_date or move.date),
            'amount': money(approval.submitted_amount),
            'total': total,
            'lines': lines,
            'more_lines': max(0, len(
                move.invoice_line_ids if move.is_invoice(include_receipts=True)
                else move.line_ids) - MAX_LINES),
            'description': move.narration or '',
            'ref': move.ref or approval.request_reference or '',
            'note': approval.request_note or '',
            'requester': approval.requested_by_id.name,
            'step_label': "Tahap %s dari %s" % (
                min(approval.current_step + 1, approval.total_steps),
                approval.total_steps) if approval.total_steps > 1 else '',
            'expires': format_datetime(env, token.expires_at, tz=env.context['tz'],
                                       dt_format='short'),
            'votes': votes,
            'error': error,
            'comment': comment,
        }

    @http.route('/dkm/approval/<string:token>', type='http', auth='public',
                methods=['GET'])
    def approval_page(self, token, **kwargs):
        record = request.env['dkm.approval.token']._dkm_find(token)
        if not record:
            return self._error("Link tidak dikenal. Periksa kembali pesan "
                               "WhatsApp Anda.")
        reason = record._dkm_unusable_reason()
        if reason:
            return self._error(reason, status=410)
        return self._render('dkm_approval_whatsapp.mobile_approval_page',
                            self._page_values(record, token))

    @http.route('/dkm/approval/<string:token>/decide', type='http',
                auth='public', methods=['POST'])
    def approval_decide(self, token, decision=None, comment=None, pin=None,
                        **kwargs):
        record = request.env['dkm.approval.token']._dkm_find(token)
        if not record:
            return self._error("Link tidak dikenal. Periksa kembali pesan "
                               "WhatsApp Anda.")
        ok, message = record._dkm_decide(decision, comment, pin)
        if ok:
            return self._render('dkm_approval_whatsapp.mobile_message', {
                'title': "Disetujui" if decision == 'approve' else "Ditolak",
                'message': message,
                'ok': True,
                'decision': decision,
                'approval': record.request_id,
                'state_label': STATE_LABELS.get(
                    record.request_id.state, record.request_id.state),
            })
        record.invalidate_recordset()
        if record._dkm_unusable_reason():
            return self._error(message, status=410)
        return self._render('dkm_approval_whatsapp.mobile_approval_page',
                            self._page_values(record, token, error=message,
                                              comment=comment or ''),
                            status=400)
