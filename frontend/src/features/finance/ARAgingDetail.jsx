/**
 * ARAgingDetail — rincian piutang SATU pelanggan (pop-up dari layar Piutang `ar-aging`).
 *
 * Fase 3 · P4 — diekstrak dari ARAgingView.jsx (batas 500 baris) dan:
 *  · kepala panel di HP 390 px: dulu satu baris kaku (judul + ringkasan + lencana kredit + "Buat Nota Denda" + ×)
 *    sehingga tombol × berada di x≈403 (di luar layar) dan panel bisa digeser ke samping. Kini baris 1 = judul + ×
 *    (selalu terlihat), baris 2 = ringkasan + aksi, keduanya membungkus;
 *  · L-07: tabel mentah → `.table-wrap` + `.data-table` baku (bergulir di dalam wadahnya sendiri).
 */
import { FileText, Loader2, Receipt, X, BadgeDollarSign } from "lucide-react";
import { formatCurrency, formatDate } from "../../utils/formatters";
import StoreCreditBadge from "../../components/StoreCreditBadge";
import PenaltyPanel from "./payments/PenaltyPanel";
import { openTrace } from "../documents/trace/traceDeepLink";
import { penaltyMeta } from "./payments/paymentApi";
// INV-ROLE-01 — wewenang dibaca dari IZIN, bukan dari daftar nama peran.
import { can } from "../../config/roles";

// UAT 24 Okt (audit UI tahap 2) — G1-15: tanggal tampilan satu format ("25 Okt 2026", WIB) via formatDate.
const fmtDate = (iso) => formatDate(iso);

export default function ARAgingDetail({ detail, customerId, loading, currentUser, accruing, onAccrue, onRefresh, onClose }) {
  // INV-ROLE-01 — sama seperti di layar induk: izin, bukan nama peran.
  const canAccrue = can(currentUser?.permissions || {}, "penalty", "issue");
  const t = detail?.totals || {};
  return (
    <div className="section-card mt-3" data-testid="ar-aging-detail">
      <div className="section-head flex-wrap items-start gap-x-2 gap-y-1.5">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          <FileText size={15} className="flex-shrink-0 text-[#0058CC]" />
          <h2 className="min-w-0 normal-case break-words" data-testid="ar-aging-detail-customer">{detail?.customer_name || "Rincian Piutang"}</h2>
          <StoreCreditBadge customerId={customerId} testId="ar-aging-store-credit" />
        </div>
        <button data-testid="ar-aging-detail-close" className="icon-button flex-shrink-0" onClick={onClose} aria-label="Tutup"><X size={14} /></button>
        {(detail || canAccrue) && (
          <div className="flex basis-full flex-wrap items-center gap-x-3 gap-y-1.5">
            {detail && (
              <span className="min-w-0 text-[11px] text-[#6B6B73]" data-testid="ar-aging-detail-summary">
                Belum lunas <b className="tabular-nums">{formatCurrency(t.total)}</b>{" "}
                (ledger <b className="tabular-nums" data-testid="ar-detail-ledger-total">{formatCurrency(t.ar_ledger || 0)}</b>
                {" "}· eksposur <b className="tabular-nums" data-testid="ar-detail-exposure-total">{formatCurrency(t.exposure || 0)}</b>)
              </span>
            )}
            {canAccrue && (
              <button type="button" className="secondary-button ml-auto" data-testid="ar-aging-accrue"
                disabled={accruing} onClick={onAccrue}>
                {accruing ? <Loader2 size={13} className="animate-spin" /> : <Receipt size={13} />}
                Buat Nota Denda
              </button>
            )}
          </div>
        )}
      </div>
      <div className="section-body space-y-3">
        {loading ? (
          <div className="grid gap-2" data-testid="ar-aging-detail-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
        ) : !detail || (detail.items || []).length === 0 ? (
          <div className="py-8 text-center text-[12px] text-[#8E8E93]" data-testid="ar-aging-detail-empty">Tidak ada pesanan terbuka.</div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table" data-testid="ar-aging-detail-table">
                <thead>
                  <tr>
                    <th>Pesanan</th>
                    <th>Jatuh Tempo</th>
                    <th className="text-center">Umur</th>
                    <th className="text-right">Total</th>
                    <th className="text-right">Terbayar</th>
                    <th className="text-right">Belum Lunas</th>
                    <th className="text-right" title="Piutang ledger (sudah diakui) · eksposur (belum dikirim)">Ledger · Eksposur</th>
                    <th className="text-right">Est. Denda</th>
                    <th>Nota Denda</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.items.map((it) => (
                    <tr key={it.order_id} data-testid={`ar-detail-row-${it.order_id}`}>
                      <td className="px-3 py-2 font-semibold text-[#0058CC]">
                        {it.order_number}
                        {it.has_plan && (
                          <span className="ml-1 rounded bg-[#EFF4FF] px-1 text-[9px] font-bold text-[#0058CC]"
                            title={`Rencana pembayaran ${it.plan_number}`}>RPB</span>
                        )}
                      </td>
                      {/* F-16 — jatuh tempo = Surat Jalan pertama + termin; belum dikirim = belum jatuh tempo */}
                      <td className="px-3 py-2 text-[#3C3C43]" data-testid={`ar-detail-due-${it.order_id}`}>
                        {it.due_date ? fmtDate(it.due_date) : <span className="text-[#8E8E93]">belum dikirim</span>}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {it.overdue
                          ? <span className="rounded bg-[#FCEBEA] px-1.5 py-0.5 text-[10px] font-bold text-[#C0392B]">telat {it.days_late} hr</span>
                          : <span className="rounded bg-[#E6F6EC] px-1.5 py-0.5 text-[10px] font-bold text-[#1B7F4B]">lancar</span>}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(it.grand_total)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#1B7F4B]">{formatCurrency(it.paid_total)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-bold">{formatCurrency(it.outstanding)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[11px]" data-testid={`ar-detail-split-${it.order_id}`}>
                        <span className="text-[#0058CC]">{formatCurrency(it.ar_ledger || 0)}</span>
                        <span className="text-[#9A9BA3]"> · {formatCurrency(it.exposure || 0)}</span>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#B45309]">{it.denda_estimate > 0 ? formatCurrency(it.denda_estimate) : "—"}</td>
                      <td className="px-3 py-2" data-testid={`ar-detail-penalties-${it.order_id}`}>
                        {(it.penalties || []).length === 0 ? (
                          it.denda_estimate > 0
                            ? <span className="text-[10.5px] font-semibold text-[#9A9BA3]">belum jadi nota</span>
                            : <span className="text-[#C7C7CC]">—</span>
                        ) : (
                          <div className="flex flex-wrap items-center gap-1">
                            {(it.penalties || []).map((p) => {
                              const pm = penaltyMeta(p.status);
                              return (
                                <button key={p.id} type="button"
                                  data-testid={`ar-detail-penalty-${p.id}`}
                                  title={`${p.line_label || ""} · ${formatCurrency(p.amount)}${p.je_number ? ` · jurnal ${p.je_number}` : ""}`}
                                  onClick={() => openTrace({ docType: "penalty", docId: p.id, number: p.number })}
                                  className="rounded px-1.5 py-0.5 text-[9.5px] font-bold hover:underline"
                                  style={{ background: pm.bg, color: pm.fg }}>
                                  {p.number} · {formatCurrency(p.amount)}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Nota denda nyata + keputusannya (terbitkan / ubah / bebaskan / catat bayar) */}
            <div>
              <div className="mb-1.5 flex flex-wrap items-center gap-2">
                <BadgeDollarSign size={14} className="text-[#B45309]" />
                <h3 className="text-[12px] font-bold text-[#1C1C1E]">Nota Denda Pelanggan Ini</h3>
                <span className="text-[10.5px] text-[#6B6B73]">
                  usulan {formatCurrency(t.penalty_draft)} · terbit belum dibayar{" "}
                  {formatCurrency(t.penalty_issued)} · dibebaskan {formatCurrency(t.penalty_waived)}
                </span>
                {(t.denda_undocumented || 0) > 0.01 && (
                  <span className="rounded bg-[#FFF3CD] px-1.5 py-0.5 text-[9.5px] font-bold text-[#8A6D00]"
                    data-testid="ar-aging-undocumented">
                    est. {formatCurrency(t.denda_undocumented)} belum jadi nota
                  </span>
                )}
              </div>
              <PenaltyPanel rows={detail.penalties || []} currentUser={currentUser}
                entityId={detail.entity_id || ""} onChanged={onRefresh} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
