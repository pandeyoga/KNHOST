"""KP-T5 serah-terima (a) — katalog jenis nomor dan pembaca format; nomor yang terbit TIDAK berubah satu pun.

U1  uji statik: semua pemanggilan `next_doc_number` di `backend/` (di luar uji, seed, dan skrip) dikenali
    `doc_number_kinds.lookup`; bawaan katalog = argumen titik panggil (lebar, cara). Sejak (b) termasuk tiga deret KP-35
    dan 11 titik panggil bersama yang kini mengirim PT dokumennya (`kind=` + `entity_id=`); U2 diulang penuh atasnya.
U2  SETARA: untuk tiap titik panggil × PT (`None`, `"all"`, `""`, `ent_ksc`, `ent_kanda`) dan tiga keadaan data
    (penghitung hari ini = 41; deret belum ada tetapi dokumen lama ada; kosong) — nomor dan isi `number_sequences`
    sesudah pemanggilan sama persis dengan fungsi LAMA (salinan utuh `core_utils.next_doc_number` di `1392969`, di bawah).
U3  semai dari nomor tertinggi yang ada: `KSC/SO-00007` → `KSC/SO-00008`.

Hitungan tangan (U2, contoh): penghitung `(ent_ksc, "SO")` = 41 → `$inc` → 42 → `KSC/` + `SO-` + `00042` (lebar 5).
Bersama: `("__shared__", "sales_returns:number:SRET-")` = 41 → `SRET-00042`. Lot: `(ent_ksc, "LOT-<YYMM>")` = 41 →
`KSC/LOT-<YYMM>-0042` (lebar 4). RFID: `("__shared__", "rfid_cycle_counts:cc_number:CC")` = 41 → `CC00042`.

Fixture: dokumen dan penghitung disisipkan langsung (bukan alur bisnis) — yang diuji adalah fungsi penomorannya.
"""
import ast
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

BACKEND = Path(__file__).resolve().parents[1]
_LEWATI_FOLDER = {"tests", "tests_mem", "scripts"}
_STEMPEL = "2611"   # pengganti bagian f-string (`LOT-{ym}-`, `INV-{nomor}-`) di uji statik

# 59 awalan daftar spesifikasi KP-T5 (44 per PT + 18 bersama − 3 kembar).
AWALAN_SPESIFIKASI = {
    "SO-", "SOS-", "PO-", "SJ-", "FKT-", "AR-", "CASH-", "JE-", "CN-", "DN-", "AMD-", "CB-", "RPB-", "SLB-", "DN-DENDA-",
    "CASE-", "FA-", "PD-", "STL-", "MCC-", "IC-", "ICS-", "ICL-", "ICR-", "PIN-", "TRF-", "GRN-", "INS-", "REG-", "LOT-",
    "MKO-", "SCT-", "SCR-", "RPR-", "LG-", "VHL-", "CF-", "DSR-", "SMP-", "SPEC-", "LV-", "OT-", "PAY-", "SLIP-",
    "SRET-", "RTN-", "PRET-", "VB-", "FPM-", "PR-", "RFQ-", "LCV-", "WO-", "SUP-", "MAK-", "CC", "BTG", "PA", "PJ",
}
# Ditemukan di HEAD tetapi tidak ada di daftar spesifikasi: kode pelanggan (`customers.code`, lebar 4, bersama) dibuat
# lewat alias `_ndn(...)` di `routers/customers.py`, `routers/admin.py`, `services/crm_omnichannel_service.py`.
AWALAN_TAMBAHAN = {"CUST-"}
# Serah-terima (b): tiga deret KP-35 ("baca nomor terakhir + 1") kini lewat `next_doc_number` → jenis ke-60…62 spesifikasi.
# Setaranya dengan generator lama diuji `test_KPT5b_pengaturan.py::test_KPT5_KP35_setara_generator_lama` (fungsi lama
# di sini tidak pernah membuat nomor itu, jadi tidak bisa menjadi oracle).
AWALAN_KP35 = {"VBM-", "EMP-", "SORD-"}
JENIS_KP35 = {"vbm", "emp", "sord"}
# CR-T1 — deret baru `PKR-` (pengajuan perubahan kredit, per PT) lahir sesudah KP-T5: tidak ada di daftar spesifikasi
# maupun fungsi lama. Setara dengan jalur lama karena katalog bawaannya = argumen titik panggil (diuji U2 seperti lainnya).
# PK-22 — deret baru `STR-` (setoran kewajiban gaji BPJS/PPh 21, per PT): alasan sama dengan `PKR-`.
# PM-T4 — deret baru `TTP-` (titipan tunai sales) dan `STT-` (setoran titipan tunai sales), per PT: alasan sama.
AWALAN_SESUDAH_KPT5 = {"PKR-", "STR-", "TTP-", "STT-"}


# ── Fungsi LAMA (salinan utuh `backend/core_utils.py` di 1392969; oracle setara) ──────────────────────────────────
async def _lama_max_existing_number(collection, field, prefix, entity_id, scope_field="entity_id"):
    from db import db
    pat = re.compile(r"(\d+)\s*$")
    n = 0
    q = {field: {"$regex": re.escape(prefix)}, scope_field: entity_id}
    async for d in db[collection].find(q, {"_id": 0, field: 1}):
        val = d.get(field)
        if isinstance(val, str):
            m = pat.search(val)
            if m:
                n = max(n, int(m.group(1)))
    return n


async def _lama_next_doc_number(collection, field, prefix, width=5, entity_id=None, scheme="per_entity_prefix"):
    from db import db
    from pymongo import ReturnDocument
    from core_utils import entity_code, now_iso
    if entity_id is None or entity_id == "all" or scheme == "shared":
        key = {"entity_id": "__shared__", "doc_type": f"{collection}:{field}:{prefix}"}
        if not await db.number_sequences.find_one(key, {"_id": 1}):
            pat = re.compile(r"(\d+)\s*$")
            n = 0
            async for d in db[collection].find(
                {field: {"$regex": f"^{re.escape(prefix)}"}}, {"_id": 0, field: 1}
            ):
                val = d.get(field)
                if isinstance(val, str):
                    m = pat.search(val)
                    if m:
                        n = max(n, int(m.group(1)))
            await db.number_sequences.update_one(
                key, {"$setOnInsert": {**key, "prefix": prefix, "last_no": n,
                                       "created_at": now_iso()}}, upsert=True)
        seq = await db.number_sequences.find_one_and_update(
            key, {"$inc": {"last_no": 1}, "$set": {"updated_at": now_iso()}},
            return_document=ReturnDocument.AFTER)
        return f"{prefix}{seq['last_no']:0{width}d}"

    doc_type = prefix.rstrip("-/").upper() or prefix
    code = await entity_code(entity_id)
    key = {"entity_id": entity_id, "doc_type": doc_type}
    if not await db.number_sequences.find_one(key):
        seed_no = await _lama_max_existing_number(collection, field, prefix, entity_id)
        await db.number_sequences.update_one(
            key,
            {"$setOnInsert": {**key, "prefix": prefix, "last_no": seed_no,
                              "created_at": now_iso()}},
            upsert=True,
        )
    seq = await db.number_sequences.find_one_and_update(
        key,
        {"$inc": {"last_no": 1}, "$set": {"updated_at": now_iso()}},
        return_document=ReturnDocument.AFTER,
    )
    return f"{code}/{prefix}{seq['last_no']:0{width}d}"


def _kunci_lama(collection, field, prefix, entity_id, scheme):
    if entity_id is None or entity_id == "all" or scheme == "shared":
        return {"entity_id": "__shared__", "doc_type": f"{collection}:{field}:{prefix}"}
    return {"entity_id": entity_id, "doc_type": prefix.rstrip("-/").upper() or prefix}


# ── Pengurai titik panggil ─────────────────────────────────────────────────────────────────────────────────────
def _nilai(node, konst: Dict[str, Any], lokal: Dict[str, ast.AST]) -> List[Any]:
    """Semua nilai teks/angka yang mungkin untuk satu argumen (konstanta, konstanta modul, variabel lokal, a if c else b,
    f-string dengan bagian berubah diganti `_STEMPEL`). Kosong = tidak bisa diurai."""
    if isinstance(node, ast.Constant):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _nilai(node.body, konst, lokal) + _nilai(node.orelse, konst, lokal)
    if isinstance(node, ast.JoinedStr):
        return ["".join(v.value if isinstance(v, ast.Constant) else _STEMPEL for v in node.values)]
    if isinstance(node, ast.Name):
        if node.id in lokal:
            return _nilai(lokal[node.id], konst, {})
        if node.id in konst:
            return [konst[node.id]]
    return []


def _titik_panggil() -> List[Dict[str, Any]]:
    hasil = []
    for p in sorted(BACKEND.rglob("*.py")):
        rel = p.relative_to(BACKEND)
        if (rel.parts[0] in _LEWATI_FOLDER or rel.name.startswith(("test_", "seed")) or rel.name == "core_utils.py"
                or "node_modules" in rel.parts):
            continue
        src = p.read_text(encoding="utf-8")
        if "next_doc_number" not in src:
            continue
        tree = ast.parse(src)
        nama = {"next_doc_number"}
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module == "core_utils":
                nama |= {a.asname or a.name for a in n.names if a.name == "next_doc_number"}
        konst = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
                 for t in n.targets if isinstance(t, ast.Name)}
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            lokal = {t.id: n.value for n in ast.walk(fn) if isinstance(n, ast.Assign) for t in n.targets
                     if isinstance(t, ast.Name)}
            for c in ast.walk(fn):
                if not (isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in nama):
                    continue
                kw = {k.arg: k.value for k in c.keywords}
                pos = list(c.args) + [None] * 6
                lebar = kw.get("width", pos[3])
                skema = kw.get("scheme", pos[5])
                jenis = kw.get("kind")
                hasil.append({
                    "file": str(rel), "line": c.lineno,
                    "collection": (_nilai(pos[0], konst, lokal) or [None])[0],
                    "field": (_nilai(pos[1], konst, lokal) or [None])[0],
                    "prefixes": _nilai(pos[2], konst, lokal),
                    "width": (_nilai(lebar, konst, lokal) or [None])[0] if lebar is not None else 5,
                    "scheme": (_nilai(skema, konst, lokal) or [None])[0] if skema is not None else "per_entity_prefix",
                    "kind": (_nilai(jenis, konst, lokal) or [""])[0] if jenis is not None else "",
                    "has_entity": "entity_id" in kw or pos[4] is not None,
                })
    # satu pemanggilan bisa berada di fungsi bersarang → hapus kembar (berkas, baris)
    unik = {(h["file"], h["line"]): h for h in hasil}
    return [unik[k] for k in sorted(unik)]


TITIK = _titik_panggil()


def test_KPT5_U1_semua_titik_panggil_dikenali_katalog():
    import doc_number_kinds as dnk
    # PK-20 — ±13 pemberi nomor kas (`next_doc_number("cash_transactions", …)` di tiap pembuat kas) disatukan di
    # `services/cash_ledger.next_cash_number`; ambang kewajaran pengurai turun dari 90 ke 80 (85 titik saat itu).
    assert len(TITIK) >= 80, f"pengurai menemukan terlalu sedikit pemanggilan: {len(TITIK)}"
    tak_dikenal, beda, awalan = [], [], set()
    for t in TITIK:
        assert t["collection"] and t["field"] and t["prefixes"], f"tidak terurai: {t}"
        for pref in t["prefixes"]:
            hit = dnk.lookup(t["collection"], t["field"], pref, t["scheme"] or "per_entity_prefix", t["kind"])
            if hit is None:
                tak_dikenal.append(f"{t['file']}:{t['line']} {t['collection']}.{t['field']} {pref!r}")
                continue
            k = hit[0]
            if k["derived"]:
                continue
            awalan.add(k["identity_prefix"])
            d = k["default"]
            if int(t["width"]) != d["width"]:
                beda.append(f"{t['file']}:{t['line']} lebar {t['width']} ≠ katalog {d['width']} ({k['kind']})")
            if t["has_entity"] and t["scheme"] != "shared" and d["scope"] != "per_pt":
                beda.append(f"{t['file']}:{t['line']} per PT di titik panggil, katalog {d['scope']} ({k['kind']})")
    assert not tak_dikenal, "pemanggilan tidak dikenali katalog:\n" + "\n".join(tak_dikenal)
    # Cara bawaan tiap jenis = cara titik panggilnya: dipanggil per PT di mana pun → `per_pt`; hanya bersama → `bersama`.
    cara: Dict[str, set] = {}
    for t in TITIK:
        for pref in t["prefixes"]:
            hit = dnk.lookup(t["collection"], t["field"], pref, t["scheme"] or "per_entity_prefix", t["kind"])
            if hit and not hit[0]["derived"]:
                per_pt = t["has_entity"] and t["scheme"] != "shared"
                cara.setdefault(hit[0]["kind"], set()).add("per_pt" if per_pt else "bersama")
    for kd, mode in cara.items():
        harap = "per_pt" if "per_pt" in mode else "bersama"
        if dnk.KINDS[kd]["default"]["scope"] != harap:
            beda.append(f"{kd}: titik panggil {sorted(mode)} → katalog harus {harap}")
    assert not beda, "bawaan katalog ≠ titik panggil:\n" + "\n".join(beda)
    # Spesifikasi menulis 59 (+3 KP-35 = 62); HEAD punya 60 (+3 = 63): CUST- lewat alias `_ndn` — laporan "Menyimpang".
    assert AWALAN_SPESIFIKASI <= awalan, sorted(AWALAN_SPESIFIKASI - awalan)
    assert awalan - AWALAN_SPESIFIKASI == AWALAN_TAMBAHAN | AWALAN_KP35 | AWALAN_SESUDAH_KPT5, \
        sorted(awalan - AWALAN_SPESIFIKASI)
    assert len(awalan) == 63 + len(AWALAN_SESUDAH_KPT5)


def _kasus() -> List[Dict[str, Any]]:
    """Kombinasi unik argumen titik panggil × PT."""
    ym = datetime.now(timezone.utc).strftime("%y%m")
    out, lihat = [], set()
    for t in TITIK:
        if t["kind"] in JENIS_KP35:
            continue
        prefs = list(t["prefixes"])
        if t["collection"] == "inventory_lots":   # sisipan bulan ini + bulan lampau (sisipan dari titik panggil dipakai)
            prefs = [p.replace(_STEMPEL, s) for p in prefs for s in (ym, "2501")]
        for pref in prefs:
            ents = [None, "all", "", "ent_ksc", "ent_kanda"] if t["has_entity"] else [None]
            for e in ents:
                k = (t["collection"], t["field"], pref, int(t["width"]), e, t["scheme"], t["kind"])
                if k not in lihat:
                    lihat.add(k)
                    out.append({"collection": k[0], "field": k[1], "prefix": k[2], "width": k[3], "entity_id": e,
                                "scheme": k[5] or "per_entity_prefix", "kind": k[6],
                                "where": f"{t['file']}:{t['line']}"})
    return out


KASUS = _kasus()


async def _bersihkan(db, koleksi: str) -> None:
    await db.number_sequences.delete_many({})
    await db[koleksi].delete_many({"_kpt5": True})


async def _isi_sequences(db) -> List[Dict[str, Any]]:
    return sorted(([{k: v for k, v in d.items() if k not in ("_id", "created_at", "updated_at")}
                    async for d in db.number_sequences.find({})]), key=lambda d: (d["entity_id"], d["doc_type"]))


async def _baru(c: Dict[str, Any]) -> str:
    from core_utils import next_doc_number
    kw = {"kind": c["kind"]} if c["kind"] else {}
    return await next_doc_number(c["collection"], c["field"], c["prefix"], c["width"], c["entity_id"], c["scheme"],
                                 **kw)


async def _lama(c: Dict[str, Any]) -> str:
    return await _lama_next_doc_number(c["collection"], c["field"], c["prefix"], c["width"], c["entity_id"],
                                       c["scheme"])


async def _dokumen_lama(db, c: Dict[str, Any]) -> None:
    """Dokumen yang sudah terbit dengan bentuk lama (per PT ber-kode, bersama, tanpa kode) di dua PT."""
    f, p = c["field"], c["prefix"]
    await db[c["collection"]].insert_many([
        {"_kpt5": True, "id": "kpt5_a", "entity_id": "ent_ksc", f: f"KSC/{p}{17:0{c['width']}d}"},
        {"_kpt5": True, "id": "kpt5_b", "entity_id": "ent_kanda", f: f"KANDA/{p}{9:0{c['width']}d}"},
        {"_kpt5": True, "id": "kpt5_c", "entity_id": "ent_ksc", f: f"{p}{23:0{c['width']}d}"},
        {"_kpt5": True, "id": "kpt5_d", "entity_id": "", f: f"{p}{31:0{c['width']}d}"},
    ])


async def _bandingkan(db, c: Dict[str, Any], siapkan) -> Optional[str]:
    hasil = {}
    for nama, fn in (("lama", _lama), ("baru", _baru)):
        await _bersihkan(db, c["collection"])
        await siapkan()
        n1 = await fn(c)
        n2 = await fn(c)
        hasil[nama] = (n1, n2, await _isi_sequences(db))
    await _bersihkan(db, c["collection"])
    if hasil["lama"] != hasil["baru"]:
        return f"{c['where']} {c} → lama {hasil['lama'][:2]} / baru {hasil['baru'][:2]}"
    return None


async def test_KPT5_U2_setara_semua_titik_panggil_tiga_keadaan(db):
    beda = []
    for c in KASUS:
        kunci = _kunci_lama(c["collection"], c["field"], c["prefix"], c["entity_id"], c["scheme"])

        async def penghitung_41(kunci=kunci):
            await db.number_sequences.insert_one({**kunci, "prefix": "x", "last_no": 41})

        async def dokumen(c=c):
            await _dokumen_lama(db, c)

        async def kosong():
            return None

        for siapkan in (penghitung_41, dokumen, kosong):
            r = await _bandingkan(db, c, siapkan)
            if r:
                beda.append(f"[{siapkan.__name__}] {r}")
    assert not beda, f"{len(beda)} beda dari {len(KASUS) * 3}:\n" + "\n".join(beda[:40])


async def test_KPT5_U2_contoh_hitung_tangan_dan_cakupan_jenis(db):
    import doc_number_kinds as dnk
    from core_utils import next_doc_number
    ym = datetime.now(timezone.utc).strftime("%y%m")
    await db.number_sequences.delete_many({})
    await db.number_sequences.insert_many([
        {"entity_id": "ent_ksc", "doc_type": "SO", "last_no": 41},
        {"entity_id": "__shared__", "doc_type": "sales_returns:number:SRET-", "last_no": 41},
        {"entity_id": "ent_ksc", "doc_type": f"LOT-{ym}", "last_no": 41},
        {"entity_id": "__shared__", "doc_type": "rfid_cycle_counts:cc_number:CC", "last_no": 41},
    ])
    assert await next_doc_number("sales_orders", "number", "SO-", entity_id="ent_ksc") == "KSC/SO-00042"
    assert await next_doc_number("sales_returns", "number", "SRET-", width=5, scheme="shared") == "SRET-00042"
    from services.lot_service import next_lot_number
    assert await next_lot_number("ent_ksc") == f"KSC/LOT-{ym}-0042"
    assert await next_doc_number("rfid_cycle_counts", "cc_number", "CC") == "CC00042"
    await db.number_sequences.delete_many({})
    # Tiap jenis katalog yang dibuat lewat `next_doc_number` diuji setara oleh U2 di atas.
    dicakup = set()
    for c in KASUS:
        hit = dnk.lookup(c["collection"], c["field"], c["prefix"], c["scheme"], c["kind"])
        if hit and not hit[0]["derived"]:
            dicakup.add(hit[0]["kind"])
    # 59 awalan spesifikasi → 61 jenis (CN-/DN- masing-masing dua jenis) + `cust` = 62 setara fungsi lama; tiga deret
    # KP-35 (`vbm`, `emp`, `sord`) lewat `next_doc_number` sejak serah-terima (b) — setara generator lama di `test_KPT5b_*`.
    assert JENIS_KP35.isdisjoint(dicakup)
    assert dicakup | JENIS_KP35 == {k["kind"] for k in dnk.KINDS_LIST if not k["derived"]}
    assert len(dicakup) == 62 + len(AWALAN_SESUDAH_KPT5) and len(dicakup | JENIS_KP35) == 65 + len(AWALAN_SESUDAH_KPT5)
    titik_kp35 = {dnk.lookup(t["collection"], t["field"], t["prefixes"][0], t["scheme"], t["kind"])[0]["kind"]
                  for t in TITIK if t["kind"] in JENIS_KP35}
    assert titik_kp35 == JENIS_KP35


async def test_KPT5_U3_semai_dari_nomor_tertinggi(db):
    from core_utils import next_doc_number
    await db.number_sequences.delete_many({})
    await db.sales_orders.delete_many({"_kpt5": True})
    await db.sales_orders.insert_one({"_kpt5": True, "id": "so_kpt5_u3", "entity_id": "ent_ksc",
                                      "number": "KSC/SO-00007"})
    try:
        assert await next_doc_number("sales_orders", "number", "SO-", entity_id="ent_ksc") == "KSC/SO-00008"
    finally:
        await db.sales_orders.delete_many({"_kpt5": True})
        await db.number_sequences.delete_many({})


async def test_KPT5_a_tanpa_baris_format_saat_dipasang(db):
    """Tanpa migrasi data: koleksi `doc_number_formats` kosong saat aplikasi menyala; pembaca jatuh ke bawaan."""
    from services import doc_numbering_service as dns
    assert await db.doc_number_formats.count_documents({}) == 0
    f = await dns.effective_format("so", "ent_ksc")
    assert (f["prefix"], f["width"], f["date_token"], f["reset"], f["scope"], f["source"]) == \
        ("SO-", 5, "", "tidak", "per_pt", "bawaan")


async def test_KPT5_a_indeks_unik_format(aplikasi):
    import indexes
    nama = {(it["collection"], it["name"]) for it in indexes.REQUIRED_UNIQUE_INDEXES}
    assert ("doc_number_formats", "uq_kind_entity") in nama


@pytest.mark.parametrize("token,stamp,reset,harap", [
    ("", "", "tidak", ""), ("YYYY", "2026", "tidak", ""), ("YYYY", "2026", "tahunan", "2026"),
    ("YY", "26", "tahunan", "26"), ("YYMM", "2611", "bulanan", "2611"), ("YYMMDD", "261113", "bulanan", "2611"),
    ("YYMMDD", "261113", "harian", "261113"), ("YYYYMM", "202611", "tahunan", "2026"),
])
def test_KPT5_a_bagian_periode(token, stamp, reset, harap):
    from services import doc_numbering_service as dns
    assert dns.period_part(token, stamp, reset) == harap
