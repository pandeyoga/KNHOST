/**
 * MobileSalesAdminDesk — Meja Admin Sales versi HP (cermin SalesAdminDesk desktop).
 *
 * Mesin & wewenang SAMA dengan desktop (workDeskApi): antrean dari `/sales-admin/desk`,
 * Verifikasi & Keputusan Pemenuhan memakai dialog yang sama (tampil sebagai lembar bawah
 * di HP), Konfirmasi langsung dari baris. Baris "Buka" diarahkan ke layar HP yang
 * menanganinya (pesanan / retur / permintaan internal / pesanan khusus); jenis lain
 * dibuka tampilan penuh.
 */
import { useCallback, useEffect, useState } from "react";
import { ChevronDown, Inbox, Layers, RefreshCw, ShieldAlert, ClipboardCheck } from "lucide-react";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import VerifyOrderDialog from "../../sales_admin/VerifyOrderDialog";
import FulfillmentDecisionDialog from "../../sales_admin/FulfillmentDecisionDialog";
import { ageTone, badgeClass, badgeLabel, confirmOrder, queueMeta, rowLink, salesAdminDesk } from "../../sales_admin/workDeskApi";

const PREVIEW = 5;
// ref_type → sub-halaman HP (menu Lainnya) atau tab Pesanan.
const MOBILE_TARGET = { sales_return: "returns", internal_request: "internal", special_order: "special" };

function DeskRow({ row, queue, busy, onAction }) {
  const age = ageTone(row.age_days);
  const isQty = queue.value_kind === "qty";
  const value = isQty ? `${formatQty(row.value)} ${row.unit || ""}`.trim() : queue.value_kind === "count" ? "" : formatCurrency(Number(row.value) || 0);
  return (
    <div className="m-list-row items-start" data-testid={`m-desk-row-${queue.id}-${row.row_key || row.ref_id}`}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[12px] font-bold text-[#0058CC]">{row.number}</span>
          {row.badge && <span className={`rounded-full border px-1.5 py-0.5 text-[9.5px] font-bold ${badgeClass(row.badge)}`}>{badgeLabel(row.badge)}</span>}
          <span className={`rounded-full border px-1.5 py-0.5 text-[9.5px] font-bold ${age.cls}`}>{age.label}</span>
        </div>
        <p className="truncate text-[12.5px] font-semibold text-[#1C1C1E]">{row.title}</p>
        {row.subtitle && <p className="truncate text-[10.5px] m-muted">{row.subtitle}</p>}
        {value && <p className="text-[11.5px] font-bold tabular-nums text-[#1C1C1E]">{value}</p>}
      </div>
      <button type="button" className={`${["verify", "confirm", "fulfill"].includes(row.action_kind) ? "primary-button" : "secondary-button"} m-press shrink-0 px-3 py-2 text-[11.5px]`}
        disabled={busy} onClick={() => onAction(row, queue)} data-testid={`m-desk-action-${queue.id}-${row.row_key || row.ref_id}`}>
        {busy ? "Memproses…" : (row.action || queue.action_label || "Buka")}
      </button>
    </div>
  );
}

function DeskQueue({ queue, busyRef, onAction }) {
  const [open, setOpen] = useState((queue.count || 0) > 0);
  const [all, setAll] = useState(false);
  const meta = queueMeta(queue.id);
  const Icon = meta.icon;
  const rows = Array.isArray(queue.rows) ? queue.rows : [];
  const shown = all ? rows : rows.slice(0, PREVIEW);
  const oldest = ageTone(queue.oldest_age_days);
  const total = queue.value_kind === "qty" ? `${formatQty(queue.total_value)} ${rows[0]?.unit || ""}`.trim()
    : queue.value_kind === "count" ? `${rows.length} dok` : formatCurrency(Number(queue.total_value) || 0);
  return (
    <div className="m-card overflow-hidden" data-testid={`m-desk-queue-${queue.id}`}>
      <button type="button" className="m-press flex w-full items-start gap-2.5 p-3 text-left" onClick={() => setOpen((v) => !v)} aria-expanded={open} data-testid={`m-desk-queue-toggle-${queue.id}`}>
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg" style={{ background: meta.bg }}><Icon size={17} style={{ color: meta.tone }} /></span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="text-[13px] font-bold leading-tight">{queue.label}</span>
            <span className="rounded-full px-2 py-0.5 text-[10.5px] font-bold tabular-nums" style={{ background: meta.bg, color: meta.tone }} data-testid={`m-desk-count-${queue.id}`}>{queue.count || 0}</span>
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10.5px] m-muted">
            <span className="font-semibold tabular-nums text-[#1C1C1E]">{total}</span>
            {(queue.count || 0) > 0 && <span className={`rounded-full border px-1.5 py-0.5 text-[9.5px] font-bold ${oldest.cls}`}>tertua {oldest.label}</span>}
          </span>
        </span>
        <ChevronDown size={16} className={`mt-1 shrink-0 text-[#8E8E93] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-[#F2F3F5] px-3">
          {queue.hint && <p className="pt-2 text-[10.5px] leading-relaxed m-muted">{queue.hint}</p>}
          {rows.length === 0 ? (
            <p className="py-5 text-center text-[11.5px] m-muted" data-testid={`m-desk-empty-${queue.id}`}>Antrean bersih — tidak ada yang perlu ditindak.</p>
          ) : shown.map((row, i) => (
            <DeskRow key={`${row.ref_type}-${row.ref_id}-${row.number || i}`} row={row} queue={queue} busy={busyRef === row.ref_id} onAction={onAction} />
          ))}
          {rows.length > PREVIEW && (
            <button type="button" className="w-full py-2.5 text-[12px] font-semibold text-[#0058CC]" onClick={() => setAll((v) => !v)} data-testid={`m-desk-see-all-${queue.id}`}>
              {all ? "Tampilkan lebih sedikit" : `Lihat semua ${rows.length} baris`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function MobileSalesAdminDesk({ selectedEntity, onOpenOrder, onOpenSub, onOpenFull }) {
  const [desk, setDesk] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [errorAction, setErrorAction] = useState(null);
  const [toast, setToast] = useState("");
  const [busyRef, setBusyRef] = useState("");
  const [verifyRow, setVerifyRow] = useState(null);
  const [fulfillRow, setFulfillRow] = useState(null);

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

  const flash = (m) => { setToast(m); setTimeout(() => setToast(""), 5000); };

  async function doConfirm(row) {
    setBusyRef(row.ref_id); setError(""); setErrorAction(null);
    try {
      const res = await confirmOrder(row.ref_id);
      flash(`${res?.number || row.number} dikonfirmasi — tugas gudang lahir.`);
      await load();
    } catch (e) {
      const msg = apiErrorText(e, "Gagal mengonfirmasi pesanan.");
      setError(msg);
      if (/verifikasi/i.test(msg)) setErrorAction({ label: "Verifikasi sekarang", run: () => setVerifyRow(row) });
    } finally { setBusyRef(""); }
  }

  function openRow(row, queue) {
    const sub = MOBILE_TARGET[row.ref_type];
    if (sub) { onOpenSub?.(sub, row.ref_id); return; }
    if (row.ref_type === "sales_order" || row.order_id) { onOpenOrder?.(row.order_id || row.ref_id); return; }
    const link = rowLink(row, queue?.id, "sales_admin");
    onOpenFull?.(link.nav_id, link.view);
  }

  function handleAction(row, queue) {
    if (row.action_kind === "verify") return setVerifyRow(row);
    if (row.action_kind === "fulfill") return setFulfillRow(row);
    if (row.action_kind === "confirm") return doConfirm(row);
    return openRow(row, queue);
  }

  const queues = Array.isArray(desk?.queues) ? desk.queues : [];
  const openItems = desk?.totals?.open_items || 0;
  const totalMoney = queues.filter((q) => q.value_kind !== "qty").reduce((s, q) => s + (q.total_value || 0), 0);
  const oldest = Math.max(0, ...queues.map((q) => q.oldest_age_days || 0));

  return (
    <div className="space-y-3" data-testid="m-sales-admin-desk">
      <div className="flex items-center justify-between px-0.5">
        <div className="flex items-center gap-2"><ClipboardCheck size={16} className="text-[#0058CC]" /><h2 className="m-section-title" data-testid="m-desk-title">Meja Admin Sales</h2></div>
        <button onClick={load} className="text-[#6B6B73]" aria-label="Muat ulang" data-testid="m-desk-refresh"><RefreshCw size={15} className={loading ? "animate-spin" : ""} /></button>
      </div>
      {toast && <div className="notice-bar success text-xs" data-testid="m-desk-toast">{toast}</div>}
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
          { icon: ShieldAlert, label: "Umur tertua", value: oldest > 0 ? `${oldest} hari` : "hari ini", bg: "rgba(255,59,48,.14)", id: "oldest" },
        ].map((m) => (
          <div key={m.id} className="m-card p-2.5" data-testid={`m-desk-metric-${m.id}`}>
            <span className="grid h-7 w-7 place-items-center rounded-lg" style={{ background: m.bg }}><m.icon size={14} /></span>
            <p className="mt-1.5 text-[9.5px] font-bold uppercase tracking-wide text-[#8E8E93]">{m.label}</p>
            <p className="truncate text-[13px] font-bold tabular-nums">{m.value}</p>
          </div>
        ))}
      </div>
      <p className="px-0.5 text-[11px] leading-relaxed m-muted">
        Periksa kelengkapan → putuskan pemenuhan → konfirmasi → dokumen → retur. Nilai besar, kredit & harga khusus tetap keputusan manajer.
      </p>
      {(desk?.not_my_desk || []).length > 0 && (
        <div className="rounded-xl border border-[#CBDFFF] bg-[#F2F7FF] px-3 py-2" data-testid="m-desk-not-mine">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#0058CC]">Bukan wewenang meja ini — ada di Meja Finance</p>
          <p className="text-[11px] text-[#31465F]">{desk.not_my_desk.join(" · ")}</p>
        </div>
      )}
      {loading && !desk ? (
        <div className="space-y-2.5">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-xl bg-[#ECEDF0]" />)}</div>
      ) : queues.length === 0 ? (
        <div className="py-12 text-center text-[12px] m-muted" data-testid="m-desk-empty">Belum ada antrean untuk badan usaha ini.</div>
      ) : queues.map((q) => <DeskQueue key={q.id} queue={q} busyRef={busyRef} onAction={handleAction} />)}

      {verifyRow && (
        <VerifyOrderDialog orderId={verifyRow.ref_id} orderNumber={verifyRow.number} customerName={verifyRow.title}
          onClose={() => setVerifyRow(null)}
          onVerified={(msg) => { setVerifyRow(null); flash(msg); load(); }}
          onOpenFull={() => { const r = verifyRow; setVerifyRow(null); onOpenOrder?.(r.ref_id); }} />
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
