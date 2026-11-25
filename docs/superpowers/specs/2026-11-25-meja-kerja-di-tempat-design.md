# Rancangan — Meja kerja di tempat (rincian pop-up, kartu tetap, satu nama, satu skala huruf)

Tanggal: 25 Nov 2026 · Status: **menunggu persetujuan pemilik** · Dasar: audit `docs/audit/meja-2026-11-25/`
(laporan + Lampiran A audit kode per meja dengan `berkas:baris` + Lampiran B uji klik/huruf) di `HEAD fe43d79`.

## 1. Maksud dan alasannya

Pemilik (25 Nov): layar Meja *"sangat bertumpuk… di-klik tidak muncul detailnya padahal di preview infonya terpotong…
sebaiknya bisa langsung dikerjakan di sini tanpa pindah ke halaman yang dituju… konten tidak lengkap… font tidak konsisten…
terlalu banyak duplikasi"*. Lalu: *"intinya soal meja karena sangat bertumpuk ini harus dipersimpel untuk previewnya, makanya
jika di-klik muncul popup detail dan yang bisa diselesaikan di halaman menu itu tanpa harus pindah halaman (yang bisa saja,
sebanyak mungkin). Kartu kosong tetap dijadikan fixed size, sama dengan jika terisi (default 5 baris) agar konsisten."*

Meja adalah tempat orang **mengerjakan** antreannya, bukan papan penunjuk ke menu lain. Saat ini:
- baris tidak bisa diklik;
- 13 dari 17 tombol aksi yang diuji memindahkan pengguna ke menu lain, sebagian hanya ke daftar;
- dua aksi berakibat besar jalan sekali klik tanpa konfirmasi;
- satu meja setinggi 2–3,3 layar sebelum pekerjaan selesai dibaca.

## 2. Keputusan pemilik (25 Nov)

| # | Keputusan |
|---|---|
| P1 | **Klik baris → pop-up rincian.** Pekerjaan yang bisa diselesaikan di meja dikerjakan di pop-up itu, tanpa pindah halaman — sebanyak mungkin. |
| P2 | **Preview baris disederhanakan.** Rincian lengkap pindah ke pop-up. |
| P3 | **Semua kartu antrean berukuran tetap**, setinggi kartu berisi 5 baris, termasuk kartu kosong. |
| P4 | Pelacak SO, Keep & Pending, dan Aturan Grade Pelanggan dipindah ke **tab "Pantau"** di meja yang sama. |
| P5 | **Satu nama per meja** (menu = breadcrumb = judul); kepala meja di dalam layar dihapus. |
| P6 | **Aksi berakibat besar wajib pratinjau + konfirmasi** (terbit faktur pajak, setujui bayar, lepas/teruskan ke gudang, terbitkan denda). |
| P7 | **Huruf minimal 12 px**, termasuk label kolom. |
| P8 | Standar `docs/blueprint/04_POLA_UI.md` diubah mengikuti P1–P7. Standar lama melarang pop-up di atas daftar (§1.6, §4), mewajibkan kartu selalu terbuka, dan menyatakan rincian = halaman/panel tetap. |

## 3. Tujuan, bukan tujuan, anti-tujuan

**Tujuan**
- Layar pertama setiap meja langsung berisi antrean kerja. Tidak ada blok penjelasan, kartu angka, atau tabel pantauan di atasnya.
- Setiap baris di setiap meja bisa diklik dan membuka rincian utuh tanpa teks terpotong.
- Aksi yang sudah punya pop-up atau panel di aplikasi dijalankan dari meja.
- Kembali dari layar penuh tidak menghapus cari/saring/halaman kartu.
- Satu skala huruf dan satu nama per meja.

**Bukan tujuan**
- Mengubah aturan bisnis atau izin. Pop-up memakai endpoint dan pemeriksaan server yang sama dengan layar asalnya.
- Membuat antrean baru, kecuali memindahkan antrean pantauan ke tab Pantau.
- Lapor Bayar CBD: rancangan terpisah, dibangun sesudah gelombang 2 dan memakai pola ini.
- Perombakan notifikasi (rancangan terpisah).
- Mengubah Meja Kredit (`CreditDeskView`). Meja ini hanya dipakai sebagai contoh pola aksi di tempat.

**Anti-tujuan** (gagal walau "jalan"):
- Pop-up yang menyalin logika layar lain. Panel rincian dan aksi wajib **memakai ulang komponen yang ada**, bukan salinan.
- Aksi dari meja yang melewati pemeriksaan yang ada di layar asalnya. Contoh: setujui bayar sample di meja sekarang tidak mengecek uang masuk, padahal di Pesanan Sample dicek.
- Pesan hasil yang tidak terlihat, misalnya tampil di puncak halaman saat pengguna sedang di kartu bawah.
- Pop-up buatan sendiri di luar `DetailModal`/`FormModal`. Penjaga `custom_modals` INV-UI-11 akan merah.
- Kartu yang bergeser ukuran saat dimuat atau saat kosong.

## 4. Pendekatan yang dipertimbangkan

1. **Semua meja sekaligus dalam satu gelombang.** Perubahan dan uji menumpuk di akhir; pemilik baru melihat hasil sesudah semuanya jadi.
2. **Bertahap — dipilih.**
   - Gelombang 1 mengganti kerangka bersama yang dipakai semua meja: kepala, kartu, baris, pop-up rincian umum, konfirmasi, huruf, dan tab Pantau. Hasilnya langsung terasa di semua meja.
   - Gelombang 2–3 mengisi pop-up per jenis dokumen dengan panel rincian dan aksi yang sudah ada, meja demi meja.
   - Setiap gelombang ditutup dengan tangkapan sebelum/sesudah untuk divalidasi pemilik.
3. **Panel tetap di kanan (`DetailDrawer`) alih-alih pop-up.** Ditolak: pemilik memilih pop-up (P1).

## 5. Rancangan

### 5.1 Kerangka halaman meja (semua meja desktop)

- **Kepala.** Satu kepala, yaitu `TopBar` (breadcrumb + judul). Kepala meja di dalam layar dihapus: kicker, h2, dan tombol muat ulang sendiri. Pembaruan memakai tombol muat ulang global.
- **Nama tunggal** dipakai sama di menu, breadcrumb, dan judul:

  | Sekarang | Nama tunggal |
  |---|---|
  | Meja Admin Sales | Meja Admin Sales |
  | Perlu Tindakan (Beranda Keuangan) | Meja Keuangan |
  | Meja Gudang / Meja Admin Gudang | Meja Gudang |
  | Meja Sample / Meja Admin Sample | Meja Sample |
  | Meja MD | Meja MD |
  | Meja Saya / Meja Manajer / Meja Sales / … | Meja Saya |

  Teks usang "Meja Finance" diganti "Meja Keuangan" di semua tempat (`SalesAdminDesk.jsx:132`, `MobileSalesAdminDesk.jsx:183`, `work_desk_service.py:283`, `sample_orders.py:184`). Ganti nama "Perlu Tindakan" → "Meja Keuangan" berlaku untuk tab hub Beranda Keuangan.
- **Penjelasan.** Paragraf alur dan kotak "Bukan wewenang meja ini" pindah ke ikon **?** di samping judul. Polanya sama dengan ikon ? standar.
- **Kartu angka dan kotak "Paling lama menunggu"** dihapus, termasuk ketiga salinan `Metric`. Gantinya, urutan kartu: kartu berisi diurutkan dari yang paling mendesak (`deskQueueOrder.compareFilledQueues`, sudah dipakai Keuangan), lalu kartu kosong.
- **Kartu "Meja retur internal"** (`ReturnDeskSummaryCard`, disisipkan router di atas Meja Gudang dan Keuangan) dipindah ke tab Pantau.
- **Tab.** Setiap meja punya dua tab: **Antrean** (bawaan) dan **Pantau**. Tab Pantau berisi:
  - Pelacak SO aktif;
  - Keep & Pending (Admin Sales);
  - Aturan Grade Pelanggan (Admin Sales);
  - kartu retur internal;
  - antrean yang sifatnya pantauan, bukan tindakan: `menunggu_manajer` (Admin Sales), `di_gudang`, `kirim_ambil`, dan `selesai` (Sample).

  Pelacak SO hanya tampil di tab Pantau. **Keputusan builder:** Pelacak SO tetap ada di Pantau semua meja yang punya izin `order.view`, karena tabelnya sudah tersaring wewenang.
- **Pesan hasil aksi** tampil di dalam pop-up tempat aksi dijalankan. Bila pop-up tertutup sesudah sukses, pesannya tampil sebagai toast. Pesan tidak boleh muncul di puncak halaman.

### 5.2 Kartu antrean (`DeskQueueCard`) — ukuran tetap, baris ringkas

- **Tinggi tetap** = kepala + bilah saring + 5 baris + pager, sama untuk kartu berisi, kartu dengan kurang dari 5 baris, kartu kosong, dan kartu yang sedang dimuat (kerangka/skeleton setinggi yang sama).
  - Kartu kosong menampilkan teks "bersih" di tengah ruang yang sama.
  - Grid tidak lagi meregangkan kartu setinggi tetangganya.
- **Kepala kartu** (satu baris): ikon · judul (14 px semi-tebal) · jumlah (lencana) · "tertua n hari" bila ada · nilai total di kanan tanpa label huruf besar.
  - Untuk antrean jumlah, jumlah hanya tampil sekali.
  - Penjelasan (`hint`) pindah ke ikon ? di judul kartu.
- **Bilah saring** tetap (cari + Status bila >1 status + Urut). Pilihan urut "Nilai terbesar" disembunyikan untuk antrean jumlah. Tinggi dan huruf dropdown sama dengan kotak cari.
- **Baris ringkas** (P2), maksimal dua baris teks:
  - kiri: nomor dokumen (13 px semi-tebal, warna aksi) dan di bawahnya nama pihak/judul (13 px normal);
  - tengah: satu lencana status dan umur ("8 hari");
  - kanan: nilai (13 px semi-tebal) dan **satu** tombol aksi.

  Keterangan panjang, "masuk tgl", sales, kota, dan sebagainya tidak tampil di baris; semuanya ada di pop-up. Baris tetap memotong teks, karena teks utuh ada di pop-up.
- **Seluruh baris bisa diklik** (selain tombol aksi) dan membuka pop-up rincian. Baris bisa difokus dengan keyboard dan dibuka dengan Enter. Kursor tangan hanya muncul pada yang benar-benar bisa diklik.
- **Status kartu tersimpan**: cari, saring, urut, dan halaman per kartu disimpan di `sessionStorage` (kunci: meja + antrean), dan posisi gulir dipulihkan saat kembali dari layar penuh.

### 5.3 Pop-up rincian

- Cangkangnya `DetailModal`. Di HP (≤ 640 px) tampil layar penuh, sesuai perilaku bawaannya.
  - Judul: nomor · nama pihak.
  - Subjudul: PT · status · umur.
- Isinya ditentukan **registri pratinjau per `ref_type`**: satu berkas peta `ref_type → komponen panel` yang dipakai semua meja.
  - Bila jenisnya punya panel (gelombang 2–3), panel itu yang tampil, lengkap dengan aksinya.
  - Bila belum, tampil **panel umum**: semua isian baris tanpa dipotong (judul, keterangan utuh, lencana, nilai, umur, waktu masuk nyata, PT, sales, kota, dan isian `extra` yang relevan), ditambah tombol aksi baris dan tautan sekunder **"Buka layar penuh"** (tujuan navigasi yang sekarang).
- **Tombol aksi di baris:**
  - bila aksinya punya pop-up sendiri (mis. `ReceivePaymentModal`, `VerifyOrderDialog`), pop-up aksi langsung dibuka;
  - bila belum, pop-up rincian dibuka dengan aksi di dalamnya.

  Aksi yang masih harus pindah halaman diberi tanda ikon "buka layar" agar pengguna tahu.
- **Sesudah aksi sukses:** kartu yang bersangkutan dimuat ulang di tempat (bukan seluruh halaman), lalu pop-up tertutup dan toast tampil. Bila aksi gagal, galat tampil di dalam pop-up.
- **Pop-up buatan sendiri** yang dipakai meja dipindah ke `FormModal`: `VerifyOrderDialog.jsx:64` dan `FulfillmentDecisionDialog.jsx:102`.

### 5.4 Aksi berakibat besar (P6)

Setiap aksi di bawah ini membuka pratinjau + konfirmasi (`FormModal`) dan memakai pemeriksaan yang sama dengan layar asalnya:

| Aksi | Pratinjau | Pemeriksaan |
|---|---|---|
| Terbitkan Faktur Pajak (`issue_tax`) | SO, pelanggan + NPWP, DPP, PPN, tanggal | sama dengan layar faktur pajak |
| Setujui Bayar sample | total, uang masuk, kurang | cek uang masuk + konfirmasi bila kurang, sama dengan `SampleOrdersView.jsx:141-153` |
| Lepas ke gudang (Ditahan) / Teruskan ke gudang (sample) | pesanan, PT, gudang, baris | — |
| Terbitkan denda (`issue_penalty`) | pelanggan, dasar, nilai | sama dengan Meja Kredit (`askConfirm`) |

Aksi `decide_variance` dan `issue_penalty` yang dikirim server ditangani di tempat (gelombang 2), tidak diteruskan ke navigasi lagi.

### 5.5 Huruf (P7)

- Hanya token `text-fs-*` (12/13/14/16/20). Px mentah, ukuran pecahan (9–11,5 / 12,5), dan warna hex mentah di berkas meja yang disentuh diganti token.
- Peta peran huruf:
  - judul kartu 14/600;
  - nomor dokumen 13/600;
  - nama pihak 13/400;
  - nilai 13/600;
  - lencana dan umur 12/500;
  - label kolom tabel Pelacak 12/600 tanpa huruf besar;
  - teks lain 12–13/400.
- Maksimal dua unsur semi-tebal dalam satu baris.
- Standar `04_POLA_UI.md` §3 disesuaikan: minimal 12 px untuk semua teks, termasuk label kolom.

### 5.6 Isi yang dilengkapi / dibetulkan

Server:
- **`_row` membawa `entity_id`.** Pop-up dan baris menampilkan nama PT pendek saat mode "Semua PT".
- **Server berhenti memotong teks** untuk alasan, brief, item, dan keterangan (`work_desk_service.py:352,747,799,863,958,1004`; `role_desk_service.py:235,264,299`; `sample_orders.py:140`). Kirim teks utuh; baris yang memotong, pop-up menampilkan utuh. **Barang kurang dikirim semua baris**, bukan 2.
- **`at` (waktu masuk) diisi nyata.** Pop-up menulis "masuk tgl" hanya bila `at` ada, tanpa tebakan "±". Untuk antrean jatuh tempo, umur dibaca sebagai "lewat n hari", bukan "menunggu".
- **`booking_until`** (batas cadangan) tampil di pop-up SO.
- **Pesanan sample hanya punya satu pemilik giliran:**
  - Pelacak SO memakai `sample_next_step` untuk SOS (bukan "Diputuskan Manajer");
  - antrean `so_acc`/Giliran saya manajer tidak memuat pesanan sample yang persetujuannya milik Admin Sample/Finance;
  - antrean `sample_acc_bayar` di Meja Keuangan pindah ke tab Pantau (Meja Sample pemiliknya).

  **Keputusan builder**, dicatat untuk diperiksa pemilik.
- **Satu baris hanya di satu kartu antrean per meja.** Di Meja Keuangan, pesanan yang sudah ada di "Uang masuk perlu dicatat" tidak diulang di "Piutang lewat jatuh tempo"; prioritas mengikuti urutan kelompok. "Giliran saya" tidak mengulang baris yang sudah ada di antrean khusus peran yang sama.
- **Tombol "Cetak"** (siap cetak SJ/Invoice) membuka pop-up dokumen pesanan (cetak SJ/Invoice) di tempat, bukan daftar Pesanan.
- **"Buat SPK QC"** membuka pembuatan SPK dengan pesanan terpilih, bukan daftar Inspeksi kosong.
- **Meja Cutting** menampilkan pelanggan dan SKU (sudah dikirim server), dan memakai `DeskQueueCard`.

### 5.7 Pop-up per jenis dokumen (gelombang 2–3)

Pakai komponen yang sudah ada (Lampiran A §3.3):

| Meja | Jenis / antrean | Panel & aksi di pop-up |
|---|---|---|
| Admin Sales | SO (perlu_verifikasi, siap_dikonfirmasi, siap_cetak, harga_ditolak, jatuh_tempo) | `OrderDetailPanel` (`DetailPopup`) + `VerifyOrderDialog` / `FulfillmentDecisionDialog` / cetak dokumen |
| Admin Sales | pelanggan_tanpa_sales | kartu pelanggan pop-up + pilih sales di tempat (endpoint penetapan sales yang ada) |
| Admin Sales | retur, retur_tukar | `ReturnDetail` |
| Admin Sales | permintaan_internal | rincian PIN + aksi yang ada |
| Admin Sales | OD (od_*) | `SpecialOrderDetail` |
| Keuangan | uang masuk, bayar sebelum kirim, sample berbayar | `ReceivePaymentModal` (sudah) + `OrderDetailPanel` ringkas |
| Keuangan | faktur pajak | pratinjau + konfirmasi (§5.4) |
| Keuangan | selisih bayar, denda | modal keputusan / `askConfirm` pola Meja Kredit |
| Keuangan | piutang lewat tempo | kartu pelanggan + tagihan terbentang (pola Meja Kredit) |
| Keuangan | hutang, kontrabon | kartu pemasok / `PODetailPanel` |
| Keuangan | retur putus nilai | `ReturnDetail` |
| Meja Saya (manajer/admin) | so_acc, po_acc, retur_acc, harga_khusus, giliran_saya (jenis persetujuan) | `ApprovalDecisionModal` |
| Meja Saya (sales) | SO miliknya | `OrderDetailPanel` |
| Meja Saya (gudang, desainer, pengemudi) | — | panel yang sesuai: tugas WMS, desain, pengiriman |
| Gudang | persetujuan_gudang | `ApprovalDecisionModal` (opname) / `TransferDetailModal` |
| Gudang | sj_belum_diangkut, logistik | `DeliveryDetailModal` / form buat pengiriman dalam `FormModal` |
| Gudang | inbound | `PODetailPanel` (`inModal`) |
| Gudang | spk, acuan | `InspectionDetailPanel` |
| MD | desain | `DesignRequestDetailPanel` |
| MD | sample | `SampleDetailPanel` + `DecideModal` / `RoundActionModal` |
| MD | pr | `PurchaseRequisitionDetailPanel` / `MyApprovalDecisionModal` |
| MD | makloon | `MakloonOrderDetailPanel` |
| MD | po_bahan | `PODetailPanel` |
| Sample | semua antrean | panel rincian + aksi Pesanan Sample (`SampleOrdersView.jsx:217-300`), diekstrak menjadi komponen bersama lalu dipakai di daftar dan meja |

Jenis yang panelnya belum ada tetap memakai panel umum (§5.3) dengan "Buka layar penuh".

### 5.8 HP

- **HP Admin Sales:**
  - baris bisa disentuh dan membuka pop-up rincian yang sama (layar penuh);
  - tidak ada lagi teks terpotong yang tak bisa dibaca;
  - huruf minimal 12 px;
  - kotak "Meja Finance" diganti dan dipindah ke ikon ?.
- **HP MD:** sudah membuka rincian; huruf disesuaikan.
- **Keputusan builder:** di HP kartu tetap bisa dibuka-tutup (bukan ukuran tetap). Layar HP sempit, dan pola lipat sudah lebih ringkas daripada desktop. Ukuran tetap (P3) berlaku untuk grid desktop.

### 5.9 Standar `04_POLA_UI.md`

Ubah:
- §1.6: rincian dari daftar meja = pop-up `DetailModal`, dan pesan hasil tampil di pop-up/toast.
- §2.B pola Meja: kartu ukuran tetap 5 baris termasuk kosong; baris bisa diklik; tab Antrean/Pantau; tanpa kartu angka.
- §3: minimal 12 px.
- §4: hapus larangan pop-up untuk rincian meja; larangan pop-up buatan sendiri tetap berlaku.

Catat asal perubahan: keputusan pemilik 25 Nov.

## 6. Gelombang kerja

| Gelombang | Isi | Selesai bila |
|---|---|---|
| 1 — Kerangka (semua meja) | §5.1, §5.2, §5.3 panel umum + registri kosong, §5.4, §5.5, §5.6 (server & dedupe), §5.8 baris HP bisa disentuh, §5.9 | semua meja desktop: baris bisa diklik, kartu sama tinggi, satu kepala, tab Pantau, tidak ada aksi besar tanpa konfirmasi; tangkapan sebelum/sesudah untuk pemilik |
| 2 — Admin Sales + Keuangan | §5.7 baris Admin Sales & Keuangan; kemudian rancangan Lapor Bayar CBD memakai pola ini | semua aksi kedua meja di tempat, kecuali yang ditandai "buka layar" dengan alasan |
| 3 — Meja Saya, Gudang, MD, Sample, Cutting | §5.7 sisanya | sama |

## 7. Uji

- **Jest `DeskQueueCard`:**
  - klik baris membuka pop-up rincian;
  - tombol aksi tidak ikut memicu klik baris;
  - kartu kosong, kartu 1 baris, dan kartu 5 baris sama tinggi (kelas tinggi tetap);
  - status cari/saring/halaman pulih dari `sessionStorage`;
  - tidak ada kelas px mentah.
- **Jest per meja:** satu kepala (tidak ada h2 meja), tab Pantau berisi Pelacak SO; aksi besar membuka konfirmasi dulu.
- **Backend:** `_row` membawa `entity_id`; teks tidak lagi dipotong server; dedupe antar kartu Keuangan; pesanan sample tidak masuk `so_acc` manajer; Pelacak SO memakai `sample_next_step`.
- **Penjaga:** `custom_modals` (INV-UI-11) dan `create_modal` (INV-UI-05) tidak bertambah merah; gate `--quick` sekali per gelombang, dibandingkan per pelanggaran.
- **Tangkapan layar** sebelum/sesudah per meja (Playwright, data acuan) untuk validasi pemilik di akhir tiap gelombang.

## 8. Batasan

- `AGENTS.md`:
  - wewenang dari izin;
  - bahasa Indonesia;
  - LF;
  - jangan ubah `deploy/`;
  - uji hemat.
- Pop-up hanya `DetailModal` / `FormModal` / `DetailPopup`. Tidak ada pop-up buatan sendiri.
- Aksi di pop-up memakai endpoint dan pemeriksaan yang sama dengan layar asalnya. Tidak ada endpoint baru untuk aksi yang sudah ada.

## 9. Dibiarkan ke builder

- Bentuk visual ikon ? dan penempatannya di kepala kartu.
- Nama dan letak berkas registri pratinjau.
- Kunci `sessionStorage`.
- Urutan pengerjaan di dalam satu gelombang.
