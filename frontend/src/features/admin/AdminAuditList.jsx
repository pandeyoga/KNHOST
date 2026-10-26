/**
 * AdminAuditList — daftar Jejak Audit (Pengaturan › Integrasi & Sistem › Integrasi & Audit).
 *
 * Fase 3 · P2 — diekstrak dari `AdminView.jsx` (batas 500 baris) apa adanya. UAT 24 Okt (audit UI tahap 2, G5-01):
 * tampilan bawaan = label aksi, nama pelaku, jenis dokumen berlabel, ringkasan data; kode/id hanya tooltip.
 */
import { useState } from "react";
import { auditActionInfo, moduleLabel } from "../../config/auditLabels";   // X-2 · G0-16
import { formatCurrency, formatDateTime } from "../../utils/formatters";
import { entityShortById } from "../../utils/entityLabel";
import { docStatusLabel } from "../../utils/docStatus";
import { actorLabel } from "../../utils/actorLabel";
import { roleLabel } from "../../config/roles";

const AUDIT_RES_LABEL = {
  user: "Akun pengguna", sales_order: "Pesanan penjualan", purchase_order: "Pesanan pembelian", uom: "Satuan",
  document_template: "Template dokumen", product: "Produk", customer: "Pelanggan", wms_task: "Tugas gudang",
  design_gallery: "Galeri desain", journal_entry: "Jurnal", vendor_bill: "Tagihan supplier", settings: "Pengaturan",
};
const auditResource = (t) => (t ? AUDIT_RES_LABEL[t] || moduleLabel(t) : "—");
const AUDIT_FIELD_LABEL = {
  email: "Email", role: "Peran", status: "Status", name: "Nama", number: "Nomor", order_number: "Nomor pesanan",
  po_number: "Nomor PO", code: "Kode", amount: "Nilai", grand_total: "Total", quantity: "Jumlah", reason: "Alasan",
  customer_name: "Pelanggan", supplier_name: "Supplier", grade: "Grade",
};
const auditFieldValue = (k, v) => (k === "role" ? roleLabel(v) : k === "status" ? docStatusLabel(v)
  : ["amount", "grand_total"].includes(k) && Number.isFinite(Number(v)) ? formatCurrency(v) : String(v));
function auditSummary(log) {
  const src = log.after ?? log.details ?? {};
  const parts = [];
  if (src && typeof src === "object" && !Array.isArray(src)) {
    const keys = Object.keys(src);
    keys.filter((k) => AUDIT_FIELD_LABEL[k] && src[k] != null && src[k] !== "" && typeof src[k] !== "object")
      .slice(0, 4).forEach((k) => parts.push(`${AUDIT_FIELD_LABEL[k]}: ${auditFieldValue(k, src[k])}`));
    const rest = keys.length - parts.length;
    if (rest > 0) parts.push(parts.length ? `+${rest} data lain` : `${rest} data teknis`);
  }
  if (log.reason) parts.unshift(`Alasan: ${log.reason}`);
  return parts.join(" · ");
}
/** Peran pelaku: "system/demo" bukan peran — login mencatat peran akun di `after.role`; job sistem = "Sistem". */
const auditRole = (log) => {
  const r = String(log.role || "");
  if (r && !r.startsWith("system")) return roleLabel(r);
  if (log.action === "login" && log.after?.role) return roleLabel(log.after.role);
  return actorLabel(log.actor) === "Sistem" ? "Sistem" : "—";
};
const auditTech = (log) => `Kunci aksi: ${log.action} · ${log.entity_type || "-"}: ${log.entity_id || "-"}`;
// Fase 4 · R6 (G5-01) — server kini mengirim `doc_number` (nomor dokumen/nama yang bisa dibaca, bukan id teknis):
// "Pesanan penjualan KSC/SO-00012" alih-alih hanya jenis datanya.
const auditDoc = (log) => [auditResource(log.entity_type), log.doc_number].filter((x) => x && x !== "—").join(" ") || "—";
const AUDIT_PAGE = 50;   // X-2 — render bertahap, bukan 500 baris sekaligus

export default function AdminAuditList({ auditLogs = [], scopeEntities = [], onShowDetail }) {
  const [shown, setShown] = useState(AUDIT_PAGE);
  const logs = auditLogs || [];
  return (
    <div data-testid="audit-history-records" className="grid gap-2">
      {logs.slice(0, shown).map((log) => {
        const info = auditActionInfo(log.action);
        const scopeName = log.scope_entity_name || (log.scope_entity_id ? entityShortById(scopeEntities, log.scope_entity_id, "") : "");
        const summary = auditSummary(log);
        return (
          <button data-testid={`audit-row-${log.id}`} key={log.id} title={auditTech(log)} type="button"
            className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] interactive-card p-2.5 text-left"
            onClick={() => onShowDetail({ title: info.label, body: `${actorLabel(log.actor)} · ${auditDoc(log)}${summary ? ` — ${summary}` : ""}`,
              facts: [{ label: "Pelaku", value: actorLabel(log.actor) }, { label: "Peran", value: auditRole(log) },
                { label: "Jenis data", value: auditResource(log.entity_type) },
                ...(log.doc_number ? [{ label: "Nomor / nama", value: log.doc_number }] : []),
                { label: "Badan Usaha", value: scopeName || "Tingkat grup" },
                { label: "Waktu", value: formatDateTime(log.timestamp) }] })}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[12.5px] font-semibold">{info.label}</p>
              <p className="text-[10.5px] font-semibold text-[#0058CC]">{formatDateTime(log.timestamp)}</p>
            </div>
            <p className="mt-0.5 text-[11.5px] text-[#3C3C43]" data-testid={`audit-row-doc-${log.id}`}>{[actorLabel(log.actor), auditDoc(log), scopeName].filter(Boolean).join(" • ")}</p>
            {summary && <p className="mt-1 line-clamp-2 text-[10.5px] text-[#3C3C43]">{summary}</p>}
          </button>
        );
      })}
      {logs.length > shown && (
        <button data-testid="audit-show-more" className="secondary-button justify-self-center" onClick={() => setShown((n) => n + AUDIT_PAGE)}>
          Tampilkan {Math.min(AUDIT_PAGE, logs.length - shown)} lagi ({shown} dari {logs.length})
        </button>
      )}
      {logs.length === 0 && <p data-testid="audit-empty" className="px-3 py-6 text-center text-[12px] text-[#6B6B73]">Tidak ada jejak audit untuk filter ini.</p>}
    </div>
  );
}
