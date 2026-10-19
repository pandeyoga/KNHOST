# Rancangan — Pemetaan Akun (GL-01) dan Pemecahan Roll Cutloss (CUT-01)

Status: rancangan, belum diimplementasi. Dasar: keputusan owner 2026-10-19C. Kode saat ini menjadi acuan (kode menang atas dokumen).

## A. Pemetaan Akun terpusat (GL-01)

### A.1 Kondisi sekarang
- `services/gl_service.py` menyimpan ±45 konstanta akun tetap (`ACC_KAS_BESAR = "1-1100"`, `ACC_HPP = "5-1000"`, `ACC_WRITEOFF = "5-9500"`, `ACC_STORE_CREDIT = "2-1450"`, ...) dipakai ±35 service/router (penjualan, pembelian, retur, makloon, payroll, aset tetap, interco, kas kecil, denda, selisih bayar, bank).
- Hanya sebagian kecil sudah bisa dikonfigurasi: kategori kas kecil (`expense_categories.account_code`), override COA per entitas (`gl_accounts` ber-`entity_id`).
- Ongkir retur (`ReturnLogisticsPanel`, 3 jenis biaya × penanggung) hanya dicatat, belum dijurnal.

### A.2 Model data
Koleksi baru `gl_account_mappings` (per scope `global` atau `entity_id`; entitas meng-override global):
```
{ id, scope_type: "global"|"entity", entity_id, key: "returns.logistics.company_expense",
  account_code: "6-4510", updated_by, updated_at, reason, version }
```
Registri kode `services/gl_mapping_registry.py` (SSOT, bukan DB) — satu baris per "kebutuhan fitur":
```
key, modul, label (bahasa awam), penjelasan, contoh jurnal (Dr/Cr), jenis akun yang diizinkan
(asset/liability/expense/revenue/equity), default (konstanta lama), wajib/opsional, dipakai_oleh
```
Resolver `gl_service.account_for(key, entity_id)` → mapping entitas → mapping global → default registri. Konstanta lama diganti bertahap menjadi pemanggilan resolver (perilaku identik selama mapping kosong).

### A.3 Kelompok kebutuhan (awal)
| Modul | Contoh key | Default sekarang |
|---|---|---|
| Kas & Bank | kas_besar, kas_kecil, kas_transit, beban_bank | 1-1100, 1-1110, 1-1150, 6-8000 |
| Penjualan | piutang, pendapatan, ppn_keluaran, uang_muka_pelanggan, denda | 1-1200, 4-1000, 2-1200, 2-1400, 4-9300 |
| Persediaan | persediaan, transit_antar_pt, hpp, penghapusan, saldo_awal | 1-1300, 1-1310, 5-1000, 5-9500, 3-2900 |
| Pembelian | hutang, gr_ir, ppn_masukan, landed_cost | 2-1100, 2-1150, 1-1500, 5-9000 |
| Retur | store_credit, **ongkir_ditanggung_perusahaan**, **ongkir_ditagih_customer**, **potongan_cacat_dibuang**, **potongan_cacat_bs** | 2-1450, *baru*, 1-1200, 5-9500, 1-1300 |
| Makloon | wip_subcon, piutang_klaim, pendapatan_klaim, jasa_tak_terserap | 1-1350, 1-1260, 4-9200, 5-1200 |
| Antar-PT | piutang_ic, utang_ic | 1-1250, 2-1250 |
| SDM/Payroll | beban_gaji, beban_bpjs, hutang_gaji, hutang_bpjs | 6-1000, 6-1100, 2-1600, 2-1700 |
| Aset tetap | akumulasi_penyusutan, beban_penyusutan, laba/rugi pelepasan | 1-2900, 6-6000, 4-9100, 6-9500 |
| Lain-lain | suspense, selisih_bayar, beban_rnd, pemasaran, insentif | 1-9999, 6-9100, 6-7000, 6-4700, 6-5000/2-1500 |

### A.4 UI "Pemetaan Akun" (Pengaturan → Keuangan)
- Daftar dikelompokkan per modul (tab/akordeon), kolom: **Kebutuhan** (bahasa awam), **Akun dipakai** (kode + nama), **Sumber** (bawaan/global/entitas), **Status** (lengkap/belum diatur/akun nonaktif).
- Pemilih akun = combobox cari kode/nama, hanya menampilkan jenis akun yang diizinkan registri; akun nonaktif/induk (header) tidak bisa dipilih.
- Panel penjelasan per baris: "Dipakai saat …", **contoh jurnal** Dr/Cr dengan angka contoh, daftar fitur pemakai.
- Pilih scope di atas: Global / per PT; baris yang di-override PT diberi lencana dan tombol "Kembali ke global".
- Simpan wajib alasan; riwayat perubahan per baris (siapa, kapan, dari → ke). Peringatan "perubahan berlaku untuk jurnal baru; jurnal lama tidak diposting ulang".
- Kartu ringkasan: "X kebutuhan belum diatur" → klik menyaring baris itu. Pencarian teks bebas.
- Hak akses baru `gl_mapping.view` / `gl_mapping.update` (default: admin + finance lihat, admin ubah).

### A.5 Ongkir retur → jurnal
Saat biaya logistik retur disimpan (atau saat dikunci di settle, lihat GL-03):
- Ditanggung perusahaan: Dr `returns.logistics.company_expense` / Cr `returns.logistics.payable` (kas/bank/hutang ekspedisi — GL-04).
- Ditanggung customer: Dr Piutang (atau dipotong dari kompensasi/saldo retur — GL-05) / Cr `returns.logistics.recovery`.
- Idempoten per (retur, jenis biaya); ubah nominal = jurnal balik + jurnal baru; batal retur = jurnal balik.

## B. Pemecahan fisik roll cutloss (CUT-01)
- Saat MD mencatat qty cacat cutloss (`record_cutloss`) pada roll yang ada di gudang, MD/QC memasukkan **posisi** potongan (yard awal–akhir) atau minimal panjang cacat, lalu memilih **Perlakuan potongan cacat: Masuk stok BS / Dibuang**.
- Eksekusi (saat Finance memutus kompensasi atau tombol "Proses potongan" — CUT-04): roll induk dipecah memakai aturan identitas retur yang sudah ada (child berurutan dari induk, histori qty/grade, EPC lama tidak menjadi roll baru):
  - potongan baik → child grade sama, status siap dikirim kembali ke customer (alur pengiriman pengganti/retur existing);
  - potongan cacat **BS** → child grade BS, status `available` di gudang QC/transit, nilai persediaan sesuai CUT-03;
  - potongan cacat **Dibuang** → child langsung `disposed` lewat disposal tercatat (alur BS dibuang existing), jurnal penghapusan ke `returns.cutloss.disposal_expense`.
- Produk berbasis kg: panjang yard dikonversi lewat master UoM (sama dengan KLR-01); bila faktor belum ada, eksekusi ditolak dengan pesan jelas.
- Cutloss tanpa barang di gudang (customer menyimpan kain, mis. diskon dari foto) tidak memecah roll.
- UI: di panel cutloss retur — pilihan dua tombol radio "Masuk stok BS" / "Dibuang", pratinjau hasil potongan (mis. "45 yd baik · 15 yd BS · 60 yd baik"), konfirmasi sebelum memproses.
