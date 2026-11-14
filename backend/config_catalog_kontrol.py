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
#: C = dulu tanpa pemeriksaan. `titik` (diisi serah-terima (b), `_TITIK` di bawah) = fungsi yang memanggil
#: `tolak_bila_pelaku_sama("<aksi>", …)` — jadi `consumers` registry dan dikenali `config_health`.
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
    # PK-38 — nama diperluas: aksi ini kini juga mencakup kasus keuangan yang menutup piutang tanpa uang masuk.
    _a("pengurang_piutang", "Pengurang piutang tanpa uang masuk", "C", "1", True, _PJ),
    _a("lewat_batas_kredit", "Izin lewat batas kredit", "C", "1", True, _PJ),
    _a("klaim_makloon", "Klaim selisih makloon", "C", "1", True, _GD),
    _a("permintaan_internal", "Permintaan internal antar-PT", "C", "1", False, _GD),
    _a("permintaan_desain", "Permintaan desain", "C", "1", False, _GD),
    _a("nilai_pesanan", "Persetujuan nilai pesanan", "C", "1", True, _PJ),
    _a("buka_kembali_tutup_buku", "Buka kembali tutup buku", "C", "1", False, _BB),
    _a("jurnal_manual", "Jurnal manual", "C", "1", True, _BB),
    # PK-38 (IA-12, K-17) — bayar kontrabon: pembanding = PENYETUJU kontrabon; bawaan satu orang.
    _a("bayar_hutang", "Bayar hutang", "C", "1", True, _PB),
    # PM-T1 — membuat rekening dan mengubah field peka rekening (nomor, bank, atas nama, peruntukan, cara bayar,
    # bawaan penerimaan, tampil di dokumen, aktif); tanpa nominal, bawaan satu orang.
    _a("ubah_rekening", "Ubah rekening kas/bank", "C", "1", False, _BB),
    # CR-T1 (K-28) — memutus pengajuan perubahan profil kredit pelanggan (plafon, termin, hari blokir, blokir manual);
    # bernominal = plafon BARU (0 bila plafon tidak diubah), bawaan satu orang.
    _a("ubah_profil_kredit", "Ubah profil kredit pelanggan", "C", "1", True, _PJ),
    # PK-24 (K-17) — mencairkan uang muka yang sudah disetujui; pembanding = PEMOHON PD (penerima dana); bernominal =
    # nilai PD, bawaan satu orang.
    _a("cairkan_uang_muka", "Cairkan uang muka", "C", "1", True, _SDM),
]

#: KF-T6 serah-terima (b) — titik pasang tiap aksi (`berkas.py:fungsi`).
_TITIK: Dict[str, Tuple[str, ...]] = {
    "acc_desain": ("services/approval_matrix_service.py:guard",),
    "acc_sample": ("services/approval_matrix_service.py:guard",),
    "po_custom": ("services/approval_matrix_service.py:guard",),
    "permintaan_pembelian": ("services/approval_matrix_service.py:guard", "services/purchase_requisition_service.py:approve_requisition"),
    "harga_khusus": ("routers/price_approvals.py:approve_price_approval", "routers/price_approvals.py:reject_price_approval", "routers/so_approvals.py:decide_approval"),
    "amandemen": ("services/amendment_service.py:decide",),
    "setujui_po": ("routers/purchase_orders.py:approve_purchase_order",),
    "po_tingkat_berikut": ("routers/purchase_orders.py:approve_purchase_order",),
    "tagihan_pemasok": ("routers/vendor_bills.py:approve_vendor_bill",),
    "biaya_masuk": ("routers/landed_cost.py:approve_landed_cost",),
    "kontrabon": ("services/contra_bon_service.py:approve",),
    "tagihan_kampanye": ("services/marketing_cost_service.py:approve_campaign_bill",),
    "retur_antar_pt": ("services/interco_return_service.py:approve",),
    "buka_periode": ("services/period_unlock_service.py:approve_request",),
    "susut_makloon": ("services/makloon_loss_service.py:decide_loss",),
    "pengecualian_retur": ("services/return_exception_service.py:decide",),
    "klaim_desain": ("services/design_ownership_service.py:decide_claim",),
    "registrasi_stok_awal": ("services/initial_registration_service.py:assert_finance_ready",),
    "transfer_gudang": ("routers/transfers.py:approve_transfer",),
    "stok_opname": ("routers/cycle_count.py:approve_session",),
    "retur_penjualan": ("routers/sales_returns.py:approve_return",),
    "retur_pembelian": ("routers/purchase_returns.py:approve_purchase_return",),
    "cuti": ("services/hr_leave_service.py:approve_leave",),
    "lembur": ("services/hr_leave_service.py:approve_overtime",),
    "proses_gaji": ("services/hr_payroll_service.py:approve_run",),
    "uang_muka": ("services/cash_advance_service.py:approve_cash_advance",),
    "lpj_uang_muka": ("services/cash_advance_service.py:approve_settlement",),
    "pengurang_piutang": ("services/penalty_service.py:waive", "services/payment_variance_service.py:decide_receipt", "services/payment_variance_service.py:decide_bill", "routers/payment_variance.py:decide", "services/ar_reduction_guard.py:periksa"),   # PK-38 — + satu pintu pengurang piutang
    "lewat_batas_kredit": ("routers/crm.py:decide_credit_override",),
    "klaim_makloon": ("routers/makloon_orders.py:approve_claim",),
    "permintaan_internal": ("services/internal_request_service.py:convert",),
    "permintaan_desain": ("services/design_request_service.py:approve",),
    "nilai_pesanan": ("routers/sales_orders_extra.py:approve_order",),
    "buka_kembali_tutup_buku": ("routers/closing.py:_reopen_dua_orang",),
    "jurnal_manual": ("routers/gl.py:create_journal", "services/journal_proposal_service.py:setujui"),
    "bayar_hutang": ("services/contra_bon_service.py:pay",),   # PK-38
    "ubah_rekening": ("services/bank_account_change_service.py:_dua_orang",
                      "services/bank_account_change_service.py:putuskan"),   # PM-T1
    "ubah_profil_kredit": ("services/credit_profile_service.py:decide",),   # CR-T1
    "cairkan_uang_muka": ("services/cash_advance_service.py:disburse_cash_advance",),   # PK-24
}
for _x in KONTROL_AKSI:
    _x["titik"] = _TITIK.get(_x["aksi"], ())

# KF-T4 — sub-judul di Pengaturan (≤ 14 kunci per sub-judul): bagian layar dipecah bila lebih besar.
_SUB_JUDUL: Dict[str, Tuple[str, ...]] = {
    "dua-orang-pembelian": ("permintaan_pembelian", "setujui_po", "po_tingkat_berikut", "retur_pembelian"),
    "dua-orang-hutang": ("tagihan_pemasok", "biaya_masuk", "kontrabon", "tagihan_kampanye", "bayar_hutang"),
    "dua-orang-piutang": ("pengurang_piutang", "lewat_batas_kredit", "ubah_profil_kredit"),   # CR-T1 + 1
}
_SUB_BAGIAN = {_PJ: "dua-orang-penjualan", _GD: "dua-orang-gudang", _SDM: "dua-orang-sdm", _BB: "dua-orang-buku"}
#: KF-T4 (T1) — nama pendek untuk label Pengaturan (≤ 45 huruf); nama panjang tetap dipakai tab Kontrol dua orang.
_PENDEK: Dict[str, str] = {
    "po_custom": "Pesanan khusus", "permintaan_pembelian": "Permintaan pembelian", "amandemen": "Koreksi dokumen",
    "po_tingkat_berikut": "PO tingkat berikutnya", "susut_makloon": "Susut makloon",
    "registrasi_stok_awal": "Nilai stok awal", "lpj_uang_muka": "Laporan uang muka",
    "pengurang_piutang": "Pengurang piutang", "lewat_batas_kredit": "Lewat batas kredit",   # PK-38
    "nilai_pesanan": "Nilai pesanan",
    "ubah_profil_kredit": "Profil kredit pelanggan",   # CR-T1
}
for _x in KONTROL_AKSI:
    _x["sub_judul"] = next((s for s, aksi in _SUB_JUDUL.items() if _x["aksi"] in aksi), _SUB_BAGIAN.get(_x["bagian"], ""))
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

#: PK-38 (FX-10, K-11) — satu batas untuk semua pengurang piutang tanpa uang masuk. Bawaan = batas hapus sisa yang
#: berlaku hari ini (Rp 1.000.000); selama kunci ini belum pernah diisi (grup maupun PT), nilai kunci lama
#: `payment.variance_writeoff_max_amount` yang dipakai (`services/ar_reduction_guard.py:batas`).
_BATAS_KHUSUS: Dict[str, Dict[str, Any]] = {
    "pengurang_piutang": dict(
        default=1000000, min=0, max=1000000000, step=100000, unit="Rp",
        label="Batas pengurang piutang tanpa uang masuk",
        help=("Berlaku untuk hapus sisa kurang bayar dan penyelesaian kasus yang menutup piutang tanpa uang masuk "
              "(biaya bank, uang dipegang karyawan, salah PT). Di atas nilai ini keputusan harus diambil orang yang "
              "berbeda dari pembuat dokumennya. 0 = tidak dipakai."),
        impact="Menaikkan nilai ini memperbesar piutang yang bisa dihapus satu orang.",
        example="Rp 1.000.000 · biaya bank Rp 1.500.000 diputus pembuat kasusnya sendiri → ditolak, harus orang kedua",
        consumers=("services/ar_reduction_guard.py:batas", f"{_DC}:butuh_orang_kedua"),
        related=(kunci_min_orang("pengurang_piutang"), "case.auto_bank_charge_max")),
}
#: KF-T4 — kartu di "Semua pengaturan" tanpa editor: kontrol dua orang diubah di satu tempat (tab Kontrol dua orang).
_EDIT_AT = {"view": "settings-dual-control", "label": "Persetujuan › Kontrol dua orang"}

for _x in KONTROL_AKSI:
    _cons = tuple(_x["titik"]) + (f"{_DC}:butuh_orang_kedua",)
    E(kunci_min_orang(_x["aksi"]), group="persetujuan", section=_x["sub_judul"], type="enum", default=_x["awal"], options=_OPSI, scopes=G,
      label=f"{_PENDEK.get(_x['aksi'], _x['label'])}: jumlah orang",
      help="1 = orang yang mengajukan boleh memutuskan sendiri. 2 = harus diputuskan orang lain.",
      impact=(f"Bila 2, pengaju “{_x['label']}” tidak bisa memutuskannya sendiri — rekan lain yang berwenang "
              "harus memutuskan. Bila 1, satu orang cukup."),
      example=f"Rina mengajukan “{_x['label']}” lalu memutuskannya sendiri → ditolak bila 2, lolos bila 1",
      consumers=_cons, risk="high", requires_reason=True, permission=("settings", "manage"), edit_at=_EDIT_AT,
      related=((kunci_batas(_x["aksi"]),) if _x["punya_nominal"] else ()) + (K_ADMIN_BOLEH,))
    if _x["punya_nominal"] and _x["aksi"] in _BATAS_KHUSUS:
        E(kunci_batas(_x["aksi"]), group="persetujuan", section=_x["sub_judul"], type="money", scopes=G,
          risk="high", requires_reason=True, permission=("settings", "manage"), edit_at=_EDIT_AT,
          **_BATAS_KHUSUS[_x["aksi"]])
    elif _x["punya_nominal"]:
        E(kunci_batas(_x["aksi"]), group="persetujuan", section=_x["sub_judul"], type="money", default=0, min=0, max=1000000000000,
          step=1000000, unit="Rp", scopes=G,
          label=f"{_PENDEK.get(_x['aksi'], _x['label'])}: dua orang di atas",
          help="Di atas nilai ini selalu dua orang walau jumlah orang = 1. 0 = tidak dipakai.",
          impact=("Dokumen bernilai di atas batas ini wajib diputuskan orang selain pengajunya, walau jumlah "
                  "orang diatur 1."),
          example=f"Batas 5.000.000 · “{_x['label']}” Rp 6.000.000 diajukan Rina → harus diputuskan rekan lain",
          consumers=_cons, risk="high", requires_reason=True, permission=("settings", "manage"), edit_at=_EDIT_AT,
          related=(kunci_min_orang(_x["aksi"]),))

E(K_ADMIN_BOLEH, group="persetujuan", section="dua-orang-admin", type="bool", default=True, scopes=G,
  label="Admin boleh memutuskan dokumennya sendiri",
  help="Bila ya, Admin tidak terkena aturan dua orang; tiap kejadian dicatat di jejak persetujuan.",
  impact=("Bila tidak, Admin yang mengajukan dokumen juga harus meminta Admin/rekan lain untuk memutuskannya — "
          "seperti pengguna lain."),
  example="Ya · Admin membuat PO lalu menyetujuinya sendiri → lolos, tercatat 'diputuskan sendiri oleh admin'",
  consumers=(f"{_DC}:tolak_bila_pelaku_sama",), risk="high", requires_reason=True,
  permission=("settings", "manage"), related=(K_ADMIN_TETAP,), edit_at=_EDIT_AT)

E(K_ADMIN_TETAP, group="persetujuan", section="dua-orang-admin", type="list", default=list(ADMIN_TETAP_DUA_ORANG_AWAL), scopes=G,
  label="Aksi yang tetap dua orang walau Admin",
  help="Admin pun tidak boleh memutuskan sendiri untuk aksi di daftar ini.",
  impact="Aksi yang dicentang tetap butuh orang kedua walau Admin boleh memutuskan dokumennya sendiri.",
  example="Daftar memuat Pengecualian retur · Admin mengajukan pengecualian retur → Admin lain yang memutuskan",
  consumers=(f"{_DC}:tolak_bila_pelaku_sama",), risk="high", requires_reason=True,
  permission=("settings", "manage"), related=(K_ADMIN_BOLEH,), edit_at=_EDIT_AT)
