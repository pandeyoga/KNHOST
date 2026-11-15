"""KP-T4 (a) — satu tabel kebijakan persetujuan: model, pembaca, uji setara (docs/blueprint/unit/KP-T4.md U1–U3).

Satu database per modul; tes berurutan dan memakai keadaan tes sebelumnya.

Penilai LAMA dibungkus adaptor di berkas ini (salinan logika pintu di HEAD `494a249`, tidak memanggil fungsi yang
dicabut serah-terima (b)); penilai BARU = `approval_policy_service.can_decide` / `required_levels`.

Persiapan U2 (fixture sisip lewat layanan, bukan alur HTTP): tiga peran uji baku (`02` §6) dibuat lewat
`POST /api/access/roles` SEBELUM migrasi; `ent_kanda` diberi nilai lama yang berbeda dari grup (kunci registry lama
ditulis lewat `config_resolver.set_value` dengan status registri sementara `active`, karena di (b) kuncinya menjadi
"tidak dipakai") dan satu aturan PO khusus PT (`approval_rules`, sisip lewat `approval_service`). Lalu migrasi
`--apply` (fungsi skrip) menulis baris bawaan + izin butir 4.

Hitungan tangan nilai uji (rupiah): 0; 9.999.999; 10.000.000; 10.000.000,01; 49.999.999; 50.000.000; 99.999.999;
100.000.000; 499.999.999; 500.000.000. Peran: 13 bawaan + Tanpa Acuan + Manajer Kosong + Sopir(=driver, bawaan) →
15 id peran berbeda (Sopir = `driver`, sudah termasuk bawaan) — dicetak di keluaran.
"""
from __future__ import annotations

import contextlib
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

import role_registry
from approval_kinds import APPROVAL_KINDS, perm_pairs
from services import approval_policy_service as aps
from services import config_resolver as resolver
from services.approval_backlog_service import QUEUES

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
SKRIP = ROOT / "scripts/migrate_kpt4_kebijakan_persetujuan.py"
JT = 1_000_000
NILAI = [0, 9_999_999, 10_000_000, 10_000_000.01, 49_999_999, 50_000_000, 99_999_999, 100_000_000,
         499_999_999, 500_000_000]
PT = ("ent_ksc", "ent_kanda")
KEADAAN: Dict[str, Any] = {}


def _skrip():
    spec = importlib.util.spec_from_file_location("migrate_kpt4_kebijakan_persetujuan", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def _status_aktif(key: str):
    """Fixture: kunci lama boleh ditulis walau di (b) berstatus 'tidak dipakai' (nilai lama sebelum migrasi)."""
    from config_registry import require
    e = require(key)
    lama = e["status"]
    e["status"] = "active"
    try:
        yield
    finally:
        e["status"] = lama


async def _set_lama(key: str, value: Any, ent: str) -> None:
    with _status_aktif(key):
        await resolver.set_value(key, value, scope_type="entity", scope_id=ent, reason="uji KP-T4", actor="uji")


# ── Penilai lama (adaptor) ─────────────────────────────────────────────────────────────────────────────────────────
def _rank(role: str) -> int:
    return role_registry.ROLE_RANK.get(role or "", 0)


def _req_rank(required: str) -> int:   # role_registry.required_rank (HEAD)
    if not required:
        return 0
    return role_registry.ROLE_RANK.get(required, role_registry.ROLES["manager"]["rank"])


def _satisfies(role: str, required: str) -> bool:   # role_registry.role_satisfies (HEAD)
    return _rank(role) >= _req_rank(required)


def _role_in(role: str, roles) -> bool:   # role_registry.role_in (HEAD)
    if role in roles:
        return True
    base = (role_registry.ROLES.get(role) or {}).get("base_role") or ""
    return bool(base) and base in roles


async def _v(key: str, ent: str) -> Any:
    return await resolver.value_of(key, {"entity_id": ent})


async def _rule_role(doc_type: str, amount: float, ent: str) -> str:
    """`config_service.evaluate_approval` (HEAD): pemilih `approval_pool` + rentang [min, max)."""
    from services.config_service import approval_pool
    for r in (await approval_pool(doc_type, ent))["rules"]:
        lo = float(r.get("min_amount") or 0)
        hi = r.get("max_amount")
        hi = float(hi) if hi is not None else float("inf")
        if lo <= float(amount) < hi:
            return r.get("required_role") or ""
    return ""


async def _po_chain(amount: float, ent: str) -> List[tuple]:
    """`config_service.build_approval_chain('purchase_order', …)` (HEAD): [(level, role, label)]."""
    from services.config_service import get_effective_settings
    l1 = await _rule_role("purchase_order", amount, ent)
    if not l1:
        return []
    chain = [(1, l1, "Persetujuan")]
    extra = ((((await get_effective_settings(ent)).get("approval") or {}).get("extra_levels") or {})
             .get("purchase_order") or [])
    for lv in extra:
        role = (lv.get("role") or "").strip()
        if role and float(amount) >= float(lv.get("min_amount", 0) or 0):
            chain.append((len(chain) + 1, role, lv.get("label") or role.title()))
    return chain


async def _matrix_on(ent: str) -> bool:
    return (str(await _v("approval.matrix_enforcement", ent) or "enforce") == "enforce"
            and str(await _v("approval.matrix_scope", ent) or "all_pending") == "all_pending")


async def lama_levels(kind: str, amt: float, ent: str) -> List[int]:
    """Jenjang tempat pintu lama BISA dipanggil untuk nilai itu (kosong = pintu tak terjangkau lewat jenis ini)."""
    if kind == "sales_order.nilai":
        return [1] if await _rule_role("sales_order", amt, ent) else []
    if kind == "purchase_order":
        return [lv for lv, _r, _l in await _po_chain(amt, ent)]
    if kind == "special_order":
        # HEAD: pesanan khusus yang diajukan SELALU `pending_approval` dengan tingkat 1 (matriks `levels[0]` tanpa
        # ambang); tingkat 2 bila nilai ≥ `approval.po_custom_direksi_min`. Ambang Rp10 jt (`APPROVAL_THRESHOLD`)
        # hanya mengisi field `requires_approval` yang tidak dibaca siapa pun (lihat laporan: koreksi U10).
        direksi = float(await _v("approval.po_custom_direksi_min", ent) or 0)
        return [1, 2] if amt >= direksi else [1]
    if kind == "cash_advance":
        return [1, 2, 3]
    return [1]


async def lama_boleh(kind: str, role: str, amt: float, ent: str, level: int, perms: Dict[str, List[str]]) -> bool:
    def punya(res_act: str) -> bool:
        r, a = res_act.split(".", 1)
        return a in (perms.get(r) or []) or "*" in (perms.get(r) or [])

    def izin_jenis() -> bool:
        return any(punya(p) for p in APPROVAL_KINDS[kind]["permissions"])

    if kind == "sales_order.nilai":
        return punya("order.approve") and _satisfies(role, await _rule_role("sales_order", amt, ent))
    if kind in ("sales_order.validasi", "sales_order.kredit", "sales_order.harga_khusus", "sales_order.makloon"):
        return punya("order.approve") and _satisfies(role, "manager")
    if kind == "sales_order.bayar_sampel":
        return punya("order.approve") and _satisfies(role, "finance")
    if kind == "purchase_order":   # pintu lama TANPA izin (PR-05) — hanya peringkat jenjang tersimpan
        return _satisfies(role, dict((lv, r) for lv, r, _l in await _po_chain(amt, ent))[level])
    if kind == "purchase_order.deviasi_harga":
        return _satisfies(role, "manager")
    if kind == "purchase_requisition":
        matrix_ok = (role == "admin" or role in ("manager", "admin")) if await _matrix_on(ent) else True
        return punya("purchase_requisition.approve") and matrix_ok and \
            _satisfies(role, await _rule_role("purchase_requisition", amt, ent))
    if kind == "special_order":
        on = await _matrix_on(ent)
        lv_roles = (["manager", "admin"] if level == 1 else ["admin"]) if on else None
        return punya("order.approve") and role in ("manager", "admin") and \
            (lv_roles is None or role == "admin" or role in lv_roles)
    if kind in ("rnd_spec", "rnd_sample", "rnd_spec.rilis"):
        key = "rnd.sample_decision_roles" if kind == "rnd_sample" else "rnd.spec_approval_roles"
        listed = await _v(key, ent) or []
        list_ok = (not listed) or role in listed
        if kind == "rnd_spec.rilis":
            return punya("rnd.decide") and list_ok
        on = await _matrix_on(ent)
        mx = ["manager", "admin"] if kind == "rnd_spec" else ["manager", "md", "admin"]
        matrix_ok = (role == "admin" or role in mx) if on else True
        return izin_jenis() and matrix_ok and list_ok
    if kind == "amendment":
        above = float(await _v("amendment.admin_approval_above", ent) or 0)
        need = "admin" if amt >= above > 0 else str(await _v("amendment.approver_role", ent) or "manager")
        return punya("finance_amendment.approve") and (role == "admin" or _role_in(role, (need,)))
    if kind == "interco":
        th = float(await _v("antar_entitas.approval_threshold_rupiah", ent) or 0)
        hi = str(await _v("antar_entitas.high_value_approval_role", ent) or "admin")
        lo = str(await _v("antar_entitas.approval_role", ent) or "manager")
        if amt >= th:
            ok = _satisfies(role, hi)
        else:
            ok = _satisfies(role, lo) or role in ("sales_admin",)
        return punya("interco.approve") and ok
    if kind == "interco_loan":   # interco_loan_service._approval_gate (HEAD): peta peringkat pribadi
        th = float(await _v("antar_entitas.approval_threshold_rupiah", ent) or 0)
        hi = str(await _v("antar_entitas.high_value_approval_role", ent) or "admin")
        lo = str(await _v("antar_entitas.approval_role", ent) or "manager")
        rank = {"warehouse": 0, "sales": 0, "manager": 1, "admin": 2}
        need = hi if (th and amt >= th) else lo
        return punya("interco.approve") and rank.get(role, 0) >= rank.get(need, 1)
    if kind == "contra_bon_approve":
        th = float(await _v("contra_bon.approval_threshold_rupiah", ent) or 0)
        need = str(await _v("contra_bon.high_value_approval_role", ent) or "admin").lower() if amt >= th > 0 \
            else str(await _v("contra_bon.approval_role", ent) or "manager").lower()
        return punya("contra_bon.approve") and _rank(role) >= role_registry.ROLE_RANK.get(need, 0)
    if kind in ("vendor_bill", "landed_cost"):   # pintu lama TANPA izin (PR-05)
        return _satisfies(role, "manager")
    if kind == "vendor_bill.kampanye":           # pintu lama TANPA izin; daftar + peran acuan
        return _role_in(role, ("finance", "manager", "admin"))
    if kind == "cash_advance":
        stage_roles = {1: ("manager", "admin"), 2: ("admin",), 3: ("admin",)}[level]
        return punya("cash_advance.approve") and (role == "admin" or _role_in(role, stage_roles))
    if kind == "makloon_claim":
        from services import contract_service as cs
        roles = [r.lower() for r in (await cs.get_settings()).get("claim_approval_roles", ["manager", "admin"])]
        return punya("makloon_order.claim_approve") and role.lower() in roles
    if kind == "payment_variance.hapus_sisa":
        need = str(await _v("payment.variance_writeoff_approver_role", ent) or "manager").lower()
        return punya("payment_variance.decide") and _role_in(role.lower(), (need, "admin"))
    # Mekanisme G (izin saja; lewat-batas kredit sesudah PR-T2)
    return izin_jenis()


#: Jenis bermekanisme G (izin saja): baris bawaannya selalu "semua pemegang akses" — tidak dihitung dari sumber lama.
JENIS_G = {k for k in APPROVAL_KINDS if k not in (
    "sales_order.nilai", "sales_order.validasi", "sales_order.kredit", "sales_order.harga_khusus",
    "sales_order.bayar_sampel", "sales_order.makloon", "purchase_order", "purchase_order.deviasi_harga",
    "purchase_requisition", "special_order", "rnd_spec", "rnd_spec.rilis", "rnd_sample", "amendment", "interco",
    "contra_bon_approve", "vendor_bill", "vendor_bill.kampanye", "landed_cost", "cash_advance", "makloon_claim",
    "payment_variance.hapus_sisa", "interco_loan")}


async def _bandingkan(perms_of, kinds=None) -> Dict[str, Any]:
    kombinasi = selisih = 0
    contoh: List[str] = []
    jenjang_beda: List[str] = []
    roles = role_registry.role_ids()
    for kind in kinds or APPROVAL_KINDS:
        for ent in PT:
            for amt in NILAI:
                old_lv = await lama_levels(kind, amt, ent)
                if kind in ("sales_order.nilai", "purchase_order", "purchase_requisition", "special_order",
                            "cash_advance"):
                    new_lv = [x["level"] for x in await aps.required_levels(kind, ent, amt)]
                    want = old_lv if kind != "purchase_requisition" else (
                        [1] if await _rule_role("purchase_requisition", amt, ent) else [])
                    if new_lv != want:
                        jenjang_beda.append(f"{kind} {ent} {amt}: lama {want} baru {new_lv}")
                for level in old_lv:
                    for role in roles:
                        actor = {"id": f"uji_{role}", "name": f"Uji {role}", "role": role}
                        lama = await lama_boleh(kind, role, amt, ent, level, perms_of(role))
                        baru = (await aps.can_decide(kind, ent, amt, actor, level))["allowed"]
                        kombinasi += 1
                        if lama != baru:
                            selisih += 1
                            if len(contoh) < 15:
                                contoh.append(f"{kind} · {ent} · {amt} · J{level} · {role}: lama={lama} baru={baru}")
    return {"kombinasi": kombinasi, "selisih": selisih, "contoh": contoh, "jenjang_beda": jenjang_beda}


# ── U1 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT4_U1_baris_bawaan_semua_antrean(db):
    assert await db.approval_policies.count_documents({}) == 0
    rows = await aps.build_default_rows("all")
    antrean = {q[0] for q in QUEUES}
    tercakup = {APPROVAL_KINDS[r["doc_kind"]]["queue_key"] for r in rows}
    print(f"\nU1: {len(rows)} baris bawaan; antrean tercakup {len(antrean & tercakup)} dari {len(antrean)}")
    # 38 antrean saat KP-T4 dirancang + `journal_proposal` (perbaikan susulan KF-T6 `8b5fdea`) = 39; AG-T5 menambah
    # `ai_card_second` (kartu asisten uang keluar menunggu orang kedua) = 40; KM-T3 menambah `incentive_sheet` (lembar
    # insentif menunggu pengesahan) = 41.
    assert len(antrean) == 41
    assert antrean <= tercakup, sorted(antrean - tercakup)
    po = sorted([r for r in rows if r["doc_kind"] == "purchase_order"], key=lambda r: (r["level"], r["min_amount"]))
    j1 = [r for r in po if r["level"] == 1 and r["roles"]]
    j2 = [r for r in po if r["level"] == 2]
    assert [(r["min_amount"], r["max_amount"]) for r in j1] == [(100 * JT, None)]
    assert "manager" in j1[0]["roles"] and "admin" in j1[0]["roles"] and "finance" not in j1[0]["roles"]
    assert [(r["min_amount"], r["label"], r["roles"]) for r in j2] == [(500 * JT, "Direksi", ["admin"])]
    # tiap jenis katalog menunjuk antrean yang ada (INV-APPR-01 aturan G); kosong = keputusan langsung tanpa antrean
    assert {v["queue_key"] for v in APPROVAL_KINDS.values()} - {""} <= antrean
    assert all(v["note"] for v in APPROVAL_KINDS.values() if not v["queue_key"])


# ── U2 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT4_U2_setara_penilai_lama(klien, kepala_admin, db, peran_tanpa_acuan, peran_manajer_kosong):
    semua_izin: Dict[str, List[str]] = {}
    for k in APPROVAL_KINDS:
        for res, act in perm_pairs(k):
            semua_izin.setdefault(res, [])
            if act not in semua_izin[res]:
                semua_izin[res].append(act)
    tanpa = await peran_tanpa_acuan(semua_izin, label="Tanpa Acuan KP-T4")
    kosong = await peran_manajer_kosong()
    KEADAAN.update(tanpa=tanpa, kosong=kosong)
    # PT kanda berbeda dari grup (nilai lama, sebelum migrasi)
    await _set_lama("contra_bon.approval_threshold_rupiah", 10 * JT, "ent_kanda")
    await _set_lama("amendment.approver_role", "admin", "ent_kanda")
    await _set_lama("amendment.admin_approval_above", 50 * JT, "ent_kanda")
    await _set_lama("antar_entitas.approval_threshold_rupiah", 100 * JT, "ent_kanda")
    await _set_lama("approval.po_custom_direksi_min", 100 * JT, "ent_kanda")
    await _set_lama("rnd.sample_decision_roles", ["md", "admin"], "ent_kanda")
    await _set_lama("payment.variance_writeoff_approver_role", "admin", "ent_kanda")
    await _set_lama("contra_bon.approval_role", "admin", "ent_kanda")
    from services import approval_service
    await approval_service.create_approval_rule("purchase_order", 0, 50 * JT, "", 1, entity_id="ent_kanda")
    await approval_service.create_approval_rule("purchase_order", 50 * JT, None, "finance", 2, entity_id="ent_kanda")

    hasil = await _skrip().jalankan(tulis=True, aktor="uji KP-T4")
    KEADAAN["migrasi"] = hasil
    assert hasil["ditulis"]["baris"] > 0
    # butir 4: Manajer Kosong (acuan Manajer, nol izin) dan finance (aturan PO kanda ≥ finance) diberi izin PO
    assert set(hasil["izin"].get(kosong, {}).get("purchase_order", [])) == {"approve", "reject"}
    assert set(hasil["izin"].get("finance", {}).get("purchase_order", [])) == {"approve", "reject"}

    from dependencies import permission_matrix
    matrix = await permission_matrix()
    role_registry_ids = role_registry.role_ids()
    assert {tanpa, kosong, "driver"} <= set(role_registry_ids)

    hasil_tabel = await _bandingkan(lambda r: matrix.get(r, {}))
    print(f"\nU2 (baris tersimpan): {hasil_tabel['kombinasi']} kombinasi, {hasil_tabel['selisih']} selisih; "
          f"peran {len(role_registry_ids)}; jenis {len(APPROVAL_KINDS)}")
    assert hasil_tabel["selisih"] == 0, hasil_tabel["contoh"]
    assert hasil_tabel["jenjang_beda"] == [], hasil_tabel["jenjang_beda"][:10]

    # Sumber `bawaan` (belum ada baris; dihitung langsung dari sumber lama) — keputusan juga sama. Jenis G dilewati:
    # baris bawaannya tetap "semua pemegang akses" dan sudah dibandingkan di atas.
    simpan = await db.approval_policies.find({}, {"_id": 0}).to_list(None)
    await db.approval_policies.delete_many({})
    try:
        hasil_bawaan = await _bandingkan(lambda r: matrix.get(r, {}),
                                         [k for k in APPROVAL_KINDS if k not in JENIS_G])
    finally:
        await db.approval_policies.insert_many([dict(x) for x in simpan])
    print(f"U2 (sumber bawaan): {hasil_bawaan['kombinasi']} kombinasi, {hasil_bawaan['selisih']} selisih")
    assert hasil_bawaan["selisih"] == 0, hasil_bawaan["contoh"]
    assert hasil_bawaan["jenjang_beda"] == []


# ── U3 ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT4_U3_setara_jenjang_po():
    from services.config_service import build_approval_chain
    n = 0
    for ent in PT:
        for amt in NILAI:
            lama = (await build_approval_chain("purchase_order", amt, ent))["approval_chain"]
            baru = await aps.required_levels("purchase_order", ent, amt)
            assert [(x["level"], x["label"]) for x in lama] == [(x["level"], x["label"]) for x in baru], (ent, amt)
            n += 1
    print(f"\nU3: {n} pasangan (10 nilai × 2 PT), jumlah jenjang & label sama")
    assert n == 20


# ── Endpoint baca (langkah 4) ──────────────────────────────────────────────────────────────────────────────────────
async def test_KPT4_baca_katalog_daftar_coba(klien, kepala_admin, akun, sesi):
    r = await klien.get("/api/approval-policies/kinds", headers=kepala_admin)
    assert r.status_code == 200, r.text
    kinds = {k["doc_kind"]: k for k in r.json()["kinds"]}
    assert set(kinds) == set(APPROVAL_KINDS)
    assert kinds["purchase_order"]["has_amount"] is True and kinds["transfer"]["has_amount"] is False
    assert kinds["purchase_order"]["permission_labels"] == ["Pembelian & Pengadaan"]

    r = await klien.get("/api/approval-policies", headers=kepala_admin,
                        params={"entity_id": "ent_kanda", "doc_kind": "cash_advance"})
    assert r.status_code == 200, r.text
    ca = r.json()["kinds"][0]
    assert [(lv["level"], lv["label"]) for lv in ca["levels"]] == [
        (1, "Atasan Langsung"), (2, "Pimpinan"), (3, "Bagian Keuangan")]
    assert ca["source"] == "grup" and ca["version"] >= 1
    assert all(t["passing_labels"] for lv in ca["levels"] for t in lv["tiers"])
    assert "Admin" in ca["levels"][0]["tiers"][0]["passing_labels"]

    r = await klien.get("/api/approval-policies/check", headers=kepala_admin,
                        params={"doc_kind": "cash_advance", "entity_id": "ent_kanda", "amount": 1_500_000})
    assert r.status_code == 200, r.text
    lv = r.json()["levels"]
    assert [x["label"] for x in lv] == ["Atasan Langsung", "Pimpinan", "Bagian Keuangan"]
    assert all(x["who"] for x in lv)

    r = await klien.get("/api/approval-policies/check", headers=kepala_admin,
                        params={"doc_kind": "purchase_order", "entity_id": "ent_ksc", "amount": 600 * JT})
    assert [x["label"] for x in r.json()["levels"]] == ["Persetujuan", "Direksi"]

    sopir = await akun("driver")
    h = await sesi(sopir)
    r = await klien.get("/api/approval-policies", headers=h, params={"entity_id": "ent_ksc"})
    assert r.status_code == 403
    pesan = r.json()["detail"]
    assert "Minta Admin menambahkan akses" in pesan and "settings." not in pesan
    r = await klien.get("/api/approval-policies/kinds", headers=h)
    assert r.status_code == 403

    r = await klien.get("/api/approval-policies", headers=kepala_admin, params={"doc_kind": "tidak_ada"})
    assert r.status_code == 400


async def test_KPT4_skrip_argumen_asing_keluar_2(db):
    jumlah = await db.approval_policies.count_documents({})
    assert _skrip().main(["--hapus"]) == 2
    assert await db.approval_policies.count_documents({}) == jumlah
    # mode lapor tidak menulis apa pun dan jalan ulang tidak menambah baris
    hasil = await _skrip().jalankan(tulis=False)
    assert hasil["mode"] == "lapor" and hasil["baris"] == [] and hasil["izin"] == {}
    assert await db.approval_policies.count_documents({}) == jumlah
