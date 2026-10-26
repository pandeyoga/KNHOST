/**
 * MobileShell v2 — SATU kerangka untuk keempat aplikasi HP (Sales, MD, Gudang, Ops). Fase 3 · P7 (L-09, D-26).
 *
 * Dulu tiga gaya: Sales & MD menggambar app bar/tab bar sendiri (MD berjudul "· MD"), Ops/Gudang memakai cangkang lama
 * dengan ikon monitor + keluar di app bar dan pil merah jumlah notifikasi (tanpa lembar notifikasi). Kini:
 *  · app bar seragam: tanda merek · "Halo, <nama depan>" · PT aktif + peran · tombol LONCENG → `NotifSheet` (semua peran);
 *  · tab bawah ≤ 5, TERKENDALI (`tab`/`onTabChange`) atau mandiri (`initialTab`), lencana per tab (`badge`);
 *  · tab terakhir selalu "Lainnya" (`moreTab` dari aplikasi, bawaan = `MobileAccountMenu`: profil, PT, push/pasang,
 *    SATU "Tampilan desktop", Keluar);
 *  · satu-satunya tempat sinkron push (`syncPushSubscription`), muat-ulang lonceng (60 dtk / kembali ke aplikasi /
 *    pesan service worker) dan banner offline — supaya tidak dobel per aplikasi.
 *
 * Props utama: `user` · `entities` · `selectedEntity` · `onSelectEntity` · `tabs` [{id, label, icon, render({setTab}),
 *   badge?, badgeTestId?, flush?}] · `tab`/`onTabChange` | `initialTab` · `moreTab` ({label?, render}) · `notifications`,
 *   `unreadCount`, `notifProps`, `onMarkAllRead`, `onMarkRead`, `onPollNotifications`, `onOpenNotif(n)` (kembalikan
 *   `false` bila lembar tetap terbuka), `notifDecideOf(n)`, `initialNotifOpen` · `onForceDesktop` · `onLogout`
 *   · `roleTag` (teks peran di baris kedua) · `topSlot` · `testId` · `ids` (penimpa testid MD: tab/tabbar/view/notif).
 */
import { useEffect, useState } from "react";
import { Bell, Layers, Menu } from "lucide-react";
import { roleLabel } from "../../config/roles";
import { entityShortById } from "../../utils/entityLabel";
import { NotifSheet } from "../sales/mobile/MobileNotifSheet";
import { syncPushSubscription } from "../sales/mobile/MobilePwa";
import MobileAccountMenu from "./MobileAccountMenu";
import OfflineBanner from "./OfflineBanner";

export const MAX_MOBILE_TABS = 5;
const DEFAULT_IDS = { tab: "mobile-tab-btn-", tabbar: "mobile-tabbar", view: "mobile-view-", notif: "mobile-notif-btn", count: "mobile-notif-count" };
const badgeText = (n) => (n > 99 ? "99+" : String(n));

/** Lonceng HP: muat ulang tiap 60 dtk saat terlihat, saat kembali ke aplikasi, dan seketika saat push masuk. */
function useNotifPolling(onPoll, onPushOpen) {
  useEffect(() => {
    if (!onPoll) return undefined;
    const tick = () => { if (document.visibilityState === "visible") onPoll(); };
    tick();
    const id = setInterval(tick, 60000);
    document.addEventListener("visibilitychange", tick);
    const onMsg = (e) => {
      if (!String(e.data?.type || "").startsWith("kn-push")) return;
      onPoll();
      if (e.data.type === "kn-push-open") onPushOpen();
    };
    navigator.serviceWorker?.addEventListener?.("message", onMsg);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", tick); navigator.serviceWorker?.removeEventListener?.("message", onMsg); };
  }, [onPoll]);   // eslint-disable-line react-hooks/exhaustive-deps
}

export default function MobileShell({
  user, entities = [], selectedEntity, onSelectEntity, tabs = [], tab: tabProp, onTabChange, initialTab, moreTab,
  notifications = [], unreadCount = 0, notifProps = {}, onMarkAllRead, onMarkRead, onPollNotifications, onOpenNotif,
  notifDecideOf, initialNotifOpen = false, onForceDesktop, onLogout, roleTag, topSlot = null,
  testId = "mobile-shell", ids: idsProp,
}) {
  const ids = { ...DEFAULT_IDS, ...(idsProp || {}) };
  const more = {
    id: "more", label: moreTab?.label || "Lainnya", icon: Menu, badge: moreTab?.badge,
    render: moreTab?.render || (() => (
      <MobileAccountMenu user={user} entities={entities} selectedEntity={selectedEntity} onSelectEntity={onSelectEntity}
        onForceDesktop={onForceDesktop} onLogout={onLogout} />
    )),
  };
  // Tab terakhir baku "Lainnya"; bilah dipotong ke 5 (aplikasi yang memberi lebih dari 4 tab kerja = galat desain).
  const allTabs = [...tabs.filter((t) => t.id !== "more").slice(0, MAX_MOBILE_TABS - 1), more];
  const [ownTab, setOwnTab] = useState(initialTab || allTabs[0]?.id);
  useEffect(() => { if (initialTab) setOwnTab(initialTab); }, [initialTab]);
  const controlled = tabProp !== undefined;
  const tab = controlled ? tabProp : ownTab;
  const setTab = (id) => { if (controlled) onTabChange?.(id); else { setOwnTab(id); onTabChange?.(id); } };
  const active = allTabs.find((t) => t.id === tab) || allTabs[0];

  const [notifOpen, setNotifOpen] = useState(!!initialNotifOpen);
  useNotifPolling(onPollNotifications, () => setNotifOpen(true));
  // Push: SATU sinkron per akun untuk semua aplikasi HP (dulu Sales & MD memanggil sendiri-sendiri).
  useEffect(() => { syncPushSubscription(); }, [user?.id]);
  const openNotif = (n) => {
    if (!n.read) onMarkRead?.(n.id);
    if (onOpenNotif?.(n) === false) return;
    setNotifOpen(false);
  };

  const firstName = String(user?.name || "").split(" ")[0];
  const place = entityShortById(entities, selectedEntity);
  const who = roleTag === undefined ? (user?.role_label || roleLabel(user?.role)) : roleTag;
  return (
    <div className="m-shell" data-testid={testId}>
      <header className="m-appbar" data-testid="mobile-appbar">
        <div className="m-brand-mark"><Layers size={16} /></div>
        <div className="m-title">
          <span className="t1" data-testid="mobile-appbar-title">Halo{firstName ? `, ${firstName}` : ""}</span>
          <span className="t2" data-testid="mobile-appbar-subtitle">{[place, who].filter(Boolean).join(" · ")}</span>
        </div>
        <button type="button" className="m-act" data-testid={ids.notif} onClick={() => setNotifOpen(true)} aria-label="Notifikasi">
          <Bell size={18} />
          {unreadCount > 0 && <span className="m-badge" data-testid={ids.count}>{badgeText(unreadCount)}</span>}
        </button>
      </header>

      {notifOpen && (
        <NotifSheet {...notifProps} unreadCount={unreadCount} notifications={notifications} onClose={() => setNotifOpen(false)}
          onMarkAll={onMarkAllRead} onMarkRead={onMarkRead} onOpen={openNotif} decideOf={notifDecideOf} />
      )}

      <main className={`m-main ${active?.flush ? "m-flush" : ""}`} data-testid={`${ids.view}${active?.id}`}>
        <OfflineBanner />
        {topSlot}
        {active?.render?.({ setTab })}
      </main>

      <nav className="m-tabbar" data-testid={ids.tabbar}>
        {allTabs.map((t) => {
          const Icon = t.icon; const on = t.id === active?.id;
          return (
            <button type="button" key={t.id} data-testid={`${ids.tab}${t.id}`} className={`m-tab ${on ? "active" : ""}`} onClick={() => setTab(t.id)} aria-current={on}>
              <span className="m-tab-ico">
                <Icon size={21} strokeWidth={on ? 2.4 : 2} />
                {Number(t.badge) > 0 && <span className="m-tab-badge" data-testid={t.badgeTestId || `${ids.tab}${t.id}-badge`}>{badgeText(Number(t.badge))}</span>}
              </span>
              {t.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
