import { useCallback, useEffect, useState } from "react";
import { Scissors, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import SampleRequestForm from "./SampleRequestForm";
import SamplePriceMaster from "./SamplePriceMaster";

const STATUS = { requested: ["Menunggu potong", "pill-warning"], done: ["Selesai", "pill-success"], cancelled: ["Dibatalkan", "pill-muted"] };

export default function SampleSalesView({ currentUser }) {
  const [rows, setRows] = useState(null); const [err, setErr] = useState("");
  const canEditPrice = ["admin", "manager"].includes(currentUser?.role);
  const canRequest = ["admin", "sales", "manager"].includes(currentUser?.role);
  const load = useCallback(() => axios.get(`${API}/sample-requests`).then((r) => { setRows(r.data || []); setErr(""); }).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat permintaan sampel.")), []);
  useEffect(() => { load(); }, [load]);
  const cancel = async (r) => { try { await axios.post(`${API}/sample-requests/${r.id}/cancel`, { reason: "dibatalkan dari layar" }); load(); } catch (e) { setErr(e.response?.data?.detail || "Gagal membatalkan."); } };
  return (
    <div className="space-y-4" data-testid="sample-sales-view">
      <div className="grid gap-4 lg:grid-cols-3">
        {canRequest && (
          <div className="section-card lg:col-span-1">
            <div className="section-head"><h2 className="font-bold text-[14px] flex items-center gap-2"><Scissors size={16} /> Ajukan Sampel</h2></div>
            <div className="section-body"><SampleRequestForm onSubmitted={load} /></div>
          </div>
        )}
        <div className={`section-card ${canRequest ? "lg:col-span-2" : "lg:col-span-3"}`}>
          <div className="section-head flex items-center justify-between"><h2 className="font-bold text-[14px]">Permintaan Sampel</h2>
            <button className="icon-button" onClick={load} aria-label="Muat ulang" data-testid="sample-refresh"><RefreshCw size={14} /></button></div>
          <div className="section-body">
            {err && <div className="notice-bar danger" data-testid="sample-list-error">{String(err)}</div>}
            {rows === null ? <div className="py-8 text-center text-[12px] text-[#6B6B73] animate-pulse" data-testid="sample-list-loading">Memuat…</div>
              : rows.length === 0 ? <div className="py-10 text-center text-[12px] text-[#6B6B73]" data-testid="sample-list-empty">Belum ada permintaan sampel. Ajukan lewat form di kiri atau dari HP sales.</div>
              : (
                <table className="data-table text-[12px]" data-testid="sample-list">
                  <thead><tr><th>Nomor</th><th>Pelanggan</th><th>Produk</th><th className="text-right">Panjang</th><th className="text-right">Nilai</th><th>Roll</th><th>Status</th><th>SO / Kwitansi</th><th /></tr></thead>
                  <tbody>{rows.map((r) => { const [lbl, cls] = STATUS[r.status] || [r.status, ""]; return (
                    <tr key={r.id} data-testid={`sample-row-${r.id}`}>
                      <td className="font-mono">{r.number}</td><td>{r.customer_name}</td><td>{r.product_name}</td>
                      <td className="text-right tabular-nums">{r.length} {r.unit}</td><td className="text-right tabular-nums">{formatCurrency(r.amount)}</td>
                      <td className="text-[11px]">{r.status === "done" ? <>{r.cut_roll_no} → <b>{r.child_roll_no}</b>{r.off_suggestion_reason ? <span className="text-[#B7791F]"> · bukan saran: {r.off_suggestion_reason}</span> : null}</> : <>saran FIFO {r.suggested_roll_no || "—"}</>}</td>
                      <td><span className={`status-pill ${cls}`}>{lbl}</span></td>
                      <td className="text-[11px]">{r.sales_order_number || "—"}{r.receipt_number ? ` / ${r.receipt_number}` : r.receipt_error ? <span className="text-[#C0392B]"> / kwitansi gagal</span> : ""}</td>
                      <td>{r.status === "requested" && canRequest && <button className="secondary-button btn-xs" onClick={() => cancel(r)} data-testid={`sample-cancel-${r.id}`}>Batal</button>}</td>
                    </tr>); })}</tbody>
                </table>
              )}
          </div>
        </div>
      </div>
      <SamplePriceMaster canEdit={canEditPrice} />
    </div>
  );
}
