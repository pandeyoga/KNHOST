"""FIX-7 (butir 6) — skrip perbaikan data aman untuk PRODUKSI.

Uji di sini GAGAL di kode dasar (skrip menolak DB `kainnusantara`, tidak punya `--production`/bukti backup/jejak/undo;
modul `services.data_fix_guard` belum ada) dan LULUS sesudah FIX-7:
  A. pagar: DB produksi tanpa `--production` DITOLAK; `--production` tanpa bukti backup < 24 jam DITOLAK; backup tua,
     terpotong, salah DB, terlalu kecil DITOLAK; nama berkas ber-cap waktu WIB < 24 jam & konfirmasi manual DITERIMA;
     DB uji lama tetap diterima tanpa flag; DB lain ditolak;
  B. dry-run bawaan tidak menulis apa pun (termasuk jejak) dan melaporkan perubahan per dokumen;
  C. `--apply` menulis jejak per dokumen (`audit_logs` source `<skrip>#<putaran>` + `migrations` sumber undo);
     `--undo --apply` memulihkan dokumen PERSIS (field yang tadinya tidak ada dihapus lagi, entri riwayat dicabut, mutasi
     yang disisipkan dihapus); apply ulang idempoten.

Data: salinan data acuan berganti nama seperti produksi (`kainnusantara`, env `FIX7_DB`) + dokumen sintetis `TEST_FIX7A`
yang dibersihkan sesudahnya. Jalankan (kontainer backend, repo = /app):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix7_data_scripts.py
"""
import gzip
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pymongo import MongoClient

# /app; putaran pembanding kode dasar: FIX7_ROOT=/app_base (skrip & modul dibaca dari salinan dasar)
ROOT = Path(os.environ.get("FIX7_ROOT") or Path(__file__).resolve().parents[2])
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
PROD_DB = os.environ.get("FIX7_DB", "kainnusantara")
CLIENT = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
DB = CLIENT[PROD_DB]
T = "TEST_FIX7A"
WIB = timezone(timedelta(hours=7))
GEDUNG = ROOT / "scripts" / "fix_data_2026_11_09_gedung_bersama.py"
TANDAI = ROOT / "scripts" / "fix_data_2026_11_09_tandai_data_uji.py"
FIX3A = ROOT / "scripts" / "fix_data_2026_11_09_fix3a_alur_masuk.py"
FIX3B = ROOT / "scripts" / "fix_data_2026_11_09_fix3b_alur_keluar.py"
MIG2 = BACKEND / "scripts" / "migrate_fix2_inspection_hold_status.py"


def _archive(path: Path, size: int = 200 * 1024) -> Path:
    with gzip.open(path, "wb") as gz:
        gz.write(bytes.fromhex("6de29981") + os.urandom(size))
    return path


@pytest.fixture(scope="module")
def bk():
    d = Path(tempfile.mkdtemp(prefix="fix7bk_"))
    stamp = datetime.now(WIB).strftime("%Y-%m-%d_%H%M")
    _archive(d / f"{PROD_DB}-{stamp}.archive.gz")
    return d


@pytest.fixture(scope="module", autouse=True)
def prod_copy():
    if PROD_DB not in CLIENT.list_database_names() or not DB.warehouses.count_documents({}):
        pytest.fail(f"DB salinan produksi `{PROD_DB}` tidak ada — pulihkan data acuan sebagai {PROD_DB} dulu.")
    _purge()
    yield
    _purge()


def _purge():
    rx = {"$regex": f"_{T}_"}
    for c in ("inventory_rolls", "sales_orders", "wms_tasks", "warehouses", "inventory_balances"):
        DB[c].delete_many({"id": rx})
    DB.inventory_movements.delete_many({"roll_id": rx})
    DB.inventory_balances.delete_many({"warehouse_id": rx})


def run(script: Path, *args: str, db_env: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ, DB_NAME=db_env or PROD_DB)
    return subprocess.run([sys.executable, str(script), *args], cwd=str(BACKEND), env=env, capture_output=True,
                          text=True, timeout=600)


def _run_id(out: str) -> str:
    m = re.search(r"putaran (\d{14}-[0-9a-f]{6})", out)
    assert m, out
    return m.group(1)


def _prod(bk_dir: Path) -> list:
    return ["--db", PROD_DB, "--production", "--backup-dir", str(bk_dir)]


# ── A. pagar ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_production_db_requires_flag_and_backup(bk):
    r = run(GEDUNG, "--db", PROD_DB)
    assert r.returncode == 2 and "--production" in r.stdout, r.stdout + r.stderr
    empty = Path(tempfile.mkdtemp(prefix="fix7empty_"))
    r = run(GEDUNG, "--db", PROD_DB, "--production", "--backup-dir", str(empty))
    assert r.returncode == 2 and "backup" in r.stdout.lower(), r.stdout + r.stderr
    r = run(GEDUNG, "--db", PROD_DB, "--production", "--backup-file", f"{PROD_DB}-2020-01-01_0230.archive.gz")
    assert r.returncode == 2 and "jam" in r.stdout, r.stdout
    r = run(GEDUNG, "--db", "db_lain")
    assert r.returncode == 2, r.stdout
    r = run(GEDUNG, "--db", "kn_test_trial", "--production")
    assert r.returncode == 2, r.stdout
    r = run(MIG2, db_env=PROD_DB)       # migrasi FIX-2 dulu menulis ke DB mana pun yang ditunjuk DB_NAME
    assert r.returncode == 2 and "--production" in r.stdout, r.stdout + r.stderr
    r = run(GEDUNG, *_prod(bk))
    assert r.returncode == 0 and "DRY-RUN" in r.stdout and "file_verified" in r.stdout, r.stdout + r.stderr


def test_backup_evidence_rules(tmp_path):
    from services import data_fix_guard as G
    now = datetime.now(timezone.utc)
    stamp = datetime.now(WIB).strftime("%Y-%m-%d_%H%M")
    ok = _archive(tmp_path / f"{PROD_DB}-{stamp}.archive.gz")
    assert G.verify_backup_file(ok, PROD_DB)["kind"] == "file_verified"
    old = _archive(tmp_path / f"{PROD_DB}-2020-01-01_0000.archive.gz")
    os.utime(old, (now.timestamp() - 30 * 3600,) * 2)
    with pytest.raises(G.Refused):
        G.verify_backup_file(old, PROD_DB)                     # mtime > 24 jam
    cut = tmp_path / f"{PROD_DB}-{stamp}-cut.archive.gz"
    cut.write_bytes(ok.read_bytes()[: len(ok.read_bytes()) // 2])
    with pytest.raises(G.Refused):
        G.verify_backup_file(cut, PROD_DB)                     # gzip terpotong (mongodump gagal di tengah)
    small = _archive(tmp_path / f"{PROD_DB}-{stamp}-kecil.archive.gz", size=10)
    with pytest.raises(G.Refused):
        G.verify_backup_file(small, PROD_DB)                   # < 100 KB
    other = _archive(tmp_path / f"db_lain-{stamp}.archive.gz")
    with pytest.raises(G.Refused):
        G.verify_backup_file(other, PROD_DB)                   # backup DB lain
    plain = tmp_path / f"{PROD_DB}-{stamp}-bukan.archive.gz"
    with gzip.open(plain, "wb") as gz:
        gz.write(os.urandom(200 * 1024))
    with pytest.raises(G.Refused):
        G.verify_backup_file(plain, PROD_DB)                   # bukan arsip mongodump
    assert G.backup_from_name(f"{PROD_DB}-{stamp}.archive.gz", PROD_DB)["kind"] == "name_stamp"
    with pytest.raises(G.Refused):
        G.backup_from_name(f"{PROD_DB}-{(datetime.now(WIB) - timedelta(hours=25)).strftime('%Y-%m-%d_%H%M')}.archive.gz", PROD_DB)
    with pytest.raises(G.Refused):
        G.backup_from_name("backup-terbaru.gz", PROD_DB)
    assert G.backup_evidence(PROD_DB, confirmed="kainnusantara-2026-11-10_0230 dicek Budi")["kind"] == "manual_confirmation"
    with pytest.raises(G.Refused):
        G.backup_evidence(PROD_DB, backup_dir=str(tmp_path / "kosong"), confirmed="ok")   # < 5 huruf


def test_legacy_test_db_still_accepted():
    """Perintah lama di DB uji tetap jalan (dry-run, tanpa flag tambahan)."""
    r = run(TANDAI, "--db", "kn_test_trial", db_env="kn_test_trial")
    assert r.returncode == 0 and "DRY-RUN" in r.stdout, r.stdout + r.stderr


# ── B/C. dry-run, jejak, undo persis ────────────────────────────────────────────────────────────────────────────
def _roll(rid, **kw):
    doc = {"id": f"roll_{T}_{rid}", "roll_no": f"{T}-{rid}", "product_id": f"prod_{T}", "warehouse_id": f"wh_{T}_a",
           "owner_entity_id": "ent_ksc", "length_remaining": 30.0, "unit": "meter", "lot": "", "created_at": "2026-11-01T00:00:00Z",
           "updated_at": "2026-11-01T00:00:00Z"}
    doc.update(kw)
    DB.inventory_rolls.insert_one(doc)
    return DB.inventory_rolls.find_one({"id": doc["id"]}, {"_id": 0})


def _doc(coll, did):
    return DB[coll].find_one({"id": did}, {"_id": 0})


def _counts():
    return (DB.audit_logs.count_documents({}), DB.migrations.count_documents({}), DB.inventory_movements.count_documents({}))


def test_fix3b_dry_run_apply_trail_undo_exact(bk):
    DB.warehouses.insert_one({"id": f"wh_{T}_a", "code": "FX7A", "name": "Uji FIX7A", "active": True, "sharing_mode": "shared"})
    DB.sales_orders.insert_one({"id": f"so_{T}_dead", "number": f"SO-{T}", "status": "cancelled", "entity_id": "ent_ksc"})
    r_dead = _roll("dead", status="reserved", reserved_ref={"type": "sales_order", "id": f"so_{T}_dead", "number": f"SO-{T}"})
    DB.wms_tasks.insert_one({"id": f"task_{T}_esc", "flow_type": "outbound", "status": "cancelled",
                             "escalation": {"status": "pending_review", "reason": "uji"}})
    t_before = _doc("wms_tasks", f"task_{T}_esc")
    before_counts = _counts()
    dry = run(FIX3B, *_prod(bk), "--show", "0")
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert f"roll_{T}_dead" in dry.stdout and "status: reserved → available" in dry.stdout, dry.stdout
    assert f"task_{T}_esc" in dry.stdout
    assert _counts() == before_counts, "dry-run menulis sesuatu"
    assert _doc("inventory_rolls", r_dead["id"]) == r_dead

    ap = run(FIX3B, *_prod(bk), "--apply")
    assert ap.returncode == 0, ap.stdout + ap.stderr
    rid = _run_id(ap.stdout)
    now_roll = _doc("inventory_rolls", r_dead["id"])
    assert now_roll["status"] == "available" and now_roll["reserved_ref"] is None
    mov = DB.inventory_movements.find_one({"roll_id": r_dead["id"], "movement_type": "release_reservation"}, {"_id": 0})
    assert mov is not None
    assert _doc("wms_tasks", f"task_{T}_esc")["escalation"]["status"] == "cancelled"
    trail = list(DB.audit_logs.find({"source": f"fix_data_2026_11_09_fix3b_alur_keluar#{rid}"}, {"_id": 0}))
    assert {(a["entity_type"], a["entity_id"]) for a in trail} >= {("inventory_rolls", r_dead["id"]),
                                                                   ("wms_tasks", f"task_{T}_esc")}
    roll_audit = next(a for a in trail if a["entity_id"] == r_dead["id"])
    assert roll_audit["before"]["status"] == "reserved" and roll_audit["after"]["status"] == "available"
    assert DB.migrations.count_documents({"kind": "data_fix_changes", "run_id": rid}) >= 1

    again = run(FIX3B, *_prod(bk), "--apply")               # idempoten: tidak ada perubahan baru
    assert again.returncode == 0 and "0 perubahan dokumen" in again.stdout, again.stdout

    un = run(FIX3B, *_prod(bk), "--undo", "--run-id", rid, "--apply")
    assert un.returncode == 0, un.stdout + un.stderr
    assert _doc("inventory_rolls", r_dead["id"]) == r_dead, "roll tidak pulih persis"
    assert _doc("wms_tasks", f"task_{T}_esc") == t_before, "eskalasi (field bertitik) tidak pulih persis"
    assert DB.inventory_movements.find_one({"id": mov["id"]}) is None, "mutasi sisipan tidak dihapus"
    mig = DB.migrations.find_one({"id": "fix_data_2026_11_09_fix3b_alur_keluar"}, {"_id": 0, "run_log": 1})
    assert any(r["run_id"] == rid and r.get("undone_at") for r in mig["run_log"])
    assert DB.audit_logs.count_documents({"action": "data_fix_undone",
                                          "reason": {"$regex": f"balik {rid}"}}) >= 2
    again_undo = run(FIX3B, *_prod(bk), "--undo", "--run-id", rid, "--apply")
    assert again_undo.returncode == 2 and "sudah dibalik" in again_undo.stdout, again_undo.stdout


def test_fix3a_transfer_hold_and_escalation_undo_exact(bk):
    r_hold = _roll("hold", status="hold", last_transfer={"outcome": "hold", "code": "TRF-FX7", "date": "2026-11-02T00:00:00Z"})
    DB.wms_tasks.insert_one({"id": f"task_{T}_in", "flow_type": "inbound", "status": "escalated",
                             "escalation": {"status": "pending_review", "pre_status": "completed"},
                             "status_history": [{"status": "escalated", "timestamp": "2026-11-01T00:00:00Z"}]})
    t_before = _doc("wms_tasks", f"task_{T}_in")
    ap = run(FIX3A, *_prod(bk), "--apply")
    assert ap.returncode == 0, ap.stdout + ap.stderr
    rid = _run_id(ap.stdout)
    after_roll = _doc("inventory_rolls", r_hold["id"])
    assert after_roll["status"] == "blocked" and after_roll["hold"]["source"] == "transfer_rule"
    assert len(after_roll["hold_history"]) == 1
    t_after = _doc("wms_tasks", f"task_{T}_in")
    assert t_after["status"] == "completed" and len(t_after["status_history"]) == 2
    un = run(FIX3A, *_prod(bk), "--undo", "--run-id", rid, "--apply")
    assert un.returncode == 0, un.stdout + un.stderr
    assert _doc("inventory_rolls", r_hold["id"]) == r_hold
    assert _doc("wms_tasks", f"task_{T}_in") == t_before


def test_migrate_fix2_inspection_hold_undo_exact(bk):
    r = _roll("insp", status="available", inspection={"hold": {"held": True, "reason": "warna beda dari sample"}})
    dry = run(MIG2, "--production", "--backup-dir", str(bk), db_env=PROD_DB)
    assert dry.returncode == 0 and r["id"] in dry.stdout, dry.stdout + dry.stderr
    assert _doc("inventory_rolls", r["id"]) == r
    ap = run(MIG2, "--production", "--backup-dir", str(bk), "--apply", db_env=PROD_DB)
    assert ap.returncode == 0, ap.stdout + ap.stderr
    rid = _run_id(ap.stdout)
    cur = _doc("inventory_rolls", r["id"])
    assert cur["status"] == "blocked" and cur["hold"]["source"] == "inspection"
    assert DB.audit_logs.count_documents({"source": f"migrate_fix2_inspection_hold_status#{rid}"}) == 1
    un = run(MIG2, "--production", "--backup-dir", str(bk), "--undo", "--run-id", rid, "--apply", db_env=PROD_DB)
    assert un.returncode == 0, un.stdout + un.stderr
    assert _doc("inventory_rolls", r["id"]) == r


def test_undo_skips_document_changed_after_script(bk):
    DB.warehouses.insert_one({"id": f"wh_{T}_ded", "code": "FX7D", "name": "Uji FIX7A khusus", "active": True,
                              "sharing_mode": "dedicated", "entity_ids": ["ent_ksc"], "updated_at": "2026-11-01T00:00:00Z"})
    ap = run(GEDUNG, *_prod(bk), "--apply")
    assert ap.returncode == 0, ap.stdout + ap.stderr
    rid = _run_id(ap.stdout)
    assert _doc("warehouses", f"wh_{T}_ded")["sharing_mode"] == "shared"
    DB.warehouses.update_one({"id": f"wh_{T}_ded"}, {"$set": {"entity_ids": ["ent_kanda"]}})   # diubah orang lain
    un = run(GEDUNG, *_prod(bk), "--undo", "--run-id", rid, "--apply")
    assert un.returncode == 0 and "LEWAT" in un.stdout, un.stdout
    assert _doc("warehouses", f"wh_{T}_ded")["entity_ids"] == ["ent_kanda"]      # tidak ditimpa
    # gedung acuan lain dari putaran yang sama tetap dipulihkan
    assert DB.warehouses.count_documents({"code": {"$in": ["SRG-01", "WH-JKT"]}, "sharing_mode": "dedicated"}) == 2
