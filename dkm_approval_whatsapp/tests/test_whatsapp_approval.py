# -*- coding: utf-8 -*-
import re
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged

from odoo.addons.dkm_approval_whatsapp.models import fonnte
from odoo.addons.dkm_approval_whatsapp.models.approval_token import (
    PARAM_ENABLED, PARAM_TOKEN, DkmApprovalToken,
)
from odoo.addons.eh_account_base.tests.common import (
    EhAccountIntegrationTestCase,
)

PIN_MANAGER = '246810'
PIN_DIRECTOR = '975318'


@tagged('dkm_approval_whatsapp', 'post_install', '-at_install')
class TestWhatsappApproval(EhAccountIntegrationTestCase, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_bool(PARAM_ENABLED, True)
        cls.env['ir.config_parameter'].sudo().set_str(PARAM_TOKEN, 'test-token')
        expense = cls.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', cls.env.company.ids),
        ], limit=1) or cls.env['account.account'].create({
            'code': '5501', 'name': 'WA Test Expense',
            'account_type': 'expense',
            'company_ids': [(6, 0, cls.env.company.ids)],
        })
        cls.expense_account = expense
        cls.partner = cls.env['res.partner'].create({'name': 'Toko Bangunan'})
        cls.group_manager = cls.env.ref('eh_account_base.group_eh_manager')
        cls.group_director = cls.env['res.groups'].create({'name': 'DKM Ketua'})
        cls.env['eh.approval.policy'].create({
            'name': 'Pengeluaran > 1000',
            'document_type': 'in_invoice',
            'company_id': cls.env.company.id,
            'rule_ids': [(0, 0, {
                'name': 'Besar', 'sequence': 10,
                'min_amount': 1000.0, 'max_amount': 0.0,
                'step_ids': [
                    (0, 0, {'group_id': cls.group_manager.id, 'sequence': 10}),
                    (0, 0, {'group_id': cls.group_director.id, 'sequence': 20}),
                ],
            })],
        })
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_manager = Users.create({
            'name': 'Bendahara', 'login': 'wa_bendahara@test',
            'email': 'wa_bendahara@test', 'dkm_whatsapp': '0812-1111-2222',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })
        cls.user_director = Users.create({
            'name': 'Ketua DKM', 'login': 'wa_ketua@test',
            'email': 'wa_ketua@test', 'dkm_whatsapp': '+62 813 3333 4444',
            'group_ids': [(6, 0, [cls.group_director.id, cls.group_manager.id])],
        })
        cls.user_no_phone = Users.create({
            'name': 'Sekretaris', 'login': 'wa_sekretaris@test',
            'email': 'wa_sekretaris@test',
            'group_ids': [(6, 0, [cls.group_manager.id])],
        })
        cls.env.user.group_ids |= cls.group_manager
        cls.user_manager._dkm_set_approval_pin(PIN_MANAGER)
        cls.user_director._dkm_set_approval_pin(PIN_DIRECTOR)

    # ---- helpers ----

    @contextmanager
    def _capture(self):
        """Capture queued WhatsApp payloads instead of sending them."""
        sent = []

        def fake_queue(model, payloads):
            sent.extend(payloads)

        with patch.object(DkmApprovalToken, '_dkm_queue_send', fake_queue):
            yield sent

    def _raw_for(self, sent, user):
        for payload in sent:
            token = self.env['dkm.approval.token'].browse(payload['token_id'])
            if token.user_id == user:
                return payload['message'].split('/dkm/approval/')[1].split()[0]
        self.fail("No WhatsApp link captured for %s" % user.name)

    def _submit_bill(self, amount=2000.0):
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'invoice_date': '2026-11-01',
            'invoice_line_ids': [(0, 0, {
                'name': 'Semen 40 sak', 'quantity': 1, 'price_unit': amount,
                'account_id': self.expense_account.id,
            })],
        })
        with self._capture() as sent:
            bill.action_eh_request_approval()
        return bill.eh_active_approval_request_id, sent

    def _token(self, raw):
        return self.env['dkm.approval.token']._dkm_find(raw)

    # ---- tests ----

    def test_normalize_number(self):
        self.assertEqual(fonnte.normalize_wa_number('0812-1111-2222'), '6281211112222')
        self.assertEqual(fonnte.normalize_wa_number('+62 813 3333 4444'), '6281333334444')
        self.assertEqual(fonnte.normalize_wa_number('81211112222'), '6281211112222')
        self.assertEqual(fonnte.normalize_wa_number('12'), '')

    def test_submit_issues_links_to_first_step(self):
        request, sent = self._submit_bill()
        self.assertEqual(request.state, 'in_review')
        tokens = request.dkm_token_ids
        self.assertIn(self.user_manager, tokens.user_id)
        self.assertNotIn(self.env.user, tokens.user_id,
                         "The requester must not receive a link")
        targets = {p['target'] for p in sent}
        self.assertIn('6281211112222', targets)
        no_phone = tokens.filtered(lambda t: t.user_id == self.user_no_phone)
        self.assertEqual(no_phone.send_state, 'skipped')
        message = next(p['message'] for p in sent
                       if p['target'] == '6281211112222')
        self.assertIn(request.name, message)
        self.assertIn('/dkm/approval/', message)
        # Only the hash is stored.
        raw = self._raw_for(sent, self.user_manager)
        self.assertNotIn(raw, tokens.sudo().mapped('token_hash'))

    def test_disabled_sends_nothing(self):
        self.env['ir.config_parameter'].sudo().set_bool(PARAM_ENABLED, False)
        request, sent = self._submit_bill()
        self.assertFalse(request.dkm_token_ids)
        self.assertFalse(sent)

    def test_full_flow_with_pin(self):
        request, sent = self._submit_bill()
        raw = self._raw_for(sent, self.user_manager)
        token = self._token(raw)

        ok, msg = token._dkm_decide('approve', '', '111111')
        self.assertFalse(ok)
        self.assertIn('PIN salah', msg)
        self.assertEqual(request.state, 'in_review')
        self.assertEqual(request.current_step, 0)

        with self._capture() as sent_step2:
            ok, msg = token._dkm_decide('approve', '', PIN_MANAGER)
        self.assertTrue(ok, msg)
        self.assertEqual(request.current_step, 1)
        self.assertEqual(token.state, 'used')
        vote = request.vote_ids.filtered(lambda v: v.user_id == self.user_manager)
        self.assertEqual(vote.decision, 'approve')
        self.assertTrue(vote.comment)

        # The same link cannot be used twice.
        ok, msg = token._dkm_decide('approve', '', PIN_MANAGER)
        self.assertFalse(ok)
        self.assertIn('sudah dipakai', msg)

        # Step 2 goes to the director only (the manager signed step 1).
        new_users = self.env['dkm.approval.token'].browse(
            [p['token_id'] for p in sent_step2]).user_id
        self.assertEqual(new_users, self.user_director)

        director_raw = self._raw_for(sent_step2, self.user_director)
        ok, msg = self._token(director_raw)._dkm_decide(
            'approve', 'Bismillah, lanjut.', PIN_DIRECTOR)
        self.assertTrue(ok, msg)
        self.assertEqual(request.state, 'approved')
        log_users = request.log_ids.filtered(
            lambda l: l.action == 'approved').user_id
        self.assertEqual(log_users, self.user_manager | self.user_director)

    def test_other_approver_pin_does_not_work(self):
        request, sent = self._submit_bill()
        token = self._token(self._raw_for(sent, self.user_manager))
        ok, _msg = token._dkm_decide('approve', '', PIN_DIRECTOR)
        self.assertFalse(ok)
        self.assertFalse(request.vote_ids)

    def test_pin_lockout(self):
        request, sent = self._submit_bill()
        token = self._token(self._raw_for(sent, self.user_manager))
        for _i in range(5):
            ok, msg = token._dkm_decide('approve', '', '000001')
            self.assertFalse(ok)
        self.assertIn('dikunci', msg)
        ok, msg = token._dkm_decide('approve', '', PIN_MANAGER)
        self.assertFalse(ok, "A correct PIN must not work while locked")
        self.assertIn('terkunci', msg)
        self.user_manager.sudo().dkm_pin_locked_until = \
            fields.Datetime.now() - timedelta(minutes=1)
        with self._capture():
            ok, msg = token._dkm_decide('approve', '', PIN_MANAGER)
        self.assertTrue(ok, msg)

    def test_reject_requires_reason(self):
        request, sent = self._submit_bill()
        token = self._token(self._raw_for(sent, self.user_manager))
        ok, msg = token._dkm_decide('reject', '  ', PIN_MANAGER)
        self.assertFalse(ok)
        self.assertEqual(request.state, 'in_review')
        ok, msg = token._dkm_decide('reject', 'Harga terlalu mahal', PIN_MANAGER)
        self.assertTrue(ok, msg)
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(request.rejection_reason, 'Harga terlalu mahal')

    def test_expired_and_revoked_links(self):
        request, sent = self._submit_bill()
        raw = self._raw_for(sent, self.user_manager)
        token = self._token(raw)
        token.expires_at = fields.Datetime.now() - timedelta(hours=1)
        ok, msg = token._dkm_decide('approve', '', PIN_MANAGER)
        self.assertFalse(ok)
        self.assertIn('kadaluarsa', msg)

        with self._capture() as resent:
            request.action_dkm_resend_whatsapp()
        self.assertEqual(token.state, 'revoked')
        new_token = self._token(self._raw_for(resent, self.user_manager))
        self.assertEqual(new_token.state, 'active')
        with self._capture():
            ok, msg = new_token._dkm_decide('approve', '', PIN_MANAGER)
        self.assertTrue(ok, msg)

    def test_withdrawn_request_link_dead(self):
        request, sent = self._submit_bill()
        token = self._token(self._raw_for(sent, self.user_manager))
        request.action_withdraw(reason='Salah input')
        ok, msg = token._dkm_decide('approve', '', PIN_MANAGER)
        self.assertFalse(ok)
        self.assertIn('tidak lagi menunggu', msg)

    def test_no_pin_set(self):
        request, sent = self._submit_bill()
        token = self._token(self._raw_for(sent, self.user_manager))
        self.user_manager.sudo().dkm_approval_pin_hash = False
        ok, msg = token._dkm_decide('approve', '', '')
        self.assertFalse(ok)
        self.assertIn('belum mengatur PIN', msg)

    def test_pin_rules_and_ownership(self):
        with self.assertRaises(UserError):
            self.user_manager._dkm_set_approval_pin('12345')
        with self.assertRaises(UserError):
            self.user_manager._dkm_set_approval_pin('111111')
        with self.assertRaises(UserError):
            self.user_manager._dkm_set_approval_pin('123456')
        with self.assertRaises(AccessError):
            self.user_director.with_user(self.user_manager)._dkm_set_approval_pin('864209')
        self.user_manager.with_user(self.user_manager)._dkm_set_approval_pin('864209')
        self.assertTrue(self.user_manager.with_user(self.user_manager).dkm_has_approval_pin)

    def test_send_now_records_result(self):
        request, sent = self._submit_bill()
        with patch.object(fonnte, 'send_message', return_value=(True, '123')):
            self.env['dkm.approval.token']._dkm_send_now(sent[:1])
        token = self.env['dkm.approval.token'].browse(sent[0]['token_id'])
        self.assertEqual(token.send_state, 'sent')
        with patch.object(fonnte, 'send_message',
                          return_value=(False, 'Fonnte menolak: invalid token')):
            self.env['dkm.approval.token']._dkm_send_now(sent[:1])
        self.assertEqual(token.send_state, 'failed')
        self.assertIn('invalid token', token.send_detail)

    def test_mobile_page(self):
        request, sent = self._submit_bill()
        raw = self._raw_for(sent, self.user_manager)
        response = self.url_open('/dkm/approval/%s' % raw)
        self.assertEqual(response.status_code, 200)
        self.assertIn(request.name, response.text)
        self.assertIn('Semen 40 sak', response.text)
        self.assertIn('csrf_token', response.text)
        self.assertEqual(response.headers.get('Cache-Control'), 'no-store')
        response = self.url_open('/dkm/approval/not-a-real-token')
        self.assertEqual(response.status_code, 404)

    def test_mobile_post_decision(self):
        request, sent = self._submit_bill()
        raw = self._raw_for(sent, self.user_manager)
        page = self.url_open('/dkm/approval/%s' % raw).text
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        url = '/dkm/approval/%s/decide' % raw

        response = self.url_open(url, data={
            'csrf_token': csrf, 'decision': 'approve', 'pin': '000002'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('PIN salah', response.text)
        self.assertEqual(request.current_step, 0)

        with self._capture():
            response = self.url_open(url, data={
                'csrf_token': csrf, 'decision': 'approve',
                'comment': 'Sesuai RAB', 'pin': PIN_MANAGER})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Persetujuan Anda sudah tercatat', response.text)
        request.invalidate_recordset()
        self.assertEqual(request.current_step, 1)

        response = self.url_open('/dkm/approval/%s' % raw)
        self.assertEqual(response.status_code, 410)
