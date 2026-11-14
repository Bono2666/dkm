#!/bin/bash
# Writes odoo.conf from environment variables, creates the database with the
# DKM modules on first start, then hands over to the official entrypoint.
#
# Required env:  HOST, USER, PASSWORD   (PostgreSQL, read by the official image)
#                ODOO_ADMIN_PASSWD      (master password, never committed)
# First start:   ODOO_INITIAL_ADMIN_PASSWORD (password of the 'admin' login,
#                required only when the database is created)
# Optional env:  ODOO_DB_NAME (dkm), ODOO_WORKERS (0), ODOO_LANG (id_ID),
#                ODOO_INIT_MODULES, ODOO_BASE_URL, PORT (5432)
set -euo pipefail

: "${ODOO_ADMIN_PASSWD:?ODOO_ADMIN_PASSWD must be set}"
: "${HOST:?HOST (PostgreSQL host) must be set}"
: "${USER:?USER (PostgreSQL user) must be set}"
: "${PASSWORD:?PASSWORD (PostgreSQL password) must be set}"
DB_NAME="${ODOO_DB_NAME:-dkm}"
WORKERS="${ODOO_WORKERS:-0}"
LANG_CODE="${ODOO_LANG:-id_ID}"
INIT_MODULES="${ODOO_INIT_MODULES:-l10n_id,base_accounting_kit,base_account_budget,dkm_approval_whatsapp}"
DB_PORT="${PORT:-5432}"

cat > /etc/odoo/odoo.conf <<EOF
[options]
addons_path = /opt/dkm-addons
data_dir = /var/lib/odoo
admin_passwd = ${ODOO_ADMIN_PASSWD}
db_name = ${DB_NAME}
dbfilter = ^${DB_NAME}\$
list_db = False
proxy_mode = True
workers = ${WORKERS}
max_cron_threads = 1
limit_time_cpu = 600
limit_time_real = 1200
limit_memory_soft = 1610612736
limit_memory_hard = 2147483648
EOF

export PGHOST="$HOST" PGPORT="$DB_PORT" PGUSER="$USER" PGPASSWORD="$PASSWORD"

for _ in $(seq 1 30); do
    pg_isready -q -d postgres && break
    echo "Waiting for PostgreSQL at ${HOST}:${DB_PORT}..."
    sleep 2
done

if ! psql -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1; then
    echo "Database ${DB_NAME} not found: creating it with ${INIT_MODULES}"
    odoo -d "$DB_NAME" -i "$INIT_MODULES" --load-language="$LANG_CODE" \
         --stop-after-init --no-http
fi

# Re-checked on every start until it succeeds, so a crash between database
# creation and this step can never leave the default admin/admin login.
BOOTSTRAPPED="$(psql -d "$DB_NAME" -Atc "SELECT 1 FROM ir_config_parameter WHERE key = 'dkm.bootstrap_done'" 2>/dev/null || true)"
if [ "$BOOTSTRAPPED" != "1" ]; then
    : "${ODOO_INITIAL_ADMIN_PASSWORD:?ODOO_INITIAL_ADMIN_PASSWORD must be set for the first start}"
    odoo shell -d "$DB_NAME" --no-http < /usr/local/share/dkm-bootstrap.py
fi

exec /entrypoint.sh "$@"
