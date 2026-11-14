# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class DkmApprovalPinWizard(models.TransientModel):
    _name = 'dkm.approval.pin.wizard'
    _description = "Atur PIN persetujuan"

    user_id = fields.Many2one(
        'res.users', required=True, readonly=True,
        default=lambda self: self.env.user,
    )
    new_pin = fields.Char(string="PIN baru (6 digit)", required=True)
    confirm_pin = fields.Char(string="Ulangi PIN", required=True)

    def action_confirm(self):
        self.ensure_one()
        if (self.new_pin or '').strip() != (self.confirm_pin or '').strip():
            raise UserError(_("PIN dan ulangan PIN tidak sama."))
        user = self.user_id.with_env(self.env)
        user._dkm_set_approval_pin(self.new_pin)
        name = user.name
        # Never let the clear PIN reach a committed transient row.
        self.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("PIN persetujuan"),
                'message': _("PIN persetujuan untuk %s sudah disimpan.",
                             name),
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
