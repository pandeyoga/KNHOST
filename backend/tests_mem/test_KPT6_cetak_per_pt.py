"""KP-T6 — dokumen dan cetak per PT (docs/blueprint/unit/KP-T6.md), uji U1–U13 di lingkungan B.

Seed lingkungan B: `ent_ksc` (Sukacita Textile, Bandung) dan `ent_kanda` (Kanda Fabric, Jakarta), akun Admin. Tes satu
modul berbagi basis data dan berjalan menurut urutan berkas (urutan disengaja: U1 → U2 → U3 → U4 memakai satu baris kop
`ent_kanda`; U6 → U7 → U8 → U9 memakai satu lapisan PT faktur `ent_kanda`).

Fixture yang disisipkan langsung ke basis data: pesanan penjualan per PT (dirender sebagai `invoice` HTML), baris
`document_branding` berteks lama (U2, U4 — data lama yang hanya bisa lahir dari layar lama), rekening bank (U9), izin
`pdf_template` untuk peran `sales` (U11), template cetak dasar `ent_kanda` (U12), baris `pdf_templates` tanpa `entity_id`
(U13). Selebihnya alur lewat API.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any, Dict

import pytest

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
SKRIP_MIGRASI = ROOT / "scripts/migrate_kpt6_template_pt.py"

KSC, KANDA = "ent_ksc", "ent_kanda"
SO_KSC, SO_KANDA = "so_kpt6_ksc", "so_kpt6_kanda"
PESAN_TEKS_KOP = "Nama, alamat, NPWP, dan kontak diubah di Profil PT."
PESAN_NPWP = "NPWP harus 15 atau 16 digit angka. Periksa kembali nomor yang diketik."   # KP-T1
PESAN_SELESAI = "Identitas kop PT ini sudah diselesaikan."
AWALAN_KUNCI_GRUP = "Bagian ini hanya bisa diatur untuk semua PT:"


def _detail(r) -> str:
    try:
        d = r.json().get("detail")
    except Exception:  # noqa: BLE001 — jawaban bukan JSON (mis. 404 rute tidak ada)
        return r.text
    return d if isinstance(d, str) else str(d)


async def _pesanan(db, eid: str, sid: str, nomor: str) -> None:
    """Fixture: satu pesanan penjualan per PT (sumber dokumen `invoice`)."""
    from core_utils import now_iso
    await db.sales_orders.update_one({"id": sid}, {"$set": {
        "id": sid, "entity_id": eid, "number": nomor, "customer_id": "cus_kpt6", "customer_name": "Toko Uji KPT6",
        "status": "confirmed", "payment_status": "unpaid", "payment_term_name": "Tunai",
        "items": [{"sku": "KPT6-1", "product_name": "Kain Uji", "quantity": 10, "unit": "m", "price": 1000,
                   "subtotal": 10000, "line_total": 10000}],
        "total_amount": 10000, "grand_total": 10000, "created_at": now_iso()}}, upsert=True)


async def _faktur(klien, h, sid: str) -> str:
    r = await klien.get(f"/api/pdf/render/invoice/{sid}", headers=h, params={"format": "html"})
    assert r.status_code == 200, r.text[:400]
    return r.text


def _tempat(html: str) -> str:
    """Isi blok "tempat, tanggal" sebelum tanda tangan (kosong bila tidak dicetak)."""
    m = re.search(r'class="place-date">([^<]*)<', html)
    return m.group(1) if m else ""


async def _pt(db, eid: str) -> Dict[str, Any]:
    return await db.business_entities.find_one({"id": eid}, {"_id": 0}) or {}


@pytest.fixture(scope="module")
async def siap(db):
    await _pesanan(db, KSC, SO_KSC, "KSC/SO-KPT6-1")
    await _pesanan(db, KANDA, SO_KANDA, "KANDA/SO-KPT6-1")
    return True


# ── U1 — tanpa teks kop lama: identitas kop = Profil PT ────────────────────────────────────────────────────────────
async def test_KPT6_U1_identitas_dari_profil_pt(klien, kepala_admin, db, siap):
    assert await db.document_branding.count_documents({"entity_id": KANDA}) == 0
    r = await klien.patch(f"/api/entities/{KANDA}", headers=kepala_admin,
                          json={"data": {"address": "Jl. Baru 9", "print_name": "KANDA TEKSTIL"}})
    assert r.status_code == 200, r.text
    r = await klien.get(f"/api/pdf/branding/{KANDA}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["company_name"] == "KANDA TEKSTIL"
    assert "Jl. Baru 9" in b["address"]
    assert b["identity_conflicts"] == []


# ── U2 — teks kop lama tetap tercetak saat dipasang; selisihnya dilaporkan ─────────────────────────────────────────
async def test_KPT6_U2_teks_lama_tetap_dan_selisih_dilaporkan(klien, kepala_admin, db, siap):
    await db.document_branding.insert_one({"entity_id": KANDA, "address": "Alamat Lama 1"})   # fixture: data lama
    r = await klien.get(f"/api/pdf/branding/{KANDA}", headers=kepala_admin)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["address"] == "Alamat Lama 1"
    beda = {c["field"]: c for c in b["identity_conflicts"]}
    assert "address" in beda, b["identity_conflicts"]
    assert beda["address"]["print_value"] == "Alamat Lama 1"
    assert "Jl. Baru 9" in beda["address"]["profile_value"]
    assert beda["address"]["label"] and "address" not in beda["address"]["label"]
    html = await _faktur(klien, kepala_admin, SO_KANDA)
    assert "Alamat Lama 1" in html


# ── U3 — "Pakai data Profil PT": kop berpindah ke Profil PT; tidak bisa diulang ───────────────────────────────────
async def test_KPT6_U3_pakai_profil(klien, kepala_admin, db, siap):
    r = await klien.post(f"/api/pdf/branding/{KANDA}/identity", headers=kepala_admin,
                         json={"action": "pakai_profil", "reason": "  "})
    assert r.status_code == 400 and _detail(r) == "Alasan wajib diisi.", r.text
    r = await klien.post(f"/api/pdf/branding/{KANDA}/identity", headers=kepala_admin,
                         json={"action": "pakai_profil", "reason": "Alamat pindah"})
    assert r.status_code == 200, r.text
    assert r.json()["identity_conflicts"] == [] and "Jl. Baru 9" in r.json()["address"]
    html = await _faktur(klien, kepala_admin, SO_KANDA)
    assert "Jl. Baru 9" in html and "KANDA TEKSTIL" in html
    assert "Alamat Lama 1" not in html
    r = await klien.post(f"/api/pdf/branding/{KANDA}/identity", headers=kepala_admin,
                         json={"action": "pakai_profil", "reason": "Alamat pindah"})
    assert r.status_code == 409 and _detail(r) == PESAN_SELESAI, r.text
    jejak = await db.audit_logs.find_one({"action": "branding_identity_resolved"}, {"_id": 0})
    assert jejak and jejak.get("after", {}).get("reason") == "Alamat pindah", jejak


# ── U4 — "Salin teks kop ke Profil PT" memakai validasi KP-T1; gagal = tidak ada yang berubah ─────────────────────
async def test_KPT6_U4_salin_ke_profil_npwp_tidak_sah(klien, kepala_admin, db, siap):
    # fixture: kembali ke keadaan U2 (belum diselesaikan) dengan NPWP lama "12"
    await db.document_branding.update_one({"entity_id": KANDA}, {
        "$unset": {"identity_resolved_at": "", "identity_resolved_by": ""},
        "$set": {"address": "Alamat Lama 1", "npwp": "12"}})
    sebelum = await _pt(db, KANDA)
    r = await klien.post(f"/api/pdf/branding/{KANDA}/identity", headers=kepala_admin,
                         json={"action": "salin_ke_profil", "reason": "x"})
    assert r.status_code == 400, r.text
    assert _detail(r) == PESAN_NPWP
    assert await _pt(db, KANDA) == sebelum
    row = await db.document_branding.find_one({"entity_id": KANDA}, {"_id": 0})
    assert not row.get("identity_resolved_at"), row


async def test_KPT6_U4b_salin_ke_profil_berhasil(klien, kepala_admin, db, siap):
    """Pelengkap U4 — teks lama yang sah disalin ke Profil PT lalu ditandai selesai; kop sama dengan Profil PT."""
    await db.document_branding.update_one({"entity_id": KANDA}, {"$set": {
        "npwp": "03.456.789.0-123.000", "phone": "021-555", "address": "Alamat Lama 1, Jakarta"}})
    r = await klien.post(f"/api/pdf/branding/{KANDA}/identity", headers=kepala_admin,
                         json={"action": "salin_ke_profil", "reason": "Kop lama yang benar"})
    assert r.status_code == 200, r.text
    pt = await _pt(db, KANDA)
    # alamat lama "…, Jakarta" berakhiran kota PT → kota tidak ikut disalin ke isian alamat (tidak tercetak dua kali)
    assert (pt["address"], pt["npwp"], pt["phone"], pt["print_name"]) == (
        "Alamat Lama 1", "03.456.789.0-123.000", "021-555", "KANDA TEKSTIL")
    b = r.json()
    assert b["identity_conflicts"] == [] and b["address"] == "Alamat Lama 1, Jakarta" and b["phone"] == "021-555"
    row = await db.document_branding.find_one({"entity_id": KANDA}, {"_id": 0})
    assert row.get("identity_resolved_at") and row.get("identity_resolved_by")


# ── U5 — teks identitas tidak lagi disimpan di kop ─────────────────────────────────────────────────────────────────
async def test_KPT6_U5_teks_kop_ditolak(klien, kepala_admin, db, siap):
    r = await klien.put(f"/api/pdf/branding/{KANDA}", headers=kepala_admin, json={"company_name": "X"})
    assert r.status_code == 400, r.text
    assert _detail(r) == PESAN_TEKS_KOP
    row = await db.document_branding.find_one({"entity_id": KANDA}, {"_id": 0})
    assert row.get("company_name") != "X"
    # gambar dan tanda tangan tetap bisa disimpan
    ttd = [{"label": "Hormat Kami", "role": "Finance", "name": "Dewi", "signature_b64": "iVBORw0KGgo="}]
    r = await klien.put(f"/api/pdf/branding/{KANDA}", headers=kepala_admin, json={"signatures": ttd})
    assert r.status_code == 200, r.text
    assert r.json()["signatures"][0]["name"] == "Dewi"


# ── U6 — naskah per PT: PT lain tidak berubah ──────────────────────────────────────────────────────────────────────
async def test_KPT6_U6_naskah_per_pt(klien, kepala_admin, db, siap):
    r = await klien.put("/api/pdf/templates/invoice", headers=kepala_admin, json={"config": {
        "closing_note": "Terima kasih.", "place": "Bandung", "show_place_date": True}})
    assert r.status_code == 200, r.text
    r = await klien.put("/api/pdf/templates/invoice", headers=kepala_admin, params={"entity_id": KANDA},
                        json={"config": {"closing_note": "Pembayaran ke {{rekening_bank}}", "place": "Jakarta"}})
    assert r.status_code == 200, r.text
    kanda = await _faktur(klien, kepala_admin, SO_KANDA)
    ksc = await _faktur(klien, kepala_admin, SO_KSC)
    assert "Jakarta," in kanda and "Pembayaran ke" in kanda
    assert _tempat(kanda).startswith("Jakarta, ")
    assert "Terima kasih." not in kanda
    assert "Bandung," in ksc and "Terima kasih." in ksc
    assert _tempat(ksc).startswith("Bandung, ")
    assert "Pembayaran ke" not in ksc
    # jawaban GET lapisan PT: cakupan, kunci yang ditimpa, nilai grup
    r = await klien.get("/api/pdf/templates/invoice", headers=kepala_admin, params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["scope"] == KANDA and j["pt_override_keys"] == ["closing_note", "place"]
    assert j["config"]["place"] == "Jakarta" and j["group_config"]["place"] == "Bandung"
    assert set(j["pt_layer_keys"]) == {"intro_text", "closing_note", "footer_text", "show_place_date", "place",
                                       "signature_slots", "watermark_text", "watermark_opacity"}
    g = (await klien.get("/api/pdf/templates/invoice", headers=kepala_admin)).json()
    assert g["scope"] == "all" and g["config"]["place"] == "Bandung"


# ── U7 — lapisan PT hanya untuk naskah & tanda tangan ──────────────────────────────────────────────────────────────
async def test_KPT6_U7_kunci_grup_ditolak_di_lapisan_pt(klien, kepala_admin, db, siap):
    r = await klien.put("/api/pdf/templates/invoice", headers=kepala_admin, params={"entity_id": KANDA},
                        json={"config": {"paper_size": "A5"}})
    assert r.status_code == 400, r.text
    assert _detail(r).startswith(AWALAN_KUNCI_GRUP) and "paper_size" not in _detail(r), _detail(r)
    j = (await klien.get("/api/pdf/templates/invoice", headers=kepala_admin, params={"entity_id": KANDA})).json()
    assert j["config"]["paper_size"] == "A4"
    assert j["config"]["place"] == "Jakarta"          # lapisan PT tidak tersentuh oleh permintaan yang ditolak


# ── U8 — buang lapisan PT: kembali ke aturan semua PT ──────────────────────────────────────────────────────────────
async def test_KPT6_U8_buang_lapisan_pt(klien, kepala_admin, db, siap):
    r = await klien.delete("/api/pdf/templates/invoice", headers=kepala_admin, params={"entity_id": KANDA})
    assert r.status_code == 200, r.text
    kanda = await _faktur(klien, kepala_admin, SO_KANDA)
    assert "Bandung," in kanda and "Terima kasih." in kanda
    assert (await klien.get("/api/pdf/templates/invoice", headers=kepala_admin)).json()["config"]["place"] == "Bandung"


async def test_KPT6_U8b_urutan_lapisan(klien, kepala_admin, db, siap):
    """Pelengkap — `__default__` PT di atas jenis dokumen grup, jenis dokumen PT di atas `__default__` PT (ASUMSI)."""
    r = await klien.put("/api/pdf/templates/__default__", headers=kepala_admin, params={"entity_id": KANDA},
                        json={"config": {"place": "Depok", "show_place_date": True}})
    assert r.status_code == 200, r.text
    assert _tempat(await _faktur(klien, kepala_admin, SO_KANDA)).startswith("Depok, ")
    assert _tempat(await _faktur(klien, kepala_admin, SO_KSC)).startswith("Bandung, ")
    r = await klien.put("/api/pdf/templates/invoice", headers=kepala_admin, params={"entity_id": KANDA},
                        json={"config": {"place": "Jakarta"}})
    assert r.status_code == 200, r.text
    assert _tempat(await _faktur(klien, kepala_admin, SO_KANDA)).startswith("Jakarta, ")
    for dt in ("invoice", "__default__"):
        r = await klien.delete(f"/api/pdf/templates/{dt}", headers=kepala_admin, params={"entity_id": KANDA})
        assert r.status_code == 200, r.text
    assert _tempat(await _faktur(klien, kepala_admin, SO_KANDA)).startswith("Bandung, ")


# ── U9 — token {{rekening_bank}}: tepat satu rekening bank aktif ───────────────────────────────────────────────────
async def test_KPT6_U9_token_rekening_bank(klien, kepala_admin, db, siap):
    from core_utils import now_iso
    assert await db.bank_accounts.count_documents({"entity_id": KANDA, "account_type": "bank"}) == 0
    await db.bank_accounts.insert_one({   # fixture: rekening bank PT
        "id": "bank_kpt6_1", "entity_id": KANDA, "account_type": "bank", "bank_name": "BCA",
        "account_number": "123", "name": "BCA Operasional", "is_active": True, "created_at": now_iso()})
    r = await klien.put("/api/pdf/templates/invoice", headers=kepala_admin, params={"entity_id": KANDA},
                        json={"config": {"closing_note": "Transfer ke {{rekening_bank}}."}})
    assert r.status_code == 200, r.text
    pertama = await _faktur(klien, kepala_admin, SO_KANDA)
    assert "BCA 123 (BCA Operasional)" in pertama
    await db.bank_accounts.insert_one({
        "id": "bank_kpt6_2", "entity_id": KANDA, "account_type": "bank", "bank_name": "Mandiri",
        "account_number": "456", "name": "Mandiri Gaji", "is_active": True, "created_at": now_iso()})
    kedua = await _faktur(klien, kepala_admin, SO_KANDA)
    assert "BCA 123" not in kedua and "{{rekening_bank}}" not in kedua and "rekening_bank" not in kedua
    assert "Transfer ke ." in kedua


# ── U10 — token tak dikenal tetap ditolak; `rekening_bank` termasuk yang sah ──────────────────────────────────────
async def test_KPT6_U10_token_tak_dikenal(klien, kepala_admin, db, siap):
    r = await klien.put("/api/pdf/templates/invoice", headers=kepala_admin,
                        json={"config": {"closing_note": "{{rekening_bca}}"}})
    assert r.status_code == 400, r.text
    assert _detail(r).startswith("Placeholder tidak dikenal")
    assert "{{rekening_bank}}" in _detail(r)
    toks = {p["token"] for p in (await klien.get("/api/pdf/templates", headers=kepala_admin)).json()["placeholders"]}
    assert "rekening_bank" in toks


# ── U11 — kop & lapisan PT di luar penugasan pengguna → 403 ────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def sales_cetak(db, akun, sesi):
    # fixture: peran `sales` diberi `pdf_template.view` + `pdf_template.manage`; akun hanya bertugas di `ent_ksc`
    await db.permission_settings.update_one({"id": "default"},
                                            {"$set": {"matrix.sales.pdf_template": ["view", "manage"]}})
    return await sesi(await akun("sales", entitas=(KSC,)))


async def test_KPT6_U11_cakupan_pt(klien, sales_cetak, db, siap):
    h = sales_cetak
    r1 = await klien.get(f"/api/pdf/branding/{KANDA}", headers=h)
    r2 = await klien.put(f"/api/pdf/branding/{KANDA}", headers=h, json={})
    r3 = await klien.put("/api/pdf/templates/invoice", headers=h, params={"entity_id": KANDA},
                         json={"config": {"closing_note": "Diubah dari PT lain"}})
    assert [r1.status_code, r2.status_code, r3.status_code] == [403, 403, 403], (r1.text, r2.text, r3.text)
    r = await klien.get(f"/api/pdf/branding/{KSC}", headers=h)
    assert r.status_code == 200, r.text
    r = await klien.get("/api/pdf/branding/all", headers=h)
    assert r.status_code == 400 and _detail(r) == "Pilih satu PT.", r.text


async def test_KPT6_U11b_contoh_pratinjau_dan_cetak_ikut_cakupan(klien, sales_cetak, kepala_admin, db, siap):
    """Pelengkap U11 — contoh, pratinjau, dan cetak dokumen tidak bisa memakai kop PT di luar penugasan."""
    h = sales_cetak
    r = await klien.get("/api/pdf/sample/invoice", headers=h, params={"entity_id": KANDA})
    assert r.status_code == 403, r.text
    r = await klien.post("/api/pdf/preview", headers=h, json={"doc_type": "invoice", "entity_id": KANDA})
    assert r.status_code == 403, r.text
    r = await klien.post("/api/pdf/preview", headers=kepala_admin,
                         json={"doc_type": "invoice", "source_id": SO_KSC, "entity_id": KANDA})
    assert r.status_code == 400, r.text
    # cetak dokumen PT sendiri dengan `entity_id` PT lain: kop tetap kop PT pemilik dokumen (N1)
    kanda_nama = (await klien.get(f"/api/pdf/branding/{KANDA}", headers=kepala_admin)).json()["company_name"]
    ksc_nama = (await klien.get(f"/api/pdf/branding/{KSC}", headers=kepala_admin)).json()["company_name"]
    r = await klien.get(f"/api/pdf/render/invoice/{SO_KSC}", headers=kepala_admin,
                        params={"format": "html", "entity_id": KANDA})
    assert r.status_code == 200, r.text[:300]
    assert ksc_nama in r.text and kanda_nama not in r.text


# ── U12 — mesin cetak lama tanpa nama perusahaan yang ditulis mati ─────────────────────────────────────────────────
async def test_KPT6_U12_mesin_lama_tanpa_nama_tertulis_mati(klien, sesi, db, siap):
    from core_utils import now_iso
    await db.document_templates.insert_one({   # fixture: template dasar surat jalan khusus PT Kanda, tanpa logo
        "id": "tmpl_kpt6_sj_kanda", "document_type": "surat_jalan", "entity_id": KANDA, "name": "SJ Kanda",
        "header": "Surat Jalan Gudang Jakarta", "footer": "Terima kasih.", "logo_url": "", "paper_size": "A4",
        "orientation": "portrait", "margin_mm": 12, "status": "active", "created_at": now_iso()})
    h = await sesi("admin@kainnusantara.id", entitas=KANDA)
    nama = (await klien.get(f"/api/pdf/branding/{KANDA}", headers=h)).json()["company_name"]
    r = await klien.get(f"/api/documents/preview/{SO_KANDA}", headers=h, params={"document_type": "surat_jalan"})
    assert r.status_code == 200, r.text[:300]
    assert "Kain Nusantara" not in r.text and "kain nusantara" not in r.text.lower()
    assert nama and nama in r.text and "KANDA" in r.text.upper()


# ── U13 — migrasi `pdf_templates.entity_id`: aman diulang, hasil cetak sama ────────────────────────────────────────
def _skrip():
    spec = importlib.util.spec_from_file_location("migrate_kpt6_template_pt", SKRIP_MIGRASI)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_KPT6_U13_migrasi_lapisan_grup(klien, kepala_admin, db, siap):
    await db.pdf_templates.delete_many({})
    await db.pdf_templates.insert_one({"doc_type": "invoice", "config": {"closing_note": "Lama"},   # fixture: bentuk lama
                                       "version": 3, "updated_by": "seed lama"})
    sebelum = await _faktur(klien, kepala_admin, SO_KSC)
    assert "Lama" in sebelum
    mod = _skrip()
    assert mod.main(["--salah"]) == 2                    # argumen tak dikenal: keluar sebelum menyentuh basis data
    lapor = await mod.jalankan(tulis=False)
    assert lapor["mode"] == "lapor" and lapor["tanpa_entity_id"] == 1 and lapor["kembar"] == []
    assert await db.pdf_templates.count_documents({"entity_id": "all"}) == 0     # mode lapor tidak menulis
    cetak: list = []
    mod._cetak(lapor, cetak.append)
    satu = await mod.jalankan(tulis=True)
    dua = await mod.jalankan(tulis=True)
    mod._cetak(satu, cetak.append)
    mod._cetak(dua, cetak.append)
    print("\n".join(cetak))                              # bukti keluaran skrip (`-s`)
    assert any("Baris tanpa entity_id" in c and ": 1 (belum ditulis" in c for c in cetak), cetak
    assert (satu["ditulis"], dua["ditulis"]) == (1, 0)
    assert await db.pdf_templates.count_documents({}) == 1
    row = await db.pdf_templates.find_one({}, {"_id": 0})
    assert row["entity_id"] == "all" and row["config"] == {"closing_note": "Lama"} and row["version"] == 3
    sesudah = await _faktur(klien, kepala_admin, SO_KSC)
    assert sesudah == sebelum
