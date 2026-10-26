import { apiErrorText } from "../../utils/apiError";
import { useState } from "react";
import axios, { API } from "../../services/apiClient";
import { ReceiptText, CheckCircle2, XCircle, Send, Printer } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import ConfirmModal from "../../components/ConfirmModal";
import { STL_STATUS, StatusPill, fmtDate, printSettlement } from "./pettyCashShared";
import { can } from "../../config/roles";

/**
 * SettlementDetail — rincian Laporan Pertanggungjawaban (LPJ) + aksi (ajukan / setujui & posting GL / tolak /
 * bayar reimburse) + cetak.
 *
 * Fase 3 · P4 (L-03/L-07) — dipisah dari SettlementsView; dulu MENGGANTI seluruh halaman (daftar hilang), kini isi
 * pop-up `DetailModal framed` (× di pojok menggantikan tombol "Kembali"). Rincian pengeluaran dulu grid buatan
 * sendiri → `.data-table` di wadah gulir (`table-wrap`). Aksi & testid tidak berubah.
 */
export default function SettlementDetail({ stl, currentUser, entities, catLabels, onChanged, flash }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [reject, setReject] = useState(false);
  const entityName = entities.find((e) => e.id === stl.entity_id)?.short_name || entities.find((e) => e.id === stl.entity_id)?.legal_name || stl.entity_id;

  // Sisir lanjutan gerbang peran (2026-10-21): ajukan/setujui/tolak LPJ = cash_settlement.submit/approve/reject; bayar talangan = accounting.create.
  const canSubmit = stl.status === "draft" && can(currentUser?.permissions, "cash_settlement", "submit");
  const canApprove = ["submitted", "draft"].includes(stl.status) && can(currentUser?.permissions, "cash_settlement", "approve");
  const canReject = ["submitted", "draft"].includes(stl.status) && can(currentUser?.permissions, "cash_settlement", "reject");
  const canPayReimburse = can(currentUser?.permissions, "accounting", "create");
  const sisa = Number(stl.sisa_kurang_dana) || 0;

  async function act(path, body, okMsg) {
    setBusy(true); setErr("");
    try {
      const res = await axios.post(`${API}/cash-advance-settlements/${stl.id}/${path}`, body || {});
      flash(okMsg); onChanged(res.data);
    } catch (e) { setErr(apiErrorText(e, "Aksi gagal.")); } finally { setBusy(false); }
  }

  return (
    <div data-testid="stl-detail" className="grid gap-4">
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <ReceiptText size={15} className="text-[#0058CC]" />
            <h2 data-testid="stl-detail-number">{stl.number}</h2>
            <StatusPill status={stl.status} map={STL_STATUS} testId="stl-detail-status" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button data-testid="stl-print" className="btn-secondary btn-xs" onClick={() => printSettlement(stl, entityName, catLabels)}><Printer size={13} /> Cetak LPJ</button>
            {canSubmit && <button data-testid="stl-submit-btn" className="btn-primary btn-xs" onClick={() => act("submit", {}, `${stl.number} diajukan.`)} disabled={busy}><Send size={13} /> Ajukan</button>}
            {stl.hutang_reimburse?.status === "open" && canPayReimburse && (
              <button data-testid="stl-pay-reimburse-btn" className="btn-primary btn-xs" disabled={busy}
                onClick={() => act("pay-reimburse", { cash_type: "kas_besar" },
                  `Kelebihan LPJ ${stl.number} dibayar ke karyawan (hutang reimburse dilunasi dari kas).`)}>
                <CheckCircle2 size={13} /> Bayar Reimburse Rp {Number(stl.hutang_reimburse.amount || 0).toLocaleString("id-ID")}
              </button>)}
            {stl.hutang_reimburse?.status === "paid" && (
              <span data-testid="stl-reimburse-paid" className="text-[11px] font-semibold text-[#15803D]">
                Reimburse dibayar · {stl.hutang_reimburse.cash_txn_number}</span>)}
            {(canApprove || canReject) && <>
              {canApprove && <button data-testid="stl-approve-btn" className="btn-primary btn-xs" onClick={() => act("approve", {}, `${stl.number} disetujui & diposting ke GL.`)} disabled={busy}><CheckCircle2 size={13} /> Setujui & Posting GL</button>}
              {canReject && <button data-testid="stl-reject-btn" className="btn-danger btn-xs" onClick={() => setReject(true)} disabled={busy}><XCircle size={13} /> Tolak</button>}
            </>}
          </div>
        </div>
        {err && <div className="notice-bar danger mx-3 mb-3" data-testid="stl-detail-error"><span>{err}</span><button onClick={() => setErr("")}>×</button></div>}

        <div className="section-body grid gap-4">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 text-[12px]">
            <Meta k="Ref. PD" v={stl.cash_advance_number || "—"} />
            <Meta k="Entitas" v={entityName} />
            <Meta k="Divisi" v={stl.divisi || "—"} />
            <Meta k="Periode" v={stl.periode || "—"} />
            <Meta k="Dibuat oleh" v={stl.dibuat_oleh || "—"} />
            {stl.journal_entry_number && <Meta k="Jurnal GL" v={stl.journal_entry_number} />}
            {stl.disetujui_oleh && <Meta k="Disetujui" v={stl.disetujui_oleh} />}
            {stl.rejected_reason && <Meta k="Alasan Tolak" v={stl.rejected_reason} danger />}
          </div>

          <div>
            <div className="table-wrap">
              <table className="data-table" data-testid="stl-detail-lines">
                <thead>
                  <tr><th>Tanggal</th><th>Uraian</th><th>Kategori</th><th className="text-right">Nominal</th></tr>
                </thead>
                <tbody>
                  {(stl.expense_lines || []).map((l, i) => (
                    <tr key={i} data-testid={`stl-detail-line-${i}`}>
                      <td className="whitespace-nowrap">{fmtDate(l.date)}</td>
                      <td>{l.description || "—"}</td>
                      <td>{catLabels[l.category] || l.category}</td>
                      <td className="text-right tabular-nums font-semibold">{formatCurrency(l.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Ringkasan di LUAR wadah gulir (P-05): tetap terbaca di HP walau tabel digeser. */}
            <div className="mt-2 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2 grid gap-1">
              <RowLine k="Total Pengeluaran" v={formatCurrency(stl.total_pengeluaran)} testId="stl-detail-total" />
              <RowLine k="Dana Diterima (PD)" v={formatCurrency(stl.total_pettycash)} />
              <RowLine k={sisa >= 0 ? "Sisa Dikembalikan" : "Kekurangan Dana"} v={formatCurrency(Math.abs(sisa))} strong tone={sisa >= 0 ? "#1A7A3A" : "#C62828"} testId="stl-detail-sisa" />
            </div>
          </div>
          {stl.catatan && <p className="text-[12px] text-[#3C3C43]"><b>Catatan:</b> {stl.catatan}</p>}
        </div>
      </section>

      <ConfirmModal open={reject} title={`Tolak ${stl.number}`} message="Berikan alasan penolakan LPJ."
        confirmLabel="Tolak LPJ" danger withReason reasonLabel="Alasan" reasonPlaceholder="mis. Bukti tidak lengkap"
        onConfirm={async (reason) => { setReject(false); await act("reject", { note: reason }, `${stl.number} ditolak.`); }}
        onCancel={() => setReject(false)} testId="stl-reject-modal" />
    </div>
  );
}

function Meta({ k, v, danger }) {
  return (<div className="flex gap-2"><span className="text-[#8E8E93] w-24 shrink-0">{k}</span><span className={`font-semibold min-w-0 break-words ${danger ? "text-red-600" : ""}`}>{v}</span></div>);
}
function RowLine({ k, v, strong, tone, testId }) {
  return (<div className="flex justify-between text-[12px]"><span className="text-[#3C3C43]">{k}</span><span data-testid={testId} className={`tabular-nums ${strong ? "font-bold" : "font-semibold"}`} style={tone ? { color: tone } : {}}>{v}</span></div>);
}
