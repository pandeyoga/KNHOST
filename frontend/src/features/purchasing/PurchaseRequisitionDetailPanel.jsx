import { useState } from "react";
import { DualName } from "../../components/DualName";
import KNDatePicker from "@/components/KNDatePicker";
import axios, { API } from "../../services/apiClient";
import {
  ArrowLeft, CheckCircle2, XCircle, Send, ShoppingCart, AlertTriangle, Ban, Pencil,
} from "lucide-react";
import { formatCurrency, formatDate, formatQty } from "../../utils/formatters";
import { actorLabel } from "../../utils/actorLabel";
import { roleLabel } from "../../config/roles";
import { askConfirm, askReason, REASON_MIN_LENGTH } from "../../services/confirmService";
import FormModal from "../../components/FormModal";
import { apiErrorText } from "../../utils/apiError";
import KNSelect from "../../components/KNSelect";
import SiteSelect from "../../components/SiteSelect";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import { SOURCE_LABEL, StatusPill, Field } from "./prConstants";
import PrSourcingPanel from "./PrSourcingPanel";
import PrLineQtyModal from "./PrLineQtyModal";   // AS-02 — ubah qty beli baris
import { FULFILLMENT_META } from "./supplier-items/supplierItemsApi";
import QtyDual from "../../components/QtyDual";      // FASE U — dua satuan

/**
 * DetailPanel — detail PR + aksi lifecycle (submit/approve/reject/cancel/convert).
 * Diekstrak dari PurchaseRequisitions.jsx agar file utama < 500 baris (compliance).
 */
export default function DetailPanel({ pr, canApprove, suppliers, warehouses, onBack, onChanged, reload }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [showConvert, setShowConvert] = useState(false);
  const [convSupplier, setConvSupplier] = useState(pr.preferred_supplier_id || "");
  const [convSite, setConvSite] = useState(pr.ship_to_site_id || "");
  const [convDate, setConvDate] = useState("");
  const [showReject, setShowReject] = useState(false);   // H3 — tangkap alasan tolak
  const [rejectReason, setRejectReason] = useState("");
  const [qtyLine, setQtyLine] = useState(null);         // AS-02 — baris yang qty-nya diubah
  // Fase 4 · R3 (L-03) — galat pop-up konversi/tolak tampil DI pop-up, bukan di bilah halaman di belakang lapisan.
  const [dlgErr, setDlgErr] = useState("");

  const nonCatalog = (pr.items || []).some((it) => !it.product_id);
  const canEditQty = ["draft", "pending_approval", "approved"].includes(pr.status);

  async function act(path, body) {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/purchase-requisitions/${pr.id}${path}`, body || {});
      onChanged("Tindakan berhasil.");
      reload(pr.id);
    } catch (e) {
      setErr(e.response?.data?.detail || "Aksi gagal.");
    } finally { setBusy(false); }
  }

  // UAT 24 Okt (audit UI tahap 2) — G4-11: Setujui & Batalkan dulu langsung POST tanpa dialog (padahal
  // Tolak wajib alasan). Setujui → konfirmasi; Batalkan → alasan (dikirim sebagai `notes`).
  async function approve() {
    const ok = await askConfirm({
      title: `Setujui ${pr.number}?`,
      message: `Estimasi ${formatCurrency(pr.total_est_amount)}. Setelah disetujui, PR bisa direalisasikan menjadi PO dan bahan untuk pesanan dicadangkan.`,
      confirmLabel: "Setujui PR",
    });
    if (ok) act("/approve");
  }

  async function cancel() {
    const reason = await askReason({
      title: `Batalkan ${pr.number}?`,
      message: "PR yang dibatalkan tidak bisa diajukan atau direalisasikan lagi; cadangan bahan dilepas.",
      reasonLabel: "Alasan pembatalan",
      confirmLabel: "Batalkan PR",
      danger: true,
    });
    if (reason !== null) act("/cancel", { notes: reason });
  }

  async function doReject() {
    if (rejectReason.trim().length < REASON_MIN_LENGTH) { setDlgErr(`Alasan penolakan minimal ${REASON_MIN_LENGTH} huruf.`); return; }
    setBusy(true); setDlgErr("");
    try {
      await axios.post(`${API}/purchase-requisitions/${pr.id}/reject`, { notes: rejectReason.trim() });
      onChanged(`${pr.number} ditolak.`);
      setShowReject(false);
      reload(pr.id);
    } catch (e) {
      setDlgErr(apiErrorText(e, "Gagal menolak PR."));
    } finally { setBusy(false); }
  }

  async function doConvert() {
    if (!convSupplier) { setDlgErr("Pilih supplier."); return; }
    setBusy(true); setDlgErr("");
    try {
      const res = await axios.post(`${API}/purchase-requisitions/${pr.id}/convert-to-po`, {
        supplier_id: convSupplier, ship_to_site_id: convSite, warehouse_id: convSite ? "" : (pr.warehouse_id || ""),
        expected_delivery_date: convDate,
      });
      onChanged(`Dikonversi ke ${res.data.po.po_number}.`);
      setShowConvert(false);
      reload(pr.id);
    } catch (e) {
      setDlgErr(apiErrorText(e, "Konversi gagal."));
    } finally { setBusy(false); }
  }

  return (
    <div data-testid="pr-detail" className="grid gap-4">
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2">
            <button className="icon-button" onClick={onBack}><ArrowLeft size={15} /></button>
            <h2 data-testid="pr-detail-number">{pr.number}</h2>
            <StatusPill status={pr.status} />
          </div>
          <div className="flex items-center gap-2">
            {/* UAT 24 Okt (audit UI tahap 2) — G4-11: satu pintu cetak (Pratinjau/Unduh PDF di bilah dokumen). */}
            <span className="status-pill pill-muted">{SOURCE_LABEL[pr.source] || pr.source}</span>
          </div>
        </div>
        <div className="section-body grid gap-3">
          {err && <div className="notice-bar danger" data-testid="pr-detail-error"><span>{err}</span><button onClick={() => setErr("")}>×</button></div>}

          <div className="grid gap-2 sm:grid-cols-3 text-[12px]">
            <Field label="Lokasi kirim" value={pr.ship_to_site_name ? `${pr.ship_to_site_name} · ${pr.warehouse_name || ""}` : (pr.warehouse_name || "—")} />
            <Field label="Supplier Preferensi" value={pr.preferred_supplier_name || "—"} />
            <Field label="Dibutuhkan" value={formatDate(pr.needed_by_date)} />
            <Field label="Dibuat oleh" value={actorLabel(pr.created_by)} />
            <Field label="Persetujuan" value={pr.approval_required ? `Perlu ${roleLabel(pr.required_approval_role || "manager")}` : "Tidak perlu"} />
            <Field label="Total Estimasi" value={formatCurrency(pr.total_est_amount)} />
          </div>
          {pr.reason && <p className="text-[12px] text-[#6B6B73]"><b>Alasan:</b> {pr.reason}</p>}
          {pr.po_number && <p className="text-[12px]" data-testid="pr-linked-po"><b>PO terkait:</b> <span className="text-[#0058CC] font-semibold">{pr.po_number}</span></p>}

          {/* Dokumen PR (mesin dokumen terpadu — PDF asli / e-sign / WA) */}
          <DocumentActionsBar docType="purchase_requisition" sourceId={pr.id} entityId={pr.entity_id}
            number={pr.number} label="Permintaan Pembelian" currentUser={{ role: "admin" }}
            className="rounded-lg border border-[#EDEEF1] bg-[#FAFBFC] px-2.5 py-2" />


          {/* Items */}
          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="grid grid-cols-[1.4fr_105px_100px_120px_120px] bg-[#FAFBFC] px-3 py-1.5 text-[10px] font-bold uppercase text-[#6B6B73]">
              <span>Item</span><span>Pemenuhan</span><span className="text-right">Qty</span><span className="text-right">Est. Harga</span><span className="text-right">Subtotal</span>
            </div>
            {(pr.items || []).map((it, i) => (
              <div key={i} data-testid={`pr-detail-item-${i}`} className="grid grid-cols-[1.4fr_105px_100px_120px_120px] items-center px-3 py-2 border-t border-[#F4F5F7]">
                <div className="min-w-0">
                  <DualName item={it} testId={`pr-detail-dualname-${i}`} />
                  <p className="text-[10px] text-[#9A9BA3]">{it.product_id ? `${it.sku} · ${it.unit}` : <span className="text-[#8C4A00]">Non-katalog · {it.unit}</span>}</p>
                </div>
                <span>
                  <span data-testid={`pr-detail-mode-${i}`}
                    className={`status-pill ${(FULFILLMENT_META[it.fulfillment_mode || "purchase"] || {}).cls || "pill-muted"}`}>
                    {(FULFILLMENT_META[it.fulfillment_mode || "purchase"] || {}).label || "Beli"}
                  </span>
                </span>
                <span className="text-[12px] tabular-nums text-right">
                  <QtyDual rolls={it.qty_rolls} measure={it.quantity} unit={it.unit} factor={it.unit_factor} factorTo={it.unit_factor_to} />
                  {it.order_qty != null && Number(it.extra_qty) > 0 && (
                    <span className="block text-[9.5px] font-semibold text-[#126E2C]" data-testid={`pr-detail-extra-${i}`}
                      title={`Kebutuhan pesanan ${formatQty(it.order_qty)} ${it.unit}; kelebihan untuk stok`}>
                      pesanan {formatQty(it.order_qty)} · +{formatQty(it.extra_qty)} stok
                    </span>
                  )}
                  {canEditQty && (
                    <button data-testid={`pr-detail-qty-edit-${i}`} className="mt-0.5 inline-flex items-center gap-0.5 text-[9.5px] font-semibold text-[#0058CC] hover:underline"
                      onClick={() => setQtyLine(it)} title="Ubah qty beli (boleh di atas kebutuhan pesanan)">
                      <Pencil size={9} /> ubah qty
                    </button>
                  )}
                </span>
                <span className="text-[12px] tabular-nums text-right">{formatCurrency(it.est_price)}</span>
                <span className="text-[12px] tabular-nums text-right font-semibold">{formatCurrency(it.subtotal)}</span>
              </div>
            ))}
            {(pr.items || []).length === 0 && (
              <div data-testid="pr-detail-items-empty" className="px-3 py-4 text-center text-[12px] text-[#9A9BA3]">Belum ada item pada PR ini.</div>
            )}
          </div>

          {nonCatalog && (
            <div className="flex items-center gap-2 text-[11.5px] text-[#8C4A00] bg-[#FFF8EE] border border-[#FFE2B8] rounded-md px-3 py-2">
              <AlertTriangle size={14} /> Ada item non-katalog (dari Pesanan Khusus) — tidak bisa dikonversi otomatis ke PO. Buat produk dulu atau proses manual.
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-wrap justify-end gap-2 pt-1">
            {pr.status === "draft" && (
              <button data-testid="pr-action-submit" className="btn-primary" disabled={busy} onClick={() => act("/submit")}><Send size={14} /> Ajukan</button>
            )}
            {pr.status === "pending_approval" && canApprove && (
              <>
                <button data-testid="pr-action-reject" className="btn-danger" disabled={busy} onClick={() => { setRejectReason(""); setDlgErr(""); setShowReject(true); }}><XCircle size={14} /> Tolak</button>
                <button data-testid="pr-action-approve" className="btn-primary" disabled={busy} onClick={approve}><CheckCircle2 size={14} /> Setujui</button>
              </>
            )}
            {pr.status === "approved" && (
              <button data-testid="pr-action-convert" className="btn-primary" disabled={busy || nonCatalog} onClick={() => { setDlgErr(""); setShowConvert(true); }}><ShoppingCart size={14} /> Konversi ke PO</button>
            )}
            {["draft", "pending_approval", "approved"].includes(pr.status) && (
              <button data-testid="pr-action-cancel" className="btn-secondary" disabled={busy} onClick={cancel}><Ban size={14} /> Batalkan</button>
            )}
          </div>
        </div>
      </section>

      {/* FASE E — routing & realisasi per baris (beli ke supplier / proses via makloon) */}
      {["approved", "converted"].includes(pr.status) && (
        <PrSourcingPanel pr={pr} suppliers={suppliers} warehouses={warehouses}
          onChanged={onChanged} reload={reload} />
      )}

      {/* Convert modal — Fase 4 · R3 (L-03): FormModal baku (layar penuh di HP, Esc berlapis, galat DI pop-up). */}
      <FormModal open={showConvert} onClose={() => setShowConvert(false)} size="sm" icon={ShoppingCart}
        title={`Konversi ${pr.number} → Pesanan Pembelian`} subtitle="Pilih supplier & gudang untuk membuat PO."
        testId="pr-convert-modal" onSubmit={doConvert} submitTestId="pr-convert-confirm"
        submitLabel={busy ? "Memproses…" : "Buat PO"} busy={busy} error={dlgErr}>
        <div className="grid gap-3">
          <div className="grid gap-1.5">
            <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Supplier *</label>
            <KNSelect
              data-testid="pr-convert-supplier"
              className="form-input"
              value={convSupplier}
              onValueChange={setConvSupplier}
              placeholder="— Pilih supplier —"
              options={suppliers.map((s) => ({ value: s.id, label: s.name }))}
            />
          </div>
          <div className="grid gap-1.5">
            <SiteSelect testId="pr-convert-site" value={convSite} onChange={setConvSite} entityId={pr.entity_id || ""} />
          </div>
          <div className="grid gap-1.5">
            <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Estimasi Tanggal Terima</label>
            <KNDatePicker data-testid="pr-convert-date" value={convDate} onChange={setConvDate} />
          </div>
        </div>
      </FormModal>

      {/* AS-02 — ubah qty beli baris */}
      {qtyLine && (
        <PrLineQtyModal pr={pr} line={qtyLine} onClose={() => setQtyLine(null)}
          onDone={() => { setQtyLine(null); onChanged("Qty beli diperbarui."); reload(pr.id); }} />
      )}

      {/* H3 — Reject modal (alasan wajib, bukan hardcode). Fase 4 · R3 (L-03): FormModal; alasan ≥ 5 huruf (K-14). */}
      <FormModal open={showReject} onClose={() => setShowReject(false)} size="sm" icon={XCircle}
        title={`Tolak ${pr.number}`} subtitle="Berikan alasan penolakan (akan tersimpan di riwayat & audit)."
        testId="pr-reject-modal" onSubmit={doReject} busy={busy} error={dlgErr}
        footer={(
          <div className="flex items-center justify-end gap-2">
            <button type="button" className="secondary-button" disabled={busy} onClick={() => setShowReject(false)}>Batal</button>
            <button type="submit" data-testid="pr-reject-confirm" className="danger-button"
              disabled={busy || rejectReason.trim().length < REASON_MIN_LENGTH}>{busy ? "Memproses…" : "Tolak PR"}</button>
          </div>
        )}>
        <div className="grid gap-1.5">
          <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Alasan Penolakan *</label>
          <textarea data-testid="pr-reject-reason" className="form-input" rows="3"
            value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}
            placeholder="Mis. nilai di atas anggaran, supplier belum disetujui, dsb." />
          <p className="text-[10.5px] text-[#6B6B73]">Minimal {REASON_MIN_LENGTH} huruf.</p>
        </div>
      </FormModal>
    </div>
  );
}