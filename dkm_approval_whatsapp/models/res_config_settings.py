# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

from . import fonnte
from .approval_token import (
    DEFAULT_VALIDITY_HOURS, PARAM_ENABLED, PARAM_TOKEN, PARAM_VALIDITY,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dkm_wa_enabled = fields.Boolean(
        string="Approval via WhatsApp", config_parameter=PARAM_ENABLED,
    )
    dkm_wa_fonnte_token = fields.Char(
        string="Token Fonnte", config_parameter=PARAM_TOKEN,
    )
    dkm_wa_link_validity_hours = fields.Integer(
        string="Masa berlaku link (jam)", config_parameter=PARAM_VALIDITY,
        default=DEFAULT_VALIDITY_HOURS,
    )

    def action_dkm_test_whatsapp(self):
        """Send a test message to the current user's WhatsApp number."""
        self.ensure_one()
        self.execute()
        target = self.env.user._dkm_whatsapp_target()
        if not target:
            raise UserError(_(
                "Isi dulu Nomor WhatsApp Anda di Preferensi (menu profil "
                "kanan atas)."))
        token = self.env['dkm.approval.token']._dkm_api_token()
        ok, detail = fonnte.send_message(
            token, target,
            _("Tes dari Odoo %s: koneksi WhatsApp approval berhasil.",
              self.env.company.name))
        if not ok:
            raise UserError(detail)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("WhatsApp"),
                'message': _("Pesan uji terkirim ke %s.", target),
                'type': 'success',
            },
        }
