"""FASE G-0 — CONFIG REGISTRY: **sumber kebenaran tunggal** untuk semua aturan configurable.

Masalah yang diselesaikan (audit 2026-07-26, `scripts/audit_config_wiring.py`):
- 105 kunci konfigurasi tersebar di `config_service.DEFAULT_GLOBAL_SETTINGS` + 5 dokumen
  scope lain di `system_settings`, **tanpa** deskripsi, tanpa batas nilai, tanpa referensi
  kode konsumen, dan tanpa satu tempat untuk melihatnya.
- Akibatnya: **6 "tombol palsu"** (ada UI, tak ada kode yang membaca) dan **31 aturan
  tersembunyi** (dipakai mesin, tak ada UI).

Registry ini membuat setiap setting **eksplisit & bisa diaudit**:
  key · label awam · penjelasan · dampak bila diubah · contoh angka · tipe & batas ·
  level scope · **referensi kode konsumen (WAJIB)** · izin pengubah · sifat baca · risiko · status.

KF-T1 — wewenang MENGUBAH sebuah kunci = `permission` (izin di matriks peran, terlihat dan bisa dicabut di layar
Peran & Hak Akses); tidak ada lagi jalur nama peran (`roles`/`owner_role`). Wewenang MEMBACA: pemegang
`settings.view`, atau yang boleh mengubah kunci itu (`routers/config.py` `_may_read`). `sensitif_baca=False` menandai
kunci yang boleh dikirim ke semua pengguna lewat `GET /api/settings/effective` (dibaca layar POS/PO/tagihan).

UI "Pusat Pengaturan" **di-generate dari registry ini**, sehingga UI dan mesin tidak
bisa lagi berbeda. Gate `scripts/audit_config_wiring.py` menolak kunci `active` yang
tidak punya consumer nyata (INV-CFG-01).

Catatan penyimpanan (kompatibilitas): kunci tanpa prefix scope disimpan di dokumen
`system_settings{scope:"global"}` (override per entitas di `system_settings{scope:<entity_id>}`),
sedangkan kunci ber-prefix `uom.` `lot.` `makloon.` `receiving.` `hr.` disimpan di dokumen
`system_settings{scope:"<prefix>"}`. Resolver (`services/config_resolver.py`) memakai peta ini
sehingga mesin lama TETAP berfungsi tanpa migrasi paksa.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ── Tipe nilai yang didukung UI generik ──────────────────────────────────────
TYPES = {
    "bool",      # switch
    "int",       # angka bulat
    "pct",       # persen (0..100)
    "money",     # rupiah
    "decimal",   # angka desimal bebas
    "enum",      # pilihan tunggal dari options
    "text",      # teks pendek
    "list",      # daftar sederhana (urutan bermakna)
    "table",     # tabel/objek kompleks (editor khusus)
    "duration",  # jumlah hari
}

# Lapisan scope, dari paling umum ke paling spesifik (yang kanan menang).
SCOPE_LEVELS: List[str] = ["global", "entity", "customer", "supplier", "product", "document"]
RISKS = {"low", "medium", "high"}
STATUSES = {"active", "not_used"}

# Bentuk data untuk setting bertipe `table`. Menentukan editor mana yang dipakai UI:
#   list → array of objects  ⇒ editor baris (tambah/hapus baris, kolom bertipe)
#   map  → objek datar       ⇒ editor pasangan kunci-nilai
#   json → struktur bersarang ⇒ editor JSON (kasus jarang & memang kompleks)
# Tanpa ini UI hanya bisa menampilkan JSON mentah — itulah alasan editor pajak lama
# terasa lebih ramah daripada Pusat Pengaturan sebelum FASE G-0 dituntaskan.
ROW_SHAPES = {"list", "map", "json",
              # KF-T4 (KF-13) — objek `{nilai kolom pertama: [baris]}` (mis. `approval.extra_levels`) disunting sebagai
              # baris datar; kolom pertama = kunci kelompok.
              "grouped_list"}

# Prefix kunci yang tersimpan di dokumen `system_settings` scope tersendiri.
# KP-T8 (KP-31) — `integrations`: hidup/mati & model pengenal gambar (`integrations.anthropic.*`) tersimpan di dokumen
# `system_settings{scope: "integrations"}` yang sama dengan sebelum unit itu (tanpa migrasi).
LEGACY_SCOPED_PREFIXES: Tuple[str, ...] = ("uom", "lot", "makloon", "receiving", "hr", "integrations")


# ── Grup: dikelompokkan berdasarkan PERTANYAAN BISNIS, bukan nama modul ──────
# `question` sengaja ditulis sebagai pertanyaan yang biasa diucapkan pemilik usaha,
# supaya user tahu grup mana yang harus dibuka tanpa perlu paham arsitektur sistem.
#
# KF-T4 (KF-UX-11/12) — 23 kelompok tanpa sub-judul (terbesar 40 kunci) diganti 13 kelompok bersub-judul
# (`docs/blueprint/unit/KF-T4.md` tabel (c)). Tiap kunci menyebut `section` (sub-judul) pada kelompoknya;
# `advanced: True` = bagian "Lanjutan (teknis)" yang tertutup secara bawaan. Sub-judul biasa paling banyak 14 kunci
# (penjaga `scripts/guardrails/verify_config_text.py` T7). Id kelompok lama tetap diterima lewat `GROUP_ALIASES`.
def _S(sid: str, label: str, advanced: bool = False) -> Dict[str, Any]:
    return {"id": sid, "label": label, "advanced": advanced}


GROUPS: List[Dict[str, Any]] = [
    {"id": "penjualan", "label": "Penjualan & harga", "order": 1,
     "question": "Siapa boleh menurunkan harga, kapan pesanan boleh jalan, dan bagaimana komisi sales dihitung?",
     "sections": [_S("harga", "Harga & diskon"), _S("alur-pesanan", "Alur pesanan"), _S("komisi", "Komisi sales"),
                  _S("saran-pos", "Saran produk di kasir (POS)")]},
    {"id": "pembayaran-pelanggan", "label": "Pembayaran pelanggan", "order": 2,
     "question": "Kapan pelanggan harus bayar, dan apa akibatnya kalau telat atau bayarnya tidak pas?",
     "sections": [_S("syarat-bayar", "Syarat bayar, DP & cicilan"), _S("denda", "Denda telat bayar"),
                  _S("selisih-bayar", "Selisih bayar")]},
    {"id": "retur-koreksi", "label": "Retur & koreksi dokumen", "order": 3,
     "question": "Bukti apa yang wajib untuk retur, dan koreksi angka mana yang harus disetujui?",
     "sections": [_S("retur", "Retur penjualan"), _S("koreksi", "Koreksi dokumen")]},
    {"id": "pembelian", "label": "Pembelian, makloon & tagihan pemasok", "order": 4,
     "question": "Apa yang wajib saat memesan ke pemasok atau makloon, dan kapan tagihannya boleh dibayar?",
     "sections": [_S("memesan", "Memesan ke pemasok"), _S("makloon", "Makloon"),
                  _S("tagihan", "Tagihan pemasok & kontrabon")]},
    {"id": "penerimaan", "label": "Penerimaan barang & lot", "order": 5,
     "question": "Boleh terima lebih dari PO? Nomor lot wajib? Satuan pemasok dihitung bagaimana?",
     "sections": [_S("menerima", "Menghitung & menerima"), _S("nomor-lot", "Nomor lot"),
                  _S("konversi-satuan", "Konversi satuan")]},
    {"id": "kualitas", "label": "Mutu kain (QC)", "order": 6,
     "question": "Berapa poin cacat jadi grade apa, dan kapan roll ditahan?",
     "sections": [_S("inspeksi", "Inspeksi & grade"), _S("tidak-sesuai", "Bila tidak sesuai sample"),
                  _S("jumlah-cek", "Berapa roll yang dicek")]},
    {"id": "stok", "label": "Stok, alokasi & potong", "order": 7,
     "question": "Roll mana dipakai lebih dulu, bagaimana sisa potong diperlakukan, dan kapan barang disebut laris "
                 "atau lambat?",
     "sections": [_S("memilih-stok", "Memilih stok untuk pesanan"), _S("potong", "Potong & sisa potong"),
                  _S("laris-lambat", "Laris/lambat & pesan ulang"), _S("kerja-gudang", "Kerja gudang")]},
    {"id": "persetujuan", "label": "Persetujuan, pengingat & dokumen", "order": 8,
     "question": "Dokumen bernilai berapa naik ke siapa, siapa diingatkan, dan bagaimana dokumen saling merujuk?",
     # KF-T6 — kunci `kontrol.*` diubah di tab Persetujuan › Kontrol dua orang; di sini dibagi per bidang (≤ 14).
     "sections": [_S("umum", "Persetujuan umum"), _S("rnd", "Persetujuan R&D"), _S("pemberitahuan", "Pemberitahuan"), _S("tenggat-pengingat", "Kapan pengingat dikirim"),
                  _S("rujukan-dokumen", "Rujukan antar dokumen"),
                  _S("dua-orang-pembelian", "Dua orang: pembelian"),
                  _S("dua-orang-hutang", "Dua orang: tagihan pemasok"),
                  _S("dua-orang-penjualan", "Dua orang: penjualan & retur"),
                  _S("dua-orang-piutang", "Dua orang: piutang"),
                  _S("dua-orang-gudang", "Dua orang: gudang, produksi & R&D"),
                  _S("dua-orang-sdm", "Dua orang: SDM"), _S("dua-orang-buku", "Dua orang: pembukuan"),
                  _S("dua-orang-admin", "Dua orang: pengecualian Admin")]},
    {"id": "pajak-pembukuan", "label": "Pajak, pembukuan & antar-PT", "order": 9,
     "question": "Berapa PPN, kapan buku ditutup, dan bagaimana jual-beli antar-PT dihitung?",
     "sections": [_S("pajak", "Pajak"), _S("tutup-buku", "Mata uang & tutup buku"),
                  _S("antar-pt", "Jual-beli antar-PT")]},
    {"id": "bank-kasus", "label": "Bank & uang yang nyangkut", "order": 10,
     "question": "Kapan mutasi bank dicocokkan otomatis, dan berapa lama uang tak jelas boleh menganggur?",
     "sections": [_S("bank", "Mencocokkan mutasi bank"), _S("kasus", "Kasus keuangan")]},
    {"id": "sdm", "label": "Gaji & SDM", "order": 11,
     "question": "Berapa iuran BPJS, PPh 21, dan upah lembur?",
     "sections": [_S("bpjs", "BPJS"), _S("pph21", "PPh 21"), _S("lembur", "Lembur, komisi & kepegawaian")]},
    {"id": "rnd", "label": "R&D & desain", "order": 12,
     "question": "Kapan barang hasil R&D boleh dijual, siapa memutus sample, dan bagaimana desainer dinilai?",
     "sections": [_S("boleh-dijual", "Kapan produk boleh dijual"), _S("sample", "Sample & pemasok pemenang"),
                  _S("kode-desain", "Kode & nilai desain"), _S("nilai-desainer", "Nilai desainer")]},
    {"id": "sistem", "label": "Sistem, AI & tampilan", "order": 13,
     "question": "Fitur AI mana yang aktif dan berapa anggarannya, serta apa yang tampil di menu?",
     # KF-T4 — tanpa `sensitif_baca` tingkat kelompok: kunci menu (`ui.*`) dan saran kasir (`pos.*`) yang dulu terbuka
     # lewat kelompok Tampilan kini menyebut `sensitif_baca=False` sendiri (keterbacaan tiap kunci tidak berubah).
     "sections": [_S("tanya-kn", "Tanya KN: arti angka & hak lihat"),
                  # AG-T1 — sub-judul sendiri: "tanya-kn" sudah 14 kunci (batas sub-judul biasa, KF-T4).
                  _S("tanya-kn-tindakan", "Tanya KN: kartu tindakan"),
                  _S("tanya-kn-teknis", "Tanya KN: model & anggaran", advanced=True),
                  _S("baca-sj", "Baca surat jalan otomatis", advanced=True),
                  _S("rfid-proses", "RFID & proses macet", advanced=True),
                  _S("menu", "Menu & halaman awal")]},
]


# ── KF-T7 — kelompok & sub-judul untuk nilai bisnis yang dulu ditulis mati (`config_catalog_nilai.py`) ──────────────
def _sisip_sub_kft7(gid: str, sub: Dict[str, Any], sesudah: str = "") -> None:
    secs = next(g for g in GROUPS if g["id"] == gid)["sections"]
    i = next((n + 1 for n, s in enumerate(secs) if s["id"] == sesudah), len(secs))
    secs.insert(i, sub)


_sisip_sub_kft7("pembayaran-pelanggan", _S("kredit", "Peringatan & blokir kredit"))
_sisip_sub_kft7("penjualan", _S("pesanan-khusus", "Pesanan khusus & katalog sample"), sesudah="alur-pesanan")
_sisip_sub_kft7("persetujuan", _S("tanda-tangan", "Tanda tangan elektronik"), sesudah="rujukan-dokumen")
GROUPS.append({"id": "keamanan", "label": "Keamanan akun & sesi", "order": 14,
               "question": "Berapa kali salah sandi sebelum akun dikunci, dan berapa lama sesi masuk berlaku?",
               "sections": [_S("masuk", "Salah sandi & lama sesi")]})
# ── akhir blok KF-T7 ──
GROUP_IDS = {g["id"] for g in GROUPS}
SECTION_IDS: Dict[str, Dict[str, Dict[str, Any]]] = {g["id"]: {x["id"]: x for x in g["sections"]} for g in GROUPS}

#: KF-T4 — id kelompok lama → (id kelompok baru, sub-judul tujuan atau ""). Dipakai `by_group`, `E(group=<id lama>)`,
#: `GET /api/config/effective?group=<id lama>`, dan layar (`configDeepLink.js` menyalin peta ini; diuji sama). Untuk
#: kelompok lama yang terbagi ke beberapa kelompok baru, tujuan pertama = kelompok yang memuat kunci terbanyak.
#: Id lama yang juga id baru (`persetujuan`, `pembelian`, `penerimaan`, `kualitas`, `sdm`, `rnd`) tidak dialiaskan.
GROUP_ALIASES: Dict[str, Tuple[str, str]] = {
    "uang-masuk": ("pembayaran-pelanggan", ""),
    "harga-diskon": ("penjualan", ""),
    "pajak": ("pajak-pembukuan", "pajak"),
    "keuangan-dasar": ("pajak-pembukuan", "tutup-buku"),
    "stok-satuan": ("stok", ""),
    "lot": ("penerimaan", "nomor-lot"),
    "makloon": ("pembelian", "makloon"),
    "tampilan": ("sistem", "menu"),
    "amandemen": ("retur-koreksi", "koreksi"),
    "dokumen": ("persetujuan", "rujukan-dokumen"),
    "bank": ("bank-kasus", "bank"),
    "kasus": ("bank-kasus", "kasus"),
    "kontrabon": ("pembelian", "tagihan"),
    "antar-entitas": ("pajak-pembukuan", "antar-pt"),
    "notifikasi": ("persetujuan", "pemberitahuan"),
    "asisten-analitik": ("sistem", "tanya-kn"),
    "retur": ("retur-koreksi", "retur"),
}


def resolve_group_id(group_id: str) -> Tuple[str, str]:
    """(id kelompok baru, sub-judul tujuan) untuk id baru atau id lama; ("", "") bila tidak dikenal."""
    g = (group_id or "").strip()
    if g in GROUP_IDS:
        return g, ""
    return GROUP_ALIASES.get(g, ("", ""))


#: KF-T4 — tema lintas kelompok (saringan "Persetujuan" · "Pengingat & batas waktu" · "Toleransi selisih"), dari pola
#: kunci (`docs/blueprint/unit/KF-T4.md` § Server).
THEMES: Tuple[Tuple[str, str, str], ...] = (
    ("persetujuan", "Persetujuan",
     r"approv|dual_control|require_so_validation|require_verification_before_confirm|decision_roles|treatment_roles"
     r"|direksi"),
    ("pengingat", "Pengingat & batas waktu",
     r"remind|sla_|_sla|stuck|escalat|holding_max_age|holding_case_after|unbilled_gr_age|wait_(warn|late)"
     r"|keep_max_age|drift_alert"),
    ("toleransi", "Toleransi selisih", r"toleran"),
)


def themes_for(key: str) -> List[str]:
    import re as _re
    return [tid for tid, _lab, pola in THEMES if _re.search(pola, key or "")]


#: KF-T4 — isi daftar (`type="list"`): butir dari `options` · id peran yang dikenal · bilangan bulat > 0 menaik · teks.
LIST_ITEMS = ("options", "roles", "int_asc", "text")
#: KF-T4 — kunci teks yang nilainya rujukan ke master: Syarat Bayar · satuan · departemen SDM.
REFS = ("payment_term", "uom", "department")

_REGISTRY: Dict[str, Dict[str, Any]] = {}
_ORDER: List[str] = []


def legacy_target(key: str) -> Tuple[str, str]:
    """Peta kunci registry → (scope dokumen `system_settings`, dot-path di dalam dokumen).

    >>> legacy_target("ar.grace_days")
    ('global', 'ar.grace_days')
    >>> legacy_target("receiving.block_over_remaining")
    ('receiving', 'block_over_remaining')
    """
    head, _, rest = key.partition(".")
    if head in LEGACY_SCOPED_PREFIXES and rest:
        return head, rest
    return "global", key


def E(
    key: str,
    *,
    group: str,
    label: str,
    help: str,
    impact: str,
    example: str = "",
    type: str = "text",
    default: Any = None,
    min: Optional[float] = None,
    max: Optional[float] = None,
    step: Optional[float] = None,
    options: Optional[Sequence[Dict[str, str]]] = None,
    unit: str = "",
    scopes: Sequence[str] = ("global", "entity"),
    consumers: Sequence[str] = (),
    risk: str = "low",
    requires_reason: bool = False,
    status: str = "active",
    not_used_reason: str = "",
    simulate: str = "",
    related: Sequence[str] = (),
    row_shape: str = "",
    columns: Optional[Sequence[Dict[str, Any]]] = None,
    permission: Optional[Tuple[str, str]] = None,
    value_format: str = "",
    sensitif_baca: Optional[bool] = None,
    bertanggal: bool = False,
    section: str = "",
    items: str = "",
    ordered: bool = False,
    ref: str = "",
    edit_at: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Daftarkan satu setting. Validasi ketat supaya registry tidak pernah setengah jadi.

    KF-T4 — `section` (wajib: sub-judul yang terdaftar pada kelompoknya; id kelompok lama diterjemahkan lewat
    `GROUP_ALIASES` dan memberi sub-judul tujuannya bila ada) · `items`/`ordered` (isi daftar) · `ref` (teks rujukan
    master) · `edit_at` (`{view, preset}`: kartu tanpa editor, diubah di layar lain)."""
    if key in _REGISTRY:
        raise ValueError(f"config_registry: kunci ganda '{key}'")
    if type not in TYPES:
        raise ValueError(f"config_registry[{key}]: type '{type}' tidak dikenal")
    group, alias_section = resolve_group_id(group)
    if group not in GROUP_IDS:
        raise ValueError(f"config_registry[{key}]: group tidak ada di GROUPS maupun GROUP_ALIASES")
    section = section or alias_section
    if not section:
        raise ValueError(f"config_registry[{key}]: section (sub-judul) wajib diisi — KF-T4")
    if section not in SECTION_IDS[group]:
        raise ValueError(f"config_registry[{key}]: section '{section}' tidak terdaftar pada kelompok '{group}'")
    if items and (type != "list" or items not in LIST_ITEMS):
        raise ValueError(f"config_registry[{key}]: items '{items}' hanya untuk type list ({', '.join(LIST_ITEMS)})")
    if items == "options" and not options:
        raise ValueError(f"config_registry[{key}]: items 'options' wajib punya options")
    if ref and (type != "text" or ref not in REFS):
        raise ValueError(f"config_registry[{key}]: ref '{ref}' hanya untuk type text ({', '.join(REFS)})")
    if edit_at is not None and not (isinstance(edit_at, dict) and edit_at.get("view")):
        raise ValueError(f"config_registry[{key}]: edit_at wajib berbentuk {{view, preset}}")
    if risk not in RISKS:
        raise ValueError(f"config_registry[{key}]: risk '{risk}' tidak dikenal")
    if status not in STATUSES:
        raise ValueError(f"config_registry[{key}]: status '{status}' tidak dikenal")
    bad_scopes = [s for s in scopes if s not in SCOPE_LEVELS]
    if bad_scopes:
        raise ValueError(f"config_registry[{key}]: scope tak dikenal {bad_scopes}")
    if type == "enum" and not options:
        raise ValueError(f"config_registry[{key}]: type enum wajib punya options")
    if row_shape and row_shape not in ROW_SHAPES:
        raise ValueError(f"config_registry[{key}]: row_shape '{row_shape}' tidak dikenal")
    if row_shape in ("list", "grouped_list") and not columns:
        raise ValueError(
            f"config_registry[{key}]: row_shape 'list' wajib mendefinisikan columns "
            f"supaya UI bisa menampilkan editor baris (bukan JSON mentah)")
    if status == "active" and not consumers:
        raise ValueError(
            f"config_registry[{key}]: kunci 'active' WAJIB mencantumkan consumers "
            f"(kode yang membacanya) — INV-CFG-01")
    if status == "not_used" and not not_used_reason:
        raise ValueError(f"config_registry[{key}]: status not_used wajib not_used_reason")
    if not label or not help or not impact:
        raise ValueError(f"config_registry[{key}]: label/help/impact wajib diisi")
    if value_format and value_format not in VALUE_FORMATS:
        raise ValueError(f"config_registry[{key}]: value_format '{value_format}' tidak dikenal")

    legacy_scope, legacy_path = legacy_target(key)
    entry: Dict[str, Any] = {
        "key": key,
        "group": group,
        "section": section,
        "label": label,
        "help": help,
        "impact": impact,
        "example": example,
        "type": type,
        "default": default,
        "min": min,
        "max": max,
        "step": step,
        "options": list(options or []),
        "unit": unit,
        "scopes": list(scopes),
        "consumers": list(consumers),
        "risk": risk,
        "requires_reason": bool(requires_reason) or risk == "high",
        "status": status,
        "not_used_reason": not_used_reason,
        "simulate": simulate,
        "related": list(related),
        "row_shape": row_shape or ("json" if type == "table" else ""),
        # FIX-3a (B3b FRM-19) — isi nilai divalidasi: `regex` (tiap butir daftar dikompilasi) · `json_map` (teks = objek JSON).
        "value_format": value_format,
        "columns": [dict(c) for c in (columns or [])],
        # Izin yang dibutuhkan untuk MENGUBAH setting ini. Default `settings.manage`
        # (admin). Beberapa setting sengaja memakai izin domainnya sendiri supaya
        # penggabungan editor lama ke Pusat Pengaturan TIDAK mencabut wewenang yang
        # sudah dimiliki peran lain (mis. manager tetap boleh mengubah aturan gaji
        # lewat `hr.manage_payroll`, persis seperti sebelum editor lama dihapus).
        "permission": list(permission or ("settings", "manage")),
        # KF-T1 — True = hanya pemegang `settings.view` / pengubah kunci ini yang membacanya. Nilai eksplisit menang;
        # bila None mengikuti kelompoknya; bawaan sensitif.
        "sensitif_baca": bool(sensitif_baca) if sensitif_baca is not None else bool(
            next((g.get("sensitif_baca", True) for g in GROUPS if g["id"] == group), True)),
        "legacy_scope": legacy_scope,
        "legacy_path": legacy_path,
        "editable": status == "active",
        # PK-46 — kunci BERTANGGAL BERLAKU: nilainya hanya dari bawaan registry + baris `config_values` menurut
        # `effective_from`, dibaca dengan tanggal (`resolve(key, ctx, at=…)`). Resolver tidak memproyeksikannya ke
        # `system_settings` dan tidak membaca lapisan lama, supaya pembacaan untuk tanggal lampau tidak jatuh ke nilai baru.
        "bertanggal": bool(bertanggal),
        # KF-T4 — isi daftar, rujukan master, dan layar pengubah lain (kartu tanpa editor).
        "items": items,
        "ordered": bool(ordered),
        "ref": ref,
        "edit_at": dict(edit_at) if edit_at else None,
    }
    _REGISTRY[key] = entry
    _ORDER.append(key)
    return entry


# ── Akses ────────────────────────────────────────────────────────────────────
def all_entries() -> List[Dict[str, Any]]:
    return [_REGISTRY[k] for k in _ORDER]


def get(key: str) -> Optional[Dict[str, Any]]:
    return _REGISTRY.get(key)


def require(key: str) -> Dict[str, Any]:
    entry = _REGISTRY.get(key)
    if not entry:
        raise KeyError(f"Setting '{key}' tidak ada di registry")
    return entry


def default_of(key: str) -> Any:
    """KF-T2 (KF-06, standar §2.2) — SATU-SATUNYA nilai cadangan kode untuk kunci registry: bawaannya sendiri.

    Dipakai bila dokumen pengaturan tidak memuat kunci itu, supaya mesin dan layar Pusat Pengaturan selalu menunjuk
    angka yang sama. Wadah (dict/list) dikembalikan sebagai salinan supaya pemanggil tidak mengubah registry."""
    import copy
    return copy.deepcopy(require(key)["default"])


def keys() -> List[str]:
    return list(_ORDER)


def groups() -> List[Dict[str, Any]]:
    """Grup + jumlah setting di dalamnya (untuk navigasi Pusat Pengaturan). KF-T4 — tiap sub-judul ikut berjumlah."""
    out = []
    for g in sorted(GROUPS, key=lambda x: x["order"]):
        items = [e for e in all_entries() if e["group"] == g["id"]]
        sections = [{**sec, "count": sum(1 for e in items if e["section"] == sec["id"])} for sec in g["sections"]]
        out.append({**g, "sections": sections, "count": len(items),
                    "active_count": len([e for e in items if e["status"] == "active"])})
    return out


def by_group(group_id: str) -> List[Dict[str, Any]]:
    """Kunci satu kelompok; KF-T4 — id kelompok lama diterjemahkan lewat `GROUP_ALIASES` (seluruh kelompok baru)."""
    gid = resolve_group_id(group_id)[0]
    return [e for e in all_entries() if e["group"] == gid] if gid else []


#: KF-T4 (KF-UX-24) — padanan kata dua arah: mencari salah satu kata = mencari semuanya (hasilnya sama persis).
SEARCH_SYNONYMS: Tuple[Tuple[str, ...], ...] = (
    ("pemasok", "supplier", "vendor"),
    ("cicilan", "angsuran"),
    ("dp", "uang muka"),
    ("terlambat", "telat"),
    ("roll", "gulungan"),
    ("utang", "hutang"),
    ("pt", "entitas", "badan usaha"),
    ("pesanan", "so", "order"),
    ("syarat bayar", "termin", "term"),
)


def _pola_cari(kata: str) -> "Any":
    """Kata pendek (≤ 4 huruf: `pt`, `so`, `dp`, `term`, `roll`) dicocokkan utuh; kata lebih panjang boleh berimbuhan di
    belakang (`pemasoknya`, `supplier_id`)."""
    import re as _re
    akhir = r"(?![a-z0-9])" if len(kata) <= 4 else ""
    return _re.compile(r"(?<![a-z0-9])" + _re.escape(kata) + akhir)


def _varian_cari(term: str) -> List[str]:
    """Bentuk lain `term` menurut `SEARCH_SYNONYMS` ([] bila `term` tidak memuat kata berpadanan)."""
    import re as _re
    varian = [term]
    kena = False
    for grup in SEARCH_SYNONYMS:
        baru: List[str] = []
        for v in varian:
            for kata in grup:
                if _pola_cari(kata).search(v):
                    kena = True
                    for ganti in grup:
                        baru.append(_re.sub(r"(?<![a-z0-9])" + _re.escape(kata) + r"(?![a-z0-9])", ganti, v))
                    break
            else:
                baru.append(v)
        varian = list(dict.fromkeys(baru))[:64]
    return varian if kena else []


def search(term: str) -> List[Dict[str, Any]]:
    """Pencarian awam: cocokkan label, key, help, impact, contoh, nama grup, dan sub-judul (KF-T4); kata berpadanan
    (`SEARCH_SYNONYMS`) dicari dua arah."""
    t = (term or "").strip().lower()
    if not t:
        return all_entries()
    glabel = {g["id"]: g["label"].lower() for g in GROUPS}
    slabel = {(g["id"], x["id"]): x["label"].lower() for g in GROUPS for x in g["sections"]}
    varian = _varian_cari(t)
    pola = [_pola_cari(v) for v in varian]
    hits = []
    for e in all_entries():
        hay = " ".join([e["key"], e["label"], e["help"], e["impact"], e.get("example") or "",
                        glabel.get(e["group"], ""), slabel.get((e["group"], e["section"]), "")]).lower()
        if (any(p.search(hay) for p in pola) if pola else t in hay):
            hits.append(e)
    return hits


# ── Validasi & koersi nilai (dipakai PUT /api/config/values) ─────────────────
VALUE_FORMATS = ("regex", "json_map", "tarif_berjenjang",
                 # KF-T4 — `date`: kosong atau `YYYY-MM-DD` · `multiline`: teks bebas berbaris (kotak multi-baris).
                 "date", "multiline",
                 # PM-T2 — `kode_huruf`: 2–4 huruf besar A–Z (awalan kode bayar, mis. `KN`).
                 "kode_huruf")


def _check_format(entry: Dict[str, Any], value: Any) -> Any:
    """FIX-3a (B3b FRM-19) — nilai yang lolos tipe tetapi isinya rusak (regex tak valid, JSON patah) DITOLAK saat disimpan;
    dulu tersimpan lalu `GET /goods-receipts/usage` / OCR galat 500 untuk semua GRN."""
    fmt = entry.get("value_format") or ""
    if fmt == "regex":
        import re as _re
        items = [str(x) for x in value]
        for i, pat in enumerate(items, 1):
            if not pat.strip():
                raise ValueError(f"'{entry['label']}' butir {i} kosong — hapus butir kosong.")
            try:
                _re.compile(pat)
            except _re.error as exc:
                raise ValueError(f"'{entry['label']}' butir {i} bukan pola yang sah ({exc}). Pola: {pat}") from exc
        return items
    if fmt == "json_map":
        import json as _json
        try:
            obj = _json.loads(value) if isinstance(value, str) else value
        except ValueError as exc:
            raise ValueError(f"'{entry['label']}' harus teks JSON yang sah ({exc}).") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"'{entry['label']}' harus objek JSON {{...}}.")
        return value if isinstance(value, str) else _json.dumps(obj)
    if fmt == "tarif_berjenjang":
        return _tarif_berjenjang(entry, value)
    if fmt == "kode_huruf":
        import re as _re
        teks = str(value or "").strip()
        if not _re.fullmatch(r"[A-Z]{2,4}", teks):
            raise ValueError(f"'{entry['label']}' harus 2–4 huruf besar A–Z (mis. KN).")
        return teks
    if fmt == "date":
        import datetime as _dt
        teks = str(value or "").strip()
        if teks:
            try:
                _dt.date.fromisoformat(teks)
            except ValueError as exc:
                raise ValueError(f"'{entry['label']}' harus tanggal (tahun-bulan-tanggal) atau dikosongkan.") from exc
        return teks
    return value


# ── PK-46 — `value_format="tarif_berjenjang"`: tabel tarif berlapis (PPh 21 TER, pasal 17) ─────────────────────────────
def _angka_tarif(label: str, tempat: str, nama: str, nilai: Any) -> float:
    import math
    from core_utils import parse_decimal
    if isinstance(nilai, bool):
        raise ValueError(f"{label} {tempat}: {nama} harus angka.")
    try:
        num = parse_decimal(nilai, 6, default=float("nan"))
    except ValueError as exc:
        raise ValueError(f"{label} {tempat}: {nama} harus angka ({exc}).") from exc
    if not math.isfinite(num):
        raise ValueError(f"{label} {tempat}: {nama} wajib diisi dengan angka.")
    return num


def _ribuan(num: float) -> str:
    return f"{num:,.0f}".replace(",", ".")


def _periksa_jenjang(label: str, baris: List[Tuple[int, Dict[str, Any]]], awalan: str) -> List[Dict[str, Any]]:
    """Satu tabel berlapis: tidak kosong; `batas_atas` naik tegas; TEPAT baris terakhir tanpa batas; tarif 0–100."""
    if not baris:
        raise ValueError(f"{label} {awalan}tidak boleh kosong.")
    out: List[Dict[str, Any]] = []
    sebelumnya: Optional[float] = None
    for pos, (nomor, r) in enumerate(baris, 1):
        tempat = f"{awalan}baris {pos}" + (f" (baris {nomor} di tabel)" if awalan else "")
        terakhir = pos == len(baris)
        mentah = r.get("batas_atas")
        if mentah is None or (isinstance(mentah, str) and not mentah.strip()):
            if not terakhir:
                raise ValueError(f"{label} {tempat}: hanya baris terakhir yang boleh tanpa batas atas.")
            batas = None
        else:
            if terakhir:
                raise ValueError(f"{label} {tempat}: baris terakhir harus tanpa batas atas (kosongkan), supaya "
                                 f"penghasilan di atas batas tertinggi tetap punya tarif.")
            num = _angka_tarif(label, tempat, "batas atas", mentah)
            if num < 0:
                raise ValueError(f"{label} {tempat}: batas atas tidak boleh negatif.")
            if sebelumnya is not None and num <= sebelumnya:
                raise ValueError(f"{label} {tempat}: batas atas {_ribuan(num)} harus lebih besar dari batas baris "
                                 f"sebelumnya ({_ribuan(sebelumnya)}).")
            sebelumnya = num
            batas = int(num) if float(num).is_integer() else num
        tarif = _angka_tarif(label, tempat, "tarif", r.get("tarif_pct"))
        if tarif < 0 or tarif > 100:
            raise ValueError(f"{label} {tempat}: tarif {tarif:g}% di luar 0–100%.")
        out.append({"batas_atas": batas, "tarif_pct": float(tarif)})
    return out


def _tarif_berjenjang(entry: Dict[str, Any], value: Any) -> List[Dict[str, Any]]:
    """Tabel tanpa kolom `kategori` diperiksa utuh; tabel BERKATEGORI (kolom `kategori` berpilihan, mis.
    `hr.pph21.ter_table`) diperiksa per kategori dan SETIAP pilihan kategori wajib ada."""
    label = f"'{entry['label']}'"
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} harus berupa daftar baris tarif dan tidak boleh kosong.")
    for i, r in enumerate(value, 1):
        if not isinstance(r, dict):
            raise ValueError(f"{label} baris {i}: harus berisi batas atas dan tarif.")
    kol = next((c for c in entry.get("columns") or [] if c.get("name") == "kategori"), None)
    if not kol:
        return _periksa_jenjang(label, list(enumerate(value, 1)), "")
    pilihan = [str(o["value"]) for o in kol.get("options") or []]
    per_kat: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {k: [] for k in pilihan}
    for i, r in enumerate(value, 1):
        k = str(r.get("kategori") or "").strip()
        if k not in per_kat:
            raise ValueError(f"{label} baris {i}: kategori '{k}' tidak dikenal (pilihan: {', '.join(pilihan)}).")
        per_kat[k].append((i, r))
    kosong = [k for k, rows in per_kat.items() if not rows]
    if kosong:
        raise ValueError(f"{label}: kategori {', '.join(kosong)} wajib ada — setiap kategori "
                         f"({', '.join(pilihan)}) harus punya tabel sendiri.")
    out: List[Dict[str, Any]] = []
    for k in pilihan:
        out += [{"kategori": k, **b} for b in _periksa_jenjang(label, per_kat[k], f"kategori {k} ")]
    return out


def coerce(entry: Dict[str, Any], value: Any) -> Any:
    """FIX-3a — tipe dulu (`_coerce_type`), lalu isi (`value_format`); KF-T4 — lalu isi daftar (`items`) dan tabel
    berkelompok (`grouped_list`)."""
    clean = _check_format(entry, _coerce_type(entry, value))
    if entry.get("type") == "list":
        clean = _check_items(entry, clean)
    if entry.get("row_shape") == "grouped_list":
        clean = _check_grouped(entry, clean)
    return clean


# ── KF-T4 (KF-13) — pesan galat simpan memakai LABEL, bukan kunci teknis ─────────────────────────────────────────────
def _nama(entry: Dict[str, Any]) -> str:
    return f"'{entry.get('label') or entry['key']}'"


def _angka_satuan(entry: Dict[str, Any], num: Any) -> str:
    """Angka gaya Indonesia + satuan kunci: "Rp 1.000", "5%", "30 hari"."""
    try:
        n = float(num)
        teks = (f"{n:,.0f}" if n.is_integer() else f"{n:,.2f}".rstrip("0").rstrip("."))
        teks = teks.replace(",", "~").replace(".", ",").replace("~", ".")
    except (TypeError, ValueError):
        teks = str(num)
    unit = (entry.get("unit") or "").strip()
    if unit == "Rp" or entry.get("type") == "money":
        return f"Rp {teks}"
    if unit in ("%", "") and entry.get("type") == "pct":
        return f"{teks}%"
    return f"{teks} {unit}".strip()


def _role_known(rid: str) -> bool:
    try:
        from role_registry import is_role
        return bool(is_role(rid))
    except Exception:   # noqa: BLE001 — registry peran belum termuat: anggap dikenal (server memuatnya saat start)
        return True


def _role_choices() -> str:
    try:
        from role_registry import role_ids, role_label
        return ", ".join(role_label(r) for r in role_ids())
    except Exception:   # noqa: BLE001
        return ""


def _check_items(entry: Dict[str, Any], value: List[Any]) -> List[Any]:
    """Isi daftar: butir sah menurut `items`; tanpa butir kembar; `allocation.priority_order` dimulai `owner`."""
    nama, items = _nama(entry), entry.get("items") or ""
    out: List[Any] = []
    if items == "options":
        allowed = {str(o["value"]): o for o in entry.get("options") or []}
        pilihan = ", ".join(str(o.get("label") or o["value"]) for o in entry.get("options") or [])
        for x in value:
            if str(x) not in allowed:
                raise ValueError(f"{nama}: butir '{x}' tidak dikenal. Pilihan: {pilihan}.")
            out.append(allowed[str(x)]["value"])
    elif items == "roles":
        for x in value:
            rid = str(x or "").strip()
            if not rid or not _role_known(rid):
                raise ValueError(f"{nama}: butir '{x}' tidak dikenal. Pilihan: {_role_choices()}.")
            out.append(rid)
    elif items == "int_asc":
        for x in value:
            try:
                num = float(x)
            except (TypeError, ValueError):
                num = float("nan")
            if isinstance(x, bool) or not num == num or not float(num).is_integer() or num <= 0:
                raise ValueError(f"{nama}: butir '{x}' harus bilangan bulat lebih dari 0.")
            if out and int(num) <= out[-1]:
                raise ValueError(f"{nama}: butir harus makin besar dari kiri ke kanan ('{x}' tidak lebih besar dari "
                                 f"'{out[-1]}').")
            out.append(int(num))
    elif items == "text":
        for x in value:
            teks = str(x if x is not None else "").strip()
            if not teks:
                raise ValueError(f"{nama}: butir kosong — hapus butir kosong.")
            out.append(teks)
    else:
        out = list(value)
    seen: set = set()
    for x in out:
        k = str(x).strip().lower() if isinstance(x, str) else repr(x)
        if k in seen:
            raise ValueError(f"{nama}: butir '{x}' tertulis dua kali.")
        seen.add(k)
    if entry["key"] == "allocation.priority_order" and out and out[0] != "owner":
        pemilik = next((o.get("label") for o in entry.get("options") or [] if o.get("value") == "owner"), "owner")
        raise ValueError(f"{nama}: '{pemilik}' harus di urutan pertama.")
    return out


def _check_grouped(entry: Dict[str, Any], value: Any) -> Dict[str, Any]:
    """`grouped_list` — `{nilai kolom pertama: [baris]}`: kunci kelompok ada di pilihan kolom pertama; kolom ber-`ref:
    "role"` = id peran yang dikenal; kolom angka ≥ 0."""
    nama = _nama(entry)
    cols = entry.get("columns") or []
    if not isinstance(value, dict):
        raise ValueError(f"{nama} harus dikelompokkan per {cols[0].get('label', 'jenis') if cols else 'jenis'}.")
    first, rest = cols[0], cols[1:]
    allowed = {str(o["value"]): o.get("label") or o["value"] for o in first.get("options") or []}
    out: Dict[str, Any] = {}
    for grp, rows in value.items():
        if allowed and str(grp) not in allowed:
            raise ValueError(f"{nama}: butir '{grp}' tidak dikenal. Pilihan: {', '.join(allowed.values())}.")
        if not isinstance(rows, list):
            raise ValueError(f"{nama} {allowed.get(str(grp), grp)}: harus berupa daftar baris.")
        clean_rows = []
        for n, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise ValueError(f"{nama} baris {n}: isinya tidak sah.")
            r = dict(row)
            for c in rest:
                v = r.get(c["name"])
                if c.get("ref") == "role":
                    rid = str(v or "").strip()
                    if not rid or not _role_known(rid):
                        raise ValueError(f"{nama} baris {n}: {c.get('label', 'peran')} '{v}' tidak dikenal. "
                                         f"Pilihan: {_role_choices()}.")
                elif c.get("type") in ("money", "int", "decimal", "pct"):
                    try:
                        num = float(v if v not in (None, "") else 0)
                    except (TypeError, ValueError):
                        num = float("nan")
                    if isinstance(v, bool) or not num == num or num < 0:
                        raise ValueError(f"{nama} baris {n}: {c.get('label', c['name'])} harus angka 0 atau lebih.")
                    r[c["name"]] = int(num) if float(num).is_integer() else num
            clean_rows.append(r)
        out[str(grp)] = clean_rows
    return out


def _coerce_type(entry: Dict[str, Any], value: Any) -> Any:
    """Ubah nilai masukan menjadi tipe yang benar; lempar `ValueError` bila tak sah.

    Pesan error ditulis dalam Bahasa Indonesia agar bisa langsung ditampilkan ke user. KF-T4 — pesan menyebut label
    pengaturan, bukan kunci teknisnya.
    """
    typ = entry["type"]
    nama = _nama(entry)
    if typ == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in {"true", "false", "1", "0", "ya", "tidak"}:
            return value.lower() in {"true", "1", "ya"}
        if value in (0, 1):
            return bool(value)
        raise ValueError(f"{nama} harus Ya atau Tidak.")

    if typ in {"int", "duration"}:
        try:
            num = int(round(float(value)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{nama} harus angka bulat.") from exc
        return _bounded(entry, num)

    if typ in {"pct", "money", "decimal"}:
        from core_utils import parse_decimal
        try:
            num = parse_decimal(value, 4)
        except ValueError as exc:
            raise ValueError(f"{nama} harus angka ({exc}).") from exc
        if typ == "pct" and (num < 0 or num > 100) and entry.get("max") is None:
            raise ValueError(f"{nama} harus antara 0% dan 100%.")
        return _bounded(entry, num)

    if typ == "enum":
        allowed = [o["value"] for o in entry["options"]]
        if value not in allowed:
            pilihan = ", ".join(str(o.get("label") or o["value"]) for o in entry["options"])
            raise ValueError(f"{nama}: pilihan '{value}' tidak dikenal. Pilihan: {pilihan}.")
        return value

    if typ == "text":
        if not isinstance(value, str):
            raise ValueError(f"{nama} harus teks.")
        return value.strip()

    if typ == "list":
        if not isinstance(value, list):
            raise ValueError(f"{nama} harus berupa daftar.")
        return value

    if typ == "table":
        if not isinstance(value, (dict, list)):
            raise ValueError(f"{nama} harus berupa tabel.")
        return value

    return value


def _bounded(entry: Dict[str, Any], num: float) -> float:
    lo, hi = entry.get("min"), entry.get("max")
    if lo is not None and num < lo:
        raise ValueError(f"{_nama(entry)} paling kecil {_angka_satuan(entry, lo)}.")
    if hi is not None and num > hi:
        raise ValueError(f"{_nama(entry)} paling besar {_angka_satuan(entry, hi)}.")
    return num


def covers(leaf_key: str) -> Optional[Dict[str, Any]]:
    """Entri registry yang "mencakup" sebuah kunci daun.

    Kunci tabel didaftarkan pada level container (mis. `hr.ptkp_table`), sedangkan
    audit memindai daun (`hr.ptkp_table.TK0`). Fungsi ini menjembatani keduanya.
    """
    if leaf_key in _REGISTRY:
        return _REGISTRY[leaf_key]
    parts = leaf_key.split(".")
    for i in range(len(parts) - 1, 0, -1):
        cand = ".".join(parts[:i])
        if cand in _REGISTRY:
            return _REGISTRY[cand]
    return None


# ── Muat katalog (harus di paling bawah: E() sudah terdefinisi) ──────────────
import config_catalog_core  # noqa: E402,F401  (registrasi via side-effect)
import config_catalog_ops   # noqa: E402,F401
import config_catalog_finance  # noqa: E402,F401  (FASE G-1 — amandemen)
import config_catalog_documents  # noqa: E402,F401  (FASE G-4 — relasi dokumen)
import config_catalog_payment  # noqa: E402,F401  (FASE G-2 — rencana pembayaran & denda)
import config_catalog_bank  # noqa: E402,F401  (FASE G-8 — rekonsiliasi bank: skor & titipan)
import config_catalog_case  # noqa: E402,F401  (FASE G-9 — pusat kasus keuangan: SLA & ambang)
import config_catalog_contrabon  # noqa: E402,F401  (FASE G-7 — kontrabon: toleransi 3-way & pengingat)
import config_catalog_interco  # noqa: E402,F401  (FASE G-6 — antar-PT: mode harga, PPN, settlement)
import config_catalog_period  # noqa: E402,F401  (FASE G-5 — unlock periode: jendela & batas mundur)
import config_catalog_ai  # noqa: E402,F401  (Tanya KN F0 — asisten analitik)
import config_catalog_rfid  # noqa: E402,F401  (PREP-H — masa simpan bukti gate RFID)

import config_catalog_rnd  # noqa: E402,F401  (FASE F — R&D & Desain: lifecycle, sample, kontrak)
import config_catalog_approval_matrix  # noqa: E402,F401  (PS-20/D-14 — penegakan matriks persetujuan divisi)
import config_catalog_kontrol  # noqa: E402,F401  (KF-T6 — kontrol "harus dua orang" per PT)
import config_catalog_nilai  # noqa: E402,F401  (KF-T7 — nilai bisnis yang dulu ditulis mati di kode)
import config_catalog_budget  # noqa: E402,F401  (PK-39 — mode pemeriksaan anggaran)
