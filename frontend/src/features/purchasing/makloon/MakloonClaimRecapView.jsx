import { useCallback, useEffect, useState } from "react";
import { Download, Loader2, RefreshCw, Scale } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency, formatQty } from "../../../utils/formatters";

const SETTLE = { potong_bon: "Potong tagihan jasa", tagih_ganti: "Tagih ganti rugi", terima_catatan: "Diterima (catatan)" };
const STATUS = { posted: "Dibukukan", pending_approval: "Menunggu persetujuan", rejected: "Ditolak", approved: "Disetujui" };

function Kpi({ label, value, testId, tone = "" }) {
  return (
    <div className="rounded-xl border border-[#E5E5EA] bg-white px-3 py-2" data-testid={testId}>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      <p className={`text-[15px] font-bold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

/** L01 — Rekap susut, klaim & potongan tagihan per mitra makloon (penagihan & evaluasi). */
export default function MakloonClaimRecapView({ selectedEntity }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [partner, setPartner] = useState("");

  const download = async () => {
    setBusy(true); setErr("");
    try {
      const res = await axios.get(`${API}/makloon-claims/recap.xlsx`, { params: { date_from: from, date_to: to, makloon_id: partner }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `rekap_klaim_mitra_${from || "awal"}_${to || "sekarang"}.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setErr("Gagal mengunduh Excel rekap."); }
    finally { setBusy(false); }
  };

  const load = useCallback(async () => {
    setBusy(true); setErr("");
    try {
      const { data: d } = await axios.get(`${API}/makloon-claims/recap`, { params: { date_from: from, date_to: to, makloon_id: partner } });
      setData(d);
    } catch (e) { setErr(e.response?.data?.detail || "Gagal memuat rekap."); }
    finally { setBusy(false); }
  }, [from, to, partner]);
  useEffect(() => { load(); }, [load, selectedEntity]);

  const [partnerOpts, setPartnerOpts] = useState([]);
  useEffect(() => { if (data && !partner && !from && !to) setPartnerOpts(data.partners || []); }, [data, partner, from, to]);
  const t = data?.totals || {};
  const rows = (data?.rows || []).filter((r) => !partner || r.makloon_id === partner);
  return (
    <section className="space-y-3" data-testid="makloon-claim-recap">
      <div className="flex flex-wrap items-end gap-2">
        <h2 className="mr-auto flex items-center gap-2 text-[15px] font-bold"><Scale size={16} /> Rekap Susut & Klaim Mitra</h2>
        <label className="text-[11px]">Dari<input type="date" className="field ml-1 !py-1" value={from} onChange={(e) => setFrom(e.target.value)} data-testid="recap-from" /></label>
        <label className="text-[11px]">Sampai<input type="date" className="field ml-1 !py-1" value={to} onChange={(e) => setTo(e.target.value)} data-testid="recap-to" /></label>
        <select className="field !w-auto !py-1 text-[12px]" value={partner} onChange={(e) => setPartner(e.target.value)} data-testid="recap-partner">
          <option value="">Semua mitra</option>
          {partnerOpts.map((p) => <option key={p.makloon_id} value={p.makloon_id}>{p.makloon_name}</option>)}
        </select>
        <button className="secondary-button !py-1.5 text-[12px]" onClick={download} disabled={busy} data-testid="recap-download-xlsx">
          <Download size={13} /> Unduh Excel
        </button>
        <button className="secondary-button !py-1.5 text-[12px]" onClick={load} disabled={busy} data-testid="recap-reload">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} Muat ulang
        </button>
      </div>
      {err && <p className="text-[12px] text-[#C0392B]" data-testid="recap-error">{err}</p>}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        <Kpi label="Beban susut wajar" value={formatCurrency(t.loss_expense || 0)} testId="recap-kpi-expense" />
        <Kpi label="Piutang klaim mitra" value={formatCurrency(t.receivable_total || 0)} testId="recap-kpi-receivable" tone="text-[#A8221A]" />
        <Kpi label="Dipotong dari tagihan" value={formatCurrency(t.deducted_total || 0)} testId="recap-kpi-deducted" tone="text-[#0A7A3B]" />
        <Kpi label="Susut menunggu" value={t.loss_pending || 0} testId="recap-kpi-loss-pending" />
        <Kpi label="Klaim selisih menunggu" value={t.variance_pending || 0} testId="recap-kpi-variance-pending" />
      </div>
      <div className="overflow-x-auto rounded-xl border border-[#E5E5EA] bg-white">
        <table className="w-full text-[12px]" data-testid="recap-partner-table">
          <thead className="bg-[#F7F7F9] text-left text-[10.5px] uppercase text-[#8E8E93]">
            <tr><th className="px-3 py-2">Mitra</th><th className="px-3 py-2 text-right">Kejadian susut</th><th className="px-3 py-2 text-right">Qty susut</th>
              <th className="px-3 py-2 text-right">Beban wajar</th><th className="px-3 py-2 text-right">Piutang klaim</th><th className="px-3 py-2 text-right">Dipotong tagihan</th>
              <th className="px-3 py-2 text-right">Klaim selisih</th><th className="px-3 py-2 text-right">Menunggu</th></tr>
          </thead>
          <tbody>
            {(data?.partners || []).filter((p) => !partner || p.makloon_id === partner).map((p) => (
              <tr key={p.makloon_id} className="border-t border-[#F0F0F3]" data-testid={`recap-partner-${p.makloon_id}`}>
                <td className="px-3 py-2 font-semibold">{p.makloon_name}</td>
                <td className="px-3 py-2 text-right tabular-nums">{p.loss_events}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatQty(p.loss_qty)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(p.loss_expense)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-[#A8221A]">{formatCurrency(p.receivable_total)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-[#0A7A3B]">{formatCurrency(p.deducted_total)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{p.variance_claims} · {formatCurrency(p.variance_claim_amount)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{p.loss_pending + p.variance_pending}</td>
              </tr>
            ))}
            {data && !(data.partners || []).length && <tr><td colSpan={8} className="px-3 py-6 text-center text-[#8E8E93]" data-testid="recap-empty">Belum ada susut atau klaim mitra pada periode ini.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="overflow-x-auto rounded-xl border border-[#E5E5EA] bg-white">
        <table className="w-full text-[11.5px]" data-testid="recap-rows-table">
          <thead className="bg-[#F7F7F9] text-left text-[10.5px] uppercase text-[#8E8E93]">
            <tr><th className="px-3 py-2">Tanggal</th><th className="px-3 py-2">Jenis</th><th className="px-3 py-2">MKO</th><th className="px-3 py-2">Mitra</th>
              <th className="px-3 py-2 text-right">Qty</th><th className="px-3 py-2 text-right">Beban</th><th className="px-3 py-2 text-right">Klaim</th>
              <th className="px-3 py-2">Penyelesaian</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Alasan</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.mko_id}-${r.step_seq}-${i}`} className="border-t border-[#F0F0F3]" data-testid={`recap-row-${i}`}>
                <td className="px-3 py-1.5">{(r.at || "").slice(0, 10)}</td>
                <td className="px-3 py-1.5">{r.kind === "susut" ? "Susut/hilang" : "Selisih hasil"}</td>
                <td className="px-3 py-1.5 font-semibold">{r.mko_number} · L{r.step_seq}</td>
                <td className="px-3 py-1.5">{r.makloon_name}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{r.qty != null ? `${formatQty(r.qty)} ${r.unit}` : "—"}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{formatCurrency(r.expense || 0)}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{formatCurrency(r.claim || 0)}</td>
                <td className="px-3 py-1.5">{SETTLE[r.settle] || "—"}</td>
                <td className="px-3 py-1.5">{STATUS[r.status] || r.status}</td>
                <td className="max-w-[260px] truncate px-3 py-1.5" title={r.reason}>{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
