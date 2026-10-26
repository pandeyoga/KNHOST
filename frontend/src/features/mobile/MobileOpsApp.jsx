import { can, roleIs } from "../../config/roles";
import { useEffect, useState } from "react";
import { Inbox, Gauge, Loader2, ClipboardList, Sparkles, LayoutGrid, ExternalLink } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import TanyaKnView from "../tanya/TanyaKnView";
import MobileShell from "./MobileShell";
import MobileApprovalInbox, { usePendingApprovals } from "./MobileApprovalInbox";
import MobileRoleSummary, { roleSummaryKind } from "./MobileRoleSummary";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { formatUnitTotals } from "../../utils/qtyByUnit";
import { actorLabel } from "../../utils/actorLabel";
import { apiErrorText, isForbiddenError } from "../../utils/apiError";
import { canSeeMatrix } from "../approvals/inboxTabs";
import { resolveDeepLinkTarget } from "../../config/navigationConfig";
import { NoBreakNumbers, decisionTarget, linkView, stageText } from "./notifText";

/**
 * Fase 3 · P7 (D-06 HP) — antrean lintas tahap (`/approvals/my-queue`: ACC desain, ACC sample, PR, PO custom, klaim
 * makloon) TANPA dokumen yang sudah tampil di daftar keputusan HP di atasnya (PO custom yang ada di daftar pesanan
 * khusus). Tiap dokumen punya "Buka layar lengkap": Pusat Persetujuan › Matriks divisi (peran yang dulu membuka
 * Persetujuan Saya) atau layar kerja tahapnya.
 */
export const dedupQueue = (items, specials) => {
  const shown = new Set((specials || []).map((s) => s.id));
  return (items || []).filter((it) => !(it.stage === "po_custom" && shown.has(it.id)));
};
export const queueFullTarget = (it, role) => (canSeeMatrix(role)
  ? { nav: "approval-inbox", view: "approval-inbox", preset: { tab: "matrix" } }
  : { nav: it.view, view: it.view });
// Verifikasi crawl fase 3: Finance tercatat pemutus satu tahap PR tetapi tanpa izin `purchase_requisition.view` →
// "Buka layar lengkap" mendarat di "Permission ditolak". Tombol hanya tampil bila layar tujuan boleh dibuka peran
// ini (aturan menu yang sama: peran + izin server + hidden_views).
export const canOpenFull = (to, role) => !!(to?.view && role && resolveDeepLinkTarget(to.view, role));

function QueuePanel({ specials, role, onOpenFull }) {
  const [q, setQ] = useState(null);
  const [err, setErr] = useState("");
  // G5-08 — galat memakai kalimat Indonesia (dulu "Permission ditolak: approval.view" mentah).
  // Fase 3 · P7 — muat ulang yang berhasil menghapus galat sebelumnya (dev StrictMode / token baru terpasang).
  useEffect(() => { axios.get(`${API}/approvals/my-queue`).then((r) => { setQ(r.data); setErr(""); }).catch((e) => setErr(isForbiddenError(e) ? "Anda tidak punya akses ke antrean persetujuan." : apiErrorText(e, "Antrean tidak bisa dimuat."))); }, []);
  if (err && !q) return <div className="notice-bar warning m-3 text-xs" data-testid="mo-queue-error">{err}</div>;
  if (!q) return <div className="p-6 text-center text-sm"><Loader2 className="animate-spin inline" size={16} /> Memuat…</div>;
  const all = q.items || q.queue || [];
  const items = dedupQueue(all, specials);
  const hidden = all.length - items.length;
  if (!items.length) return <div className="p-6 text-center text-sm text-[#6E6E73]" data-testid="mo-queue-empty">Tidak ada dokumen lain yang menunggu keputusan Anda.</div>;
  return (
    <div className="space-y-2 p-3" data-testid="mo-queue-list">
      {items.map((it, i) => {
        const to = queueFullTarget(it, role);
        return (
          <div key={it.id || i} className="m-card p-3" data-testid={`mo-queue-${it.id || i}`}>
            <div className="flex justify-between gap-2"><b className="min-w-0 break-words"><NoBreakNumbers text={it.doc_number || it.number || it.title || it.stage_label || stageText(it.stage || "")} /></b><span className="status-pill pill-warning shrink-0">{it.stage_label || (it.stage ? stageText(it.stage) : "menunggu")}</span></div>
            {/* Audit UI 24 Okt (HP manager › Antrean) — titik yatim "· Rp 0" & akun teknis ("system-seed") tidak tampil. */}
            <div className="text-xs text-[#6E6E73] mt-1">{[it.customer_name || actorLabel(it.requester_name || it.requester, ""), Number(it.amount) > 0 ? formatCurrency(it.amount) : ""].filter(Boolean).join(" · ")}</div>
            {onOpenFull && canOpenFull(to, role) && (
              <button type="button" className="mt-2 inline-flex items-center gap-1 text-[12px] font-semibold text-[#0058CC]" data-testid={`mo-queue-open-${it.id || i}`}
                onClick={() => onOpenFull(to.nav, to.view, to.preset ? { preset: to.preset } : undefined)}>Buka layar lengkap <ExternalLink size={12} /></button>
            )}
          </div>
        );
      })}
      <p className="text-xs text-[#6E6E73] px-1" data-testid="mo-queue-note">Dokumen di atas diputus di layar lengkap{hidden > 0 ? ` · ${hidden} pesanan khusus sudah ada di daftar keputusan HP` : ""}.</p>
    </div>
  );
}

/** Tab Persetujuan: yang bisa diputus di HP (harga/pesanan khusus) + antrean lintas tahap (dulu tab "Antrean"). */
function ApprovalsTab({ canPrice, canSpecial, canQueue, focusId, pending, role, onOpenFull }) {
  return (
    <div data-testid="mo-approvals">
      {(canPrice || canSpecial) && <MobileApprovalInbox canPrice={canPrice} canSpecial={canSpecial} focusId={focusId} pending={pending} />}
      {canQueue && (
        <section data-testid="mo-queue-section">
          <h3 className="px-4 pt-3 text-[12px] font-semibold uppercase tracking-wide text-[#6E6E73]">Antrean lintas tahap</h3>
          <QueuePanel specials={pending?.specials} role={role} onOpenFull={onOpenFull} />
        </section>
      )}
    </div>
  );
}

function KpiPanel() {
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
  return nums.length ? (
    <div className="grid grid-cols-2 gap-2 p-3" data-testid="mo-kpi">
      {nums.map(([k, v, unit]) => (
        <div key={k} className="m-card p-3"><div className="text-[11px] text-[#6E6E73]">{k}</div>
          <div className={`${typeof v === "number" ? "text-xl" : "text-[14px] leading-snug"} font-bold tabular-nums`}>{typeof v === "number" ? formatQty(v) : v}{unit ? <span className="ml-1 text-[11px] font-semibold text-[#6E6E73]">{unit}</span> : null}</div></div>
      ))}
    </div>
  ) : <div className="p-8 text-center text-sm text-[#6E6E73]" data-testid="mo-kpi-empty">Belum ada angka ringkas untuk peran ini.</div>;
}

const AI_ROLES = ["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin"];
// Keputusan pemilik K-11 (26 Okt) — Admin Sample TIDAK memutus pesanan khusus (SORD) di HP: tab/aksi PO custom
// disembunyikan apa pun izin yang termuat (server: matriks bawaan sample_admin tanpa `order.approve` → 403).
const NO_SORD_DECISION_ROLES = ["sample_admin"];

export default function MobileOpsApp(props) {
  // UAT 24 Okt (audit UI tahap 2, G5-08) — tab dibentuk dari IZIN (sumber yang sama dengan penjaga server). Dulu
  // Persetujuan & Antrean diberikan ke SEMUA peran: desainer/admin sample melihat "Permission ditolak:
  // approval.view" dan 403 harga khusus disamarkan jadi "Tidak ada … yang menunggu". Izin belum termuat → tampil.
  const { user, onOpenFull } = props;
  const perms = user?.permissions;
  const allow = (m, a) => !perms || can(perms, m, a);
  const canPrice = allow("price_approval", "approve");
  const canSpecial = allow("order", "approve") && !roleIs(user?.role, NO_SORD_DECISION_ROLES);
  const canQueue = allow("approval", "view");
  // Satu daftar keputusan HP untuk tab Persetujuan, dedup antrean & lencana "Putuskan di HP" di lonceng.
  const pending = usePendingApprovals({ canPrice, canSpecial });
  const [focus, setFocus] = useState("");
  const firstTab = canPrice || canSpecial || canQueue ? "queue" : "kpi";
  const [tab, setTab] = useState(props.initialTab || firstTab);
  useEffect(() => { if (props.initialTab) setTab(props.initialTab); }, [props.initialTab]);
  // Fitur tanpa layar HP → "tampilan penuh" SEMENTARA (tombol kembali ke aplikasi HP), bukan mode desktop menetap.
  const openFull = (navId, view, opts) => {
    if (onOpenFull) { onOpenFull(navId, view, opts); return; }
    props.onNavigate?.(navId, view); props.onForceDesktop?.();
  };
  // Lonceng (L-09): dokumen yang ada di daftar Persetujuan HP → tab Persetujuan terfokus; tautan lain → layar penuh.
  const decideOf = (n) => decisionTarget(n, pending.prices, pending.specials);
  const openNotif = (n) => {
    const target = decideOf(n);
    if (target) { setFocus(target); setTab("queue"); return true; }
    const view = linkView(n);
    if (!view) return false;
    openFull(view, view);
    return true;
  };

  const tabs = [];
  if (canPrice || canSpecial || canQueue) {
    const waiting = (pending.prices || []).length + (pending.specials || []).length;
    tabs.push({ id: "queue", label: "Persetujuan", icon: Inbox, badge: waiting, render: () => (
      <ApprovalsTab canPrice={canPrice} canSpecial={canSpecial} canQueue={canQueue} focusId={focus} pending={pending}
        role={user?.role} onOpenFull={openFull} />) });
  }
  // K-12 (26 Okt) — Ringkas per peran: Desainer & Admin Sample melihat angka pekerjaannya; peran lain panel umum.
  // D-26 — tombol "Buka Tampilan Desktop" (`mo-open-desktop`) di Ringkas dicabut: satu pintu di tab Lainnya.
  const summaryKind = roleSummaryKind(user?.role);
  tabs.push({ id: "kpi", label: "Ringkas", icon: Gauge, render: () => (summaryKind
    ? <MobileRoleSummary kind={summaryKind} selectedEntity={props.selectedEntity} onOpen={openFull} />
    : <KpiPanel />) });
  const qcAllowed = can(perms, "qc", "inspect") || can(perms, "qc", "random_check");
  const qcButton = <button type="button" data-testid="mobile-open-inspections" className="primary-button w-full justify-center" onClick={() => openFull("quality-hub", "inspections")}>Meja QC · SPK inspeksi & random check scan</button>;
  if (["admin", "manager", "md"].includes(user?.role)) tabs.push({
    // Audit UI HP (manager) — tab ini berisi pintasan (produk, sample R&D, kedatangan barang, order makloon).
    // Fase 3 · P7 — pintasan dibuka sebagai tampilan penuh + tombol kembali (dulu sebagian tidak berpindah layar).
    id: "catalog", label: "Pintasan", icon: LayoutGrid,
    render: () => (
      <div className="space-y-3 p-5">
        <button type="button" data-testid="mobile-open-catalog" className="primary-button w-full justify-center" onClick={() => openFull("products-pricing", "md-products")}>Produk & varian</button>
        <button type="button" data-testid="mobile-open-rnd" className="secondary-button w-full justify-center" onClick={() => openFull("rnd-hub", "rnd-samples")}>Permintaan Sample R&D</button>
        {user?.role !== "md" && <button type="button" data-testid="mobile-open-grn-ops" className="secondary-button w-full justify-center" onClick={() => openFull("wms-operations", "goods-receipts")}>Kedatangan Barang & foto SJ</button>}
        {can(perms, "makloon_order", "view") && <button type="button" data-testid="mobile-open-makloon-orders" className="secondary-button w-full justify-center" onClick={() => openFull("purchase-orders", "makloon-orders")}>Order Makloon (detail & retur bahan)</button>}
        {qcAllowed && qcButton}
      </div>
    ),
  });
  // L05 — petugas QC/MD Quality: Meja QC (SPK, random check dari scan) bisa dibuka dari HP.
  else if (qcAllowed) tabs.push({ id: "qc", label: "QC", icon: ClipboardList, render: () => <div className="space-y-3 p-5">{qcButton}</div> });
  if (AI_ROLES.includes(user?.role)) {
    tabs.push({ id: "tanya", label: "Tanya", icon: Sparkles, render: () => (
      <div className="m-tanya" data-testid="mo-tanya"><TanyaKnView selectedEntity={props.selectedEntity} entities={props.entities} /></div>) });
  }
  return (
    <MobileShell {...props} tabs={tabs} tab={tab} onTabChange={setTab} testId="mobile-ops-app"
      onOpenNotif={openNotif} notifDecideOf={decideOf} />
  );
}
