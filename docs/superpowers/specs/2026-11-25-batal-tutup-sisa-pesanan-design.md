# Rancangan — Tutup sisa pesanan & persetujuan pembatalan (A1 + A2)

Tanggal: 25 Nov 2026 · Status: **disetujui pemilik 25 Nov** (sudah diperiksa pembaca-builder; 7 pertanyaan dijawab) · Basis kode: `main` @ `a30efa0`

## 1. Maksud dan alasan

Penelusuran alur pembatalan (24–25 Nov) menemukan dua celah yang langsung terasa di operasional:

* **A1 — pesanan yang sudah dikirim sebagian tidak bisa ditutup sisanya.** Tombol Batalkan tertutup untuk status
  `partially_shipped`, dan PO punya "tutup-kurang" tetapi pesanan penjualan tidak. Kalau pelanggan tidak mau sisanya, sisa
  itu menggantung selamanya: roll tetap dipesan, plafon kredit tetap terpakai, gerbang CBD menagih nilai penuh, dan
  **komisi tetap dihitung dari jumlah yang dipesan** (mesin komisi membaca baris pesanan, bukan jumlah terkirim).
* **A2 — pembatalan tanpa persetujuan.** Pemegang `order.cancel` (bawaan: sales untuk pesanan miliknya, Admin Sales,
  Manager, Admin) membatalkan langsung dengan alasan — termasuk pesanan CBD yang sudah dibayar dan pesanan yang barangnya
  sudah disiapkan gudang.

Keputusan pemilik (25 Nov, "ikut saran"):

| # | Keputusan |
|---|---|
| A1-1 | Tutup sisa mengikuti aturan persetujuan yang sama dengan batal (A2) |
| A1-2 | Kelebihan uang (CBD/DP) sesudah sisa ditutup → **titipan pelanggan** (bukan langsung dikembalikan) |
| A1-3 | Tempo: piutang sudah per Surat Jalan → tidak perlu nota kredit; nilai pesanan turun, plafon kembali |
| A1-4 | Faktur Pajak per pesanan yang sudah terbit → **tutup sisa ditolak** sampai faktur dibatalkan/diganti (otomatis menyusul) |
| A1-5 | Sisa backorder ikut ditutup |
| A1-6 | Komisi atas barang yang tidak jadi dikirim **dipotong di bulan penutupan** (bulan lalu tidak diubah; kurang → terbawa ke bulan berikutnya); berlaku juga untuk batal sesudah bayar |
| A2-1 | Persetujuan wajib bila **sudah ada uang masuk ATAU barang sudah disiapkan gudang**; selain itu langsung |
| A2-2 | Penyetuju diatur di tabel kebijakan persetujuan, jenis baru "Pembatalan pesanan"; bawaan Manager + Finance |
| A2-3 | Pengaju yang memegang wewenang setuju → langsung jalan, tercatat "disetujui sendiri"; **sales pemilik pesanan tidak pernah bisa menyetujui pembatalannya sendiri** |
| A2-4 | Selama menunggu: stok tetap dipesan, pekerjaan gudang **ditahan** (tidak dibatalkan) |
| A2-5 | Ditolak → pesanan lanjut normal; pengaju diberi tahu alasannya |
| Cara | Pilihan 1: catatan permintaan yang menempel di pesanan (bukan koleksi baru) |

## 2. Sasaran, bukan sasaran, anti-sasaran

**Sasaran**
1. Pesanan `partially_shipped` bisa ditutup sisanya; sesudahnya angka pesanan (jumlah, nilai, komisi, plafon, gerbang CBD)
   sama dengan yang benar-benar dikirim.
2. Pembatalan/tutup sisa yang berisiko uang atau barang lewat satu pintu persetujuan yang bisa diatur per PT.
3. Satu mesin eksekusi: batal sesudah disetujui menjalankan logika batal yang **sudah ada** (`cancel_order`), bukan salinan.

**Bukan sasaran (unit ini)**
* A3 — transfer stok/PR pemenuhan ikut batal otomatis.
* A4 — batal sebagian baris di luar Pesanan Khusus.
* Draf Faktur Pajak pengganti otomatis (A1-4 opsi b).
* Mengubah logika gerbang RFID atau `gate_evaluator`.

**Anti-sasaran (gagal walau "jalan")**
* Ada jalan pintas yang membatalkan pesanan dibayar/disiapkan tanpa persetujuan (endpoint lama, aksi massal, AI, HP).
* Sales menyetujui pembatalan pesanannya sendiri lewat peran kustom.
* Barang terkirim saat permintaan batal masih menunggu.
* Tutup sisa mengubah jurnal atau piutang yang sudah tercatat per Surat Jalan.
* Komisi sales tetap menghitung jumlah yang tidak pernah dikirim.

## 3. Batasan

* Standar wajib `docs/blueprint/02_STANDAR.md`: wewenang dari izin (Z1–Z6), izin baru di empat tempat (§3.2), nilai
  aturan bisnis = pengaturan (§2), uji peran baku (`Tanpa Acuan`, `Manajer Kosong`).
* Keuangan: tidak ada jurnal baru untuk tutup sisa (uang muka dan titipan sama-sama 2-1400); baca
  `docs/finance/AUDIT_KEUANGAN_2026-11-13.md` sebelum menyentuh `ar_receipt_service`/`gl_service`.
* `dispatch_guard` (`services/loading_check_service.py`) boleh ditambah pemeriksaan **sebelum** pemeriksaan muat/RFID,
  seperti CR-T3; logika RFID tidak diubah (`docs/rfid/KEPUTUSAN_GATE_RFID.md`).
* Pola antrean: `services/approval_backlog_service.QUEUES` (view wajib layar nyata), `approval_kinds.APPROVAL_KINDS`
  (INV-APPR-01), `services/approval_policy_service` (KP-T4), `services/dual_control` (KF-T6).
* Uji hemat (`docs/blueprint/03_LINGKUNGAN_UJI.md` §6).

## 4. Pendekatan yang ditimbang

| Pendekatan | Untung | Rugi | Putusan |
|---|---|---|---|
| **1. Catatan `cancel_request` menempel di pesanan** + antrean baru + jenis persetujuan baru | Tanpa koleksi baru; riwayat ikut di pesanan; pola sama dengan verifikasi Admin Sales (`sales_orders.verification` + antrean `so_verify`) | Riwayat permintaan lintas pesanan dicari lewat kueri pesanan | **Dipilih pemilik** |
| 2. Dokumen permintaan terpisah (seperti `credit_overrides`) | Bernomor, daftar sendiri | Koleksi baru, tautan dua arah, lebih banyak titik konsistensi | Tidak dipilih |
| 3. Menumpang `pending_approvals[]` pesanan | Antrean sudah ada | `pending_approvals` menahan pesanan di tahap "menunggu persetujuan" (`so_approvals.all_approved`, `derive_stage_substatus`) — pesanan terkonfirmasi akan mundur tahap | Dibuang |

## 5. Rancangan

### 5.1 Data — `sales_orders.cancel_request`

Satu objek aktif per pesanan, riwayat di `cancel_requests[]` (append-only):

```
cancel_request = {
  id, action: "cancel" | "close_remaining",
  status: "pending" | "approved" | "rejected" | "withdrawn" | "void",
  reason, requested_by, requested_by_id, requested_at,
  needs_approval: bool, approval_basis: ["paid", "prepared"],   # alasan wajib-setuju, untuk layar
  amount: grand_total saat diajukan,                             # dasar rentang kebijakan
  decided_by, decided_by_id, decided_at, decision_note, self_approved: bool,
  result: {...}                                                   # ringkasan eksekusi (titipan, roll dilepas, dll.)
}
```

* Permintaan baru hanya bila tidak ada `cancel_request.status == "pending"` (klaim bersyarat; pakai `atomic_claim` seperti
  `cancel_order`).
* Keputusan/penarikan memindahkan objek ke `cancel_requests[]` dan mengosongkan `cancel_request` aktif (atau status
  final tetap di objek — pilihan builder, asal antrean hanya menghitung `pending`).
* Pesanan menjadi mati (kedaluwarsa, batal lewat jalur lain) → permintaan pending ditutup `void` beralasan.

### 5.2 Kapan wajib persetujuan (A2-1, pengaturan)

Kunci Pusat Pengaturan baru **`order.cancel_approval_when`** (per PT, enum), bawaan `dibayar_atau_disiapkan`:

| Nilai | Arti |
|---|---|
| `dibayar_atau_disiapkan` (bawaan) | wajib bila `paid_total > 0` **atau** barang sudah disiapkan |
| `selalu` | semua permintaan wajib disetujui |
| `tidak_pernah` | perilaku lama (langsung) |

"Barang sudah disiapkan" = ada roll pesanan berstatus di luar `reserved`/`available` (pola `so_line_cancel_service.check`)
**atau** tugas outbound aktif yang sudah mencatat ambil (`scan_log` jenis `pick`, `picked_qty > 0`) atau berstatus
`packing`/`staging`.

Untuk `close_remaining` kedua syarat dinilai atas **bagian sisa**: wajib-setuju bila **ada kelebihan uang yang akan pindah
ke titipan** (§5.6 langkah 6, > 0) **atau** barang sisa sudah disiapkan. Pelanggan tempo yang sudah membayar bagian
terkirim tidak memicu persetujuan karena tidak ada uang yang bergerak. *(Keputusan implementer — §7.)*

**Nominal dan rentang kebijakan.** Dasar nominal: batal = `grand_total`; tutup sisa = **nilai sisa yang ditutup**
(`grand_total` lama − baru). Wajib-setuju = pengaturan di atas menyatakan wajib **dan** tabel kebijakan
(`approval_policy_service`) memberi jenjang untuk nominal itu. Bawaan tabel satu rentang 0–∞, jadi semua yang wajib menurut
pengaturan butuh persetujuan; bila pemilik membuat rentang mulai Rp X, nominal di bawah X langsung jalan — sama dengan
jenis persetujuan lain (`required_levels` kosong). *(Keputusan implementer — §7.)*

### 5.3 Izin dan jenis persetujuan (A2-2, A2-3)

* Izin baru **`order.approve_cancel`** (label "Setujui pembatalan & tutup sisa pesanan"), bawaan `admin`, `manager`,
  `finance`. Empat tempat §3.2 dalam satu commit.
* `approval_kinds.APPROVAL_KINDS["sales_order.batal"]` — label "Pesanan Penjualan — pembatalan & tutup sisa",
  grup Penjualan, `queue_key="so_cancel"`, `permissions=("order.approve_cancel",)`, `amount_field="grand_total"`.
  Bawaan kebijakan (`build_default_rows`): satu rentang 0–∞, `any_holder`.
* Antrean `approval_backlog_service.QUEUES`: `("so_cancel", "Pembatalan/tutup sisa pesanan menunggu ACC",
  "approval-inbox", "sales_orders", {"cancel_request.status": "pending"})` + tab inbox (lihat §5.7).
* Siapa boleh memutus = `approval_policy_service` (pemegang izin **dan** rentang nominal) **dan** bukan pengaju **dan**
  bukan sales pesanan. "Sales pesanan" = id aktor sama dengan `sales_id` **atau** salah satu anggota `sales_team`
  (pemilik sebagian, K-21). `created_by` **tidak** dihitung (Manager/Admin yang menginput atas nama sales tetap boleh
  memutus), dan cakupan "tim" tidak dihitung (supervisor boleh memutus pesanan anggotanya). Jadi **bukan**
  `sales_ownership.owns` apa adanya. `dual_control` dipakai bila sudah menyediakan aturan "pembuat ≠ penyetuju".
  *(Keputusan implementer — §7.)*
* **Disetujui sendiri (A2-3a):** bila pengaju lolos aturan memutus di atas untuk nominal itu (berarti ia bukan sales
  pemilik), permintaan langsung `approved` + `self_approved=true` dan eksekusi jalan di request yang sama.

### 5.4 Alur

```
Pengguna (order.cancel) menekan Batalkan / Tutup sisa + alasan
  └─ server menilai: needs_approval? (5.2)  ─ tidak ─▶ eksekusi langsung (perilaku sekarang / 5.6)
                                             └ ya ──▶ pengaju boleh memutus sendiri? ─ ya ─▶ approved (self) → eksekusi
                                                                                      └ tidak ─▶ cancel_request pending
pending:  stok tetap dipesan · pengiriman diblok · ambil/kemas diblok · notifikasi ke penyetuju
  ├─ Setujui (order.approve_cancel + kebijakan)  → eksekusi; pengaju + sales pemilik + Finance diberi tahu
  ├─ Tolak (alasan wajib)                        → pesanan lanjut; pengaju + sales pemilik diberi tahu
  └─ Tarik (pengaju / pemegang order.cancel)     → pesanan lanjut
```

Endpoint (nama final pilihan builder):
* `POST /api/sales-orders/{id}/cancel` — **tetap jalur masuk** (layar, HP, AI memakainya). Bila wajib-setuju dan
  pengaju tidak bisa memutus: kembalikan **202** + `cancel_request` (bukan 200 `cancelled`), supaya klien lama tidak salah
  membaca "sudah batal". Semua pemanggil lain `cancel_order` di server (AI, aksi massal bila ada) ikut lewat penilaian
  yang sama — builder wajib mendata pemanggilnya.
* `POST /api/sales-orders/{id}/close-remaining` — sama dengan di atas untuk tutup sisa.
* `POST /api/sales-orders/{id}/cancel-request/decision` `{decision: approve|reject, note}` — `order.approve_cancel`.
* `POST /api/sales-orders/{id}/cancel-request/withdraw` — pengaju atau pemegang `order.cancel` atas pesanan itu.

### 5.5 Penahanan gudang selama pending (A2-4)

* `loading_check_service.dispatch_guard`: tolak **409** "Pesanan sedang diajukan batal/tutup sisa — tunggu keputusan"
  bila `cancel_request.status == "pending"`, diletakkan sesudah gerbang bayar & kredit, sebelum pemeriksaan muat/RFID.
  Berlaku di semua jalur kirim (Barang Keluar, maju tahap WMS, cek keberangkatan trip).
* Aksi tugas outbound `scan_pick` dan `advance` ditolak dengan pesan yang sama (pintu aksi tugas di
  `outbound_task_state`/router tugas — builder mencari pintu tunggalnya). Status tugas **tidak** diubah, jadi penolakan
  langsung memulihkan keadaan.
* Layar tugas gudang menampilkan tanda "Ditahan: menunggu keputusan batal".

### 5.6 Eksekusi

**Batal (`action=cancel`)** — panggil inti `cancel_order` yang ada (dipisah menjadi fungsi layanan yang dipanggil
endpoint lama dan pemutus), tanpa mengubah perilakunya: lepas roll + kembalikan ke rak, tutup tugas gudang, uang muka →
titipan + notifikasi Finance (sudah ada), jurnal dibalik, sales diberi tahu, Faktur Pajak aktif tetap memblok (409).
Pemeriksaan status dan faktur dijalankan **lagi saat eksekusi** (keadaan bisa berubah selama menunggu).

**Tutup sisa (`action=close_remaining`)** — hanya untuk `partially_shipped`:
1. Tolak bila ada Faktur Pajak aktif (`normal`/`pengganti`, bukan `retur`) yang **bukan** faktur per Surat Jalan (baris
   ber-`shipment_id`); pesan: batalkan/ganti faktur dulu, sama dengan batal (A1-4a).
   **Tolak juga (versi pertama) bila:** pesanan punya nota kredit/debit amandemen atau `extra_billing_lines`; pesanan
   lama berjurnal pendapatan per pesanan (`source_type="sales_order"`, bukan per Surat Jalan); ada baris yang terkirim
   **lebih** dari dipesan; atau ada baris Pesanan Khusus (`special_order_item_id`) yang belum terkirim penuh — pesan
   mengarahkan ke Batal item Pesanan Khusus. *(Keputusan implementer — §7.)*
2. Hitung jumlah terkirim per baris dari tugas outbound (`shipped_qty`, abaikan `cancelled`) — sumber yang sama dengan
   `fulfillment_status.recompute_so_status`.
3. Batalkan tugas outbound yang belum terkirim (`outbound_task_state.cancel_for_order` atau varian per tugas), lepas roll
   sisa (`release_order_rolls`, yang sudah diambil → antrean Penempatan Rak), tutup backorder terbuka (A1-5).
4. Turunkan `items[].quantity` ke jumlah terkirim; simpan `items[].quantity_ordered_original` (sekali, tidak ditimpa).
   Baris yang terkirim 0 dikeluarkan dari `items` dan dicatat di `closed_lines[]`.
5. **Nilai baru = nilai yang sudah dibukukan per Surat Jalan.** `grand_total` baru (beserta DPP dan PPN) dipaksa sama
   dengan jumlah pendapatan + PPN yang sudah diakui jurnal Surat Jalan pesanan itu (`gl_service.order_revenue_recognized`
   / `post_shipment_revenue`), supaya piutang buku = sisa tagihan pesanan dan tidak ada jurnal baru (A1-3). Mesin harga
   (`compute_order_pricing(..., snapshot=potret_dokumen(order))`) hanya dipakai untuk rincian baris; selisih pembulatan
   ditaruh di baris terakhir. Bila selisih hitungan ulang vs yang dibukukan lebih dari toleransi pembulatan (Rp 1/baris),
   **tolak** dengan pesan jelas (jangan menebak). Potret aturan komisi per baris (`items[].commission_rule`) dibawa apa
   adanya. *(Keputusan implementer — §7.)*
6. Uang: `kelebihan = min(gl.order_advance_unrecognized(order_baru), paid_total − grand_total_baru)`; bila > 0 → titipan
   lewat jalur yang sama dengan `uang_muka_pesanan_batal_ke_titipan` (fungsi diperluas/diparameterkan, tanpa jurnal) +
   notifikasi Finance (A1-2). Sesudah langkah 5, `order_advance_unrecognized` harus = kelebihan (tidak ada sisa
   menggantung di 2-1400) — diuji. Tempo tanpa uang muka: tidak ada gerak uang (A1-3).
7. `recompute_so_status` → `shipped` (atau `done` bila semua Surat Jalan sudah diterima — ikuti aturan yang ada);
   tandai `closed_short = {at, by, reason, request_id}` untuk label "Dikirim — sisa ditutup".
8. Audit + timeline + notifikasi sales pemilik.

### 5.6a Jalur sejajar yang tidak lewat `cancel_order`

| Jalur | Perlakuan *(keputusan implementer — §7)* |
|---|---|
| Tutup-sisa per tugas di eskalasi gudang (`routers/outbound_picking.resolve_outbound_escalation`, `close_remainder`, `wms.approve`) | Dibiarkan (keputusan gudang per tugas, belum dibayar saja). Ditambah: ditolak selama `cancel_request` pending; pesan "sudah ada pembayaran" diganti mengarah ke **Tutup sisa** di rincian pesanan |
| Batal Pesanan Sample (`POST /sample-orders/{id}/cancel`) | Di luar cakupan (alur bayar sample sendiri, `sample_billing`) |
| Batal item Pesanan Khusus (`so_line_cancel_service`) | Dibiarkan (keputusan pemilik 21 Okt: nota kredit menunggu Finance). Ditambah: ditolak selama `cancel_request` pending |

### 5.7 Layar

* **Rincian pesanan** (`features/orders/OrderDetailPanel.jsx`):
  * tombol **Batalkan** (sudah ada) dan tombol baru **Tutup sisa** (status `partially_shipped`, izin `order.cancel`);
  * dialog menampilkan apakah perlu persetujuan dan alasannya ("sudah ada pembayaran Rp …", "barang sudah disiapkan
    gudang"), lalu tombolnya menjadi **Ajukan pembatalan / Ajukan tutup sisa**;
  * dialog tutup sisa memperlihatkan ringkasan sebelum-sesudah: jumlah per baris (dipesan → terkirim), nilai pesanan
    lama → baru, kelebihan yang jadi titipan;
  * bilah status saat pending: siapa mengajukan, alasan, kapan; tombol **Setujui/Tolak** untuk yang berwenang, **Tarik**
    untuk pengaju.
* **Pusat Persetujuan** (`features/approvals/`): tab/antrean "Pembatalan pesanan" (`INBOX_TABS`, `BACKLOG_INBOX_TAB`,
  `LISTED_IN_INBOX`), baris berisi nomor pesanan, pelanggan, jenis (batal/tutup sisa), nilai, alasan, pengaju; aksi
  Setujui/Tolak atau buka rincian pesanan.
* Ikuti `docs/blueprint/04_POLA_UI.md`.

### 5.8 Notifikasi

Lewat `notification_service.create_addressed` (per orang, pagar PT):
* pending → pemegang `order.approve_cancel` yang lolos kebijakan nominal (atau minimal pemegang izin; builder memilih
  bila kebijakan tidak bisa dievaluasi per orang secara murah);
* disetujui/ditolak → pengaju + sales pemilik (`also_users`);
* uang ke titipan → Finance (sudah ada, `_beri_tahu_finance_titipan`).

### 5.9 Komisi

Mesin komisi menghitung `jumlah dasar baris × (bayar di periode / grand_total)`, dan bulan yang sudah berakrual dibekukan
(keputusan 2.a komisi). Uang yang dipindah ke titipan tercatat sebagai baris bayar negatif di bulan penutupan.

**Keputusan pemilik A1-6 (25 Nov): komisi atas barang yang tidak jadi dikirim DIPOTONG di bulan penutupan.** Berlaku
sama untuk batal sesudah bayar dan tutup sisa.
* Bulan yang sudah berakrual/disahkan **tidak diubah**; koreksinya muncul sebagai baris negatif di bulan penutupan,
  dengan rincian (pesanan, jumlah, alasan "sisa ditutup"/"pesanan dibatalkan") di Rincian Komisi sales.
* Besar potongan = komisi yang dulu dihitung untuk bagian yang tidak dikirim (memakai potret aturan baris yang sama),
  bukan hitungan ulang dengan aturan sekarang.
* Koreksi negatif **tidak** dipotong batas margin/nol (`margin_cap_pct`, pemotong ≥ 0) — kalau dipotong, koreksinya hilang.
* Bila total komisi bulan penutupan menjadi negatif, sisanya **terbawa ke bulan berikutnya** sebagai saldo potongan
  per sales per PT sampai habis; tidak pernah menjadi tagihan gaji negatif. Bentuk penyimpanan saldo = pilihan builder.
* Tidak dobel: titipan yang dipakai untuk pesanan lain menghasilkan komisi pesanan itu seperti biasa.
* Pesanan dibatalkan sebelum komisinya pernah berakrual: cukup hilang dari hitungan (perilaku sekarang), tanpa baris
  koreksi.

## 6. Uji (ringkas)

`backend/tests_mem/` (database tiruan) — minimal:
* belum dibayar & belum disiapkan → batal langsung (perilaku lama);
* dibayar → 202 pending; tidak bisa dikirim (`dispatch_guard` 409); disetujui → batal + titipan; ditolak → tetap jalan;
* barang disiapkan (roll `picked`) → pending; ambil/kemas ditolak selama pending;
* sales pemilik + peran kustom berizin `order.approve_cancel` tetap tidak bisa menyetujui miliknya;
* Manager mengajukan → disetujui sendiri, tercatat `self_approved`;
* tutup sisa tempo: jumlah turun ke terkirim, nilai dihitung ulang, plafon kembali, jurnal tidak bertambah, status
  `shipped`, komisi dari jumlah baru;
* tutup sisa CBD lunas: kelebihan → titipan (jumlah tepat), tanpa jurnal, Finance diberi tahu;
* tutup sisa ditolak bila Faktur Pajak per pesanan aktif; lolos bila faktur per Surat Jalan;
* komisi (A1-6): contoh CBD 100 m dibayar bulan 1 (berakrual), 40 m terkirim, sisa ditutup bulan 2 → bulan 1 tetap,
  bulan 2 berisi koreksi −60 m tidak terpotong batas margin; total bulan 2 negatif → saldo potongan terbawa ke bulan 3;
  titipan dipakai pesanan lain → komisi pesanan itu normal; batal sesudah bayar mengikuti aturan yang sama;
* nilai sesudah tutup sisa = pendapatan + PPN jurnal Surat Jalan; `order_advance_unrecognized` = kelebihan; piutang buku =
  sisa tagihan pesanan;
* pengaturan `selalu` / `tidak_pernah`; uji izin baku (§3.2 butir 4); antrean & KPI (INV-APPR-01, INV-HOME-01).
Jest: dialog (perlu persetujuan / langsung, ringkasan tutup sisa), bilah pending, tab inbox.

## 7. Keputusan implementer (bukan dari pemilik — periksa)

1. Pengaturan `order.cancel_approval_when` dengan tiga nilai (standar §2: aturan bisnis = pengaturan); bawaan = keputusan A2-1.
2. Tutup sisa: wajib-setuju bila ada **kelebihan uang yang pindah ke titipan** atau barang **sisa** sudah disiapkan
   (bukan sekadar `paid_total > 0`).
3. Endpoint batal lama mengembalikan **202** saat menjadi permintaan.
4. Penyetuju bawaan = semua pemegang `order.approve_cancel` (Admin, Manager, Finance), satu rentang 0–∞; rentang
   nominal yang mulai dari Rp X membebaskan nominal di bawahnya (sama dengan jenis lain). Nominal tutup sisa = nilai sisa.
5. Penahanan gudang = blok aksi (kirim, ambil, kemas), bukan mengubah status tugas.
6. Pengaju atau pemegang `order.cancel` atas pesanan itu boleh menarik permintaan.
7. "Sales pesanan" yang tidak boleh memutus = `sales_id` + anggota `sales_team`; bukan `created_by`, bukan cakupan tim.
8. Nilai pesanan sesudah tutup sisa = yang sudah dibukukan per Surat Jalan; selisih di luar pembulatan → ditolak.
9. Versi pertama menolak tutup sisa untuk: pesanan bernota amandemen/`extra_billing_lines`, berjurnal per pesanan,
   baris terkirim lebih dari dipesan, dan baris Pesanan Khusus yang belum terkirim penuh.
10. Jalur sejajar (eskalasi gudang, batal item Pesanan Khusus) dibiarkan tetapi diblok selama ada permintaan pending;
    batal Pesanan Sample di luar cakupan.

## 8. Diserahkan ke builder

Nama endpoint/fungsi final, letak pemisahan inti `cancel_order` menjadi fungsi layanan, pintu tunggal aksi tugas
gudang, bentuk riwayat (`cancel_requests[]`), daftar pemanggil `cancel_order` lain yang harus ikut dinilai, teks pesan
dan tata letak dialog sesuai pola UI, urutan unit kerja.
