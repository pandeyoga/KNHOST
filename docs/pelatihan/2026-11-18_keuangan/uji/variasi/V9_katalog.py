"""V9 — katalog bukti untuk setiap klaim yang bisa diuji di teks materi (konsep, cek_buku, kesalahan_umum, titik_kontrol,
catatan_pelatih) semua materi F/K/H/A (S1–S4 dikerjakan agen lain). Nasihat umum tidak dimasukkan.

  python3 docs/pelatihan/2026-11-18_keuangan/uji/variasi/V9_katalog.py   → src/variasi_klaim_materi.json

Bukti tiap klaim: langkah uji layar lama (`uji/<kode>…js` + `uji/hasil/<kode>/hasil.json`), uji variasi V1–V8 (`src/variasi_*.json`),
uji dokumen D1–D3, uji unit (`backend/tests_mem`, jest `frontend/src/features/__tests__`), atau uji BARU V9
(`uji/variasi/V9_klaim_*.js`, hasil `uji/hasil/V9/<blok>/`). Rujukan V9 ditulis "V9:<blok>#<langkah>" dan dibaca dari
`klaim.json`/`hasil.json` blok itu (lulus/gagal ikut tercatat apa adanya).
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
PEL = os.path.abspath(os.path.join(ROOT, "..", ".."))
HASIL = os.path.join(PEL, "uji", "hasil")

UJI = {"F01": "uji/F01_orientasi.js", "F02": "uji/F02_pelunasan_penuh.js", "F03": "uji/F03_bayar_sebagian.js",
       "F04": "uji/F04_lebih_bayar_titipan.js", "F05": "uji/F05_rencana_denda.js", "F06": "uji/F06_kredit_plafon.js",
       "F07": "uji/F07_kas_kecil.js", "F08": "uji/F08_titipan_sales.js", "F09": "uji/F09_rekening_transaksi_kas.js",
       "F10": "uji/F10_rekonsiliasi_bank.js", "F11": "uji/F11_bayar_tagihan.js", "F12": "uji/F12_kontrabon.js",
       "F13": "uji/F13_faktur_pajak.js", "F14": "uji/F14_sample_berbayar.js", "F15": "uji/F15_setoran_gaji.js",
       "F16": "uji/F16_buku_besar_jejak.js", "F17": "uji/F17_laporan_keuangan.js", "F18": "uji/F18_tutup_buku.js",
       "K01": "uji/konfigurasi/K01_bagan_akun.js", "K02": "uji/konfigurasi/K02_pemetaan_akun.js",
       "K03": "uji/konfigurasi/K03_profil_pt_periode.js", "K04": "uji/konfigurasi/K04_rekening_kas_bank.js",
       "K05": "uji/konfigurasi/K05_aturan_keuangan_pajak.js", "K06": "uji/konfigurasi/K06_termin_plafon.js",
       "K07": "uji/konfigurasi/K07_hak_akses_persetujuan.js", "K08": "uji/konfigurasi/K08_nomor_naskah_dokumen.js",
       "K09": "uji/sdm/K09_konfigurasi_sdm.js", "H01": "uji/sdm/H01_karyawan_baru.js", "H02": "uji/sdm/H02_masukan_gaji.js",
       "H03": "uji/sdm/H03_proses_gaji.js", "H04": "uji/sdm/H04_bayar_gaji_slip.js", "A1": "uji/e2e/A1_order_to_cash.js",
       "A2": "uji/e2e/A2_procure_to_pay.js", "A3j": "uji/e2e/A3_retur_penjualan.js", "A3b": "uji/e2e/A3_retur_pembelian.js",
       "A3t": "uji/e2e/A3_retur_tukar.js", "V1": "uji/variasi/V1_terima_pembayaran.js", "V2": "uji/variasi/V2_kas.js",
       "V3": "uji/variasi/V3_rekonsiliasi.js", "V4": "uji/variasi/V4_denda_hitungan.js", "V5": "uji/variasi/V5_bayar_tagihan.js",
       "V6": "uji/variasi/V6_kontrabon_pajak.js", "V7": "uji/variasi/V7_gaji.js", "V8": "uji/variasi/V8_buku_laporan.js",
       "D2": "uji/dokumen/D2_dokumen_keuangan.js", "D3": "uji/dokumen/D3_template_naskah.js"}
V9 = {"piutang-toleransi": "uji/variasi/V9_klaim_piutang.js", "piutang-umur": "uji/variasi/V9_klaim_piutang.js",
      "piutang-denda": "uji/variasi/V9_klaim_piutang.js", "piutang-janji": "uji/variasi/V9_klaim_piutang.js",
      "piutang-tertua": "uji/variasi/V9_klaim_piutang.js", "piutang-kembalikan": "uji/variasi/V9_klaim_piutang.js",
      "kas": "uji/variasi/V9_klaim_kas.js", "hutang-tagihan": "uji/variasi/V9_klaim_hutang.js",
      "hutang-kontrabon": "uji/variasi/V9_klaim_hutang.js", "hutang-faktur": "uji/variasi/V9_klaim_hutang.js",
      "hutang-grir": "uji/variasi/V9_klaim_hutang.js",
      "gaji": "uji/variasi/V9_klaim_gaji.js", "buku": "uji/variasi/V9_klaim_buku.js"}


def u(kode, langkah):
    """Langkah uji layar lama: berkas · langkah · status di hasil.json."""
    k = kode[:2] if kode.startswith("A3") else kode
    folder = {"A3j": "A3_retur_penjualan", "A3b": "A3_retur_pembelian", "A3t": "A3_retur_tukar"}.get(kode, kode)
    st = ""
    try:
        h = json.load(open(os.path.join(HASIL, folder, "hasil.json")))
        nos = [x.strip() for x in str(langkah).replace("–", ",").split(",")]
        oks = [s["ok"] for s in h["steps"] if str(s["no"]) in nos]
        st = " (lulus)" if oks and all(oks) else (" (GAGAL)" if oks else "")
    except (OSError, KeyError, ValueError):
        pass
    del k
    return f"{UJI[kode]} · langkah {langkah}{st}"


def v(kasus):
    """Kasus uji variasi lama, mis. v('V1.24') → baris tabel Lampiran A."""
    return f"uji variasi {kasus} (src/variasi_piutang_kas.json / variasi_hutang_pajak_gaji.json)"


T = "terbukti — uji lama"
T9 = "terbukti — uji V9"
TU = "terbukti — uji unit"
TB = "terbukti — cek buku/izin"
DT = "diperbaiki teks"
DA = "diperbaiki aplikasi + teks"
KP = "perlu keputusan pemilik"
BB = "belum dibuktikan"

# (kode, bagian, klaim, hasil, [bukti], catatan)
K = [
 # ── F01 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F01", "konsep.0", "Beranda Keuangan punya tiga tab: Perlu Tindakan, Posisi, Analisis", T, [u("F01", "1")], ""),
 ("F01", "konsep.2", "Posisi Kas = saldo akun kas dan bank di buku besar", T, [u("F01", "8, 9")], ""),
 ("F01", "cek_buku.0", "POSISI KAS = 1-1100 + 1-1110 di Neraca Saldo, sama sampai rupiah", T, [u("F01", "9")], ""),
 ("F01", "cek_buku.1", "Piutang 'tercatat' = saldo 1-1200; 'belum dikirim' di luar buku", T, [u("F01", "8")], ""),
 ("F01", "cek_buku.2", "Hutang = saldo 2-1100; modal kerja = kas + piutang tercatat − hutang", T, [u("F01", "8")], ""),
 ("F01", "cek_buku.3", "Pendapatan & Laba Bersih YTD = baris Sukacita di Analisis = jurnal tahun berjalan", T, [u("F01", "9, 10")], ""),
 ("F01", "kesalahan_umum.0", "[Terbitkan] di kartu 'Faktur pajak perlu terbit' langsung menerbitkan tanpa bertanya", T,
  [u("F13", "2"), u("A1", "19"), "V9:hutang-faktur#1"], "Klik [Terbitkan] langsung memunculkan bilah hijau 'Faktur Pajak … diterbitkan'."),
 ("F01", "kesalahan_umum.1", "[Batal] di form Terima pembayaran tidak mencatat apa pun", T, [u("F01", "5"), v("V1.21")], ""),
 ("F01", "kesalahan_umum.2", "Yang sama dengan buku adalah piutang 'tercatat', bukan total PIUTANG (AR)", T, [u("F01", "8")], ""),
 ("F01", "kesalahan_umum.3", "Cari 'Latihan NN' ikut memuat pelanggan 'Toko Kain Cicilan NN'", T, [u("F01", "4"), "LAPORAN_AUDIT B-29"], ""),
 ("F01", "catatan_pelatih", "Bilah Lokasi tampil untuk Finance karena izin lihat produk/logistik", T, [u("F01", "2"), "LAPORAN_AUDIT B-06"], ""),
 ("F01", "catatan_pelatih", "Tidak ada fitur ganti sandi sendiri; sandi direset Admin", KP, [u("F01", "11")], "Pertanyaan pemilik K-01."),
 ("F01", "catatan_pelatih", "'CHAT AI: Menunggu kunci penyedia model' — contoh laporan tetap jalan", T, [u("F01", "12")], ""),
 ("F01", "catatan_pelatih", "Kartu 'Selisih bayar' sudah diperbaiki (dulu Rp 0, tombol macet)", T, [u("F01", "7")], "B-01."),
 # ── F02 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F02", "konsep.0", "Tagihan SO menjadi piutang saat barang dikirim; uang masuk mengurangi piutang", T, [u("A1", "16, 20, 24")], ""),
 ("F02", "konsep.1", "Kwitansi dialokasikan ke SO yang dibayar", T, [u("F02", "4–6")], ""),
 ("F02", "konsep.2", "Jurnal otomatis: Kas/Bank (D) · Piutang Usaha (K)", T, [u("F02", "7")], ""),
 ("F02", "cek_buku.0", "Jurnal kwitansi 1-1100 D = 1-1200 K = total SO", T, [u("F02", "7")], ""),
 ("F02", "cek_buku.1", "SO Lunas, sisa Rp 0, tanpa titipan", T, [u("F02", "6")], ""),
 ("F02", "cek_buku.2", "Kas kwitansi tercatat di BCA dan dipakai di rekonsiliasi (F10)", T, [u("F10", "4")], ""),
 ("F02", "kesalahan_umum.0", "Dengan [Tertua dulu] uang masuk ke SO tertua lebih dulu, bukan ke SO yang dimaksud", T9, ["V9:piutang-tertua#1"], ""),
 ("F02", "kesalahan_umum.2", "Cara bayar Tunai → uang masuk Kas Kecil, bukan bank", T9, ["V9:piutang-tertua#1", "V9:piutang-tertua#2"], ""),
 ("F02", "kesalahan_umum.3", "SO bernilai ,50: layar membulatkan, buku menyimpan ,50", T, [u("F02", "4"), "LAPORAN_AUDIT B-19"], ""),
 ("F02", "catatan_pelatih", "Selisih Rp 0,50 di rekonsiliasi untuk SO bernilai ,50", KP, [u("F02", "4")], "Pertanyaan pemilik K-07."),
 ("F02", "catatan_pelatih", "Nominal di kotak alokasi tidak ditolak, dibatasi ke sisa tagihan", T, [v("V1.1"), v("V1.2")], ""),
 ("F02", "catatan_pelatih", "Label 'Jurnal Terbit' bisa diklik membuka jurnal", T, [u("F02", "7")], "B-13."),
 # ── F03 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F03", "konsep.0", "Bayar sebagian mengurangi piutang sebesar uang masuk; sisanya tetap piutang", T, [u("F03", "4, 5")], ""),
 ("F03", "konsep.1", "Di atas toleransi Rp 5.000 wajib keputusan berlabel: sisa tetap piutang, ubah jadwal, atau hapus sisa (wajib Manajer)", T9,
  ["V9:piutang-toleransi#2"], ""),
 ("F03", "konsep.2", "Umur piutang dihitung dari jatuh tempo; belum jatuh tempo vs 1–30, 31–60 …", T, [u("F03", "6, 7"), u("F05", "3"), v("V4.1")], ""),
 ("F03", "konsep.3", "Keputusan 'Sisa tetap jadi piutang' tidak membuat jurnal", T, [u("F03", "5")], ""),
 ("F03", "cek_buku.0", "Jurnal kwitansi bayar sebagian seimbang", T, [u("F03", "5")], ""),
 ("F03", "cek_buku.1", "Keputusan 'Sisa tetap jadi piutang' hanya dokumen KSC/SLB-…, tanpa jurnal", T, [u("F03", "4, 5")], ""),
 ("F03", "cek_buku.2", "SO berstatus Sebagian; sisa = total − pembayaran", T, [u("F03", "5")], ""),
 ("F03", "cek_buku.3", "Saldo & Umur: piutang tercatat = saldo akun piutang (selisih Rp 0)", T, [u("F03", "7"), u("F01", "8")], ""),
 ("F03", "kesalahan_umum.0", "Label alasan bawaan 'Dipotong biaya bank' — untuk bayar sebagian pilih 'Bayar sebagian (disepakati)'", T,
  [u("F03", "3"), "V9:piutang-toleransi#2"], "Pertanyaan pemilik K-11 (bawaan alasan)."),
 ("F03", "kesalahan_umum.1", "'Hapus sisa kurang bayar' membebankan sisa ke beban dan wajib Manajer", T9,
  ["V9:piutang-toleransi#3", "V9:piutang-toleransi#4"], "Finance yang memilih Hapus sisa: kwitansi tersimpan, keputusan masuk antrean Selisih Bayar; Manajer memutus → 6-9100 (D) / 1-1200 (K)."),
 ("F03", "kesalahan_umum.2", "[Batal] di jendela selisih: kwitansi belum tersimpan", T, [v("V1.20")], ""),
 ("F03", "kesalahan_umum.3", "Kotak cari Saldo & Umur menerima nama pelanggan atau sales, bukan nomor SO", T9, ["V9:piutang-umur#1"], ""),
 ("F03", "catatan_pelatih", "Selisih dalam toleransi (Rp 5.000) diputus otomatis sebagai pembulatan", T9, ["V9:piutang-toleransi#1"], ""),
 ("F03", "catatan_pelatih", "Kalimat batas menyebut 'sisa tagihan pesanan tujuan, belum jatuh tempo'", T, [u("F03", "2, 3")], "B-16."),
 ("F03", "catatan_pelatih", "SO ,50: rincian bisa beda Rp 1 dari angka besar", KP, [u("F02", "4")], "Pertanyaan pemilik K-07."),
 # ── F04 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F04", "konsep.0", "Kelebihan bayar dicatat sebagai kewajiban 2-1400 Uang Muka Pelanggan", T, [u("F04", "5")], ""),
 ("F04", "konsep.1", "Di [Atur sendiri] nominal tidak bisa melebihi sisa SO", T, [v("V1.1"), u("F02", "4")], ""),
 ("F04", "konsep.2", "[Tertua dulu] ke tagihan terbuka tertua; sisanya jadi titipan setelah diputus", T, [u("F04", "2–5"), "V9:piutang-tertua#3"], ""),
 ("F04", "konsep.3", "'Pakai titipan' menutup sebagian tagihan, sisanya dari transfer baru", T, [u("F04", "8, 9")], ""),
 ("F04", "cek_buku.0", "Kwitansi lebih bayar: 1-1100 D Rp 2.000.000 = 1-1200 K + 2-1400 K Rp 45.290 — seimbang", DT,
  [u("F04", "5")], "Contoh lama menulis 1-1200 K Rp 1.980.517,50 (D ≠ K). Dikoreksi ke Rp 1.954.710 sesuai uji jalan (KSC/JE-00147)."),
 ("F04", "cek_buku.1", "Saldo titipan = kolom Deposit; keputusan 'deposit' tidak menambah jurnal", T, [u("F04", "5, 6")], ""),
 ("F04", "cek_buku.2", "Kwitansi pakai titipan: Kas D + 2-1400 D = 1-1200 K; titipan kembali Rp 0", T, [u("F04", "9")], ""),
 ("F04", "kesalahan_umum.0", "Di [Atur sendiri] uang lebih tidak bisa dicatat; pilih [Tertua dulu]", T, [v("V1.1")], "K-08."),
 ("F04", "kesalahan_umum.1", "[Tertua dulu] saat ada tagihan terbuka lain: kelebihan melunasi tagihan itu, bukan jadi titipan", T9,
  ["V9:piutang-tertua#3"], ""),
 ("F04", "kesalahan_umum.2", "'Kembalikan ke pelanggan' wajib Manajer; Finance memilih deposit atau alokasi", T9,
  ["V9:piutang-kembalikan#1", "V9:piutang-kembalikan#2"], ""),
 ("F04", "catatan_pelatih", "Kelebihan ≤ Rp 5.000 dianggap pembulatan dan TIDAK menjadi titipan", DT, ["V9:piutang-tertua#4"],
  "SALAH: kelebihan ≤ Rp 5.000 diputus otomatis sebagai pembulatan TANPA jendela keputusan, tetapi tetap MENJADI titipan (2-1400 K, saldo titipan naik). Aturan 'naikkan Rp 500.000' tetap perlu supaya jendela muncul. LAPORAN_AUDIT C-27 juga menulis 'titipan tidak terbentuk'."),
 ("F04", "catatan_pelatih", "'Pakai titipan' di Atur sendiri melunasi SO; pesan lebih bayar menyebut uang diterima", T, [u("F04", "4, 9")], "B-14, B-15."),
 # ── F05 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F05", "konsep.0", "Rencana pembayaran membagi SO menjadi cicilan bertanggal", T, [u("F05", "1, 2")], ""),
 ("F05", "konsep.1", "Denda = sisa × 2%/bulan × hari telat ÷ 30, tanpa tenggang", T, [u("F05", "6"), v("V4.2")], ""),
 ("F05", "konsep.2", "Nota denda lahir sebagai usulan tanpa jurnal; nominal bisa diubah/dibebaskan Manajer", T9,
  ["V9:piutang-denda#1", "V9:piutang-denda#3"], ""),
 ("F05", "konsep.3", "Nota terbit → 1-1270 Piutang Denda / 4-9300 Pendapatan Denda", T, [u("F05", "8")], ""),
 ("F05", "cek_buku.0", "Nota usulan belum berjurnal", T, [u("F05", "5")], ""),
 ("F05", "cek_buku.1", "Nota terbit contoh Rp 1.679.846 × 2% × 20/30", DT, [u("F05", "8")],
  "Contoh menulis Rp 22.398,09; hitungan & uji jalan = Rp 22.397,95 (KSC/JE-00151). Dikoreksi."),
 ("F05", "cek_buku.2", "Piutang usaha SO tidak berubah; denda piutang terpisah (1-1270)", T, [u("F05", "8")], ""),
 ("F05", "kesalahan_umum.0", "Finance tidak punya [Susun Jadwal]; rencana baru disusun Admin Penjualan/Manajer", T9, ["V9:piutang-umur#2"], ""),
 ("F05", "kesalahan_umum.1", "'est. — belum jadi nota' belum dokumen maupun jurnal", T, [u("F05", "3, 5")], ""),
 ("F05", "kesalahan_umum.2", "Sesudah terbit, mengubah/membebaskan butuh Manajer dan jurnal pembalik", T9,
  ["V9:piutang-denda#4", "V9:piutang-denda#5"], ""),
 ("F05", "kesalahan_umum.3", "Tombol Buat Nota Denda mati bila tidak ada denda baru", T, [u("F05", "5")], ""),
 ("F05", "catatan_pelatih", "Kotak cari berisi nomor nota: kartu RENCANA AKTIF dan jumlah tab Jadwal ikut tersaring", DT, ["V9:piutang-denda#2"],
  "Sejak perbaikan C-25 kartu RENCANA AKTIF tetap seluruh PT; hanya angka di tab Jadwal Pembayaran yang tersaring."),
 ("F05", "catatan_pelatih", "Status rencana 'Aktif' (dulu 'Active')", T, [u("F05", "1")], "B-17."),
 # ── F06 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F06", "konsep.0", "Izin kredit = tambahan batas sementara yang diajukan Sales", T, [u("A1", "7, 8"), u("F06", "1")], ""),
 ("F06", "konsep.1", "Eksposur = terkirim + belum dikirim + giro belum cair − titipan, dibanding plafon", T, [u("F06", "note"), u("A1", "4, 6")], ""),
 ("F06", "konsep.2", "Finance hanya membaca antrean kredit; Manajer memutus", T, [u("F06", "1"), u("A1", "8")], ""),
 ("F06", "konsep.3", "Plafon & izin kredit tidak mengubah buku besar", TB, [u("A1", "5, 9")],
  "Cek buku V9: jenis sumber jurnal di basis data tidak memuat izin kredit/profil kredit (tidak ada jalur posting)."),
 ("F06", "cek_buku.2", "Izin kredit tetap 'Menunggu' sampai Manajer memutus", T, [u("F06", "1"), u("A1", "8")], ""),
 ("F06", "kesalahan_umum.0", "Finance tidak punya tombol Setujui", T, [u("F06", "1")], ""),
 ("F06", "kesalahan_umum.1", "'PLAFON tanpa batas' = plafon belum diatur/disetujui", T, [u("K06", "1")], "K-09."),
 ("F06", "kesalahan_umum.3", "Janji bayar dicatat lewat ikon telepon di Penagihan & Penerimaan", DA,
  ["V9:piutang-janji#1", "V9:piutang-janji#2", "jest latihV9TindakLanjutIzin.test.js"],
  "Untuk Finance SALAH: server menolak (403, izin ubah pesanan). Ikon telepon & lonceng tampil untuk Finance padahal ditolak → kini disembunyikan bagi yang tanpa izin (CollectionWorklist.jsx). Teks dikoreksi: janji dicatat Sales/Admin Sales; pertanyaan pemilik K-10."),
 ("F06", "catatan_pelatih", "Satu pengajuan profil kredit terbuka per pelanggan per PT", T, [u("K06", "2")], ""),
 ("F06", "catatan_pelatih", "Hasil pencarian antrean tidak tertimpa daftar lama", TU, ["jest latihPiutangKredit.test.js"], "B-18."),
 # ── F07 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F07", "konsep.0", "PD disetujui berjenjang sebelum dicairkan", T, [u("F07", "2")], ""),
 ("F07", "konsep.1", "Pencairan dicatat sebagai uang muka 1-1400, belum beban", T, [u("F07", "4")], ""),
 ("F07", "konsep.2", "LPJ mengubah uang muka jadi beban per kategori", T, [u("F07", "8")], ""),
 ("F07", "konsep.3", "Sisa dikembalikan → saldo uang muka PD nol", T, [u("F07", "10")], ""),
 ("F07", "cek_buku.0", "Jurnal pencairan 1-1400 D / 1-1110 K", T, [u("F07", "4")], ""),
 ("F07", "cek_buku.1", "Jurnal LPJ beban D / 1-1400 K", T, [u("F07", "8"), v("V2.3")], ""),
 ("F07", "cek_buku.2", "Jurnal pengembalian sisa 1-1110 D / 1-1400 K", T, [u("F07", "10")], ""),
 ("F07", "cek_buku.3", "Saldo uang muka PD 0; Kas Toko bersih turun sebesar biaya", T, [u("F07", "10, 11")], ""),
 ("F07", "cek_buku.4", "Biaya > uang muka: LPJ mencatat 2-1650 Hutang Reimburse (K) dan muncul [Bayar Reimburse]", T9,
  ["V9:kas#7", "V9:kas#8", v("V2.7")], ""),
 ("F07", "kesalahan_umum.1", "Kategori LPJ menentukan akun beban", T, [u("F07", "8")], ""),
 ("F07", "kesalahan_umum.2", "LPJ tanpa [Ajukan] tetap Draf, Manajer tidak bisa menyetujui; bukti hanya bisa diunggah selama Draf", T9,
  ["V9:kas#2", "V9:kas#3", "V9:kas#4"], ""),
 ("F07", "catatan_pelatih", "Finance tidak bisa menyetujui PD maupun LPJ", T9, ["V9:kas#4"],
  "LPJ di layar (V9). PD: izin Finance tanpa 'setujui' (server); jenjang Pimpinan & Bagian Keuangan = Admin (K-13)."),
 ("F07", "catatan_pelatih", "[Tanda Terima] mencetak bukti serah", T9, ["V9:kas#1"], ""),
 ("F07", "catatan_pelatih", "LPJ ditolak Manajer → pembuat klik [Perbaiki & Ajukan Lagi]", T9, ["V9:kas#5", "V9:kas#6"], ""),
 ("F07", "catatan_pelatih", "LPJ yang diketik Finance tercatat atas nama pemohon PD", T, [u("F07", "7")], "B-25."),
 ("F07", "catatan_pelatih", "'Lampiran wajib' menolak LPJ tanpa bukti", T, [v("V2.2")], "K-17."),
 # ── F08 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F08", "konsep.0", "Kwitansi tunai sales melunasi piutang; uang masih di sales", T, [u("F08", "3")], ""),
 ("F08", "konsep.1", "Uang di sales dicatat 1-1280 Piutang Titipan Karyawan", T, [u("F08", "3")], ""),
 ("F08", "konsep.2", "Menjadi kas setelah Finance [Terima setoran]", T, [u("F08", "4, 5")], ""),
 ("F08", "konsep.3", "Uang kurang → setoran ditolak, titipan tetap atas nama sales", T9, ["V9:kas#9"], ""),
 ("F08", "cek_buku.0", "Kwitansi tunai sales: 1-1280 D / 1-1200 K, belum ada kas", T, [u("F08", "3")], ""),
 ("F08", "cek_buku.1", "Terima setoran: 1-1110 D / 1-1280 K", T, [u("F08", "5")], ""),
 ("F08", "cek_buku.2", "Titipan kwitansi ini Rp 0 setelah setoran diterima", T, [u("F08", "5")], ""),
 ("F08", "kesalahan_umum.0", "Hitung dulu; bila berbeda [Tolak] + alasan", T9, ["V9:kas#9"], ""),
 ("F08", "kesalahan_umum.2", "Sales pemegang izin kas mencatat kas langsung, tanpa titipan", TU, ["tests_mem test_PMT4_titipan_sales.py::U3"], ""),
 ("F08", "catatan_pelatih", "[Terima setoran] mati untuk penyetor sendiri", TU,
  ["jest pmt4TitipanSales.test.js (cth-deposit-own)", "tests_mem test_PMT4_titipan_sales.py::U7"], ""),
 ("F08", "catatan_pelatih", "Pengaturan tunai sales = titipan dinyalakan skrip latihan", KP, [], "K-14."),
 # ── F09 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F09", "konsep.1", "Kategori menentukan akun lawan; Operasional keluar → 6-4000", T, [u("F09", "6"), v("V2.8")], ""),
 ("F09", "konsep.2", "Semua rekening bank & kas besar memakai 1-1100", T, [u("F09", "6"), u("K04", "4")], ""),
 ("F09", "konsep.3", "Transaksi bank baru berstatus rekonsiliasi 'Belum'", T, [u("F09", "7")], ""),
 ("F09", "cek_buku.0", "Jurnal kas keluar Operasional 6-4000 D / 1-1100 K", T, [u("F09", "6")], ""),
 ("F09", "cek_buku.1", "Kartu BCA turun; mutasi 'Belum'", T, [u("F09", "7")], ""),
 ("F09", "cek_buku.2", "Peta kategori: …; uang masuk selain 'Setoran Modal' → 1-9999", DT, [v("V2.8–V2.19")],
  "Transfer / Top-up keluar → 1-1150 D, masuk → 1-1150 K (V2.14, V2.15), bukan 1-9999. Teks dikoreksi."),
 ("F09", "kesalahan_umum.1", "'Transfer / Top-up': sisi keluar jadi beban, sisi masuk Suspense → laba turun palsu", DT, [v("V2.14"), v("V2.15")],
  "Usang sesudah perbaikan B-26: kedua sisi lewat 1-1150 Kas & Bank Transit. Kesalahan diganti: mencatat satu sisi saja/nominal beda → 1-1150 tidak nol."),
 ("F09", "kesalahan_umum.2", "Uang masuk lain-lain jatuh ke Suspense", T, [v("V2.19")], "K-12."),
 ("F09", "catatan_pelatih", "Kotak cari Jurnal tidak mencari nomor KSC/CASH di kolom Sumber", DT,
  ["V9:kas#10", "uji variasi V8 (cari nomor kwitansi)"], "Usang sesudah perbaikan B-27: nomor KSC/CASH-… ditemukan."),
 ("F09", "catatan_pelatih", "Pertanyaan pemilik: 'Transfer / Top-up' tidak memakai 1-1150", DT, [v("V2.14")], "Sudah memakai 1-1150 (B-26); dihapus dari daftar pertanyaan."),
 ("F09", "catatan_pelatih", "Form Transaksi Kas tidak menampilkan akun lawan sebelum disimpan", T, [u("F09", "3")], "K-15."),
 # ── F10 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F10", "konsep.1", "Mencocokkan tidak membuat jurnal baru", T, [u("F10", "7"), "V9:kas#11"], ""),
 ("F10", "konsep.2", "Mutasi yang belum ada di buku dibukukan dari layar rekonsiliasi", T, [u("F10", "6, 7")], ""),
 ("F10", "konsep.3", "Skor ≥ 80 tertaut otomatis; ≥ 60 usulan", T, [u("F10", "4")], ""),
 ("F10", "cek_buku.0", "Pencocokan tanpa jurnal; kas berubah status 'Terekonsiliasi'", T, [u("F10", "7, 9")], ""),
 ("F10", "cek_buku.1", "Biaya bank 6-8000 D / 1-1100 K", T, [u("F10", "7")], ""),
 ("F10", "cek_buku.2", "Bunga bank → Pendapatan Bunga; Titipkan → 2-1950", TU, ["tests_mem test_PK15_titipan_biaya_bank.py"], ""),
 ("F10", "cek_buku.3", "Selisih per periode = mutasi bersih − buku bersih", T, [v("V3.23"), u("F10", "8")], ""),
 ("F10", "kesalahan_umum.0", "Nominal berkoma tanpa kutip → kolom bergeser, baris ditolak", T, [v("V3.20")], ""),
 ("F10", "kesalahan_umum.1", "Keterangan sama → dilewati sebagai duplikat", T, [v("V3.22")], ""),
 ("F10", "kesalahan_umum.3", "[Abaikan] tidak membukukan beban; salah cocok dibatalkan [Lepas]", T9, ["V9:kas#11", "V9:kas#12"], ""),
 ("F10", "catatan_pelatih", "Baris ekspedisi (skor 60) & biaya admin tidak tertaut otomatis", T, [u("F10", "4")], ""),
 ("F10", "catatan_pelatih", "Sesudah beberapa cocok manual muncul '1 usulan menunggu' aturan pembelajaran", BB, [],
  "Butuh beberapa peserta mencocokkan manual baris serupa; tidak diuji (perilaku kelas)."),
 ("F10", "catatan_pelatih", "Bentuk nominal & pemisah TAB/titik koma terbaca", T, [v("V3.6–V3.15")], ""),
 ("F10", "catatan_pelatih", "Impor tempel 'tempel baris', ringkasan berperiode, tiga tombol berjurnal minta konfirmasi", T, [u("F10", "3, 6, 8")], "B-20–B-22."),
 # ── F11 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F11", "konsep.0", "Hutang lahir saat tagihan terposting; bayar mengurangi hutang & bank", T, [u("F11", "6"), u("A2", "16, 23")], ""),
 ("F11", "konsep.1", "3-way match: jumlah dan harga harus sama sebelum dibayar", DT, ["V9:hutang-tagihan#5", "V9:hutang-tagihan#6", "V9:hutang-tagihan#7"],
  "Tidak harus sama: harga ±5% dan selisih bernilai ≤ Rp 50.000 dianggap cocok; di luar itu tagihan menunggu persetujuan dan tidak bisa dibayar."),
 ("F11", "konsep.2", "Sisa GR/IR nol setelah tagihan masuk", T, [u("F11", "7"), u("A2", "26")], ""),
 ("F11", "cek_buku.0", "Jurnal bayar 2-1100 D / 1-1100 K", T, [u("F11", "6")], ""),
 ("F11", "cek_buku.1", "Jurnal tagihan 2-1150 D + 1-1500 D / 2-1100 K", T, [u("K02", "5"), u("A2", "16")], ""),
 ("F11", "cek_buku.2", "Sisa GR/IR PO = Rp 0", T, [u("F11", "7")], ""),
 ("F11", "kesalahan_umum.0", "Tagihan berselisih jangan dibayar sebelum diputus Pembelian atau Manajer", DT, ["V9:hutang-tagihan#7", "V9:hutang-tagihan#8"],
  "Finance tidak punya [Bayar] pada tagihan 'Menunggu persetujuan'; pemutusnya Manajer/Admin (bukan Pembelian), dan bukan pembuat tagihan (kontrol dua orang)."),
 ("F11", "kesalahan_umum.2", "Kurang ≤ Rp 5.000 ditutup otomatis", T, [v("V5 1.864.000")], "Kini diberitahukan di layar (V-07)."),
 ("F11", "kesalahan_umum.3", "GR/IR tanpa 'Tampilkan yang sudah nol' → 'Tidak ada sisa GR/IR yang cocok'", T9, ["V9:hutang-tagihan#2"], ""),
 ("F11", "catatan_pelatih", "Finance melihat & membayar; membuat & membatalkan tagihan wewenang Manajer", T9, ["V9:hutang-tagihan#1", u("F11", "3")], "B-08."),
 ("F11", "catatan_pelatih", "Pita kuning 'Selisih harga pembelian belum diatur' di GR/IR", T, ["V9:hutang-tagihan#9", "V9:hutang-grir#1", u("K02", "4")], "K-26."),
 ("F11", "catatan_pelatih", "Kalender Tanggal bayar mengizinkan bulan depan", KP, [v("V5 2026-12-15")], "K-16."),
 # ── F12 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F12", "konsep.1", "Manajer membuat/memverifikasi/menjadwalkan; Admin menyetujui; Finance membayar", T, [u("F12", "1–9")], ""),
 ("F12", "konsep.2", "Pengaju kontrabon tidak boleh menyetujuinya sendiri", T, [u("F12", "6")], ""),
 ("F12", "konsep.3", "Kontrabon tidak membuat jurnal sampai dibayar", TB, [u("F12", "10"), "V9:hutang-kontrabon#3"],
  "Cek buku V9: satu-satunya jurnal kontrabon adalah jurnal pembayaran (2-1100 D / 1-1100 K)."),
 ("F12", "cek_buku.0", "Jurnal bayar kontrabon seimbang, satu kas keluar", T, [u("F12", "10")], ""),
 ("F12", "cek_buku.1", "Tagihan di kontrabon Lunas, sisa Rp 0", T, [u("F12", "10")], ""),
 ("F12", "cek_buku.2", "Membuat/verifikasi/setuju/jadwal tanpa jurnal", TB, ["V9:hutang-kontrabon#3"], "Lihat konsep.3."),
 ("F12", "kesalahan_umum.0", "Finance tidak punya [Kontrabon baru]", T, [u("F12", "1")], ""),
 ("F12", "kesalahan_umum.1", "Manajer menyetujui kontrabon buatannya sendiri → ditolak", T, [u("F12", "6")], ""),
 ("F12", "kesalahan_umum.2", "Tombol bayar baru ada sesudah 'Dijadwalkan bayar'", T9, ["V9:hutang-kontrabon#2", "V9:hutang-kontrabon#3"], "K-05."),
 ("F12", "catatan_pelatih", "Satu faktur hanya boleh ada di satu kontrabon", T9, ["V9:hutang-kontrabon#1"], ""),
 ("F12", "catatan_pelatih", "Finance membaca 'Langkah berikutnya — Jadwalkan pembayaran'", T9, ["V9:hutang-kontrabon#2"], "B-09."),
 ("F12", "catatan_pelatih", "Server mengizinkan bayar kontrabon 'Disetujui' tanpa jadwal", KP, [], "K-05."),
 # ── F13 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F13", "konsep.0", "Faktur pajak tidak membuat jurnal", T, [u("F13", "6")], ""),
 ("F13", "konsep.1", "PPN keluaran dijurnal saat surat jalan", T, [u("F13", "6"), u("A1", "16")], ""),
 ("F13", "konsep.2", "PPN 12% × DPP nilai lain 11/12", T, [u("F13", "5"), v("V6 DPP nilai lain")], ""),
 ("F13", "konsep.3", "NSFP diisi manual setelah terbit", T, [u("F13", "4")], ""),
 ("F13", "cek_buku.1", "PPN faktur = 2-1200 K di jurnal pengiriman", T, [u("F13", "6")], ""),
 ("F13", "cek_buku.2", "Status bayar & sisa piutang SO tidak berubah", T, [u("F13", "6")], ""),
 ("F13", "cek_buku.3", "Panel 'Pencocokan PPN keluaran' membandingkan faktur dengan 2-1200 per masa", BB, [],
  "Panel ada di layar Pajak (TaxOutputRecon) tetapi angkanya belum dicocokkan oleh uji."),
 ("F13", "kesalahan_umum.0", "Faktur yang terbit hanya bisa dibatalkan Manajer", T9, ["V9:hutang-faktur#1"], ""),
 ("F13", "kesalahan_umum.1", "NSFP kembar ditolak 'sudah dipakai'", T, [v("V6 NSFP kembar")], ""),
 ("F13", "kesalahan_umum.3", "Lencana 'Data Pajak Belum Lengkap' untuk pelanggan tanpa NPWP/NIK", T, [u("F13", "3")], ""),
 ("F13", "catatan_pelatih", "Finance boleh menerbitkan, isi NSFP, faktur pengganti; batal = Manajer", T9, ["V9:hutang-faktur#1", u("F13", "2, 4")], ""),
 ("F13", "catatan_pelatih", "Faktur per pesanan tanpa NPWP boleh terbit; NSFP tanpa cek digit; e-Faktur hanya sakelar", KP, [v("V6 NSFP")], "K-03, K-04, K-21."),
 # ── F14 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F14", "konsep.0", "Sample berbayar disetujui Finance/Admin Sample sebelum ke gudang", T, [u("F14", "5")], ""),
 ("F14", "konsep.2", "Uang sebelum kirim → 2-1400 Uang Muka", T, [u("F14", "6")], ""),
 ("F14", "konsep.3", "PPN Rp 75.000 × 11/12 × 12% = Rp 8.250", T, [u("F14", "2")], ""),
 ("F14", "cek_buku.0", "Kwitansi sample 1-1100 D / 2-1400 K Rp 83.250", T, [u("F14", "6")], ""),
 ("F14", "cek_buku.1", "Persetujuan pembayaran tanpa jurnal", T, [u("F14", "6")], ""),
 ("F14", "cek_buku.2", "Saat sample dikirim: jurnal penjualan terbit dan uang muka menutup piutang", TU,
  ["tests_mem test_PK32_nota_kredit.py::U3_U4 (dibayar sebelum kirim lalu kirim)"],
  "Diuji pada pesanan biasa (jalur sama); pengiriman sample sendiri tidak diuji di layar."),
 ("F14", "kesalahan_umum.3", "Uang baru sebagian → 'kurang Rp …' dan jendela 'Uang belum lengkap'", T, [v("V6 sample 50.000")], ""),
 ("F14", "catatan_pelatih", "Nilai potong berubah > ±5% → 'ACC ulang'", TU, ["jest f15SamplePaymentReapproval.test.js"], ""),
 ("F14", "catatan_pelatih", "Harga sample latihan Rp 25.000/yard", T, [u("F14", "2")], ""),
 # ── F15 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F15", "konsep.0", "Posting proses gaji → beban + Hutang Gaji, BPJS, PPh 21", T, [u("H03", "7")], ""),
 ("F15", "konsep.1", "Bayar gaji = satu kas keluar dari rekening berperuntukan Gaji", T, [u("F15", "3, 4"), "V9:gaji#7"], ""),
 ("F15", "konsep.2", "Setoran mengurangi hutang pajak; boleh sebagian", T, [u("F15", "6, 7"), v("V7 setoran 36.945")], ""),
 ("F15", "cek_buku.0", "Bayar gaji 2-1600 D / 1-1100 K", T, [u("F15", "4")], ""),
 ("F15", "cek_buku.1", "Setoran PPh 21 2-1800 D / 1-1100 K", T, [u("F15", "7")], ""),
 ("F15", "cek_buku.2", "Sisa = Kewajiban − setoran", T, [u("F15", "5, 6")], ""),
 ("F15", "kesalahan_umum.1", "Masa gaji November → kartu Rp 0", T9, ["V9:gaji#9"], ""),
 ("F15", "kesalahan_umum.2", "Setoran melebihi sisa ditolak", T, [v("V7 sisa + 1.000")], ""),
 ("F15", "kesalahan_umum.3", "'Tanpa Rekening — Bayar Tunai' di daftar transfer", T, [u("F15", "2")], ""),
 ("F15", "catatan_pelatih", "Proses reguler per PT & masa hanya satu", T9, ["V9:gaji#4"], ""),
 ("F15", "catatan_pelatih", "Membatalkan setoran butuh izin Manajer", T9, ["V9:gaji#10"], ""),
 ("F15", "catatan_pelatih", "Isian nominal setoran memakai format rupiah baku", T, [v("V7 40.864,50")], "B-10."),
 ("F15", "catatan_pelatih", "PPh 21 susulan bisa bersen", KP, [v("V7 PPh 21 TER")], "K-06."),
 # ── F16 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F16", "konsep.0", "Setiap jurnal seimbang", T, [u("F16", "1, 3")], ""),
 ("F16", "konsep.1", "Neraca Saldo menampilkan saldo akhir semua akun", T, [u("F16", "6")], ""),
 ("F16", "konsep.2", "SO → jurnal pendapatan & HPP saat kirim, penerimaan saat bayar", T, [u("F16", "4")], ""),
 ("F16", "konsep.3", "Jejak Dokumen: rantai SO sampai jurnal dengan nilai", T, [u("F16", "8")], ""),
 ("F16", "cek_buku.0", "Jurnal penerimaan = kwitansi = kas", T, [u("F16", "2, 3")], ""),
 ("F16", "cek_buku.1", "Jurnal pendapatan contoh", T, [u("F16", "4")], ""),
 ("F16", "cek_buku.2", "Jurnal HPP contoh", T, [u("F16", "4")], ""),
 ("F16", "cek_buku.3", "Saldo 1-1200 buku besar = Neraca Saldo = piutang tercatat", T, [u("F16", "5"), u("F01", "8")], ""),
 ("F16", "kesalahan_umum.0", "Keterangan jurnal kas memuat nomor kwitansi, bukan nomor SO", T, [u("F16", "2")], ""),
 ("F16", "kesalahan_umum.1", "TOTAL DEBIT di kartu = total kolom Neraca Saldo", T, [u("F16", "1, 6")], ""),
 ("F16", "kesalahan_umum.2", "Rantai dokumen perlu digeser; ada 'Daftar relasi'", T, [u("F16", "8")], ""),
 ("F16", "catatan_pelatih", "Finance hanya izin lihat; tombol tulis disembunyikan", T, [u("F16", "1, 7"), "jest latihBukuBesarIzin.test.js"], "B-02."),
 ("F16", "catatan_pelatih", "Simpul jurnal di Jejak Dokumen bernilai", T, [u("F16", "8")], "B-03."),
 ("F16", "catatan_pelatih", "Jurnal kas lama 'Kas in', baru 'Kas masuk'", T, [u("F16", "2"), "uji dokumen D2"], "P-09."),
 # ── F17 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F17", "konsep.0", "Laba-Rugi = pendapatan − HPP − beban", T, [u("F17", "2")], ""),
 ("F17", "konsep.1", "Aset = Kewajiban + Ekuitas; laba tahun berjalan masuk ekuitas", T, [u("F17", "4"), "V9:buku#1"], ""),
 ("F17", "konsep.2", "Arus Kas menjelaskan perubahan kas", T, [u("F17", "5")], ""),
 ("F17", "konsep.3", "Angka laporan dari jurnal; klik akun → buku besar", T, [u("F17", "3")], ""),
 ("F17", "cek_buku.0", "Laba-Rugi = saldo akun 4/5/6", T, [u("F17", "2"), v("V8 Laba-Rugi")], ""),
 ("F17", "cek_buku.1", "Neraca seimbang dari saldo akun", T, [u("F17", "4"), v("V8 Neraca")], ""),
 ("F17", "cek_buku.2", "Kas akhir Arus Kas = 1-1100 + 1-1110", T, [u("F17", "5")], ""),
 ("F17", "cek_buku.3", "Profitabilitas: selisih belum dijelaskan Rp 0 (denda masuk)", T, [u("F17", "6")], "B-04."),
 ("F17", "kesalahan_umum.1", "Laba bulan ini bisa beda tanda dengan Laba Tahun Berjalan", T, [u("F17", "2, 4")], ""),
 ("F17", "kesalahan_umum.2", "Saldo awal rekening yang didaftarkan tahun ini di baris terpisah", T, [u("F17", "5")], ""),
 ("F17", "kesalahan_umum.3", "Suspense harus nol sebelum tutup buku", TU, ["tests_mem test_PK43_alur_layar.py::U11"], ""),
 ("F17", "catatan_pelatih", "Total Pendapatan termasuk denda 4-9300", T, [u("F17", "2, 3")], ""),
 ("F17", "catatan_pelatih", "Denda/bunga/klaim di Pendapatan, bukan 'Pendapatan lain-lain'", KP, [], "K-02."),
 # ── F18 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("F18", "konsep.0", "Tutup buku mengunci periode; jurnal di periode itu ditolak; laba/rugi → Laba Ditahan", T,
  [u("F18", "3–5"), v("V1.26"), v("V8 periode tertutup")], ""),
 ("F18", "konsep.1", "Daftar periksa memuat suspense & posting gagal", T, [u("F18", "2")], ""),
 ("F18", "konsep.2", "Buka Periode perlu dua orang; Buka Kembali khusus Admin", T, [u("F18", "6, 9")],
  "Izin server: Manajer akuntansi tanpa 'buka kembali', Admin punya (izin peran)."),
 ("F18", "konsep.3", "Posting Gagal harus kosong sebelum tutup buku", T, [u("F18", "7")], ""),
 ("F18", "cek_buku.0", "Pratinjau Oktober (contoh) jurnal penutup seimbang", DT, [u("F18", "3")],
  "Contoh lama tidak seimbang (6-1000 Rp 45.300.000 · 6-5000 Rp 4.521.000 → K Rp 54.364.612 ≠ D Rp 61.741.612). Dikoreksi sesuai tangkapan layar uji: 53.300.000 · 4.543.612 · 3.898.000."),
 ("F18", "cek_buku.1", "September terkunci sesudah Tutup, terbuka sesudah Buka Kembali", T, [u("F18", "5, 9")], ""),
 ("F18", "cek_buku.2", "Usul buka periode Menunggu → Ditolak, tanpa jendela aktif", T, [u("F18", "6, 8")], ""),
 ("F18", "cek_buku.3", "Akhir latihan: periode tertutup & usul sama dengan awal", T, [u("F18", "10")], ""),
 ("F18", "kesalahan_umum.1", "Daftar periksa dimuat bersama Pratinjau", T, [u("F18", "2")], ""),
 ("F18", "kesalahan_umum.2", "Buka Periode = jendela sementara; batalkan penutupan = Buka Kembali (Admin)", T, [u("F18", "6, 9")], ""),
 ("F18", "kesalahan_umum.3", "Suspense tidak nol → penutupan diblokir", TU, ["tests_mem test_PK43_alur_layar.py::U11"],
  "Admin dapat menembus dengan alasan (K-15 di kode)."),
 ("F18", "catatan_pelatih", "Jendela Buka Periode aktif memunculkan pita merah untuk semua pengguna", BB, [],
  "Sengaja tidak diuji di layar (memengaruhi semua pengguna); dasar: komponen PeriodUnlockBanner."),
 ("F18", "catatan_pelatih", "Penggajian belum diposting → 'Perlu Dilihat' + peringatan oranye; tutup tetap bisa", TU, ["jest pk43AlurLayar.test.js"], "C-23."),
 ("F18", "catatan_pelatih", "'Reopen' kini 'Buka Kembali'", T, [u("F18", "9")], "B-05."),
 # ── H01–H04 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("H01", "konsep.0", "PTKP menentukan kategori TER; rekening dipakai daftar transfer", T, [u("K09", "2"), u("H04", "2")], ""),
 ("H01", "konsep.1", "Kompensasi bertanggal berlaku; perubahan disahkan Manajer", T, [u("H01", "6"), "tests_mem test_PYT2_riwayat_kompensasi.py"], ""),
 ("H01", "cek_buku.0", "Data karyawan tidak membuat jurnal", T, [u("H01", "5, 6"), u("H03", "7")], ""),
 ("H01", "kesalahan_umum.0", "TK1 → kategori A, K1 → B", T, [u("K09", "2")], ""),
 ("H01", "kesalahan_umum.1", "Tanggal masuk kosong → kompensasi berlaku sejak hari ini", T9, ["V9:gaji#1"], ""),
 ("H01", "kesalahan_umum.3", "Gaji pokok tidak diubah lewat Ubah karyawan", T9, ["V9:gaji#2", "jest pyt2RiwayatKompensasi.test.js"], ""),
 ("H01", "catatan_pelatih", "Gaji pokok karyawan baru langsung disahkan", T, [u("H01", "6")], "K-32."),
 ("H02", "konsep.0", "Masukan dihitung sesudah disahkan; susulan memuat semua masukan disahkan belum terpakai", T, [u("H03", "1, 2")], ""),
 ("H02", "konsep.1", "Lembur = jam × (gaji pokok + tunjangan dasar) ÷ 173 × pengali, di proses reguler", TU, ["tests_mem test_PYT3_aturan_hitung.py (lembur)"], ""),
 ("H02", "cek_buku.0", "Masukan & lembur tidak membuat jurnal", T, [u("H02", "2–4"), u("H03", "7")], ""),
 ("H02", "kesalahan_umum.1", "Nominal bersen ditolak (rupiah bulat)", T9, ["V9:gaji#3", "jest pyt1KomponenMasukan.test.js"], ""),
 ("H02", "kesalahan_umum.2", "Masukan disahkan ikut susulan siapa pun yang menghitung lebih dulu", T, [u("H03", "2")], ""),
 ("H02", "kesalahan_umum.3", "Lembur hanya dihitung di proses reguler", TU, ["tests_mem test_PYT3_aturan_hitung.py"], ""),
 ("H02", "catatan_pelatih", "Finance bisa menyetujui lembur yang ia ajukan", KP, [], "K-32."),
 ("H03", "konsep.0", "Finance menghitung/mengajukan/memposting; Manajer mengesahkan & membatalkan", T, [u("H03", "4–6"), "V9:gaji#6"], ""),
 ("H03", "konsep.1", "Satu proses reguler per masa; susulan tanpa BPJS", T, [u("H03", "3"), "V9:gaji#4"], ""),
 ("H03", "konsep.2", "PPh 21 gabungan sebulan × TER", T, [v("V7 PPh 21 TER")], ""),
 ("H03", "cek_buku.0", "Jurnal gaji susulan contoh", T, [u("H03", "7")], ""),
 ("H03", "kesalahan_umum.1", "Jenis Reguler membuka proses reguler yang ada", T9, ["V9:gaji#4"], ""),
 ("H03", "kesalahan_umum.2", "'Tidak ada masukan yang belum terpakai untuk Oktober 2026'", T9, ["V9:gaji#5"], ""),
 ("H03", "kesalahan_umum.3", "Anulir proses yang diposting hanya Manajer", T9, ["V9:gaji#6"], ""),
 ("H04", "konsep.0", "Bayar gaji satu kas keluar dari rekening Gaji", T, [u("H04", "1, 2, 4")], ""),
 ("H04", "konsep.1", "Tanggal bayar ≥ tanggal buku; gaji dibayar tidak bisa dianulir", T9,
  ["V9:gaji#6", "V9:gaji#8", "jest pyt4BayarGaji.test.js", "tests_mem test_PYT4_bayar_gaji.py::U6"], ""),
 ("H04", "konsep.2", "Hutang PPh 21 disetor lewat Setoran & Pajak", T, [u("H04", "6, 7")], ""),
 ("H04", "cek_buku.0", "Jurnal bayar gaji", T, [u("H04", "4")], ""),
 ("H04", "cek_buku.1", "Jurnal setoran PPh 21", T, [u("H04", "7")], ""),
 ("H04", "cek_buku.2", "Saldo 2-1600 & 2-1800 proses ini nol", T, [u("H04", "4, 7")], ""),
 ("H04", "kesalahan_umum.1", "Tanggal bayar sebelum jurnal → tombol mati beralasan", TU, ["jest pyt4BayarGaji.test.js"], "C-06."),
 # ── K01–K09 ──────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("K01", "konsep.0", "Awalan kode per kelompok; 5 & 6 tampil di bawah Beban", T, [u("K01", "2")], ""),
 ("K01", "konsep.1", "Saldo normal Debit/Kredit per kelompok", T, [u("K01", "2, 3")], ""),
 ("K01", "konsep.2", "Akun induk mengelompokkan; detail dijurnal", T, [u("K01", "2, 4")], ""),
 ("K01", "konsep.3", "Akun sistem; akun kontrol hanya lewat dokumen", T, [u("K01", "4"), "tests_mem test_PK36_akun_kontrol.py"], ""),
 ("K01", "konsep.4", "Finance hanya melihat; Manajer/Admin kelola; akun baru untuk PT terpilih", T, [u("K01", "5, 6")], ""),
 ("K01", "cek_buku.0", "Total akun di kartu = jumlah akun", T, [u("K01", "1")], ""),
 ("K01", "cek_buku.1", "Akun detail punya induk", T, [u("K01", "4")], ""),
 ("K01", "cek_buku.2", "Bagan sesudah latihan sama dengan sebelumnya", T, [u("K01", "8")], ""),
 ("K01", "kesalahan_umum.1", "Finance tidak punya tombol Tambah Akun", T, [u("K01", "5")], ""),
 ("K01", "kesalahan_umum.2", "Tambah akun di 'Semua PT' → Template Global", T9, ["V9:buku#2"], ""),
 ("K01", "catatan_pelatih", "Ikon hapus hanya akun khusus PT, dengan konfirmasi", TU, ["jest latihK01HapusAkun.test.js"], "C-01."),
 ("K02", "konsep.0", "Dokumen menjurnal lewat pemetaan", T, [u("K02", "2, 3, 5")], ""),
 ("K02", "konsep.1", "Lapisan Bawaan → Global → Khusus PT", T, [u("K02", "2, 6")], ""),
 ("K02", "konsep.3", "Ubah pemetaan hanya untuk jurnal baru; beralasan & tercatat", T, [u("K02", "1, 6, 7")], ""),
 ("K02", "konsep.4", "Finance boleh mengubah pemetaan; Manajer hanya melihat", T9, ["V9:buku#3", u("K02", "6")], ""),
 ("K02", "cek_buku.0", "Jurnal pendapatan kirim memakai akun pemetaan", T, [u("K02", "5")], ""),
 ("K02", "cek_buku.1", "Jurnal tagihan memakai akun pemetaan Pembelian", T, [u("K02", "5")], ""),
 ("K02", "cek_buku.2", "Pemetaan sesudah peragaan sama; dua baris riwayat", T, [u("K02", "8")], ""),
 ("K02", "kesalahan_umum.2", "'Selisih harga pembelian' belum diatur → selisih tertinggal di GR/IR, kliring ditolak", T9,
  ["V9:hutang-tagihan#9", "V9:hutang-grir#1", "tests_mem test_PK28_gr_ir.py::U4, U10b"], "K-26."),
 ("K02", "kesalahan_umum.3", "Akun pengganti di riwayat tetap dihitung akun kontrol", KP, [], "K-28."),
 ("K03", "konsep.0", "Profil PT sumber kop dokumen", T, [u("K03", "4")], ""),
 ("K03", "konsep.1", "PKP; kode dokumen terkunci", T, [u("K03", "1, 2")], ""),
 ("K03", "konsep.2", "Tahun buku Jan–Des, IDR", T, [u("K03", "2, 5")], ""),
 ("K03", "konsep.3", "Periode tertutup mengunci; membuka butuh usul & persetujuan", T, [u("F18", "6")], ""),
 ("K03", "cek_buku.0", "Kop faktur = Profil PT", T, [u("K03", "4")], ""),
 ("K03", "cek_buku.1", "Bulan tutup 12, IDR, periode tertutup mengunci", T, [u("K03", "5")], ""),
 ("K03", "cek_buku.2", "Periode tertutup layar = buku; pengaturan tidak berubah", T, [u("K03", "6, 7")], ""),
 ("K03", "kesalahan_umum.1", "Kode dokumen terkunci sesudah ada dokumen bernomor", T, [u("K03", "2")], ""),
 ("K03", "kesalahan_umum.2", "Transaksi bertanggal di periode tertutup ditolak", T, [v("V1.26"), v("V8 periode tertutup")], ""),
 ("K03", "catatan_pelatih", "Riwayat PT untuk Manajer: 'hanya bisa dibaca pemegang akses Riwayat Audit'", TU, ["jest latihK03RiwayatPt.test.js"], "C-02."),
 ("K04", "konsep.0", "Rekening rincian akun 1-1100 / 1-1110", T, [u("K04", "4")], ""),
 ("K04", "konsep.1", "Saldo awal dijurnal 1-1100 D / 3-2900 K", T, [u("K04", "3, 4")], ""),
 ("K04", "konsep.2", "'Dipakai untuk' menentukan layar penawaran rekening", T, [u("K04", "5")], ""),
 ("K04", "konsep.3", "Koreksi saldo awal lewat jurnal penyesuaian", T, [u("K04", "6")], ""),
 ("K04", "cek_buku.0", "Jurnal saldo awal", T, [u("K04", "4")], ""),
 ("K04", "cek_buku.1", "Saldo kartu = saldo awal", T, [u("K04", "5")], ""),
 ("K04", "cek_buku.2", "Pembersihan: efek bersih Rp 0", T, [u("K04", "6")], ""),
 ("K04", "kesalahan_umum.2", "Form Ubah rekening tidak memuat saldo awal", T9, ["V9:buku#5"], ""),
 ("K04", "kesalahan_umum.3", "Semua rekening bank memakai 1-1100", T, [u("K04", "4")], ""),
 ("K04", "catatan_pelatih", "Petunjuk Cara Bayar di Perusahaan (PT) › Master per PT", T, [], "C-03 (BankAccountForm)."),
 ("K04", "catatan_pelatih", "Finance belum punya menu Master per PT", KP, [], "K-30."),
 ("K05", "konsep.0", "Nilai aturan berlapis: bawaan → grup → khusus PT", T, [u("K05", "1")], ""),
 ("K05", "konsep.1", "PPN 12% DPP nilai lain 11/12", T, [u("K05", "2")], ""),
 ("K05", "konsep.2", "Aturan pembayaran pelanggan, LPJ, cara bayar", T, [u("K05", "3, 4")], ""),
 ("K05", "konsep.3", "Ubah berlaku seketika; tercatat; Ikuti nilai grup mencabut", T, [u("K05", "6–9")], ""),
 ("K05", "konsep.4", "Finance tidak membuka layar Aturan Keuangan & Pajak", T9, ["V9:buku#4"], ""),
 ("K05", "cek_buku.0", "Pengaturan kembali seperti awal", T, [u("K05", "8")], ""),
 ("K05", "cek_buku.1", "Saldo piutang tidak berubah, hanya kolom umur", T, [u("K05", "7")], ""),
 ("K05", "cek_buku.2", "Contoh PPN 1.680.000 → 184.800", T, [u("F11", "3")], ""),
 ("K05", "kesalahan_umum.2", "Aturan berisiko tinggi tanpa alasan → Simpan mati", T9, ["V9:buku#6"], ""),
 ("K05", "kesalahan_umum.3", "Finance hanya melihat Pemetaan Akun di Keuangan & Pajak", T9, ["V9:buku#4"], ""),
 ("K05", "catatan_pelatih", "Manajer hanya membaca; 'Kelompok umur' butuh izin kelola pengaturan", TB, [], "Izin peran Manajer: pengaturan = lihat saja. K-27."),
 ("K06", "konsep.0", "Profil kredit per pelanggan per PT, berlabel asal nilai", T, [u("K06", "1")], ""),
 ("K06", "konsep.1", "Perubahan lewat pengajuan; satu terbuka per pelanggan", T, [u("K06", "2, 3")], ""),
 ("K06", "konsep.2", "Plafon dicek saat pesanan dibuat; termin di luar daftar ditolak", TU,
  [u("A1", "6"), "tests_mem test_CRT3_pemasangan.py::ganti_termin_di_luar_daftar_ditolak"], ""),
 ("K06", "konsep.3", "Daftar termin master per PT; termin pemasok → jatuh tempo", T, [u("K06", "7, 8")], ""),
 ("K06", "cek_buku.0", "Profil kredit sesuai pengajuan yang disetujui", T, [u("K06", "4, 6")], ""),
 ("K06", "cek_buku.1", "Pengajuan bernomor KSC/PKR-…", T, [u("K06", "2, 5")], ""),
 ("K06", "cek_buku.2", "Aturan kredit PT tidak berubah", T, [u("K06", "9")], ""),
 ("K06", "kesalahan_umum.0", "Plafon/termin tidak di form Ubah pelanggan", TU, ["jest pk45KreditPelanggan.test.js (customer-credit-note)"], ""),
 ("K06", "kesalahan_umum.1", "Pengajuan kedua: tombol mati", T, [u("K06", "2")], ""),
 ("K06", "kesalahan_umum.2", "'Termin bawaan belum dipakai saat pesanan dibuat'", T, [u("K06", "5")], ""),
 ("K06", "kesalahan_umum.3", "Tanpa termin dicentang = semua termin aktif PT", T, [u("K06", "1")], ""),
 ("K07", "konsep.0", "Peran berisi modul dengan tingkat; menu mengikuti izin", T, [u("K07", "2, 7")], ""),
 ("K07", "konsep.1", "Contoh izin bawaan Finance (… Izin SDM & Penggajian sedang ditambahkan)", DT, [u("K07", "2, 7"), u("K09", "1"), u("H03", "2, 6")],
  "Izin SDM & Penggajian untuk Finance sudah aktif (Finance menyiapkan, memposting, membayar gaji). Teks diperbarui."),
 ("K07", "konsep.2", "Admin memberi izin; ringkasan sebelum simpan", T, [u("K07", "4")], ""),
 ("K07", "konsep.3", "Aturan Persetujuan PO ≥ 100 jt, > 500 jt + Direksi; Coba nilai", T, [u("K07", "5, 6")], ""),
 ("K07", "konsep.4", "Kontrol dua orang", T, [u("F12", "6"), u("F18", "6"), "V9:hutang-tagihan#8"], ""),
 ("K07", "cek_buku.0", "Izin & aturan tidak berubah", T, [u("K07", "8")], ""),
 ("K07", "cek_buku.1", "Izin sesi Finance: akuntansi lihat, pemetaan ubah, kas kelola", T, [u("K07", "note")], ""),
 ("K07", "cek_buku.2", "Coba nilai PO Rp 600 jt dua jenjang", T, [u("K07", "6")], ""),
 ("K07", "kesalahan_umum.1", "Menyimpan peran bawaan mengubah semua akun Finance", T, [u("K07", "4")], ""),
 ("K07", "catatan_pelatih", "Izin SDM & Penggajian untuk Finance sedang ditambahkan", DT, [u("K09", "1")], "Sudah ditambahkan; teks diperbarui."),
 ("K08", "konsep.0", "Format nomor per PT; nomor tidak dipakai ulang", T, [u("K08", "1, 2")], ""),
 ("K08", "konsep.1", "Faktur Komersial mengikuti nomor pesanan", T, [u("K08", "1")], ""),
 ("K08", "konsep.2", "Desainer PDF berlapis; aturan PT terbatas", T, [u("K08", "3"), "uji dokumen D3"], ""),
 ("K08", "konsep.3", "Token terisi; berlaku pada cetak ulang dokumen lama", T, [u("K08", "4")], ""),
 ("K08", "konsep.4", "Desainer PDF khusus Admin; Finance mencetak di Pusat Dokumen", T, [u("K08", "4"), "uji dokumen D3"], "K-24."),
 ("K08", "cek_buku.0", "Nomor kwitansi berikutnya > terakhir", T, [u("K08", "1")], ""),
 ("K08", "cek_buku.1", "Teks penutup bertoken tercetak; sesudah kembali identik", T, [u("K08", "4, 5")], ""),
 ("K08", "cek_buku.2", "Format & naskah sama dengan sebelumnya", T, [u("K08", "5")], ""),
 ("K08", "kesalahan_umum.1", "Token salah → peringatan & Simpan ditolak", T, ["uji dokumen D3"], "P-08."),
 ("K08", "kesalahan_umum.3", "Kop dasar hanya tombol cetak lama", T, ["uji dokumen D3"], "K-24."),
 ("K09", "konsep.1", "Komponen gaji = baris slip", T, [u("K09", "4")], ""),
 ("K09", "konsep.2", "TER: TK0/TK1/K0 = A; TK2/TK3/K1/K2 = B; K3 = C", T, [u("K09", "2")], ""),
 ("K09", "konsep.3", "BPJS di reguler; THR & susulan tanpa BPJS", TU, [u("H03", "3"), "tests_mem test_PYT1_komponen_gaji.py::U4, U5 (THR)"], ""),
 ("K09", "konsep.4", "'Satu nilai untuk seluruh grup'", T, [u("K09", "3")], ""),
 ("K09", "cek_buku.0", "Konfigurasi tanpa jurnal", T, [u("K09", "6, 7")], ""),
 ("K09", "cek_buku.1", "Akun yang diisi proses gaji", T, [u("H03", "7"), v("V7 akrual insentif")], ""),
 ("K09", "cek_buku.2", "Potongan tidak hadir/terlambat/cuti tanpa gaji → 6-1000", TU, ["tests_mem test_PYT3_aturan_hitung.py::U6, U7, U8"], ""),
 ("K09", "catatan_pelatih", "Finance memegang izin aturan gaji (PTKP/TER/BPJS grup)", T, [u("K09", "1")], "K-31."),
 # ── A1–A5 ────────────────────────────────────────────────────────────────────────────────────────────────────────────
 ("A1", "konsep.1", "Buku berubah hanya saat barang keluar & uang masuk", T, [u("A1", "5, 17, 19, 22, 24")], ""),
 ("A1", "konsep.2", "Piutang lahir saat surat jalan; jatuh tempo dari tanggal SJ", T, [u("A1", "16, 18")], ""),
 ("A1", "konsep.3", "Eksposur dicek saat SO; lewat plafon → tunggu izin Manajer", T, [u("A1", "4, 6–9")], ""),
 ("A1", "konsep.4", "PPN contoh DPP 2.356.000 → 259.160", T, [u("A1", "note")], ""),
 ("A1", "titik_kontrol.0", "Lewat plafon: Buat SO terkunci sampai izin disetujui", T, [u("A1", "6–9")], ""),
 ("A1", "titik_kontrol.1", "Admin Sales memeriksa sebelum melepas", T, [u("A1", "10, 11")], ""),
 ("A1", "titik_kontrol.2", "Gudang hanya mengambil roll yang dicadangkan; jumlah = panjang roll", T, [u("A1", "12, 13")],
  "Roll dicadangkan tampil & jumlah = panjang roll; scan roll lain tidak diuji."),
 ("A1", "titik_kontrol.3", "Roll tanpa RFID memblokir; pengecualian Manajer; Gudang ditolak saat menekan Override", DT,
  [u("A1", "14, 15"), "jest latihA1Gudang.test.js"], "Sesudah perbaikan C-12 Gudang tidak melihat tombol Override (bukan 'ditolak saat menekan'). Teks dikoreksi."),
 ("A1", "titik_kontrol.4", "Kwitansi tidak melebihi sisa; konfirmasi menyebut nominal, pelanggan, rekening, PT", T, [v("V1.1"), u("A1", "20")], ""),
 ("A1", "titik_kontrol.5", "Mutasi bank ditautkan ke transaksi kas", T, [u("A1", "22")], ""),
 ("A1", "cek_buku.0", "Jurnal pendapatan kirim", T, [u("A1", "16, 24")], ""),
 ("A1", "cek_buku.1", "Jurnal HPP; laba kotor", T, [u("A1", "16, 24")], ""),
 ("A1", "cek_buku.2", "Jurnal kwitansi; piutang SO nol", T, [u("A1", "20, 24")], ""),
 ("A1", "cek_buku.3", "Faktur & pencocokan bank tanpa jurnal", T, [u("A1", "19, 22")], ""),
 ("A1", "cek_buku.4", "Nilai SO = faktur = kwitansi = kas = mutasi", T, [u("A1", "24")], ""),
 ("A1", "kesalahan_umum.1", "[Kirim Pengambilan] hanya mencatat roll; SJ lewat [Kirim Semua]", T, [u("A1", "13, 16")], ""),
 ("A1", "kesalahan_umum.2", "Piutang & jurnal sudah lahir saat SJ, bukan 'Tandai Diterima'", T, [u("A1", "16, 17")], ""),
 ("A1", "kesalahan_umum.3", "Transfer dicatat Tunai → Kas Kecil", T9, ["V9:piutang-tertua#2"], ""),
 ("A1", "catatan_pelatih", "Tanpa kode bayar skor 75 → cocok manual; dengan kode → otomatis", T, [u("A1", "22"), u("F10", "4")], ""),
 ("A1", "catatan_pelatih", "Perbaikan Periksa ulang kredit, pelacak dimuat ulang, kotak roll", TU, ["jest a1AlurPesanan.test.js"], "C-09–C-11."),
 ("A2", "konsep.0", "Rantai PR → PO → terima → SPK → tagihan → kontrabon → bayar → mutasi", T, [u("A2", "27")], ""),
 ("A2", "konsep.1", "Hutang dua tahap: GR/IR saat terima, Hutang Usaha saat tagihan", T, [u("A2", "10, 16")], ""),
 ("A2", "konsep.2", "3-way match: cocok → terposting; selisih DALAM toleransi → perlu persetujuan; lebih tagih → ditolak", DT,
  ["V9:hutang-tagihan#4", "V9:hutang-tagihan#5", "V9:hutang-tagihan#6"],
  "Selisih dalam toleransi (±5% harga, atau nilai ≤ Rp 50.000) dianggap COCOK dan langsung terposting; yang perlu persetujuan adalah selisih DI LUAR toleransi. Ambang Rp 50.000 ditambahkan ke teks."),
 ("A2", "konsep.3", "PR ≥ 50 jt & PO ≥ 100 jt perlu persetujuan; pembuat tidak menyetujui sendiri", T, [u("A2", "3–6"), u("K07", "5, 6")], ""),
 ("A2", "konsep.4", "PPN masukan 11% DPP; bayar & rekonsiliasi tanpa jurnal baru", T, [u("A2", "16, 23, 25")], ""),
 ("A2", "titik_kontrol.0", "PR ≥ 50 jt disetujui sebelum jadi PO", T, [u("A2", "3, 4")], ""),
 ("A2", "titik_kontrol.1", "Pembuat PO tidak menyetujui sendiri", T, [u("A2", "5")], ""),
 ("A2", "titik_kontrol.2", "Barang karantina sampai SPK MD Quality ditutup", T, [u("A2", "13")], ""),
 ("A2", "titik_kontrol.3", "Jumlah tagih tidak boleh melebihi diterima; selisih harga di atas toleransi butuh persetujuan", DT,
  ["V9:hutang-tagihan#4", "V9:hutang-tagihan#6", "V9:hutang-tagihan#8"],
  "Lebih tagih bernilai ≤ Rp 50.000 masih bisa dikirim dengan persetujuan; di atasnya tombol kirim mati. Persetujuan oleh orang kedua (pembuat tagihan tidak memutus sendiri)."),
 ("A2", "titik_kontrol.4", "Nomor faktur pemasok tidak boleh dipakai dua kali", T9, ["V9:hutang-tagihan#3"], ""),
 ("A2", "titik_kontrol.5", "Kontrabon diverifikasi, disetujui orang kedua, dijadwalkan, dibayar Finance", T, [u("A2", "18–22")], ""),
 ("A2", "titik_kontrol.6", "Pembayaran punya pasangan mutasi", T, [u("A2", "24, 25")], ""),
 ("A2", "cek_buku.0", "Jurnal penerimaan barang", T, [u("A2", "10")], ""),
 ("A2", "cek_buku.1", "Jurnal tagihan pemasok", T, [u("A2", "16")], ""),
 ("A2", "cek_buku.2", "Jurnal pembayaran", T, [u("A2", "23")], ""),
 ("A2", "cek_buku.3", "Sisa GR/IR & hutang nol", T, [u("A2", "23, 26")], ""),
 ("A2", "cek_buku.4", "Mutasi BCA tercocok tanpa jurnal baru", T, [u("A2", "25")], ""),
 ("A2", "kesalahan_umum.1", "PPN Masukan baru saat tagihan, bukan saat barang datang", T, [u("A2", "10, 16")], ""),
 ("A2", "kesalahan_umum.2", "Kontrabon disetujui ≠ hutang lunas", T, [u("A2", "20, 23")], ""),
 ("A2", "catatan_pelatih", "Pembelian kecil disetujui otomatis; dua tombol PR → PO; MD Quality sampling", T, [u("A2", "4, 12, 13")], "K-35."),
 ("A2", "catatan_pelatih", "Keterangan jurnal sistem masih Inggris ('Goods Receipt', 'Vendor Bill')", DT, [],
  "Cek buku V9: jurnal baru berketerangan 'Penerimaan barang …' dan 'Tagihan pemasok …' (C-17). Teks diperbarui."),
 ("A2", "catatan_pelatih", "Nomor PR/VB tanpa awalan PT", KP, ["V9:hutang-tagihan#3"], "K-22."),
 ("A2", "catatan_pelatih", "Pembayaran tidak dicek ke saldo bank", KP, [], "K-36."),
 ("A3", "konsep.0", "Retur dari pesanan terkirim per roll; persetujuan awal tanpa jurnal", T, [u("A3j", "A2, A3")], ""),
 ("A3", "konsep.1", "Gudang scan terima; QC lewat SPK otomatis; nilai = harga neto × qty QC + PPN", T, [u("A3j", "A5–A9")], ""),
 ("A3", "konsep.2", "Manajer memilih outcome; satu Nota Kredit", T, [u("A3j", "A8, B8"), u("A3t", "T8")], ""),
 ("A3", "konsep.3", "Potong tagihan SO asal dulu", T, [u("A3j", "B8, B9")], ""),
 ("A3", "konsep.4", "Jurnal Nota Kredit membalik penjualan & HPP", T, [u("A3j", "A9, B9")], ""),
 ("A3", "konsep.5", "Nota Debit: Hutang D / Persediaan K + PPN Masukan K; memotong tagihan lewat kontrabon", T, [u("A3b", "4, 5, 7, 12")], ""),
 ("A3", "titik_kontrol.1", "Pembuat retur tidak menyetujui sendiri; kontrabon orang kedua", T, [u("A3j", "A2, A3"), u("A3b", "9")], ""),
 ("A3", "titik_kontrol.2", "QC wajib sebelum selesai; roll belum di-scan belum bisa diperiksa", TU, [u("A3j", "A5–A8"), "jest latihA3Karantina.test.js"], ""),
 ("A3", "titik_kontrol.3", "Pratinjau = Nota Kredit yang terbit", T, [u("A3j", "A8, B8")], ""),
 ("A3", "titik_kontrol.4", "Nota Debit dipotong sekali; potongan = nilai termasuk PPN", TU, [u("A3b", "7"), "tests_mem test_A3_nota_debit_kontrabon.py"], "C-19."),
 ("A3", "titik_kontrol.5", "Finance mencocokkan saldo, kas refund, sisa tagihan", T, [u("A3j", "A11, B10"), u("A3b", "11, 12")], ""),
 ("A3", "cek_buku.0", "Jurnal Nota Kredit Store Credit", T, [u("A3j", "A9, A10")], ""),
 ("A3", "cek_buku.1", "Pemakaian saldo 2-1450 D / 1-1200 K", T, [u("A3j", "A11")], ""),
 ("A3", "cek_buku.2", "Jurnal Nota Kredit Pengembalian Dana (contoh CN-00002)", DT, [u("A3j", "B9")],
  "Contoh menulis 2-1200 (D) Rp 331.622,50 → D ≠ K. Uji jalan: PPN Rp 345.262,50 (KSC/JE-00139). Dikoreksi."),
 ("A3", "cek_buku.3", "Jurnal Nota Debit", T, [u("A3b", "4")], ""),
 ("A3", "cek_buku.4", "Bayar kontrabon = nilai bersih; hutang pemasok nol", T, [u("A3b", "11, 12")], ""),
 ("A3", "kesalahan_umum.0", "Persetujuan awal belum berarti uang kembali", T, [u("A3j", "A3, A8")], ""),
 ("A3", "kesalahan_umum.1", "Pengembalian Dana pada SO belum lunas memotong sisa tagihan dulu", T, [u("A3j", "B9")], ""),
 ("A3", "kesalahan_umum.2", "QC 'Rusak' → HPP tidak dibalik, stok tanpa nilai", KP, [], "K-40."),
 ("A3", "kesalahan_umum.3", "Tagihan diretur dibayar penuh di luar kontrabon → Nota Debit tetap terbuka", T, [u("A3b", "5")], "K-39."),
 ("A3", "catatan_pelatih", "Refund langsung kas keluar saat Manajer menyimpan", KP, [u("A3j", "B8–B10")], "K-38."),
 ("A3", "catatan_pelatih", "Perbaikan potongan ND termasuk PPN, Maks bersen, panel pesanan pengganti", TU,
  ["tests_mem test_A3_nota_debit_kontrabon.py", "jest a3PakaiSaldoSen.test.js", "jest a3TukarPerRoll.test.js", u("A3t", "T10, T11")], ""),
 ("A4", "konsep.1", "Pemisahan tugas Finance/Manajer", T, [u("H03", "1–6")], ""),
 ("A4", "konsep.2", "Jurnal hanya di posting, bayar, setoran", T, [u("H03", "7"), u("H04", "4, 7")], ""),
 ("A4", "konsep.3", "Reguler sekali per masa; susulan/THR hanya masukan + PPh 21", T, ["V9:gaji#4", u("H03", "3")], ""),
 ("A4", "konsep.4", "Tanggal buku = akhir masa; bayar mulai tanggal itu", T, [u("H03", "6"), "tests_mem test_PYT4_bayar_gaji.py::U6"], ""),
 ("A4", "titik_kontrol.0", "Manajer mengesahkan masukan", T, [u("H03", "1"), u("H02", "2")], ""),
 ("A4", "titik_kontrol.1", "Manajer mengesahkan perubahan gaji & penugasan", TU, ["tests_mem test_PYT2_riwayat_kompensasi.py"], ""),
 ("A4", "titik_kontrol.2", "Finance tidak bisa mengesahkan proses gaji", T, [u("H03", "4")], ""),
 ("A4", "titik_kontrol.3", "Kontrol dua orang penggajian (bila dinyalakan)", TU, ["tests_mem test_PK22_penggajian.py::kontrol_dua_orang_posting"], "K-33."),
 ("A4", "titik_kontrol.4", "Bayar hanya dari rekening Gaji, tidak sebelum tanggal jurnal", T9, ["V9:gaji#7", "tests_mem test_PYT4_bayar_gaji.py::U3, U6"], ""),
 ("A4", "titik_kontrol.5", "Anulir hanya Manajer; gaji dibayar dikoreksi lewat susulan", T9, ["V9:gaji#6", "V9:gaji#8"], ""),
 ("A4", "titik_kontrol.6", "Setoran tidak melebihi sisa kewajiban", T, [v("V7 sisa + 1.000")], ""),
 ("A4", "cek_buku.0", "Hutang gaji/BPJS/PPh 21 nol sesudah satu daur", T, [u("H04", "4, 7")], ""),
 ("A4", "cek_buku.1", "Contoh jurnal peserta 01", T, [u("H03", "7"), u("H04", "4")], ""),
 ("A4", "kesalahan_umum.1", "Antrean Gaji siap dibayar hanya proses Diposting", T, [u("F15", "1")], ""),
 ("A4", "kesalahan_umum.2", "Kartu Setoran & Pajak menandai sisa kewajiban", T, [u("F15", "5")], ""),
 ("A5", "konsep.3", "Laporan dari jurnal; Neraca seimbang", T, [u("F17", "2–5")], ""),
 ("A5", "konsep.4", "Membuka kembali periode butuh alasan dan persetujuan", DT, [u("F18", "6, 9"), v("V8 Buka Kembali")],
  "Tidak tepat: Buka Periode (jendela) butuh alasan + orang kedua; Buka Kembali (batalkan penutupan) oleh Admin tanpa isian alasan (K-19). Teks dirinci."),
 ("A5", "titik_kontrol.0", "Neraca saldo seimbang", T, [u("F16", "6")], ""),
 ("A5", "titik_kontrol.1", "Saldo bank buku = rekening koran sesudah rekonsiliasi", T, [u("F10", "8"), v("V3.23")], ""),
 ("A5", "titik_kontrol.2", "Akun sementara nol sebelum tutup buku", TU, ["tests_mem test_PK43_alur_layar.py::U11"], ""),
 ("A5", "cek_buku.0", "Aset = Kewajiban + Ekuitas", T, [u("F17", "4")], ""),
 ("A5", "cek_buku.1", "Laba bersih Laba-Rugi = perubahan laba ditahan di Neraca", DT, ["V9:buku#1"],
  "Laba Ditahan tidak berubah sebelum tutup buku; laba bersih 1 Jan–hari ini sama dengan baris 'Laba Tahun Berjalan' di Neraca. Teks dikoreksi."),
]


def muat_v9():
    out = {}
    base = os.path.join(HASIL, "V9")
    if not os.path.isdir(base):
        return out
    for blok in os.listdir(base):
        f = os.path.join(base, blok, "hasil.json")
        if not os.path.isfile(f):
            continue
        h = json.load(open(f))
        for s in h.get("steps", []):
            out[f"{blok}#{s['no']}"] = {"ok": s["ok"], "action": s["action"], "info": s.get("info", "")[:300]}
    return out


def bangun():
    v9 = muat_v9()
    rows = []
    for kode, bagian, klaim, hasil, bukti, catatan in K:
        b2 = []
        gagal = False
        for b in bukti:
            if b.startswith("V9:"):
                key = b[3:]
                st = v9.get(key)
                blok, no = key.split("#")
                lbl = f"{V9.get(blok, 'uji/variasi/V9_klaim_*.js')} · hasil/V9/{blok} langkah {no}"
                if st is None:
                    b2.append(lbl + " (belum dijalankan)")
                    gagal = True
                else:
                    b2.append(lbl + (" (lulus)" if st["ok"] else " (GAGAL)"))
                    gagal = gagal or not st["ok"]
            else:
                b2.append(b)
        row = {"kode": kode, "bagian": bagian, "klaim": klaim, "hasil": hasil, "bukti": b2}
        if catatan:
            row["catatan"] = catatan
        if gagal:
            row["catatan"] = (row.get("catatan", "") + " Bukti V9 belum lulus semua — lihat hasil.json.").strip()
        rows.append(row)
    ring = {}
    for r in rows:
        ring[r["hasil"]] = ring.get(r["hasil"], 0) + 1
    v9_lulus = sum(1 for x in v9.values() if x["ok"])
    doc = {"judul": "V9 — Bukti untuk setiap klaim di teks materi pelatihan keuangan",
           "lingkup": "konsep · cek_buku · kesalahan_umum · titik_kontrol · catatan_pelatih semua materi F01–F18, K01–K09, H01–H04, "
                      "A1–A5 (S1–S4 dikerjakan agen lain). Nasihat umum tidak dimasukkan.",
           "ringkasan": {"klaim": len(rows), **ring, "langkah_uji_V9": len(v9), "langkah_uji_V9_lulus": v9_lulus},
           "klaim": rows}
    tujuan = os.path.join(PEL, "src", "variasi_klaim_materi.json")
    open(tujuan, "w").write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(doc["ringkasan"], ensure_ascii=False))


if __name__ == "__main__":
    bangun()
