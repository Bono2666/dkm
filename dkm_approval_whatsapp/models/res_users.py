# -*- coding: utf-8 -*-
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .fonnte import normalize_wa_number

PIN_MAX_FAILURES = 5
PIN_LOCK_MINUTES = 15
WEAK_PINS = {'123456', '654321', '012345', '543210', '123123', '112233'}


class ResUsers(models.Model):
    _inherit = 'res.users'

    dkm_whatsapp = fields.Char(
        string="Nomor WhatsApp",
        user_writeable=True,
        help="Nomor WhatsApp untuk menerima link persetujuan, misalnya "
             "0812xxxxxxx. Jika kosong, nomor telepon kontak dipakai.",
    )
    dkm_approval_pin_hash = fields.Char(
        groups='base.group_system', copy=False, readonly=True,
    )
    dkm_pin_failed_count = fields.Integer(
        groups='base.group_system', copy=False, readonly=True,
    )
    dkm_pin_locked_until = fields.Datetime(
        groups='base.group_system', copy=False, readonly=True,
    )
    dkm_has_approval_pin = fields.Boolean(
        string="PIN persetujuan sudah diatur",
        compute='_compute_dkm_has_approval_pin',
    )

    @api.depends_context('uid')
    def _compute_dkm_has_approval_pin(self):
        for user, sudo_user in zip(self, self.sudo()):
            user.dkm_has_approval_pin = bool(sudo_user.dkm_approval_pin_hash)

    # ---- WhatsApp number ----

    def _dkm_whatsapp_target(self):
        self.ensure_one()
        return normalize_wa_number(self.dkm_whatsapp or self.partner_id.phone)

    # ---- PIN ----

    @api.model
    def _dkm_validate_new_pin(self, pin):
        pin = (pin or '').strip()
        if not re.fullmatch(r'\d{6}', pin):
            raise UserError(_("PIN harus tepat 6 digit angka."))
        if len(set(pin)) == 1 or pin in WEAK_PINS:
            raise UserError(_(
                "PIN terlalu mudah ditebak. Hindari angka berulang atau "
                "berurutan."))
        return pin

    def _dkm_set_approval_pin(self, pin):
        self.ensure_one()
        if self.env.user != self and not self.env.user.has_group(
                'base.group_system'):
            raise AccessError(_(
                "Hanya pemilik akun atau Administrator yang dapat mengatur "
                "PIN persetujuan."))
        pin = self._dkm_validate_new_pin(pin)
        pin_hash = self._crypt_context().hash(pin)
        self.sudo().write({
            'dkm_approval_pin_hash': pin_hash,
            'dkm_pin_failed_count': 0,
            'dkm_pin_locked_until': False,
        })

    def _dkm_check_approval_pin(self, pin):
        """Verify the approval PIN with a failure lockout.

        Returns ``(ok, message)`` and never raises: the failure counter must
        be committed by the caller, which a raised exception would roll back.
        """
        self.ensure_one()
        user = self.sudo()
        now = fields.Datetime.now()
        if not user.dkm_approval_pin_hash:
            return False, _(
                "Anda belum mengatur PIN persetujuan. Atur PIN di Odoo: "
                "menu profil > Preferensi > Atur PIN Persetujuan.")
        if user.dkm_pin_locked_until and user.dkm_pin_locked_until > now:
            minutes = int(
                (user.dkm_pin_locked_until - now).total_seconds() // 60) + 1
            return False, _(
                "PIN terkunci karena terlalu banyak percobaan salah. Coba "
                "lagi dalam %s menit.", minutes)
        pin = (pin or '').strip()
        valid = bool(re.fullmatch(r'\d{6}', pin)) and \
            self._crypt_context().verify(pin, user.dkm_approval_pin_hash)
        if valid:
            if user.dkm_pin_failed_count or user.dkm_pin_locked_until:
                user.write({
                    'dkm_pin_failed_count': 0,
                    'dkm_pin_locked_until': False,
                })
            return True, ''
        failures = user.dkm_pin_failed_count + 1
        if failures >= PIN_MAX_FAILURES:
            user.write({
                'dkm_pin_failed_count': 0,
                'dkm_pin_locked_until': now + timedelta(
                    minutes=PIN_LOCK_MINUTES),
            })
            return False, _(
                "PIN salah %(n)s kali. PIN dikunci selama %(m)s menit.",
                n=PIN_MAX_FAILURES, m=PIN_LOCK_MINUTES)
        user.write({'dkm_pin_failed_count': failures})
        return False, _(
            "PIN salah. Sisa percobaan: %s.", PIN_MAX_FAILURES - failures)

    def action_dkm_open_pin_wizard(self):
        self.ensure_one()
        if self.env.user != self and not self.env.user.has_group(
                'base.group_system'):
            raise AccessError(_(
                "Hanya pemilik akun atau Administrator yang dapat mengatur "
                "PIN persetujuan."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Atur PIN Persetujuan"),
            'res_model': 'dkm.approval.pin.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_user_id': self.id},
        }
