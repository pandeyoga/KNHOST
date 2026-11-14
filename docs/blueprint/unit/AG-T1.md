# AG-T1 — Asisten: rapikan kartu tindakan yang ada dan pasang lapisan penyedia model

| | |
|---|---|
| Gelombang | Modul — asisten keuangan |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PK-02 |
| Menutup temuan | AG-01, AG-02, AG-04, AG-05 |
| Keputusan | K-43, K-44 |
| Standar | §2.1, §2.4, §3.4 (N1, N3, N5), §4 (L1, L4), §5 (D9), §6 |
| Lingkungan uji | B; satu butir bersamaan di A |

## Tujuan

Kartu tindakan Tanya KN yang gagal berakhir **gagal** dan tidak bisa diulang, kartu lama kedaluwarsa, dan kartu hanya
bisa disetujui untuk PT tempat ia disiapkan. Pencarian pemasok, gudang, dan sales oleh asisten hanya mengembalikan data
PT pengguna. Mesin percakapan berbicara dengan penyedia model lewat satu lapisan yang bisa diganti, sehingga semua unit
`AG-*` berikutnya bisa diuji dengan pelaksana tiruan tanpa panggilan ke luar.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`. AG-01 belum pernah dijalankan; uji U1 unit ini yang membuktikannya.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Ada tiga jenis kartu: draf PO, pengingat penagihan ke sales, tindak lanjut pelanggan tidak aktif | `backend/services/ai_actions.py:19` (`TYPES`) |
| 2 | Saat disetujui kartu diklaim `pending → running`; bila pelaksana melempar galat, status dikembalikan ke `pending` | `backend/services/ai_actions.py:208-210` (`confirm`) |
| 3 | Draf PO membuat satu PO per pemasok di dalam satu putaran; PO pertama sudah tersimpan saat PO kedua gagal, lalu kartu kembali `pending` → menyetujui lagi membuat PO pertama dua kali (AG-01) | `backend/services/ai_actions.py:166` (`_exec_po`) |
| 4 | Pemeriksaan izin dan "semua qty nol" dijalankan **sesudah** klaim, jadi kesalahan isian ikut memicu jalur butir 2 | `backend/services/ai_actions.py:160` (`has_permission`) |
| 5 | Dokumen kartu tidak punya masa berlaku (AG-02) | `backend/services/ai_actions.py:131` (`propose_action`) |
| 6 | PT kartu = PT aktif; pada mode "Semua PT" diambil PT pertama dalam cakupan tanpa memberi tahu pengguna | `backend/services/ai_actions.py:127` (`entity_id`) |
| 7 | Endpoint setujui tidak membawa konteks PT, sehingga PT kartu tidak diadu ulang dengan akses pengguna saat itu (AG-02) | `backend/routers/ai_assist.py:19` (`confirm_action`) |
| 8 | Pencarian `supplier`, `warehouse`, dan `sales_person` tanpa saringan PT; `customer` sudah disaring (AG-04) | `backend/services/ai_tools.py:364-366` (`spec`) |
| 9 | Hasil pencarian selalu lima teratas walau skema menawarkan `limit` | `backend/services/ai_tools.py:378` (`cands`) |
| 10 | Skema alat menawarkan 11 jenis dokumen; server melayani 7. Tidak dilayani: `delivery_note`, `tax_invoice`, `ar_receipt`, `roll` (AG-05) | `backend/data/ai/tools_kn_analitik_v1.json:842` (`doc_type`) · `backend/services/ai_tools.py:397` (`get_document`) |
| 11 | Skema menawarkan 19 laporan; `hr_summary` tidak punya pelaksana dan hanya menghasilkan peringatan | `backend/data/ai/tools_kn_analitik_v1.json:642` (`report`) · `backend/services/ai_tools.py:355` (`run_report`) |
| 12 | Skema menawarkan 9 jenis pencarian; server melayani 5. Tidak dilayani: `makloon_partner`, `category`, `entity`, `city` | `backend/data/ai/tools_kn_analitik_v1.json:803` (`kind`) · `backend/services/ai_tools.py:361` (`find_entities`) |
| 13 | Pustaka klien penyedia model dipanggil langsung di tiga tempat | `backend/services/ai_chat_service.py:199` (`client`) · `backend/services/ai_chat_service.py:328` (`job_ai_prewarm`) · `backend/services/ai_narrative.py:85` (`_ai_text`) |
| 14 | "Mode uji" hanya mengganti jawaban dengan templat; putaran alat tidak bisa diuji tanpa penyedia sungguhan | `backend/services/ai_chat_service.py:65` (`_is_mock`) |
| 15 | Harga per model ditulis di kode | `backend/services/ai_cost.py:12` (`PRICES`) |
| 16 | Label pengaturan dan pesan layar menyebut nama penyedia | `backend/config_catalog_ai.py:40` (`ai.enabled`) · `backend/services/ai_chat_service.py:173` (`chat_events`) |
| 17 | Kartu di layar mengenal tiga status selain menunggu; tidak ada tampilan gagal atau kedaluwarsa | `frontend/src/features/tanya/TanyaActionCard.jsx:8` (`STATUS`) |
| 18 | Koleksi `ai_action_proposals` tidak terdaftar di registri koleksi milik pengguna | `backend/entity_scope.py:252` (`USER_SCOPED_COLLECTIONS`) |

Alat bisa dipanggil tanpa model lewat `POST /api/ai/tools/{tool}` (`backend/routers/ai_analytics.py:104`, `run_tool`);
uji unit ini memakainya untuk menyiapkan kartu.

## Perubahan

### Data

Koleksi `ai_action_proposals` (sudah ada) mendapat:

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `expires_at` | teks ISO UTC | ya, kartu baru | `created_at` + nilai `ai.kartu_masa_berlaku_jam` untuk PT kartu |
| `status` | teks | ya | Nilai baru `failed` dan `expired` di samping `pending`, `running`, `confirmed`, `dismissed` |
| `result` | daftar | tidak | Diisi **bertahap**: tiap PO/pengingat yang berhasil langsung ditambahkan, sebelum butir berikutnya dijalankan |
| `error` | teks ≤ 500 | bila `failed` | Pesan galat asli dari pelaksana |
| `finished_at` | teks ISO UTC | bila selesai | Saat status menjadi `confirmed`, `failed`, `dismissed`, atau `expired` |

Transisi yang sah: `pending → running → confirmed`, `pending → running → failed`, `pending → dismissed`,
`pending → expired`. Tidak ada transisi kembali ke `pending`.

Indeks: `id` unik; `(user_id, status, created_at)`. Koleksi ditambahkan ke `USER_SCOPED_COLLECTIONS` dan dicatat di
`ENTITY_REGISTRY.md` (D9).

Data lama, tanpa skrip migrasi: kartu `pending` tanpa `expires_at` dianggap berlaku sampai `created_at` + masa berlaku;
kartu `running` yang tidak berubah lebih dari 10 menit (batas teknis, konstanta) dianggap proses mati dan menjadi
`failed` dengan pesan "Proses berhenti sebelum selesai. Periksa daftar PO sebelum meminta draf baru." Keduanya
diterapkan saat kartu dibaca.

### Server

**Kartu** — `backend/services/ai_actions.py`:

| Fungsi | Perubahan |
|---|---|
| `propose_action(args, user, ctx, session_id)` | Mode "Semua PT" (`ctx.view_all`) ditolak dengan pesan alat "Pilih satu PT dulu. Tindakan tidak bisa disiapkan dalam mode Semua PT." Mengisi `expires_at` |
| `load(pid, user)` | Menerapkan kedaluwarsa dan "proses mati" sebelum mengembalikan dokumen |
| `confirm(pid, user, edits, ctx)` | Urutan baru di bawah. Tanda tangan bertambah `ctx` |
| `dismiss(pid, user)` | Menolak kartu kedaluwarsa dengan pesan yang sama seperti `confirm` |

Urutan `confirm`:

1. Muat kartu; bukan pembuatnya → 403 (pesan lama).
2. Kedaluwarsa → status `expired`, 409.
3. `entity_id` kartu tidak ada di `ctx.allowed_entity_ids` → 403. PT aktif berbeda, atau mode "Semua PT" → 409.
4. Periksa izin dan terapkan perubahan isian (`_apply_edits`). Galat di sini (403, 400) **tidak mengubah status**.
5. Klaim atomik `pending → running`; gagal klaim → 409.
6. Jalankan. Tiap butir yang berhasil langsung disimpan ke `result`.
7. Semua berhasil → `confirmed`. Ada galat → berhenti, `failed`, simpan `error`; butir yang sudah jadi tetap di `result`.

`POST /api/ai/actions/{pid}/confirm` (`backend/routers/ai_assist.py`) meneruskan `await entity_ctx(request)`.
Jawaban langkah 6–7 selalu 200 berisi dokumen kartu; `status` di dalamnya `confirmed` atau `failed`.

| Keadaan | Kode | Pesan |
|---|---|---|
| Kartu kedaluwarsa | 409 | "Draf ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi." |
| PT kartu tidak lagi bisa diakses | 403 | "Anda tidak lagi punya akses ke PT draf ini." |
| PT aktif berbeda atau mode Semua PT | 409 | "Draf ini disiapkan untuk {nama PT}. Pindah ke PT itu lalu setujui lagi." |
| Sudah diproses, gagal, atau diabaikan | 409 | "Draf ini sudah diproses" (teks lama) |
| Gagal di tengah (isi `error`) | 200 | "{pesan asli}. Yang sudah dibuat: {daftar nomor}." bila ada hasil sebagian |

**Pencarian** — `find_entities`: `supplier` disaring dengan `resolve_list_scope_inherit("suppliers", …)`
(`backend/entity_scope.py:567`); `warehouse` dengan `usable_query(entity_id)`
(`backend/services/warehouse_scope_service.py:78`) untuk tiap PT dalam cakupan; `sales_person` hanya akun yang
`home_entity_id` atau `allowed_entity_ids`-nya beririsan dengan cakupan. `limit` dihormati (1–20, bawaan 5).

**Skema alat** — `backend/data/ai/tools_kn_analitik_v1.json`: nilai yang tidak dilayani (butir 10–12) dicabut dari
`enum`. Ditambah satu uji statik yang membandingkan tiap `enum` dengan kunci yang dilayani kode.

**Lapisan penyedia** — berkas baru `backend/services/ai_provider.py`:

```python
@dataclass
class ToolCall:   id: str; name: str; arguments: dict
@dataclass
class ModelTurn:  text: str; tool_calls: list[ToolCall]; usage: dict; carry: list   # carry = butir mentah yang wajib dikirim balik

class ModelProvider(Protocol):
    name: str
    async def run_turn(self, *, model: str, instructions: list[str], tools: list[dict], conversation: list,
                       effort: str, max_output_tokens: int,
                       on_text: Callable[[str], Awaitable[None]] | None = None) -> ModelTurn: ...
    async def short_text(self, *, model: str, instructions: str, content: str, max_output_tokens: int) -> tuple[str, dict]: ...
    async def prewarm(self, *, model: str, instructions: list[str], tools: list[dict]) -> dict: ...
    def price_of(self, model: str) -> dict | None: ...

async def active_provider() -> ModelProvider | None      # None = tidak ada kunci atau fitur mati
def set_test_provider(p: ModelProvider | None) -> None   # hanya dipanggil tes
```

Pelaksana tiruan — berkas baru `backend/services/ai_provider_fake.py`: `ScriptedProvider(script)` dengan `script` =
daftar langkah `{"tool": nama, "args": {...}}` atau `{"text": "..."}`, atau fungsi `(conversation) -> langkah`.
Ia mencatat setiap permintaan di `.calls` (instruksi, daftar alat, percakapan) supaya tes bisa memeriksa apa yang
dikirim ke penyedia.

Pemanggil dialihkan: `_model_loop`, `job_ai_prewarm`, dan `_ai_text` memakai `active_provider()`; tabel harga pindah ke
`price_of` pelaksana (angka tidak berubah). Model tetap dibaca dari `ai.model_main` dan `ai.model_fast`. Bentuk event
SSE ke layar tidak berubah. Label dan teks bantu kunci `ai.*` serta pesan layar yang menyebut nama penyedia diganti
"penyedia model" (`00` §7 butir 8); nilai bawaan kunci tidak diubah.

### Pengaturan

| Field | Nilai |
|---|---|
| key | `ai.kartu_masa_berlaku_jam` |
| group · type | `asisten-analitik` · `int` |
| default · min · max · unit | 24 · 1 · 168 · jam |
| scopes | `("global", "entity")` |
| label | "Kartu tindakan asisten berlaku selama (jam)" |
| help | "Kartu yang belum disetujui setelah waktu ini tidak bisa dijalankan dan harus disiapkan ulang." |
| impact | "Lebih kecil = kartu lebih cepat hangus; lebih besar = kartu lama masih bisa disetujui walau data mungkin sudah berubah." |
| example | "24 → kartu yang dibuat Senin 09.00 hangus Selasa 09.00" |
| risk · requires_reason | `low` · tidak |
| permission | `("settings", "manage")` |
| consumers | `services/ai_actions.py:propose_action` |

### Izin dan peran

Tidak ada.

### Layar

Tanya KN › kartu tindakan di percakapan — `frontend/src/features/tanya/TanyaActionCard.jsx`:

- Kartu menunggu menampilkan satu baris di bawah judul: "PT: {nama PT} · berlaku sampai {tanggal, jam} WIB".
- Mode "Semua PT" atau PT aktif berbeda: tombol setujui mati dengan petunjuk "Pindah ke {nama PT} untuk menyetujui."
- Status baru: **Gagal** — "Gagal: {pesan}"; bila ada hasil sebagian, baris kedua "Sudah dibuat sebelum gagal: {daftar}";
  baris ketiga "Kartu ini tidak bisa diulang. Minta asisten menyiapkan draf baru untuk sisanya."
  **Kedaluwarsa** — "Draf ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi."
- Label tombol tidak berubah: "Setujui & buat PO", "Setujui & kirim ke sales", "Abaikan".

## Uji penerimaan

Persiapan bersama (fixture, disisipkan langsung): pemasok **S1** dan **S2** milik `ent_ksc`, pemasok **S3** milik
`ent_kanda`, pemasok **S4** ber-entitas `all`; produk **P1** (sumber S1) dan **P2** (sumber S2); satu gudang yang boleh
dipakai `ent_ksc` dan satu gudang khusus `ent_kanda`; akun `adm` (admin seed). Kartu disiapkan lewat
`POST /api/ai/tools/propose_action` dengan `X-Entity-Id: ent_ksc`.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | Kartu draf PO berisi P1 dan P2 (dua pemasok → dua PO). Pembuat PO dipaksa gagal pada panggilan kedua dengan 400 "Periode tertutup" | `confirm` | 200; `status` = `failed`; `result` memuat 1 nomor PO; `error` memuat "Periode tertutup"; jumlah `purchase_orders` = 1 |
| U2 | B | Lanjutan U1 | `confirm` lagi | 409 "Draf ini sudah diproses"; jumlah `purchase_orders` tetap 1 (sebelum perbaikan: 2 atau lebih) |
| U3 | B | Kartu draf PO berisi P1 | `confirm` dua kali berurutan | Pertama 200 `confirmed`; kedua 409; jumlah PO = 1 |
| U4 | A | Sama dengan U3 | Dua `confirm` dikirim bersamaan | Tepat satu 200 dan satu 409; jumlah PO = 1 |
| U5 | B | Kartu baru; `expires_at` digeser ke satu menit lalu | `confirm` | 409 "Draf ini sudah kedaluwarsa…"; `status` di database `expired`; jumlah PO = 0 |
| U6 | B | Kartu lama tanpa `expires_at`, `created_at` 30 jam lalu; pengaturan 24 | `GET /api/ai/actions/{id}` | `status` = `expired` (30 > 24) |
| U7 | B | `ai.kartu_masa_berlaku_jam` = 48 khusus `ent_ksc`; kartu sama dengan U6 | `GET` kartu `ent_ksc`; `GET` kartu serupa milik `ent_kanda` | `ent_ksc`: `pending` (30 < 48); `ent_kanda`: `expired` (bawaan 24) |
| U8 | B | Kartu `ent_ksc` | `confirm` dengan `X-Entity-Id: ent_kanda`; lalu dengan `X-Entity-Id: all` | Keduanya 409 "Draf ini disiapkan untuk …"; `status` tetap `pending` |
| U9 | B | Kartu `ent_ksc`; `allowed_entity_ids` pembuat diubah menjadi hanya `ent_kanda` | `confirm` | 403; `status` tetap `pending`; jumlah PO = 0 |
| U10 | B | — | `propose_action` dengan `X-Entity-Id: all` | 400 "Pilih satu PT dulu…"; tidak ada dokumen kartu baru |
| U11 | B | Kartu draf PO berisi P1 | `confirm` dengan semua qty 0; lalu `confirm` dengan qty 5 | Pertama 400 dan status tidak pernah berubah selama permintaan (kode lama: `running` lalu `pending`); kedua 200 `confirmed` |
| U12 | B | Akun sales ber-PT `ent_ksc` | `POST /api/ai/tools/find_entities` `{"kind": "supplier", "query": "s"}` | Kandidat memuat S1, S2, S4; tidak memuat S3 |
| U13 | B | Sama | `find_entities` jenis `warehouse` dan `sales_person` | Gudang khusus `ent_kanda` dan akun sales ber-PT `ent_kanda` saja tidak muncul |
| U14 | B | — | Uji statik: tiap nilai `enum` `doc_type`, `report`, `kind` (alat `find_entities`) dibandingkan dengan yang dilayani kode | Jumlah nilai: 7, 18, 5; tidak ada nilai tanpa pelaksana |
| U15 | B | `ai.enabled` = ya; `set_test_provider(ScriptedProvider([{"tool": "find_entities", "args": {"kind": "supplier", "query": "s1"}}, {"text": "Ada satu pemasok."}]))` | `POST /api/ai/chat` | Event memuat `tool` bernama `find_entities` dan `done` berteks "Ada satu pemasok."; `.calls` berisi 2 permintaan; satu baris `ai_usage_log` berstatus `done` |
| U16 | B | — | Uji statik: berkas di `backend/services/` yang mengimpor pustaka klien penyedia model | Hanya modul pelaksana penyedia: `ai_provider.py` (Tanya KN), ditambah pelaksana fitur lain yang sudah ada (`ocr_openai_client.py`, `hr_ai_service.py`); `ai_chat_service.py` dan `ai_narrative.py` tidak lagi mengimpor |
| U17 | B | — | Putaran `t1_config.py` untuk `ai.kartu_masa_berlaku_jam` (nilai 0 dan 200) | Tulis global terbaca; lapisan PT hanya PT itu; 0 dan 200 → 400 |
| U18 | layar (uji jalan) | Kartu dari U1 | Buka percakapannya di Tanya KN | Tampil "Gagal: …", "Sudah dibuat sebelum gagal: …", tanpa tombol setujui |

## Langkah kerja

1. Tulis U1–U17 di `backend/tests_mem/test_AGT1_kartu.py` dan `test_AGT1_penyedia.py`; U1, U2, U5–U14 harus merah.
2. Lapisan penyedia dan pelaksana tiruan; alihkan tiga pemanggil. Tes Tanya KN yang ada di `backend/tests/` tetap hijau.
3. Kartu: masa berlaku, urutan `confirm`, hasil bertahap, status `failed` dan `expired`, pemeriksaan PT.
4. Pencarian bersaring PT; skema alat.
5. Pengaturan `ai.kartu_masa_berlaku_jam`; label netral.
6. Layar kartu; uji jalan U18.
7. Gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (koleksi `ai_action_proposals` beserta field baru); `CODEBASE_MAP.md` (`services/ai_provider.py`,
`services/ai_provider_fake.py`).

## Di luar lingkup

- Alat baca keuangan, pemanggil endpoint sendiri, penyamaran nama, pemeriksa angka sebagai penghalang → AG-T2.
- Mesin kartu umum (sidik data, kunci idempotensi, tab "Tindakan", daftar kartu) → AG-T3.
- Pelaksana penyedia kedua dan pengaturan pemilihnya: dibuat saat pelaksana kedua ada. Satu pilihan saja akan menjadi
  pengaturan yang tidak berefek (`02` §4 L5).
- Gerbang asisten yang masih memakai nama peran (`_ai_user`, `load`) → PR-T2; izin asisten keuangan → AG-T2.

## Asumsi dan risiko

- `ASUMSI:` masa berlaku 24 jam diambil dari rancangan `08` §4.3 dan dijadikan pengaturan per PT.
- `ASUMSI:` kartu hanya bisa disetujui saat PT aktif sama dengan PT kartu, bukan sekadar PT yang boleh diakses,
  supaya konfirmasi selalu menyebut PT yang benar (`02` §3.4 N5).
- `ASUMSI:` kartu yang gagal di tengah tidak dilanjutkan; pengguna meminta kartu baru untuk sisanya (rancangan: hasil
  "tidak pernah kembali menunggu").
- `ASUMSI:` pelaksanaan yang gagal dijawab 200 dengan `status: "failed"`, karena keputusan pengguna berhasil diproses;
  kode 4xx dipakai hanya untuk penolakan sebelum klaim.
- `RISIKO:` pengalihan ke lapisan penyedia mengubah jalur yang sudah berjalan. Membatalkan: kembalikan tiga pemanggil
  ke pemanggilan langsung; berkas lapisan tidak dibaca kode lain.
- `RISIKO:` pengguna yang terbiasa menyetujui ulang kartu setelah galat kini harus meminta draf baru. Teks kartu gagal
  mengatakannya.
