"""F0-F + FASE E-1 — Provisioning & VALIDASI badan usaha (SATU JALUR).

Membuat badan usaha siap-pakai dalam satu langkah:
  - **validasi tunggal** (`validate_entity_input`) yang dipakai `POST` MAUPUN
    `PATCH` — sebelum FASE E-1 keduanya punya aturan sendiri sehingga `PATCH`
    bisa menembus keunikan yang ditegakkan `POST` (E1.2),
  - lengkapi default badan usaha (`ENTITY_DEFAULTS`); tahun buku & mata uang yang dipilih saat dibuat ditulis ke
    lapisan PT registry (`finance.fiscal_year_end_month`, `finance.base_currency` — KP-T1),
  - pastikan bagan akun (CoA) tersedia — CoA SHARED by-code, buku terpisah lewat
    `journal_entries.entity_id` (lihat `gl_service`) — KP-T2: SEBELUM PT disimpan,
  - siapkan penanda config override per-badan-usaha dan pemasok antar-PT — KP-T2: langkah yang
    bisa diulang (`run_provisioning_steps`, `POST /api/entities/{id}/provisioning/retry`).
Penomoran (CODE/PREFIX-NNNNN) & buku besar otomatis aktif begitu dipakai.
"""
import re
from typing import Any, Dict, Optional

from fastapi import HTTPException

from db import db
from core_utils import invalidate_entity_code, new_id, now_iso
from domain_registry import ENTITY_TYPE_VALUES, PERSONAL_ENTITY_TYPES
from services.entity_context_service import ENTITY_DEFAULTS
from services import entity_lifecycle_service as lifecycle
from services import gl_service

TAX_MODES = lifecycle.TAX_MODES
#: KP-T1 — pesan 400 isian profil PT (sama dengan validasi di layar).
NPWP_MESSAGE = lifecycle.NPWP_MESSAGE
OWNERSHIP_MESSAGE = "Persen kepemilikan harus lebih dari 0 dan paling banyak 100."
IS_GROUP_MESSAGE = "Isian PT induk harus ya atau tidak."
TAX_MODE_PATCH_MESSAGE = "Status PKP diubah lewat tindakan 'Ubah status PKP', bukan lewat ubah profil."
#: KP-T1 — isian `POST /api/entities` yang ditulis ke lapisan PT registry, bukan ke master PT.
PROFILE_INPUT_KEYS = {name: key for name, key in lifecycle.PROFILE_KEYS}


def _slug_prefix(short_name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]", "", short_name or "").upper()
    return s[:6] or "ENT"


def compose_personal_legal_name(owner_name: str, business_label: str) -> str:
    """E1.1 — nama legal usaha perorangan = nama pemilik + label usaha.

    Usaha perorangan tidak punya badan hukum terpisah, jadi “nama legal”-nya
    adalah nama orangnya. Label usaha (mis. “Toko Kain Berkah”) dipakai sebagai
    nama dagang. Hasil: “Budi Santoso (Toko Kain Berkah)”.
    """
    owner = (owner_name or "").strip()
    label = (business_label or "").strip()
    if owner and label:
        return f"{owner} ({label})"
    return owner or label


async def validate_entity_input(data: Dict[str, Any], *, entity_id: str = "",
                                existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validasi + normalisasi payload badan usaha. Dipakai POST dan PATCH.

    `existing` diisi saat PATCH supaya aturan bisa membandingkan nilai lama
    (mis. kunci prefix E1.3 hanya berlaku bila prefix BERUBAH).
    Mengembalikan dict berisi HANYA field yang tervalidasi & ternormalisasi.
    """
    prev = dict(existing or {})
    out = dict(data or {})
    is_patch = bool(entity_id)

    def eff(key: str, default: Any = "") -> Any:
        """Nilai efektif setelah patch diterapkan."""
        return out[key] if key in out else prev.get(key, default)

    # ── jenis badan usaha (E1.1) ──
    if "type" in out:
        out["type"] = (out.get("type") or "").strip()
        if out["type"] not in ENTITY_TYPE_VALUES:
            raise HTTPException(
                status_code=400,
                detail=f"Jenis badan usaha “{out['type']}” tidak dikenal. "
                       f"Pilihan: {', '.join(ENTITY_TYPE_VALUES)}.")
    ent_type = eff("type", "PT")

    # ── usaha perorangan: nama legal dibentuk dari nama pemilik + label usaha ──
    if ent_type in PERSONAL_ENTITY_TYPES:
        owner = str(eff("owner_name")).strip()
        label = str(eff("business_label")).strip()
        if not is_patch and not owner:
            raise HTTPException(
                status_code=400,
                detail="Usaha perorangan wajib menyebut nama pemilik — nama legalnya "
                       "adalah nama orangnya, bukan nama PT.")
        composed = compose_personal_legal_name(owner, label)
        if composed:
            out["owner_name"] = owner
            out["business_label"] = label
            out["legal_name"] = composed

    # ── wajib isi ──
    legal_name = str(eff("legal_name")).strip()
    short_name = str(eff("short_name")).strip()
    if not legal_name or not short_name:
        raise HTTPException(status_code=400,
                            detail="Nama legal dan nama singkat wajib diisi.")
    if "legal_name" in out:
        out["legal_name"] = legal_name
    if "short_name" in out:
        out["short_name"] = short_name

    # ── mode pajak & NPWP: WAJIB hanya bila PKP (E1.1) ──
    if "default_tax_mode" in out:
        out["default_tax_mode"] = (out.get("default_tax_mode") or "").strip()
        if is_patch:
            # KP-T1 (KP-02) — status PKP berubah hanya lewat tindakan bertanggal + beralasan (`change_tax_status`).
            if out["default_tax_mode"] != (prev.get("default_tax_mode") or ""):
                raise HTTPException(status_code=400, detail=TAX_MODE_PATCH_MESSAGE)
            out.pop("default_tax_mode")
        elif out["default_tax_mode"] not in TAX_MODES:
            raise HTTPException(
                status_code=400,
                detail="Mode pajak harus “ppn” (PKP) atau “non_ppn” (non-PKP).")
    # KP-T1 (KP-23) — pola NPWP, persen kepemilikan, PT induk: hanya isian yang DIKIRIM dan nilainya BERUBAH, supaya data
    # lama yang belum rapi tidak menghalangi perubahan isian lain.
    def changed(key: str) -> bool:
        return key in out and (not is_patch or out[key] != prev.get(key))

    if "npwp" in out:
        out["npwp"] = str(out.get("npwp") or "").strip()
        if changed("npwp") and out["npwp"] and not lifecycle.npwp_valid(out["npwp"]):
            raise HTTPException(status_code=400, detail=NPWP_MESSAGE)
    if changed("ownership_pct"):
        val = out["ownership_pct"]
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not 0 < float(val) <= 100:
            raise HTTPException(status_code=400, detail=OWNERSHIP_MESSAGE)
        out["ownership_pct"] = round(float(val), 2)
    if changed("is_group") and not isinstance(out["is_group"], bool):
        raise HTTPException(status_code=400, detail=IS_GROUP_MESSAGE)
    if eff("default_tax_mode", "ppn") == "ppn" and not str(eff("npwp")).strip():
        raise HTTPException(
            status_code=400,
            detail="Badan usaha PKP wajib mengisi NPWP karena akan menerbitkan "
                   "faktur pajak. Untuk non-PKP, pilih mode pajak “non_ppn”.")

    # ── keunikan (case-insensitive) ──
    if "short_name" in out:
        await lifecycle.assert_unique("short_name", out["short_name"], exclude_id=entity_id)

    # ── kode dokumen: normalisasi → keunikan → kunci bila sudah terbit dokumen ──
    if "doc_prefix" in out:
        prefix = (out.get("doc_prefix") or "").strip().upper()
        if not prefix:
            prefix = _slug_prefix(short_name)
        if not re.fullmatch(r"[A-Z0-9]{2,10}", prefix):
            raise HTTPException(
                status_code=400,
                detail="Kode dokumen hanya boleh huruf/angka (2–10 karakter), "
                       "mis. KSC atau KANDA — dipakai sebagai awalan nomor dokumen.")
        out["doc_prefix"] = prefix
        await lifecycle.assert_unique("doc_prefix", prefix, exclude_id=entity_id)
        if is_patch:
            await lifecycle.assert_prefix_change_allowed(
                entity_id, prev.get("doc_prefix", ""), prefix)

    # ── lokasi tervalidasi pada PATCH (Fase 4 · R6, G5-25) — POST dinormalisasi `provision_entity`. ──
    if is_patch:
        from services.entity_location_service import normalize_location_patch
        out.update(normalize_location_patch(prev, out))
    return out


def _profile_value_or_400(name: str, value: Any) -> Any:
    """KP-T1 — nilai tahun buku / mata uang saat PT dibuat, diperiksa dengan aturan registry (pesan untuk manusia)."""
    import config_registry as registry
    entry = registry.require(PROFILE_INPUT_KEYS[name])
    try:
        return registry.coerce(entry, value)
    except ValueError:
        if entry["type"] == "enum":
            pilihan = ", ".join(o["label"] for o in entry.get("options") or [])
            raise HTTPException(status_code=400,
                                detail=f"{entry['label']} harus salah satu dari: {pilihan}.") from None
        raise HTTPException(status_code=400, detail=(
            f"{entry['label']} harus bulan {entry.get('min', 1)} sampai {entry.get('max', 12)} "
            f"(1 = Januari, 12 = Desember).")) from None


async def _write_profile_layers(entity_id: str, profile: Dict[str, Any], actor_name: str) -> None:
    """KP-T1 — tulis lapisan PT registry hanya bila nilainya berbeda dari nilai efektif grup."""
    from services import config_resolver
    for name, value in profile.items():
        key = PROFILE_INPUT_KEYS[name]
        if value == await config_resolver.value_of(key, {}):
            continue
        await config_resolver.set_value(key, value, scope_type="entity", scope_id=entity_id, actor=actor_name,
                                        reason="Ditetapkan saat PT dibuat")


async def provision_entity(payload: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
    data = {k: v for k, v in (payload or {}).items() if v is not None}
    # KP-T1 — tahun buku & mata uang bukan isian master PT: diperiksa dulu (400 sebelum PT lahir), ditulis ke registry.
    profile = {name: _profile_value_or_400(name, data.pop(name)) for name in list(PROFILE_INPUT_KEYS) if name in data}
    data.setdefault("doc_prefix", "")   # dorong ke jalur validasi/normalisasi prefix
    clean = await validate_entity_input(data)

    # KP-T2 (KP-24) — urutan: validasi → bagan akun bersama → simpan PT → langkah penyiapan yang bisa diulang.
    # Bagan akun bersama tidak menulis apa pun atas nama PT, jadi bila gagal PT belum lahir (dulu PT tersimpan lebih
    # dulu lalu tertinggal tanpa penanda lapisan dan tanpa cara mengulang).
    try:
        coa_added = await gl_service.seed_default_coa()   # idempotent — semua PT memakai bagan akun yang sama by-code
    except Exception as exc:  # noqa: BLE001 — galat apa pun di sini = PT tidak dibuat
        print(f"[provision] bagan akun bersama gagal disiapkan, PT tidak dibuat: {exc}")
        raise HTTPException(status_code=500, detail=COA_FAILED_MESSAGE) from None

    entity: Dict[str, Any] = dict(ENTITY_DEFAULTS)
    entity.update(data)
    entity.update(clean)
    from services.wilayah_service import apply_location
    apply_location(entity)   # lokasi badan usaha tervalidasi (2026-09)
    entity.update({
        "id": new_id("ent"),
        "status": lifecycle.STATUS_ACTIVE,
        "created_by": actor_name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "provisioning": {"coa": True, "config_layer": False, "group_partners": False, "at": now_iso()},
    })
    await db.business_entities.insert_one(entity)
    invalidate_entity_code(entity["id"])   # E1.4
    # KP-T2 — PT baru langsung bisa dipilih sebagai PT aktif (langkah "Lengkapi PT"): cache status PT (20 detik) dibuang,
    # kalau tidak permintaan ber-`X-Entity-Id` PT baru ditolak 403 "tidak ada" sampai cache kedaluwarsa.
    lifecycle.invalidate_status_cache()

    steps = await run_provisioning_steps(entity["id"], actor_name)
    entity["provisioning"] = steps["provisioning"]

    await _write_profile_layers(entity["id"], profile, actor_name)

    entity.pop("_id", None)
    prefix = entity.get("doc_prefix", "")
    return {
        "entity": entity,
        "provisioning": {
            "doc_prefix": prefix,
            "number_preview": f"{prefix}/SO-00001",
            "is_pkp": entity.get("default_tax_mode") == "ppn",
            "coa_accounts_added": coa_added,
            "coa_shared": True,
            "config_override_created": bool(steps["provisioning"].get("config_layer")),
            "group_partner_suppliers": steps.get("group_partner_suppliers") or {},
            "steps": steps["provisioning"],   # KP-T2 — langkah penyiapan yang berhasil
            "errors": steps["errors"],
        },
    }


# ─── KP-T2 (KP-24) — langkah penyiapan PT yang masing-masing aman diulang ─────────────────────────────────────────
COA_FAILED_MESSAGE = "Bagan akun bersama gagal disiapkan, jadi PT belum dibuat. Coba simpan lagi."
PROVISIONING_STEPS = ("coa", "config_layer", "group_partners")
STEP_LABEL = {"coa": "Bagan akun bersama", "config_layer": "Lapisan pengaturan PT",
              "group_partners": "Pemasok antar-PT (entitas grup)"}


async def _step_coa(entity_id: str, actor_name: str) -> Dict[str, Any]:
    return {"accounts_added": await gl_service.seed_default_coa()}


async def _step_config_layer(entity_id: str, actor_name: str) -> Dict[str, Any]:
    """Penanda lapisan pengaturan per PT (efektif via `get_effective_settings`); upsert → tetap satu dokumen."""
    await db.system_settings.update_one(
        {"scope": entity_id},
        {"$setOnInsert": {"scope": entity_id, "created_at": now_iso()}, "$set": {"updated_at": now_iso()}},
        upsert=True,
    )
    return {}


async def _step_group_partners(entity_id: str, actor_name: str) -> Dict[str, Any]:
    # FASE E-7 (E7.7) — badan usaha baru langsung SALING TERLIHAT sebagai pemasok bertipe "Entitas grup". Tanpa ini,
    # badan usaha yang lahir sesudah fase E-7 tidak punya jangkar pemasoknya dan pagar PO/SO hanya bisa mengenalinya
    # lewat pencocokan nama/NPWP (lapis kedua) — cukup, tetapi layarnya jadi kosong. Idempotent.
    from services import group_partner_service as _grp
    return {"suppliers": await _grp.sync_group_entity_suppliers(actor_name=actor_name)}


_STEP_FUNCS = {"coa": _step_coa, "config_layer": _step_config_layer, "group_partners": _step_group_partners}


async def run_provisioning_steps(entity_id: str, actor_name: str) -> Dict[str, Any]:
    """Jalankan tiga langkah penyiapan PT (bagan akun, penanda lapisan, pemasok antar-PT); aman diulang.

    Langkah yang berhasil ditandai `true` di `business_entities.provisioning` (yang sudah pernah berhasil tidak dicabut
    oleh kegagalan berikutnya). Kegagalan satu langkah tidak membatalkan PT dan tidak menghentikan langkah lain; ia
    dilaporkan di `errors`. → `{provisioning, errors, group_partner_suppliers}`.
    """
    cur = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "provisioning": 1}) or {}
    state = {k: bool((cur.get("provisioning") or {}).get(k)) for k in PROVISIONING_STEPS}
    errors: Dict[str, str] = {}
    extra: Dict[str, Any] = {}
    for step in PROVISIONING_STEPS:
        try:
            extra[step] = await _STEP_FUNCS[step](entity_id, actor_name)
            state[step] = True
        except Exception as exc:  # noqa: BLE001 — satu langkah gagal tidak membatalkan PT; dilaporkan
            print(f"[provision] langkah {step} untuk {entity_id} gagal: {exc}")
            errors[step] = f"{STEP_LABEL[step]} gagal disiapkan. Tekan Ulangi penyiapan untuk mencoba lagi."
    provisioning = {**state, "at": now_iso()}
    await db.business_entities.update_one({"id": entity_id}, {"$set": {"provisioning": provisioning}})
    return {"provisioning": provisioning, "errors": errors,
            "group_partner_suppliers": (extra.get("group_partners") or {}).get("suppliers") or {}}
