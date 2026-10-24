/** UAT 24 Okt (P7) — rincian Perbaikan: kirim (roll keluar dari stok jual), terima hasil (qty hasil = susut, grade &
 *  dye lot baru, biaya aktual dikapitalisasi), batal. */
import { useState } from "react";
import { PackageCheck, Send, Wrench, XCircle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { askReason } from "@/services/confirmService";
import { can } from "../../../config/roles";
import { DetailHeader, Panel, Cell } from "../../../components/DetailParts";
import KNSelect from "../../../components/KNSelect";
import useDomainEnums from "../../../hooks/useDomainEnums";
import { formatCurrency, formatDateTime, formatQty } from "../../../utils/formatters";
import { openTrace } from "../../documents/trace/traceDeepLink";

const TONE = { draft: "bg-[#F1F2F4] text-[#4A4B52]", sent: "bg-[#FFF4E5] text-[#B45309]", done: "bg-[#E9F7EF] text-[#1B7F4B]", cancelled: "bg-[#FDECEC] text-[#9B1C1C]" };
const BASIS = { per_unit: "per satuan", per_roll: "per roll", lumpsum: "borongan" };

export function StatusPill({ ro }) {
  return <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-bold ${TONE[ro.status] || ""}`} data-testid={`repair-status-${ro.id}`}>{ro.status_label || ro.status}</span>;
}

export default function RepairOrderDetail({ ro, currentUser, onBack, onChanged }) {
  const perms = currentUser?.permissions;
  const { options } = useDomainEnums();
  const [recv, setRecv] = useState(null);   // { roll_id: {qty_out, grade, dye_lot} }
  const [cost, setCost] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const run = async (fn) => {
    setBusy(true); setErr("");
    try { onChanged?.((await fn()).data); setRecv(null); } catch (e) { setErr(e.response?.data?.detail || "Gagal."); } finally { setBusy(false); }
  };
  const startRecv = () => {
    setCost(String(ro.cost_estimate || 0));
    setRecv(Object.fromEntries(ro.lines.map((ln) => [ln.roll_id, { qty_out: String(ln.qty_sent), grade: ln.grade_before || "A", dye_lot: ro.target?.dye_lot || "" }])));
  };
  const cancel = async () => {
    const reason = await askReason({ title: `Batalkan ${ro.number}?`, message: ro.status === "sent" ? "Roll kembali ke status semula." : "", danger: true });
    if (reason) run(() => axios.post(`${API}/repair-orders/${ro.id}/cancel`, { reason }));
  };
  const totalSent = ro.lines.reduce((s, ln) => s + Number(ln.qty_sent || 0), 0);
  return (
    <div className="grid gap-3" data-testid="repair-detail">
      <DetailHeader onBack={onBack} backLabel="Kembali ke daftar Perbaikan" backTestId="repair-back" icon={Wrench} title={ro.number} titleTestId="repair-number"
        badges={<StatusPill ro={ro} />}
        subtitle={`${ro.kind_label} · ${ro.partner_name}${ro.target?.color_name ? ` · warna tujuan ${ro.target.color_name}` : ""}${ro.target?.product_sku ? ` → SKU ${ro.target.product_sku}` : ""}`}
        actions={<div className="flex flex-wrap gap-2">
          {ro.status === "draft" && can(perms, "repair_order", "send") && (
            <button type="button" className="primary-button" disabled={busy} onClick={() => run(() => axios.post(`${API}/repair-orders/${ro.id}/send`))} data-testid="repair-send"><Send size={13} /> Kirim — roll keluar dari stok</button>)}
          {ro.status === "sent" && can(perms, "repair_order", "receive") && !recv && (
            <button type="button" className="primary-button" onClick={startRecv} data-testid="repair-receive-open"><PackageCheck size={13} /> Terima hasil</button>)}
          {["draft", "sent"].includes(ro.status) && can(perms, "repair_order", "cancel") && (
            <button type="button" className="secondary-button" disabled={busy} onClick={cancel} data-testid="repair-cancel"><XCircle size={13} /> Batalkan</button>)}
          <button type="button" className="secondary-button" onClick={() => openTrace({ docType: "repair_order", docId: ro.id, number: ro.number })}>Jejak Dokumen</button>
        </div>} />
      {err && <p className="rounded-lg bg-[#FDECEC] px-3 py-2 text-[11.5px] text-[#9B1C1C]" data-testid="repair-error">{err}</p>}
      <div className="grid gap-2 sm:grid-cols-4">
        <Cell label="Roll">{ro.lines.length} · {formatQty(totalSent)}</Cell>
        <Cell label="Biaya" sub={`${BASIS[ro.cost?.basis] || ""} ${ro.cost?.rate ? formatCurrency(ro.cost.rate) : ""}`}>{formatCurrency(ro.actual_cost ?? ro.cost_estimate)}{ro.actual_cost == null ? " (perkiraan)" : ""}</Cell>
        <Cell label="Susut">{ro.total_shrink != null ? formatQty(ro.total_shrink) : "—"}</Cell>
        <Cell label="Jurnal kapitalisasi">{ro.journal_number || "—"}</Cell>
      </div>
      <Panel title="Roll" testId="repair-lines">
        <div className="table-container overflow-x-auto">
          <table className="data-table !text-[11.5px]">
            <thead><tr><th>Roll</th><th>Barang</th><th className="text-right">Dikirim</th><th>Grade / lot awal</th>
              {(recv || ro.status === "done") && <><th className="text-right">Hasil</th><th>Grade baru</th><th>Dye lot baru</th></>}
              {ro.status === "done" && <><th className="text-right">Susut</th><th>Roll hasil</th></>}</tr></thead>
            <tbody>
              {ro.lines.map((ln) => (
                <tr key={ln.roll_id} data-testid={`repair-line-${ln.roll_id}`}>
                  <td className="font-mono font-semibold">{ln.roll_no}</td>
                  <td>{ln.sku}<span className="block text-[10px] text-[#6B6B73]">{ln.product_name}</span></td>
                  <td className="text-right tabular-nums">{formatQty(ln.qty_sent)} {ln.unit}</td>
                  <td>{ln.grade_before || "-"} · {ln.lot_before || "-"}</td>
                  {recv && (<>
                    <td className="text-right"><input type="number" min="0" className="field !w-24 text-right" value={recv[ln.roll_id].qty_out} data-testid={`repair-recv-qty-${ln.roll_id}`}
                      onChange={(e) => setRecv((x) => ({ ...x, [ln.roll_id]: { ...x[ln.roll_id], qty_out: e.target.value } }))} /></td>
                    <td className="min-w-[90px]"><KNSelect value={recv[ln.roll_id].grade} options={options("grade")} searchable={false} data-testid={`repair-recv-grade-${ln.roll_id}`}
                      onValueChange={(v) => setRecv((x) => ({ ...x, [ln.roll_id]: { ...x[ln.roll_id], grade: v } }))} /></td>
                    <td><input className="field !w-28" value={recv[ln.roll_id].dye_lot} placeholder={ln.lot_before || "lot"} data-testid={`repair-recv-lot-${ln.roll_id}`}
                      onChange={(e) => setRecv((x) => ({ ...x, [ln.roll_id]: { ...x[ln.roll_id], dye_lot: e.target.value } }))} /></td>
                  </>)}
                  {!recv && ro.status === "done" && (<>
                    <td className="text-right tabular-nums">{formatQty(ln.qty_out)}</td><td>{ln.grade_after}</td><td>{ln.lot_after}</td>
                    <td className="text-right tabular-nums">{formatQty(ln.shrink)}</td>
                    <td className="font-mono">{ln.result_roll_no}{ln.result_product_id && ln.result_product_id !== ln.product_id ? " (SKU baru)" : ""}</td>
                  </>)}
                </tr>))}
            </tbody>
          </table>
        </div>
        {recv && (
          <div className="mt-3 flex flex-wrap items-end gap-2" data-testid="repair-receive-form">
            <label><span className="field-label">Biaya aktual (Rp)</span>
              <input type="number" min="0" className="field !w-44" value={cost} onChange={(e) => setCost(e.target.value)} data-testid="repair-recv-cost" /></label>
            <button type="button" className="primary-button" disabled={busy} data-testid="repair-receive-submit"
              onClick={() => run(() => axios.post(`${API}/repair-orders/${ro.id}/receive`, {
                actual_cost: cost === "" ? null : Number(cost),
                lines: ro.lines.map((ln) => ({ roll_id: ln.roll_id, qty_out: Number(recv[ln.roll_id].qty_out || 0), grade: recv[ln.roll_id].grade, dye_lot: recv[ln.roll_id].dye_lot })) }))}>
              <PackageCheck size={13} /> Simpan hasil &amp; kembalikan ke stok</button>
            <button type="button" className="secondary-button" onClick={() => setRecv(null)}>Batal</button>
            <p className="w-full text-[10.5px] text-[#6B6B73]">Selisih dikirim − hasil dicatat sebagai susut. Biaya dikapitalisasi ke roll hasil sebanding qty hasil.</p>
          </div>)}
      </Panel>
      <Panel title="Riwayat" testId="repair-timeline">
        <ol className="grid gap-1 text-[11px]">{[...(ro.timeline || [])].reverse().map((t, i) => (
          <li key={i} className="flex gap-2"><span className="w-36 shrink-0 text-[#8E8E93]">{formatDateTime(t.at)}</span><span>{t.note}{t.by ? ` · ${t.by}` : ""}</span></li>))}</ol>
        {ro.notes && <p className="mt-2 text-[11px] text-[#3C3C43]">Catatan: {ro.notes}</p>}
      </Panel>
    </div>
  );
}
