import { can, roleLabel } from "../../config/roles";
import { useEffect, useState } from "react";
import { Inbox, Gauge, Loader2, ClipboardList, Bell, Sparkles, LayoutGrid, ChevronRight } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import TanyaKnView from "../tanya/TanyaKnView";
import MobileShell from "./MobileShell";
import MobileApprovalInbox, { usePendingApprovals } from "./MobileApprovalInbox";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { formatUnitTotals } from "../../utils/qtyByUnit";
import { actorLabel } from "../../utils/actorLabel";
import { apiErrorText, isForbiddenError } from "../../utils/apiError";
import { docStatusLabel } from "../../utils/docStatus";
import { resolveView } from "../../utils/viewAlias";

// Audit UI HP (manager) — status/tahap mentah di teks notifikasi ("tahap: pending_approval") → label Indonesia.
const STAGE_LABEL = {
  pending_approval: "menunggu persetujuan", pending: "menunggu", approved: "disetujui", rejected: "ditolak",
  draft: "draf", submitted: "diajukan", in_review: "ditinjau", inspecting: "diperiksa", received: "diterima",
  completed: "selesai", done: "selesai", cancelled: "dibatalkan", waiting_stock: "menunggu stok",
  // UAT 24 Okt (audit UI tahap 2, G5-10) — tahap giliran yang dulu tetap mentah ("tahap: shipped").
  waiting_approval: "menunggu persetujuan", confirmed: "dikonfirmasi", picked: "sudah diambil", shipped: "dikirim",
  partially_shipped: "dikirim sebagian", receiving: "sedang diterima", partial: "diterima sebagian",
  inspected: "selesai inspeksi", refund_settled: "selesai · pengembalian dana", credit_settled: "selesai · store credit",
  nego_settled: "selesai · nego", settled: "selesai · per roll (campuran)",
};
const lc = (t) => t.charAt(0).toLowerCase() + t.slice(1);
// Kode tak dikenal jatuh ke peta status bersama (docStatusLabel), bukan ke kode mentah.
const stageText = (code) => STAGE_LABEL[code] || lc(docStatusLabel(code));
const humanizeNotif = (text) => String(text || "")
  .replace(/\b(tahap|status):\s*([a-z][a-z_]+)/g, (m, k, code) => `${k}: ${stageText(code)}`)
  // Eskalasi lama: "… oleh all." / "oleh manager." (kode peran mentah dari server).
  .replace(/\boleh (all|[a-z][a-z_]*)\./g, (m, r) => (r === "all" ? "oleh semua penerima." : roleLabel(r) !== r ? `oleh ${roleLabel(r)}.` : m))
  .replace(/\bAvailable\b/g, "Tersedia");

// G5-57 — nomor dokumen ("SRET-00158", "KSC/SOS-00014") tidak boleh patah di tengah saat judul dibungkus.
const DOC_NO = /((?:[A-Z]{2,6}\/)?[A-Z]{2,6}-\d[\d-]*)/;
function NoBreakNumbers({ text }) {
  return String(text || "").split(DOC_NO).map((part, i) => (i % 2 ? <span key={i} className="whitespace-nowrap">{part}</span> : part));
}

function QueuePanel() {
  const [q, setQ] = useState(null);
  const [err, setErr] = useState("");
  // G5-08 — galat memakai kalimat Indonesia (dulu "Permission ditolak: approval.view" mentah).
  useEffect(() => { axios.get(`${API}/approvals/my-queue`).then((r) => setQ(r.data)).catch((e) => setErr(isForbiddenError(e) ? "Anda tidak punya akses ke antrean persetujuan." : apiErrorText(e, "Antrean tidak bisa dimuat."))); }, []);
  if (err) return <div className="notice-bar warning m-3 text-xs" data-testid="mo-queue-error">{err}</div>;
  if (!q) return <div className="p-6 text-center text-sm"><Loader2 className="animate-spin inline" size={16} /> Memuat…</div>;
  const items = q.items || q.queue || [];
  if (!items.length) return <div className="p-6 text-center text-sm text-[#6E6E73]" data-testid="mo-queue-empty">Tidak ada dokumen lain yang menunggu keputusan Anda.</div>;
  return (
    <div className="space-y-2 p-3" data-testid="mo-queue-list">
      {items.map((it, i) => (
        <div key={it.id || i} className="m-card p-3" data-testid={`mo-queue-${it.id || i}`}>
          <div className="flex justify-between gap-2"><b className="min-w-0 break-words"><NoBreakNumbers text={it.doc_number || it.number || it.title || it.stage_label || stageText(it.stage || "")} /></b><span className="status-pill pill-warning shrink-0">{it.stage_label || (it.stage ? stageText(it.stage) : "menunggu")}</span></div>
          {/* Audit UI 24 Okt (HP manager › Antrean) — titik yatim "· Rp 0" & akun teknis ("system-seed") tidak tampil. */}
          <div className="text-xs text-[#6E6E73] mt-1">{[it.customer_name || actorLabel(it.requester_name || it.requester, ""), Number(it.amount) > 0 ? formatCurrency(it.amount) : ""].filter(Boolean).join(" · ")}</div>
        </div>
      ))}
      <p className="text-xs text-[#6E6E73] px-1">Harga khusus & pesanan khusus bisa diputuskan di atas; dokumen lain di tampilan desktop.</p>
    </div>
  );
}

/** Tab Persetujuan: yang bisa diputus di HP (harga/pesanan khusus) + antrean lintas tahap (dulu tab "Antrean"). */
function ApprovalsTab({ canPrice, canSpecial, canQueue, focusId }) {
  return (
    <div data-testid="mo-approvals">
      {(canPrice || canSpecial) && <MobileApprovalInbox canPrice={canPrice} canSpecial={canSpecial} focusId={focusId} />}
      {canQueue && (
        <section data-testid="mo-queue-section">
          <h3 className="px-4 pt-3 text-[12px] font-semibold uppercase tracking-wide text-[#6E6E73]">Antrean lintas tahap</h3>
          <QueuePanel />
        </section>
      )}
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

// UAT 24 Okt (audit UI tahap 2, G5-09) — lencana "Putuskan di HP" dulu dipasang dari regex teks ("persetujuan",
// "harga khusus") lalu selalu membuka tab Persetujuan yang tidak memuat dokumennya. Kini lencana hanya bila
// dokumennya BENAR-BENAR ada di daftar Persetujuan (harga khusus via action_id, PO custom via ref/nomor).
const sordIdOf = (n) => (String(n.ref || "").match(/so_custom_appr:([A-Za-z0-9_]+)/) || [])[1] || "";
const sordNoOf = (n) => (String(n.title || "").match(/(?:[A-Z]{2,6}\/)?SORD-[\d-]+/) || [])[0] || "";
function decisionTarget(n, prices, specials) {
  if (n.action_type === "price_approval_view" && (prices || []).some((p) => p.id === n.action_id)) return n.action_id;
  if (n.type === "special_order_approval" || n.link === "special-orders") {
    const id = sordIdOf(n);
    if (id && (specials || []).some((s) => s.id === id)) return id;
    const no = sordNoOf(n);
    const hit = no && (specials || []).find((s) => s.number === no);
    if (hit) return hit.id;
  }
  return "";
}
const linkView = (n) => resolveView(String(n.link || "").replace(/^\/?(\?view=)?/, ""));

function NotifPanel({ canPrice, canSpecial, onDecide, onOpenDesktop }) {
  const [rows, setRows] = useState(null);
  const [total, setTotal] = useState(null);
  const [err, setErr] = useState("");
  const { prices, specials } = usePendingApprovals({ canPrice, canSpecial });
  const load = () => {
    axios.get(`${API}/notifications`, { params: { unread_only: true } })
      .then((r) => { setRows(Array.isArray(r.data) ? r.data : r.data.items || []); setErr(""); })
      .catch((e) => { setRows([]); setErr(apiErrorText(e, "Notifikasi tidak bisa dimuat.")); });
    axios.get(`${API}/notifications/unread-count`).then((r) => setTotal(Number(r.data?.count) || 0)).catch(() => setTotal(null));
  };
  useEffect(() => { load(); }, []);
  const markRead = (ids) => Promise.all(ids.map((id) => axios.post(`${API}/notifications/${id}/read`).catch(() => null)));
  const open = async (g, target) => {
    await markRead(g.ids);
    if (target) { onDecide(target); return; }
    const view = linkView(g.n);
    if (view) { onOpenDesktop(view); return; }
    load();
  };
  const markAll = async () => {
    try { await axios.post(`${API}/notifications/read-all`); } catch (e) { setErr(apiErrorText(e, "Gagal menandai notifikasi.")); }
    load();
  };
  if (rows === null) return <div className="p-6 text-center text-sm"><Loader2 className="animate-spin inline" size={16} /> Memuat…</div>;
  // G5-57 — eskalasi lama yang tersalin per penerima tampil 2× berurutan: kartu identik digabung (dibaca bersama).
  const groups = [];
  const byKey = new Map();
  rows.forEach((n) => {
    const k = `${n.type}|${n.title}|${n.body}`;
    if (byKey.has(k)) { byKey.get(k).ids.push(n.id); return; }
    const g = { n, ids: [n.id] };
    byKey.set(k, g); groups.push(g);
  });
  return (
    <div className="space-y-2 p-3" data-testid="mo-notif-list">
      <div className="flex items-center justify-between gap-2 px-1" data-testid="mo-notif-head">
        <span className="text-[13px] font-semibold">Belum dibaca{total != null ? ` · ${formatQty(total)}` : ""}</span>
        {rows.length > 0 && <button type="button" className="text-[12px] font-semibold text-[#0058CC]" onClick={markAll} data-testid="mo-notif-mark-all">Tandai semua dibaca</button>}
      </div>
      {total != null && total > rows.length && <p className="px-1 text-[11px] text-[#6E6E73]" data-testid="mo-notif-partial">Menampilkan {formatQty(rows.length)} terbaru dari {formatQty(total)}.</p>}
      {err && <div className="notice-bar danger text-xs" data-testid="mo-notif-error">{err}</div>}
      {!rows.length && !err && <div className="p-8 text-center text-sm text-[#6E6E73]" data-testid="mo-notif-empty">Tidak ada notifikasi baru.</div>}
      {groups.map((g) => {
        const n = g.n;
        const target = decisionTarget(n, prices, specials);
        const view = !target && linkView(n);
        return (
          <button key={n.id} className="m-card m-press w-full p-3 text-left" onClick={() => open(g, target)} data-testid={`mo-notif-${n.id}`}>
            <div className="flex items-center gap-2 text-[13px]"><Bell size={14} className={n.severity === "warning" || n.severity === "critical" ? "text-[#B25E00]" : "text-[#0058CC]"} /><b className="min-w-0 flex-1 break-words"><NoBreakNumbers text={humanizeNotif(n.title)} /></b>{g.ids.length > 1 && <span className="shrink-0 text-[10px] text-[#6E6E73]">×{g.ids.length}</span>}{target && <span className="status-pill pill-warning shrink-0 text-[10px] !normal-case" data-testid={`mo-notif-decide-${n.id}`}>Putuskan di HP</span>}</div>
            <p className="text-[11px] text-[#6E6E73] mt-1 break-words"><NoBreakNumbers text={humanizeNotif(n.body)} /></p>
            {view && <span className="mt-1 inline-flex items-center gap-0.5 text-[11px] font-semibold text-[#0058CC]">Buka di tampilan desktop <ChevronRight size={12} /></span>}
          </button>
        );
      })}
    </div>
  );
}

export default function MobileOpsApp(props) {
  // UAT 24 Okt (audit UI tahap 2, G5-08) — tab dibentuk dari IZIN (sumber yang sama dengan penjaga server). Dulu
  // Persetujuan & Antrean diberikan ke SEMUA peran: desainer/admin sample melihat "Permission ditolak:
  // approval.view" dan 403 harga khusus disamarkan jadi "Tidak ada … yang menunggu". Izin belum termuat → tampil.
  const perms = props.user?.permissions;
  const allow = (m, a) => !perms || can(perms, m, a);
  const canPrice = allow("price_approval", "approve");
  const canSpecial = allow("order", "approve");
  const canQueue = allow("approval", "view");
  const [focus, setFocus] = useState("");
  const openDesktop = (view) => { props.onNavigate?.(view, view); props.onForceDesktop?.(); };
  const tabs = [];
  if (canPrice || canSpecial || canQueue) {
    tabs.push({ id: "queue", label: "Persetujuan", icon: Inbox, render: () => <ApprovalsTab canPrice={canPrice} canSpecial={canSpecial} canQueue={canQueue} focusId={focus} /> });
  }
  tabs.push({ id: "notif", label: "Notifikasi", icon: Bell, render: ({ setTab }) => (
    <NotifPanel canPrice={canPrice} canSpecial={canSpecial} onOpenDesktop={openDesktop}
      onDecide={(id) => { setFocus(id); setTab("queue"); }} />) });
  const desktop = <DesktopPanel role={props.user?.role} onForceDesktop={props.onForceDesktop} />;
  // G5-58 — bilah bawah maksimal 5 tab: tab "Desktop" (isinya hanya satu tombol) dilebur ke Ringkas; tombol desktop
  // juga sudah ada di app bar. Peran pemakai asisten mendapat tab "Tanya".
  tabs.push({ id: "kpi", label: "Ringkas", icon: Gauge, render: () => <KpiPanel desktop={desktop} /> });
  const qcAllowed = can(perms, 'qc', 'inspect') || can(perms, 'qc', 'random_check');
  const qcButton = <button data-testid="mobile-open-inspections" className="primary-button w-full justify-center" onClick={() => props.onNavigate?.('quality-hub', 'inspections')}>Meja QC · SPK inspeksi & random check scan</button>;
  if (['admin', 'manager', 'md'].includes(props.user?.role)) tabs.push({
    // Audit UI HP (manager) — tab ini berisi pintasan (produk, sample R&D, kedatangan barang, order makloon),
    // bukan hanya produk; ikonnya juga dibedakan dari tab Antrean. G5-58: Meja QC ikut di sini (bukan tab sendiri).
    id: 'catalog', label: 'Pintasan', icon: LayoutGrid,
    render: () => <div className="space-y-3 p-5"><button data-testid="mobile-open-catalog" className="primary-button w-full justify-center" onClick={() => props.onNavigate?.('products-pricing', 'md-products')}>Produk & varian</button><button data-testid="mobile-open-rnd" className="secondary-button w-full justify-center" onClick={() => props.onNavigate?.('rnd-hub', 'rnd-samples')}>Permintaan Sample R&D</button>{props.user?.role !== 'md' && <button data-testid="mobile-open-grn-ops" className="secondary-button w-full justify-center" onClick={() => props.onNavigate?.('wms-operations', 'goods-receipts')}>Kedatangan Barang & foto SJ</button>}{can(props.user?.permissions, 'makloon_order', 'view') && <button data-testid="mobile-open-makloon-orders" className="secondary-button w-full justify-center" onClick={() => props.onNavigate?.('purchase-orders', 'makloon-orders')}>Order Makloon (detail & retur bahan)</button>}{qcAllowed && qcButton}</div>,
  });
  // L05 — petugas QC/MD Quality: Meja QC (SPK, random check dari scan) bisa dibuka dari HP.
  else if (qcAllowed) tabs.push({ id: 'qc', label: 'QC', icon: ClipboardList, render: () => <div className="space-y-3 p-5">{qcButton}</div> });
  if (AI_ROLES.includes(props.user?.role)) {
    tabs.push({ id: "tanya", label: "Tanya", icon: Sparkles, render: () => (
      <div className="m-tanya" data-testid="mo-tanya"><TanyaKnView selectedEntity={props.selectedEntity} entities={props.entities} /></div>) });
  }
  return <MobileShell {...props} tabs={tabs} testId="mobile-ops-app" />;
}
