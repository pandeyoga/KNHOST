#!/usr/bin/env bash
# setup_demo_lengkap.sh — SEKALI JALAN di VPS: data demo LENGKAP di atas master produk ASLI.
#   cd /opt/kainnusantara && git fetch origin main && git reset --hard origin/main && bash deploy/setup_demo_lengkap.sh
#   Opsi: SKIP_UPDATE=1 (tanpa tarik kode/build ulang) · SKIP_BACKUP=1 (tanpa backup dulu — tidak disarankan)
# Langkah: backup → update kode → (impor master asli bila belum) → master & stok demo → transaksi demo → cek akhir.
# Idempoten: dijalankan ulang hanya melengkapi yang belum ada. Batal total = restore backup langkah 1.
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$APP_DIR/deploy/.env"
compose() { docker compose --env-file "$ENV_FILE" -f "$APP_DIR/deploy/docker-compose.yml" "$@"; }
log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mXX  %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || die "deploy/.env belum ada — jalankan dulu: bash deploy/install_vps.sh"

log "1/6 Backup database sebelum mengisi data demo"
if [ "${SKIP_BACKUP:-0}" = 1 ]; then echo "dilewati (SKIP_BACKUP=1)"; else bash "$APP_DIR/deploy/backup.sh"; fi

log "2/6 Tarik kode terbaru + build + restart"
if [ "${SKIP_UPDATE:-0}" = 1 ]; then echo "dilewati (SKIP_UPDATE=1)"; else bash "$APP_DIR/deploy/update.sh"; fi

log "3/6 Master produk ASLI (Excel migrasi) + stok awal"
N_MASTER="$(compose exec -T backend python -c "
import asyncio
from db import db
async def main():
    print(await db.products.count_documents({'import_batch': 'MIGRASI_MASTER_PRODUK_KN'}))
asyncio.run(main())" | tail -1)"
if [ "${N_MASTER:-0}" -gt 0 ] 2>/dev/null; then
  echo "sudah ada ($N_MASTER SKU) — tidak diimpor ulang"
else
  compose exec -T backend python scripts/import_master_produk_kn.py | tail -2
  compose exec -T backend python scripts/import_stok_awal_kn.py | tail -2
fi

log "4/6 Master pendukung, struktur gudang, akun semua peran, produk & stok semua tahap bahan"
compose cp "$APP_DIR/seed_realistic.py" backend:/app/seed_realistic.py
compose exec -T backend python scripts/seed_demo_lengkap_kn.py

log "5/6 Transaksi demo (PR→PO→terima→tagihan→bayar · SO berbagai status · makloon berjalan · kas)"
compose exec -T backend python scripts/seed_demo_transaksi_kn.py

log "5b/6 Harga internal antar-PT (data uji: 70% harga jual standar PT penjual, semua pasangan dua arah)"
compose exec -T backend python scripts/seed_demo_harga_internal_kn.py

log "6/6 Pemeriksaan akhir"
compose exec -T backend python - <<'PY'
import asyncio
from db import db
from services import gl_service
async def main():
    rec = await gl_service.inventory_reconciliation()
    bad = [r for r in rec["rows"] if abs(r["difference"]) > 1]
    c = {k: await db[k].count_documents(q) for k, q in {
        "users": {"status": "active"}, "warehouses": {"active": True}, "products": {}, "inventory_rolls": {},
        "purchase_orders": {}, "sales_orders": {}, "makloon_orders": {}, "cash_transactions": {}}.items()}
    print("Ringkasan:", " · ".join(f"{k}={v}" for k, v in c.items()))
    print("GL Persediaan vs subledger:", "SELARAS" if not bad else f"SELISIH {bad}")
    raise SystemExit(1 if bad else 0)
asyncio.run(main())
PY

DOMAIN="$(grep '^DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
cat <<TXT

$(printf '\033[1;32mSELESAI — data demo lengkap siap.\033[0m') Buka https://${DOMAIN}
Semua akun demo bersandi: demo1234   (admin@kainnusantara.id TETAP memakai ADMIN_PASSWORD di deploy/.env)
  md@ · manager@ · finance@ · salesadmin@ · salesadmin.kanda@ · salesadmin.cst@
  sales@ · sales2@ · sales.kanda@ · sales.cst@ · warehouse@ (Jakarta) · warehouse.soreang@
  warehouse.rancamalang@ · whadmin@ · designer@ · sampleadmin@ · driver@        (domain @kainnusantara.id)
Batal total: bash deploy/backup.sh restore deploy/backups/<berkas backup langkah 1>
TXT
