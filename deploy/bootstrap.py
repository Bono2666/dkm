# Run once through `odoo shell` right after the database is created.
import os

admin = env.ref('base.user_admin')
admin.password = os.environ['ODOO_INITIAL_ADMIN_PASSWORD']
lang = os.environ.get('ODOO_LANG', 'id_ID')
if env['res.lang']._lang_get(lang):
    admin.lang = lang
params = env['ir.config_parameter'].sudo()
base_url = os.environ.get('ODOO_BASE_URL')
if base_url:
    params.set_str('web.base.url', base_url)
    params.set_bool('web.base.url.freeze', True)
params.set_bool('dkm.bootstrap_done', True)
env.cr.commit()
print("DKM bootstrap: admin password, language and base URL configured")
