# Deploy Odoo 20 DKM ke Easypanel

Server: `43.173.27.76` (Easypanel di port 3000) · Domain: `finance.alukhuwahbsd.com`

Image dibangun dari `Dockerfile` di root repo ini: `odoo:20.0-20261112` plus
semua modul DKM (`/opt/dkm-addons`). Saat pertama kali jalan, container
membuat database `dkm` dan meng-install
`l10n_id, base_accounting_kit, base_account_budget, dkm_approval_whatsapp,
dkm_masjid`
dengan bahasa Indonesia.

## 0. DNS (Niagahoster)

Record **A** `finance` → `43.173.27.76`. Hapus record lama yang menunjuk ke
`109.106.253.114`.

## 1. Project

Easypanel → **Create Project** → nama `dkm`.

## 2. PostgreSQL

Di project `dkm` → **+ Service** → **Postgres**
- Service name: `db`
- Image: `postgres:17`
- Catat **Password** dan **Internal Host** (biasanya `dkm_db`).

## 3. Odoo

**+ Service** → **App** → service name `odoo`

**Source** → GitHub: `Bono2666/dkm`, branch `main`, path `/`
**Build** → **Dockerfile**, file `Dockerfile`

**Environment**:

```
HOST=dkm_db
PORT=5432
USER=odoo
PASSWORD=<password acak baru untuk role odoo>
PG_SUPERUSER=postgres
PG_SUPERUSER_PASSWORD=<password service db>
ODOO_ADMIN_PASSWD=<master password acak, simpan di password manager>
ODOO_INITIAL_ADMIN_PASSWORD=<password login admin, simpan di password manager>
ODOO_BASE_URL=https://finance.alukhuwahbsd.com
ODOO_DB_NAME=dkm
ODOO_WORKERS=0
```

Odoo menolak berjalan sebagai superuser `postgres`; entrypoint memakai
`PG_SUPERUSER` untuk membuat role `odoo` (CREATEDB, bukan superuser) dan
menjadikannya pemilik database `dkm` (Easypanel sudah membuat database kosong
bernama project).

**Mounts** → **Volume**: name `odoo-data`, mount path `/var/lib/odoo`
(wajib: berisi lampiran/filestore; tanpa ini lampiran hilang saat redeploy).

**Domains** → `finance.alukhuwahbsd.com`, HTTPS aktif, port **8069**.

**Deploy**. Start pertama ±3–6 menit (membuat database). Pantau di
tab **Logs** sampai muncul `HTTP service (werkzeug) running`.

## 4. Setelah online

1. Buka `https://finance.alukhuwahbsd.com`, login `admin` dengan
   `ODOO_INITIAL_ADMIN_PASSWORD`. (`web.base.url` sudah diisi dari
   `ODOO_BASE_URL` dan dikunci; link WhatsApp dibuat dari alamat ini.)
2. Settings → Companies: nama `Al Ukhuwah`, negara Indonesia, mata uang IDR.
3. Settings → Invoicing → **Approval via WhatsApp**: aktifkan, isi token
   Fonnte, klik **Kirim pesan uji ke WA saya**.
4. Setiap pengurus: Preferensi → isi **Nomor WhatsApp** → **Atur PIN
   Persetujuan**.

## Update modul berikutnya

Push ke `main` → Easypanel **Deploy** ulang. Untuk upgrade modul yang
berubah, jalankan sekali dari Console service `odoo`:

```
odoo -d dkm -u <nama_modul> --stop-after-init --no-http
```

lalu restart service. Sebelum upgrade, backup dulu dari service `db`
(Easypanel → db → Backups) atau `pg_dump`.

## Catatan

- `ODOO_WORKERS=0` (mode thread) cukup untuk pengguna sedikit dan semua
  trafik (termasuk websocket) lewat port 8069. Jika nanti dinaikkan ke ≥2,
  tambahkan domain kedua dengan path `/websocket` ke port **8072**.
- Database manager dimatikan (`list_db = False`); master password hanya
  dibutuhkan untuk operasi database dari CLI.
