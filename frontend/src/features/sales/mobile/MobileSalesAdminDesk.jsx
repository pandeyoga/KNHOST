/**
 * MobileSalesAdminDesk — Meja Admin Sales versi HP (cermin SalesAdminDesk desktop).
 *
 * Mesin & wewenang SAMA dengan desktop (workDeskApi): antrean dari `/sales-admin/desk`,
 * Verifikasi & Keputusan Pemenuhan memakai dialog yang sama (tampil sebagai lembar bawah
 * di HP), Konfirmasi langsung dari baris. Baris "Buka" diarahkan ke layar HP yang
 * menanganinya (pesanan / retur / permintaan internal / pesanan khusus); jenis lain
 * dibuka tampilan penuh.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, Inbox, Layers, RefreshCw, ShieldAlert, ClipboardCheck } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { HelpTip } from "../../../components/ListPageParts";
import DeskRowDetail from "../../desks/DeskRowDetail";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { formatUnitTotals } from "../../../utils/qtyByUnit";
import VerifyOrderDialog from "../../sales_admin/VerifyOrderDialog";
import FulfillmentDecisionDialog from "../../sales_admin/FulfillmentDecisionDialog";
import KeepPendingPanel from "../../sales_admin/KeepPendingPanel";
import ReleaseToWarehouseDialog from "../../sales_admin/ReleaseToWarehouseDialog";
import AssignSalesDialog from "../../sales_admin/AssignSalesDialog";
import { inPlaceOf } from "../../sales_admin/DeskQueueCard";
import { adminSalesQueues, catatDiingatkan, inPlaceAdminSales, tolakPermintaanInternal } from "../../sales_admin/deskRowActions";
import { ageTone, badgeClass, badgeLabel, queueMeta, releaseMessage, releaseOrder, rowLink, salesAdminDesk } from "../../sales_admin/workDeskApi";

const PREVIEW = 5;
// ref_type → sub-halaman HP (menu Lainnya) atau tab Pesanan.
// Aksi Meja gelombang 2 (Task 8) — tetapkan sales, catat diingatkan, tolak PIN — sama dengan desktop (`deskRowActions`).
const IN_PLACE_LAMA = inPlaceOf(["verify", "fulfill", "release"]);
const IN_PLACE = (row) => IN_PLACE_LAMA(row) || inPlaceAdminSales(row);
const HELP_ALUR = "Periksa kelengkapan → putuskan pemenuhan → konfirmasi → dokumen → retur. Nilai besar, kredit & harga khusus tetap keputusan manajer.";
const MOBILE_TARGET = { sales_return: "returns", internal_request: "internal", special_order: "special" };

function DeskRow({ row, queue, busy, onAction, onOpen }) {
  const age = ageTone(row.age_days);
  const isQty = queue.value_kind === "qty";
  const value = isQty ? `${formatQty(row.value)} ${row.unit || ""}`.trim() : queue.value_kind === "count" ? "" : formatCurrency(Number(row.value) || 0);
  const rk = row.row_key || row.ref_id;
  // R18: baris BUKAN kontrol (berisi tombol sungguhan) — sentuh di mana saja membuka rincian, tap pada tombol/tautan
  // di dalamnya diabaikan; jalur papan ketik = tombol nomor dokumen.
  const onClick = (e) => {
    const hit = e.target.closest?.("button, a, input, select, textarea");
    if (hit && hit !== e.currentTarget && e.currentTarget.contains(hit)) return;
    onOpen(row, queue);
  };
  return (
    <div className="m-list-row items-start" onClick={onClick} data-testid={`m-desk-row-${queue.id}-${rk}`}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <button type="button" className="link-button -mx-1 -my-0.5" aria-haspopup="dialog" onClick={() => onOpen(row, queue)} data-testid={`m-desk-number-${queue.id}-${rk}`}>
            <span className="text-fs-13 font-semibold text-kn-action">{row.number}</span>
          </button>
          {row.badge && <span className={`rounded-full border px-1.5 py-0.5 text-fs-12 font-medium ${badgeClass(row.badge)}`}>{badgeLabel(row.badge)}</span>}
          <span className={`rounded-full border px-1.5 py-0.5 text-fs-12 font-medium ${age.cls}`}>{age.label}</span>
        </div>
        <p className="truncate text-fs-13 text-kn-text">{row.title}</p>
        {row.subtitle && <p className="truncate text-fs-12 m-muted">{row.subtitle}</p>}
        {value && <p className="text-fs-13 font-semibold tabular-nums text-kn-text">{value}</p>}
      </div>
      <button type="button" className={`${["verify", "release", "fulfill"].includes(row.action_kind) ? "primary-button" : "secondary-button"} m-press shrink-0 px-3 py-2 text-fs-12`}
        disabled={busy} onClick={(e) => { e.stopPropagation(); onAction(row, queue); }} data-testid={`m-desk-action-${queue.id}-${rk}`}>
        {busy ? "Memproses…" : (row.action || queue.action_label || "Buka")}
      </button>
    </div>
  );
}

function DeskQueue({ queue, busyRef, onAction, onOpen }) {
  const [open, setOpen] = useState((queue.count || 0) > 0);
  const [all, setAll] = useState(false);
  const meta = queueMeta(queue.id);
  const Icon = meta.icon;
  const rows = Array.isArray(queue.rows) ? queue.rows : [];
  const shown = all ? rows : rows.slice(0, PREVIEW);
  const oldest = ageTone(queue.oldest_age_days);
  // Audit UI 24 Okt (HP Meja Admin Sales) — total qty PER SATUAN (dulu 60 kg + 1.000 yard + 60 kg tertulis
  // "1.120 kg" memakai satuan baris pertama). Sama dengan DeskQueueCard desktop.
  const unitTotals = queue.value_kind === "qty"
    ? rows.reduce((m, r) => { const u = r.unit || ""; m[u] = (m[u] || 0) + (Number(r.value) || 0); return m; }, {})
    : null;
  const total = queue.value_kind === "qty" ? (rows.length ? formatUnitTotals(unitTotals, queue.total_value) : formatQty(queue.total_value))
    : queue.value_kind === "count" ? `${rows.length} dok` : formatCurrency(Number(queue.total_value) || 0);
  return (
    <div className="m-card overflow-hidden" data-testid={`m-desk-queue-${queue.id}`}>
      <button type="button" className="m-press flex w-full items-start gap-2.5 p-3 text-left" onClick={() => setOpen((v) => !v)} aria-expanded={open} data-testid={`m-desk-queue-toggle-${queue.id}`}>
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg" style={{ background: meta.bg }}><Icon size={17} style={{ color: meta.tone }} /></span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="text-fs-14 font-semibold leading-tight">{queue.label}</span>
            <span className="rounded-full px-2 py-0.5 text-fs-12 font-medium tabular-nums" style={{ background: meta.bg, color: meta.tone }} data-testid={`m-desk-count-${queue.id}`}>{queue.count || 0}</span>
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-fs-12 m-muted">
            <span className="font-semibold tabular-nums text-kn-text">{total}</span>
            {(queue.count || 0) > 0 && <span className={`rounded-full border px-1.5 py-0.5 text-fs-12 font-medium ${oldest.cls}`}>tertua {oldest.label}</span>}
          </span>
        </span>
        <ChevronDown size={16} className={`mt-1 shrink-0 text-kn-text-2 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-kn-divider px-3">
          {queue.hint && <p className="pt-2 text-fs-12 leading-relaxed m-muted">{queue.hint}</p>}
          {rows.length === 0 ? (
            <p className="py-5 text-center text-fs-13 m-muted" data-testid={`m-desk-empty-${queue.id}`}>Antrean bersih — tidak ada yang perlu ditindak.</p>
          ) : shown.map((row, i) => (
            <DeskRow key={`${row.ref_type}-${row.ref_id}-${row.number || i}`} row={row} queue={queue} busy={busyRef === row.ref_id} onAction={onAction} onOpen={onOpen} />
          ))}
          {rows.length > PREVIEW && (
            <button type="button" className="w-full py-2.5 text-fs-13 font-semibold text-kn-action" onClick={() => setAll((v) => !v)} data-testid={`m-desk-see-all-${queue.id}`}>
              {all ? "Tampilkan lebih sedikit" : `Lihat semua ${rows.length} baris`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function MobileSalesAdminDesk({ selectedEntity, onOpenOrder, onOpenSub, onOpenFull, currentUser }) {
  const [desk, setDesk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [errorAction, setErrorAction] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busyRef, setBusyRef] = useState("");
  const [verifyRow, setVerifyRow] = useState(null);
  const [fulfillRow, setFulfillRow] = useState(null);
  const [releaseRow, setReleaseRow] = useState(null);
  const [assignRow, setAssignRow] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
      setDesk(await salesAdminDesk(params));
      setError(""); setErrorAction(null);
    } catch (e) { setError(apiErrorText(e, "Gagal memuat Meja Admin Sales.")); }
    finally { setLoading(false); }
  }, [selectedEntity]);
  useEffect(() => { load(); }, [load]);

  const flash = (m) => toast({ title: m });

  // Trial 22 Okt (E8) — antrean "Ditahan": lepas ke gudang.
  const doRelease = (row) => { setError(""); setErrorAction(null); setReleaseRow(row); };

  function openRow(row, queue) {
    const sub = MOBILE_TARGET[row.ref_type];
    if (sub) { onOpenSub?.(sub, row.ref_id); return; }
    if (row.ref_type === "sales_order" || row.order_id) { onOpenOrder?.(row.order_id || row.ref_id); return; }
    const link = rowLink(row, queue?.id, "sales_admin");
    onOpenFull?.(link.nav_id, link.view);
  }

  // R20: tombol aksi di baris langsung bertindak bila aksinya di tempat atau tujuannya layar HP; tujuan layar desktop
  // dibuka lewat pop-up rincian dulu (aksi di pop-up bertanda "pindah layar" + "Buka layar penuh").
  const isMobileTarget = (row) => Boolean(MOBILE_TARGET[row.ref_type]) || row.ref_type === "sales_order" || Boolean(row.order_id);
  function onRowAction(row, queue) {
    if (row.action_kind === "view") return setDetail({ row, queue });   // "Lihat" = pop-up rincian saja
    if (IN_PLACE(row) || isMobileTarget(row)) return handleAction(row, queue);
    setDetail({ row, queue });
  }

  /** Aksi satu langkah: sukses → toast + muat ulang; galat → kotak galat meja. */
  async function aksiLangsung(row, fn) {
    setError(""); setErrorAction(null); setBusyRef(row.ref_id);
    try {
      const pesan = await fn(row);
      if (pesan) { flash(pesan); load(); }
    } catch (e) { setError(apiErrorText(e, "Aksi gagal.")); }
    finally { setBusyRef(""); }
  }

  function handleAction(row, queue) {
    if (row.action_kind === "view") return setDetail({ row, queue });
    if (row.action_kind === "assign_sales") return setAssignRow({ id: row.ref_id, name: row.title, entity_id: row.entity_id || "" });
    if (row.action_kind === "mark_reminded") return aksiLangsung(row, catatDiingatkan);
    if (row.action_kind === "reject_internal") return aksiLangsung(row, tolakPermintaanInternal);
    if (row.action_kind === "verify") return setVerifyRow(row);
    if (row.action_kind === "fulfill") return setFulfillRow(row);
    if (row.action_kind === "release") return doRelease(row);
    return openRow(row, queue);
  }

  const notMine = (desk?.not_my_desk || []).filter(Boolean);
  const perms = currentUser?.permissions;
  const queues = useMemo(() => adminSalesQueues(desk?.queues, perms || {}), [desk, perms]);
  const openItems = desk?.totals?.open_items || 0;
  const totalMoney = queues.filter((q) => q.value_kind !== "qty").reduce((s, q) => s + (q.total_value || 0), 0);
  const oldest = Math.max(0, ...queues.map((q) => q.oldest_age_days || 0));

  return (
    <div className="space-y-3" data-testid="m-sales-admin-desk">
      <div className="flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2"><ClipboardCheck size={16} className="text-kn-action" /><h2 className="m-section-title" data-testid="m-desk-title">Meja Admin Sales</h2>
          <HelpTip testId="m-desk-help" label="Penjelasan Meja Admin Sales" text={<>{HELP_ALUR}{notMine.length > 0 && <><br /><b>Bukan wewenang meja ini:</b> {notMine.join(" · ")} (ada di Meja Keuangan)</>}</>} /></div>
        <button onClick={load} className="text-kn-text-2" aria-label="Muat ulang" data-testid="m-desk-refresh"><RefreshCw size={15} className={loading ? "animate-spin" : ""} /></button>
      </div>
      {error && (
        <div className="notice-bar danger text-xs" data-testid="m-desk-error">
          <span className="flex-1">{error}</span>
          {errorAction && <button className="ml-2 font-bold underline" onClick={errorAction.run} data-testid="m-desk-error-action">{errorAction.label}</button>}
        </div>
      )}
      <div className="grid grid-cols-3 gap-2" data-testid="m-desk-metrics">
        {[
          { icon: Inbox, label: "Perlu ditindak", value: openItems, bg: "rgba(255,149,0,.16)", id: "open" },
          { icon: Layers, label: "Nilai antrean", value: formatCurrency(totalMoney), bg: "rgba(0,122,255,.12)", id: "value" },
          { icon: ShieldAlert, label: "Umur tertua", value: oldest > 0 ? `${oldest} hari` : "< 1 hari", bg: "rgba(255,59,48,.14)", id: "oldest" },
        ].map((m) => (
          <div key={m.id} className="m-card p-2.5" data-testid={`m-desk-metric-${m.id}`}>
            <span className="grid h-7 w-7 place-items-center rounded-lg" style={{ background: m.bg }}><m.icon size={14} /></span>
            <p className="mt-1.5 text-fs-12 font-medium text-kn-text-2">{m.label}</p>
            <p className="truncate text-fs-13 font-semibold tabular-nums">{m.value}</p>
          </div>
        ))}
      </div>
      <KeepPendingPanel selectedEntity={selectedEntity} testPrefix="m-kp" onOpenDocument={(l) => onOpenOrder?.(l.focus_id)} />
      {loading && !desk ? (
        <div className="space-y-2.5">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-xl bg-kn-neutral-soft" />)}</div>
      ) : queues.length === 0 ? (
        <div className="py-12 text-center text-fs-12 m-muted" data-testid="m-desk-empty">Belum ada antrean untuk badan usaha ini.</div>
      ) : queues.map((q) => <DeskQueue key={q.id} queue={q} busyRef={busyRef} onAction={onRowAction} onOpen={(row, queue) => setDetail({ row, queue })} />)}

      {detail && (
        <DeskRowDetail row={detail.row} queue={detail.queue} testPrefix="m-desk" inPlace={IN_PLACE} currentUser={currentUser} traceEnabled={false} onAction={handleAction}
          onOpenFull={(row, queue) => openRow(row, queue)} onClose={() => setDetail(null)} />
      )}
      {verifyRow && (
        <VerifyOrderDialog orderId={verifyRow.ref_id} orderNumber={verifyRow.number} customerName={verifyRow.title}
          onClose={() => setVerifyRow(null)}
          onVerified={(msg) => { setVerifyRow(null); flash(msg); load(); }}
          onOpenFull={() => { const r = verifyRow; setVerifyRow(null); onOpenOrder?.(r.ref_id); }} />
      )}
      {assignRow && (
        <AssignSalesDialog customer={assignRow} onClose={() => setAssignRow(null)}
          onDone={(msg) => { setAssignRow(null); flash(msg); load(); }} />
      )}
      {releaseRow && (
        <ReleaseToWarehouseDialog
          order={{ id: releaseRow.ref_id, number: releaseRow.number, title: releaseRow.title, entity_id: releaseRow.entity_id,
            order_lines: releaseRow.order_lines }}
          run={() => releaseOrder(releaseRow.ref_id)} onClose={() => setReleaseRow(null)}
          onDone={(res) => { const r = releaseRow; setReleaseRow(null); flash(releaseMessage(res, r.number)); load(); }} />
      )}
      {fulfillRow && (
        <FulfillmentDecisionDialog orderId={fulfillRow.ref_id} orderNumber={fulfillRow.number} customerName={fulfillRow.title}
          onClose={() => setFulfillRow(null)}
          onDecided={(msg) => { setFulfillRow(null); flash(msg); load(); }}
          onOpenFull={() => { const r = fulfillRow; setFulfillRow(null); onOpenOrder?.(r.ref_id); }} />
      )}
    </div>
  );
}
