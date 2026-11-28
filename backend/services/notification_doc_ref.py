"""notification_doc_ref — DOKUMEN yang dituju sebuah notifikasi (bukan hanya layarnya).

Fase 4 · R6 (sisa audit UI tahap 2, G5-09). Notifikasi nota kredit batal item OD (`od_cancel_credit_note`) dan
notifikasi desain (`design_lifecycle`, `design_claim_*`, `design_ai_comment`) hanya membawa `link` berupa LAYAR
("orders", "rnd-designs", bahkan "design-gallery" yang bukan id layar mana pun). Mengekliknya membuka daftar,
lalu orang harus mencari sendiri dokumennya.

Modul ini menurunkan `doc = {ref_type, ref_id, number, label}` dari isi notifikasi saat DIBACA, sehingga
notifikasi LAMA di DB ikut bertaut tanpa migrasi:
  * nota kredit batal item → **SO yang dikoreksi** (`ref_type="sales_order"`): nota ini ditinjau/diterbitkan di
    jejak amandemen detail SO itu (`OdCancelNoteActions`), sama dengan antrean Finance `nota_batal_item`;
  * desain → `ref_type="design"` + id desain galeri (layar Desain & Pattern membuka rinciannya lewat `openRnd`);
  * Kas & Bank 2 (Tugas 4) — kas keluar manual diajukan/diputus → **pengajuannya** (`ref_type="cash_out_request"`,
    `ref` = `<id>` / `<id>:<hasil>`): layar Transaksi Kas membuka pratinjau pengajuan itu;
  * Kas & Bank 3 (Tugas 4b) — selisih opname kas menunggu / diputus → **opnamenya** (`ref_type="cash_count"`, `ref` =
    `<id>` / `<id>:<hasil>`): layar Kas & Bank › Opname Kas membuka pratinjau opname itu.
Bentuk `doc` sama dengan hasil `/documents/resolve`, jadi layar memakai peta tujuan yang sudah ada
(`docLinkTarget` di `workDeskApi.js`). Lookup berkelompok (≤ 4 query per halaman: nota kredit, desain, pengajuan kas,
opname). Tidak pernah melempar.
"""
from typing import Any, Dict, List, Optional, Tuple

from db import db

#: `link` lama yang tidak menunjuk layar mana pun → layar yang benar.
LEGACY_LINK = {"design-gallery": "rnd-designs"}
DESIGN_TYPES = ("design_lifecycle", "design_claim_pending", "design_claim_decided", "design_ai_comment")
#: Kas & Bank 2 — `notification_service.KAS_KELUAR_DIAJUKAN_TYPE` / `KAS_KELUAR_DIPUTUS_TYPE`.
KAS_KELUAR_TYPES = ("kas_keluar_diajukan", "kas_keluar_diputus")
#: Kas & Bank 3 — `notification_service.OPNAME_MENUNGGU_TYPE` / `OPNAME_DIPUTUS_TYPE`.
OPNAME_TYPES = ("opname_kas_menunggu", "opname_kas_diputus")


def _base_ref(n: Dict[str, Any]) -> str:
    """`ref` tanpa akhiran penerima `#<user_id>` (lihat `notification_service.create_addressed`)."""
    return str(n.get("ref") or "").split("#", 1)[0]


def _key_of(n: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """(jenis kunci, nilai) yang dicari untuk satu notifikasi, atau None bila tipenya tidak ditangani."""
    t, ref = str(n.get("type") or ""), _base_ref(n)
    if not ref:
        return None
    if t == "od_cancel_credit_note":
        return ("cn", ref)
    if t == "design_lifecycle":
        return ("design", ref.split(":", 1)[0])
    if t in ("design_claim_pending", "design_claim_decided"):
        return ("claim", ref.split(":", 1)[-1])
    if t == "design_ai_comment":
        return ("file", ref.split(":", 1)[0])
    if t in KAS_KELUAR_TYPES:
        return ("pkk", ref.split(":", 1)[0])
    if t in OPNAME_TYPES:
        return ("opk", ref.split(":", 1)[0])
    return None


async def attach_doc_refs(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tambahkan `doc` (dan perbaiki `link` lama) pada notifikasi yang ditangani. In-place, lalu balik list."""
    keys: Dict[str, set] = {"cn": set(), "design": set(), "claim": set(), "file": set(), "pkk": set(), "opk": set()}
    for n in rows:
        if isinstance(n, dict):
            if n.get("link") in LEGACY_LINK:
                n["link"] = LEGACY_LINK[n["link"]]
            k = _key_of(n)
            if k:
                keys[k[0]].add(k[1])
    if not any(keys.values()):
        return rows
    found: Dict[Tuple[str, str], Dict[str, Any]] = {}
    try:
        if keys["cn"]:
            async for c in db.credit_notes.find({"id": {"$in": list(keys["cn"])}},
                                                {"_id": 0, "id": 1, "number": 1, "order_id": 1, "order_number": 1}):
                if c.get("order_id"):
                    found[("cn", c["id"])] = {
                        "ref_type": "sales_order", "ref_id": c["order_id"], "number": c.get("order_number") or "",
                        "label": f"Nota kredit {c.get('number') or ''} di {c.get('order_number') or 'pesanan'}".strip()}
        proj = {"_id": 0, "id": 1, "code": 1, "title": 1, "claims.id": 1, "files.id": 1}
        or_q = []
        if keys["design"]:
            or_q.append({"id": {"$in": list(keys["design"])}})
        if keys["claim"]:
            or_q.append({"claims.id": {"$in": list(keys["claim"])}})
        if keys["file"]:
            or_q.append({"files.id": {"$in": list(keys["file"])}})
        if or_q:
            async for d in db.design_gallery.find({"$or": or_q}, proj):
                doc = {"ref_type": "design", "ref_id": d["id"], "number": d.get("code") or "",
                       "label": f"Desain {d.get('code') or d.get('title') or ''}".strip()}
                found[("design", d["id"])] = doc
                for c in d.get("claims") or []:
                    if c.get("id") in keys["claim"]:
                        found[("claim", c["id"])] = doc
                for f in d.get("files") or []:
                    if f.get("id") in keys["file"]:
                        found[("file", f["id"])] = doc
        if keys["pkk"]:
            async for c in db.cash_out_requests.find({"id": {"$in": list(keys["pkk"])}},
                                                     {"_id": 0, "id": 1, "number": 1}):
                found[("pkk", c["id"])] = {"ref_type": "cash_out_request", "ref_id": c["id"],
                                           "number": c.get("number") or "",
                                           "label": f"Pengajuan kas keluar {c.get('number') or ''}".strip()}
        if keys["opk"]:
            async for c in db.cash_counts.find({"id": {"$in": list(keys["opk"])}}, {"_id": 0, "id": 1, "number": 1}):
                found[("opk", c["id"])] = {"ref_type": "cash_count", "ref_id": c["id"], "number": c.get("number") or "",
                                           "label": f"Opname kas {c.get('number') or ''}".strip()}
    except Exception:  # noqa: BLE001 — tautan dokumen pelengkap; gagal → notifikasi tetap tampil dengan link layar
        return rows
    for n in rows:
        if not isinstance(n, dict):
            continue
        k = _key_of(n)
        if k and k in found:
            n["doc"] = found[k]
    return rows
