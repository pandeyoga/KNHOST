/**
 * JournalDetailModal — rincian satu jurnal (diklik dari tab Jurnal di GeneralLedger).
 *
 * Fase 4 · R2 (L-03) — diekstrak dari `GeneralLedger.jsx`; `div fixed inset-0` buatan sendiri → `DetailModal`
 * framed (Esc lewat tumpukan lapisan, klik latar gestur utuh, layar penuh di HP).
 *  · "Anulir Jurnal" dulu langsung memanggil API tanpa bertanya → kini `askConfirm` (danger).
 *  · Galat anulir dulu dilempar ke bilah galat HALAMAN (di belakang pop-up, tak terlihat) → kini tampil di DALAM
 *    pop-up (`gl-journal-detail-error`).
 * Testid lama tetap: `gl-journal-detail`, `gl-journal-detail-close`, `gl-reverse-*`, `gl-print-*`, `gl-journal-void`,
 * `gl-journal-reverse`, `gl-journal-back-to-trace`.
 */
import { useState } from "react";
import { ArrowLeftRight, FileStack, Printer, X } from "lucide-react";
import DetailModal from "../../components/DetailModal";
import ErrorNotice from "../../components/ErrorNotice";
import KNDatePicker from "../../components/KNDatePicker";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { printPaymentVoucher, printReceivedVoucher } from "../../utils/docPrint";
import { formatCurrency, formatDate, todayWib } from "../../utils/formatters";
import { openTrace } from "../documents/trace/traceDeepLink";

export default function JournalDetailModal({ je, sourceMeta, entities = [], selectedEntity, onClose, onVoid, onReverse }) {
  const [revOpen, setRevOpen] = useState(false);
  const [revDate, setRevDate] = useState(todayWib());
  const [revReason, setRevReason] = useState("");
  const [revBusy, setRevBusy] = useState(false);
  const [revErr, setRevErr] = useState("");
  const [voidBusy, setVoidBusy] = useState(false);
  const [err, setErr] = useState("");
  const sm = sourceMeta(je.source_type);
  const entId = je.entity_id || (selectedEntity && selectedEntity !== "all" ? selectedEntity : "");
  const ent = entities.find((e) => e.id === entId);
  const entityName = ent?.short_name || ent?.legal_name || "";
  // G1-26 — arah kas dari baris akun kas/bank (1-11xx): debit = kas masuk, kredit = kas keluar.
  const cashLines = (je.lines || []).filter((l) => String(l.account_code || "").startsWith("1-11"));
  const cashIn = cashLines.reduce((a, l) => a + Number(l.debit || 0), 0);
  const cashOut = cashLines.reduce((a, l) => a + Number(l.credit || 0), 0);
  const cashDir = cashIn > 0 && cashOut <= 0 ? "in" : cashOut > 0 && cashIn <= 0 ? "out" : "";

  const doVoid = async () => {
    if (!(await askConfirm({
      title: `Anulir jurnal ${je.number}?`,
      message: "Jurnal manual ini ditandai Anulir dan tidak lagi dihitung di buku besar.",
      confirmLabel: "Anulir Jurnal",
      danger: true,
    }))) return;
    setVoidBusy(true); setErr("");
    try { await onVoid(je); } catch (e) { setErr(apiErrorText(e, "Gagal void jurnal.")); } finally { setVoidBusy(false); }
  };

  return (
    <DetailModal open onClose={onClose} framed showClose={false} size="md" label={`Jurnal ${je.number}`}
      testId="gl-journal-detail">
      <div className="sticky -top-4 z-10 -mx-4 -mt-4 mb-3 flex items-center gap-2 border-b border-[#EFF0F2] bg-white px-4 py-3">
        <FileStack size={16} className="shrink-0 text-[#0058CC]" />
        <h3 className="min-w-0 font-bold text-[14px]">Jurnal <span className="font-mono tabular-nums text-[#6B6B73]">{je.number}</span></h3>
        <span className={`text-[10px] font-bold rounded px-1.5 py-0.5 ${sm.tone}`}>{sm.label}</span>
        <button type="button" data-testid="gl-journal-detail-close" className="icon-button ml-auto" onClick={onClose} aria-label="Tutup"><X size={15} /></button>
      </div>

      <ErrorNotice message={err} onDismiss={() => setErr("")} testId="gl-journal-detail-error" />
      <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[12px] text-[#6B6B73]">
        <span className="min-w-0">{formatDate(je.date)} · {je.description}</span>
        <span>oleh {je.created_by}</span>
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Akun</th>
              <th className="text-right">Debit</th>
              <th className="text-right">Kredit</th>
            </tr>
          </thead>
          <tbody>
            {(je.lines || []).map((l, i) => (
              <tr key={i}>
                <td><span className="font-mono text-[11px] text-[#9A9BA3]">{l.account_code}</span> {l.account_name}{l.description ? <span className="block text-[10px] text-[#9A9BA3]">{l.description}</span> : null}</td>
                <td className="text-right tabular-nums">{l.debit > 0 ? formatCurrency(l.debit) : "—"}</td>
                <td className="text-right tabular-nums">{l.credit > 0 ? formatCurrency(l.credit) : "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="font-bold">
              <td className="text-right text-[11px]">Total</td>
              <td className="text-right tabular-nums">{formatCurrency(je.total_debit)}</td>
              <td className="text-right tabular-nums">{formatCurrency(je.total_credit)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {je.reversed_by_entry_id && (
        <p data-testid="gl-journal-reversed-note" className="mt-2 text-[12px] font-semibold text-[#0058CC]">
          Sudah dibalik oleh {je.reversed_by_entry_number || je.reversed_by_entry_id} · {je.reversal_reason}</p>)}
      {je.ref?.reverses_entry_number && (
        <p data-testid="gl-journal-reverses-note" className="mt-2 text-[12px] font-semibold text-[#0058CC]">
          Jurnal pembalik atas {je.ref.reverses_entry_number} · {je.ref.reason}</p>)}
      {revOpen && (
        <div data-testid="gl-reverse-form" className="mt-3 grid gap-2 rounded-lg border border-[#D6E4FF] bg-[#F5F9FF] p-3 text-[12px]">
          <p className="font-bold">Jurnal pembalik (debit ↔ kredit) — tanggal wajib di periode terbuka; jurnal asli tidak diubah.</p>
          <KNDatePicker data-testid="gl-reverse-date" clearable={false} value={revDate} onChange={setRevDate} />
          <textarea data-testid="gl-reverse-reason" className="field" rows={2} placeholder="Alasan pembalikan (wajib, minimal 5 huruf)"
            value={revReason} onChange={(e) => setRevReason(e.target.value)} />
          {revErr && <ErrorNotice message={revErr} onDismiss={() => setRevErr("")} testId="gl-reverse-error" />}
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" className="secondary-button" onClick={() => setRevOpen(false)}>Batal</button>
            <button type="button" data-testid="gl-reverse-submit" className="primary-button"
              disabled={revBusy || !revDate || revReason.trim().length < 5 /* K-14 — seragam 5 huruf */}
              onClick={async () => {
                setRevBusy(true); setRevErr("");
                try { await onReverse(je, revDate, revReason); } catch (e) { setRevErr(apiErrorText(e, "Gagal membalik jurnal.")); } finally { setRevBusy(false); }
              }}>Buat Jurnal Pembalik</button>
          </div>
        </div>)}

      <div className="sticky -bottom-4 z-10 -mx-4 -mb-4 mt-4 flex flex-wrap justify-end gap-2 border-t border-[#EFF0F2] bg-[#FAFBFC] px-4 py-3">
        {je._from_trace?.docId && (
          <button type="button" data-testid="gl-journal-back-to-trace" className="secondary-button mr-auto"
            onClick={() => { onClose(); openTrace(je._from_trace); }}>
            <ArrowLeftRight size={13} /> Kembali ke Jejak {je._from_trace.number || ""}
          </button>
        )}
        {/* G1-26 — hanya bukti kas yang sesuai arah kas jurnal ini (dulu "Payment Voucher" & "Received Voucher"
            selalu tampil berdua, juga untuk jurnal kas masuk). Arah tak jelas → keduanya. */}
        {cashDir !== "in" && (
          <button type="button" data-testid="gl-print-payment-voucher" className="secondary-button" onClick={() => printPaymentVoucher(je, entityName)}><Printer size={13} /> Bukti Kas Keluar</button>
        )}
        {cashDir !== "out" && (
          <button type="button" data-testid="gl-print-received-voucher" className="secondary-button" onClick={() => printReceivedVoucher(je, entityName)}><Printer size={13} /> Bukti Kas Masuk</button>
        )}
        {je.source_type === "manual" && je.status !== "void" && (
          <button type="button" data-testid="gl-journal-void" className="secondary-button !text-[#C0392B]" disabled={voidBusy} onClick={doVoid}>Anulir Jurnal</button>
        )}
        {je.status !== "void" && !je.reversed_by_entry_id && !["closing", "reversal"].includes(je.source_type) && onReverse && (
          <button type="button" data-testid="gl-journal-reverse" className="secondary-button" onClick={() => setRevOpen(true)}>Balik Jurnal</button>
        )}
        <button type="button" className="primary-button" onClick={onClose}>Tutup</button>
      </div>
    </DetailModal>
  );
}
