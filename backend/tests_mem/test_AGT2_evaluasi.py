"""AG-T2 — kumpulan evaluasi Asisten Keuangan (60 butir) dan pengukur mode `engine`.

    python -m pytest backend/tests_mem/test_AGT2_evaluasi.py -n 0 -q        # dari root repo

U17 resmi = lapis A (data acuan: `python tools/ai_eval/run_eval.py --mode engine --set keuangan`, lulus 60/60). Di sini
pengukur yang sama dijalankan di database tiruan (data seed) untuk membuktikan bentuk set dan cara menilainya: alat
harapan sebagai peran itu, angka `check.paths` = jawaban endpoint yang sama dalam sesi yang sama; `denied` = alat galat
DAN endpoint 403. Tanpa layanan luar. Persiapan (FIXTURE, disisip): satu pesanan kredit belum lunas supaya penanda
`@pelanggan` terisi.
"""
import collections
import datetime
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "tools" / "ai_eval"
EMAIL = {"admin": "admin@kainnusantara.id", "sales": "sales@kainnusantara.id", "finance": "finance@kainnusantara.id",
         "warehouse_admin": "warehouse@kainnusantara.id", "sales_admin": "salesadmin@kainnusantara.id",
         "md": "md@kainnusantara.id", "manager": "manager@kainnusantara.id"}
KATEGORI = {"jurnal_buku_besar": 10, "laporan": 10, "piutang": 8, "hutang": 6, "kas_bank": 6, "periode_posting": 4,
            "antar_pt": 4, "pajak": 4, "anggaran": 2, "hak_akses": 4, "sisipan_perintah": 2}


def _set():
    return json.loads((ROOT / "questions_keuangan_v1.json").read_text(encoding="utf-8"))["questions"]


def _pengukur():
    spec = importlib.util.spec_from_file_location("eval_keuangan", ROOT / "eval_keuangan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_AGT2_U17a_bentuk_set_keuangan():
    qs = _set()
    assert len(qs) == 60 and len({q["id"] for q in qs}) == 60
    assert collections.Counter(q["category"] for q in qs) == KATEGORI
    assert {q["expect"] for q in qs} == {"ok", "denied", "cross_entity_denied", "injection_ignored", "clarify"}
    from services import ai_finance_tools as fin
    for q in qs:
        assert q["mode"] == "keuangan" and q["entity"] and q["role"] in EMAIL, q["id"]
        if q["expect"] == "clarify":
            assert q["expected"] is None, q["id"]
            continue
        assert q["expected"]["tool"] in fin.TOOLS, q["id"]
        if q["expect"] != "injection_ignored":
            assert q["check"]["endpoint"].startswith("/api/"), q["id"]
        if q["expect"] == "ok":
            assert q["check"]["paths"], q["id"]


async def test_AGT2_U17b_pengukur_engine_60_dari_60_di_data_seed(klien, db, akun):
    now = datetime.datetime.now(datetime.timezone.utc)
    # FIXTURE — seed database tiruan hanya memuat admin, sales, manager, gudang; akun peran lain dibuat dengan email data
    # acuan (peran bawaan, satu PT) supaya pemetaan peran → akun sama dengan pengukur lapis A.
    for peran in ("finance", "md", "warehouse_admin", "sales_admin"):
        if not await db.users.find_one({"email": EMAIL[peran]}):
            await akun(peran, entitas=("ent_ksc",), email=EMAIL[peran])
    if not await db.bank_accounts.find_one({"entity_id": "ent_ksc"}):   # FIXTURE — penanda `@rekening`
        await db.bank_accounts.insert_one({"id": "bank_agt2e", "name": "Bank Uji Evaluasi", "entity_id": "ent_ksc",
                                           "type": "bank", "account_type": "bank", "gl_account_code": "1-1100",
                                           "is_active": True, "status": "active", "created_at": now.isoformat()})
    await db.customers.insert_one({"id": "cus_agt2e", "name": "Toko Evaluasi", "entity_id": "ent_ksc", "status": "active",
                                   "payment_profile": {}, "created_at": now.isoformat()})
    await db.sales_orders.insert_one({"id": "so_agt2e", "number": "SO-AGT2E", "customer_id": "cus_agt2e",
                                      "customer_name": "Toko Evaluasi", "entity_id": "ent_ksc", "status": "confirmed",
                                      "payment_status": "unpaid", "grand_total": 750000, "total_amount": 750000,
                                      "payments": [], "payment_term_days": 0, "payment_term_code": "NET30",
                                      "created_at": (now - datetime.timedelta(days=2)).isoformat()})

    async def user_for(role):
        u = await db.users.find_one({"email": EMAIL[role]}, {"_id": 0, "password_hash": 0})
        assert u, role
        return u

    ukur = _pengukur()
    rows = await ukur.run_engine_keuangan(_set(), user_for)
    gagal = [(r["id"], r["category"], r["error"], r["detail"]) for r in rows if not r["ok"]]
    assert not gagal, gagal
    ring = ukur.summary(rows)
    assert ring["n"] == ring["lulus"] == 60 and ring["akses_ditolak_pct"] == 100.0
    # Sesi sementara pengukur dihapus semua.
    assert await db.sessions.count_documents({"purpose": "ai_schedule"}) == 0
