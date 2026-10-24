import { can, roleLabel } from "../../config/roles";
import { useEffect, useState } from "react";
import { Inbox, Gauge, Monitor, Loader2, ClipboardList, Bell, Sparkles, LayoutGrid } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import TanyaKnView from "../tanya/TanyaKnView";
import MobileShell from "./MobileShell";
import MobileApprovalInbox from "./MobileApprovalInbox";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { formatUnitTotals } from "../../utils/qtyByUnit";
import { actorLabel } from "../../utils/actorLabel";

// Audit UI HP (manager) — status/tahap mentah di teks notifikasi ("tahap: pending_approval") → label Indonesia.
const STAGE_LABEL = {
  pending_approval: "menunggu persetujuan", pending: "menunggu", approved: "disetujui", rejected: "ditolak",
  draft: "draf", submitted: "diajukan", in_review: "ditinjau", inspecting: "diperiksa", received: "diterima",
  completed: "selesai", done: "selesai", cancelled: "dibatalkan", waiting_stock: "menunggu stok",
};
const humanizeNotif = (text) => String(text || "")
  .replace(/\b(tahap|status):\s*([a-z][a-z_]+)/g, (m, k, code) => `${k}: ${STAGE_LABEL[code] || code.replace(/_/g, " ")}`)
  .replace(/\bAvailable\b/g, "Tersedia");

function QueuePanel() {
  const [q, setQ] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { axios.get(`${API}/approvals/my-queue`).then((r) => setQ(r.data)).catch((e) => setErr(e.response?.data?.detail || "Antrean tidak bisa dimuat.")); }, []);
  if (err) return <div className="notice-bar danger m-4" data-testid="mo-queue-error">{String(err)}</div>;
  if (!q) return <div className="p-6 text-center text-sm"><Loader2 className="animate-spin inline" size={16} /> Memuat…</div>;
  const items = q.items || q.queue || [];
  if (!items.length) return <div className="p-8 text-center text-sm text-[#6E6E73]" data-testid="mo-queue-empty">Tidak ada persetujuan yang menunggu Anda.</div>;
  return (
    <div className="space-y-2 p-3" data-testid="mo-queue-list">
      {items.map((it, i) => (
        <div key={it.id || i} className="m-card p-3" data-testid={`mo-queue-${it.id || i}`}>
          <div className="flex justify-between"><b>{it.doc_number || it.number || it.title || it.stage_label || it.stage}</b><span className="status-pill pill-warning">{it.stage_label || STAGE_LABEL[it.stage] || it.stage || "menunggu"}</span></div>
          {/* Audit UI 24 Okt (HP manager › Antrean) — titik yatim "· Rp 0" & akun teknis ("system-seed") tidak tampil. */}
          <div className="text-xs text-[#6E6E73] mt-1">{[it.customer_name || actorLabel(it.requester_name || it.requester, ""), Number(it.amount) > 0 ? formatCurrency(it.amount) : ""].filter(Boolean).join(" · ")}</div>
        </div>
      ))}
      <p className="text-xs text-[#6E6E73] px-1">Harga khusus & pesanan khusus bisa diputuskan di tab Persetujuan; dokumen lain di tampilan desktop.</p>
    </div>
  );
}

function DesktopPanel({ role, onForceDesktop }) {
  return (
    <div className="p-6 text-center space-y-3" data-testid="mo-desktop">
      <p className="text-sm">Layar lengkap untuk <b>{roleLabel(role)}</b> tersedia di tampilan desktop.</p>
      <button className="primary-button w-full py-4" onClick={onForceDesktop} data-testid="mo-open-desktop">Buka Tampilan Desktop</button>
    </div>
  );
}

function KpiPanel({ desktop }) {
  const [d, setD] = useState(null);
  useEffect(() => { axios.get(`${API}/dashboard`).then((r) => setD(r.data)).catch(() => setD({})); }, []);
  if (!d) return <div className="p-6 text-center text-sm">Memuat…</div>;
  // Audit UI HP (manager/Ringkas) — dulu menampilkan kunci mentah tingkat atas ("expired released 0");
  // angka ringkas sebenarnya ada di `metrics`. Label Indonesia + satuan per kg/yard.
  const m = d.metrics || {};
  const nums = [
    ["Pesanan aktif", m.active_orders, "pesanan"],
    ["Stok tersedia", m.available_by_unit ? formatUnitTotals(m.available_by_unit, m.available_qty) : null],
    ["Stok dipesan", m.reserved_by_unit ? formatUnitTotals(m.reserved_by_unit, m.reserved_qty) : null],
    ["Roll tersedia", m.available_rolls, "roll"],
    ["Produk", m.products, "SKU"],
    ["Pelanggan", m.customers, "pelanggan"],
    ["Gudang", m.warehouses, "gudang"],
    ["Reservasi kedaluwarsa dilepas", d.expired_released, "baris"],
  ].filter(([, v]) => v != null && v !== "");
  return (
    <>
      {nums.length ? (
        <div className="grid grid-cols-2 gap-2 p-3" data-testid="mo-kpi">
          {nums.map(([k, v, unit]) => (
            <div key={k} className="m-card p-3"><div className="text-[11px] text-[#6E6E73]">{k}</div>
              <div className={`${typeof v === "number" ? "text-xl" : "text-[14px] leading-snug"} font-bold tabular-nums`}>{typeof v === "number" ? formatQty(v) : v}{unit ? <span className="ml-1 text-[11px] font-semibold text-[#6E6E73]">{unit}</span> : null}</div></div>
          ))}
        </div>
      ) : <div className="p-8 text-center text-sm text-[#6E6E73]" data-testid="mo-kpi-empty">Belum ada angka ringkas untuk peran ini.</div>}
      {desktop}
    </>
  );
}

const AI_ROLES = ["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin"];

function NotifPanel({ setTab }) {
  const [rows, setRows] = useState(null);
  const load = () => axios.get(`${API}/notifications`, { params: { unread_only: true } }).then((r) => setRows(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  const isApproval = (n) => /price-approval|special-order|harga khusus|pesanan khusus|persetujuan/i.test(`${n.link || ""} ${n.title || ""} ${n.type || ""}`);
  const open = async (n) => { try { await axios.post(`${API}/notifications/${n.id}/read`); } catch { /* abaikan */ } if (isApproval(n)) setTab("queue"); else load(); };
  if (rows === null) return <div className="p-6 text-center text-sm"><Loader2 className="animate-spin inline" size={16} /> Memuat…</div>;
  if (!rows.length) return <div className="p-8 text-center text-sm text-[#6E6E73]" data-testid="mo-notif-empty">Tidak ada notifikasi baru.</div>;
  return (
    <div className="space-y-2 p-3" data-testid="mo-notif-list">
      {rows.map((n) => (
        <button key={n.id} className="m-card m-press w-full p-3 text-left" onClick={() => open(n)} data-testid={`mo-notif-${n.id}`}>
          <div className="flex items-center gap-2 text-[13px]"><Bell size={14} className={n.severity === "warning" ? "text-[#B25E00]" : "text-[#0058CC]"} /><b className="min-w-0 flex-1 break-words">{humanizeNotif(n.title)}</b>{isApproval(n) && <span className="status-pill pill-warning shrink-0 text-[10px] !normal-case">Putuskan di HP</span>}</div>
          <p className="text-[11px] text-[#6E6E73] mt-1">{humanizeNotif(n.body)}</p>
        </button>
      ))}
    </div>
  );
}

export default function MobileOpsApp(props) {
  const tabs = [
    { id: "queue", label: "Persetujuan", icon: Inbox, render: () => <MobileApprovalInbox /> },
    { id: "notif", label: "Notifikasi", icon: Bell, render: ({ setTab }) => <NotifPanel setTab={setTab} /> },
    { id: "matrix", label: "Antrean", icon: ClipboardList, render: () => <QueuePanel /> },
  ];
  const desktop = <DesktopPanel role={props.user?.role} onForceDesktop={props.onForceDesktop} />;
  // Peran pemakai asisten: tab "Tanya" menggantikan tab Desktop (tombol desktop pindah ke Ringkas & app bar).
  if (AI_ROLES.includes(props.user?.role)) {
    tabs.push({ id: "kpi", label: "Ringkas", icon: Gauge, render: () => <KpiPanel desktop={desktop} /> });
    tabs.push({ id: "tanya", label: "Tanya", icon: Sparkles, render: () => (
      <div className="m-tanya" data-testid="mo-tanya"><TanyaKnView selectedEntity={props.selectedEntity} entities={props.entities} /></div>) });
  } else {
    tabs.push({ id: "kpi", label: "Ringkas", icon: Gauge, render: () => <KpiPanel /> });
    tabs.push({ id: "desktop", label: "Desktop", icon: Monitor, render: () => desktop });
  }
  if (['admin', 'manager', 'md'].includes(props.user?.role)) tabs.splice(4, 0, {
    // Audit UI HP (manager) — tab ini berisi pintasan (produk, sample R&D, kedatangan barang, order makloon),
    // bukan hanya produk; ikonnya juga dibedakan dari tab Antrean.
    id: 'catalog', label: 'Pintasan', icon: LayoutGrid,
    render: () => <div className="space-y-3 p-5"><button data-testid="mobile-open-catalog" className="primary-button w-full justify-center" onClick={() => props.onNavigate?.('products-pricing', 'md-products')}>Produk & varian</button><button data-testid="mobile-open-rnd" className="secondary-button w-full justify-center" onClick={() => props.onNavigate?.('rnd-hub', 'rnd-samples')}>Permintaan Sample R&D</button>{props.user?.role !== 'md' && <button data-testid="mobile-open-grn-ops" className="secondary-button w-full justify-center" onClick={() => props.onNavigate?.('wms-operations', 'goods-receipts')}>Kedatangan Barang & foto SJ</button>}{can(props.user?.permissions, 'makloon_order', 'view') && <button data-testid="mobile-open-makloon-orders" className="secondary-button w-full justify-center" onClick={() => props.onNavigate?.('purchase-orders', 'makloon-orders')}>Order Makloon (detail & retur bahan)</button>}</div>,
  });
  // L05 — petugas QC/MD Quality: Meja QC (SPK, random check dari scan) bisa dibuka dari HP.
  if (can(props.user?.permissions, 'qc', 'inspect') || can(props.user?.permissions, 'qc', 'random_check')) tabs.splice(Math.min(4, tabs.length), 0, {
    id: 'qc', label: 'QC', icon: ClipboardList,
    render: () => <div className="space-y-3 p-5"><button data-testid="mobile-open-inspections" className="primary-button w-full justify-center" onClick={() => props.onNavigate?.('quality-hub', 'inspections')}>Meja QC · SPK inspeksi & random check scan</button></div>,
  });
  return <MobileShell {...props} tabs={tabs} testId="mobile-ops-app" />;
}
