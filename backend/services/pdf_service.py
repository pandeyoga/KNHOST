"""
pdf_service.py — Orkestrasi render dokumen: template config + branding entitas +
resolver context + (opsional) blok e-sign → HTML → PDF.

KP-T6 (KP-18, KP-19, KP-34) — identitas kop (nama, alamat, NPWP, kontak, slogan, situs) dari **Profil PT**
(`business_entities`); `document_branding` hanya menyimpan gambar & tanda tangan (teks lama tetap dibaca sampai PT itu
diselesaikan lewat `resolve_identity`). Konfigurasi template punya lapisan PT (`pdf_templates.entity_id`) khusus untuk
naskah, tempat, tanda tangan, dan tanda air (`PT_LAYER_KEYS`). Token `{{rekening_bank}}` diisi penyedia yang bisa diganti
(`register_token_provider`).
"""
from __future__ import annotations
import base64
import copy
import hashlib
import io
import json
from db import db
from services.pdf_engine import render_html, render_pdf
from services.pdf_resolvers import DOC_REGISTRY

# ─── Default template config per dokumen ─────────────────────────────────────
# Sesi #086 — konfigurasi BERLAPIS (pola sipro `doc_layout`): bawaan kode → `__default__`
# (gaya seluruh dokumen) → override per jenis dokumen yang hanya menyimpan PERBEDAAN.
DEFAULT_CODE = "__default__"
DEFAULT_TEMPLATE_CFG = {
    "paper_size": "A4", "orientation": "portrait",
    "margin_top": 16, "margin_right": 14, "margin_bottom": 16, "margin_left": 14,
    "font_family": "'DejaVu Sans'", "font_size": 10,
    "color_primary": "#0058CC", "color_accent": "#1a1a1a",
    "show_logo": True, "show_terbilang": True,
    "watermark_text": "", "watermark_opacity": 6,          # 1..40 (%)
    "footer_text": "", "show_page_numbers": True,
    "title_override": "",
    "custom_fields": [],       # [{label, value}]
    "signature_slots": [],     # override doc.signatures bila diisi [{label, role, name, show_stamp}]
    "hidden_fields": [],       # label meta yang disembunyikan
    # Kop: dirakit sistem | gambar kop desainer | kosong (kertas berkop cetakan)
    "header_mode": "system",   # system | image | none
    "footer_mode": "text",     # text | image | none
    # Naskah pembuka/penutup dengan placeholder {{token}} (divalidasi saat simpan)
    "intro_text": "", "closing_note": "",
    "show_place_date": False, "place": "",
    "show_materai": False, "materai_note": "Bermeterai cukup",
    "show_generated_note": False,
    # Bagian dokumen yang boleh dimatikan (angka tetap milik mesin — hanya tampil/sembunyi)
    "sections": {"parties": True, "meta": True, "items": True, "totals": True,
                 "notes": True, "signatures": True, "refs": True},
    # Gaya tabel rincian
    "table": {"grid": "full", "show_header": True, "header_fill": True, "zebra": False,
              "total_highlight": True, "font_size": 9, "grid_color": "#bbbbbb"},
}
NESTED_KEYS = ("sections", "table")

# Placeholder yang SAH di naskah — diturunkan dari konteks dokumen yang benar-benar terisi.
PLACEHOLDERS = {
    "nomor": "Nomor dokumen", "tanggal": "Tanggal dokumen", "judul": "Judul dokumen",
    "status": "Status dokumen", "perusahaan": "Nama perusahaan penerbit",
    "alamat_perusahaan": "Alamat perusahaan", "npwp_perusahaan": "NPWP perusahaan",
    "pihak": "Nama pihak tujuan (pelanggan/supplier)", "alamat_pihak": "Alamat pihak tujuan",
    "grand_total": "Nilai total dokumen", "terbilang": "Total dalam huruf",
    "jumlah_baris": "Jumlah baris rincian", "hari_ini": "Tanggal cetak (WIB)",
    # KP-T6 (KP-34) — nilainya dari penyedia token (`register_token_provider`), bukan dari konteks dokumen.
    "rekening_bank": "Rekening bank pembayaran PT",
}
#: KP-T6 — keterangan token di layar naskah (dikirim bersama daftar token).
PLACEHOLDER_NOTES = {
    "rekening_bank": ("Rekening bank pembayaran PT. Kosong bila PT punya lebih dari satu rekening dan belum ada "
                      "rekening tujuan di pesanan."),
}

# KP-T6 (KP-19) — lapisan PT hanya boleh memuat naskah, tempat-tanggal, tanda tangan, dan tanda air. Tata letak (kertas,
# margin, huruf, warna, kolom) tetap satu untuk semua PT.
PT_LAYER_KEYS = ("intro_text", "closing_note", "footer_text", "show_place_date", "place",
                 "signature_slots", "watermark_text", "watermark_opacity")
GROUP_SCOPE = "all"
_GROUP_VALUES = [GROUP_SCOPE, "", None]   # baris lama tanpa `entity_id` = lapisan grup (sampai dimigrasi)
#: Label isian template untuk pesan galat (L1 — tanpa nama field).
TEMPLATE_KEY_LABELS = {
    "paper_size": "Ukuran kertas", "orientation": "Orientasi", "margin_top": "Margin atas",
    "margin_right": "Margin kanan", "margin_bottom": "Margin bawah", "margin_left": "Margin kiri",
    "font_family": "Huruf", "font_size": "Ukuran huruf", "color_primary": "Warna utama",
    "color_accent": "Warna aksen", "show_logo": "Tampilkan logo", "show_terbilang": "Tampilkan terbilang",
    "watermark_text": "Tanda air", "watermark_opacity": "Ketebalan tanda air", "footer_text": "Teks footer",
    "show_page_numbers": "Nomor halaman", "title_override": "Judul dokumen", "custom_fields": "Field tambahan",
    "signature_slots": "Slot tanda tangan", "hidden_fields": "Baris info yang disembunyikan",
    "header_mode": "Mode kop surat", "footer_mode": "Mode footer", "intro_text": "Teks pembuka",
    "closing_note": "Teks penutup", "show_place_date": "Tempat & tanggal sebelum tanda tangan", "place": "Tempat",
    "show_materai": "Catatan meterai", "materai_note": "Teks meterai",
    "show_generated_note": "Catatan dihasilkan sistem", "sections": "Bagian dokumen", "table": "Gaya tabel",
}
_TOKEN_RE = None


def _token_re():
    global _TOKEN_RE
    if _TOKEN_RE is None:
        import re
        _TOKEN_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
    return _TOKEN_RE


def unknown_tokens(text: str) -> list:
    return sorted({t for t in _token_re().findall(text or "") if t not in PLACEHOLDERS})


def render_text(text: str, doc: dict, branding: dict, extra: dict | None = None) -> str:
    """Isi {{token}} dari konteks dokumen (+ `extra` dari penyedia token). Token tak dikenal dibiarkan apa adanya."""
    if not text:
        return ""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    party = doc.get("party_to") or {}
    total = ""
    for t in doc.get("totals") or []:
        if t.get("strong"):
            total = t.get("value") or ""
    vals = {
        "nomor": doc.get("number") or "", "tanggal": doc.get("date") or "",
        "judul": doc.get("title") or "", "status": doc.get("status") or "",
        "perusahaan": branding.get("company_name") or "",
        "alamat_perusahaan": branding.get("address") or "",
        "npwp_perusahaan": branding.get("npwp") or "",
        "pihak": party.get("name") or "", "alamat_pihak": party.get("address") or "",
        "grand_total": total, "terbilang": doc.get("terbilang") or "",
        "jumlah_baris": str(len(doc.get("items") or [])),
        "hari_ini": datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d %b %Y"),
    }
    vals.update(extra or {})
    return _token_re().sub(lambda m: str(vals.get(m.group(1), m.group(0))), text)


def _clean_cfg(config: dict) -> dict:
    """Ambil hanya kunci yang dikenal; kelompok bersarang digabung per kunci."""
    out = {}
    for k, v in (config or {}).items():
        if k not in DEFAULT_TEMPLATE_CFG:
            continue
        if k in NESTED_KEYS and isinstance(v, dict):
            out[k] = {kk: vv for kk, vv in v.items() if kk in DEFAULT_TEMPLATE_CFG[k]}
        else:
            out[k] = v
    return out


def merge_cfg(base: dict, over: dict) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
           for k, v in base.items()}
    for k, v in (over or {}).items():
        if k in NESTED_KEYS and isinstance(v, dict):
            out[k] = {**out.get(k, {}), **v}
        else:
            out[k] = v
    return out


def diff_cfg(effective_default: dict, full: dict) -> dict:
    """Simpan hanya yang BERBEDA dari bawaan efektif (pola override sipro)."""
    out = {}
    for k, v in full.items():
        base = effective_default.get(k)
        if k in NESTED_KEYS and isinstance(v, dict):
            d = {kk: vv for kk, vv in v.items() if (base or {}).get(kk) != vv}
            if d:
                out[k] = d
        elif v != base:
            out[k] = v
    return out


def qr_data_url(payload: str) -> str:
    import qrcode
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ─── Lapisan template: bawaan kode → `__default__` grup → jenis grup → `__default__` PT → jenis PT ──────────────────
def _is_group(entity_id: str | None) -> bool:
    return entity_id in (None, "", GROUP_SCOPE)


def _layer_filter(doc_type: str, entity_id: str | None = None) -> dict:
    """Saringan satu baris lapisan. Grup = `entity_id` "all" atau baris lama tanpa `entity_id` (KP-T6)."""
    if _is_group(entity_id):
        return {"doc_type": doc_type, "entity_id": {"$in": list(_GROUP_VALUES)}}
    return {"doc_type": doc_type, "entity_id": entity_id}


async def _layer_row(doc_type: str, entity_id: str | None = None, projection: dict | None = None) -> dict:
    return await db.pdf_templates.find_one(_layer_filter(doc_type, entity_id), projection or {"_id": 0}) or {}


def _pt_only(config: dict) -> dict:
    """Lapisan PT hanya membawa `PT_LAYER_KEYS` (kunci lain di baris PT diabaikan saat dibaca)."""
    return {k: v for k, v in _clean_cfg(config).items() if k in PT_LAYER_KEYS}


async def _default_effective() -> dict:
    row = await _layer_row(DEFAULT_CODE)
    cfg = merge_cfg(DEFAULT_TEMPLATE_CFG, {})
    if row and isinstance(row.get("config"), dict):
        cfg = merge_cfg(cfg, _clean_cfg(row["config"]))
    return cfg


async def _group_cfg(doc_type: str) -> dict:
    """Hasil lapisan grup saja (tanpa PT): bawaan kode → `__default__` → jenis dokumen."""
    cfg = await _default_effective()
    if doc_type != DEFAULT_CODE:
        row = await _layer_row(doc_type)
        if row and isinstance(row.get("config"), dict):
            cfg = merge_cfg(cfg, _clean_cfg(row["config"]))
    return cfg


async def _pt_base(doc_type: str, entity_id: str) -> dict:
    """Konfigurasi di BAWAH lapisan PT `doc_type` — pembanding saat menyimpan lapisan itu."""
    if doc_type == DEFAULT_CODE:
        return await _default_effective()
    cfg = await _group_cfg(doc_type)
    row = await _layer_row(DEFAULT_CODE, entity_id)
    if isinstance(row.get("config"), dict):
        cfg = merge_cfg(cfg, _pt_only(row["config"]))
    return cfg


async def get_template_cfg(doc_type: str, entity_id: str | None = None) -> dict:
    """Konfigurasi EFEKTIF. Tanpa `entity_id` = hasil grup (perilaku sebelum KP-T6).

    KP-T6 (`ASUMSI` spesifikasi) — `__default__` PT di atas jenis dokumen grup: PT yang menetapkan kota sekali untuk
    semua dokumennya tidak tertimpa aturan grup per jenis dokumen."""
    return await _with_pt_layers(await _group_cfg(doc_type), doc_type, entity_id)


def _pt_layer_types(doc_type: str) -> tuple:
    return (DEFAULT_CODE,) if doc_type == DEFAULT_CODE else (DEFAULT_CODE, doc_type)


async def _with_pt_layers(cfg: dict, doc_type: str, entity_id: str | None) -> dict:
    """Terapkan lapisan `__default__` PT lalu jenis dokumen PT di atas `cfg` (tanpa PT: `cfg` apa adanya)."""
    if _is_group(entity_id):
        return cfg
    for dt in _pt_layer_types(doc_type):
        row = await _layer_row(dt, entity_id)
        if isinstance(row.get("config"), dict):
            cfg = merge_cfg(cfg, _pt_only(row["config"]))
    return cfg


async def pt_override_keys(doc_type: str, entity_id: str) -> list:
    """Kunci yang ditimpa PT untuk jenis dokumen ini (lapisan `__default__` PT + jenis PT)."""
    keys: set = set()
    for dt in _pt_layer_types(doc_type):
        row = await _layer_row(dt, entity_id, {"_id": 0, "config": 1})
        keys |= set(_pt_only(row.get("config") or {}))
    return sorted(keys)


async def template_meta(doc_type: str, entity_id: str | None = None) -> dict:
    row = await _layer_row(doc_type, entity_id)
    return {"customized": bool(row), "version": row.get("version") or 0,
            "updated_at": row.get("updated_at") or "", "updated_by": row.get("updated_by") or "",
            "override_keys": sorted((row.get("config") or {}).keys())}


def _assert_known_tokens(clean: dict) -> None:
    for t in ("intro_text", "closing_note"):
        bad = unknown_tokens(clean.get(t, ""))
        if bad:
            raise ValueError(f"Placeholder tidak dikenal di naskah: {', '.join('{{' + b + '}}' for b in bad)}. "
                             f"Yang sah: {', '.join('{{' + k + '}}' for k in PLACEHOLDERS)}")


async def save_template_cfg(doc_type: str, config: dict, actor: str = "", entity_id: str | None = GROUP_SCOPE) -> dict:
    """`__default__` grup menyimpan konfigurasi penuh; jenis dokumen hanya menyimpan PERBEDAAN terhadap bawaan efektif,
    sehingga mengganti warna di `__default__` ikut mengubah semua dokumen yang tidak menimpanya (pola sipro).

    KP-T6 — `entity_id` PT: hanya `PT_LAYER_KEYS`, disimpan bila berbeda dari lapisan di bawahnya (`_pt_base`). Kunci
    lain yang dikirim dengan nilai SAMA dengan aturan semua PT dibuang diam-diam (layar mengirim konfigurasi penuh);
    yang nilainya BERBEDA → `ValueError` "Bagian ini hanya bisa diatur untuk semua PT: …"."""
    from core_utils import now_iso
    clean = _clean_cfg(config)
    _assert_known_tokens(clean)
    group = _is_group(entity_id)
    if group and doc_type == DEFAULT_CODE:
        stored = merge_cfg(DEFAULT_TEMPLATE_CFG, clean)
    elif group:
        base = await _default_effective()
        stored = diff_cfg(base, merge_cfg(base, clean))
    else:
        base = await _pt_base(doc_type, entity_id)
        outside = [k for k, v in clean.items() if k not in PT_LAYER_KEYS and diff_cfg(base, {k: v})]
        if outside:
            raise ValueError("Bagian ini hanya bisa diatur untuk semua PT: "
                             f"{', '.join(TEMPLATE_KEY_LABELS.get(k, k) for k in outside)}.")
        stored = diff_cfg(base, {k: v for k, v in clean.items() if k in PT_LAYER_KEYS})
    scope = GROUP_SCOPE if group else entity_id
    cur = await _layer_row(doc_type, scope, {"_id": 0, "version": 1})
    await db.pdf_templates.update_one(
        _layer_filter(doc_type, scope),
        {"$set": {"doc_type": doc_type, "entity_id": scope, "config": stored, "updated_by": actor,
                  "updated_at": now_iso(), "version": int(cur.get("version") or 0) + 1}},
        upsert=True,
    )
    return await get_template_cfg(doc_type, None if group else scope)


async def reset_template_cfg(doc_type: str, entity_id: str | None = GROUP_SCOPE) -> dict:
    """Buang lapisan itu saja (grup ATAU satu PT); dokumen yang sudah terbit tidak berubah."""
    await db.pdf_templates.delete_many(_layer_filter(doc_type, entity_id))
    return await get_template_cfg(doc_type, None if _is_group(entity_id) else entity_id)


async def list_templates() -> list:
    rows = {r["doc_type"]: r for r in await db.pdf_templates.find(
        {"entity_id": {"$in": list(_GROUP_VALUES)}},
        {"_id": 0, "doc_type": 1, "version": 1, "updated_at": 1, "updated_by": 1}).to_list(500)}
    out = [{"doc_type": DEFAULT_CODE, "label": "Bawaan seluruh dokumen (gaya & kop)",
            "module": "__default__", "customized": DEFAULT_CODE in rows,
            **{k: (rows.get(DEFAULT_CODE) or {}).get(k) for k in ("version", "updated_at", "updated_by")}}]
    for k, v in DOC_REGISTRY.items():
        r = rows.get(k) or {}
        out.append({"doc_type": k, "label": v["label"], "module": v["module"],
                    "esignable": v.get("esignable", False), "customized": k in rows,
                    "version": r.get("version"), "updated_at": r.get("updated_at"),
                    "updated_by": r.get("updated_by")})
    return out


def placeholder_list() -> list:
    return [{"token": k, "label": v, **({"note": PLACEHOLDER_NOTES[k]} if k in PLACEHOLDER_NOTES else {})}
            for k, v in PLACEHOLDERS.items()]


# ─── KP-T6 (KP-34) — penyedia token yang bisa diganti (PM-T2 mengganti `rekening_bank`) ──────────────────────────────
_TOKEN_PROVIDERS: dict = {}


def register_token_provider(name: str, fn) -> None:
    """`fn(entity_id, doc) -> str` (async). Hanya untuk token yang terdaftar di `PLACEHOLDERS`."""
    if name not in PLACEHOLDERS:
        raise ValueError(f"Token '{name}' tidak terdaftar di PLACEHOLDERS")
    _TOKEN_PROVIDERS[name] = fn


async def default_bank_text(entity_id: str | None, doc: dict) -> str:
    """Bawaan KP-T6: PT dengan TEPAT SATU rekening bank aktif → "{bank} {nomor} ({nama})"; selain itu kosong.
    (`ASUMSI` spesifikasi — belum ada penanda rekening utama; rekening tujuan per pesanan = unit PM-T2.)"""
    if not entity_id:
        return ""
    rows = await db.bank_accounts.find(
        {"entity_id": entity_id, "account_type": "bank", "is_active": {"$ne": False}},
        {"_id": 0, "bank_name": 1, "account_number": 1, "name": 1}).to_list(2)
    if len(rows) != 1:
        return ""
    a = rows[0]
    head = " ".join(x for x in (str(a.get("bank_name") or "").strip(), str(a.get("account_number") or "").strip()) if x)
    name = str(a.get("name") or "").strip()
    return f"{head} ({name})" if head and name else (head or name)


register_token_provider("rekening_bank", default_bank_text)


async def token_values(cfg: dict, entity_id: str | None, doc: dict) -> dict:
    """Nilai token dari penyedia — hanya token yang dipakai naskah konfigurasi ini."""
    used = set(_token_re().findall(f"{cfg.get('intro_text') or ''}\n{cfg.get('closing_note') or ''}"))
    return {name: str(await fn(entity_id, doc) or "") for name, fn in _TOKEN_PROVIDERS.items() if name in used}


# ─── KP-T6 (KP-18) — identitas kop: satu sumber = Profil PT ────────────────────────────────────────────────────────
#: (kunci kop, label) — urutan tampil di tabel selisih layar.
IDENTITY_FIELDS = (("company_name", "Nama di kop"), ("address", "Alamat"), ("npwp", "NPWP"), ("phone", "Telepon"),
                   ("email", "Email"), ("tagline", "Slogan"), ("website", "Situs web"))
LEGACY_TEXT_KEYS = tuple(k for k, _ in IDENTITY_FIELDS)
BRANDING_IMAGE_KEYS = ("logo_b64", "header_image_b64", "footer_image_b64", "stamp_b64", "signatures")
TEXT_FIELDS_MESSAGE = "Nama, alamat, NPWP, dan kontak diubah di Profil PT."
IDENTITY_ACTIONS = ("pakai_profil", "salin_ke_profil")
IDENTITY_RESOLVED_MESSAGE = "Identitas kop PT ini sudah diselesaikan."


class IdentityConflict(Exception):
    """409 — identitas kop PT sudah diselesaikan sebelumnya."""


def _txt(v) -> str:
    return str(v or "").strip()


def _profile_address(ent: dict) -> str:
    return ", ".join(x for x in (_txt(ent.get("address")), _txt(ent.get("city"))) if x)


def profile_identity(ent: dict) -> dict:
    """Identitas kop dari Profil PT (`print_name` → nama legal)."""
    return {"company_name": _txt(ent.get("print_name")) or _txt(ent.get("legal_name")) or _txt(ent.get("short_name"))
            or "Perusahaan",
            "address": _profile_address(ent), "npwp": _txt(ent.get("npwp")), "phone": _txt(ent.get("phone")),
            "email": _txt(ent.get("email")), "tagline": _txt(ent.get("tagline")), "website": _txt(ent.get("website"))}


def legacy_identity(row: dict, ent: dict) -> dict:
    """Rumus kop sebelum KP-T6 (teks `document_branding` menang) — dipakai sampai PT diselesaikan."""
    return {"company_name": _txt(row.get("company_name")) or _txt(ent.get("legal_name")) or _txt(ent.get("short_name"))
            or "Perusahaan",
            "address": _txt(row.get("address")) or _profile_address(ent),
            "npwp": _txt(row.get("npwp")) or _txt(ent.get("npwp")), "phone": _txt(row.get("phone")),
            "email": _txt(row.get("email")) or _txt(ent.get("email")), "tagline": _txt(row.get("tagline")),
            "website": _txt(row.get("website"))}


def has_legacy_text(row: dict) -> bool:
    return any(_txt((row or {}).get(k)) for k in LEGACY_TEXT_KEYS)


async def get_branding(entity_id: str | None) -> dict:
    ent = await db.business_entities.find_one({"id": entity_id}, {"_id": 0}) if entity_id else None
    ent = ent or {}
    row = await db.document_branding.find_one({"entity_id": entity_id}, {"_id": 0}) if entity_id else None
    row = row or {}
    logo_src = ""
    if row.get("logo_b64"):
        logo_src = f"data:image/png;base64,{row['logo_b64']}" if not str(row["logo_b64"]).startswith("data:") else row["logo_b64"]
    elif ent.get("logo_url"):
        logo_src = ent["logo_url"]

    def _img(key):
        v = row.get(key) or ""
        return v if (not v or str(v).startswith("data:")) else f"data:image/png;base64,{v}"
    profile = profile_identity(ent)
    legacy_mode = bool(row) and not row.get("identity_resolved_at") and has_legacy_text(row)
    ident = legacy_identity(row, ent) if legacy_mode else profile
    conflicts = [{"field": k, "label": lbl, "print_value": ident[k], "profile_value": profile[k]}
                 for k, lbl in IDENTITY_FIELDS if legacy_mode and ident[k] != profile[k]]
    return {
        "entity_id": entity_id,
        **ident,
        "address": ident["address"] or "-",
        "logo_src": logo_src,
        "header_image_src": _img("header_image_b64"),   # kop gambar buatan desainer
        "footer_image_src": _img("footer_image_b64"),
        "stamp_src": _img("stamp_b64"),                 # cap perusahaan
        "signatures": row.get("signatures") or [],   # [{label, role, name, signature_b64}]
        # KP-T6 — dari mana identitas kop dibaca + selisih teks lama ↔ Profil PT (kosong bila sudah memakai Profil PT)
        "identity_source": "teks_lama" if legacy_mode else "profil",
        "identity_conflicts": conflicts,
        "identity_resolved_at": row.get("identity_resolved_at") or "",
        "identity_resolved_by": row.get("identity_resolved_by") or "",
    }


async def save_branding(entity_id: str, data: dict, actor: str = "") -> dict:
    """KP-T6 — hanya gambar & tanda tangan. Teks identitas (field lama) → `ValueError` (400 di router)."""
    from core_utils import now_iso
    if any(k in data and data.get(k) is not None for k in LEGACY_TEXT_KEYS):
        raise ValueError(TEXT_FIELDS_MESSAGE)
    allowed = {k: data.get(k) for k in BRANDING_IMAGE_KEYS if k in data}
    await db.document_branding.update_one(
        {"entity_id": entity_id},
        {"$set": {"entity_id": entity_id, **allowed, "updated_by": actor, "updated_at": now_iso()}},
        upsert=True,
    )
    return await get_branding(entity_id)


def legacy_to_profile(row: dict, ent: dict) -> dict:
    """Isian Profil PT dari teks kop lama yang TERISI ("Salin teks kop ke Profil PT").

    - nama di kop → `print_name` (kosong bila sama dengan nama legal);
    - alamat → `address`; akhiran ", {kota PT}" dibuang karena kop mencetak alamat + kota;
    - NPWP, telepon, email, slogan, situs → isian bernama sama. Teks lama yang kosong tidak menghapus Profil PT."""
    out: dict = {}
    name = _txt(row.get("company_name"))
    if name:
        out["print_name"] = "" if name == _txt(ent.get("legal_name")) else name
    addr = _txt(row.get("address"))
    if addr:
        city = _txt(ent.get("city"))
        if city and addr.lower().endswith(f", {city}".lower()):
            addr = addr[: -len(f", {city}")].rstrip(" ,")
        out["address"] = addr
    for k in ("npwp", "phone", "email", "tagline", "website"):
        if _txt(row.get(k)):
            out[k] = _txt(row.get(k))
    return out


async def resolve_identity(entity_id: str, action: str, reason: str, actor: dict) -> dict:
    """KP-T6 — selesaikan identitas kop PT: `pakai_profil` (tandai selesai) atau `salin_ke_profil` (teks lama → Profil
    PT lewat `validate_entity_input` KP-T1, lalu tandai selesai). 400 alasan kosong / pilihan salah / validasi;
    `IdentityConflict` bila sudah diselesaikan. Kembali: `{branding, copied}` (`copied` = isian Profil PT yang ditulis)."""
    from core_utils import now_iso
    from services import entity_lifecycle_service as lifecycle
    from services import entity_provisioning_service as provisioning
    reason = _txt(reason)
    if not reason:
        raise ValueError("Alasan wajib diisi.")
    if action not in IDENTITY_ACTIONS:
        raise ValueError("Pilihan tidak dikenal. Pilih 'Pakai data Profil PT' atau 'Salin teks kop ke Profil PT'.")
    ent = await lifecycle.get_entity_or_404(entity_id)
    row = await db.document_branding.find_one({"entity_id": entity_id}, {"_id": 0}) or {}
    if row.get("identity_resolved_at"):
        raise IdentityConflict(IDENTITY_RESOLVED_MESSAGE)
    clean: dict = {}
    if action == "salin_ke_profil":
        data = legacy_to_profile(row, ent)
        if data:   # validasi dulu (400 sebelum menulis apa pun)
            clean = await provisioning.validate_entity_input(data, entity_id=entity_id, existing=ent)
    if not row:
        await db.document_branding.update_one({"entity_id": entity_id}, {"$setOnInsert": {"entity_id": entity_id}},
                                              upsert=True)
    res = await db.document_branding.update_one(
        {"entity_id": entity_id, "identity_resolved_at": {"$in": [None, ""]}},
        {"$set": {"identity_resolved_at": now_iso(), "identity_resolved_by": actor.get("name", ""),
                  "identity_resolved_action": action, "identity_resolved_reason": reason}})
    if not res.modified_count:
        raise IdentityConflict(IDENTITY_RESOLVED_MESSAGE)
    if clean:
        await db.business_entities.update_one({"id": entity_id}, {"$set": {**clean, "updated_at": now_iso()}})
    return {"branding": await get_branding(entity_id), "copied": clean}


def _apply_cfg_to_doc(doc: dict, cfg: dict, branding: dict, tokens: dict | None = None) -> dict:
    if cfg.get("title_override"):
        doc["title"] = cfg["title_override"]
    # custom fields → tambah ke meta
    meta = list(doc.get("meta") or [])
    for cf in cfg.get("custom_fields") or []:
        if cf.get("label"):
            meta.append({"label": cf["label"], "value": cf.get("value", "")})
    # sembunyikan field tertentu
    hidden = set(cfg.get("hidden_fields") or [])
    doc["meta"] = [m for m in meta if m["label"] not in hidden]
    # override signature slots dari config, jika tidak ada pakai default doc + isi nama dari branding
    if cfg.get("signature_slots"):
        doc["signatures"] = cfg["signature_slots"]
    # tempel gambar TTD dari branding (match by role/label)
    brand_sig = {(s.get("role") or s.get("label") or "").lower(): s for s in (branding.get("signatures") or [])}
    for s in doc.get("signatures") or []:
        key = (s.get("role") or s.get("label") or "").lower()
        if key in brand_sig and brand_sig[key].get("signature_b64"):
            b = brand_sig[key]["signature_b64"]
            s["signature_src"] = b if str(b).startswith("data:") else f"data:image/png;base64,{b}"
            if not s.get("name") and brand_sig[key].get("name"):
                s["name"] = brand_sig[key]["name"]
        if s.get("show_stamp") and branding.get("stamp_src"):
            s["stamp_src"] = branding["stamp_src"]
    # Bagian yang dimatikan konfigurasi — nilai tidak diubah, hanya tidak dicetak.
    sec = {**DEFAULT_TEMPLATE_CFG["sections"], **(cfg.get("sections") or {})}
    if not sec.get("parties"):
        doc["party_to"] = None
    if not sec.get("meta"):
        doc["meta"] = []
    if not sec.get("items"):
        doc["items"] = []
    if not sec.get("totals"):
        doc["totals"] = []
    if not sec.get("notes"):
        doc["notes"] = ""
    if not sec.get("signatures"):
        doc["signatures"] = []
    doc["_hide_refs"] = not sec.get("refs")
    # Naskah pembuka/penutup + tempat-tanggal (placeholder diisi dari konteks nyata).
    doc["intro_text"] = render_text(cfg.get("intro_text") or "", doc, branding, tokens)
    doc["closing_note"] = render_text(cfg.get("closing_note") or "", doc, branding, tokens)
    if cfg.get("show_place_date"):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        hari = doc.get("date") or datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d %b %Y")
        doc["place_date"] = f"{cfg.get('place') or ''}, {hari}".strip(", ")
    return doc


ESIGN_HASH_VERSION = 2
_VOLATILE_META = {"Dicetak"}


def canonical_content(content: dict) -> dict:
    """CX-10 — isi dokumen yang ditandatangani: output resolver tanpa stempel cetak/metadata turunan."""
    c = {k: v for k, v in copy.deepcopy(content or {}).items()
         if not k.startswith("_") and k not in ("esign", "esign_superseded", "refs")}
    if isinstance(c.get("meta"), list):
        c["meta"] = [m for m in c["meta"] if not (isinstance(m, dict) and m.get("label") in _VOLATILE_META)]
    return c


def content_hash(content: dict) -> str:
    payload = json.dumps(canonical_content(content), sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _attach_esign(doc: dict, doc_type: str, source_id: str, public_base: str, chash: str = ""):
    """Tempel blok e-sign + QR HANYA dari tanda tangan atas versi isi yang sama (CX-10)."""
    all_sigs = await db.document_signatures.find(
        {"doc_type": doc_type, "source_id": source_id, "status": "signed"},
        {"_id": 0, "signature_b64": 0, "doc_snapshot": 0}).sort("signed_at", 1).to_list(50)
    sigs = [s for s in all_sigs
            if s.get("hash_version") == ESIGN_HASH_VERSION and s.get("doc_hash") == chash]
    if not sigs:
        if all_sigs:
            doc["esign_superseded"] = {
                "message": "Isi dokumen berubah setelah ditandatangani — tanda tangan lama tidak berlaku untuk versi ini.",
                "last_signed_at": (all_sigs[-1].get("signed_at") or "")[:19].replace("T", " ")}
        return doc
    last = sigs[-1]
    code = last.get("verification_code")
    verify_url = f"{public_base}/verify-document/{code}"
    # FASE G-4 — blok tanda tangan harus BERNAMA: siapa, JABATAN apa, dan KAPAN.
    # Nama saja tidak cukup untuk dokumen kertas yang dipegang pihak luar.
    people = []
    for s in sigs:
        people.append({
            "name": s.get("signer_name") or "-",
            "role": s.get("signer_role") or "",
            "at": (s.get("signed_at") or "")[:19].replace("T", " "),
        })
    doc["esign"] = {
        "code": code,
        "signers": ", ".join(p["name"] for p in people),
        "people": people,
        "signed_at": (last.get("signed_at") or "")[:19].replace("T", " "),
        "hash_short": (last.get("doc_hash") or "")[:24] + "…",
        "verify_url": verify_url,
        "qr_src": qr_data_url(verify_url),
    }
    return doc


async def attach_document_refs(doc: dict, doc_type: str, source_id: str,
                               source: dict, public_base: str) -> dict:
    """FASE G-4 — tempelkan blok **Referensi Dokumen** (+ QR Jejak Dokumen).

    Dipasang di SATU tempat (bukan di 21 resolver) supaya setiap dokumen cetak —
    apa pun jenisnya — otomatis menyebut surat-surat yang berkaitan. Tanpa ini,
    penerima kertas tidak bisa menghubungkan Surat Jalan dengan pesanannya.

    Aturannya configurable lewat Pusat Pengaturan (kelompok "Dokumen, Referensi &
    Tanda Tangan"): tampil/tidak, pakai QR/tidak, dan berapa nomor yang dicetak.

    Kunci yang mengatur blok ini (dibaca lewat `doc_refs_service.pdf_options`):
    `docref.show_in_pdf` · `docref.qr_in_pdf` · `docref.pdf_max_refs`.
    """
    from services import doc_refs_service as refs

    entity_id = source.get("entity_id") or ""
    try:
        opts = await refs.pdf_options(entity_id)
    except Exception:  # noqa: BLE001 — konfigurasi belum ter-seed → pakai bawaan aman
        opts = {"show": True, "qr": True, "max": 6}
    if not opts.get("show"):
        return doc

    # doc_type PDF bisa berbagi koleksi (invoice/delivery_note/picking_list → sales_orders);
    # relasi selalu dibaca dari doc_type KANONIK koleksinya.
    reg = DOC_REGISTRY.get(doc_type) or {}
    canon = (doc_type if doc_type in refs.DOC_TYPES
             else refs.type_of_collection(reg.get("collection", "")))
    if not canon:
        return doc
    line = await refs.reference_line(canon, source_id, limit=int(opts.get("max") or 6))
    if not line.get("items"):
        return doc
    trace_url = f"{public_base}/jejak-dokumen/{canon}/{source_id}" if public_base else ""
    doc["refs_block"] = {
        "text": line["text"],
        "items": line["items"],
        "hidden": line.get("hidden", 0),
        "trace_url": trace_url,
        # UAT 24 Okt (audit UI 106) — teks di kertas: alamat aplikasi + nomor dokumen, bukan URL berisi id internal.
        "trace_host": public_base.split("://", 1)[-1] if public_base else "",
        "qr_src": qr_data_url(trace_url) if (opts.get("qr") and trace_url) else "",
    }
    return doc


async def build_document(doc_type: str, source_id: str, entity_id: str | None,
                         cfg_override: dict | None = None, public_base: str = "",
                         override_layer: str = "") -> dict:
    """Return {source, cfg, branding, doc} — dipakai render html/pdf.

    FASE G-4 — `public_base` kosong (render dari job/penjadwal/WhatsApp/skrip) TIDAK
    boleh menghasilkan QR tanpa host: kertas yang dipegang orang jadi tidak bisa
    dibuka. Karena itu di sini ada fallback ke URL aplikasi yang terkonfigurasi.

    KP-T6 — konfigurasi berlapis PT (`get_template_cfg(doc_type, eid)`). `override_layer="all"` (pratinjau perancang
    saat menyunting aturan semua PT): `cfg_override` menggantikan hasil grup, lalu lapisan PT tetap diterapkan di
    atasnya — pratinjau = yang benar-benar tercetak untuk PT itu. Selain itu `cfg_override` ditaruh paling atas.
    """
    from services.app_url import configured_app_url
    public_base = (public_base or configured_app_url() or "").rstrip("/")
    reg = DOC_REGISTRY.get(doc_type)
    if not reg:
        raise ValueError(f"doc_type '{doc_type}' tidak dikenal")
    source = await db[reg["collection"]].find_one({"id": source_id}, {"_id": 0})
    if not source:
        raise LookupError(f"Dokumen sumber {doc_type}/{source_id} tidak ditemukan")
    eid = entity_id or source.get("entity_id")
    # FASE G-0 — `finance.base_currency` kini benar-benar dipakai: seluruh nominal pada
    # dokumen cetak (invoice, surat jalan, PO) mengikuti mata uang pembukuan entitas.
    from services.config_currency import base_currency
    from services.pdf_engine import set_document_currency
    set_document_currency(await base_currency(eid))
    if cfg_override and override_layer == GROUP_SCOPE:
        cfg = await _with_pt_layers(merge_cfg(await _group_cfg(doc_type), _clean_cfg(cfg_override)), doc_type, eid)
    else:
        cfg = await get_template_cfg(doc_type, eid)
        if cfg_override:
            cfg = merge_cfg(cfg, _clean_cfg(cfg_override))
    branding = await get_branding(eid)
    doc = await reg["resolver"](source, db)
    chash = content_hash(doc)  # CX-10 — hash isi sebelum template/branding/esign/refs
    snapshot = canonical_content(doc)
    tokens = await token_values(cfg, eid, doc)   # KP-T6 — sebelum naskah diisi
    doc = _apply_cfg_to_doc(doc, cfg, branding, tokens)
    doc = await _attach_esign(doc, doc_type, source_id, public_base, chash)
    if not doc.get("_hide_refs"):
        doc = await attach_document_refs(doc, doc_type, source_id, source, public_base)
    return {"source": source, "cfg": cfg, "branding": branding, "doc": doc, "reg": reg,
            "content_hash": chash, "content_snapshot": snapshot}


async def render_document(doc_type: str, source_id: str, entity_id: str | None,
                          fmt: str = "pdf", cfg_override: dict | None = None, public_base: str = "",
                          hidden: set | None = None, override_layer: str = ""):
    built = await build_document(doc_type, source_id, entity_id, cfg_override, public_base, override_layer)
    if hidden:  # L01 LN-012 — atribut tersembunyi untuk peran pencetak diganti "—"
        from services.field_visibility import ensure_product_grades, redact
        await ensure_product_grades()
        built["doc"] = redact(built["doc"], hidden, placeholder="—")
    html = render_html(built["cfg"], built["branding"], built["doc"])
    if fmt == "html":
        return html, "text/html", built
    pdf, engine = render_pdf(html)
    return pdf, "application/pdf", built
