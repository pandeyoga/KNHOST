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
