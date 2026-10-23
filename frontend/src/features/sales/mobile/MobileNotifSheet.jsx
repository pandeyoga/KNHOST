import { useMemo, useState } from "react";
import { X, CheckCheck, Check, AlertTriangle, Info, ArrowUpCircle, UserCheck, Volume2, VolumeX, CheckCircle2, Loader2, ChevronRight } from "lucide-react";
import { canActOn, typeLabel, SEV_CHIPS, timeAgo } from "../../../components/NotificationCenter";
import { roleLabel } from "../../../config/roles";
import { isSirenMuted, setSirenMuted, playSiren } from "../../../utils/sirenAlarm";
import { MobilePushBanner } from "./MobilePwa";
import KNSelect from "../../../components/KNSelect";

const SEV_STYLE = {
  critical: { bg: "bg-[#FFECEB]", fg: "text-[#C0261B]", Icon: AlertTriangle },
  warning: { bg: "bg-[#FFF4E0]", fg: "text-[#B25E00]", Icon: AlertTriangle },
  info: { bg: "bg-[#EAF2FF]", fg: "text-[#0058CC]", Icon: Info },
};

function AddrTag({ n }) {
  if (n.recipient_user) return <span className="inline-flex items-center gap-0.5 rounded-full bg-[#E6F6EC] px-1.5 py-[1px] text-[9.5px] font-bold text-[#1B7F4B]" data-testid={`mobile-notif-addr-me-${n.id}`}><UserCheck size={9} /> Untuk Anda</span>;
  if (n.recipient_role && n.recipient_role !== "all") return <span className="rounded-full bg-[#F1ECFA] px-1.5 py-[1px] text-[9.5px] font-bold text-[#6B219A]" data-testid={`mobile-notif-addr-role-${n.id}`}>{roleLabel(n.recipient_role)}</span>;
  return <span className="rounded-full bg-[#F2F3F5] px-1.5 py-[1px] text-[9.5px] font-bold text-[#6B6B73]" data-testid={`mobile-notif-addr-all-${n.id}`}>Umum</span>;
}

function NotifRow({ n, onOpen, onMarkRead, canApprove, approving, onApprove }) {
  const sev = SEV_STYLE[n.severity] || SEV_STYLE.info;
  const Icon = n.type === "escalation" ? ArrowUpCircle : sev.Icon;
  return (
    <div role="button" tabIndex={0} onClick={() => onOpen?.(n)} data-testid={`mobile-notif-${n.id}`}
      className={`flex gap-2.5 border-b border-[#F2F3F5] py-3 last:border-b-0 ${n.read ? "opacity-75" : ""}`}>
      <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full ${sev.bg} ${sev.fg}`}><Icon size={15} /></span>
      <div className="min-w-0 flex-1">
        <p className={`text-[12.5px] leading-snug ${n.read ? "font-medium text-[#3C3C43]" : "font-bold text-[#1C1C1E]"}`}>
          {n.title || typeLabel(n.type)}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          {n.type === "escalation" && <span className="inline-flex items-center gap-0.5 rounded-full bg-[#FFECEB] px-1.5 py-[1px] text-[9.5px] font-bold text-[#C0261B]" data-testid={`mobile-notif-escalation-${n.id}`}><ArrowUpCircle size={9} /> Eskalasi</span>}
          <AddrTag n={n} />
        </div>
        {n.body && <p className="mt-1 text-[11.5px] leading-snug text-[#6B6B73]">{n.body}</p>}
        <div className="mt-1 flex items-center justify-between gap-2">
          <p className="text-[10px] text-[#AEAEB2]" data-testid={`mobile-notif-meta-${n.id}`}>{timeAgo(n.created_at)} · {typeLabel(n.type)}</p>
          {canApprove && (
            <button type="button" data-testid={`mobile-notif-approve-${n.id}`} disabled={approving}
              onClick={(e) => { e.stopPropagation(); onApprove(n); }}
              className="inline-flex items-center gap-1 rounded-full bg-[#1B7F4B] px-2.5 py-1 text-[11px] font-bold text-white disabled:opacity-60">
              {approving ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />} {approving ? "Memproses…" : "Setujui"}
            </button>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-col items-center justify-between gap-2">
        {!n.read ? (
          <button type="button" aria-label="Tandai dibaca" data-testid={`mobile-notif-read-${n.id}`}
            onClick={(e) => { e.stopPropagation(); onMarkRead?.(n.id); }}
            className="grid h-7 w-7 place-items-center rounded-full border border-[#CBDFFF] bg-[#F2F7FF] text-[#0058CC]"><Check size={13} /></button>
        ) : <span className="h-7 w-7" />}
        {n.link && <ChevronRight size={15} className="text-[#C7C7CC]" />}
      </div>
    </div>
  );
}

/** Lembar notifikasi HP — fitur setara lonceng desktop (filter, alamat, setujui, muat lebih banyak). */
export function NotifSheet({ notifications = [], unreadCount, onClose, onMarkAll, onOpen, onMarkRead, total = 0, hasMore = false, onLoadMore, onApprove, currentUserRole = "" }) {
  const [sev, setSev] = useState("");
  const [type, setType] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [approving, setApproving] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [muted, setMuted] = useState(isSirenMuted());

  const types = useMemo(() => {
    const c = {};
    notifications.forEach((n) => { c[n.type] = (c[n.type] || 0) + 1; });
    return Object.entries(c).map(([k, v]) => ({ value: k, label: `${typeLabel(k)} (${v})` })).sort((a, b) => a.label.localeCompare(b.label));
  }, [notifications]);
  const filtered = useMemo(() => notifications.filter((n) => (!sev || (n.severity || "info") === sev) && (!type || n.type === type) && (!unreadOnly || !n.read)), [notifications, sev, type, unreadOnly]);
  const unread = unreadCount ?? notifications.filter((n) => !n.read).length;
  const hasFilter = Boolean(sev || type || unreadOnly);

  const approve = async (n) => { setApproving(n.id); try { await onApprove?.(n); } finally { setApproving(null); } };
  const toggleSiren = () => { const next = !muted; setSirenMuted(next); setMuted(next); if (!next) playSiren(1); };
  const loadMore = async () => { setLoadingMore(true); try { await onLoadMore?.(); } finally { setLoadingMore(false); } };
  const chip = (on) => `shrink-0 rounded-full border px-3 py-1 text-[11.5px] font-semibold ${on ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E5E5EA] bg-white text-[#3C3C43]"}`;

  return (
    <div className="m-sheet-wrap" data-testid="mobile-notif-sheet">
      <div className="m-sheet-backdrop" onClick={onClose} />
      <div className="m-sheet">
        <div className="m-sheet-grip" />
        <div className="flex items-center justify-between gap-2 px-4 pb-2">
          <div className="min-w-0">
            <h3 className="m-section-title">Notifikasi</h3>
            <p className="text-[10.5px] text-[#8E8E93]" data-testid="mobile-notif-unread-count">{unread} belum dibaca{total > notifications.length ? ` · ${total} total` : ""}</p>
          </div>
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={toggleSiren} data-testid="mobile-notif-siren" aria-label="Sirine alarm"
              className="grid h-8 w-8 place-items-center rounded-full bg-[#F2F3F5] text-[#3C3C43]">{muted ? <VolumeX size={14} /> : <Volume2 size={14} />}</button>
            {onMarkAll && unread > 0 && (
              <button data-testid="mobile-notif-markall" onClick={onMarkAll} className="inline-flex h-8 items-center gap-1 rounded-full bg-[#EAF2FF] px-2.5 text-[11.5px] font-semibold text-[#0058CC]"><CheckCheck size={13} /> Semua dibaca</button>
            )}
            <button onClick={onClose} aria-label="Tutup" className="grid h-8 w-8 place-items-center rounded-full bg-[#F2F3F5] text-[#6B6B73]" data-testid="mobile-notif-close"><X size={16} /></button>
          </div>
        </div>
        <div className="border-b border-[#EFF0F2] px-4 pb-2" data-testid="mobile-notif-filters">
          <div className="no-scrollbar -mx-4 flex gap-1.5 overflow-x-auto px-4" style={{ maskImage: "linear-gradient(90deg,#000 88%,transparent)", WebkitMaskImage: "linear-gradient(90deg,#000 88%,transparent)" }}>
            {SEV_CHIPS.map((c) => (
              <button key={c.key || "all"} type="button" data-testid={`mobile-notif-filter-sev-${c.key || "all"}`} className={chip(sev === c.key)} onClick={() => setSev(c.key)}>{c.label}</button>
            ))}
            <button type="button" data-testid="mobile-notif-filter-unread" className={chip(unreadOnly)} onClick={() => setUnreadOnly((v) => !v)}>Belum dibaca</button>
            <span className="w-4 shrink-0" />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <KNSelect data-testid="mobile-notif-filter-type" value={type} onValueChange={setType} aria-label="Filter jenis notifikasi"
              className="min-w-0 flex-1 rounded-lg border border-[#E5E5EA] bg-white !px-2 !py-1.5 text-[12px]"
              options={[{ value: "", label: "Semua jenis" }, ...types.map((t) => ({ value: t.value, label: t.label }))]} />
            {hasFilter && <button type="button" data-testid="mobile-notif-filter-reset" onClick={() => { setSev(""); setType(""); setUnreadOnly(false); }} className="shrink-0 text-[11.5px] font-bold text-[#0058CC]">Reset</button>}
          </div>
          <p className="mt-1.5 text-[10.5px] text-[#8E8E93]" data-testid="mobile-notif-filter-count">Menampilkan {filtered.length} dari {notifications.length} notifikasi</p>
        </div>
        <div className="m-sheet-scroll px-4" data-testid="mobile-notif-list">
          <MobilePushBanner />
          {notifications.length === 0 && <div className="py-12 text-center text-[13px] m-muted" data-testid="mobile-notif-empty">Tidak ada notifikasi. Sistem dalam kondisi baik.</div>}
          {notifications.length > 0 && filtered.length === 0 && <div className="py-10 text-center text-[12.5px] m-muted" data-testid="mobile-notif-empty-filter">Tidak ada notifikasi yang cocok dengan filter ini.</div>}
          {filtered.map((n) => (
            <NotifRow key={n.id} n={n} onOpen={onOpen} onMarkRead={onMarkRead} onApprove={approve} approving={approving === n.id}
              canApprove={["po_approve", "vendor_bill_approve"].includes(n.action_type) && !n.read && !!onApprove && canActOn(currentUserRole, n.action_role || "manager", n.action_type)} />
          ))}
          {hasMore && (
            <button type="button" data-testid="mobile-notif-load-more" disabled={loadingMore} onClick={loadMore}
              className="my-3 w-full rounded-xl border border-[#CBDFFF] bg-[#F2F7FF] py-2.5 text-[12.5px] font-semibold text-[#0058CC]">
              {loadingMore ? "Memuat…" : `Muat lebih banyak (${Math.max(0, total - notifications.length)} lagi)`}
            </button>
          )}
          {!hasMore && notifications.length > 0 && total > 0 && (
            <p className="py-3 text-center text-[10.5px] text-[#AEAEB2]" data-testid="mobile-notif-list-end">Sudah sampai baris terakhir · {notifications.length} dari {total} notifikasi</p>
          )}
        </div>
      </div>
    </div>
  );
}
