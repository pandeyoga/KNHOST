/** TransferDetailModal — detail view + lifecycle actions for a single transfer. */
import { useEffect, useState } from "react";
import { can } from "../../../config/roles";
import { CheckCircle, XCircle, BookOpen, ArrowRightLeft, AlertTriangle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatQty, formatCurrency } from "../../../utils/formatters";
import { StatusBadge } from "./transferConstants";
import TransferReceiptPanel from "./TransferReceiptPanel";
import DocumentActionsBar from "../../documents/DocumentActionsBar";
import ErrorNotice from "../../../components/ErrorNotice";
import DetailModal from "../../../components/DetailModal";
import QtyDual from "../../../components/QtyDual";      // FASE U — dua satuan
import { entityShortFromCtx } from "../../../utils/entityLabel";

const fmtIDR = (n) => formatCurrency(n);

export default function TransferDetailModal({ transfer, user, onClose, onApprove, onReject, onUpdateStatus, onCancel,
  actionError = "", onDismissActionError, onReceiptChanged }) {
  const je = transfer?.je_intercompany || null;
  const isIC = transfer?.transfer_kind === "inter_entity";
  // FE-04 — dulu hanya `role === "manager"`; server memakai izin transfer.approve / transfer.reject.
  const canApproveTransfer = can(user?.permissions, "transfer", "approve");
  const canRejectTransfer = can(user?.permissions, "transfer", "reject");
  const [ruleCheck, setRuleCheck] = useState([]);
  const [ruleReason, setRuleReason] = useState("");
  const showReceipt = !isIC && ["dispatched", "partially_received", "completed"].includes(transfer.status);
  useEffect(() => {
    if (!isIC || transfer.status !== "waiting_approval") return;
    axios.get(`${API}/transfers/${transfer.id}`).then((r) => setRuleCheck(r.data?.dest_rule_check || [])).catch(() => {});
  }, [isIC, transfer.id, transfer.status]);
  // Fase 3 · P5 — D-16 / L-03: dulu `div fixed inset-0` buatan sendiri (latar menutup walau KNSelect terbuka,
  // tanpa Esc berlapis); kini DetailModal baku (layar penuh di HP). Satu pop-up untuk transfer antar gudang & antar
  // PT — daftar antar-PT terpisah (kartu ungu + tombol lain) sudah dilebur ke daftar Transfer.
  return (
    <DetailModal onClose={onClose} size="lg" label={`Rincian transfer ${transfer.code || ""}`.trim()}
      testId="transfer-detail-modal" framed showClose={false}>
        <div className="p-1 sm:p-2">
          <div className="flex items-center justify-between gap-2 mb-4">
            <h3 className="text-lg font-semibold">
              Detail Transfer
              <span data-testid="transfer-detail-kind"
                className={`ml-2 align-middle status-pill ${isIC ? "pill-purple" : "pill-muted"}`}>
                {isIC ? "Antar PT" : "Antar gudang"}
              </span>
            </h3>
            <button type="button" onClick={onClose} data-testid="transfer-detail-close" className="icon-button" aria-label="Tutup">
              <XCircle size={20} className="text-[#3C3C43]" />
            </button>
          </div>

          {/* Dokumen — Surat Jalan Transfer (Pratinjau · Unduh PDF · Kirim WA) */}
          <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-[#EDEEF1] bg-[#FAFBFC] px-3 py-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-[#8E8E93]">Dokumen</span>
            <DocumentActionsBar
              docType="transfer"
              sourceId={transfer.id}
              entityId={transfer.entity_id}
              number={transfer.code}
              label="Surat Jalan Transfer"
              esignable={false}
              autoCheckSignature={false}
              currentUser={user}
            />
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#F2F2F7] rounded-lg p-3">
                <p className="text-xs text-[#3C3C43] mb-1">Kode</p>
                <p className="font-semibold" data-testid="transfer-detail-code">{transfer.code}</p>
              </div>
              <div className="bg-[#F2F2F7] rounded-lg p-3">
                <p className="text-xs text-[#3C3C43] mb-1">Status</p>
                <StatusBadge status={transfer.status} />
              </div>
              {isIC ? (
                <>
                  <div className="bg-[#F3EAFB] rounded-lg p-3 border border-[#E6D8F0]" data-testid="transfer-detail-source-entity">
                    <p className="text-xs text-[#6B219A] mb-1 flex items-center gap-1">
                      <ArrowRightLeft size={11} /> PT Sumber
                    </p>
                    <p className="font-semibold text-sm">{entityShortFromCtx(transfer.source_entity_id, transfer.source_entity_name || "—")}</p>
                  </div>
                  <div className="bg-[#F3EAFB] rounded-lg p-3 border border-[#E6D8F0]" data-testid="transfer-detail-dest-entity">
                    <p className="text-xs text-[#6B219A] mb-1 flex items-center gap-1">
                      <ArrowRightLeft size={11} /> PT Tujuan
                    </p>
                    <p className="font-semibold text-sm">{entityShortFromCtx(transfer.dest_entity_id, transfer.dest_entity_name || "—")}</p>
                  </div>
                </>
              ) : (
                <>
                  <div className="bg-[#F2F2F7] rounded-lg p-3">
                    <p className="text-xs text-[#3C3C43] mb-1">Gudang Asal</p>
                    <p className="font-semibold text-sm">{transfer.source_warehouse_name}</p>
                  </div>
                  <div className="bg-[#F2F2F7] rounded-lg p-3">
                    <p className="text-xs text-[#3C3C43] mb-1">Gudang Tujuan</p>
                    <p className="font-semibold text-sm">{transfer.dest_warehouse_name}</p>
                  </div>
                </>
              )}
            </div>

            {transfer.sales_order_number && (
              <div data-testid="transfer-detail-so" className="rounded-lg border border-[#D7E3F7] bg-[#F7FAFF] px-3 py-2 text-[12px]">
                Transfer untuk memenuhi <b>{transfer.sales_order_number}</b>{transfer.sales_order_customer ? ` · ${transfer.sales_order_customer}` : ""}.
                <span className="block text-[11px] text-[#6B6B73]">SJ transfer ini terpisah dari surat jalan pelanggan; roll berkomitmen tetap terkunci untuk SO.</span>
              </div>
            )}
            {ruleCheck.length > 0 && (
              <div data-testid="transfer-detail-rule-check" className="rounded-lg border border-[#F1C4C1] bg-[#FDF1F0] px-3 py-2 text-[12px] text-[#8A1C17]">
                <p className="flex items-center gap-1 font-semibold"><AlertTriangle size={13} /> {ruleCheck.length} roll melanggar aturan gudang untuk pemilik baru</p>
                <ul className="mt-1 list-disc pl-4 text-[11px]">{ruleCheck.slice(0, 5).map((v) => <li key={v.roll_id}>{v.roll_no} @ {v.warehouse}: {v.violations[0]}</li>)}</ul>
                <input data-testid="transfer-approve-rule-reason" value={ruleReason} onChange={(e) => setRuleReason(e.target.value)}
                  placeholder="Alasan pengecualian (supervisor) — wajib agar bisa disetujui" className="mt-2 w-full rounded border border-[#E5B34A] bg-white px-2 py-1 text-[11px]" />
              </div>
            )}
            {showReceipt && (
              <TransferReceiptPanel transfer={transfer} user={user} onChanged={onReceiptChanged} />
            )}
            {/* Items */}
            <div>
              <h4 className="text-sm font-semibold mb-2">Barang</h4>
              <div className="space-y-2">
                {transfer.items?.map((item, index) => (
                  <div key={index} className="flex items-center justify-between bg-[#F2F2F7] rounded-lg p-2">
                    <div>
                      <p className="text-sm font-semibold">{item.sku} - {item.product_name}</p>
                      {(item.lots?.length > 0 || item.rolls?.length > 0) && (
                        <p className="text-[11px] text-[#6B6B73] mt-0.5">
                          {item.rolls?.length > 0 && <span>{item.rolls.length} roll</span>}
                          {item.lots?.length > 0 && <span> • Lot: {item.lots.join(", ")}</span>}
                          {item.owner_entity_id && <span> • Pemilik: {entityShortFromCtx(item.owner_entity_id)}</span>}
                        </p>
                      )}
                    </div>
                    <p className="text-sm font-bold tabular-nums"><QtyDual rolls={item.qty_rolls} measure={item.qty} unit={item.unit} /></p>
                  </div>
                ))}
              </div>
            </div>

            {/* M-3 — Audit trail JE Intercompany (hanya untuk inter-entity, at-cost) */}
            {isIC && je && (
              <div data-testid="transfer-detail-je-intercompany" className="rounded-lg border border-[#E6D8F0] bg-[#FAF6FE] p-3">
                <div className="flex items-center gap-2 mb-2">
                  <BookOpen size={14} className="text-[#6B219A]" />
                  <h4 className="text-sm font-semibold text-[#6B219A]">Jurnal Antar-PT (sebesar biaya)</h4>
                  {je.posted ? (
                    <span className="ml-auto text-[10px] font-bold uppercase tracking-wide rounded-full bg-[#6B219A] text-white px-2 py-0.5">
                      Terposting
                    </span>
                  ) : (
                    <span className="ml-auto text-[10px] font-bold uppercase tracking-wide rounded-full bg-gray-200 text-gray-700 px-2 py-0.5">
                      Belum terposting
                    </span>
                  )}
                </div>
                {je.posted ? (
                  <div className="space-y-2 text-[12px]">
                    <div className="flex items-center justify-between">
                      <span className="text-[#6B6B73]">Total nilai</span>
                      <span className="font-bold tabular-nums" data-testid="je-ic-total">{fmtIDR(je.total)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#6B6B73]">Pair ID</span>
                      <span className="font-mono text-[11px] text-[#3C3C43]" data-testid="je-ic-pair">{je.pair_id}</span>
                    </div>
                    <div className="border-t border-[#E6D8F0] pt-2 space-y-1">
                      {je.source_je && (
                        <div className="flex items-center justify-between" data-testid="je-ic-source">
                          <span className="text-[#6B6B73]">Sumber ({entityShortFromCtx(je.source_je.entity_id)})</span>
                          <span className="font-mono font-semibold text-[#0058CC]">{je.source_je.number}</span>
                        </div>
                      )}
                      {je.dest_je && (
                        <div className="flex items-center justify-between" data-testid="je-ic-dest">
                          <span className="text-[#6B6B73]">Tujuan ({entityShortFromCtx(je.dest_je.entity_id)})</span>
                          <span className="font-mono font-semibold text-[#0058CC]">{je.dest_je.number}</span>
                        </div>
                      )}
                    </div>
                    {Array.isArray(je.breakdown) && je.breakdown.length > 0 && (
                      <details className="pt-1">
                        <summary className="text-[11px] text-[#6B219A] cursor-pointer hover:underline" data-testid="je-ic-breakdown-toggle">
                          Lihat rincian nilai per produk ({je.breakdown.length})
                        </summary>
                        <table className="w-full text-[11px] mt-2">
                          <thead className="text-[#8E8E93]">
                            <tr><th className="text-left py-1">Produk</th><th className="text-right">Qty</th><th className="text-right">Biaya/Satuan</th><th className="text-right">Nilai</th></tr>
                          </thead>
                          <tbody>
                            {je.breakdown.map((b, i) => (
                              <tr key={i} className="border-t border-[#E6D8F0]/50">
                                <td className="py-1"><span className="font-mono text-[10px] text-[#6B6B73]">{b.sku}</span> {b.name}</td>
                                <td className="text-right tabular-nums">{formatQty(b.qty)}</td>
                                <td className="text-right tabular-nums">{fmtIDR(b.unit_cost)}</td>
                                <td className="text-right tabular-nums font-semibold">{fmtIDR(b.value)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </details>
                    )}
                  </div>
                ) : (
                  // UAT 24 Okt (audit UI tahap 2) — dulu "NOT POSTED · JE tidak di-post — alasan tidak diketahui."
                  <p className="text-[11px] text-[#6B6B73]" data-testid="je-ic-not-posted">
                    Jurnal belum terposting — {je.reason === "zero_cost"
                      ? "produk yang ditransfer belum memiliki HPP (rata-rata biaya = 0)."
                      : je.reason === "already_posted"
                      ? "jurnal untuk transfer ini sudah pernah diposting."
                      : <>penyebabnya tercatat di <a href="?view=posting-failures" className="font-semibold text-[#6B219A] underline">Posting Gagal</a>.</>}
                  </p>
                )}
              </div>
            )}

            {/* Actions */}
            {/* FASE P5 — kegagalan aksi (setujui/tolak/batal) tampil DI SINI, di dalam
                modal, tepat di atas tombolnya. Sebelumnya `alert()`; kalau dipindah ke
                bilah halaman ia akan tertutup modal ini sendiri → penolakan backend
                (mis. "status sudah berubah") hilang tanpa jejak. */}
            <ErrorNotice message={actionError} onDismiss={onDismissActionError} testId="transfer-action-error" />
            <div className="flex flex-wrap gap-2">
              {transfer.status === "waiting_approval" && (canApproveTransfer || canRejectTransfer) && (   /* FE-04 — transfer.approve / transfer.reject */
                <>
                  {canApproveTransfer && <button
                    data-testid="approve-transfer-button"
                    onClick={() => onApprove(transfer.id, ruleReason)}
                    className="primary-button flex items-center gap-2"
                  >
                    <CheckCircle size={14} /> {isIC ? "Setujui & pindahkan kepemilikan" : "Setujui"}
                  </button>}
                  {canRejectTransfer && <button
                    data-testid="reject-transfer-button"
                    onClick={() => onReject(transfer.id)}
                    className="danger-button flex items-center gap-2"
                  >
                    <XCircle size={14} /> Tolak
                  </button>}
                </>
              )}
              {transfer.status === "approved" && (
                <button
                  data-testid="start-picking-button"
                  onClick={() => onUpdateStatus(transfer.id, "picking")}
                  className="primary-button"
                >
                  Mulai Pengambilan
                </button>
              )}
              {transfer.status === "picking" && (
                <button
                  data-testid="move-to-staging-button"
                  onClick={() => onUpdateStatus(transfer.id, "staging")}
                  className="primary-button"
                >
                  Siap Muat (Staging)
                </button>
              )}
              {transfer.status === "staging" && (
                <button
                  data-testid="dispatch-button"
                  onClick={() => onUpdateStatus(transfer.id, "dispatched")}
                  className="primary-button"
                >
                  Berangkatkan (Dalam Perjalanan)
                </button>
              )}
              {!isIC && ["dispatched", "partially_received"].includes(transfer.status) && (
                <p data-testid="transfer-receipt-hint" className="text-[11px] text-[#6B6B73] self-center">
                  Transfer selesai otomatis setelah semua roll diterima atau dikembalikan (lihat Penerimaan per roll).
                </p>
              )}
              {!["completed", "rejected", "cancelled", "partially_received"].includes(transfer.status) && (
                <button
                  data-testid="cancel-transfer-button"
                  onClick={() => onCancel(transfer.id)}
                  className="secondary-button"
                >
                  Batal
                </button>
              )}
            </div>
          </div>
        </div>
    </DetailModal>
  );
}
