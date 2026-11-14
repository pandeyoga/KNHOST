"""FASE E-8 (E8.1) — **REGISTRY PERAN**: satu sumber kebenaran untuk peran & peringkat.

KENAPA BERKAS INI ADA
=====================
Sampai FASE E-7 sistem hanya punya **4 peran** (`admin`/`manager`/`sales`/`warehouse`)
dan peringkatnya ditulis sebagai **angka ajaib yang disalin di dua tempat**
(`services/config_service.role_satisfies` dan `services/so_approvals.ROLE_RANK`),
sementara daftar peran yang boleh lintas badan usaha ditulis di tempat KETIGA
(`services/entity_context_service.CROSS_ENTITY_ROLES`), dan label peran untuk manusia
di tempat KEEMPAT (frontend). Menambah satu peran berarti mengubah empat berkas dan
berharap tidak ada yang terlewat — kelas cacat yang paling mahal untuk urusan wewenang.

Berkas ini menjadi SSOT-nya. Semua tempat lama sekarang **membaca dari sini**.

DUA PERAN BARU (keputusan pemilik 2026-08-10, mengikat)
-------------------------------------------------------
Orang yang mengurus keseluruhan pesanan penjualan dulu harus dijadikan `sales`
(tak bisa Konfirmasi SO) atau `manager` (ikut dapat kuasa tutup buku, payroll,
bayar tagihan supplier, hapus master). Keduanya salah. Maka:

* **`sales_admin` (Admin Sales)** — pemilik alur SO end-to-end: validasi → keputusan
  pemenuhan (stok sendiri · ambil dari PT lain · reorder ke supplier) → konfirmasi →
  dokumen → memproses retur. **TANPA** menyentuh uang masuk & faktur pajak.
* **`finance` (Kasir/Finance)** — sisi UANG MASUK & PAJAK KELUARAN: kwitansi AR,
  faktur pajak keluaran, keputusan selisih bayar, penerbitan denda, kas.

PERINGKAT (`rank`) — dipakai matriks persetujuan
-----------------------------------------------
`sales:1 · warehouse:1 · sales_admin:2 · finance:2 · manager:3 · admin:4`
Arti praktisnya: aturan persetujuan yang menuntut `manager` TIDAK bisa dipenuhi oleh
Admin Sales/Finance (peringkat 2 < 3). Itu memang tujuannya — mereka pelaksana, bukan
penyetuju nilai.

LINTAS BADAN USAHA
------------------
Hanya `admin` & `manager`. **`sales_admin` SENGAJA TIDAK lintas-entitas**
(keputusan pemilik E8.10b#1: Admin Sales berbasis PENUGASAN — boleh dikunci 1 badan
usaha atau diberi beberapa lewat `users.allowed_entity_ids`, mekanisme yang sudah ada
untuk peran non-lintas). `finance` mengikuti pola yang sama karena kas & pajak selalu
milik satu badan usaha (keputusan E7e).
"""
from typing import Any, Dict, List, Optional

# ─── REGISTRY ────────────────────────────────────────────────────────────────
# `home_view`/`home_nav_id` WAJIB sama dengan `frontend/src/config/navMeta.js`
# (ROLE_HOME_REGISTRY). POC E-8 memeriksa kesamaannya supaya tidak diam-diam bercabang.
ROLES: Dict[str, Dict[str, Any]] = {
    "admin": {
        "label": "Admin",
        "long_label": "Admin sistem",
        "rank": 4,
        "cross_entity": True,
        "home_view": "admin-home",
        "home_nav_id": "home",
        "scope_hint": "lintas badan usaha",
        "description": "Kendali penuh sistem, master data, hak akses & audit.",
        "order": 1,
    },
    "manager": {
        "label": "Manajer",
        "long_label": "Manajer",
        "rank": 3,
        "cross_entity": True,
        "home_view": "manager-home",
        "home_nav_id": "home",
        "scope_hint": "lintas badan usaha",
        "description": "Penyetuju nilai/kredit/harga, tutup buku, payroll, pembayaran supplier.",
        "order": 2,
    },
    "sales_admin": {
        "label": "Admin Sales",
        "long_label": "Admin Sales (alur pesanan)",
        "rank": 2,
        "cross_entity": False,
        # GELOMBANG 2: beranda = **Meja Admin Sales** (`sales-admin-desk`). Peran
        # pelaksana yang mendarat di DAFTAR harus menyaring sendiri untuk menemukan
        # apa yang perlu ditindak; meja kerja sudah menyusunnya jadi antrean.
        "home_view": "sales-admin-desk",
        "home_nav_id": "sales-admin-desk",
        "scope_hint": "1 badan usaha (bisa ditugaskan ke beberapa)",
        "description": (
            "Mengelola keseluruhan pesanan: validasi, keputusan pemenuhan "
            "(stok sendiri / ambil dari PT lain / reorder supplier), konfirmasi, "
            "dokumen, dan memproses retur. Tidak menyentuh uang masuk & faktur pajak."
        ),
        "order": 3,
        "new_in": "E-8",
    },
    "finance": {
        "label": "Finance",
        "long_label": "Kasir / Finance (uang masuk & pajak keluaran)",
        "rank": 2,
        "cross_entity": False,
        # GELOMBANG 2: beranda = **Meja Finance** (5 antrean uang masuk & pajak).
        "home_view": "finance-desk",
        "home_nav_id": "finance-desk",
        "scope_hint": "1 badan usaha (bisa ditugaskan ke beberapa)",
        "description": (
            "Mencatat uang masuk (kwitansi AR), menerbitkan faktur pajak keluaran, "
            "memutus selisih bayar, menerbitkan denda, dan mencatat kas."
        ),
        "order": 4,
        "new_in": "E-8",
    },
    "sales": {
        "label": "Sales",
        "long_label": "Sales (lapangan)",
        "rank": 1,
        "cross_entity": False,
        "home_view": "sales-home",
        "home_nav_id": "home",
        "scope_hint": "1 badan usaha",
        "description": (
            "Menjual: basis pelanggan sendiri, membuat pesanan, memantau perjalanan "
            "pesanannya, dan mengajukan retur."
        ),
        "order": 5,
    },
    "warehouse": {
        "label": "Gudang",
        "long_label": "Gudang (WMS)",
        "rank": 1,
        "cross_entity": False,
        "home_view": "operations",
        "home_nav_id": "wms-operations",
        "scope_hint": "1 badan usaha",
        "description": "Penerimaan, penyimpanan, pengambilan, kirim, dan hitung ulang stok.",
        "order": 6,
    },
    # FASE D (2026-08-20) — PERAN KE-7 (keputusan pemilik): desainer menjadi peran
    # ber-AKUN supaya alur "desainer mengunggah artwork-nya sendiri" nyata dan
    # rapor desainer terisi dari pekerjaan, bukan dari orang lain yang mewakilkan.
    # Peringkat 1 (pelaksana) — SENGAJA tidak bisa memenuhi tuntutan `manager`:
    # yang menilai karya adalah atasan, bukan pembuatnya (pola KPI Desainer PS-18).
    "designer": {
        "label": "Desainer",
        "long_label": "Desainer (MD Desain)",
        "rank": 1,
        "cross_entity": False,
        "home_view": "design-requests",
        "home_nav_id": "design-requests",
        "scope_hint": "1 badan usaha",
        "description": ("Mengerjakan permintaan desain yang ditugaskan kepadanya: "
                        "mulai mengerjakan, mengunggah artwork ke Galeri Desain, "
                        "lalu menyerahkannya untuk keputusan atasan."),
        "order": 7,
        "new_in": "D",
    },
    # FB-02 (2026-09-02) — PERAN KE-8: sopir/kurir armada sendiri. Ia yang berada di lapangan,
    # maka ia yang memotret muat/POD & mencatat posisi. Pengiriman DIBUAT gudang.
    "driver": {
        "label": "Sopir",
        "long_label": "Sopir / Kurir (Logistik)",
        "rank": 1,
        "cross_entity": False,
        "home_view": "logistics",
        "home_nav_id": "logistics",
        "scope_hint": "1 badan usaha",
        "description": ("Menjalankan pengiriman armada sendiri: foto muat, posisi di jalan, "
                        "bukti terima (POD) di tujuan."),
        "order": 8,
        "new_in": "FB2",
    },
    # Sesi #087 (permintaan pemilik 2026-09-03) — dua peran pelaksana baru dengan MEJA
    # KERJA-nya sendiri (pola Admin Sales/Finance): bekerja dari ANTREAN, bukan daftar.
    "md": {
        "label": "MD",
        "long_label": "MD / Merchandiser (produk, sample & desain)",
        "rank": 2,
        "cross_entity": False,
        "home_view": "md-desk",
        "home_nav_id": "md-desk",
        "scope_hint": "1 badan usaha (bisa ditugaskan ke beberapa)",
        "description": ("Mengurus pengembangan produk: permintaan desain, putaran sample/labdip, "
                        "spesifikasi, master produk & harga, dan pengajuan pembelian bahan."),
        "order": 9,
        "new_in": "R9",
    },
    "warehouse_admin": {
        "label": "Admin Gudang",
        "long_label": "Admin Gudang (kepala operasi gudang & logistik)",
        "rank": 2,
        "cross_entity": False,
        "home_view": "warehouse-admin-desk",
        "home_nav_id": "warehouse-admin-desk",
        "scope_hint": "1 badan usaha (bisa ditugaskan ke beberapa)",
        "description": ("Memimpin gudang: menugaskan SPK inspeksi, menyetujui opname & transfer, "
                        "memastikan SJ yang dispatch diangkut logistik, menutup pengiriman."),
        "order": 10,
        "new_in": "R9",
    },
    # REVISI SAMPEL (2026-09-17) — PERAN KE-11: Admin Sample. Pesanan sample (SOS-) dipisah
    # dari SO roll biasa; yang mengurusnya (setujui pembayaran sample berbayar, teruskan
    # ke gudang untuk dipotong) adalah meja ini — BUKAN Admin Sales.
    "sample_admin": {
        "label": "Admin Sample",
        "long_label": "Admin Sample (alur pesanan sample)",
        "rank": 2,
        "cross_entity": False,
        "home_view": "sample-admin-desk",
        "home_nav_id": "sample-admin-desk",
        "scope_hint": "1 badan usaha (bisa ditugaskan ke beberapa)",
        "description": ("Mengelola pesanan sample dari sales: menyetujui pembayaran sample berbayar, "
                        "meneruskan permintaan potong ke gudang, memantau sampai terkirim/diambil."),
        "order": 11,
        "new_in": "SMP",
    },
    # P05 IMP-16 (DEC-06) — dua peran mutu. Hak keduanya untuk sementara JUGA melekat ke MD.
    "md_quality": {
        "label": "MD Quality",
        "long_label": "MD Quality (warna & handfeel vs sample ACC)",
        "rank": 2,
        "cross_entity": False,
        "home_view": "inspections",
        "home_nav_id": "quality-hub",
        "scope_hint": "1 badan usaha (bisa ditugaskan ke beberapa)",
        "description": ("Memeriksa warna & handfeel penerimaan PO dan hasil makloon terhadap sample "
                        "yang di-ACC, lalu melepas atau menolak barang yang ditahan."),
        "order": 12,
        "new_in": "P05",
    },
    "qc": {
        "label": "QC",
        "long_label": "QC (cacat 4-point, grade & random check)",
        "rank": 1,
        "cross_entity": False,
        "home_view": "inspections",
        "home_nav_id": "quality-hub",
        "scope_hint": "1 badan usaha (bisa ditugaskan ke beberapa)",
        "description": ("Mengisi cacat 4-point & grade per roll, serta menjalankan random check "
                        "roll di stok (roll ditahan selama dicek)."),
        "order": 13,
        "new_in": "P05",
    },
}

#: Peringkat peran — SATU definisi (dulu disalin di config_service & so_approvals).
ROLE_RANK: Dict[Any, int] = {"": 0, None: 0, **{rid: r["rank"] for rid, r in ROLES.items()}}

#: Peran KUSTOM (dibuat admin dari layar "Peran & Hak Akses"; tersimpan di `custom_roles`).
CUSTOM_ROLE_IDS: set = set()

#: Nilai BAWAAN sistem "lintas badan usaha" per peran bawaan (sebelum pengaturan admin).
BUILTIN_CROSS_ENTITY: Dict[str, bool] = {rid: bool(r["cross_entity"]) for rid, r in ROLES.items()}


def register_custom_roles(rows: List[Dict[str, Any]]) -> None:
    """Muat ulang peran kustom ke registry (dipanggil saat start & setiap perubahan)."""
    from access_modules import nav_for_levels

    for rid in list(CUSTOM_ROLE_IDS):
        ROLES.pop(rid, None)
        ROLE_RANK.pop(rid, None)
    CUSTOM_ROLE_IDS.clear()
    for i, row in enumerate(rows):
        rid = row.get("id") or ""
        if not rid or rid in ROLES:
            continue
        base = ROLES.get(row.get("base_role") or "")
        home = base or {"home_view": "hr-my-profile", "home_nav_id": "hr-my-profile"}
        ROLES[rid] = {
            "label": row.get("label") or rid,
            "long_label": row.get("label") or rid,
            "rank": base["rank"] if base else 1,
            "cross_entity": False,
            "home_view": home["home_view"],
            "home_nav_id": home["home_nav_id"],
            "scope_hint": "1 badan usaha (bisa ditugaskan ke beberapa)",
            "description": row.get("description") or "Peran kustom.",
            "order": 100 + i,
            "custom": True,
            "base_role": row.get("base_role") or "",
            "nav": nav_for_levels(row.get("levels") or {}),
        }
        ROLE_RANK[rid] = ROLES[rid]["rank"]
        CUSTOM_ROLE_IDS.add(rid)

#: Peran yang boleh mengoperasikan SEMUA badan usaha (oversight lintas-PT). Himpunan ini DIUBAH DI TEMPAT
#: oleh `apply_cross_entity` (pengaturan admin) supaya semua modul yang mengimpornya ikut berubah.
CROSS_ENTITY_ROLES = {rid for rid, r in ROLES.items() if r["cross_entity"]}


def cross_entity_default(rid: str) -> bool:
    """Nilai bawaan tanpa pengaturan admin: peran bawaan → registry; peran kustom → peran acuannya."""
    if rid == "admin":
        return True
    if rid in BUILTIN_CROSS_ENTITY:
        return BUILTIN_CROSS_ENTITY[rid]
    return BUILTIN_CROSS_ENTITY.get((ROLES.get(rid) or {}).get("base_role") or "", False)


def apply_cross_entity(overrides: Optional[Dict[str, Any]]) -> None:
    """Keputusan owner 2026-10-21 — akses lintas badan usaha DAPAT DIKONFIGURASI per peran (bawaan & kustom).
    `overrides` = {peran: bool} dari `permission_settings.cross_entity`; tanpa nilai → `cross_entity_default`
    (peran kustom mengikuti nilai EFEKTIF peran acuannya). Admin selalu lintas badan usaha."""
    ov = {k: bool(v) for k, v in (overrides or {}).items() if v is not None}

    def eff(rid: str) -> bool:
        if rid == "admin":
            return True
        if rid in ov:
            return ov[rid]
        if rid in BUILTIN_CROSS_ENTITY:
            return BUILTIN_CROSS_ENTITY[rid]
        base = (ROLES.get(rid) or {}).get("base_role") or ""
        return eff(base) if base and base != rid and base in ROLES else False

    for rid in ROLES:
        ROLES[rid]["cross_entity"] = eff(rid)
    CROSS_ENTITY_ROLES.clear()
    CROSS_ENTITY_ROLES.update(rid for rid, r in ROLES.items() if r["cross_entity"])

# ─── PR-T4 — SIFAT PERAN: cakupan data · halaman awal · kategori kerja · alamat notifikasi ──────────────────────────
# Disimpan di `permission_settings.role_traits.<id peran>` (pola `cross_entity`/`hidden_views`) dan diterapkan ke
# `ROLES[rid]` oleh `apply_traits` (dipanggil `custom_role_service.sync_registry`). Kunci yang tidak disimpan =
# nilai TURUNAN: peran bawaan → `PRT4_BUILTIN_TRAITS`/registry (= perilaku sebelum PR-T4); peran kustom → nilai
# efektif peran dasarnya; tanpa peran dasar → "semua" / Profil Saya / tanpa kategori / tanpa alamat tambahan.
TRAIT_KEYS = ("data_scope", "home_view", "kategori_kerja", "notify_like")
DATA_SCOPES = ("milik_sendiri", "tim", "semua")   # urutan = makin luas (`02` §3.3 E3)
DATA_SCOPE_LABEL = {"milik_sendiri": "Milik sendiri", "tim": "Milik sendiri dan timnya",
                    "semua": "Semua di PT yang boleh dibuka"}
WORK_CATEGORIES = ("", "sales", "sopir", "desainer", "gudang", "pengawas")
WORK_CATEGORY_LABEL = {"": "Tidak ada", "sales": "Sales", "sopir": "Sopir", "desainer": "Desainer",
                       "gudang": "Petugas gudang", "pengawas": "Pengawas"}
#: Nilai bawaan sistem peran bawaan (sebelum pengaturan admin); yang tidak disebut: "semua" dan tanpa kategori.
PRT4_BUILTIN_TRAITS: Dict[str, Dict[str, str]] = {
    "sales": {"data_scope": "milik_sendiri", "kategori_kerja": "sales"},
    "driver": {"data_scope": "milik_sendiri", "kategori_kerja": "sopir"},
    "designer": {"data_scope": "milik_sendiri", "kategori_kerja": "desainer"},
    "warehouse": {"kategori_kerja": "gudang"},
    "admin": {"kategori_kerja": "pengawas"},
    "manager": {"kategori_kerja": "pengawas"},
}
#: Halaman awal bawaan peran bawaan (foto registry sebelum `apply_traits` menimpa `home_view`/`home_nav_id`).
BUILTIN_HOME: Dict[str, tuple] = {rid: (r["home_view"], r["home_nav_id"]) for rid, r in ROLES.items()}
PROFILE_HOME = ("hr-my-profile", "hr-my-profile")
#: Pilihan halaman awal: `requires` = izin (sumber daya, aksi) yang dibutuhkan layarnya; `needs_category` = meja kerja.
HOME_CHOICES: List[Dict[str, Any]] = [
    {"view": "hr-my-profile", "nav_id": "hr-my-profile", "label": "Profil Saya", "requires": None},
    {"view": "my-desk", "nav_id": "my-desk", "label": "Meja Saya", "requires": None, "needs_category": True},
    {"view": "sales-home", "nav_id": "home", "label": "Performa Saya", "requires": ("order", "view")},
    {"view": "manager-home", "nav_id": "home", "label": "Beranda Manajer", "requires": ("manager_home", "view")},
    {"view": "admin-home", "nav_id": "home", "label": "Beranda Admin", "requires": ("manager_home", "view")},
    {"view": "sales-admin-desk", "nav_id": "sales-admin-desk", "label": "Meja Admin Sales",
     "requires": ("order", "confirm")},
    {"view": "finance-desk", "nav_id": "finance-desk", "label": "Meja Finance",
     "requires": ("payment_variance", "decide")},
    {"view": "md-desk", "nav_id": "md-desk", "label": "Meja MD", "requires": ("design_request", "view")},
    {"view": "warehouse-admin-desk", "nav_id": "warehouse-admin-desk", "label": "Meja Admin Gudang",
     "requires": ("wms", "view")},
    {"view": "sample-admin-desk", "nav_id": "sample-admin-desk", "label": "Meja Admin Sample",
     "requires": ("sample_order", "view")},
    {"view": "operations", "nav_id": "wms-operations", "label": "Operasi Gudang", "requires": ("wms", "view")},
    {"view": "design-requests", "nav_id": "design-requests", "label": "Permintaan Desain",
     "requires": ("design_request", "view")},
    {"view": "logistics", "nav_id": "logistics", "label": "Pengiriman", "requires": ("logistics", "view")},
    {"view": "inspections", "nav_id": "quality-hub", "label": "SPK Inspeksi", "requires": ("inspection", "view")},
]
HOME_BY_VIEW: Dict[str, Dict[str, Any]] = {c["view"]: c for c in HOME_CHOICES}
#: Nilai yang DISIMPAN Admin (`permission_settings.role_traits`); diisi `apply_traits`.
TRAIT_OVERRIDES: Dict[str, Dict[str, Any]] = {}


def home_allowed(view: str, perms: Optional[Dict[str, Any]], category: str) -> bool:
    """Syarat satu halaman awal terpenuhi oleh izin `perms` (dan kategori kerja untuk Meja Saya)?"""
    choice = HOME_BY_VIEW.get(view or "")
    if not choice:
        return False
    if choice.get("needs_category") and not category:
        return False
    need = choice.get("requires")
    if not need:
        return True
    acts = (perms or {}).get(need[0]) or []
    return need[1] in acts or "*" in acts


def _derived_trait(rid: str, key: str, depth: int = 0) -> Any:
    """Nilai turunan (tanpa simpanan peran itu sendiri)."""
    entry = ROLES.get(rid) or {}
    if rid in BUILTIN_HOME and not entry.get("custom"):
        if key == "home_view":
            return BUILTIN_HOME[rid][0]
        if key == "notify_like":
            return []
        return (PRT4_BUILTIN_TRAITS.get(rid) or {}).get(key, "semua" if key == "data_scope" else "")
    base = entry.get("base_role") or ""
    if key == "notify_like":
        return [base] if base in BUILTIN_HOME else []
    if base and base != rid and base in ROLES and depth < 5:
        return _effective_trait(base, key, depth + 1)
    return {"data_scope": "semua", "home_view": PROFILE_HOME[0], "kategori_kerja": ""}[key]


def _effective_trait(rid: str, key: str, depth: int = 0) -> Any:
    ov = TRAIT_OVERRIDES.get(rid) or {}
    if key in ov:
        return ov[key]
    return _derived_trait(rid, key, depth)


def _home_nav(rid: str, view: str, depth: int = 0) -> str:
    """`home_nav_id` untuk halaman awal `view` peran `rid` (bawaan registry bila view = bawaan)."""
    if rid in BUILTIN_HOME and not (ROLES.get(rid) or {}).get("custom") and view == BUILTIN_HOME[rid][0]:
        return BUILTIN_HOME[rid][1]
    base = (ROLES.get(rid) or {}).get("base_role") or ""
    if "home_view" not in (TRAIT_OVERRIDES.get(rid) or {}) and base and base in ROLES and depth < 5:
        return _home_nav(base, view, depth + 1)
    return (HOME_BY_VIEW.get(view) or {}).get("nav_id") or view


def trait_defaults(rid: str) -> Dict[str, Any]:
    """Nilai turunan keempat sifat (yang berlaku bila Admin tidak menyimpan apa pun untuk peran ini)."""
    return {k: (list(v) if isinstance(v, list) else v) for k, v in
            ((k, _derived_trait(rid, k)) for k in TRAIT_KEYS)}


def apply_traits(overrides: Optional[Dict[str, Dict[str, Any]]],
                 matrix: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
    """Isi `ROLES[rid]` dengan sifat EFEKTIF: `data_scope`, `kategori_kerja`, `notify_like`, `home_view`,
    `home_nav_id`, `home_view_fallback`. `matrix` (izin efektif per peran) dipakai memeriksa halaman awal yang
    DISIMPAN: syaratnya tidak lagi terpenuhi → Profil Saya + `home_view_fallback`."""
    TRAIT_OVERRIDES.clear()
    for rid, vals in (overrides or {}).items():
        clean = {k: v for k, v in (vals or {}).items() if k in TRAIT_KEYS and v is not None}
        if clean:
            TRAIT_OVERRIDES[rid] = clean
    for rid in ROLES:
        entry = ROLES[rid]
        entry["data_scope"] = _effective_trait(rid, "data_scope")
        entry["kategori_kerja"] = _effective_trait(rid, "kategori_kerja")
        entry["notify_like"] = list(_effective_trait(rid, "notify_like") or [])
        view = _effective_trait(rid, "home_view")
        fallback = False
        if "home_view" in (TRAIT_OVERRIDES.get(rid) or {}) and matrix is not None \
                and not home_allowed(view, matrix.get(rid) or {}, entry["kategori_kerja"]):
            view, fallback = PROFILE_HOME[0], True
        entry["home_view"] = view
        entry["home_nav_id"] = PROFILE_HOME[1] if fallback else _home_nav(rid, view)
        entry["home_view_fallback"] = fallback


def traits_of(rid: str) -> Dict[str, Any]:
    entry = ROLES.get(rid) or {}
    return {"data_scope": entry.get("data_scope") or _effective_trait(rid, "data_scope"),
            "home_view": entry.get("home_view") or PROFILE_HOME[0],
            "kategori_kerja": entry.get("kategori_kerja", _effective_trait(rid, "kategori_kerja")) or "",
            "notify_like": list(entry.get("notify_like", _effective_trait(rid, "notify_like")) or [])}


def data_scope_of(role: Optional[str]) -> str:
    """Cakupan data peran (`milik_sendiri` · `tim` · `semua`). Peran tak dikenal = "semua" (tanpa izin apa pun)."""
    r = role or ""
    if r not in ROLES:
        return "semua"
    return ROLES[r].get("data_scope") or _effective_trait(r, "data_scope")


def category_of(role: Optional[str]) -> str:
    """Kategori kerja peran ("" bila tidak ada)."""
    r = role or ""
    if r not in ROLES:
        return ""
    entry = ROLES[r]
    return entry["kategori_kerja"] if "kategori_kerja" in entry else _effective_trait(r, "kategori_kerja")


def roles_in_category(kategori: str) -> List[str]:
    """Id peran (bawaan & kustom) berkategori kerja `kategori`, urut registry."""
    return [rid for rid in role_ids() if category_of(rid) == kategori]


def notify_addresses(role: Optional[str]) -> List[str]:
    """Peran bawaan yang notifikasinya ikut diterima pemegang `role` (selain alamat perannya sendiri)."""
    r = role or ""
    if r not in ROLES:
        return []
    entry = ROLES[r]
    return list(entry["notify_like"] if "notify_like" in entry else _effective_trait(r, "notify_like") or [])


def home_choices_for(perms: Optional[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """Untuk layar: `allowed` menurut izin tersimpan; `requires`/`needs_category` supaya editor menghitung ulang
    selagi izin diubah sebelum disimpan."""
    return [{"view": c["view"], "label": c["label"], "allowed": home_allowed(c["view"], perms, category),
             "requires": list(c["requires"]) if c.get("requires") else None,
             "needs_category": bool(c.get("needs_category"))} for c in HOME_CHOICES]


apply_traits({})   # PR-T4 — peran bawaan langsung bersifat bawaan sebelum `sync_registry` pertama


#: Peringkat yang dipakai bila `required_role` diisi nilai yang tidak dikenal.
#: Sengaja = peringkat manajer (perilaku lama), supaya konfigurasi persetujuan yang
#: sudah tersimpan di basis data tidak mendadak jadi lebih longgar.
_DEFAULT_REQUIRED_RANK = ROLES["manager"]["rank"]


def role_ids() -> List[str]:
    """Semua id peran, urut sesuai wewenang (admin dulu)."""
    return sorted(ROLES, key=lambda r: ROLES[r]["order"])


def is_role(role: str) -> bool:
    return role in ROLES


def base_or_self(role: Optional[str]) -> str:
    """Peran ACUAN untuk peran kustom (bila ada), selain itu peran itu sendiri — mis. meja kerja per peran."""
    r = role or ""
    return (ROLES.get(r) or {}).get("base_role") or r


def role_in(actor_role: Optional[str], roles) -> bool:
    """Peran (atau peran ACUAN untuk peran kustom) termasuk dalam `roles`?"""
    r = actor_role or ""
    if r in roles:
        return True
    base = (ROLES.get(r) or {}).get("base_role") or ""
    return bool(base) and base in roles


def role_label(role: str, long: bool = False) -> str:
    """Label untuk MANUSIA. Jangan pernah menampilkan id teknis ke pengguna."""
    entry = ROLES.get(role or "")
    if not entry:
        return role or "—"
    return entry["long_label"] if long else entry["label"]


def rank_of(role: str) -> int:
    return ROLE_RANK.get(role or "", 0)


def required_rank(required_role: Optional[str]) -> int:
    """Peringkat yang dituntut sebuah aturan persetujuan.

    `""`/`None` = tanpa persetujuan (0). Nilai tak dikenal = peringkat manajer.
    """
    if not required_role:
        return 0
    return ROLE_RANK.get(required_role, _DEFAULT_REQUIRED_RANK)


def role_satisfies(actor_role: str, required_role: Optional[str]) -> bool:
    """Apakah peran aktor memenuhi `required_role` dari matriks persetujuan?

    Hirarki: admin(4) > manager(3) > sales_admin/finance(2) > sales/warehouse(1).
    `admin` selalu lolos. Admin Sales & Finance TIDAK memenuhi tuntutan `manager`
    — itu disengaja (mereka pelaksana, bukan penyetuju nilai).
    """
    return rank_of(actor_role) >= required_rank(required_role)


def home_of(role: str) -> Dict[str, str]:
    entry = ROLES.get(role or "") or ROLES["sales"]
    return {"view": entry["home_view"], "nav_id": entry["home_nav_id"]}


def public_list() -> List[Dict[str, Any]]:
    """Bentuk untuk API/FE (dipakai layar “Badan Usaha & Akses” + POC)."""
    return [
        {
            "id": rid,
            "label": ROLES[rid]["label"],
            "long_label": ROLES[rid]["long_label"],
            "rank": ROLES[rid]["rank"],
            "cross_entity": ROLES[rid]["cross_entity"],
            "scope_hint": ROLES[rid]["scope_hint"],
            "description": ROLES[rid]["description"],
            "home_view": ROLES[rid]["home_view"],
            "home_nav_id": ROLES[rid]["home_nav_id"],
            "new_in": ROLES[rid].get("new_in", ""),
            "custom": bool(ROLES[rid].get("custom")),
            "base_role": ROLES[rid].get("base_role", ""),
            "nav": ROLES[rid].get("nav"),
            # PR-T4 — sifat efektif (halaman awal di atas sudah efektif).
            "data_scope": data_scope_of(rid),
            "kategori_kerja": category_of(rid),
            "notify_like": notify_addresses(rid),
        }
        for rid in role_ids()
    ]


def assert_valid_role(role: str) -> str:
    """Validasi peran saat membuat/mengubah akun.

    Dulu `role` adalah teks bebas: salah ketik (`"sales-admin"`, `"Finance"`) membuat
    akun yang **tidak punya izin apa pun** dan pemiliknya bingung kenapa semua layar
    kosong. Sekarang ditolak dengan menyebut pilihan yang sah.
    """
    from fastapi import HTTPException

    clean = (role or "").strip()
    if clean in ROLES:
        return clean
    pilihan = " · ".join(f"{rid} ({ROLES[rid]['label']})" for rid in role_ids())
    raise HTTPException(
        status_code=400,
        detail=f"Peran “{clean or '(kosong)'}” tidak dikenal. Pilihan yang sah: {pilihan}.",
    )


# ─── SELF-TEST (dipakai gate: `python -m role_registry --self-test`) ─────────
def _self_test() -> int:
    fails = 0

    def chk(name: str, cond: bool, note: str = "") -> None:
        nonlocal fails
        mark = "\033[92m[PASS]\033[0m" if cond else "\033[91m[FAIL]\033[0m"
        print(f"  {mark} {name}" + (f"  · {note}" if note else ""))
        if not cond:
            fails += 1

    print("== SELF-TEST role_registry (FASE E-8) ==")
    # FASE D — dulu `len(ROLES) == 6`. Angka mati itu memerah setiap kali peran baru
    # lahir, padahal tidak ada yang rusak: yang dijaga registry ini adalah PERINGKAT,
    # LABEL & BERANDA, bukan populasinya. Asersi yang benar = peran inti tetap ada
    # (kalau salah satunya hilang, matriks persetujuan di bawah ikut kehilangan arti).
    inti = {"admin", "manager", "sales_admin", "finance", "sales", "warehouse"}
    chk(f"{len(ROLES)} peran terdaftar (peran inti lengkap)", inti <= set(ROLES),
        " · ".join(role_ids())
        + (f"  · KURANG: {sorted(inti - set(ROLES))}" if inti - set(ROLES) else ""))
    chk("admin peringkat tertinggi", max(r["rank"] for r in ROLES.values()) == ROLES["admin"]["rank"])
    chk("sales_admin & finance di atas sales/gudang",
        rank_of("sales_admin") > rank_of("sales") and rank_of("finance") > rank_of("warehouse"))
    chk("sales_admin & finance DI BAWAH manajer (bukan penyetuju nilai)",
        rank_of("sales_admin") < rank_of("manager") and rank_of("finance") < rank_of("manager"))
    chk("BAWAAN lintas badan usaha hanya admin & manager (selebihnya diatur admin per peran)",
        {r for r, v in BUILTIN_CROSS_ENTITY.items() if v} == {"admin", "manager"},
        str(sorted(r for r, v in BUILTIN_CROSS_ENTITY.items() if v)))
    chk("aturan 'manager' tidak bisa dipenuhi Admin Sales",
        not role_satisfies("sales_admin", "manager"))
    chk("aturan 'manager' dipenuhi manajer & admin",
        role_satisfies("manager", "manager") and role_satisfies("admin", "manager"))
    chk("aturan kosong = tanpa persetujuan (siapa pun yang boleh ubah)",
        role_satisfies("sales", "") and role_satisfies("warehouse", None))
    chk("required_role tak dikenal jatuh ke peringkat manajer (tidak jadi longgar)",
        not role_satisfies("sales_admin", "direksi") and role_satisfies("manager", "direksi"))
    chk("setiap peran punya label manusia & beranda",
        all(ROLES[r]["label"] and ROLES[r]["home_view"] for r in ROLES))
    chk("tidak ada label peran yang dobel",
        len({ROLES[r]["label"] for r in ROLES}) == len(ROLES))

    # PR-T4 — nilai awal sifat peran = perilaku sebelum sifat bisa diatur.
    chk("cakupan 'milik sendiri' bawaan hanya Sales, Sopir, Desainer",
        {r for r in BUILTIN_HOME if trait_defaults(r)["data_scope"] != "semua"} == {"sales", "driver", "designer"})
    chk("setiap halaman awal bawaan ada di daftar pilihan",
        all(BUILTIN_HOME[r][0] in HOME_BY_VIEW for r in BUILTIN_HOME))

    # BUKTI-MERAH: kalau peringkat Admin Sales disamakan dengan manajer, gate HARUS memerah.
    saved = ROLE_RANK["sales_admin"]
    ROLE_RANK["sales_admin"] = ROLE_RANK["manager"]
    broke = role_satisfies("sales_admin", "manager")
    ROLE_RANK["sales_admin"] = saved
    chk("BUKTI-MERAH: menaikkan peringkat Admin Sales memang mengubah keputusan",
        broke and not role_satisfies("sales_admin", "manager"))

    print(f"\n  {'HIJAU' if fails == 0 else 'MERAH'} — {len(ROLES)} peran, {fails} gagal.")
    return fails


if __name__ == "__main__":
    import sys

    sys.exit(1 if _self_test() else 0)
