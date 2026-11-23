/**
 * incentiveModes.js — KA-9 · SATU tempat nilai sakelar insentif PT (`hr.payroll_commission_mode`) di frontend.
 *
 * Dipakai kartu "Capaian & Insentif Saya" (`MyIncentiveCard`), Target & Aturan (kartu Kesiapan), tab Skema & Tarif
 * (① Sumber insentif, kartu akrual), Beranda Sales, dan layar HP sales. Pilihan & labelnya ada di registri
 * (`backend/config_catalog_ops.py`); pembaca server satu: `hr_payroll_service.commission_mode`.
 *
 * Pemetaan pilihan ① (rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.5, keputusan penulis):
 * "Komisi otomatis" → `accrue_then_settle`, KECUALI PT sedang `pay_on_invoice` (nilai itu dipertahankan; cara pembukuan
 * tidak diubah diam-diam); "Lembar Insentif" → `sheet`; "Keduanya dibayar" → `auto_and_sheet`. `off` dan
 * `pay_on_invoice` tampil apa adanya ("lain") dengan tautan ke Pusat Pengaturan.
 */
export const MODE_OTOMATIS = "accrue_then_settle";   // komisi otomatis: dicadangkan, dilunasi lewat gaji (bawaan)
export const MODE_SAAT_FAKTUR = "pay_on_invoice";    // komisi otomatis dibayar saat faktur terbit (tanpa akrual)
export const MODE_MATI = "off";                      // tidak ada komisi di gaji
export const MODE_LEMBAR = "sheet";                  // dari Lembar Insentif yang disahkan
export const MODE_KEDUANYA = "auto_and_sheet";       // KA-7 — komisi otomatis + Lembar Insentif, keduanya dibayar

/** Sakelar yang mematikan komisi otomatis (mesin tidak menghitung komisi untuk PT itu). */
export const MODE_TANPA_MESIN = [MODE_LEMBAR, MODE_MATI];
/** Sakelar yang membukukan akrual komisi otomatis tiap bulan (KA-7: termasuk "keduanya dibayar"). */
export const MODE_AKRU = [MODE_OTOMATIS, MODE_KEDUANYA];

/** Komisi otomatis berjalan di PT bermode `mode`? Mode kosong/tidak diketahui = tidak. */
export const komisiOtomatisJalan = (mode) => !!mode && !MODE_TANPA_MESIN.includes(mode);

/** Pilihan ① untuk mode tersimpan: "otomatis" | "lembar" | "keduanya" | "lain" (`pay_on_invoice`, `off`, lainnya). */
export function pilihanSumber(mode) {
  if (mode === MODE_OTOMATIS) return "otomatis";
  if (mode === MODE_LEMBAR) return "lembar";
  if (mode === MODE_KEDUANYA) return "keduanya";
  return "lain";
}

/** Mode yang disimpan bila pengguna memilih `pilihan` sementara PT bermode `modeSekarang`. */
export function modeDariPilihan(pilihan, modeSekarang) {
  if (pilihan === "lembar") return MODE_LEMBAR;
  if (pilihan === "keduanya") return MODE_KEDUANYA;
  if (pilihan === "otomatis") return modeSekarang === MODE_SAAT_FAKTUR ? MODE_SAAT_FAKTUR : MODE_OTOMATIS;
  return modeSekarang;
}

/** Pilihan ini mengubah cara pembukuan PT `pay_on_invoice` menjadi akrual bulanan? (wajib dikonfirmasi) */
export function butuhKonfirmasiAkru(pilihan, modeSekarang) {
  return modeSekarang === MODE_SAAT_FAKTUR && MODE_AKRU.includes(modeDariPilihan(pilihan, modeSekarang));
}
