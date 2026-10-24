/** UAT 24 Okt (P7) — menu Perbaikan: roll jadi yang cacat / warnanya meleset diperbaiki, dicelup ulang, atau
 *  di-finishing ulang (internal atau mitra makloon) lalu kembali ke stok dengan biaya dikapitalisasi. */
import { useCallback, useEffect, useState } from "react";
import { Plus, Wrench } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { can } from "../../../config/roles";
import { SearchBox, StatusTabs } from "../../../components/ListControls";
import { formatCurrency, formatDate, formatQty } from "../../../utils/formatters";
import RepairCreateModal from "./RepairCreateModal";
import RepairOrderDetail, { StatusPill } from "./RepairOrderDetail";

const TABS = [["", "Semua"], ["draft", "Draf"], ["sent", "Dikirim"], ["done", "Selesai"], ["cancelled", "Dibatalkan"]];

export default function RepairOrdersView({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [data, setData] = useState({ items: [], counts: {} });
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);
  const [create, setCreate] = useState(false);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/repair-orders`, { params: { status: status || undefined, q: q || undefined } })
      .then((r) => setData(r.data)).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat perbaikan.")).finally(() => setLoading(false));
  }, [status, q]);
  useEffect(() => { const t = setTimeout(load, 200); return () => clearTimeout(t); }, [load, selectedEntity]);
  useEffect(() => {
    if (focusDoc?.focus_type === "repair_order" && focusDoc.focus_id) {
      axios.get(`${API}/repair-orders/${focusDoc.focus_id}`).then((r) => setOpen(r.data)).catch(() => {});
      onClearFocus?.();
    }
  }, [focusDoc, onClearFocus]);
  if (open) return <RepairOrderDetail ro={open} currentUser={currentUser} onBack={() => { setOpen(null); load(); }} onChanged={setOpen} />;
  const total = Object.values(data.counts || {}).reduce((s, n) => s + n, 0);
  return (
    <div className="grid gap-3" data-testid="repair-orders-view">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] text-[#6B6B73]">Roll cacat / warna meleset → perbaikan, celup ulang, atau finishing ulang → kembali ke stok. Selama dikirim, roll tidak bisa dijual.</p>
        {can(currentUser?.permissions, "repair_order", "create") && (
          <button type="button" className="primary-button" onClick={() => setCreate(true)} data-testid="repair-new"><Plus size={13} /> Perbaikan baru</button>)}
      </div>
      <StatusTabs value={status} onChange={setStatus} testIdPrefix="repair-tab"
        tabs={TABS.map(([k, l]) => ({ key: k, label: l, count: k ? data.counts?.[k] || 0 : total }))} />
      <SearchBox value={q} onChange={setQ} placeholder="Cari nomor, mitra, roll, SKU…" testId="repair-search" />
      {err && <p className="text-[11.5px] text-[#A8221A]">{err}</p>}
      {loading ? <div className="loading-state"><p>Memuat…</p></div> : data.items.length === 0 ? (
        <div className="empty-state" data-testid="repair-empty"><Wrench size={28} style={{ opacity: 0.3 }} /><p>Belum ada dokumen perbaikan{status ? " dengan status ini" : ""}.</p></div>
      ) : (
        <div className="table-container">
          <table className="data-table" style={{ minWidth: 820 }}>
            <thead><tr><th>Nomor</th><th>Jenis</th><th>Pelaksana</th><th className="text-right">Roll</th><th className="text-right">Biaya</th><th>Status</th><th>Dibuat</th></tr></thead>
            <tbody>
              {data.items.map((ro) => (
                <tr key={ro.id} className="cursor-pointer" onClick={() => axios.get(`${API}/repair-orders/${ro.id}`).then((r) => setOpen(r.data))} data-testid={`repair-row-${ro.id}`}>
                  <td className="font-mono font-semibold">{ro.number}</td>
                  <td>{ro.kind_label}</td>
                  <td>{ro.partner_name}</td>
                  <td className="text-right tabular-nums">{ro.lines.length} · {formatQty(ro.lines.reduce((s, l) => s + Number(l.qty_sent || 0), 0))}</td>
                  <td className="text-right tabular-nums">{formatCurrency(ro.actual_cost ?? ro.cost_estimate)}</td>
                  <td><StatusPill ro={ro} /></td>
                  <td>{formatDate(ro.created_at)}<span className="block text-[10px] text-[#8E8E93]">{ro.created_by}</span></td>
                </tr>))}
            </tbody>
          </table>
        </div>)}
      {create && <RepairCreateModal onClose={() => setCreate(false)} onCreated={(ro) => { setCreate(false); setOpen(ro); }} />}
    </div>
  );
}
