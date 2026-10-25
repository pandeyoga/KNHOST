// UAT 24 Okt (audit UI tahap 2) — G0-03/G0-14/G0-15/G0-16: API bersama aditif (formatter, label status,
// pembersih kode internal, pesan izin ditolak, label aksi audit).
import { formatCompactIDR, formatDecimal, formatPct, formatPeriod, formatQty } from "../formatters";
import { docStatusLabel, hasDocStatusLabel } from "../docStatus";
import { stripInternalCodes } from "../cleanText";
import apiErrorText, { isForbiddenError, permissionDeniedText } from "../apiError";
import { auditActionInfo, auditActionLabel, isKnownAuditAction } from "../../config/auditLabels";

describe("G0-14 formatter", () => {
  test("formatPct id-ID", () => {
    expect(formatPct(32.4)).toBe("32,4%");
    expect(formatPct(0.75, 2)).toBe("0,75%");
    expect(formatPct(12)).toBe("12,0%");
    expect(formatPct(12, 1, { trim: true })).toBe("12%");
    expect(formatPct(-0.01)).toBe("0,0%");
    expect(formatPct(null)).toBe("—");
    expect(formatPct("abc")).toBe("—");
  });
  test("formatPeriod", () => {
    expect(formatPeriod("2026-10")).toBe("Oktober 2026");
    expect(formatPeriod("2026-01-15")).toBe("Januari 2026");
    expect(formatPeriod("2026-10", { short: true })).toBe("Okt 2026");
    expect(formatPeriod("")).toBe("—");
    expect(formatPeriod("Q4")).toBe("Q4");
  });
  test("formatCompactIDR tanpa .0", () => {
    expect(formatCompactIDR(150000000)).toBe("150 jt");
    expect(formatCompactIDR(1400000000)).toBe("1,4 M");
    expect(formatCompactIDR(1000000000)).toBe("1 M");
    expect(formatCompactIDR(999960000)).toBe("1 M");
    expect(formatCompactIDR(12500)).toBe("12,5 rb");
    expect(formatCompactIDR(950)).toBe("950");
    expect(formatCompactIDR(-2500000)).toBe("-2,5 jt");
    expect(formatCompactIDR(2.5e12, { rp: true })).toBe("Rp 2,5 T");
    expect(formatCompactIDR(0)).toBe("0");
    expect(formatCompactIDR(undefined)).toBe("—");
  });
  test("formatDecimal pengganti toFixed", () => {
    expect(formatDecimal(1234.5)).toBe("1.234,5");
    expect(formatDecimal(0.756, 2)).toBe("0,76");
    expect(formatDecimal(3, 2, 2)).toBe("3,00");
    expect(formatDecimal(null)).toBe("—");
    expect(formatQty(1234.567)).toBe("1.234,57");   // formatter lama tidak berubah
  });
});

describe("G0-15 label status & pembersih kode", () => {
  test("docStatusLabel diperluas, kebal huruf besar/spasi, peta lokal didahulukan", () => {
    expect(docStatusLabel("waiting_goods")).toBe("Menunggu barang");
    expect(docStatusLabel("qc_pending")).toBe("Menunggu QC");
    expect(docStatusLabel("siap_disahkan")).toBe("Siap disahkan");
    expect(docStatusLabel("CANCELLED")).toBe("Dibatalkan");
    expect(docStatusLabel("Waiting Approval")).toBe("Menunggu persetujuan");
    expect(docStatusLabel("received", { received: "Diterima gudang" })).toBe("Diterima gudang");
    expect(docStatusLabel("some_code")).toBe("Some code");          // perilaku lama dipertahankan
    expect(docStatusLabel("constructor")).toBe("Constructor");      // bukan fungsi prototipe
    expect(docStatusLabel("")).toBe("");
    expect(hasDocStatusLabel("posted")).toBe(true);
    expect(hasDocStatusLabel("some_code")).toBe(false);
  });
  test("stripInternalCodes mengenal kode keputusan/invarian", () => {
    expect(stripInternalCodes("diputus sistem (KLR-05)")).toBe("diputus sistem");
    expect(stripInternalCodes("Menunggu KLX-03")).toBe("Menunggu");
    expect(stripInternalCodes("Dibayar per PT pembayar, KLX-03.")).toBe("Dibayar per PT pembayar.");
    expect(stripInternalCodes("Perbaikan (keputusan pemilik P7-K1) dicatat sebagai Vendor Bill"))
      .toBe("Perbaikan dicatat sebagai Vendor Bill");
    expect(stripInternalCodes("Siklus hidup R&D (KN-D16)")).toBe("Siklus hidup R&D");
    expect(stripInternalCodes("Auto-generated (FASE G-6) eliminasi (INV-IC-02/INV-IC-03)")).toBe("Auto-generated eliminasi");
    expect(stripInternalCodes("Auto G-6: Eliminasi antar-PT")).toBe("Auto Eliminasi antar-PT");
    expect(stripInternalCodes("Sinkron Antar-PT (G-6)")).toBe("Sinkron Antar-PT");
    expect(stripInternalCodes("Override kredit (KN_17 §5.2)")).toBe("Override kredit");
    expect(stripInternalCodes("Harga khusus (berlaku 30 hari, KLR-05)")).toBe("Harga khusus (berlaku 30 hari)");
    // bukan kode internal: kode warna & nomor dokumen tetap utuh
    expect(stripInternalCodes("Warna KN-BLU-01 untuk KSC/INV-00012")).toBe("Warna KN-BLU-01 untuk KSC/INV-00012");
    // aturan lama tetap jalan
    expect(stripInternalCodes("Langkah (FASE E-9) selesai")).toBe("Langkah selesai");
    expect(stripInternalCodes("")).toBe("");
  });
});

describe("G0-03 pesan izin ditolak", () => {
  const e403 = (detail) => ({ response: { status: 403, data: { detail } } });
  test("kode izin tidak tampil", () => {
    const t = apiErrorText(e403("Permission ditolak: approval.view"));
    expect(t).toBe("Anda tidak punya akses ke Persetujuan.");
    expect(apiErrorText(e403("Permission ditolak: settings.view"))).toBe("Anda tidak punya akses ke Pengaturan.");
    expect(apiErrorText(e403("Permission ditolak: sales_return.reject"))).toBe("Anda tidak punya izin “Tolak” di Retur Penjualan.");
  });
  test("keterangan server dipertahankan, kode dibuang", () => {
    const t = apiErrorText(e403("Permission ditolak: wms.untagged_override — roll tanpa tag wajib dicetak/diverifikasi RFID."));
    expect(t).toBe("Anda tidak punya izin “Izinkan Roll Tanpa Tag” di WMS / Gudang. Roll tanpa tag wajib dicetak/diverifikasi RFID.");
    expect(apiErrorText(e403("Permission ditolak: od_pricing.set_price (harga item tanpa induk diisi PIC Special Order).")))
      .toBe("Anda tidak punya izin “Tetapkan Harga” di Harga Pesanan Khusus. Harga item tanpa induk diisi PIC Special Order.");
    expect(apiErrorText(e403("Permission ditolak: butuh salah satu dari sales_return.view / interco.view / purchase_return.view")))
      .toBe("Anda tidak punya akses ke Retur Penjualan, Antar-Badan Usaha, atau Retur Pembelian.");
    expect(apiErrorText(e403("Permission ditolak: rnd.view atau design_request.view"))).toBe("Anda tidak punya akses ke R&D atau Permintaan Desain.");
  });
  test("403 dengan kalimat biasa & status lain tidak berubah", () => {
    expect(apiErrorText(e403("Akses gudang tujuan ditolak."))).toBe("Akses gudang tujuan ditolak.");
    expect(apiErrorText({ response: { status: 403, data: {} } })).toBe("Anda tidak punya izin untuk tindakan ini.");
    expect(apiErrorText({ response: { status: 400, data: { detail: "Wajib pilih alasan" } } })).toBe("Wajib pilih alasan");
    expect(apiErrorText("Permission ditolak: approval.view")).toBe("Anda tidak punya akses ke Persetujuan.");
    expect(permissionDeniedText("Gagal simpan")).toBe("");
  });
  test("isForbiddenError", () => {
    expect(isForbiddenError(e403("x"))).toBe(true);
    expect(isForbiddenError({ response: { status: 500, data: { detail: "Permission ditolak: a.view" } } })).toBe(true);
    expect(isForbiddenError({ response: { status: 404 } })).toBe(false);
    expect(isForbiddenError(null)).toBe(false);
  });
});

describe("G0-16 label aksi audit", () => {
  test("tidak jatuh ke humanize Inggris", () => {
    expect(auditActionLabel("reservation_expired")).toBe("Reservasi kedaluwarsa");
    expect(auditActionLabel("login")).toBe("Masuk");
    expect(auditActionLabel("logout")).toBe("Keluar");
    expect(auditActionLabel("bank_line_ignored")).toBe("Baris mutasi bank diabaikan");
    expect(auditActionLabel("order_created")).toBe("Pesanan dibuat");
    expect(auditActionLabel("zzz_unknown_thing")).toBe("Aksi lain");
    expect(isKnownAuditAction("zzz_unknown_thing")).toBe(false);
    expect(auditActionInfo("zzz_unknown_thing").code).toBe("zzz_unknown_thing");
    expect(auditActionLabel("constructor")).toBe("Aksi lain");
  });
});
