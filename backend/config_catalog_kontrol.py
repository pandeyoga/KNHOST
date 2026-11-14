"""KF-T6 — Katalog **kontrol "harus dua orang"** yang bisa diatur per PT (`docs/blueprint/unit/KF-T6.md`).

Keputusan pemilik 13 Nov 2026 (`docs/blueprint/01_KEPUTUSAN.md` butir 2): setiap aturan "pengaju tidak boleh
memutuskan sendiri" menjadi pengaturan per PT. Aksi yang HARI INI sudah melarang setuju-sendiri mulai dengan "2"
(tidak ada kontrol yang melonggar diam-diam saat dipasang); buka periode dan aksi yang dulu tanpa pemeriksaan mulai
dengan "1".

Satu putaran mendaftarkan, untuk tiap aksi di `KONTROL_AKSI`:
  kontrol.<aksi>.min_orang       enum "1" · "2"                  (35 aksi)
  kontrol.<aksi>.batas_nominal   money, 0 = tidak dipakai        (aksi ber-nominal saja)
plus dua kunci pengecualian Admin. Pembacanya satu: `services/dual_control.py`. Layarnya: Pengaturan › Persetujuan ›
Kontrol dua orang (`frontend/src/features/settings/kontrol/DualControlView.jsx`).

Unit lain menambah aksinya di sini (`bayar_hutang`, `cairkan_uang_muka`, `lembar_insentif`, `ubah_profil_kredit`,
`asisten_uang_keluar`) — cukup satu baris `KONTROL_AKSI` + titik pasang `tolak_bila_pelaku_sama("<aksi>", …)`.
"""
from typing import Any, Dict, List, Tuple

from config_registry import E

G = ("global", "entity")
_DC = "services/dual_control.py"

#: Kelompok layar (urutan tampil di tab Kontrol dua orang).
BAGIAN: Tuple[str, ...] = ("Pembelian & hutang", "Penjualan & piutang", "Gudang & produksi", "SDM", "Buku besar")


def _a(aksi: str, label: str, kelompok: str, awal: str, punya_nominal: bool, bagian: str,
       titik: Tuple[str, ...] = ()) -> Dict[str, Any]:
    return {"aksi": aksi, "label": label, "kelompok": kelompok, "awal": awal,
            "punya_nominal": punya_nominal, "bagian": bagian, "titik": titik}


_PB, _PJ, _GD, _SDM, _BB = BAGIAN

#: 35 aksi (tabel A–C spesifikasi). `kelompok`: A = dulu diatur sakelar, B = dulu ditulis mati melarang,
#: C = dulu tanpa pemeriksaan. `titik` = fungsi yang memanggil `tolak_bila_pelaku_sama("<aksi>", …)`.
KONTROL_AKSI: List[Dict[str, Any]] = [
    # A — dulu sakelar `approval.matrix_sod` / `amendment.dual_control`
    _a("acc_desain", "ACC desain", "A", "2", False, _GD),
    _a("acc_sample", "Keputusan sample", "A", "2", False, _GD),
    _a("po_custom", "Pesanan khusus (PO custom)", "A", "2", True, _PJ),
    _a("permintaan_pembelian", "Permintaan pembelian (PR)", "A", "2", True, _PB),
    _a("harga_khusus", "Harga khusus", "A", "2", False, _PJ),
    _a("amandemen", "Koreksi / amandemen dokumen", "A", "2", True, _BB),
    # B — dulu ditulis mati melarang
    _a("setujui_po", "Persetujuan PO", "B", "2", True, _PB),
    _a("po_tingkat_berikut", "PO berjenjang: tingkat berikutnya", "B", "2", False, _PB),
    _a("tagihan_pemasok", "Tagihan pemasok", "B", "2", True, _PB),
    _a("biaya_masuk", "Voucher biaya masuk", "B", "2", True, _PB),
    _a("kontrabon", "Kontrabon", "B", "2", True, _PB),
    _a("tagihan_kampanye", "Tagihan kampanye", "B", "2", True, _PB),
    _a("retur_antar_pt", "Retur antar-PT", "B", "2", True, _PJ),
    _a("buka_periode", "Buka periode buku", "B", "1", False, _BB),
    _a("susut_makloon", "Susut bahan di mitra makloon", "B", "2", True, _GD),
    _a("pengecualian_retur", "Pengecualian retur", "B", "2", False, _PJ),
    _a("klaim_desain", "Klaim kepemilikan desain", "B", "2", False, _PJ),
    _a("registrasi_stok_awal", "Stok awal: penyetuju nilai ≠ penyetuju hitungan", "B", "2", False, _GD),
    # C — dulu tanpa pemeriksaan (bawaan satu orang)
    _a("transfer_gudang", "Transfer gudang / antar-PT", "C", "1", False, _GD),
    _a("stok_opname", "Stok opname", "C", "1", False, _GD),
    _a("retur_penjualan", "Retur penjualan", "C", "1", True, _PJ),
    _a("retur_pembelian", "Retur pembelian", "C", "1", True, _PB),
    _a("cuti", "Cuti", "C", "1", False, _SDM),
    _a("lembur", "Lembur", "C", "1", False, _SDM),
    _a("proses_gaji", "Pengesahan gaji", "C", "1", True, _SDM),
    _a("uang_muka", "Uang muka / kasbon", "C", "1", True, _SDM),
    _a("lpj_uang_muka", "Pertanggungjawaban uang muka", "C", "1", True, _SDM),
    _a("pengurang_piutang", "Bebas denda dan hapus selisih bayar", "C", "1", True, _PJ),
    _a("lewat_batas_kredit", "Izin lewat batas kredit", "C", "1", True, _PJ),
    _a("klaim_makloon", "Klaim selisih makloon", "C", "1", True, _GD),
    _a("permintaan_internal", "Permintaan internal antar-PT", "C", "1", False, _GD),
    _a("permintaan_desain", "Permintaan desain", "C", "1", False, _GD),
    _a("nilai_pesanan", "Persetujuan nilai pesanan", "C", "1", True, _PJ),
    _a("buka_kembali_tutup_buku", "Buka kembali tutup buku", "C", "1", False, _BB),
    _a("jurnal_manual", "Jurnal manual", "C", "1", True, _BB),
]
AKSI_BY_ID: Dict[str, Dict[str, Any]] = {a["aksi"]: a for a in KONTROL_AKSI}

#: Empat titik † yang dulu TIDAK mengecualikan Admin (ASUMSI unit: dipertahankan lewat daftar ini).
ADMIN_TETAP_DUA_ORANG_AWAL = ["susut_makloon", "pengecualian_retur", "klaim_desain", "registrasi_stok_awal"]

K_ADMIN_BOLEH = "kontrol.admin_boleh_sendiri"
K_ADMIN_TETAP = "kontrol.admin_tetap_dua_orang"


def kunci_min_orang(aksi: str) -> str:
    return f"kontrol.{aksi}.min_orang"


def kunci_batas(aksi: str) -> str:
    return f"kontrol.{aksi}.batas_nominal"


_OPSI = ({"value": "1", "label": "Cukup satu orang"}, {"value": "2", "label": "Harus dua orang"})

for _x in KONTROL_AKSI:
    _cons = tuple(_x["titik"]) + (f"{_DC}:butuh_orang_kedua",)
    E(kunci_min_orang(_x["aksi"]), group="persetujuan", type="enum", default=_x["awal"], options=_OPSI, scopes=G,
      label=f"{_x['label']}: jumlah orang",
      help="1 = orang yang mengajukan boleh memutuskan sendiri. 2 = harus diputuskan orang lain.",
      impact=(f"Bila 2, pengaju “{_x['label']}” tidak bisa memutuskannya sendiri — rekan lain yang berwenang "
              "harus memutuskan. Bila 1, satu orang cukup."),
      example=f"Rina mengajukan “{_x['label']}” lalu memutuskannya sendiri → ditolak bila 2, lolos bila 1",
      consumers=_cons, risk="high", requires_reason=True, permission=("settings", "manage"),
      related=((kunci_batas(_x["aksi"]),) if _x["punya_nominal"] else ()) + (K_ADMIN_BOLEH,))
    if _x["punya_nominal"]:
        E(kunci_batas(_x["aksi"]), group="persetujuan", type="money", default=0, min=0, max=1000000000000,
          step=1000000, unit="Rp", scopes=G,
          label=f"{_x['label']}: dua orang di atas (Rp)",
          help="Di atas nilai ini selalu dua orang walau jumlah orang = 1. 0 = tidak dipakai.",
          impact=("Dokumen bernilai di atas batas ini wajib diputuskan orang selain pengajunya, walau jumlah "
                  "orang diatur 1."),
          example=f"Batas 5.000.000 · “{_x['label']}” Rp 6.000.000 diajukan Rina → harus diputuskan rekan lain",
          consumers=_cons, risk="high", requires_reason=True, permission=("settings", "manage"),
          related=(kunci_min_orang(_x["aksi"]),))

E(K_ADMIN_BOLEH, group="persetujuan", type="bool", default=True, scopes=G,
  label="Admin boleh memutuskan dokumennya sendiri",
  help="Bila ya, Admin tidak terkena aturan dua orang; tiap kejadian dicatat di jejak persetujuan.",
  impact=("Bila tidak, Admin yang mengajukan dokumen juga harus meminta Admin/rekan lain untuk memutuskannya — "
          "seperti pengguna lain."),
  example="Ya · Admin membuat PO lalu menyetujuinya sendiri → lolos, tercatat 'diputuskan sendiri oleh admin'",
  consumers=(f"{_DC}:tolak_bila_pelaku_sama",), risk="high", requires_reason=True,
  permission=("settings", "manage"), related=(K_ADMIN_TETAP,))

E(K_ADMIN_TETAP, group="persetujuan", type="list", default=list(ADMIN_TETAP_DUA_ORANG_AWAL), scopes=G,
  label="Aksi yang tetap dua orang walau Admin",
  help="Admin pun tidak boleh memutuskan sendiri untuk aksi di daftar ini.",
  impact="Aksi yang dicentang tetap butuh orang kedua walau Admin boleh memutuskan dokumennya sendiri.",
  example="Daftar memuat 'pengecualian_retur' · Admin mengajukan pengecualian retur → Admin lain yang memutuskan",
  consumers=(f"{_DC}:tolak_bila_pelaku_sama",), risk="high", requires_reason=True,
  permission=("settings", "manage"), related=(K_ADMIN_BOLEH,))
