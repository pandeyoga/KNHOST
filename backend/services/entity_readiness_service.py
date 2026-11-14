"""FASE E-1 (E1.9) — DAFTAR KESIAPAN BADAN USAHA.

Entitas baru sering “lahir setengah jadi”: sudah ada di daftar tetapi belum punya
pengguna, rekening, harga jual, atau kop surat — lalu orang bingung kenapa layar
kosong. Daftar ini menjawab “apa lagi yang kurang?” dengan **angka terhitung**
(bukan teks statis) dan setiap baris membawa `view` supaya UI bisa mengantar
pengguna ke layar penyelesaiannya (E-3 `EntityReadinessPanel`).

KP-T2 (KP-10, KP-24) — 16 butir berurutan seperti urutan mengisi: semua hal yang membuat transaksi pertama dan tutup
buku bisa berjalan (penyiapan awal, alamat, pajak, kode dokumen, pengguna, pengguna keuangan dari matriks izin, gudang,
rekening bank dan akun kas terpisah, pemetaan akun, periode hari ini, termin bawaan, harga, saldo awal, kop, penanda
tangan). Tiap baris mengantar ke layar yang benar (`view` + `tab` opsional); butir lama `bank_accounts` dipecah dan
`fiscal_year` dibuang (tahun buku selalu bernilai sejak KP-T1). Bentuk ringkasan tidak berubah.

Dipakai:
  GET /api/entities/{id}/readiness           → daftar lengkap
  GET /api/entities?with_readiness=true      → ringkasan (%) per baris daftar
  POST /api/entities, POST /api/entities/{id}/provisioning/retry → daftar lengkap PT itu
"""
import re
from typing import Any, Dict, List

from db import db
from services.entity_context_service import is_pkp


async def _usable_warehouses(entity_id: str) -> int:
    """Gudang yang boleh dipakai entitas.

    Sebelum FASE E-4 `warehouses` belum punya `sharing_mode`, jadi gudang tanpa
    field itu dianggap BERSAMA (perilaku hari ini) — bukan dianggap tidak ada,
    supaya angka kesiapan tidak berbohong.
    """
    return await db.warehouses.count_documents({
        "$and": [
            {"$or": [{"active": True}, {"active": {"$exists": False}}]},
            {"$or": [{"sharing_mode": {"$exists": False}},
                     {"sharing_mode": "shared"},
                     {"sharing_mode": "dedicated", "entity_ids": entity_id}]},
        ]})


# ─── KP-T2 — pembaca per butir (masing-masing memakai sumber angka yang sudah ada) ─────────────────────────────────
async def _provisioning_state(entity_id: str) -> Dict[str, bool]:
    """Penyiapan awal dari DATA (juga untuk PT lama tanpa field `provisioning`): bagan akun bersama + penanda lapisan."""
    coa = await db.gl_accounts.count_documents({"entity_id": {"$in": [None, ""]}})
    layer = await db.system_settings.count_documents({"scope": entity_id})
    return {"coa": coa > 0, "config_layer": layer > 0}


async def _finance_users(entity_id: str) -> int:
    """Pengguna aktif yang boleh bekerja di PT ini DAN perannya memegang `cash.create` menurut matriks izin (Z2)."""
    from dependencies import permission_matrix
    from role_registry import CROSS_ENTITY_ROLES
    matrix = await permission_matrix()
    holders = sorted(r for r, perms in matrix.items()
                     if any(a in ((perms or {}).get("cash") or []) for a in ("create", "*")))
    if not holders:
        return 0
    where: List[Dict[str, Any]] = [{"home_entity_id": entity_id}, {"allowed_entity_ids": entity_id}]
    cross = sorted(set(holders) & set(CROSS_ENTITY_ROLES))   # sifat peran "lintas PT" (Peran & Hak Akses)
    if cross:
        where.append({"role": {"$in": cross}})
    return await db.users.count_documents({"status": "active", "role": {"$in": holders}, "$or": where})


async def _accounts_of(entity_id: str, account_type: str) -> int:
    """Rekening/akun kas MILIK PT (bukan `entity_id: "all"` tingkat grup), yang tidak dinonaktifkan."""
    return await db.bank_accounts.count_documents(
        {"entity_id": entity_id, "account_type": account_type, "is_active": {"$ne": False}})


async def _unsettled_mappings(entity_id: str) -> int:
    """Pemetaan akun WAJIB yang belum beres (status ≠ ok) — angka sama dengan layar Pemetaan Akun."""
    from services.gl_mapping_service import list_mappings
    rows = (await list_mappings(entity_id)).get("rows") or []
    return sum(1 for r in rows if r.get("required") and r.get("status") != "ok")


async def _period_today(entity_id: str) -> Dict[str, Any]:
    from services.closing_service import status_for_date
    from services.entity_lifecycle_service import today_wib
    return await status_for_date(today_wib(), entity_id)


async def _payment_term(entity_id: str) -> Dict[str, Any]:
    """Termin bawaan EFEKTIF untuk PT ini (lapisan PT Pusat Pengaturan) + barisnya di master termin PT."""
    from services.config_service import default_payment_term_code
    from services.entity_master_service import resolve_row
    code = str(await default_payment_term_code(entity_id) or "").strip()
    row = await resolve_row("payment-terms", code, entity_id) if code else None
    return {"code": code, "row": row}


#: KP-T9 — butir profil/akun menuju tab hub baru (`settings-pt-profile`, `settings-accounts`); `tab` lama ("entities",
#: "accounts") tetap dikirim untuk klien yang masih membuka layar Badan Usaha & Akses lewat id lamanya.
def _item(key: str, label: str, ready: bool, count: int, detail: str, how_to: str, view: str,
          tab: str = "") -> Dict[str, Any]:
    out = {"key": key, "label": label, "ready": bool(ready), "count": int(count), "detail": detail,
           "how_to": how_to, "view": view}
    if tab:
        out["tab"] = tab
    return out


async def readiness(entity_id: str, entity: Dict[str, Any]) -> Dict[str, Any]:
    ent = entity or {}
    pkp = is_pkp(ent)
    prov = await _provisioning_state(entity_id)
    addr_filled = sum(1 for k in ("address", "city", "province") if str(ent.get(k) or "").strip())
    tax_mode = str(ent.get("default_tax_mode") or "").strip()
    npwp = str(ent.get("npwp") or "").strip()
    prefix = str(ent.get("doc_prefix") or "").strip()
    prefix_ok = bool(re.fullmatch(r"[A-Z0-9]{2,10}", prefix))

    users = await db.users.count_documents({"home_entity_id": entity_id, "status": "active"})
    finance_users = await _finance_users(entity_id)
    warehouses = await _usable_warehouses(entity_id)
    banks = await _accounts_of(entity_id, "bank")
    cashes = await _accounts_of(entity_id, "cash")
    unsettled = await _unsettled_mappings(entity_id)
    period = await _period_today(entity_id)
    term = await _payment_term(entity_id)
    prices = await db.entity_prices.count_documents({"entity_id": entity_id})
    global_prices = await db.products.count_documents({"price": {"$gt": 0}})
    opening = await db.journal_entries.count_documents(
        {"entity_id": entity_id, "source": {"$regex": "opening"}})
    brand = await db.document_branding.find_one(
        {"entity_id": entity_id}, {"_id": 0, "logo_b64": 1, "header_image_b64": 1, "signatures": 1}) or {}
    has_brand = bool(brand.get("logo_b64") or brand.get("header_image_b64") or ent.get("logo_url"))
    signers = [str(s.get("name")).strip() for s in (brand.get("signatures") or [])
               if isinstance(s, dict) and str(s.get("name") or "").strip()]

    term_name = (term["row"] or {}).get("name") or ""
    items: List[Dict[str, Any]] = [
        _item("provisioning", "Penyiapan awal", prov["coa"] and prov["config_layer"],
              int(prov["coa"]) + int(prov["config_layer"]),
              "Bagan akun bersama dan lapisan pengaturan PT sudah tersedia" if prov["coa"] and prov["config_layer"]
              else "Penyiapan awal PT belum tuntas",
              "Tekan Ulangi penyiapan.", ""),
        _item("address", "Alamat lengkap", addr_filled == 3, addr_filled,
              "Alamat, kota, dan provinsi sudah diisi" if addr_filled == 3
              else "Alamat, kota, atau provinsi masih kosong",
              "Lengkapi alamat di profil PT.", "settings-pt-profile", "entities"),
        _item("tax", "Status pajak & NPWP", bool(tax_mode) and (bool(npwp) or not pkp), 1 if tax_mode else 0,
              ("PKP — NPWP terisi" if pkp and npwp
               else "PKP tetapi NPWP masih kosong" if pkp
               else "Non-PKP — tidak memungut PPN" if tax_mode
               else "Status pajak belum ditetapkan"),
              "Lengkapi NPWP di profil PT, atau pakai tombol Ubah status PKP.", "settings-pt-profile", "entities"),
        _item("doc_prefix", "Kode dokumen", prefix_ok, 1 if prefix_ok else 0,
              f"Nomor dokumen berawalan {prefix}/" if prefix_ok
              else "Kode dokumen belum diisi atau bukan 2–10 huruf besar/angka",
              "Atur kode dokumen di profil PT; kode terkunci setelah dokumen pertama terbit.",
              "settings-pt-profile", "entities"),
        _item("users", "Pengguna", users > 0, users,
              f"{users} akun aktif ber-PT utama di sini" if users
              else "Belum ada akun yang ber-PT utama di sini",
              "Buat akun di Pengaturan › Pengguna & Hak Akses › Akun dan pilih PT ini sebagai PT utama.",
              "settings-accounts", "accounts"),
        _item("finance_user", "Pengguna keuangan", finance_users > 0, finance_users,
              f"{finance_users} pengguna bisa mencatat kas untuk PT ini" if finance_users
              else "Belum ada pengguna yang bisa mencatat kas untuk PT ini",
              "Beri seorang pengguna peran yang punya akses Kas & Bank, dan tugaskan ke PT ini.",
              "settings-accounts", "accounts"),
        _item("warehouses", "Gudang yang boleh dipakai", warehouses > 0, warehouses,
              f"{warehouses} gudang tersedia" if warehouses else "Tidak ada gudang yang boleh dipakai PT ini",
              "Atur gudang bersama atau khusus di Master Gudang.", "md-warehouses"),
        _item("bank_account", "Rekening bank", banks > 0, banks,
              f"{banks} rekening bank aktif" if banks else "Belum ada rekening bank",
              "Tambah rekening di Keuangan › Rekening & Saldo.", "bank-accounts"),
        _item("cash_account", "Akun kas", cashes > 0, cashes,
              f"{cashes} akun kas aktif" if cashes else "Belum ada akun kas",
              "Tambah akun kas di Keuangan › Rekening & Saldo.", "bank-accounts"),
        _item("gl_mappings", "Pemetaan akun", unsettled == 0, unsettled,
              "Semua pemetaan akun wajib sudah beres" if unsettled == 0
              else f"{unsettled} pemetaan akun wajib belum beres",
              "Lengkapi di Pengaturan › Keuangan & Pajak › Pemetaan Akun.", "gl-account-mappings"),
        _item("period", "Periode buku hari ini terbuka", not period.get("closed"), 0 if period.get("closed") else 1,
              "Tanggal hari ini berada di periode yang sudah ditutup" if period.get("closed")
              else "Tanggal hari ini berada di periode yang masih terbuka",
              "Periksa Tutup Buku; transaksi bertanggal hari ini akan ditolak.", "closing"),
        _item("payment_term", "Termin pembayaran bawaan", bool(term["row"]), 1 if term["row"] else 0,
              (f"Termin bawaan “{term['code']}”" + (f" — {term_name}" if term_name else "")) if term["row"]
              else f"Termin bawaan “{term['code']}” tidak ada di daftar termin PT ini",
              "Pilih termin yang ada di Pusat Pengaturan, atau tambahkan terminnya.", "entity-masters"),
        _item("prices", "Harga jual", (prices > 0) or (global_prices > 0), prices,
              (f"{prices} harga khusus PT ini" if prices
               else (f"Belum ada harga khusus — memakai {global_prices} harga umum"
                     if global_prices else "Belum ada harga jual sama sekali")),
              "Atur harga khusus PT di Produk & Harga › Harga per PT, atau isi harga umum produk.",
              "pricelist"),
        _item("opening_balance", "Saldo awal", opening > 0, opening,
              f"{opening} jurnal saldo awal" if opening
              else "Belum ada jurnal saldo awal (stok/kas/piutang pembuka)",
              "Catat saldo awal lewat Keuangan › Jurnal & Buku Besar.", "general-ledger"),
        _item("branding", "Kop surat & logo", has_brand, 1 if has_brand else 0,
              "Kop surat sudah diatur" if has_brand else "Dokumen cetak masih memakai kop bawaan",
              "Atur di Pengaturan › Dokumen & Notifikasi › Template Dokumen.", "pdf-templates"),
        _item("signers", "Penanda tangan", bool(signers), len(signers),
              f"{len(signers)} penanda tangan: {', '.join(signers[:3])}" if signers
              else "Belum ada nama penanda tangan",
              "Isi di Pengaturan › Dokumen & Notifikasi › Template Dokumen.", "pdf-templates"),
    ]
    ready_count = sum(1 for i in items if i["ready"])
    return {
        "entity_id": entity_id,
        "items": items,
        "ready": ready_count,
        "total": len(items),
        "percent": round(ready_count * 100 / len(items)) if items else 0,
        "is_ready": ready_count == len(items),
    }


async def readiness_summary(entity_id: str, entity: Dict[str, Any]) -> Dict[str, Any]:
    full = await readiness(entity_id, entity)
    counts = {i["key"]: i.get("count", 0) for i in full["items"]}
    return {"percent": full["percent"], "ready": full["ready"], "total": full["total"],
            "missing": [i["label"] for i in full["items"] if not i["ready"]],
            # FASE E-3 — daftar badan usaha menampilkan "#gudang yang boleh dipakai"
            # tanpa harus memanggil endpoint kesiapan satu-satu per baris.
            "warehouse_count": counts.get("warehouses", 0)}
