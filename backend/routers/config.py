"""FASE G-0 — Router Pusat Pengaturan (Config Center).

Satu pintu API untuk seluruh konfigurasi sistem:
  GET  /api/config/registry        — katalog setting + grup (sumber UI generik)
  GET  /api/config/effective       — nilai efektif per grup / hasil pencarian
  GET  /api/config/explain         — "kenapa nilainya begini?" (jejak lapisan)
  POST /api/config/simulate        — "coba dulu" sebelum menyimpan
  PUT  /api/config/values          — simpan (append-only + proyeksi ke mesin lama)
  POST /api/config/values/cancel-scheduled — KF-T3: batalkan perubahan berjadwal yang belum berlaku
  GET  /api/config/history         — riwayat siapa-ubah-apa-kapan-kenapa
  GET  /api/config/layers          — KF-T5: pelanggan/barang yang punya aturan khusus untuk satu kunci
  GET  /api/config/health          — kesehatan wiring (tidak ada tombol palsu)
  POST /api/config/impact-preview  — DAFTAR DAMPAK koreksi harga master
  POST /api/config/impact-apply    — terapkan HANYA ke dokumen yang dicentang

KF-T1 — wewenang: UBAH = Admin atau izin `entry.permission` (`_may_edit`); BACA = Admin, `settings.view`, atau yang
boleh mengubah kunci itu (`_may_read`). Tanpa satu pun kunci terbaca → 403 (B1); kunci/kelompok di luar → 403 (B2).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

import config_registry as registry
from dependencies import audit, current_user, permission_matrix, require_permission
from schemas_config import (
    ConfigBulkValuesIn, ConfigCancelScheduledIn, ConfigSimulateIn, ConfigValueIn, ImpactApplyIn, ImpactPreviewIn,
)
from services import config_health, config_simulator
from services import config_resolver as resolver
from services import config_scoped_rules as aturan_khusus   # KF-T5

router = APIRouter(prefix="/api/config", tags=["config"])


def _ctx(model: Any) -> Dict[str, Any]:
    return model.model_dump() if model else {}


async def _allowed(user: Dict[str, Any]) -> Dict[str, List[str]]:
    """Izin efektif user saat ini (matriks bisa di-override lewat permission_settings)."""
    matrix = await permission_matrix()
    return matrix.get(user.get("role") or "", {}) or {}


def _may(perms: Dict[str, List[str]], module: str, action: str) -> bool:
    actions = perms.get(module) or []
    return action in actions or "*" in actions


def _may_edit(entry: Dict[str, Any], user: Dict[str, Any], perms: Dict[str, List[str]]) -> bool:
    """Apakah user BERWENANG mengubah setting ini (izin saja, tanpa melihat status).

    KF-T1 (K-47) — satu aturan: Admin selalu boleh; selain itu HANYA izin `entry["permission"]` di matriks peran
    (mis. `settings.manage`, `inventory.configure`, `hr.manage_payroll`). Tidak ada jalur nama peran (`roles`) maupun
    `owner_role` — wewenang terlihat dan bisa dicabut di layar Peran & Hak Akses.
    """
    if (user.get("role") or "") == "admin":
        return True
    module, action = (entry.get("permission") or ["settings", "manage"])[:2]
    return _may(perms, module, action)


async def require_setting_edit(request: Request, key: str) -> Dict[str, Any]:
    """PR-T2 — layar lama yang mengubah kunci Pusat Pengaturan (mis. `PUT /lots/settings`) memakai pemeriksa yang SAMA
    dengan `PUT /api/config/values` (`_may_edit`), supaya kedua layar selalu sepakat siapa yang boleh mengubah."""
    user = await current_user(request)
    if not _may_edit(registry.require(key), user, await _allowed(user)):
        raise HTTPException(status_code=403, detail=(
            "Anda belum punya akses untuk mengubah pengaturan ini. Minta Admin menambahkan akses 'Pengaturan'."))
    return user


def _may_read(entry: Optional[Dict[str, Any]], user: Dict[str, Any], perms: Dict[str, List[str]]) -> bool:
    """KF-T1 — boleh MEMBACA sebuah setting: Admin, pemegang `settings.view`, atau yang boleh mengubahnya.

    Bentuk umum batas baca MD (keputusan pemilik K-11, 26 Okt): MD tetap membaca tepat kunci berizin `rnd.manage`."""
    if not entry:
        return False
    if (user.get("role") or "") == "admin" or _may(perms, "settings", "view"):
        return True
    return _may_edit(entry, user, perms)


def _module_label(resource: str) -> str:
    from access_modules import MODULE_CATALOG
    for m in MODULE_CATALOG:
        if resource in (m.get("resources") or []):
            return m.get("label", resource)
    return resource


ADMIN_MODULE = "Pengaturan, Pengguna & Hak Akses"


def _perm_error(entry: Dict[str, Any]) -> str:
    module = (entry.get("permission") or ["settings", "manage"])[0]
    return (f"Anda belum punya akses untuk mengubah pengaturan “{entry['label']}”. Minta Admin menambahkan akses "
            f"'{_module_label(module)}'.")


def _deny_all() -> HTTPException:
    """B1 — tidak ada satu pun pengaturan yang boleh dibaca."""
    return HTTPException(status_code=403, detail=(
        f"Anda belum punya akses untuk melihat pengaturan. Minta Admin menambahkan akses '{ADMIN_MODULE}'."))


def _deny_one(label: str, resource: str = "settings") -> HTTPException:
    """B2 — kunci/kelompok di luar yang terbaca."""
    return HTTPException(status_code=403, detail=(
        f"Anda belum punya akses untuk melihat pengaturan “{label}”. Minta Admin menambahkan akses "
        f"'{_module_label(resource)}'."))


def _deny_entry(entry: Dict[str, Any]) -> HTTPException:
    return _deny_one(entry.get("label") or entry.get("key", ""), (entry.get("permission") or ["settings"])[0])


def _deny_group(group: str) -> HTTPException:
    g = next((x for x in registry.GROUPS if x["id"] == group), None)
    items = registry.by_group(group)
    return _deny_one((g or {}).get("label", group), (items[0].get("permission") or ["settings"])[0] if items else "settings")


def _can_edit(entry: Dict[str, Any], user: Dict[str, Any], perms: Dict[str, List[str]]) -> bool:
    """Boleh-tidaknya tombol Simpan aktif di UI.

    Yang terlihat bisa diklik = yang benar-benar diizinkan server. Setting
    berstatus `not_used` sengaja tidak bisa diubah siapa pun; alasannya
    ditampilkan pada kartunya sendiri.
    """
    if entry.get("status") != "active":
        return False
    return _may_edit(entry, user, perms)


def _full_reader(user: Dict[str, Any], perms: Dict[str, List[str]]) -> bool:
    return (user.get("role") or "") == "admin" or _may(perms, "settings", "view")


def _readable_groups(user: Dict[str, Any], perms: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """Kelompok + hitungan yang TERBACA user (hitungan ikut saringan, bukan jumlah katalog)."""
    if _full_reader(user, perms):
        return registry.groups()
    out = []
    for g in registry.groups():
        items = [e for e in registry.by_group(g["id"]) if _may_read(e, user, perms)]
        if items:
            out.append({**g, "count": len(items),
                        "active_count": len([e for e in items if e.get("status") == "active"])})
    # Kelompok dengan kunci terbaca terbanyak di urutan pertama → layar membukanya lebih dulu (mis. R&D untuk MD).
    out.sort(key=lambda g: -g["count"])
    return out


def _assert_any_readable(user: Dict[str, Any], perms: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    groups = _readable_groups(user, perms)
    if not groups:
        raise _deny_all()
    return groups


async def _global_write_allowed(request: Request) -> bool:
    from entity_scope import entity_ctx
    return (await entity_ctx(request)).is_cross_entity


async def _assert_scope_write(request: Request, entry: Dict[str, Any], scope_type: str, scope_id: str) -> None:
    """IX-06/IX-07 — lapisan tulis wajib dalam penugasan; nilai grup (global) yang punya lapisan
    entitas hanya boleh diubah peran lintas badan usaha.

    KF-T5 — lapisan pelanggan/barang: sasarannya harus ada (404) dan pelanggan harus milik PT dalam cakupan pelaku
    (403); lapisan pemasok/dokumen belum punya layar (400)."""
    from entity_scope import entity_ctx, resolve_requested_entity
    ctx = await entity_ctx(request)
    if scope_type == "entity":
        resolve_requested_entity(ctx, scope_id)
    elif scope_type == "global" and "entity" in (entry.get("scopes") or []) and not ctx.is_cross_entity:
        raise HTTPException(status_code=403, detail=(
            f"Nilai grup '{entry['label']}' hanya dapat diubah peran lintas badan usaha. "
            "Pilih 'Badan usaha' untuk mengubah nilai khusus PT Anda."))
    elif scope_type in aturan_khusus.LAPISAN_KHUSUS + aturan_khusus.BELUM_TERSEDIA:   # KF-T5
        await aturan_khusus.pastikan_sasaran(ctx, scope_type, scope_id)


@router.get("/registry")
async def read_registry(request: Request, group: str = "", q: str = "") -> Dict[str, Any]:
    """Katalog setting (label awam, penjelasan, dampak, tipe, batas, scope, consumer)."""
    user = await current_user(request)
    perms = await _allowed(user)
    groups = _assert_any_readable(user, perms)          # KF-T1 — B1 bila tidak satu pun terbaca
    if group and not q and not any(_may_read(e, user, perms) for e in registry.by_group(group)):
        raise _deny_group(group)
    entries = registry.search(q) if q else (
        registry.by_group(group) if group else registry.all_entries())
    entries = [{**e, "can_edit": _can_edit(e, user, perms)} for e in entries if _may_read(e, user, perms)]
    full = _full_reader(user, perms)
    return {"groups": groups, "entries": entries, "total": len(entries),
            "scope_levels": registry.SCOPE_LEVELS,
            "simulators": [x for x in config_simulator.catalog() if _sim_readable(x, user, perms)],
            # `caps` membuat UI jujur: tab/tombol yang tidak diizinkan server
            # tidak ditampilkan sama sekali (bukan ditampilkan lalu ditolak 403).
            "caps": {
                "settings_manage": _may(perms, "settings", "manage"),
                "settings_view": full,
                "impact_apply": _may(perms, "product", "update"),
                "editable_count": sum(1 for e in entries if e["can_edit"]),
                # IX-06 — UI hanya menawarkan lapisan "Global" bila server mengizinkannya
                "global_write": await _global_write_allowed(request),
                # KF-T1 — kelompok yang terbaca bila pelaku tidak memegang `settings.view`; kosong = semua.
                "read_scope": "" if full else ", ".join(g["label"] for g in groups),
            }}


@router.get("/effective")
async def read_effective(request: Request, group: str = "", q: str = "",
                         entity_id: str = "", customer_id: str = "", supplier_id: str = "",
                         product_id: str = "", document_id: str = "", scope: str = "") -> Dict[str, Any]:
    """Nilai efektif + lapisan asal untuk satu grup (atau hasil pencarian).

    KF-T5 — `scope` (`customer` · `product`): hanya kunci yang bisa dibedakan per pelanggan/barang, tiap butir ditambah
    `layer_value` (nilai milik `customer_id`/`product_id` itu, atau `null`) dan `inherited_value` (nilai PT/grup)."""
    user = await current_user(request)
    perms = await _allowed(user)
    groups = _assert_any_readable(user, perms)
    if group and not q and not any(_may_read(e, user, perms) for e in registry.by_group(group)):
        raise _deny_group(group)
    if scope:   # KF-T5 — pelanggan/barang harus ada; pelanggan dalam cakupan PT pembaca; aturan PT = PT pelanggan
        from entity_scope import entity_ctx
        aturan_khusus.periksa_lapisan(scope)
        sid = customer_id if scope == "customer" else product_id
        if sid:
            doc = await aturan_khusus.pastikan_sasaran(await entity_ctx(request), scope, sid)
            if scope == "customer" and not entity_id:
                entity_id = doc.get("entity_id") or ""
    await resolver.apply_due_values()      # aktifkan perubahan berjadwal yang jatuh tempo
    ctx = {"entity_id": entity_id, "customer_id": customer_id, "supplier_id": supplier_id,
           "product_id": product_id, "document_id": document_id}
    items = await resolver.resolve_group(group or None, ctx, term=q)
    items = [it for it in items if _may_read(registry.get(it["key"]), user, perms)]
    for it in items:
        it["can_edit"] = _can_edit(registry.get(it["key"]) or it, user, perms)
    if scope:   # KF-T5
        items = await aturan_khusus.tambah_nilai_lapisan(items, scope, ctx)
    return {"groups": groups, "context": ctx, "items": items, "total": len(items)}


@router.get("/explain")
async def explain(request: Request, key: str, entity_id: str = "", customer_id: str = "",
                  supplier_id: str = "", product_id: str = "",
                  document_id: str = "") -> Dict[str, Any]:
    """Jejak lapisan: default kode → global → entitas → pelanggan → … dan mana yang menang."""
    user = await current_user(request)
    entry = registry.get(key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' tidak ada di registry")
    if not _may_read(entry, user, await _allowed(user)):
        raise _deny_entry(entry)
    ctx = {"entity_id": entity_id, "customer_id": customer_id, "supplier_id": supplier_id,
           "product_id": product_id, "document_id": document_id}
    res = await resolver.resolve(key, ctx)
    return {"entry": entry, "context": ctx, **res,
            "layer_order": resolver.LAYER_ORDER,
            "wiring": config_health.check_entry(entry)}


@router.post("/simulate")
async def simulate(payload: ConfigSimulateIn, request: Request) -> Dict[str, Any]:
    """"Coba dulu": jalankan aturan memakai nilai efektif (+ nilai hipotetis) tanpa menyimpan."""
    user = await current_user(request)
    perms = await _allowed(user)
    sim_id = payload.simulator
    if not sim_id:
        entry = registry.get(payload.key)
        if not entry:
            raise HTTPException(status_code=404, detail="Sebutkan `simulator` atau `key` yang sah")
        sim_id = entry.get("simulate") or ""
    if not sim_id:
        raise HTTPException(status_code=400,
                            detail="Setting ini belum punya simulator — lihat 'Kenapa nilainya begini?'")
    try:
        sim = config_simulator.get(sim_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    for k in sim["needs"]:
        if not _may_read(registry.get(k), user, perms):
            raise _deny_entry(registry.get(k) or {"key": k, "label": k})
    ctx = _ctx(payload.ctx)
    values: Dict[str, Any] = {}
    trail: List[Dict[str, Any]] = []
    for key in sim["needs"]:
        if key in payload.overrides:
            res = await resolver.resolve(key, ctx, hypothetical=payload.overrides[key])
        else:
            res = await resolver.resolve(key, ctx)
        values[key] = res["value"]
        e = registry.get(key)
        trail.append({"key": key, "label": (e or {}).get("label", key), "value": res["value"],
                      "source_layer": res["source_layer"], "source_label": res["source_label"],
                      "hypothetical": key in payload.overrides})
    out = config_simulator.run(sim_id, values, payload.sample)
    return {**out, "resolved": trail, "context": ctx}


@router.put("/values")
async def write_values(payload: ConfigBulkValuesIn, request: Request) -> Dict[str, Any]:
    """Simpan perubahan (bisa beberapa sekaligus). Append-only + langsung aktif di mesin."""
    actor = await current_user(request)
    perms = await _allowed(actor)
    if not payload.items:
        raise HTTPException(status_code=400, detail="Tidak ada perubahan yang dikirim")
    saved: List[Dict[str, Any]] = []
    for item in payload.items:
        entry = registry.get(item.key)
        if not entry:
            raise HTTPException(status_code=404,
                                detail=f"Setting '{item.key}' tidak ada di registry")
        # Status `not_used` sengaja TIDAK ditangani di sini: resolver yang menolak
        # dengan pesan berisi ALASAN kenapa setting itu tidak dipakai (lebih
        # berguna bagi user daripada sekadar "tidak berwenang").
        if not _may_edit(entry, actor, perms):
            raise HTTPException(status_code=403, detail=_perm_error(entry))
        await _assert_scope_write(request, entry, item.scope_type, item.scope_id)
        try:
            row = await resolver.set_value(
                item.key, item.value, scope_type=item.scope_type, scope_id=item.scope_id,
                actor=actor.get("name", ""), actor_id=actor.get("id", ""),
                reason=item.reason, effective_from=item.effective_from, ctx=_ctx(item.ctx))
        except resolver.ConfigWriteError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await audit(actor.get("name", ""), "config_value_changed", "config_values", row["id"],
                    {"key": item.key, "scope": f"{item.scope_type}:{item.scope_id or '-'}",
                     "from": row["prev_value"], "to": row["value"],
                     "effective_from": row["effective_from"]}, reason=item.reason)
        saved.append(row)
    from services import location_scope, product_exclusivity
    location_scope.invalidate()
    product_exclusivity.invalidate_hidden_stages()
    return {"saved": saved, "count": len(saved)}


@router.post("/values/reset")
async def reset_value(payload: ConfigValueIn, request: Request) -> Dict[str, Any]:
    """Kembalikan sebuah setting ke nilai default sistem (tetap tercatat sebagai perubahan)."""
    actor = await current_user(request)
    perms = await _allowed(actor)
    entry = registry.get(payload.key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Setting '{payload.key}' tidak ada di registry")
    if not _may_edit(entry, actor, perms):
        raise HTTPException(status_code=403, detail=_perm_error(entry))
    await _assert_scope_write(request, entry, payload.scope_type, payload.scope_id)
    try:
        row = await resolver.set_value(
            payload.key, entry["default"], scope_type=payload.scope_type,
            scope_id=payload.scope_id, actor=actor.get("name", ""), actor_id=actor.get("id", ""),
            reason=payload.reason or "Kembalikan ke default sistem")
    except resolver.ConfigWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "config_value_reset", "config_values", row["id"],
                {"key": payload.key, "to": row["value"]}, reason=row["reason"])
    return row


@router.post("/values/clear")
async def clear_value_layer(payload: ConfigValueIn, request: Request) -> Dict[str, Any]:
    """FASE E-4 (E4.6) — cabut nilai pada satu lapisan → kembali mewarisi lapisan di atasnya.

    Dipakai tombol "Kembalikan ke global" di Pusat Pengaturan. Berbeda dari
    `/values/reset` yang menulis nilai bawaan KODE pada lapisan ini.
    """
    actor = await current_user(request)
    perms = await _allowed(actor)
    entry = registry.get(payload.key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Setting '{payload.key}' tidak ada di registry")
    if not _may_edit(entry, actor, perms):
        raise HTTPException(status_code=403, detail=_perm_error(entry))
    await _assert_scope_write(request, entry, payload.scope_type, payload.scope_id)
    try:
        row = await resolver.clear_layer(
            payload.key, scope_type=payload.scope_type, scope_id=payload.scope_id,
            actor=actor.get("name", ""), actor_id=actor.get("id", ""),
            reason=payload.reason or "")
    except resolver.ConfigWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "config_value_cleared", "config_values", row["id"],
                {"key": payload.key, "scope": f"{payload.scope_type}:{payload.scope_id or '-'}",
                 "from": row["prev_value"], "now": row.get("value_now"),
                 "now_source": row.get("source_label_now")}, reason=row["reason"])
    return row


@router.post("/values/cancel-scheduled")
async def cancel_scheduled_value(payload: ConfigCancelScheduledIn, request: Request) -> Dict[str, Any]:
    """KF-T3 (KF-09) — batalkan satu perubahan berjadwal yang belum berlaku. Wewenang = pengubah kunci itu
    (`_may_edit`) pada lapisan barisnya (`_assert_scope_write`). Baris tetap tersimpan (append-only) dengan penanda
    `cancelled_at`; nilai yang berlaku sekarang tidak berubah."""
    actor = await current_user(request)
    perms = await _allowed(actor)
    try:
        row = await resolver.scheduled_row(payload.id)
    except resolver.ScheduleError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    entry = registry.require(row["key"])
    if not _may_edit(entry, actor, perms):
        raise HTTPException(status_code=403, detail=_perm_error(entry))
    await _assert_scope_write(request, entry, row.get("scope_type") or "global", row.get("scope_id") or "")
    try:
        out = await resolver.cancel_scheduled(payload.id, actor=actor.get("name", ""), actor_id=actor.get("id", ""),
                                              reason=payload.reason)
    except resolver.ScheduleError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "config_schedule_cancelled", "config_values", out["id"],
                {"key": out["key"], "scope": f"{out.get('scope_type')}:{out.get('scope_id') or '-'}",
                 "value": out.get("value"), "effective_from": out.get("effective_from")},
                reason=out.get("cancel_reason", ""))
    return out


@router.get("/history")
async def read_history(request: Request, key: str = "", scope_type: str = "",
                       scope_id: str = "", limit: int = 100) -> Dict[str, Any]:
    """Riwayat perubahan konfigurasi (append-only, terbaru dulu)."""
    user = await current_user(request)
    perms = await _allowed(user)
    n = min(max(int(limit), 1), 500)
    if key:
        entry = registry.get(key)
        if not _may_read(entry, user, perms):
            raise _deny_entry(entry or {"key": key, "label": key})
    else:
        _assert_any_readable(user, perms)
    # KF-T1 — pembaca terbatas hanya melihat riwayat setting yang boleh dibacanya.
    full = _full_reader(user, perms)
    rows = await resolver.history(key, scope_type, scope_id, n if full else 500)
    if not full:
        rows = [r for r in rows if _may_read(registry.get(r["key"]), user, perms)][:n]
    rows = await aturan_khusus.beri_nama(rows)   # KF-T5 — cakupan pelanggan/barang tampil bernama, bukan id
    return {"rows": rows, "total": len(rows)}


# KF-T5 — daftar pelanggan/barang yang punya aturan khusus untuk satu kunci (dibaca kartu Pusat Pengaturan).
@router.get("/layers")
async def read_layers(request: Request, key: str = "", scope_type: str = "") -> Dict[str, Any]:
    """Satu baris per pelanggan/barang yang punya nilai sendiri: `{"rows": [{scope_id, scope_label, value, changed_by,
    changed_at, reason}], "total"}`; terbaru dulu, paling banyak 200 baris. Izin baca = `_may_read` kunci itu."""
    from entity_scope import entity_ctx
    user = await current_user(request)
    entry = registry.get(key)
    if not entry:
        raise HTTPException(status_code=404, detail="Pengaturan tidak ditemukan.")
    if not _may_read(entry, user, await _allowed(user)):
        raise _deny_entry(entry)
    aturan_khusus.periksa_lapisan(scope_type)
    ctx = await entity_ctx(request)
    return await aturan_khusus.daftar_lapisan(key, scope_type, ctx.allowed_entity_ids)


@router.get("/health")
async def read_health(request: Request) -> Dict[str, Any]:
    """Kesehatan wiring: setiap setting aktif WAJIB punya kode pembaca yang nyata."""
    await require_permission(request, "settings", "view")
    rep = config_health.report()
    pending = await resolver.apply_due_values()
    return {**rep, "scheduled_applied": pending}


@router.post("/impact-preview")
async def impact_preview(payload: ImpactPreviewIn, request: Request) -> Dict[str, Any]:
    """DAFTAR DAMPAK — dokumen terbuka mana saja yang akan berubah bila harga master dikoreksi."""
    await require_permission(request, "product", "view")
    from services import config_impact_service as impact
    try:
        return await impact.preview(payload.product_id, payload.new_price,
                                    payload.current_doc_id, payload.entity_id)
    except impact.ImpactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/impact-apply")
async def impact_apply(payload: ImpactApplyIn, request: Request) -> Dict[str, Any]:
    """Terapkan koreksi harga master HANYA ke dokumen yang dicentang (INV-CFG-07)."""
    actor = await require_permission(request, "product", "update")
    from services import config_impact_service as impact
    try:
        return await impact.apply(payload.product_id, payload.new_price, payload.doc_ids,
                                  reason=payload.reason, actor=actor.get("name", ""),
                                  entity_id=payload.entity_id,
                                  update_master=payload.update_master)
    except impact.ImpactError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/simulators")
async def list_simulators(request: Request) -> Dict[str, Any]:
    """Daftar simulator yang tersedia + input yang diminta (KF-T1: hanya yang semua masukannya terbaca)."""
    user = await current_user(request)
    perms = await _allowed(user)
    _assert_any_readable(user, perms)
    return {"simulators": [x for x in config_simulator.catalog() if _sim_readable(x, user, perms)]}


def _sim_readable(sim: Dict[str, Any], user: Dict[str, Any], perms: Dict[str, List[str]]) -> bool:
    return all(_may_read(registry.get(k), user, perms) for k in (sim.get("needs") or []))
