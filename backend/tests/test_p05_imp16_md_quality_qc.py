"""P05 IMP-16 — MD Quality vs QC (random check, hold release/reject) tests.

Uji permission matrix (meta flags), random check lifecycle, MD Quality on po_receipt SPK.
"""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"

ADMIN = ("admin@kainnusantara.id", "demo12345")
MDQ = ("mdquality@kainnusantara.id", "demo12345")
QC = ("qc@kainnusantara.id", "demo12345")
WH = ("warehouse@kainnusantara.id", "demo12345")

ENT_KSC = "ent_ksc"
WH_JKT = "wh_jakarta"
_DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} => {r.status_code} {r.text}"
    return r.json()["token"]


def _hdr(token: str, entity: str = ENT_KSC) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Entity-Id": entity, "Content-Type": "application/json"}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_tok():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def mdq_tok():
    return _login(*MDQ)


@pytest.fixture(scope="module")
def qc_tok():
    return _login(*QC)


@pytest.fixture(scope="module")
def wh_tok():
    return _login(*WH)


@pytest.fixture(scope="module")
def po_spk():
    """SPK penerimaan PO BARU berstatus draft (dulu: SPK draft sisa seed CST/INS-00001 — sejak F-14 seed menutup SPK
    lewat keputusan, jadi tes membuat SPK-nya sendiri lewat alur PO → terima → karantina)."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import test_f14_spk_one_decision as f14
    u = {k: f14.base.Api(e) for k, e in (("mgr", "manager@kainnusantara.id"), ("wh", "warehouse@kainnusantara.id"))}
    _po, _task, spk = f14._po_in_quarantine(u, rolls=1)
    assert spk["status"] == "draft"
    return {"id": spk["id"], "line": spk["lines"][0]["id"], "ent": spk.get("entity_id") or ENT_KSC}


# ---------- meta/permission tests ----------
class TestMetaPermissions:
    def test_admin_can_everything(self, admin_tok):
        r = requests.get(f"{BASE_URL}/api/inspections/meta", headers=_hdr(admin_tok))
        assert r.status_code == 200
        d = r.json()
        assert d["can_md_quality"] is True
        assert d["can_qc"] is True
        assert d["can_random_check"] is True
        assert d["can_qc_release"] is True
        assert d["can_md_quality_decide"] is True

    def test_mdquality_role_only_md(self, mdq_tok):
        r = requests.get(f"{BASE_URL}/api/inspections/meta", headers=_hdr(mdq_tok))
        assert r.status_code == 200
        d = r.json()
        assert d["can_md_quality"] is True
        assert d["can_md_quality_decide"] is True
        assert d["can_qc"] is False
        assert d["can_random_check"] is False
        assert d["can_qc_release"] is False

    def test_qc_role_can_qc_random_not_md(self, qc_tok):
        r = requests.get(f"{BASE_URL}/api/inspections/meta", headers=_hdr(qc_tok))
        assert r.status_code == 200
        d = r.json()
        assert d["can_qc"] is True
        assert d["can_random_check"] is True
        assert d["can_qc_release"] is True
        assert d["can_md_quality"] is False
        assert d["can_md_quality_decide"] is False

    def test_warehouse_no_random_check(self, wh_tok):
        r = requests.get(f"{BASE_URL}/api/inspections/meta", headers=_hdr(wh_tok))
        assert r.status_code == 200
        d = r.json()
        assert d["can_random_check"] is False
        assert d["can_qc_release"] is False
        # warehouse DOES have qc:inspect
        assert d["can_qc"] is True


# ---------- permission enforcement on routes ----------
class TestRoutePermissions:
    def test_warehouse_cannot_create_random_check(self, wh_tok):
        r = requests.post(
            f"{BASE_URL}/api/inspections/random-check",
            headers=_hdr(wh_tok, ENT_KSC),
            json={"warehouse_id": WH_JKT, "count": 1},
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"

    def test_warehouse_cannot_release_hold(self, wh_tok, po_spk):
        r = requests.post(
            f"{BASE_URL}/api/inspections/{po_spk['id']}/lines/{po_spk['line']}/release-hold",
            headers=_hdr(wh_tok, po_spk["ent"]),
            json={"reason": "coba warehouse buka tahanan"},
        )
        assert r.status_code == 403

    def test_qc_cannot_inspect_md_quality_part(self, qc_tok, po_spk):
        r = requests.post(
            f"{BASE_URL}/api/inspections/{po_spk['id']}/lines/{po_spk['line']}/inspect",
            headers=_hdr(qc_tok, po_spk["ent"]),
            json={"part": "md_quality", "color_result": "beda_shade"},
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


# ---------- random check lifecycle ----------
class TestRandomCheckLifecycle:
    """Create random check, inspect lines (part=qc), finish; one line decision=tolak."""

    @pytest.fixture(scope="class")
    def rc(self, admin_tok):
        r = requests.post(
            f"{BASE_URL}/api/inspections/random-check",
            headers=_hdr(admin_tok, ENT_KSC),
            json={"warehouse_id": WH_JKT, "count": 2},
        )
        assert r.status_code == 200, f"create random check: {r.status_code} {r.text}"
        doc = r.json()
        return doc

    def test_created_random_check_shape(self, rc):
        assert rc["kind"] == "random_check"
        assert rc["status"] == "assigned"
        assert rc.get("assigned_to"), "harus auto-assigned ke pembuat"
        assert len(rc["lines"]) == 2
        assert rc["number"], "nomor SPK harus terbit"

    def test_rolls_blocked_after_creation(self, rc, admin_tok):
        roll_id = rc["lines"][0]["roll_id"]
        r = requests.get(f"{BASE_URL}/api/inventory/rolls/{roll_id}", headers=_hdr(admin_tok, ENT_KSC))
        if r.status_code != 200:
            pytest.skip(f"inventory roll endpoint unavailable ({r.status_code})")
        d = r.json()
        assert d.get("status") == "blocked", f"roll should be blocked, got {d.get('status')}"

    def test_md_quality_rejected_on_random_check(self, rc, admin_tok):
        """part=md_quality pada random check → 400 'Random check hanya berisi pemeriksaan QC'."""
        line_id = rc["lines"][0]["id"]
        r = requests.post(
            f"{BASE_URL}/api/inspections/{rc['id']}/lines/{line_id}/inspect",
            headers=_hdr(admin_tok, ENT_KSC),
            json={"part": "md_quality", "color_result": "sesuai"},
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "random check" in r.text.lower() or "qc" in r.text.lower()

    def test_finish_before_all_lines_fails(self, rc, admin_tok):
        """Finish sebelum semua baris QC → 400."""
        # inspect only ONE line with qc
        line_id = rc["lines"][0]["id"]
        r = requests.post(
            f"{BASE_URL}/api/inspections/{rc['id']}/lines/{line_id}/inspect",
            headers=_hdr(admin_tok, ENT_KSC),
            json={"part": "qc", "defects": [], "decision": "terima"},
        )
        assert r.status_code == 200, f"inspect line1: {r.status_code} {r.text}"
        # try to finish
        r = requests.post(
            f"{BASE_URL}/api/inspections/{rc['id']}/finish",
            headers=_hdr(admin_tok, ENT_KSC),
            json={"decision": "terima", "remark": "coba tutup walau belum semua"},
        )
        assert r.status_code == 400, f"finish early: {r.status_code} {r.text}"

    def test_finish_and_close_random_check(self, rc, admin_tok):
        """Isi line kedua dgn decision=tolak lalu finish → line1 roll jadi available, line2 blocked."""
        line2_id = rc["lines"][1]["id"]
        r = requests.post(
            f"{BASE_URL}/api/inspections/{rc['id']}/lines/{line2_id}/inspect",
            headers=_hdr(admin_tok, ENT_KSC),
            json={
                "part": "qc",
                "defects": [{"point_value": 4, "count": 5, "note": "cacat"}],
                "decision": "tolak",
                "remark": "ada cacat parah pada roll",
            },
        )
        assert r.status_code == 200, f"inspect line2: {r.status_code} {r.text}"

        r = requests.post(
            f"{BASE_URL}/api/inspections/{rc['id']}/finish",
            headers=_hdr(admin_tok, ENT_KSC),
            json={"decision": "terima", "remark": "random check selesai"},
        )
        assert r.status_code == 200, f"finish: {r.status_code} {r.text}"
        doc = r.json()
        assert doc["status"] == "done"
        lines = doc["lines"]
        # line1 lulus
        l1 = next(ln for ln in lines if ln["id"] == rc["lines"][0]["id"])
        assert l1.get("random_check_result") == "lulus"
        # line2 gagal
        l2 = next(ln for ln in lines if ln["id"] == line2_id)
        assert l2.get("random_check_result") == "gagal"
        assert l2.get("hold") is True

        # verify roll statuses
        r1 = requests.get(f"{BASE_URL}/api/inventory/rolls/{rc['lines'][0]['roll_id']}", headers=_hdr(admin_tok, ENT_KSC))
        r2 = requests.get(f"{BASE_URL}/api/inventory/rolls/{rc['lines'][1]['roll_id']}", headers=_hdr(admin_tok, ENT_KSC))
        if r1.status_code == 200 and r2.status_code == 200:
            assert r1.json().get("status") == "available", f"line1 roll should be available: {r1.json().get('status')}"
            assert r2.json().get("status") == "blocked", f"line2 roll should remain blocked: {r2.json().get('status')}"

    def test_reopen_random_check_forbidden(self, rc, admin_tok):
        r = requests.post(
            f"{BASE_URL}/api/inspections/{rc['id']}/reopen",
            headers=_hdr(admin_tok, ENT_KSC),
            json={"reason": "coba buka kembali random check untuk uji"},
        )
        assert r.status_code == 400
        # Random check already finished (status=done) → service rejects with "random check" message.
        # If status still open, we get a generic status error — either way validates it cannot be reopened.


# ---------- MD Quality on po_receipt SPK ----------
class TestMdQualityOnPoReceipt:
    """SPK penerimaan PO — F-13 (keputusan owner Q-06b): MD Quality baru boleh mengisi SESUDAH SPK ditugaskan."""

    def test_md_quality_ditolak_saat_draft_lalu_boleh_sesudah_ditugaskan(self, admin_tok, po_spk):
        """part=md_quality pada draft -> 400 (dulu 200); sesudah ditugaskan -> 200; beda_shade -> hold true."""
        sid, lid, ent = po_spk["id"], po_spk["line"], po_spk["ent"]
        url = f"{BASE_URL}/api/inspections/{sid}/lines/{lid}/inspect"
        body = {"part": "md_quality", "color_result": "beda_shade", "handfeel_result": "sesuai"}
        r = requests.post(url, headers=_hdr(admin_tok, ent), json=body)
        assert r.status_code == 400 and "ditugaskan" in r.text, f"MD inspect draft: {r.status_code} {r.text}"
        qc_user = _DB.users.find_one({"email": QC[0]}, {"_id": 0, "id": 1})
        r = requests.post(f"{BASE_URL}/api/inspections/{sid}/assign", headers=_hdr(admin_tok, ent),
                          json={"assigned_to": qc_user["id"], "bagian": "QC"})
        assert r.status_code == 200, r.text
        r = requests.get(f"{BASE_URL}/api/inspections/{sid}", headers=_hdr(admin_tok, ent))
        assert r.status_code == 200
        before = r.json()
        line_before = next(ln for ln in before["lines"] if ln["id"] == lid)
        grade_before = line_before.get("grade_after")

        # inspect MD Quality: beda_shade (SPK sudah ditugaskan)
        r = requests.post(url, headers=_hdr(admin_tok, ent), json=body)
        assert r.status_code == 200, f"MD inspect: {r.status_code} {r.text}"
        doc = r.json()
        line = next(ln for ln in doc["lines"] if ln["id"] == lid)
        assert line["hold"] is True, "beda_shade pada kebijakan 'tahan' harus menahan"
        # grade should NOT be changed by MD quality
        assert line.get("grade_after") == grade_before, "grade tidak boleh berubah oleh MD Quality"

        # roll must also be marked hold.held
        roll_id = line.get("roll_id")
        if roll_id:
            r = requests.get(f"{BASE_URL}/api/inventory/rolls/{roll_id}", headers=_hdr(admin_tok, po_spk["ent"]))
            if r.status_code == 200:
                roll = r.json()
                assert ((roll.get("inspection") or {}).get("hold") or {}).get("held") is True

    def test_reject_hold_requires_long_reason(self, admin_tok, po_spk):
        """Alasan < 15 huruf -> 400."""
        r = requests.post(
            f"{BASE_URL}/api/inspections/{po_spk['id']}/lines/{po_spk['line']}/reject-hold",
            headers=_hdr(admin_tok, po_spk["ent"]),
            json={"reason": "tolak"},
        )
        assert r.status_code == 400

    def test_reject_hold_success(self, admin_tok, po_spk):
        r = requests.post(
            f"{BASE_URL}/api/inspections/{po_spk['id']}/lines/{po_spk['line']}/reject-hold",
            headers=_hdr(admin_tok, po_spk["ent"]),
            json={"reason": "shade terlalu beda, mitra tidak mau terima barang ini"},
        )
        assert r.status_code == 200, f"reject-hold: {r.status_code} {r.text}"
        doc = r.json()
        line = next(ln for ln in doc["lines"] if ln["id"] == po_spk["line"])
        assert line["decision"] == "tolak"
        mdd = line.get("md_quality_decision") or {}
        assert mdd.get("action") == "reject"

    def test_release_hold_success(self, admin_tok, po_spk):
        r = requests.post(
            f"{BASE_URL}/api/inspections/{po_spk['id']}/lines/{po_spk['line']}/release-hold",
            headers=_hdr(admin_tok, po_spk["ent"]),
            json={"reason": "pelanggan setuju shade sedikit beda untuk batch ini"},
        )
        assert r.status_code == 200, f"release-hold: {r.status_code} {r.text}"
        doc = r.json()
        line = next(ln for ln in doc["lines"] if ln["id"] == po_spk["line"])
        assert line["hold"] is False
        mdd = line.get("md_quality_decision") or {}
        assert mdd.get("action") == "release"
