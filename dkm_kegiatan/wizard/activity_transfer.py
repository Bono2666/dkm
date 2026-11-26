# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

RESTRICTED_NET_ASSETS = '31210010'      # Aset Neto Terikat
UNRESTRICTED_NET_ASSETS = '31100020'    # Aset Neto Tidak Terikat


class DkmActivityTransfer(models.TransientModel):
    """Move an activity's unused Dana Kegiatan to Dana Umum/Operasional or to
    another activity. No cash moves: it reclassifies net assets (Aset Neto
    Terikat -> Tidak Terikat, or between activities)."""
    _name = 'dkm.activity.transfer'
    _description = "Pindahkan Sisa Dana Kegiatan"

    activity_id = fields.Many2one('dkm.activity', string="Dari Kegiatan", required=True,
                                  readonly=True)
    company_id = fields.Many2one(related='activity_id.company_id')
    currency_id = fields.Many2one(related='activity_id.currency_id')
    remainder = fields.Monetary(related='activity_id.fund_remainder', string="Sisa Dana Kegiatan")
    amount = fields.Monetary("Jumlah", required=True, compute='_compute_amount',
                             store=True, readonly=False, precompute=True)
    target = fields.Selection([
        ('fund', "Sumber Dana lain (mis. Dana Umum)"),
        ('activity', "Kegiatan lain (mis. Qurban tahun depan)"),
    ], string="Pindahkan ke", required=True, default='fund')
    fund_id = fields.Many2one(
        'dkm.fund', string="Sumber Dana",
        default=lambda self: self.env.ref('dkm_masjid.fund_umum', raise_if_not_found=False),
        domain="[('id', '!=', kegiatan_fund_id)]")
    kegiatan_fund_id = fields.Many2one(
        'dkm.fund', default=lambda self: self.env.ref('dkm_kegiatan.fund_kegiatan'))
    target_activity_id = fields.Many2one(
        'dkm.activity', string="Kegiatan Tujuan",
        domain="[('id', '!=', activity_id), ('state', 'in', ('draft', 'open')), "
               "('company_id', '=', company_id)]")
    date = fields.Date("Tanggal", required=True, default=fields.Date.context_today)
    note = fields.Char("Keterangan")

    @api.depends('activity_id')
    def _compute_amount(self):
        for wizard in self:
            wizard.amount = max(wizard.activity_id.fund_remainder, 0.0)

    def _account(self, code):
        Account = self.env['account.account'].with_company(self.company_id)
        account = Account.search([*Account._check_company_domain(self.company_id),
                                  ('code', '=', code)], limit=1)
        if not account:
            raise UserError(f"Akun {code} tidak ditemukan di bagan akun.")
        return account

    def _journal(self):
        Journal = self.env['account.journal']
        domain = [('company_id', '=', self.company_id.id), ('type', '=', 'general')]
        return Journal.search(domain + [('code', '=', 'MISC')], limit=1) \
            or Journal.search(domain + [('code', 'not in', ('KSB', 'GAJI'))], limit=1)

    def action_confirm(self):
        self.ensure_one()
        activity = self.activity_id
        currency = self.currency_id
        if currency.compare_amounts(self.amount, 0.0) <= 0:
            raise UserError("Jumlah yang dipindahkan harus lebih dari 0.")
        if currency.compare_amounts(self.amount, activity.fund_remainder) > 0:
            raise UserError("Jumlah melebihi sisa Dana Kegiatan.")
        source = {
            'account_id': self._account(RESTRICTED_NET_ASSETS).id,
            'debit': self.amount,
            'dkm_fund_id': self.kegiatan_fund_id.id,
            'dkm_activity_id': activity.id,
        }
        if self.target == 'fund':
            if not self.fund_id:
                raise UserError("Pilih sumber dana tujuan.")
            where = self.fund_id.name
            dest = {'account_id': self._account(UNRESTRICTED_NET_ASSETS).id,
                    'dkm_fund_id': self.fund_id.id}
        else:
            if not self.target_activity_id:
                raise UserError("Pilih kegiatan tujuan.")
            where = self.target_activity_id.name
            dest = {'account_id': self._account(RESTRICTED_NET_ASSETS).id,
                    'dkm_fund_id': self.kegiatan_fund_id.id,
                    'dkm_activity_id': self.target_activity_id.id}
        label = self.note or f"Pindahan sisa dana {activity.name} ke {where}"
        fname = 'label' if 'label' in self.env['account.move.line']._fields else 'name'
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self._journal().id,
            'date': self.date,
            'ref': label,
            'company_id': self.company_id.id,
            'line_ids': [(0, 0, {**source, fname: label}),
                         (0, 0, {**dest, 'credit': self.amount, fname: label})],
        })
        move.action_post()
        (activity | self.target_activity_id).invalidate_recordset()
        activity.message_post(body=f"{label}: {currency.format(self.amount)} ({move.name}).")
        if self.target == 'activity':
            self.target_activity_id.message_post(
                body=f"Menerima {label.lower()}: {currency.format(self.amount)} ({move.name}).")
        return {'type': 'ir.actions.act_window_close'}
