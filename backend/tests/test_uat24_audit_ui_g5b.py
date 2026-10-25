"""UAT 24 Okt (audit UI tahap 2, grup G5b) — notifikasi & dokumen cetak berbahasa Indonesia.

* G5-10/G5-57 — eskalasi: satu kartu per dokumen sumber (bukan per salinan per orang), "oleh <label peran>"
  (bukan "oleh all"); teks giliran "tahap: dikirim" (bukan "tahap: shipped").
* G5-11 — PDF: tanggal "25 Okt 2026" (WIB), angka id-ID, baris DPP nilai lain + PPN (format akhir K-03, 26 Okt).
* G5-12 — Surat Jalan Transfer Antar-PT: PT dari entitas sumber/tujuan, gudang di baris sendiri, pembuat = pengaju.
* G5-13 — SPK Makloon: jenis order berlabel, kolom proses dari `process_type`, angka id-ID.

Semua uji MURNI (tanpa HTTP, tanpa menulis DB):
  cd /app/backend && python -m pytest tests/test_uat24_audit_ui_g5b.py -p no:randomly -n 0 -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402 — loop tempat klien Motor terikat


def _n(i, *, ref, user="", role="", sev="warning", depth=0, typ="special_order_approval"):
    return {"id": f"ntf_{i}", "type": typ, "ref": ref, "recipient_user": user, "recipient_role": role,
            "severity": sev, "escalation_depth": depth, "title": "PO custom menunggu persetujuan: SORD-1",
            "body": "Toko A · Rp 1", "created_at": "2026-10-20T00:00:00+00:00"}


def test_escalation_one_card_per_source_document():
    from services.escalation_service import plan_escalations
    users = {"u_mgr": {"id": "u_mgr", "role": "manager", "name": "Dewi"},
             "u_mgr2": {"id": "u_mgr2", "role": "manager", "name": "Rudi"},
             "u_adm": {"id": "u_adm", "role": "admin", "name": "Admin"}}
    cands = [
        _n(1, ref="so_custom_appr:sord_a#u_mgr", user="u_mgr"),
        _n(2, ref="so_custom_appr:sord_a#u_mgr2", user="u_mgr2"),
        _n(3, ref="so_custom_appr:sord_a#u_adm", user="u_adm"),     # sudah di admin → tidak dieskalasi
        _n(4, ref="so_custom_appr:sord_b#u_mgr", user="u_mgr"),     # dokumen lain → kartu sendiri
        _n(5, ref="", role="sales", typ="ar_due"),                    # siaran peran → manajer
        _n(6, ref="x", role="all", sev="info", typ="info"),           # di bawah ambang keparahan
    ]
    plan = plan_escalations(cands, users, min_rank=2, max_level=2)
    keys = {(g["lead"]["ref"].split("#")[0] or g["lead"]["id"], g["next_role"]): g for g in plan["groups"]}
    assert len(plan["groups"]) == 3, plan["groups"]
    a = keys[("so_custom_appr:sord_a", "admin")]
    assert [s["id"] for s in a["siblings"]] == ["ntf_2"], "salinan per orang digabung ke satu eskalasi"
    assert a["who"] == "Dewi (Manajer)" or "Dewi" in a["who"]
    assert ("so_custom_appr:sord_b", "admin") in keys
    assert keys[("ntf_5", "manager")]["who"] != "sales", "peran berlabel, bukan kode"
    assert plan["skipped_top"] == 1


def test_escalation_who_never_raw_all():
    from services.escalation_service import _recipient
    assert _recipient({"recipient_role": "all"}, {})[1] == "semua penerima"
    assert _recipient({"recipient_role": ""}, {})[1] == "semua penerima"
    role, who = _recipient({"recipient_role": "manager"}, {})
    assert role == "manager" and who != "manager"


def test_turn_body_stage_is_labelled():
    from services.turn_notification_service import stage_text
    assert stage_text("shipped") == "dikirim"
    assert stage_text("refund_settled").startswith("selesai")
    assert stage_text("partial") == "diterima sebagian"
    assert "_" not in stage_text("partially_shipped")


def test_pdf_date_and_numbers_indonesian():
    from services import pdf_resolvers as pr
    assert pr.fmt_date("2026-10-25T05:53:59+00:00") == "25 Okt 2026"
    assert pr.fmt_date("2026-10-24T18:30:00+00:00") == "25 Okt 2026", "stempel UTC dibaca WIB"
    assert pr.fmt_date("2026-05-04") == "04 Mei 2026"
    assert pr.fmt_num(5337.91) == "5.337,91"
    assert pr.fmt_num(12.0) == "12"
    assert pr.fmt_num(0.75) == "0,75"
    assert pr.fmt_num(353.79) == "353,79"
    assert "WIB" in pr.fmt_now()


def test_pdf_sales_order_shows_dpp_nilai_lain():
    from services import pdf_resolvers as pr
    so = {"number": "KSC/SO-1", "created_at": "2026-10-25T05:53:59+00:00", "status": "confirmed",
          "items": [{"sku": "A", "product_name": "Kain", "quantity": 353.79, "unit": "yard", "price": 1000,
                     "line_total": 353790}],
          "net_subtotal": 202318.4, "dpp": 185458.53, "dpp_nilai_lain": True, "ppn_rate": 12.0,
          "ppn_mode": "excluded", "ppn_amount": 22255.02, "grand_total": 224573.42}
    out = run(pr.resolve_sales_order(so, None))
    labels = [t["label"] for t in out["totals"]]
    # Keputusan pemilik K-03 (26 Okt): DPP · DPP nilai lain (11/12) · PPN · Total (termasuk PPN).
    assert labels == ["DPP (harga sebelum PPN)", "DPP nilai lain (11/12)", "PPN 12% × DPP nilai lain",
                      "Total (termasuk PPN)"], labels
    assert "12.0" not in " ".join(labels)
    assert out["items"][0]["qty"] == "353,79 yard"
    assert out["date"] == "25 Okt 2026"


class _Coll:
    def __init__(self, rows):
        self.rows = rows

    async def find_one(self, q, proj=None):
        return next((r for r in self.rows if r.get("id") == q.get("id")), None)


class _Db:
    def __init__(self, **colls):
        self._c = {k: _Coll(v) for k, v in colls.items()}

    def __getattr__(self, name):
        return self._c.get(name) or _Coll([])


def test_pdf_interco_transfer_names_pt_not_warehouse():
    from services import pdf_resolvers as pr
    db = _Db(business_entities=[{"id": "ent_ksc", "legal_name": "Sukacita Textile"},
                                {"id": "ent_kanda", "legal_name": "Kanda Fabric"}],
             warehouses=[{"id": "wh_a", "name": "Jakarta · Gudang Sukacita"}, {"id": "wh_b", "name": "Gudang Kanda"}])
    tr = {"code": "KSC/TRF-1", "transfer_kind": "inter_entity", "source_entity_id": "ent_ksc",
          "dest_entity_id": "ent_kanda", "source_warehouse_id": "wh_a", "dest_warehouse_id": "wh_b",
          "requested_by": "Budi Santoso", "created_at": "2026-10-23T17:55:53+00:00", "items": []}
    meta = {m["label"]: m["value"] for m in run(pr.resolve_transfer(tr, db))["meta"]}
    assert meta["PT Asal"] == "Sukacita Textile" and meta["PT Tujuan"] == "Kanda Fabric"
    assert meta["Gudang Asal"] == "Jakarta · Gudang Sukacita" and meta["Gudang Tujuan"] == "Gudang Kanda"
    assert meta["Dibuat oleh"] == "Budi Santoso"


def test_pdf_makloon_spk_has_no_raw_codes():
    from services import pdf_resolvers as pr
    mko = {"mko_number": "MKO-1", "mode": "process_only", "material_name": "PFP", "material_qty": 5337.91,
           "material_unit": "yard", "created_by": "Budi", "created_at": "2026-10-24T03:00:00+00:00",
           "steps": [{"seq": 1, "process_name": None, "process_type": "printing", "makloon_name": "CV Printing",
                      "input_qty": 5337.91, "input_unit": "yard", "tariff": 1000}]}
    out = run(pr.resolve_makloon_spk(mko, None))
    meta = {m["label"]: m["value"] for m in out["meta"]}
    assert "process_only" not in str(out["meta"]) and meta["Jenis order"].startswith("Proses saja")
    assert "5.337,91" in meta["Material"]
    assert out["items"][0]["proc"] == "Printing"
    assert out["items"][0]["qty"] == "5.337,91 yard"


def test_export_status_columns_are_labelled():
    """G5-14 — pratinjau & berkas ekspor: status/jenis berlabel; filter menerima kode ATAU label."""
    from services import export_engine as eng
    from services.export_registry import DATASET_BY_ID
    so = {c["key"]: c for c in DATASET_BY_ID["sales_orders"]["columns"]}
    assert so["status"]["enum"] == "status" and so["order_type"]["enum"] == "order_type"
    assert so["payment_status"]["enum"] == "payment_status"
    assert eng._norm(so["status"], "waiting_stock") == "Menunggu stok"
    assert eng._norm(so["status"], "shipped") == "Dikirim"
    assert eng._norm(so["order_type"], "sample") == "Sampel"
    assert eng._norm(so["stage"], "Reserved") == "Dipesan" and "lama" in so["stage"]["label"]
    assert eng._norm(so["payment_status"], "partial") == "Dibayar sebagian"
    cols = {"status": {**so["status"], "source": "base"}}
    f = eng.compile_filter({"field": "status", "cmp": "eq", "value": "Dikirim"}, cols)
    assert set(f["status"]["$in"]) >= {"shipped", "dispatched"}
    assert eng.compile_filter({"field": "status", "cmp": "eq", "value": "done"}, cols) == {"status": "done"}


def test_export_dataset_permissions_exist_in_matrix():
    """G5-52 — izin dataset yang tidak ada di matriks membuat dataset 'tidak tersedia' bagi SEMUA peran (admin juga)."""
    from permissions_config import DEFAULT_PERMISSIONS
    from services.export_registry import DATASETS
    held = {}
    for perms in DEFAULT_PERMISSIONS.values():
        for mod, acts in perms.items():
            held.setdefault(mod, set()).update(acts)
    bad = [(d["id"], d["perm"]) for d in DATASETS if d.get("perm")
           and not ({d["perm"][1], "*"} & held.get(d["perm"][0], set()))]
    assert not bad, bad
