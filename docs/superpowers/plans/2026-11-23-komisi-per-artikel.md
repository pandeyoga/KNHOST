# Komisi per Artikel, Pengali yang Bisa Diatur, dan Tab "Skema & Tarif" — Rencana Pelaksanaan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Komisi otomatis bisa diatur per artikel (dengan pengecualian per varian), dikalikan pengali harga dan pengali
capaian yang diatur pemilik, memakai aturan yang berlaku saat pesanan dibuat, bisa dibayar bersama Lembar Insentif, dan
diatur dari satu tab "Skema & Tarif".

**Architecture:** Satu modul aturan baru `backend/services/commission_rules.py` memegang pencarian tarif, potret aturan
per baris pesanan, pengali harga, pengali capaian, dan pembekuan bulan; fungsi hitung per baris di sana murni (tanpa
basis data). Mesin lama `sales_force_service._compute_commission_per_sku` tetap pemilik pengulangan pesanan, fraksi
terbayar, bobot tim, dan batas margin, tetapi membaca aturan dari potret baris (`items[].commission_rule`). Pengali =
kunci Pusat Pengaturan (`commission.*`), tarif = data `incentive_rates` (+ `template_id`/`product_id`). Layar baru
`IncentiveSchemeView` menyematkan `SettingsBrowser` yang sudah ada untuk kunci pengaturan, plus tabel tarif artikel.

**Tech Stack:** FastAPI + Motor (MongoDB), Pydantic; React (CRA/craco) + jest; uji `backend/tests_mem` (mongomock).

**Spec:** `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` (disetujui pemilik 23 Nov 2026, `a944e69`).
Pelaksana membaca rancangan itu dulu; rencana ini memuat keputusan tambahan yang tidak ada di sana.

## Global Constraints

- Bahasa layar, pesan galat, label pengaturan, pesan commit: **Bahasa Indonesia**; tanpa kode mentah di layar (`02_STANDAR.md` §4).
- PT yang tidak mengubah apa pun mendapat komisi **sama persis** seperti sebelum rilis (anti-tujuan 1). Bawaan: `commission.price_basis = "diskon_baris"`, pita = satu baris ×1,0, aturan sumber = semua `ikut_pita`, pengali capaian mati.
- Aturan bisnis = kunci Pusat Pengaturan (`02_STANDAR.md` §2): daftar di `config_catalog_core.py`, baca lewat `services.config_resolver`, cadangan = `config_registry.require(key)["default"]`. Label ≤ 45 huruf; `risk="high"`, `requires_reason=True` untuk kunci yang mengubah uang.
- Wewenang = izin, bukan nama peran (`02_STANDAR.md` §3): lihat `sales_force.view`, ubah tarif `sales_force.update`, hapus `sales_force.delete`, kunci pengaturan = izin registrinya. Server menolak 403 berkalimat.
- Aturan berlaku = aturan saat **pesanan dibuat** (keputusan 2.a); amandemen tidak memotret ulang (amandemen hanya mengubah baris yang ada — `amendment_service._apply_changes`, tidak ada baris baru).
- Satu-satunya jalur pembuatan baris pesanan: `routers/sales_orders.py:create_order` (`db.sales_orders.insert_one` hanya di sana).
- Hitungan memakai pecahan + `round(…, 2)` seperti mesin sekarang (bukan sen).
- Sakelar mode gaji PT nyata tidak diubah agen (H5); bawaan `hr.payroll_commission_mode` tetap `accrue_then_settle`.
- Tidak menyentuh `deploy/docker-compose.yml`, `deploy/Dockerfile.*`; LF; tidak commit `.env`.
- Uji hemat (`03_LINGKUNGAN_UJI.md` §6): uji terarah per tugas; `tests_mem` penuh dan jest penuh **sekali** di Tugas 11.
- Commit diakhiri dua baris atribusi sesi (`Co-Authored-By: …`, `Claude-Session: …`); tanpa nama model di repo.

## Review Focus

1. **Tarif ditambahkan sesudah pesanan dibuat.** Pesanan yang dipotret "tanpa tarif" tetap tanpa komisi; pesanan baru
   mendapat tarif baru. Pengguna wajar mengira tarif baru berlaku mundur — layar dan uji harus menunjukkan sebaliknya
   (uji `test_KA5_U6`; teks bantuan di Tugas 9).
2. **Satu pesanan, baris campuran, dibayar sebagian.** Baris harga khusus berpengali tetap dan baris harga PT berpita
   dalam satu pesanan yang baru dibayar 40%: tiap baris memakai fraksi yang sama tetapi pengalinya sendiri (`test_KA5_U7`).
3. **"Semua PT" dan periode bukan bulan dengan pengali capaian menyala.** "Semua PT" → pengali ×1,0 dan rincian menulis
   alasannya; triwulan = Σ hasil per bulan (`test_KA6_U5`, `test_KA6_U6`).
4. **PT pindah ke "Keduanya" di tengah tahun.** Gaji bulan itu memuat komisi otomatis dan baris lembar; beban tidak
   terbukukan dua kali dan Hutang Insentif kembali 0 sesudah gaji (`test_KA7_U3`).
5. **Tarif artikel dihapus / Excel berisi kode artikel tak dikenal.** Pesanan lama tetap memakai tarif yang dipotret;
   baris Excel tak dikenal tampil "galat" dan tidak diterapkan (`test_KA5_U8`, `test_KA8_U6`).

## Peta berkas

| Berkas | Tanggung jawab |
|---|---|
| `backend/services/commission_rules.py` (baru) | Validasi nilai tabel, kunci tarif, indeks tarif, aturan PT, potret, pengali harga & pita, hitung baris, pengali capaian, pembekuan bulan |
| `backend/services/commission_rate_service.py` (baru) | Daftar artikel + tarif efektif, varian, ubah banyak, Excel unduh/pratinjau/terapkan |
| `backend/services/sales_force_service.py` | Mesin memakai potret; rincian per artikel; jumlah bulanan; simulasi |
| `backend/routers/incentive_rates.py` | Isian `template_id`/`product_id`/pengali khusus artikel; rute baru layar |
| `backend/routers/sales_orders.py` | Panggil `potret_pesanan` di `create_order` |
| `backend/bootstrap.py` | Isi awal `rate_key` tarif lama dan potret pesanan lama |
| `backend/config_catalog_core.py`, `backend/config_registry.py` | 6 kunci baru, sub-judul `komisi-pengali` |
| `backend/config_catalog_ops.py`, `services/hr_payroll_service.py`, `services/incentive_payroll.py` (+ pemakai mode) | Mode `auto_and_sheet` |
| `backend/services/config_simulator.py` | Simulator "Coba dulu" `commission_price`, `commission_achievement` |
| `backend/services/gl_service.py` | Pembekuan bulan saat akrual insentif dibukukan |
| `backend/indexes.py` | `uq_incentive_rate_key`, `uq_commission_period` |
| `frontend/src/features/incentive/IncentiveSchemeView.jsx` (+ `SchemeSourcePicker.jsx`, `ArticleRatesTable.jsx`, `SchemeSimulation.jsx`) (baru) | Tab "Skema & Tarif" |
| `frontend/src/features/incentive/MyIncentiveCard.jsx`, `features/home/SalesHome.jsx` | Rincian faktor per artikel |

ID uji: **KA** (Komisi per Artikel). Berkas uji backend `backend/tests_mem/test_KA<n>_<ringkas>.py`; jest
`frontend/src/features/__tests__/kaSkemaTarif.test.js`. Perintah uji dari root repo:
`python -m pytest backend/tests_mem/<berkas> -n 0 -q` · `cd frontend && CI=true npx craco test --watchAll=false <berkas>`.

---

### Task 1: Kunci Pusat Pengaturan pengali + validasi nilai tabel

**Files:**
- Modify: `backend/config_registry.py:82` (daftar `sections` kelompok penjualan: tambah `_S("komisi-pengali", "Komisi sales: pengali")` sesudah `komisi`)
- Modify: `backend/config_catalog_core.py` (sesudah `commission.discount_potong_rp`, ±baris 452)
- Create: `backend/services/commission_rules.py` (validasi + dua pembaca kunci)
- Modify: `backend/services/config_resolver.py:545-553` (kait validasi di `set_value`, pola `periksa_nilai` pengingat)
- Test: `backend/tests_mem/test_KA1_kunci_komisi.py`

**Interfaces:**
- Produces: `commission_rules.PRICE_KEYS = ("commission.price_basis", "commission.price_bands", "commission.price_source_rules")`,
  `ACH_KEYS = ("commission.achievement_multiplier", "commission.achievement_basis", "commission.achievement_tiers")`,
  `SUMBER_KHUSUS = ("special_approval", "customer", "special_order")`,
  `def periksa_nilai(key: str, value: Any) -> Any` (mengembalikan nilai ternormalisasi; `ValueError` berkalimat; kunci lain dikembalikan apa adanya),
  `async def aturan_pt(entity_id: Optional[str], hipotetis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]` — kunci
  `price_basis`, `price_bands`, `price_source_rules` (dilengkapi `ikut_pita` untuk sumber yang tidak ada), `acuan` (dari
  `insentif.harga_acuan`), `discount_threshold_type`, `discount_threshold`, `discount_mechanic`, `discount_factor`,
  `discount_potong_rp`, `default_margin_cap_pct`; `hipotetis` = `{kunci: nilai}` menimpa (simulasi),
  `async def aturan_capaian(entity_id: str, at: Optional[datetime] = None) -> Dict[str, Any]` → `{"aktif", "basis", "jenjang"}`
  lewat `config_resolver.resolve_keys(ACH_KEYS, {"entity_id": entity_id}, at=at)`.

Kunci (semua `group="penjualan"`, `section="komisi-pengali"`, `scopes=("global","entity")`, `risk="high"`,
`requires_reason=True`, izin sama dengan kunci `commission.*` lain; `consumers` = `services/commission_rules.py:aturan_pt`
untuk tiga kunci harga dan `services/commission_rules.py:aturan_capaian` untuk tiga kunci capaian):

| Kunci | Tipe | Bawaan | Kolom / pilihan |
|---|---|---|---|
| `commission.price_basis` | enum | `diskon_baris` | `diskon_baris` "Diskon baris (cara lama)" · `pricelist` "Selisih dari harga acuan" |
| `commission.price_bands` | table `row_shape="list"` | `[{"sampai_pct": None, "pengali": 1.0}]` | `sampai_pct` decimal (kosong = tanpa batas, bawaan kolom 100) · `pengali` decimal (bawaan 1,0) |
| `commission.price_source_rules` | table `row_shape="list"` | 3 baris `{"sumber": s, "cara": "ikut_pita", "pengali": 1.0}` untuk `SUMBER_KHUSUS` | `sumber` enum (Harga khusus · Harga pelanggan · Pesanan khusus) · `cara` enum (`ikut_pita` "Ikut cara harga" · `pengali_tetap` "Pengali tetap") · `pengali` decimal |
| `commission.achievement_multiplier` | bool | `False` | — |
| `commission.achievement_basis` | enum | `omzet_bersih` | `omzet_bersih` "Omzet bersih" · `uang_masuk` "Uang masuk" |
| `commission.achievement_tiers` | table `row_shape="list"` | `[{"capaian_min_pct": 0, "pengali": 1.0}]` | `capaian_min_pct` pct (bawaan kolom 100) · `pengali` decimal (bawaan 1,0) |

Aturan `periksa_nilai` (bawaan kolom dipilih supaya uji putaran KF-T8 — "tambah satu baris berisi bawaan kolom" — lolos):
- pita: daftar ≥ 1 baris; diurutkan `sampai_pct` naik, kosong paling akhir; tepat satu baris kosong; `sampai_pct` > 0 dan
  tidak kembar; `pengali` ≥ 0.
- aturan sumber: `sumber` ∈ `SUMBER_KHUSUS` tidak kembar (boleh kurang dari 3 — yang tidak ada = `ikut_pita`); `cara` sah; `pengali` ≥ 0.
- jenjang: ≥ 1 baris; urut `capaian_min_pct` naik; harus ada baris 0; tidak kembar; `pengali` ≥ 0.

- [ ] **Step 1: Tulis uji yang gagal**

```python
async def test_KA1_U1_bawaan_kunci(klien, kepala_admin):
    for key, bawaan in (("commission.price_basis", "diskon_baris"),
                        ("commission.price_bands", [{"sampai_pct": None, "pengali": 1.0}]),
                        ("commission.achievement_multiplier", False),
                        ("commission.achievement_basis", "omzet_bersih"),
                        ("commission.achievement_tiers", [{"capaian_min_pct": 0, "pengali": 1.0}])):
        assert await value_of(key, {"entity_id": "ent_ksc"}) == bawaan
    assert [r["cara"] for r in await value_of("commission.price_source_rules", {})] == ["ikut_pita"] * 3

def test_KA1_U2_pita_dinormalisasi():
    v = periksa_nilai("commission.price_bands", [{"sampai_pct": None, "pengali": 0}, {"sampai_pct": 10, "pengali": 0.5},
                                                 {"sampai_pct": 3, "pengali": 0.8}])
    assert v == [{"sampai_pct": 3, "pengali": 0.8}, {"sampai_pct": 10, "pengali": 0.5}, {"sampai_pct": None, "pengali": 0}]

@pytest.mark.parametrize("key,nilai", [
    ("commission.price_bands", []), ("commission.price_bands", [{"sampai_pct": 3, "pengali": 1}]),
    ("commission.price_bands", [{"sampai_pct": 3, "pengali": 1}, {"sampai_pct": 3, "pengali": 1}, {"sampai_pct": None, "pengali": 1}]),
    ("commission.price_bands", [{"sampai_pct": None, "pengali": -0.1}]),
    ("commission.price_source_rules", [{"sumber": "entity", "cara": "ikut_pita", "pengali": 1}]),
    ("commission.achievement_tiers", [{"capaian_min_pct": 80, "pengali": 1}])])
async def test_KA1_U3_nilai_tak_sah_400(klien, kepala_admin, key, nilai):
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json={"items": [{"key": key, "value": nilai, "scope_type": "global", "reason": "uji KA-1"}]})
    assert r.status_code == 400, r.text

async def test_KA1_U4_lapisan_pt(klien, kepala_admin):
    # PUT price_basis pricelist lapisan PT ent_kanda (beralasan) → hanya ent_kanda berubah
    assert (await aturan_pt("ent_kanda"))["price_basis"] == "pricelist"
    assert (await aturan_pt("ent_ksc"))["price_basis"] == "diskon_baris"
    assert (await aturan_pt("ent_ksc", {"commission.price_basis": "pricelist"}))["price_basis"] == "pricelist"
    assert [r["sumber"] for r in (await aturan_pt("ent_ksc"))["price_source_rules"]] == list(SUMBER_KHUSUS)
```

- [ ] **Step 2: Jalankan — gagal** (`KeyError`/`404` kunci belum terdaftar). `python -m pytest backend/tests_mem/test_KA1_kunci_komisi.py -n 0 -q`
- [ ] **Step 3: Daftarkan sub-judul + 6 kunci; tulis `periksa_nilai`, `aturan_pt`, `aturan_capaian`; kaitkan validasi di `set_value`** (`if key in PRICE_KEYS + ACH_KEYS: clean = periksa_nilai(key, clean)` di blok `try` yang sama dengan pemeriksa lain).
- [ ] **Step 4: Jalankan — lulus**, lalu uji putaran khusus kunci baru:
  `python -m pytest backend/tests_mem/test_KFT8_putaran_pengaturan.py -n 0 -q -k "price_ or achievement_"` → semua lulus;
  `python scripts/guardrails/verify_config_text.py` → 0 pelanggaran (istilah baru yang ditolak glosarium dicatat di
  `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.3).
- [ ] **Step 5: Commit** `feat(komisi): kunci pengali harga & capaian di Pusat Pengaturan (KA-1)`

---

### Task 2: Tarif per artikel dan pengecualian per varian (data + API)

**Files:**
- Modify: `backend/routers/incentive_rates.py` (payload, `_FIELDS`, `create_rate`, `update_rate`, cek kembar)
- Modify: `backend/services/commission_rules.py` (`rate_key`)
- Modify: `backend/bootstrap.py` (`backfill_incentive_rate_key`, dipanggil di `run_bootstrap` **sebelum** pembuatan indeks wajib)
- Modify: `backend/indexes.py` (`REQUIRED_UNIQUE_INDEXES` += `uq_incentive_rate_key`)
- Modify: `ENTITY_REGISTRY.md` §`incentive_rates` (field baru)
- Test: `backend/tests_mem/test_KA2_tarif_artikel.py`

**Interfaces:**
- Consumes: `commission_rules.periksa_nilai` (Task 1) untuk pita/aturan sumber khusus artikel.
- Produces: dokumen `incentive_rates` + `template_id: str`, `product_id: str`, `rate_key: str`
  (`"varian:<product_id>"` · `"artikel:<template_id>"` · `"kategori:<category>"`), `target_name`, `target_code`,
  `price_bands: Optional[list]`, `price_source_rules: Optional[list]` (None = ikut PT).
  `def rate_key(doc: Dict[str, Any]) -> str` di `commission_rules`.

Perilaku:
- `RatePayload` + `template_id: str = ""`, `product_id: str = ""`, `price_bands: Optional[List[Dict]] = None`,
  `price_source_rules: Optional[List[Dict]] = None`. Keduanya diisi → 400 "Pilih artikel atau varian, bukan keduanya.".
  `template_id` tak ada di `product_templates` → 400 "Artikel tidak ditemukan."; `product_id` tak ada → 400 "Varian tidak
  ditemukan.". Baris artikel/varian: `category` dipotret dari artikel/produk (isian `category` permintaan diabaikan),
  `target_name` = nama artikel/produk, `target_code` = `sku_prefix`/`sku`. Baris kategori: `category` wajib (pesan lama).
- Kembar → 409 "Tarif untuk {target_name atau category} di PT ini sudah ada." (cek aplikasi + indeks unik
  `(entity_id, rate_key)` parsial `rate_key` tak kosong, `DuplicateKeyError` → 409 yang sama).
- PATCH yang mengubah `entity_id`/`category`/`template_id`/`product_id` menghitung ulang `rate_key` (dan nama potret).
- `backfill_incentive_rate_key`: baris tanpa `rate_key` → `rate_key(doc)`; idempoten.

- [ ] **Step 1: Tulis uji yang gagal** — fixture: artikel `tpl_ka_mega` ("Batik Mega", `sku_prefix` "BTK-MEGA", kategori
  "Batik"), varian `prd_ka_mega_mrh`, `prd_ka_mega_bru` (`template_id="tpl_ka_mega"`).

```python
async def test_KA2_U1_tarif_artikel(klien, kepala_admin):
    r = await klien.post("/api/incentive-rates", headers=kepala_admin,
                         json={"entity_id": "ent_ksc", "template_id": "tpl_ka_mega", "category": "salah", "per_unit_amount": 3500})
    assert r.status_code == 200, r.text
    j = r.json()
    assert (j["rate_key"], j["category"], j["target_name"], j["target_code"]) == (
        "artikel:tpl_ka_mega", "Batik", "Batik Mega", "BTK-MEGA")

async def test_KA2_U2_kembar_409_dan_dua_kunci_400(klien, kepala_admin): ...  # kedua kalinya 409; template+product 400
async def test_KA2_U3_pengecualian_varian(klien, kepala_admin): ...           # rate_key "varian:prd_ka_mega_bru"
async def test_KA2_U4_pita_khusus_artikel_divalidasi(klien, kepala_admin):    # PATCH price_bands [] → 400
async def test_KA2_U5_isi_awal_rate_key(db):
    await db.incentive_rates.insert_one({"id": "irate_ka_lama", "entity_id": "all", "category": "Tenun", "per_unit_amount": 2500, "status": "active"})
    await bootstrap.backfill_incentive_rate_key()
    assert (await db.incentive_rates.find_one({"id": "irate_ka_lama"}))["rate_key"] == "kategori:Tenun"
def test_KA2_U6_indeks_wajib_terdaftar():
    assert any(i["name"] == "uq_incentive_rate_key" and i["collection"] == "incentive_rates" for i in REQUIRED_UNIQUE_INDEXES)
```

- [ ] **Step 2: Jalankan — gagal.** `python -m pytest backend/tests_mem/test_KA2_tarif_artikel.py -n 0 -q`
- [ ] **Step 3: Terapkan** perubahan router, `rate_key`, isi awal, indeks (pola `uq_component_code`, `_finder_dup`).
- [ ] **Step 4: Jalankan — lulus**; juga `python -m pytest backend/tests_mem/test_PK14_indeks_wajib.py backend/tests_mem/test_KMT5_kartu_sales.py -n 0 -q` lulus.
- [ ] **Step 5: Commit** `feat(komisi): tarif per artikel dan pengecualian varian (KA-2)`

---

### Task 3: Aturan murni — indeks tarif, aturan PT, potret, pengali harga, hitung baris

**Files:**
- Modify: `backend/services/commission_rules.py`
- Modify: `backend/services/sales_force_service.py:249-273` (`_discount_factor` pindah ke `commission_rules.faktor_diskon`; nama lama tetap sebagai alias)
- Modify: `backend/services/config_simulator.py` (simulator `commission_price`, `commission_achievement`; kunci Task 1 diberi `simulate=`)
- Test: `backend/tests_mem/test_KA3_aturan.py`

**Interfaces:**
- Consumes: `rate_key`, `aturan_pt`, `PRICE_KEYS`, `SUMBER_KHUSUS` (Task 1–2).
- Produces (semua di `commission_rules`):
  - `ACUAN_FIELD = {"daftar_pt": "list_price", "umum": "global_price", "batas_bawah": "floor_price"}`
  - `async def muat_indeks_tarif(entity_id: Optional[str]) -> Dict[str, Dict[str, Any]]` — `rate_key` → dokumen tarif aktif + `_lingkup` (`"pt"`/`"semua_pt"`); baris PT menimpa `"all"`; `entity_id` None/`"all"` = hanya `"all"`.
  - `def pilih_tarif(indeks, *, product_id: str, template_id: str, category: str) -> Optional[Dict[str, Any]]` — urutan varian → artikel → kategori; salinan dokumen + `asal_tingkat` (`varian`·`artikel`·`kategori`) + `asal_lingkup`.
  - `def potret(tarif: Optional[Dict], pt: Dict, *, artikel: Optional[Dict], sumber: str, waktu: str) -> Dict[str, Any]` — bentuk v1 di bawah.
  - `def sumber_harga(line: Dict) -> str` — `"special_order"` bila `price_source == "special_order"` atau `special_order_price`; selain itu `price_source` (kosong → `"global"`).
  - `def pilih_pita(pita: List[Dict], selisih_pct: float) -> float`
  - `def pilih_jenjang(jenjang: List[Dict], capaian_pct: float) -> float` — baris dengan `capaian_min_pct` terbesar ≤ capaian.
  - `def faktor_diskon(cfg: Dict, line: Dict, per_unit: float) -> Tuple[float, float]` (isi = `_discount_factor` lama, tak berubah).
  - `def pengali_harga(aturan: Dict, line: Dict) -> Tuple[float, float, str, Optional[float]]` → `(tarif_efektif, pengali, alasan, selisih_pct)`.
  - `def hitung_baris(aturan: Dict, line: Dict, *, fraksi: float, bobot: float, biaya: float, biaya_diketahui: bool, pengali_capaian: float) -> Dict[str, Any]` → `{"komisi", "komisi_penuh", "qty_dasar_terbayar", "tarif", "pengali_harga", "alasan_harga", "selisih_pct", "pengali_capaian", "dibatasi"}`.
  - `ALASAN_LABEL: Dict[str, str]` (teks layar per kode alasan).

Bentuk potret (disimpan di `items[].commission_rule`):

```python
{"v": 1, "sumber": "pesanan" | "isi_awal" | "saat_hitung", "dipotret_pada": "<iso>",
 "artikel": None | {"id": "...", "nama": "...", "kode": "..."},
 "tarif": None | {"id", "asal_tingkat", "asal_lingkup", "per_unit_amount", "margin_cap_pct",
                  "discount_threshold_type", "discount_threshold", "discount_mechanic", "discount_factor", "discount_potong_rp"},
 "price_basis": "...", "acuan": "...", "price_bands": [...], "price_source_rules": [...]}
```
Isian diskon & `margin_cap_pct` tarif = nilai baris tarif, kosong → nilai PT (sama dengan `eff_cfg = {**cfg, **rate_cfg}`
dan `rate_cfg.get("margin_cap_pct", margin_cap_pct_default)` sekarang). Pita/aturan sumber khusus artikel (bukan None)
menggantikan milik PT.

Algoritma `pengali_harga` (urutan menentukan hasil):
1. `tarif = aturan["tarif"]["per_unit_amount"]`; `s = sumber_harga(line)`.
2. `s ∈ SUMBER_KHUSUS` dan aturan sumbernya `pengali_tetap` → `(tarif, pengali, f"sumber_tetap:{s}", None)`.
3. Basis `pricelist`: `acuan = line[ACUAN_FIELD[aturan["acuan"]]]`; bila > 0: `bersih = line_total / quantity`,
   `selisih = (acuan − bersih) / acuan × 100`; `selisih ≤ 0` → `(tarif, 1.0, "harga_penuh", 0.0)`; selain itu
   `(tarif, pilih_pita(...), "pita", round(selisih, 2))`. Acuan kosong/0 → lanjut ke 4 dengan alasan `tanpa_pembanding`.
4. Basis `diskon_baris`: `faktor_diskon(...)` → alasan `diskon_lewat_ambang` bila hasilnya mengubah tarif/pengali,
   selain itu `diskon_baris`.

`pilih_pita`: baris pertama yang `selisih ≤ sampai_pct` (batas termasuk); baris kosong menangkap sisanya.
`hitung_baris`: `qty = base_quantity × fraksi`; `kotor = qty × tarif_efektif × pengali_harga × pengali_capaian`; batas
margin hanya bila `margin_cap_pct > 0` dan `biaya_diketahui` (rumus mesin sekarang); `komisi = max(min(kotor, batas), 0) × bobot`;
`dibatasi = kotor > batas`; `komisi_penuh` = sama dengan `fraksi = 1`.

- [ ] **Step 1: Tulis uji yang gagal** (fungsi murni; satu uji DB untuk `aturan_pt`/`muat_indeks_tarif`).

```python
# Indeks: kategori:Batik semua_pt 3000 · artikel:tpl_ka_mega pt(ent_ksc) 3500 · artikel:tpl_ka_mega semua_pt 3200 ·
#         varian:prd_ka_mega_bru pt(ent_ksc) 4000
def test_KA3_U1_urutan_tarif():
    assert _asal(pilih_tarif(IDX_KSC, product_id="prd_ka_mega_mrh", template_id="tpl_ka_mega", category="Batik")) == (3500, "artikel", "pt")
    assert _asal(pilih_tarif(IDX_KSC, product_id="prd_ka_mega_bru", template_id="tpl_ka_mega", category="Batik")) == (4000, "varian", "pt")
    assert _asal(pilih_tarif(IDX_KSC, product_id="prd_x", template_id="tpl_x", category="Batik")) == (3000, "kategori", "semua_pt")
    assert _asal(pilih_tarif(IDX_KANDA, product_id="prd_ka_mega_mrh", template_id="tpl_ka_mega", category="Batik")) == (3200, "artikel", "semua_pt")
    assert pilih_tarif(IDX_KSC, product_id="p", template_id="", category="Lurik") is None

# Pita [≤3 ×0,8 · ≤10 ×0,5 · sisa ×0] · basis pricelist · acuan daftar_pt · list_price 50.000 · qty 100
@pytest.mark.parametrize("bersih,harap", [(50_000, (1.0, "harga_penuh")), (51_000, (1.0, "harga_penuh")),
    (49_000, (0.8, "pita")), (48_500, (0.8, "pita")), (47_500, (0.5, "pita")), (44_000, (0.0, "pita"))])
def test_KA3_U2_pita(bersih, harap):
    _, f, alasan, _ = pengali_harga(ATURAN_PITA, _baris(bersih, list_price=50_000))
    assert (f, alasan) == harap

def test_KA3_U3_sumber_tetap():  # special_approval pengali_tetap 0,5 → 0,5 walau harga = acuan; special_order_price (price_source global) + aturan special_order 0,7 → 0,7
def test_KA3_U4_tanpa_pembanding():  # basis pricelist, list_price None → (tarif, 1.0, "tanpa_pembanding", None) (ambang diskon tak terlampaui)
def test_KA3_U5_acuan_batas_bawah():  # acuan batas_bawah: floor_price 45.000, bersih 44.100 → selisih 2% → 0,8
def test_KA3_U6_diskon_baris_sama_dengan_lama():
    # discount_percent 15 > ambang 10, tier_factor 0,5 → (3500, 0.5, "diskon_lewat_ambang", None) = faktor_diskon lama
def test_KA3_U7_hitung_baris():
    # base 100, fraksi 0,5, tarif 3.500, pita 0,8, capaian 1,1, bersih/dasar 49.000, biaya 35.000
    # kotor = 50 × 3.500 × 0,8 × 1,1 = 154.000; batas 50% × 50 × 14.000 = 350.000 → 154.000, tidak dibatasi
    # batas 10% → 70.000, dibatasi
    assert (h["komisi"], h["dibatasi"]) == (154_000, False); assert (h10["komisi"], h10["dibatasi"]) == (70_000, True)
def test_KA3_U8_pilih_jenjang():
    j = [{"capaian_min_pct": 0, "pengali": 0.5}, {"capaian_min_pct": 80, "pengali": 1.0}, {"capaian_min_pct": 100, "pengali": 1.2}]
    assert [pilih_jenjang(j, p) for p in (0, 79.9, 80, 99.9, 100, 250)] == [0.5, 0.5, 1.0, 1.0, 1.2, 1.2]
async def test_KA3_U9_simulator(klien, kepala_admin):    # POST simulator commission_price → langkah memuat "0,8"
```

- [ ] **Step 2: Jalankan — gagal.** `python -m pytest backend/tests_mem/test_KA3_aturan.py -n 0 -q`
- [ ] **Step 3: Terapkan** fungsi di atas; daftarkan dua simulator (pola `commission_discount`, memanggil
  `pengali_harga`/`pilih_jenjang`, tanpa rumus kedua) dan isi `simulate=` pada kunci Task 1.
- [ ] **Step 4: Jalankan — lulus**; `python scripts/audit_config_wiring.py` tidak menambah baris merah.
- [ ] **Step 5: Commit** `feat(komisi): aturan tarif, pengali harga, dan hitung baris (KA-3)`

---

### Task 4: Potret aturan saat pesanan dibuat + potret pesanan lama

**Files:**
- Modify: `backend/services/commission_rules.py` (`potret_pesanan`, `aturan_baris`)
- Modify: `backend/routers/sales_orders.py:~395` (sesudah `unit_cost` per baris, sebelum validasi potong minimum)
- Modify: `backend/bootstrap.py` (`backfill_so_line_commission_rule`, dipanggil di `run_bootstrap` sesudah `backfill_so_line_cost` dan `backfill_incentive_rate_key`)
- Modify: `ENTITY_REGISTRY.md` (`sales_orders.items[].commission_rule`)
- Test: `backend/tests_mem/test_KA4_potret_pesanan.py`

**Interfaces:**
- Consumes: `muat_indeks_tarif`, `pilih_tarif`, `aturan_pt`, `potret` (Task 3).
- Produces:
  - `async def potret_pesanan(entity_id: str, items: List[Dict], products: Dict[str, Dict], *, sumber: str = "pesanan") -> None` — mengisi `it["commission_rule"]` tiap baris (satu kueri artikel untuk semua `template_id`).
  - `async def aturan_baris(line: Dict, entity_id: Optional[str], cache: Dict[str, Any]) -> Dict` — potret baris bila ada; bila tidak, potret dari aturan sekarang dengan `sumber="saat_hitung"` (tidak ditulis ke basis data). `cache` menyimpan indeks, aturan PT, produk, artikel.

Pesanan lama dipotret **sekali saat aplikasi pertama kali menyala sesudah rilis** (`sumber="isi_awal"`, aturan saat itu
= aturan hari ini, jadi angka tidak berubah) — setara "saat pertama dihitung sesudah rilis" di rancangan 6.5a tanpa
menulis dari jalur baca. Galat potret di `create_order` tidak ditelan (pesanan gagal 500 sama seperti galat harga).

- [ ] **Step 1: Tulis uji yang gagal** (fixture pola `test_KMT1_pengalihan.py`: produk varian `prd_ka4_mrh` dengan
  `template_id="tpl_ka4"`, harga PT 55.000; tarif artikel `tpl_ka4` di `ent_ksc` 3.500).

```python
async def test_KA4_U1_pesanan_memotret_aturan(klien, db, uji):
    so = await _pesan(klien, uji["adm"], "cus_ka4_c1", pid="prd_ka4_mrh")
    r = (await db.sales_orders.find_one({"id": so["id"]}))["items"][0]["commission_rule"]
    assert (r["v"], r["sumber"], r["price_basis"], r["acuan"]) == (1, "pesanan", "diskon_baris", "daftar_pt")
    assert (r["tarif"]["per_unit_amount"], r["tarif"]["asal_tingkat"], r["tarif"]["asal_lingkup"]) == (3500, "artikel", "pt")
    assert r["artikel"] == {"id": "tpl_ka4", "nama": "Batik KA4", "kode": "BTK-KA4"}

async def test_KA4_U2_ubah_tarif_tidak_mengubah_potret(klien, db, uji):   # PATCH tarif 4.000 → potret pesanan U1 tetap 3.500; pesanan baru 4.000
async def test_KA4_U3_tanpa_tarif_dipotret_kosong(klien, db, uji):        # produk kategori tanpa tarif → r["tarif"] is None
async def test_KA4_U4_isi_awal_sekali(db):
    # sisip pesanan tanpa potret → backfill → sumber "isi_awal"; backfill kedua tidak mengubah dipotret_pada
```

- [ ] **Step 2: Jalankan — gagal.** `python -m pytest backend/tests_mem/test_KA4_potret_pesanan.py -n 0 -q`
- [ ] **Step 3: Terapkan** (`create_order`: satu panggilan `await commission_rules.potret_pesanan(entity_id, items, products)`).
- [ ] **Step 4: Jalankan — lulus**; `python -m pytest backend/tests_mem/test_KMT1_pengalihan.py backend/tests_mem/test_PK45_penjaga_cepat.py -n 0 -q` lulus.
- [ ] **Step 5: Commit** `feat(komisi): potret aturan komisi per baris pesanan (KA-4)`

---

### Task 5: Mesin komisi membaca potret + rincian per artikel

**Files:**
- Modify: `backend/services/sales_force_service.py:276-428` (`_compute_commission_per_sku`)
- Test: `backend/tests_mem/test_KA5_mesin.py`

**Interfaces:**
- Consumes: `aturan_baris`, `hitung_baris`, `ALASAN_LABEL` (Task 3–4); `pengali_capaian` disuntik Task 6 (sementara ×1,0).
- Produces: `_compute_commission_per_sku(sales_id, period, entity_id, settings, *, sumber_aturan: Optional[Callable[[Dict], Awaitable[Dict]]] = None)` — `sumber_aturan` (simulasi, Task 8) menggantikan `aturan_baris`.
  Baris `breakdown` (kunci lama tetap ada): `{"category", "sku", "name", "template_id", "qty_base", "commission",
  "rate", "rate_origin", "price_factor", "price_reason", "price_reason_label", "achievement_factor", "capped"}`;
  agregasi per (`template_id` atau `sku`, `rate`, `price_factor`, `price_reason`, `capped`); `name` = nama artikel
  bila ada, `sku` = kode artikel bila ada; `rate_origin` = teks "Tarif artikel (PT ini)" / "(Semua PT)", varian, kategori.
  Tanpa angka margin/HPP di keluaran.

Yang tidak berubah: pemilihan pesanan, `DEAD_STATUSES`, bobot `sales_team`, fraksi terbayar, `contributes`,
`cost_for_line`, bentuk kunci hasil teratas.

- [ ] **Step 1: Tulis uji yang gagal** (pesanan disisip langsung — dicatat sebagai fixture; hitung tangan di komentar).

```python
async def test_KA5_U1_tanpa_potret_sama_dengan_lama(db, f):
    # pola KM-T5 U5: tarif kategori Rp 500/m, batas margin 0, 1.000 m lunas → 500.000 (sama dengan sebelum rilis)
async def test_KA5_U2_diskon_lama_sama(db, f):
    # discount_percent 15, ambang 10, faktor 0,5 → 250.000 (= rumus lama)
async def test_KA5_U3_potret_dipakai_bukan_tarif_baru(db, f):
    # potret tarif 3.000; tarif sekarang 3.500; 100 yd lunas → 300.000
async def test_KA5_U4_pita_pricelist(db, f):
    # potret basis pricelist, pita contoh; 100 yd list 50.000 bersih 49.000 lunas, tarif 3.500 → 100×3.500×0,8 = 280.000
    # rincian: price_reason "pita", price_reason_label "2% di bawah harga acuan", rate_origin "Tarif artikel (PT ini)"
async def test_KA5_U5_batas_margin_ditandai_tanpa_angka(db, f):
    # capped True; kunci "margin", "cost", "unit_cost" tidak ada di baris rincian
async def test_KA5_U6_tarif_ditambah_sesudah_pesanan(db, f):   # Review Focus 1
    # pesanan dipotret tarif None, lalu tarif dibuat → komisi 0; pesanan baru (potret 3.500) → 350.000
async def test_KA5_U7_baris_campuran_bayar_sebagian(db, f):    # Review Focus 2
    # pesanan 2 baris @100 yd: A harga khusus (pengali_tetap 0,5, tarif 3.000), B harga PT bersih 47.500 list 50.000
    # (pita 0,5, tarif 3.500); grand_total 9.500.000, bayar 3.800.000 → fraksi 0,4
    # A: 40 × 3.000 × 0,5 = 60.000 · B: 40 × 3.500 × 0,5 = 70.000 → total 130.000
async def test_KA5_U8_tarif_dihapus_pesanan_lama_tetap(db, klien, f):  # Review Focus 5 (bagian 1)
    # DELETE tarif artikel → pesanan berpotret 3.500 tetap 350.000
```

- [ ] **Step 2: Jalankan — gagal.** `python -m pytest backend/tests_mem/test_KA5_mesin.py -n 0 -q`
- [ ] **Step 3: Terapkan**: pengulangan baris memanggil `rule = await (sumber_aturan or (lambda ln: aturan_baris(ln, entity_id, cache)))(line)`;
  `rule["tarif"] is None` atau `per_unit_amount ≤ 0` → lewati (seperti sekarang); hitung via `hitung_baris`.
- [ ] **Step 4: Jalankan — lulus**; uji lama yang memakai mesin tetap lulus:
  `python -m pytest backend/tests_mem/test_KMT5_kartu_sales.py backend/tests_mem/test_KMT4_insentif_gaji.py backend/tests_mem/test_PK22_penggajian.py -n 0 -q`.
- [ ] **Step 5: Commit** `feat(komisi): mesin memakai aturan yang dipotret + rincian faktor (KA-5)`

---

### Task 6: Pengali capaian target + pembekuan bulan

**Files:**
- Modify: `backend/services/commission_rules.py` (`pengali_capaian`, `capaian_aktif`, `bekukan_periode`)
- Modify: `backend/services/sales_force_service.py` (`compute_commission`: jumlah bulanan; mesin memakai `pengali_capaian`)
- Modify: `backend/services/gl_service.py:post_incentive_accrual` (panggil `bekukan_periode` sebelum jurnal, di kedua cabang)
- Modify: `backend/indexes.py` (`uq_commission_period` pada `commission_period_rules (entity_id, period)`), `ENTITY_REGISTRY.md` (koleksi baru), `scripts/verify_contract.py` (kenali koleksi)
- Test: `backend/tests_mem/test_KA6_capaian.py`

**Interfaces:**
- Consumes: `aturan_capaian` (Task 1), `pilih_jenjang` (Task 3), `iach.resolve_period`, `iach.achievement(entity_id, per, defn, iach.saringan([sid]), "sales", False)` (baris `pct_omzet` / `pct_pencairan`; `None` = tanpa target), `idef.current_definition`, `ifacts.ensure_fresh(60)`; `config_resolver.resolve_keys(ACH_KEYS, ctx, at=…)`.
- Produces:
  - `async def capaian_aktif(entity_id: Optional[str]) -> bool`
  - `async def pengali_capaian(entity_id: Optional[str], sales_id: str, period: str) -> Tuple[float, Dict[str, Any]]` — info `{"aktif", "basis", "capaian_pct", "sumber_jenjang": "beku"|"akhir_bulan", "alasan"}`; alasan `mati` · `semua_pt` · `bukan_bulan` · `tanpa_target_bulanan` · `jenjang`.
  - `async def bekukan_periode(entity_id: str, period: str, *, oleh: str) -> Dict[str, Any]` — sisip-bila-belum-ada `commission_period_rules` `{id: "cpr_…", entity_id, period, achievement: {aktif, basis, jenjang}, sales: [{sales_id, total, breakdown}], recorded_at, recorded_by}`; idempoten (dokumen yang ada dikembalikan, tidak ditimpa).
  - Hasil `compute_commission` + `achievement_multiplier: {"factor", "info"}`.

Aturan: jenjang = dokumen beku bila ada, selain itu nilai kunci yang berlaku pada **akhir bulan komisi** (`at` = hari
terakhir bulan 23.59.59 WIB). Capaian = bulan komisi (bulan uang masuk), target bulanan saja. Periode triwulan/tahun dengan
pengali menyala = Σ hasil `_compute_commission_per_sku` per bulan (rincian digabung; `projection_full` dijumlah).

- [ ] **Step 1: Tulis uji yang gagal**

```python
async def test_KA6_U1_jenjang_akhir_bulan(db, f6):
    # jenjang dijadwalkan berlaku 30 Nov → dipakai untuk Nov; dijadwalkan 1 Des → tidak dipakai untuk Nov
async def test_KA6_U2_mati_bawaan_x1(db, f6):          # pengali menyala=False → factor 1.0, alasan "mati"
async def test_KA6_U3_capaian_omzet(db, f6):
    # target Nov omzet 400.000.000, omzet bersih 500.000.000 → 125% → ×1,2; komisi dasar 350.000 → 420.000
async def test_KA6_U4_tanpa_target_bulanan(db, f6):    # → 1.0, alasan "tanpa_target_bulanan"
async def test_KA6_U5_semua_pt(db, f6):                # Review Focus 3 — entity "all" → 1.0, alasan "semua_pt"
async def test_KA6_U6_triwulan_jumlah_bulanan(db, f6): # Review Focus 3 — Q4 = Σ Okt, Nov, Des per bulan
async def test_KA6_U7_beku_saat_akrual(klien, db, f6):
    # POST /api/sales/incentive/post-gl Nov → dokumen commission_period_rules (ent_ksc, 2026-11) ada;
    # jenjang diubah sesudahnya (berlaku mundur 1 Nov) → komisi Nov tetap pakai jenjang beku
async def test_KA6_U8_akrual_ulang_tidak_menimpa(db, f6):  # bekukan_periode kedua → recorded_at sama
```

- [ ] **Step 2: Jalankan — gagal.** `python -m pytest backend/tests_mem/test_KA6_capaian.py -n 0 -q`
- [ ] **Step 3: Terapkan.**
- [ ] **Step 4: Jalankan — lulus**; `python -m pytest backend/tests_mem/test_PK14_indeks_wajib.py backend/tests_mem/test_PK22_penggajian.py -n 0 -q`; `python scripts/verify_contract.py` hijau.
- [ ] **Step 5: Commit** `feat(komisi): pengali capaian target + pembekuan bulan saat akrual (KA-6)`

---

### Task 7: Sumber insentif "Keduanya dibayar" (`auto_and_sheet`)

**Files:**
- Modify: `backend/config_catalog_ops.py:801-815` (pilihan + `help`/`impact` menyebut "keduanya")
- Modify: `backend/services/hr_payroll_service.py:319` (`COMMISSION_MODES`)
- Modify: `backend/services/incentive_payroll.py` (konstanta + pembantu; `info_lembar`, `cek_hutang_insentif`)
- Modify: `backend/services/incentive_sheet_service.py:602`, `backend/services/posting_registry.py:267,288`,
  `backend/services/gl_service.py:3831`, `backend/services/home_service.py:461,466`, `backend/routers/crm.py:490,510`
- Modify: `frontend/src/features/incentive/IncentiveSetupView.jsx:593,602` (akrual juga untuk mode baru)
- Test: `backend/tests_mem/test_KA7_keduanya.py`

**Interfaces:**
- Produces di `incentive_payroll`: `MODE_BOTH = "auto_and_sheet"`, `LEMBAR_KE_GAJI = (MODE_SHEET, MODE_BOTH)`,
  `MODE_AKRU = (MODE_ACCRUE, MODE_BOTH)`, `def akru(mode: str) -> bool`, `def lembar_ke_gaji(mode: str) -> bool`.
  `TANPA_MESIN` tidak berubah. Semua titik di "Files" memakai pembantu ini, bukan perbandingan teks.

Perilaku: slip memuat komisi mesin (kolom komisi) **dan** masukan `INSENTIF` lembar; `post_payroll` mengakru hanya
bagian komisi mesin (`commission_parts(slips)[0]`); jurnal gaji Dr Hutang Insentif untuk keduanya; pengesahan lembar
lewat `sahkan_tertaut`; akrual manual & `gl-status.estimate` berlaku; beranda admin = belum dibayar lembar + estimasi
mesin (label `LABEL_CAMPURAN`); INV-KM-4 hanya memeriksa PT `sheet` (PT `auto_and_sheet` dilewati — saldo hutangnya
juga memuat akrual mesin; catat di docstring).

- [ ] **Step 1: Tulis uji yang gagal** (fixture & alur gaji mengikuti `test_KMT4_insentif_gaji.py` `f4`, PT `ent_kanda`
  diset `auto_and_sheet` lewat `config_resolver.set_value`, beralasan).

```python
async def test_KA7_U1_pilihan_terdaftar(klien, kepala_admin):   # PUT nilai auto_and_sheet → 200; label memuat "keduanya"
async def test_KA7_U2_lembar_tertaut(klien, db, f7):            # sahkan → payroll_linked True, gl_status "posted"
async def test_KA7_U3_gaji_memuat_keduanya(klien, db, f7):      # Review Focus 4
    # komisi mesin 1.000 m × 500 = 500.000; lembar 2.000.000
    # slip: komisi 500.000 + baris INSENTIF 2.000.000; jurnal INS-2026-11 = 500.000 (bukan 2.500.000);
    # jurnal gaji Dr 2-1500 2.500.000; saldo 2-1500 sesudah gaji = 0
async def test_KA7_U4_akrual_manual_boleh(klien, f7):           # POST /api/sales/incentive/post-gl → 200; gl-status estimate > 0
async def test_KA7_U5_komisi_tidak_409(klien, f7):              # GET /api/sales/commission → 200
async def test_KA7_U6_beranda_admin_campuran(klien, f7):        # incentive_payout_label == LABEL_CAMPURAN
```

- [ ] **Step 2: Jalankan — gagal.** `python -m pytest backend/tests_mem/test_KA7_keduanya.py -n 0 -q`
- [ ] **Step 3: Terapkan.**
- [ ] **Step 4: Jalankan — lulus**; `python -m pytest backend/tests_mem/test_KMT4_insentif_gaji.py backend/tests_mem/test_KMT5_kartu_sales.py backend/tests_mem/test_KFT4_registry.py -n 0 -q` lulus.
- [ ] **Step 5: Commit** `feat(komisi): sumber insentif keduanya dibayar (KA-7)`

---

### Task 8: API layar — daftar artikel, varian, ubah banyak, Excel, simulasi

**Files:**
- Create: `backend/services/commission_rate_service.py`
- Modify: `backend/routers/incentive_rates.py` (rute di bawah; rute tetap `/api/incentive-rates/...` sebelum `/{rate_id}`)
- Modify: `backend/services/sales_force_service.py` (`simulate_commission`)
- Modify: `CODEBASE_MAP.md` (berkas & rute baru)
- Test: `backend/tests_mem/test_KA8_api_layar.py`

**Interfaces:**
- Consumes: `muat_indeks_tarif`, `pilih_tarif`, `aturan_pt`, `potret`, `periksa_nilai`, `_compute_commission_per_sku(..., sumber_aturan=…)`.
- Produces (izin di kurung):
  - `GET /api/incentive-rates/categories?entity_id=` (`sales_force.view`) → `{"items": [{"category", "rate": {"per_unit_amount", "margin_cap_pct", "asal_lingkup", "rate_id"} | None, "articles": n, "articles_own_rate": n}]}` — kategori = gabungan kategori artikel aktif dan kategori yang punya tarif; urut nama.
  - `GET /api/incentive-rates/articles?entity_id=&search=&category=&page=1&page_size=50` (`sales_force.view`) →
    `{"items": [{"template_id", "name", "code", "category", "rate": {"per_unit_amount", "margin_cap_pct", "asal_tingkat", "asal_lingkup", "rate_id"} | None, "own_rate_id", "variant_exceptions"}], "total", "page", "page_size"}`; artikel aktif saja, urut nama.
  - `GET /api/incentive-rates/articles/{template_id}/variants?entity_id=` (`sales_force.view`) → `{"items": [{"product_id", "sku", "name", "rate": {…} | None, "follows": "artikel"|"kategori"|"tanpa_tarif"}]}`.
  - `POST /api/incentive-rates/bulk` `{entity_id, template_ids: [..], per_unit_amount, margin_cap_pct?: float, reason}` (`sales_force.update`) → `{"created": n, "updated": n}`; jejak audit per tarif berisi alasan.
  - `GET /api/incentive-rates/export?entity_id=` (`sales_force.view`) → xlsx, kolom: Kode artikel · Nama artikel · Kategori · Kode varian · Tarif per satuan dasar · Batas margin % · Asal tarif.
  - `POST /api/incentive-rates/import/preview` (multipart `file`, `entity_id`) (`sales_force.update`) → `{"rows": [{"baris", "kode_artikel", "kode_varian", "nama", "lama", "baru", "status": "baru"|"ubah"|"sama"|"galat", "pesan", "template_id", "product_id"}]}` — tidak menulis apa pun.
  - `POST /api/incentive-rates/import/apply` `{entity_id, rows: [{template_id|product_id, per_unit_amount, margin_cap_pct}], reason}` (`sales_force.update`) → `{"created", "updated"}`; baris tanpa id sah ditolak 400 seluruhnya.
  - `POST /api/incentive-rates/simulate` `{entity_id, sales_id, period, draft_rates: [{template_id|product_id|category, per_unit_amount, margin_cap_pct?}]}` (`sales_force.view`; PT tunggal wajib) → `{"sekarang": <hasil mesin>, "dengan_perubahan": <hasil mesin tanpa potret, aturan sekarang + draf>, "catatan": "Perubahan tarif berlaku untuk pesanan yang dibuat sesudah disimpan. Kolom kanan menunjukkan angka bila pesanan bulan ini dibuat dengan aturan baru."}`.
  - `async def simulate_commission(sales_id: str, period: str, entity_id: str, draft_rates: List[Dict]) -> Dict` di `sales_force_service`.

- [ ] **Step 1: Tulis uji yang gagal**

```python
async def test_KA8_U0_daftar_kategori(klien, kepala_admin, f8):
    # Batik: tarif kategori 3.000 (semua_pt), articles 2, articles_own_rate 1; Lurik: rate None, articles 1
async def test_KA8_U1_daftar_artikel_tarif_efektif(klien, kepala_admin, f8):
    # Batik Mega: tarif artikel PT 3.500 (asal artikel/pt, variant_exceptions 1); Batik Parang: ikut kategori 3.000
async def test_KA8_U2_varian_ikut_artikel(klien, kepala_admin, f8):     # merah follows "artikel", biru tarif sendiri 4.000
async def test_KA8_U3_ubah_banyak(klien, kepala_admin, f8):             # 2 artikel → created 1, updated 1; audit memuat alasan
async def test_KA8_U4_izin(klien, f8, peran_tanpa_acuan, sesi, akun):   # hanya sales_force.view → bulk/import apply 403, articles 200
async def test_KA8_U5_excel_unduh_unggah(klien, kepala_admin, f8):      # unduh → ubah satu tarif → pratinjau status "ubah", lain "sama"; apply → updated 1
async def test_KA8_U6_excel_kode_tak_dikenal(klien, kepala_admin, f8):  # Review Focus 5 — baris "XX-999" → status "galat", pesan "Artikel XX-999 tidak ditemukan."; apply tanpa baris itu
async def test_KA8_U7_simulasi(klien, kepala_admin, f8):
    # pesanan Nov berpotret 3.500, 100 yd lunas; draf tarif artikel 4.000 → sekarang 350.000, dengan_perubahan 400.000
```

- [ ] **Step 2: Jalankan — gagal.** `python -m pytest backend/tests_mem/test_KA8_api_layar.py -n 0 -q`
- [ ] **Step 3: Terapkan** (Excel memakai `openpyxl` seperti `incentive_achievement.export_xlsx`; daftar berhalaman, D4).
- [ ] **Step 4: Jalankan — lulus**; `python backend/tests_mem/sapuan_izin.py --awalan /api/incentive-rates` tanpa pelanggaran baru.
- [ ] **Step 5: Commit** `feat(komisi): API tarif artikel, Excel, dan simulasi (KA-8)`

---

### Task 9: Layar "Skema & Tarif"

**Files:**
- Create: `frontend/src/features/incentive/IncentiveSchemeView.jsx`, `SchemeSourcePicker.jsx`, `ArticleRatesTable.jsx`, `SchemeSimulation.jsx`
- Modify: `frontend/src/config/hubTabs.js:236` (tab `{ view: "incentive-scheme", label: "Skema & Tarif", roles: ["admin", "manager", "finance"] }` sesudah Lembar Insentif), `config/navMeta.js`, `appViewImports.js`, `AppViewRouter.jsx:357`
- Modify: `frontend/src/config/viewAliases.js:155-156` (`incentive-rates`, `incentive-schemes` → `incentive-scheme`)
- Modify: `frontend/src/features/settings/config/configGroupViews.js:24` (`COMMISSION_HOME.view = "incentive-scheme"`), `SettingsHub.jsx:53`, `features/settings/masters/EntityMastersView.jsx:33`
- Modify: `frontend/src/features/incentive/IncentiveSetupView.jsx` (bagian "Komisi otomatis (cara lama)" dicabut; kartu akrual pindah ke tab baru; tautan ke tab baru)
- Modify: `frontend/src/features/incentive/LegacySchemeEditor.jsx:160` (isian "Bonus per produk fokus" dicabut dari layar; data tidak dihapus)
- Modify: `backend/access_modules.py` (nav modul `sales_force` + `["hrd", "hr-kpi-hub", "incentive-scheme"]` sesudah blok KM-T5; modul `incentive` tidak ikut)
- Modify: `docs/KN_13_NAVIGATION_MAP.md`
- Test: `frontend/src/features/__tests__/kaSkemaTarif.test.js`

**Interfaces:**
- Consumes: rute Task 8; `PUT /api/config/values`; `useSettingsBrowser`/`SettingsBrowser` (`includeKeys` per bagian);
  `GET /api/incentive/targets` (`commission_mode(s)`) untuk mode PT; `GET /api/audit-logs/resource?entity_type=incentive_rate&entity_id=` (tombol "Riwayat" per tarif, hanya bila `audit.view`).
- Produces (diekspor untuk uji): `export function pilihanSumber(mode: string): "otomatis"|"lembar"|"keduanya"|"lain"`,
  `export function modeDariPilihan(pilihan: string, modeSekarang: string): string`,
  `export function butuhKonfirmasiAkru(pilihan: string, modeSekarang: string): boolean`.

Isi layar (urut, sesuai sketsa rancangan 6.6):
- Kepala: pemilih PT (PT tunggal wajib untuk ① dan simulasi; "Semua PT" = hanya baca dengan kalimat "Pilih satu PT").
- ① `SchemeSourcePicker`: tiga pilihan. `modeDariPilihan("otomatis", "pay_on_invoice") === "pay_on_invoice"`,
  `("otomatis", lain) → "accrue_then_settle"`, `("lembar", *) → "sheet"`, `("keduanya", *) → "auto_and_sheet"`.
  `pilihanSumber("off"|"pay_on_invoice")` → `"lain"`: tampil label registri + tautan ke Pusat Pengaturan. Simpan =
  `askReason` lalu `PUT /api/config/values` lapisan PT. "Keduanya" menampilkan peringatan "Insentif dari dua sumber
  dibayar bersama."; dari `pay_on_invoice` meminta konfirmasi "Cara pembukuan berubah menjadi dicadangkan tiap bulan."
- ② `ArticleRatesTable` — **pohon tiga tingkat Kategori → Artikel → Varian** (pemilik 23 Nov: "bisa dari beberapa
  level … user baru bisa memutuskan category dulu saja"). Tingkat atas = daftar kategori (`GET …/categories`): tarif
  kategori + "n artikel bertarif sendiri"; kategori tanpa tarif bertanda "Belum ada tarif — sales tidak mendapat komisi
  untuk kategori ini" dengan tombol "Atur tarif kategori". Buka kategori → artikelnya (`GET …/articles?category=`):
  tarif sendiri atau "ikut kategori Rp …". Buka artikel → varian (`GET …/variants`): "ikut artikel" / "ikut kategori" /
  tarif sendiri. Satu pop-up ubah tarif untuk ketiga tingkat (tarif, batas margin; pengali khusus hanya tingkat artikel);
  "Hapus tarif" di artikel/varian = kembali ikut tingkat di atasnya. Cari artikel lintas kategori; pilih beberapa artikel →
  "Ubah banyak"; "Unduh Excel" / "Unggah Excel" → pratinjau berstatus → "Terapkan" (alasan). Pengguna baru cukup
  mengisi tarif kategori; tingkat artikel/varian opsional. Teks bantuan: "Tarif berlaku untuk pesanan yang dibuat
  sesudah disimpan; pesanan lama memakai tarif saat pesanan dibuat."
- ③ `SettingsBrowser` `includeKeys` = `PRICE_KEYS` + `commission.discount_*`; ④ = `ACH_KEYS`; ⑤ = `commission.default_margin_cap_pct` ("bawaan batas margin untuk tarif baru"). `commission.incentive_unit` dan `commission.strategy` tidak ditampilkan.
- Kartu akrual bulanan (`KartuAkrual`, dipindah) dan `LegacySchemeEditor` (hanya bila `commission.strategy` = `achievement_tiered`).
- `SchemeSimulation`: pilih sales (roster PT) + bulan, draf tarif opsional → tabel per artikel: yard · tarif · pengali harga (+alasan) · pengali capaian · komisi, kolom "Sekarang" dan "Dengan perubahan", plus `catatan` server.
- Tombol tampil menurut izin (`canCurrent("sales_force", …)`); tanpa `sales_force.view` → kalimat izin, tanpa panggilan API.

- [ ] **Step 1: Tulis uji jest yang gagal**

```js
test("KA9 pemetaan sumber insentif", () => {
  expect(pilihanSumber("accrue_then_settle")).toBe("otomatis");
  expect(pilihanSumber("auto_and_sheet")).toBe("keduanya");
  expect(pilihanSumber("pay_on_invoice")).toBe("lain");
  expect(modeDariPilihan("otomatis", "pay_on_invoice")).toBe("pay_on_invoice");
  expect(modeDariPilihan("otomatis", "sheet")).toBe("accrue_then_settle");
  expect(modeDariPilihan("keduanya", "sheet")).toBe("auto_and_sheet");
  expect(butuhKonfirmasiAkru("keduanya", "pay_on_invoice")).toBe(true);
});
test("KA9 tab Skema & Tarif terdaftar dan alias lama mengarah ke sana", () => { /* HUB_TABS["hr-kpi-hub"], resolveDeepLinkTarget("incentive-rates") */ });
test("KA9 pohon tarif: kategori → artikel (ikut kategori / sendiri) → varian (ikut artikel)", async () => { /* mock GET categories + articles + variants */ });
test("KA9 kategori tanpa tarif menulis 'Belum ada tarif' dan tombol Atur tarif kategori", async () => {});
test("KA9 unggah Excel: pratinjau berstatus, Terapkan meminta alasan", async () => {});
test("KA9 tanpa izin ubah: tombol ubah/ubah banyak/unggah tidak tampil", async () => {});
test("KA9 Target & Aturan tidak lagi memuat bagian Komisi otomatis (cara lama)", async () => {});
test("KA9 LegacySchemeEditor tanpa isian Bonus per produk fokus", () => {});
```

- [ ] **Step 2: Jalankan — gagal.** `cd frontend && CI=true npx craco test --watchAll=false src/features/__tests__/kaSkemaTarif.test.js`
- [ ] **Step 3: Terapkan** (pola UI `docs/blueprint/04_POLA_UI.md`: kartu tetap, bilah saring dropdown, ubah di pop-up `FormModal`, `KNSelect`, `ErrorNotice`, `askReason`).
- [ ] **Step 4: Jalankan — lulus**; suite terkait: `kmt1TargetAturan`, `kmt5KartuSales` lulus (perbarui harapan uji lama yang menunjuk bagian yang dipindah, catat di pesan commit); `python scripts/guardrails/verify_access_catalog_nav.py` dan `python scripts/audit_sales_roles_ux.py` hijau.
- [ ] **Step 5: Commit** `feat(komisi): tab Skema & Tarif di SDM › Kinerja & Insentif (KA-9)`

---

### Task 10: Rincian faktor untuk sales

**Files:**
- Modify: `backend/services/incentive_me.py:88-102` (`komisi_otomatis` + `breakdown`)
- Modify: `frontend/src/features/incentive/MyIncentiveCard.jsx` (daftar "Rincian komisi otomatis")
- Modify: `frontend/src/features/home/SalesHome.jsx:153-180` (kolom Tarif · Pengali harga · Pengali capaian; judul "Rincian Komisi per Artikel")
- Test: `backend/tests_mem/test_KA5_mesin.py` (tambah U9), `frontend/src/features/__tests__/kaSkemaTarif.test.js` (tambah)

**Interfaces:**
- Consumes: baris `breakdown` Task 5, `achievement_multiplier` Task 6.
- Produces: `GET /api/incentive/me` → `auto_commission: {"mtd", "projection_month_end", "breakdown": [{"name", "sku", "qty_base", "rate", "rate_origin", "price_factor", "price_reason_label", "achievement_factor", "capped", "commission"}]}` (hanya kunci ini — daftar putih).

- [ ] **Step 1: Tulis uji yang gagal**

```python
async def test_KA5_U9_kartu_sales_rincian_tanpa_margin(klien, f):
    j = (await klien.get("/api/incentive/me", headers=f["h_sales"])).json()
    b = j["auto_commission"]["breakdown"][0]
    assert set(b) == {"name", "sku", "qty_base", "rate", "rate_origin", "price_factor", "price_reason_label",
                      "achievement_factor", "capped", "commission"}
```
```js
test("KA10 kartu: baris rincian menulis 'dibatasi batas margin' tanpa angka margin", () => {});
test("KA10 beranda sales: kolom tarif dan pengali tampil", () => {});
```

- [ ] **Step 2: Jalankan — gagal.**
- [ ] **Step 3: Terapkan.**
- [ ] **Step 4: Jalankan — lulus**; `kmt5KartuSales.test.js` lulus.
- [ ] **Step 5: Commit** `feat(komisi): rincian faktor komisi di kartu dan beranda sales (KA-10)`

---

### Task 11: Dokumen, uji penuh sekali, gate, serah-terima

**Files:**
- Modify: `memory/PRD.md` (fitur), `ENTITY_REGISTRY.md` (cek lengkap), `CODEBASE_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (istilah "artikel", "pengali", "pita harga" bila belum ada), `SESSION_HANDOFF.md` + `memory/SESSION_HANDOFF.md` (catatan teratas)
- Modify: `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §8 — tambah keputusan pelaksanaan: (a) pesanan lama dipotret saat aplikasi pertama menyala sesudah rilis; (b) aturan sumber `pengali_tetap` juga berlaku di basis diskon baris; (c) harga ≥ acuan selalu ×1,0, pita hanya untuk di bawah acuan; (d) INV-KM-4 melewati PT "Keduanya"; (e) riwayat per tarif lewat Jejak Audit, riwayat kunci lewat kartu pengaturan; (f) yang dibekukan saat akrual adalah
  ATURAN (potret baris + jenjang bulan); rincian per sales yang disimpan bersama akrual adalah catatan (D3), sedangkan
  gaji/kartu tetap menghitung dari aturan beku itu sehingga angka hanya berubah karena data sumber (bayar/retur)
- Create: `docs/superpowers/plans/2026-11-23-komisi-per-artikel-hasil.md` (ringkasan uji & tangkapan layar)

- [ ] **Step 1:** `python -m pytest backend/tests_mem -n 0 -q` sekali → catat angka lulus/gagal apa adanya.
- [ ] **Step 2:** `cd frontend && CI=true npx craco test --watchAll=false` sekali → catat angka (kendala lingkungan yang sudah tercatat di `03_LINGKUNGAN_UJI.md` §6 dirujuk, bukan diselidiki ulang).
- [ ] **Step 3:** `bash scripts/gate.sh` → nilai per pelanggaran dengan `python scripts/blueprint/bandingkan_pelanggaran_gate.py` terhadap garis dasar `origin/main`; pelanggaran baru = perbaiki dulu.
- [ ] **Step 4:** Uji layar satu alur ujung ke ujung (Playwright, data acuan): atur tarif artikel → pita pricelist → buat pesanan harga PT dan harga khusus → bayar → kartu sales menunjukkan faktor → simulasi; simpan tangkapan layar (skala 2) di laporan hasil.
- [ ] **Step 5:** Commit dokumen + laporan; push ke `claude/nifty-carson-jjx3c8` (bukan main).
