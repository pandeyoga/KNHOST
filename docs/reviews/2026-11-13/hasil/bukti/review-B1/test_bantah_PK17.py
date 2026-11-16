"""Uji bantahan reviewer B1 — PK-17 (IA-01, IA-02, IA-03). Lapis B; cp ke backend/tests_mem/ lalu jalankan -n 0 -s."""
# ruff: noqa: F811
import json

import pytest

from test_PK17_nominal_berizin import JT, SEKARANG, pembaca_po, siap  # noqa: F401
from services import doc_refs_service as refs

pytestmark = pytest.mark.anyio

ANGKA_TAGIHAN = ("27500000", "27.500.000")
ANGKA_KONTRABON = ("12000000", "12.000.000", "10000000", "10.000.000", "2000000", "2.000.000")


def _bocor(teks: str, angka) -> list:
    return [a for a in angka if a in teks]


async def test_IA01_jalur_lain_relasi_dokumen_po(klien, siap, pembaca_po):
    """`/documents/relations/purchase_order/{id}` (graf proses) hanya butuh purchase_order.view. Nominal tagihan
    pemasok tidak boleh ikut bagi pembaca tanpa vendor_bill.view."""
    r = await klien.get("/api/documents/relations/purchase_order/po_x", headers=pembaca_po)
    print("OBS relasi", r.status_code, _bocor(r.text, ANGKA_TAGIHAN), r.text[:0])
    assert r.status_code in (200, 403), r.text
    if r.status_code == 200:
        assert not _bocor(r.text, ANGKA_TAGIHAN), "nominal tagihan pemasok terbaca lewat /documents/relations"


async def test_IA01_jalur_lain_teks_penuh_empat_pintu(klien, siap, pembaca_po):
    bocor = {}
    for nama, url, par in (("trace", "/api/documents/trace/purchase_order/po_x", None),
                           ("refs", "/api/documents/refs/purchase_order/po_x", None),
                           ("cari", "/api/documents/trace-search", {"q": "PK17"}),
                           ("cetak", "/api/documents/trace/purchase_order/po_x/print", None),
                           ("jangkar_tagihan", "/api/documents/trace/vendor_bill/vb_x", None),
                           ("refs_tagihan", "/api/documents/refs/vendor_bill/vb_x", None)):
        r = await klien.get(url, headers=pembaca_po, params=par)
        b = _bocor(r.text, ANGKA_TAGIHAN + ANGKA_KONTRABON[:2])
        print("OBS pintu", nama, r.status_code, b)
        if r.status_code == 200 and b:
            bocor[nama] = b
    assert not bocor, f"nominal dokumen tanpa izin terbaca: {bocor}"


async def test_IA01_tanpa_izin_jenis_tanpa_perm_nota_kredit_dan_kontrabon(klien, db, siap, akun, sesi,
                                                                          peran_tanpa_acuan):
    """Jenis dokumen bernilai uang yang TIDAK punya `perm` di DOC_TYPES tidak disaring. Dicek: nota kredit."""
    await db.credit_notes.insert_one({"id": "cn_b1", "number": "CN-UJI-B1", "entity_id": "ent_ksc", "kind": "credit",
                                      "amount": 3_333_333, "total": 3_333_333, "grand_total": 3_333_333,
                                      "status": "issued", "customer_name": "Toko Uji", "created_at": SEKARANG})
    h = await sesi(await akun(await peran_tanpa_acuan({"document": ["view"]}, label="B1 Dok saja")))
    tanpa_perm = sorted(t for t, m in refs.DOC_TYPES.items() if not m.get("perm"))
    print("OBS jenis tanpa perm:", tanpa_perm)
    r = await klien.get("/api/documents/trace-search", params={"q": "UJI"}, headers=h)
    assert r.status_code == 200, r.text
    terlihat = {x["doc_type"]: x.get("amount") for x in r.json() if x.get("amount") is not None}
    print("OBS nominal terlihat oleh peran document.view saja:", terlihat)
    assert "contra_bon" not in terlihat and "vendor_bill" not in terlihat and "purchase_order" not in terlihat
    assert "credit_note" not in terlihat, f"nota kredit bernominal terlihat tanpa izin keuangan: {terlihat}"


async def test_IA02_tanpa_izin_gudang_pintu_tagihan_dan_rekening(klien, db, siap, akun, sesi, peran_tanpa_acuan):
    adm_gudang = await sesi(await akun("warehouse_admin"))
    hasil = {}
    for h_nama, h in (("warehouse", siap["gudang_h"]), ("warehouse_admin", adm_gudang)):
        for url in ("/api/vendor-bills", "/api/vendor-bills/vb_x", "/api/landed-cost", "/api/input-tax-invoices"):
            r = await klien.get(url, headers=h)
            hasil[(h_nama, url)] = r.status_code
            assert r.status_code in (403, 404), (h_nama, url, r.status_code, r.text[:200])
    print("OBS gudang:", hasil)
    await db.bank_accounts.insert_one({"id": "ba_b1", "name": "Rek B1", "account_type": "bank",
                                       "entity_id": "ent_ksc", "opening_balance": 0, "is_active": True})
    catat = await sesi(await akun(await peran_tanpa_acuan({"cash": ["view", "create"]}, label="B1 Catat Kas")))
    r = await klien.patch("/api/bank-accounts/ba_b1", headers=catat, json={"name": "Diubah", "is_active": False})
    assert r.status_code == 403, r.text
    r = await klien.post("/api/bank-account-changes", headers=catat,
                         json={"account_id": "ba_b1", "changes": {"name": "Diubah"}})
    print("OBS bank-account-changes oleh cash.create:", r.status_code, r.text[:160])
    assert r.status_code in (403, 404, 405, 422), r.text
    assert (await db.bank_accounts.find_one({"id": "ba_b1"}))["name"] == "Rek B1"


async def test_IA02_data_lama_matriks_tersimpan_gudang(db, siap):
    """Matriks tersimpan sebelum PK-17 (gudang memegang vendor_bill.view): apakah proses awal mencabutnya?
    Uji ini MENCATAT; pencabutan di data tersimpan adalah tugas skrip `apply_pk17_role_cleanup.py --apply` (H3)."""
    import bootstrap
    await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix.warehouse_admin.vendor_bill": ["view"]}})
    await bootstrap.run_bootstrap()
    m = (await db.permission_settings.find_one({"id": "default"}))["matrix"]
    masih = "vendor_bill" in m["warehouse_admin"]
    print("OBS matriks lama warehouse_admin.vendor_bill bertahan sesudah start:", masih)
    await db.permission_settings.update_one({"id": "default"}, {"$unset": {"matrix.warehouse_admin.vendor_bill": ""}})
    assert masih is True   # perilaku yang didokumentasikan: start TIDAK mencabut; butuh skrip --apply


async def test_IA03_tanpa_izin_gudang_papan_finance_bernominal(klien, siap):
    """Gudang memegang contra_bon.view (tanpa nominal di layar Kontrabon, U12). Papan Meja Finance tidak boleh
    menjadi pintu yang menampilkan nominal kontrabon kepada peran yang sama."""
    r = await klien.get("/api/home/finance", headers=siap["gudang_h"])
    b = _bocor(r.text, ANGKA_KONTRABON)
    kunci = [x["key"] for x in r.json().get("waiting_boards", [])] if r.status_code == 200 else []
    print("OBS papan finance gudang", r.status_code, kunci, "bocor:", b)
    if r.status_code == 200:
        baris = [row for bd in r.json()["waiting_boards"] for row in bd.get("rows", [])]
        print("OBS baris papan:", json.dumps(baris)[:400])
    assert r.status_code == 403 or not b, f"papan Meja Finance menampilkan nominal kontrabon ke gudang: {b}"


async def test_IA03_pt_lain_dan_papan_lain(klien, siap, akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"vendor_bill": ["view"], "contra_bon": ["view"]}, label="B1 Hutang Kanda")
    h = await sesi(await akun(rid, entitas=("ent_kanda",)), entitas="ent_kanda")
    r = await klien.get("/api/home/finance", headers=h, params={"entity_id": "ent_ksc"})
    print("OBS pt_lain", r.status_code, _bocor(r.text, ANGKA_TAGIHAN + ANGKA_KONTRABON))
    assert r.status_code in (403, 404) or not _bocor(r.text, ANGKA_TAGIHAN + ANGKA_KONTRABON + ("Pemasok PK17",))
    for url in ("/api/home/sales", "/api/home/warehouse", "/api/home/admin", "/api/home/manager"):
        r = await klien.get(url, headers=siap["sopir_h"])
        b = _bocor(r.text, ANGKA_TAGIHAN + ANGKA_KONTRABON + ("Pemasok PK17",))
        print("OBS sopir", url, r.status_code, b)
        assert not b, (url, b)


async def test_IA03_tanpa_izin_gudang_papan_finance_kontrabon_bertotal(klien, db, siap):
    """Sama dengan uji di atas, tetapi kontrabon membawa `totals` seperti dokumen nyata (hasil `recompute`)."""
    await db.contra_bons.update_one({"id": "cb_x"}, {"$set": {"totals": {
        "bills_total": 12 * JT, "deductions_total": 2 * JT, "net_payable": 10 * JT, "paid": 0, "outstanding": 10 * JT}}})
    r = await klien.get("/api/home/finance", headers=siap["gudang_h"])
    baris = [row for bd in r.json().get("waiting_boards", []) for row in bd.get("rows", [])] if r.status_code == 200 else []
    print("OBS2 papan gudang", r.status_code, [(x["number"], x.get("amount"), x.get("title")) for x in baris])
    cb = (await klien.get("/api/contra-bons/cb_x", headers=siap["gudang_h"])).json()
    print("OBS2 layar kontrabon gudang net_payable:", (cb.get("totals") or {}).get("net_payable"), cb.get("amount_hidden"))
    assert r.status_code == 403 or all(not x.get("amount") for x in baris), (
        "gudang (contra_bon.view, nominal disembunyikan di layar Kontrabon) melihat nominal kontrabon di papan Meja Finance")
