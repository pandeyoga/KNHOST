"""Keputusan pemilik 26 Okt 2026 (audit UI tahap 2) — wilayah D3 (peran, SDM, R&D, HP). Uji tingkat layanan, TANPA HTTP.

* K-08 — bobot nilai desainer bawaan 30/30/20/20 (= 100%); `compute_grade` = Σ bobot × komponen ÷ Σ bobot.
* K-09 — penggajian baru berawalan `PAY-` (deret per badan usaha); order makloon baru ikut prefiks badan usaha.
* K-11 — papan PO Custom peran sales hanya pelanggan miliknya / dokumen buatannya (`owner_scope`); Admin Sample tanpa
  `order.approve`; MD hanya MEMBACA kelompok Pusat Pengaturan R&D (+ setting berizin R&D).
* K-12 — ringkasan permintaan desain membawa `due_soon` (tenggat ≤ 3 hari, belum lewat).
* K-14 — alasan minimum seragam 5 huruf di skema & service wilayah D3.
* K-16 — labdip produk baru tanpa handfeel ACC: ditolak tanpa alasan, lolos dengan alasan ≥ 5 huruf (tercatat).

Jalankan (DB uji, data bertanda TEST_D3 dihapus lagi):
  cd /app/backend && DB_NAME=kn_test_trial python -m pytest tests/test_uat26_d3_decisions.py -p no:randomly -n 0 -q
"""
import inspect
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config_registry as registry  # noqa: E402
from permissions_config import DEFAULT_PERMISSIONS  # noqa: E402
from services import approval_backlog_service as abl  # noqa: E402
from services import design_request_service as dsr  # noqa: E402
from services import hr_payroll_service as payroll  # noqa: E402
from services import rnd_flow_service as flow  # noqa: E402
from services import rnd_kpi_service as kpi  # noqa: E402
from services import rnd_revalidation_service as reval  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
ENT = f"ent_TEST_D3_{TAG}"
SALES = {"id": f"usr_TEST_D3_{TAG}_s", "email": f"sales.d3.{TAG}@test.local", "role": "sales", "name": "Sales Uji"}
MANAGER = {"id": f"usr_TEST_D3_{TAG}_m", "email": f"mgr.d3.{TAG}@test.local", "role": "manager", "name": "Manajer Uji"}


@pytest.fixture(scope="module", autouse=True)
def seed():
    DB.customers.insert_many([
        {"id": f"cust_TEST_D3_{TAG}_own", "name": "Pelanggan Saya", "entity_id": ENT, "assigned_sales_id": SALES["id"]},
        {"id": f"cust_TEST_D3_{TAG}_team", "name": "Pelanggan Tim", "entity_id": ENT,
         "sales_team": [{"sales_id": SALES["id"], "role": "pic"}]},
        {"id": f"cust_TEST_D3_{TAG}_other", "name": "Pelanggan Rekan", "entity_id": ENT, "assigned_sales_id": "usr_lain"},
    ])
    base = {"entity_id": ENT, "status": "pending_approval", "created_at": "2026-10-20T00:00:00Z", "total_amount": 1000}
    DB.special_orders.insert_many([
        {**base, "id": f"sord_TEST_D3_{TAG}_1", "number": f"T-{TAG}-1", "customer_id": f"cust_TEST_D3_{TAG}_own",
         "created_by": "orang.lain@test.local"},
        {**base, "id": f"sord_TEST_D3_{TAG}_2", "number": f"T-{TAG}-2", "customer_id": f"cust_TEST_D3_{TAG}_team",
         "created_by": "orang.lain@test.local"},
        {**base, "id": f"sord_TEST_D3_{TAG}_3", "number": f"T-{TAG}-3", "customer_id": f"cust_TEST_D3_{TAG}_other",
         "created_by": SALES["email"]},                                       # dokumen buatannya sendiri
        {**base, "id": f"sord_TEST_D3_{TAG}_4", "number": f"T-{TAG}-4", "customer_id": f"cust_TEST_D3_{TAG}_other",
         "created_by": "orang.lain@test.local"},                              # milik rekan → tidak terlihat sales
    ])
    today = datetime.now(timezone.utc).date()
    DB.design_requests.insert_many([
        {"id": f"dsr_TEST_D3_{TAG}_late", "entity_id": ENT, "status": "in_progress",
         "due_date": (today - timedelta(days=1)).isoformat()},
        {"id": f"dsr_TEST_D3_{TAG}_soon", "entity_id": ENT, "status": "assigned",
         "due_date": (today + timedelta(days=2)).isoformat()},
        {"id": f"dsr_TEST_D3_{TAG}_far", "entity_id": ENT, "status": "revision",
         "due_date": (today + timedelta(days=10)).isoformat()},
        {"id": f"dsr_TEST_D3_{TAG}_done", "entity_id": ENT, "status": "approved",
         "due_date": (today + timedelta(days=1)).isoformat()},
    ])
    yield
    DB.customers.delete_many({"entity_id": ENT})
    DB.special_orders.delete_many({"entity_id": ENT})
    DB.design_requests.delete_many({"entity_id": ENT})
    DB.number_sequences.delete_many({"entity_id": ENT})


# ── K-08 ─────────────────────────────────────────────────────────────────────
def test_k08_default_weights_sum_to_100_and_grade_is_normalised():
    keys = ("rnd.kpi_weight_on_time", "rnd.kpi_weight_score", "rnd.kpi_weight_acc", "rnd.kpi_weight_design")
    defaults = [registry.get(k)["default"] for k in keys]
    assert defaults == [30, 30, 20, 20] and sum(defaults) == 100
    w = {"on_time": 30, "score": 30, "acc": 20, "design": 20, "penalty_rework": 0, "penalty_overdue": 0}
    row = {"on_time_pct": 100.0, "avg_score": 50.0, "acc_rate": 0.0, "design_avg_score": 2.0,
           "rework_pct": 0, "late_total": 0, "rounds": 0}
    g = kpi.compute_grade(row, w)
    assert g["grade_base"] == 65.0          # (30×100 + 30×50 + 20×0 + 20×100) ÷ 100 — nilai desain BAGIAN dari 100%
    # Setelan yang jumlahnya bukan 100 tetap disetarakan (tidak pernah > 100).
    g2 = kpi.compute_grade(row, {**w, "on_time": 40, "score": 40})
    assert g2["grade_base"] == round((40 * 100 + 40 * 50 + 0 + 20 * 100) / 120, 1)


# ── K-09 ─────────────────────────────────────────────────────────────────────
def test_k09_payroll_prefix_is_pay_and_numbering_per_entity():
    assert payroll.PAYROLL_PREFIX == "PAY-"
    assert 'next_doc_number("hr_payroll_runs", "number", PAYROLL_PREFIX' in inspect.getsource(payroll.create_run)
    from core_utils import next_doc_number
    no = run(next_doc_number("hr_payroll_runs", "number", payroll.PAYROLL_PREFIX, entity_id=ENT))
    assert no.endswith("/PAY-00001"), no


def test_k09_makloon_order_number_follows_entity_prefix():
    from services import makloon_order_service as mko
    no = run(mko._next_mko_number(ENT))
    assert "/MKO-" in no and no.split("/")[0], no      # KODE/MKO-nnnnn
    src = inspect.getsource(mko.create_makloon_order)
    assert "_next_mko_number(entity_id)" in src


# ── K-11 ─────────────────────────────────────────────────────────────────────
def test_k11_sales_board_only_own_customers_or_own_documents():
    allowed = DEFAULT_PERMISSIONS["sales"]
    res = run(abl.queue_detail("special_order", ENT, limit=50, allowed=allowed, actor=SALES))
    nums = {r["number"] for r in res["rows"]}
    assert nums == {f"T-{TAG}-1", f"T-{TAG}-2", f"T-{TAG}-3"}, nums
    assert res["count"] == 3 and res["owner_scoped"] is True
    assert all(r["action"] is None for r in res["rows"])         # sales tidak memutus PO custom
    mgr = run(abl.queue_detail("special_order", ENT, limit=50, allowed=DEFAULT_PERMISSIONS["manager"], actor=MANAGER))
    assert mgr["count"] == 4 and mgr["owner_scoped"] is False    # peran lain tidak berubah
    # Papan lain tidak disaring kepemilikan.
    assert run(abl.owner_scope("price", SALES)) == {}


def test_k11_sample_admin_cannot_decide_special_orders():
    assert "approve" not in DEFAULT_PERMISSIONS["sample_admin"].get("order", [])
    from routers import special_orders as so_router
    for fn in (so_router.approve_special_order_endpoint, so_router.reject_special_order_endpoint):
        assert 'require_permission(request, "order", "approve")' in inspect.getsource(fn)


def test_k11_md_reads_only_rnd_settings_groups():
    from routers import config as cfg
    md = {"role": "md"}
    lim = cfg._read_limit(md, DEFAULT_PERMISSIONS["md"])
    assert lim and lim["groups"] == ("rnd",)
    assert cfg._visible(registry.get("rnd.kpi_weight_design"), lim)
    assert cfg._visible(registry.get("approval.matrix_sod"), lim)     # dijaga izin R&D → tetap terbaca & bisa diubah
    hidden = [e for e in registry.all_entries() if e["group"] == "pajak"]
    assert hidden and not any(cfg._visible(e, lim) for e in hidden)
    groups = cfg._visible_groups(lim)
    assert groups[0]["id"] == "rnd" and {g["id"] for g in groups} <= {"rnd", "persetujuan"}
    # Semua setting yang BISA diubah MD tetap terlihat (hak ubah tidak berkurang).
    for e in registry.all_entries():
        if cfg._can_edit(e, md, DEFAULT_PERMISSIONS["md"]):
            assert cfg._visible(e, lim), e["key"]
    # Admin/manajer (settings.view) & peran lain tanpa batas → membaca semua kelompok seperti sebelumnya.
    assert cfg._read_limit({"role": "manager"}, DEFAULT_PERMISSIONS["manager"]) is None
    assert cfg._read_limit({"role": "sales"}, DEFAULT_PERMISSIONS["sales"]) is None
    assert cfg._read_limit({"role": "md"}, {**DEFAULT_PERMISSIONS["md"], "settings": ["view"]}) is None


# ── K-12 ─────────────────────────────────────────────────────────────────────
def test_k12_design_summary_due_soon():
    s = run(dsr.summary({"entity_id": ENT}))
    assert s["overdue"] == 1 and s["due_soon"] == 1 and s["due_soon_days"] == 3
    assert s["open"] == 3 and s["revision"] == 1


# ── K-14 ─────────────────────────────────────────────────────────────────────
def test_k14_reason_min_five_in_d3_schemas_and_services():
    from schemas_design_gallery import DesignRejectIn
    from schemas_hr_payroll import PayrollRejectInput
    from schemas_rnd import ReasonBody
    for model in (ReasonBody, PayrollRejectInput, DesignRejectIn):
        with pytest.raises(ValidationError):
            model(reason="abcd")
        assert model(reason="abcde").reason == "abcde"
    assert dsr.REASON_MIN == 5
    with pytest.raises(reval.RevalError, match="minimal 5"):
        run(reval.prepare({"revalidation_supplier_id": "sup_x", "revalidation_reason": "abcd"}, "prd_x", ["labdip"]))


# ── K-16 ─────────────────────────────────────────────────────────────────────
def test_k16_labdip_without_handfeel_needs_reason_and_is_recorded():
    payload = {"title": "Labdip uji"}
    with pytest.raises(flow.FlowError, match="alasannya"):
        run(flow.assert_stage_chain(payload, ["labdip"], None, ""))
    with pytest.raises(flow.FlowError):
        run(flow.assert_stage_chain({**payload, "chain_override_reason": "abcd"}, ["labdip"], None, ""))
    out = run(flow.assert_stage_chain({**payload, "chain_override_reason": "kain sama dengan produk berjalan"},
                                      ["labdip"], None, ""))
    assert out["stage"] == "labdip"
    assert out["chain_override"]["missing"] == "handfeel_acc"
    assert out["chain_override"]["reason"] == "kain sama dengan produk berjalan"
    # Labdip + handfeel dalam satu permintaan tetap sah tanpa alasan (bukan pengecualian).
    assert "chain_override" not in run(flow.assert_stage_chain(payload, ["labdip", "handfeel"], None, ""))
