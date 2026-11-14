// HRD H4 — util Payroll bersama.
import axios, { API } from "../../services/apiClient";
import { formatCurrency, formatPct } from "../../utils/formatters";

export const rp = (v) => formatCurrency(v || 0);
// UAT 24 Okt (audit UI tahap 2) — G5-66: persen id-ID ("0,75%", dulu "0.75%" dari toFixed). `v` = rasio 0–1.
export const pct = (v) => formatPct(Number(v || 0) * 100, 2);

// PK-22 — label sama dengan server (`hr_payroll_service.RUN_STATUS_LABEL`, dipakai pesan 409 "…berstatus {label}…");
// lencana Dibatalkan & Dianulir baru (glosarium: void = anulir); status antara (`posting`, `paying`, `voiding`) = langkah yang sedang berjalan.
export const RUN_STATUS = {
  draft: { cls: "pill-muted", label: "Draf" },
  // UTANG ALUR F-6.7 — tahap "diajukan" ada di antara draf & disetujui supaya draf yang
  // masih dikerjakan HR tidak bercampur dengan yang menunggu keputusan penyetuju.
  pending_approval: { cls: "pill-warning", label: "Menunggu pengesahan" },
  approved: { cls: "pill-info", label: "Disahkan" },
  posting: { cls: "pill-info", label: "Sedang diposting" },
  posted: { cls: "pill-warning", label: "Diposting" },
  paying: { cls: "pill-warning", label: "Sedang dibayar" },
  paid: { cls: "pill-success", label: "Dibayar" },
  cancelled: { cls: "pill-muted", label: "Dibatalkan" },
  voiding: { cls: "pill-warning", label: "Sedang dianulir" },
  void: { cls: "pill-danger", label: "Dianulir" },
};
// PY-T1 — jenis proses gaji (server: `hr_pay_components.RUN_TYPE_LABEL`); proses lama tanpa jenis = Reguler.
export const RUN_TYPE_LABEL = { regular: "Reguler", thr: "THR", susulan: "Susulan" };
export const RUN_TYPE_OPTIONS = Object.entries(RUN_TYPE_LABEL).map(([value, label]) => ({ value, label }));
export const runTypeLabel = (t) => RUN_TYPE_LABEL[t || "regular"] || RUN_TYPE_LABEL.regular;

/** Potongan slip tanpa PPh 21 = BPJS karyawan + potongan lain (komponen). */
export const slipDeductions = (s) => Number(s?.bpjs_emp_total || 0) + Number(s?.other_deductions || 0);

const GROUPS = [["pendapatan", "Pendapatan"], ["potongan", "Potongan"], ["tanggungan_perusahaan", "Tanggungan perusahaan"]];
/** PY-T1 — komponen slip dikelompokkan Pendapatan · Potongan · Tanggungan perusahaan. Slip lama tanpa `components`
 *  disusun dari kolomnya (baris bernilai 0 dilewati, kecuali gaji pokok). */
export function slipGroups(s) {
  let rows = Array.isArray(s?.components) ? s.components : null;
  if (!rows || rows.length === 0) {
    const b = s?.bpjs_emp || {};
    const n = (v) => Number(v || 0);
    rows = [
      { code: "GAJI_POKOK", label: "Gaji Pokok", kind: "pendapatan", amount: n(s?.base_salary) },
      { code: "TUNJANGAN", label: "Tunjangan", kind: "pendapatan", amount: n(s?.allowances) },
      { code: "LEMBUR", label: "Lembur", kind: "pendapatan", amount: n(s?.overtime) },
      { code: "KOMISI", label: "Komisi / insentif penjualan", kind: "pendapatan", amount: n(s?.commission) },
      { code: "BPJS_KES", label: "BPJS Kesehatan", kind: "potongan", amount: n(b.kesehatan) },
      { code: "BPJS_JHT", label: "BPJS JHT", kind: "potongan", amount: n(b.jht) },
      { code: "BPJS_JP", label: "BPJS JP", kind: "potongan", amount: n(b.jp) },
      { code: "PPH21", label: "PPh 21", kind: "potongan", amount: n(s?.pph21) },
      { code: "BPJS_PT", label: "BPJS (perusahaan)", kind: "tanggungan_perusahaan", amount: n(s?.bpjs_er_total) },
    ].filter((r) => r.code === "GAJI_POKOK" || r.code === "PPH21" || r.amount !== 0);
  }
  return GROUPS.map(([key, label]) => ({ key, label, rows: rows.filter((r) => r.kind === key) }));
}

/** Aksi yang boleh menurut status (sama dengan server PK-22). */
export const CAN_RECALC = ["draft"];
export const CAN_CANCEL = ["draft", "pending_approval", "approved"];
export const CAN_VOID = ["posted"];

const WIB_OFFSET_MS = 7 * 3600 * 1000;
export const curMonth = () => new Date(Date.now() + WIB_OFFSET_MS).toISOString().slice(0, 7);
export function recentMonths(n = 15) {
  const out = [];
  const d = new Date(Date.now() + WIB_OFFSET_MS);
  d.setDate(1);
  for (let i = 0; i < n; i++) { out.push(d.toISOString().slice(0, 7)); d.setMonth(d.getMonth() - 1); }
  return out;
}

// Unduh / buka PDF slip via blob (axios membawa header Authorization).
export async function openPayslipPdf(slipId) {
  const res = await axios.get(`${API}/hr/payslips/${slipId}/pdf`, { responseType: "blob" });
  const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
