"""GL-01 — registri kebutuhan akun (SSOT di kode). Satu baris = satu kebutuhan fitur.

`remap=True`: kebutuhan yang dulu berupa konstanta tetap di gl_service. Baris jurnal otomatis
yang memakai kode bawaan konstanta itu dialihkan ke akun pemetaan (lihat gl_mapping_service).
`remap=False`: kebutuhan khusus fitur, dipanggil eksplisit lewat `account_key`.
"""
from typing import Any, Dict, List

MODULES = [
    ("kas_bank", "Kas & Bank"), ("penjualan", "Penjualan"), ("persediaan", "Persediaan"),
    ("pembelian", "Pembelian"), ("retur", "Retur"), ("makloon", "Makloon"),
    ("antar_pt", "Antar-PT"), ("sdm", "SDM & Payroll"), ("aset", "Aset Tetap"), ("lain", "Lain-lain"),
]
# UAT 24 Okt (audit UI tahap 2) — G1-08: bagan akun (gl_service.ACCOUNT_TYPES) memakai `income` untuk akun 4-xxxx;
# dulu registri menulis `revenue` sehingga kandidat akun pendapatan selalu kosong. `revenue` tetap dikenali sebagai alias.
TYPE_BY_DIGIT = {"1": "asset", "2": "liability", "3": "equity", "4": "income", "5": "expense", "6": "expense"}
TYPE_LABEL = {"asset": "Aset", "liability": "Kewajiban", "equity": "Ekuitas", "income": "Pendapatan",
              "revenue": "Pendapatan", "expense": "Beban"}
TYPE_ALIAS = {"revenue": "income"}


def norm_type(t: Any) -> str:
    """Jenis akun baku (alias lama `revenue` → `income`)."""
    return TYPE_ALIAS.get(t, t) if isinstance(t, str) else ""


def _e(key, default, label, used_when, dr_cr, used_by, remap=True, types=None, required=True):
    return {"key": key, "module": key.split(".")[0], "default": default, "label": label,
            "used_when": used_when, "example": dr_cr, "used_by": list(used_by), "remap": remap,
            "allowed_types": list(types or [TYPE_BY_DIGIT[default[0]]]), "required": required}


ENTRIES: List[Dict[str, Any]] = [
    _e("kas_bank.kas_besar", "1-1100", "Kas besar / bank utama", "uang masuk/keluar kas besar bila rekening tidak dipilih",
       ("Kas besar", "Piutang"), ["Kas & Bank", "Kwitansi AR", "Pembayaran supplier"]),
    _e("kas_bank.kas_kecil", "1-1110", "Kas kecil", "transaksi kas kecil",
       ("Beban", "Kas kecil"), ["Kas kecil", "PD/LPJ"]),
    _e("kas_bank.kas_transit", "1-1150", "Dana dalam perjalanan", "pindah-buku antar rekening sendiri",
       ("Dana transit", "Bank asal"), ["Pindah buku bank"]),
    _e("kas_bank.beban_bank", "6-8000", "Beban administrasi bank", "biaya admin/transfer dipotong bank",
       ("Beban bank", "Bank"), ["Rekonsiliasi bank"]),
    _e("kas_bank.titipan_dana", "2-1950", "Titipan dana belum teridentifikasi", "dana masuk yang belum dikenali",
       ("Bank", "Titipan dana"), ["Rekonsiliasi bank"]),
    _e("kas_bank.uang_muka_karyawan", "1-1400", "Uang muka & biaya dibayar dimuka", "pengajuan dana (PD) kas kecil",
       ("Uang muka", "Kas"), ["PD/LPJ"]),
    _e("kas_bank.hutang_reimburse", "2-1650", "Hutang reimburse karyawan", "LPJ melebihi uang muka",
       ("Beban", "Hutang reimburse"), ["PD/LPJ"]),
    _e("kas_bank.piutang_karyawan", "1-1280", "Piutang titipan karyawan", "uang perusahaan dipegang karyawan",
       ("Piutang karyawan", "Kas"), ["Kas & Bank"]),
    _e("penjualan.piutang", "1-1200", "Piutang usaha", "penjualan kredit & penagihan",
       ("Piutang", "Pendapatan"), ["Penjualan", "Kwitansi AR", "Aging"]),
    _e("penjualan.pendapatan", "4-1000", "Pendapatan penjualan", "barang dikirim ke pelanggan",
       ("Piutang", "Pendapatan"), ["Penjualan", "Surat Jalan"]),
    _e("penjualan.ppn_keluaran", "2-1200", "PPN keluaran", "penjualan ber-PPN",
       ("Piutang", "PPN keluaran"), ["Penjualan", "Faktur pajak"]),
    _e("penjualan.uang_muka_pelanggan", "2-1400", "Uang muka pelanggan", "DP / kelebihan bayar pelanggan",
       ("Kas", "Uang muka pelanggan"), ["Kwitansi AR"]),
    _e("penjualan.piutang_denda", "1-1270", "Piutang denda pelanggan", "denda keterlambatan dibebankan",
       ("Piutang denda", "Pendapatan denda"), ["Denda"]),
    _e("penjualan.pendapatan_denda", "4-9300", "Pendapatan denda", "denda keterlambatan dibebankan",
       ("Piutang denda", "Pendapatan denda"), ["Denda"]),
    _e("penjualan.selisih_bayar", "6-9100", "Beban selisih pembayaran", "kurang bayar kecil dihapus",
       ("Beban selisih", "Piutang"), ["Kwitansi AR"]),
    _e("penjualan.beban_insentif", "6-5000", "Beban insentif sales", "akrual insentif penjualan",
       ("Beban insentif", "Hutang insentif"), ["Insentif"]),
    _e("penjualan.hutang_insentif", "2-1500", "Hutang insentif sales", "akrual insentif penjualan",
       ("Beban insentif", "Hutang insentif"), ["Insentif"]),
    _e("penjualan.pendapatan_lain", "4-9000", "Pendapatan lain-lain", "pendapatan di luar penjualan",
       ("Kas", "Pendapatan lain"), ["Kas & Bank"]),
    _e("penjualan.beban_pemasaran", "6-4700", "Beban pemasaran", "realisasi biaya kampanye",
       ("Beban pemasaran", "Kas"), ["Marketing"]),
    _e("persediaan.persediaan", "1-1300", "Persediaan barang", "barang masuk/keluar gudang",
       ("Persediaan", "Barang diterima belum ditagih"), ["Penerimaan", "HPP", "Opname"]),
    _e("persediaan.transit_antar_pt", "1-1310", "Persediaan dalam perjalanan antar-PT", "transfer antar-PT dikirim",
       ("Persediaan transit", "Persediaan"), ["Transfer antar-PT"]),
    _e("persediaan.hpp", "5-1000", "Harga pokok penjualan", "barang terjual dikirim",
       ("HPP", "Persediaan"), ["Surat Jalan"]),
    _e("persediaan.penghapusan", "5-9500", "Beban penghapusan persediaan", "stok rusak/BS dibuang",
       ("Beban penghapusan", "Persediaan"), ["Disposisi retur", "Opname"]),
    _e("persediaan.saldo_awal", "3-2900", "Ekuitas saldo awal persediaan", "impor stok awal",
       ("Persediaan", "Ekuitas saldo awal"), ["Stok awal"]),
    _e("persediaan.overhead_diserap", "5-1100", "Overhead produksi diserap", "kapitalisasi overhead ke persediaan",
       ("Persediaan", "Overhead diserap"), ["Produksi"]),
    _e("persediaan.beban_rnd", "6-7000", "Beban sample & pengembangan", "bahan sample keluar gudang",
       ("Beban R&D", "Persediaan"), ["R&D Sample"]),
    _e("pembelian.hutang", "2-1100", "Hutang usaha", "tagihan supplier",
       ("Barang diterima belum ditagih", "Hutang"), ["Tagihan supplier", "Pembayaran supplier"]),
    _e("pembelian.gr_ir", "2-1150", "Barang diterima belum ditagih (GR/IR)", "barang PO diterima gudang",
       ("Persediaan", "Barang diterima belum ditagih"), ["Penerimaan PO", "Tagihan supplier"]),
    _e("pembelian.ppn_masukan", "1-1500", "PPN masukan", "tagihan supplier ber-PPN",
       ("PPN masukan", "Hutang"), ["Tagihan supplier", "Pajak masukan"]),
    _e("pembelian.landed_cost", "5-9000", "Biaya masuk pembelian (angkut/bea)", "biaya angkut/bea pembelian",
       ("Biaya masuk", "Hutang"), ["Landed cost"]),
    _e("pembelian.beban_operasional", "6-4000", "Beban operasional", "pengeluaran operasional umum",
       ("Beban operasional", "Kas"), ["Kas & Bank"]),
    _e("retur.store_credit", "2-1450", "Saldo kredit pelanggan", "retur diselesaikan sebagai saldo kredit pelanggan",
       ("Retur penjualan", "Saldo kredit"), ["Retur penjualan"]),
    _e("retur.ongkir_perusahaan", "6-4500", "Beban ongkir retur (ditanggung perusahaan)",
       "ongkir retur/QC/kirim pengganti ditanggung perusahaan", ("Beban ongkir", "Kas/Bank/Hutang ekspedisi"),
       ["Biaya logistik retur"], remap=False),
    _e("retur.ongkir_pembayaran", "1-1110", "Lawan ongkir bawaan (bila Finance tidak memilih)",
       "dipakai bila akun pembayaran ongkir tidak dipilih", ("Beban ongkir", "Kas kecil"),
       ["Biaya logistik retur"], remap=False, types=["asset", "liability"]),
    _e("retur.ongkir_piutang_customer", "1-1200", "Piutang ongkir ke pelanggan",
       "ongkir armada KN ditagih terpisah ke pelanggan", ("Piutang", "Pendapatan ongkir"),
       ["Biaya logistik retur"], remap=False),
    _e("retur.ongkir_pendapatan", "4-9000", "Pendapatan penggantian ongkir",
       "ongkir armada KN ditagih ke pelanggan", ("Piutang", "Pendapatan ongkir"),
       ["Biaya logistik retur"], remap=False),
    _e("retur.ongkir_ppn_masukan", "1-1500", "PPN masukan atas ongkir",
       "bila pengaturan PPN ongkir aktif dan ekspedisi PKP", ("PPN masukan", "Kas/Bank"),
       ["Biaya logistik retur"], remap=False),
    _e("retur.cutloss_dibuang", "5-9500", "Beban potongan cacat (cutloss) dibuang",
       "potongan cacat cutloss diputuskan dibuang", ("Beban penghapusan", "Persediaan"),
       ["Cutloss retur"], remap=False),
    _e("retur.cutloss_bs", "1-1300", "Persediaan potongan BS (cutloss)",
       "potongan cacat cutloss masuk stok BS", ("Persediaan BS", "Persediaan"),
       ["Cutloss retur"], remap=False),
    _e("makloon.wip_subcon", "1-1350", "Persediaan dalam proses makloon", "bahan dikirim ke mitra makloon",
       ("WIP makloon", "Persediaan"), ["Makloon"]),
    _e("makloon.piutang_klaim", "1-1260", "Piutang klaim mitra makloon", "klaim susut/ganti rugi mitra",
       ("Piutang klaim", "Pendapatan klaim"), ["Makloon"]),
    _e("makloon.pendapatan_klaim", "4-9200", "Pendapatan klaim makloon", "klaim susut/ganti rugi mitra",
       ("Piutang klaim", "Pendapatan klaim"), ["Makloon"]),
    _e("makloon.jasa_tak_terserap", "5-1200", "Jasa makloon tak terserap", "jasa murni yang tak menempel ke kain",
       ("Jasa tak terserap", "Hutang"), ["Makloon"]),
    _e("antar_pt.piutang_ic", "1-1250", "Piutang antar-PT", "penjualan/transfer antar-PT",
       ("Piutang antar-PT", "Pendapatan"), ["Transaksi antar-PT"]),
    _e("antar_pt.utang_ic", "2-1250", "Utang antar-PT", "pembelian/transfer antar-PT",
       ("Persediaan", "Utang antar-PT"), ["Transaksi antar-PT"]),
    _e("sdm.beban_gaji", "6-1000", "Beban gaji & upah", "payroll diposting",
       ("Beban gaji", "Hutang gaji"), ["Payroll"]),
    _e("sdm.beban_bpjs", "6-1100", "Beban BPJS perusahaan", "payroll diposting",
       ("Beban BPJS", "Hutang BPJS"), ["Payroll"]),
    _e("sdm.hutang_gaji", "2-1600", "Hutang gaji", "payroll diposting & dibayar",
       ("Beban gaji", "Hutang gaji"), ["Payroll"]),
    _e("sdm.hutang_bpjs", "2-1700", "Hutang BPJS", "payroll diposting",
       ("Beban BPJS", "Hutang BPJS"), ["Payroll"]),
    _e("aset.akumulasi_penyusutan", "1-2900", "Akumulasi penyusutan", "penyusutan bulanan aset tetap",
       ("Beban penyusutan", "Akumulasi penyusutan"), ["Aset tetap"]),
    _e("aset.beban_penyusutan", "6-6000", "Beban penyusutan", "penyusutan bulanan aset tetap",
       ("Beban penyusutan", "Akumulasi penyusutan"), ["Aset tetap"]),
    _e("aset.laba_pelepasan", "4-9100", "Laba pelepasan aset", "aset dijual di atas nilai buku",
       ("Kas", "Laba pelepasan"), ["Aset tetap"]),
    _e("aset.rugi_pelepasan", "6-9500", "Rugi pelepasan aset", "aset dijual di bawah nilai buku",
       ("Rugi pelepasan", "Aset"), ["Aset tetap"]),
    _e("lain.suspense", "1-9999", "Akun penampung (suspense)", "posting yang belum jelas akunnya",
       ("Suspense", "Kas"), ["Posting gagal", "Reklas suspense"]),
]

BY_KEY: Dict[str, Dict[str, Any]] = {e["key"]: e for e in ENTRIES}
REMAP_BY_DEFAULT: Dict[str, str] = {e["default"]: e["key"] for e in ENTRIES if e["remap"]}
assert len(REMAP_BY_DEFAULT) == sum(1 for e in ENTRIES if e["remap"]), "default remap harus unik"


def require(key: str) -> Dict[str, Any]:
    if key not in BY_KEY:
        raise KeyError(f"Kebutuhan akun tidak dikenal: {key}")
    return BY_KEY[key]
