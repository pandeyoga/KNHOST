/** UAT 24 Okt (P7) — menu Perbaikan: roll jadi yang cacat / warnanya meleset diperbaiki, dicelup ulang, atau
 *  di-finishing ulang (internal atau mitra makloon) lalu kembali ke stok dengan biaya dikapitalisasi. */
import { useCallback, useEffect, useState } from "react";
import { Plus, Wrench } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { can } from "../../../config/roles";
import { SearchBox } from "../../../components/ListControls";
import { PageHeader } from "../../../components/ListPageParts";
import FilterChips from "../../../components/FilterChips";
import ResponsiveTable from "../../../components/ResponsiveTable";
import { formatCurrency, formatDate, formatQty } from "../../../utils/formatters";
import RepairCreateModal from "./RepairCreateModal";
import RepairOrderDetail, { StatusPill } from "./RepairOrderDetail";

const TABS = [["", "Semua"], ["draft", "Draf"], ["sent", "Dikirim"], ["done", "Selesai"], ["cancelled", "Dibatalkan"]];

// Fase 4 · R3 (L-02/L-07) — kepala = PageHeader baku (dulu satu kalimat tanpa judul); status = FilterChips (saringan,
// bukan tab; testid `repair-tab-*` tetap); tabel min 820 px → ResponsiveTable (kartu di HP; testid `repair-row-<id>` tetap).
const COLUMNS = [
  { key: "number", header: "Nomor", mobile: "title", className: "font-mono font-semibold" },
  { key: "status", header: "Status", mobile: "badge", render: (ro) => <StatusPill ro={ro} /> },
  { key: "kind_label", header: "Jenis", mobile: "subtitle" },
  { key: "partner_name", header: "Pelaksana", priority: 1 },
  { key: "rolls", header: "Roll", align: "right", priority: 2, className: "tabular-nums",
    render: (ro) => `${ro.lines.length} · ${formatQty(ro.lines.reduce((s, l) => s + Number(l.qty_sent || 0), 0))}` },
  { key: "cost", header: "Biaya", align: "right", priority: 3, className: "tabular-nums",
    render: (ro) => formatCurrency(ro.actual_cost ?? ro.cost_estimate) },
  { key: "created_at", header: "Dibuat", priority: 4,
    render: (ro) => <>{formatDate(ro.created_at)}<span className="block text-[10px] text-[#8E8E93]">{ro.created_by}</span></> },
];

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
      <PageHeader icon={Wrench} title="Perbaikan" testId="repair-header"
        subtitle="Roll cacat / warna meleset → perbaikan, celup ulang, atau finishing ulang → kembali ke stok. Selama dikirim, roll tidak bisa dijual."
        actions={can(currentUser?.permissions, "repair_order", "create") && (
          <button type="button" className="primary-button" onClick={() => setCreate(true)} data-testid="repair-new"><Plus size={13} /> Perbaikan baru</button>)} />
      <section className="section-card section-pad grid gap-3">
        <FilterChips value={status} onChange={setStatus} testId="repair-tab" ariaLabel="Status perbaikan"
          options={TABS.map(([k, l]) => ({ key: k, label: l, count: k ? data.counts?.[k] || 0 : total, testId: `repair-tab-${k || "all"}` }))} />
        <SearchBox value={q} onChange={setQ} placeholder="Cari nomor, mitra, roll, SKU…" testId="repair-search" />
        {err && <p className="text-[11.5px] text-[#A8221A]">{err}</p>}
        {!loading && data.items.length === 0 ? (
          <div className="empty-state" data-testid="repair-empty"><Wrench size={28} style={{ opacity: 0.3 }} /><p>Belum ada dokumen perbaikan{status ? " dengan status ini" : ""}.</p></div>
        ) : (
          <ResponsiveTable testId="repair" rows={loading ? [] : data.items} loading={loading} columns={COLUMNS}
            onRowClick={(ro) => axios.get(`${API}/repair-orders/${ro.id}`).then((r) => setOpen(r.data))} />
        )}
      </section>
      {create && <RepairCreateModal onClose={() => setCreate(false)} onCreated={(ro) => { setCreate(false); setOpen(ro); }} />}
    </div>
  );
}
