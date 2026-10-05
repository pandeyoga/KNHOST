echo "=== [5/7] seed_realistic $(date)"
cd /app
python seed_realistic.py 2>&1 | tail -15
echo "SEED_EXIT=$?"

echo "=== [6/7] VERIFIKASI FONDASI (gagal berisik, bukan gate merah menyesatkan) $(date)"
python - <<'PY'
import sys
from pymongo import MongoClient

# Koleksi yang HANYA lahir dari `bootstrap.run_bootstrap()` (saat backend START),
# bukan dari `seed_realistic.py`. Kalau salah satu kosong, artinya backend pernah
# start tanpa DB → restart backend sekali lagi sudah cukup.
WAJIB = {
    "expense_categories": "kategori pengeluaran petty cash (POC FASE E-4 memeriksanya)",
    "uoms": "master satuan (FASE U: CM·INCH·KG·MTR·PANEL·PCS·RLL·YRD)",
    "gl_accounts": "bagan akun baku (COA) — semua jurnal bergantung padanya",
}
db = MongoClient("mongodb://localhost:27017")["test_database"]
kosong = {c: why for c, why in WAJIB.items() if db[c].count_documents({}) == 0}
for c, why in sorted(WAJIB.items()):
    n = db[c].count_documents({})
    print(f"  {'OK ' if n else 'KOSONG'}  {c:22s} {n:>4} dok   — {why}")
if kosong:
    print("\nFATAL: koleksi fondasi KOSONG: " + ", ".join(sorted(kosong)))
    print("Sebabnya hampir selalu: backend start SEBELUM mongodb hidup, atau DB")
    print("di-drop sesudah backend berjalan. Obatnya satu perintah:")
    print("    supervisorctl restart backend   # bootstrap jalan ulang (idempotent)")
    sys.exit(1)
print("  fondasi LENGKAP.")
PY
FOUND_EXIT=$?
if [ $FOUND_EXIT -ne 0 ]; then
  echo "=== [6b/7] fondasi kosong → restart backend sekali lagi lalu ukur ulang"
  supervisorctl restart backend 2>&1 | tail -3
  sleep 14
  python - <<'PY'
import sys
from pymongo import MongoClient
db = MongoClient("mongodb://localhost:27017")["test_database"]
sisa = [c for c in ("expense_categories", "uoms", "gl_accounts")
        if db[c].count_documents({}) == 0]
print("  masih kosong:", sisa or "tidak ada — fondasi LENGKAP.")
sys.exit(1 if sisa else 0)
PY
  echo "FOUNDATION_RETRY_EXIT=$?"
fi

echo "=== [7/7] rebuild frontend $(date)"
bash /app/scripts/rebuild_frontend.sh 2>&1 | tail -15
echo "BUILD_EXIT=$?"
echo "=== RESTORE DONE $(date)"
