import { useState, useEffect } from "react";
import { formatUnitTotals } from "./utils/qtyByUnit";
import "./App.css";
import { LoginScreen, MetricCard, Sidebar, TopBar } from "./components/CoreWidgets";
import { formatQty } from "./utils/formatters";
import useIsMobile from "./hooks/useIsMobile";
// Fase 3 · P1 — pemilih aplikasi HP diekstrak (wilayah P7); navigasi & sinkron sesi diekstrak ke hook.
import MobileAppSwitch from "./features/mobile/MobileAppSwitch";
import useAppNavigation from "./hooks/useAppNavigation";
import useSessionSync from "./hooks/useSessionSync";
import DetailDrawer from "./components/DetailDrawer";
import TourMenu from "./components/TourMenu";
import OnboardingPanel from "./components/OnboardingPanel";
import EntitySwitcher from "./components/EntitySwitcher";
import NotificationCenter from "./components/NotificationCenter";
import { PAGE_META, breadcrumbFor, buildNavGroups, isComingSoonView, isHomeView, resolveActiveNavId, hubForView } from "./config/navigationConfig";
import CommandPalette from "./components/CommandPalette";
import useDeepLinks from "./hooks/useDeepLinks";
import useViewDeepLink from "./hooks/useViewDeepLink";
import { useAppActions } from "./hooks/useAppActions";
import { setActiveEntity } from "./services/apiClient";
import axios, { API } from "./services/apiClient";
import GuidedTour from "./components/GuidedTour";
import AppViewRouter from "./AppViewRouter";
import ErrorBoundary from "./components/ErrorBoundary";
import PeriodUnlockBanner from "./components/PeriodUnlockBanner";
import ScopeReadOnlyBanner from "./components/ScopeReadOnlyBanner";
import ArchivedReadOnlyBanner from "./components/ArchivedReadOnlyBanner";
import { EntityScopeProvider } from "./context/EntityScopeContext";
import { entityShortById } from "./utils/entityLabel";
import { isGroupScope } from "./utils/writeScope";
import PublicVerify from "./features/documents/PublicVerify";
import { setAccessContext, roleIs } from "./config/roles";
import {
  Archive,
  Boxes,
  Building2,
  Clock3,
  PackageCheck,
  Sparkles,
  Smartphone,
} from "lucide-react";

function App() {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem("kn_user") || "null"));
  setAccessContext(user);   // L01 LN-015 — menu/tab mengikuti izin EFEKTIF + tab yang disembunyikan peran
  const [token, setToken] = useState(() => localStorage.getItem("kn_token") || "");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Fase 3 · P1 — satu jalur navigasi (alias + preset): hooks/useAppNavigation.js.
  const {
    activeView, setActiveView, activeNavId, setActiveNavId, wmsInitialTab, focusDoc, setFocusDoc,
    viewPreset, handleNavSelect, navigateTo, openDocument, lastFocusRef,
  } = useAppNavigation({ role: user?.role, setSidebarOpen });
  const [data, setData] = useState({ products: [], customers: [], orders: [], warehouses: [], metrics: {} });
  const [movements, setMovements] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [users, setUsers] = useState([]);
  const [uoms, setUoms] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [onboarding, setOnboarding] = useState(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [permissions, setPermissions] = useState({ matrix: {}, actions: [] });
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditFilters, setAuditFilters] = useState({ actor: "", module: "", action: "", date_from: "", date_to: "" });

  // Guided Tour state
  const [activeTour, setActiveTour] = useState(null);
  const [showTourMenu, setShowTourMenu] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");
  const [activeDetail, setActiveDetail] = useState(null);
  // Desktop: sidebar bisa di-hide/show (persist). Mobile (<=900px) pakai drawer (sidebarOpen).
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => typeof window !== "undefined" && localStorage.getItem("kn_sidebar_collapsed") === "1"
  );
  const handleToggleSidebar = () => {
    if (typeof window !== "undefined" && window.innerWidth <= 900) {
      setSidebarOpen((v) => !v);
    } else {
      setSidebarCollapsed((v) => {
        const nv = !v;
        try { localStorage.setItem("kn_sidebar_collapsed", nv ? "1" : "0"); } catch (_) { /* noop */ }
        return nv;
      });
    }
  };
  // Semua deep-link global (Pusat Pengaturan · Jejak Dokumen · hub R&D) — lihat
  // hooks/useDeepLinks.js. `ready` menahan jangkar QR sampai pengguna masuk.
  const {
    configFocus, clearConfigFocus, traceAnchor, clearTraceAnchor, rndFocus, clearRndFocus,
    caseFocus, clearCaseFocus, logisticsFocus, clearLogisticsFocus,
  } = useDeepLinks({
    setActiveNavId, setActiveView, setSidebarOpen, ready: Boolean(user),
    role: user?.role,   // fase 3 · P2 — openConfig → layar Pengaturan domain yang boleh dibuka peran ini
    // FB-02 — dari Logistik → detail Pesanan (reuse jalur focusDoc EPIC6).
    onOpenOrder: (orderId) => openDocument({ view: "orders", nav_id: "sales-orders", focus_type: "sales_order", focus_id: orderId }),
  });
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [breakdown, setBreakdown] = useState(null);
  const [cart, setCart] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [selectedAddress, setSelectedAddress] = useState("");
  const [search, setSearch] = useState("");
  // UAT 24 Okt (audit UI tahap 2) — G0-21: pesan awal "Sistem siap. Stok reservation dikunci 3 hari." (campur Inggris)
  // selalu tampil & mendesak pemilih badan usaha. Kini kosong — bilah hanya muncul bila ada pesan sungguhan.
  const [notice, setNotice] = useState("");
  const [lastDocument, setLastDocument] = useState(null);
  const [lastLabel, setLastLabel] = useState(null);
  const [loading, setLoading] = useState(false);

  // Multi-Entity + Notification Center (Fase 0)
  const [entities, setEntities] = useState([]);
  const [entityContext, setEntityContext] = useState(() => JSON.parse(localStorage.getItem("kn_entity_ctx") || "null"));
  const [selectedEntity, setSelectedEntity] = useState(() => localStorage.getItem("kn_entity") || "all");
  const [notifications, setNotifications] = useState([]);
  const [notifMeta, setNotifMeta] = useState({ page: 1, total: 0, has_more: false });
  const [unreadCount, setUnreadCount] = useState(0);

  // Configuration Foundation (Fase 1A) consumed by Sales/Orders (Fase 1B)
  const [settings, setSettings] = useState({});
  const [paymentTerms, setPaymentTerms] = useState([]);

  // F-6 — device-aware: sales di HP dapat tampilan mobile-first dedicated.
  const isMobile = useIsMobile();
  const [forceDesktop, setForceDesktop] = useState(() => localStorage.getItem("kn_force_desktop") === "1");
  const [mobileVisit, setMobileVisit] = useState(false);
  // Test affordance (default OFF): set localStorage kn_force_mobile="1" untuk merender
  // MobileSalesApp di lebar berapa pun (verifikasi UI mobile saat automasi memaksa desktop).
  const [forceMobile] = useState(() => typeof window !== "undefined" && localStorage.getItem("kn_force_mobile") === "1");

  const onSelectEntity = (id) => {
    if (id !== selectedEntity) {
      // KN-D20 — keranjang & pelanggan hidup DI ATAS key remount, jadi tanpa ini keranjang
      // PT lama terbawa ke PT baru dan distempel entity_id baru saat submit.
      setCart([]);
      setSelectedCustomer(null);
      setSelectedAddress("");
      setBreakdown(null);
    }
    setSelectedEntity(id);
    localStorage.setItem("kn_entity", id);
    setActiveEntity(id);  // sinkron header X-Entity-Id sebelum view anak re-fetch
  };

  // Pastikan header X-Entity-Id ter-set sejak awal (restore session / refresh).
  useEffect(() => { setActiveEntity(selectedEntity || "all"); }, [selectedEntity]);

  // Auto-hide notice transien (mis. 'Login berhasil ...') agar tidak menetap permanen di TopBar.
  useEffect(() => {
    if (!notice) return undefined;
    const t = setTimeout(() => setNotice(""), 5000);
    return () => clearTimeout(t);
  }, [notice]);

  // FASE E-8 · peran kustom · landing per peran — hooks/useSessionSync.js (diekstrak fase 3 · P1).
  const { rolesVersion } = useSessionSync({ token, user, setUser, setEntityContext, setEntities, setActiveView, setActiveNavId });

  // Switcher: cross-entity (admin/manager) lihat SEMUA entitas aktif; single-entity terkunci.
  const canSwitchEntity = entityContext
    ? entityContext.can_switch_entity !== false
    : entities.length > 1;
  const allowedEntityIds = entityContext?.allowed_entity_ids || entities.map((e) => e.id);
  const switcherEntities = canSwitchEntity
    ? entities
    : entities.filter((e) => allowedEntityIds.includes(e.id));

  // FASE E-3 (user story 7) — mode "Semua Entitas" = HANYA LIHAT. Pita peringatan
  // muncul selama mode itu aktif, dan berdenyut sekali lagi tiap kali server
  // menolak sebuah penyimpanan (event dari interseptor `apiClient`).
  const groupScope = isGroupScope(selectedEntity) && canSwitchEntity;
  const archivedEntities = entityContext?.archived_entities || [];
  const archivedActive = archivedEntities.find((e) => e.id === selectedEntity);
  const [scopeFlash, setScopeFlash] = useState(0);
  useEffect(() => {
    const onBlocked = () => setScopeFlash((n) => n + 1);
    window.addEventListener("kn:scope-blocked", onBlocked);
    return () => window.removeEventListener("kn:scope-blocked", onBlocked);
  }, []);

  // All async actions + side-effects live in this hook (SSOT for business logic).
  const actions = useAppActions({
    // values
    user, token, auditFilters, selectedCustomer, selectedAddress, cart, data, selectedEntity,
    // setters
    setUser, setToken, setActiveView, setNotice, setOnboarding, setShowOnboarding,
    setData, setTemplates, setUoms, setMovements, setTasks, setUsers, setPermissions, setAuditLogs,
    setSelectedCustomer, setSelectedAddress, setSelectedProduct, setBreakdown,
    setCart, setLastDocument, setLastLabel, setPreviewHtml,
    setActiveDetail, setLoading, setEntities, setNotifications, setUnreadCount,
    setNotifMeta,
    setSettings, setPaymentTerms, setEntityContext, setSelectedEntity,
    setActiveNavId,
  });
  const {
    login, logout, showMetricDetail, loadAll,
    markNotificationRead, markAllNotificationsRead, generateNotifications,
    loadMoreNotifications,
    approveFromNotification,
  } = actions;

  // ─── FASE E-4 — alamat untuk setiap layar (`?view=...&tab=...&entity=...`) ───
  // Satu layar sekarang bisa di-bookmark & dibagikan; menyegarkan halaman tidak
  // lagi melempar pengguna ke halaman depan peran.
  useViewDeepLink({
    role: user?.role,
    // Peran kustom (cr_*) baru dikenal navigasi setelah /api/roles terdaftar — tunggu dulu.
    ready: Boolean(user && token) && (!String(user?.role || "").startsWith("cr_") || rolesVersion > 0),
    activeView,
    activeEntity: selectedEntity,
    onNavigate: handleNavSelect,
    onPickEntity: onSelectEntity,
    onOpenDoc: openDocument,
  });

  const navGroups = buildNavGroups(user?.role, {
    withHeadings: true,   // fase 3 · P1 — sub-judul di dalam grup (L-05)
    showComingSoon: settings?.ui?.show_coming_soon !== false,
    comingSoonCollapsed: settings?.ui?.coming_soon_collapsed !== false,
  });
  // Klasifikasi view (SSOT di navigationConfig): coming-soon & halaman landing role.
  const isComingSoon = isComingSoonView(activeView);
  const showHomeWidgets = isHomeView(activeView);

  const nav = navGroups; // passed to new Sidebar (groups prop)
  // Poin 11 — highlight sidebar SELALU turunan dari activeView (cegah desync saat navigasi non-sidebar).
  const effectiveNavId = resolveActiveNavId(activeView, activeNavId, user?.role);

  // Halaman verifikasi dokumen PUBLIK (tanpa login) — di-handle sebelum gate auth.
  const _verifyMatch = typeof window !== "undefined" && window.location.pathname.match(/^\/verify-document\/(.+)$/);
  if (_verifyMatch) return <PublicVerify code={decodeURIComponent(_verifyMatch[1])} />;

  // Gate auth. Token WAJIB ada, bukan hanya profil pengguna: bila `kn_user` masih
  // tersimpan tetapi `kn_token` hilang/kedaluwarsa (sesi lama, tab dibuka ulang setelah
  // token dibersihkan, sesi disuntik alat uji), dulu aplikasi tetap merender kerangka
  // penuh sehingga pengguna menatap layar penuh galat "Login diperlukan" tanpa tahu
  // harus masuk lagi. Sekarang dikembalikan ke layar masuk dengan pesan jelas.
  if (!user || !token) {
    return <LoginScreen onLogin={login}
      notice={user && !token ? "Sesi Anda sudah berakhir — silakan masuk lagi." : notice} />;
  }

  // F-6 — Sales di perangkat mobile → tampilan mobile-first dedicated (device-aware).
  // 'Tampilan Desktop' (forceDesktop) memberi escape-hatch ke antarmuka penuh.
  // §3-A (2026-09) — SEMUA peran mendapat tampilan mobile di perangkat mobile: sales →
  // MobileSalesApp; gudang → MobileWarehouseApp (satu tugas per layar, pindai RFID);
  // peran lain → inbox persetujuan + KPI + jalan ke desktop. forceDesktop = escape-hatch.
  const wantMobile = (isMobile || forceMobile) && !forceDesktop;
  // Master/R&D are responsive pages, not redirects to the mobile approval inbox.
  // Keep an explicitly selected/deep-linked page when the viewport changes.
  // Fitur tanpa layar HP khusus dibuka "tampilan penuh" (mobileVisit) + tombol kembali ke aplikasi HP.
  const responsiveWorkspace = ['md-products', 'product-templates', 'rnd-specs', 'goods-receipts', 'makloon-orders', 'inspections'].includes(activeView) || mobileVisit;
  const goDesktop = () => { localStorage.setItem("kn_force_desktop", "1"); setForceDesktop(true); };
  const goMobile = () => { localStorage.removeItem("kn_force_desktop"); setForceDesktop(false); setMobileVisit(false); };
  const openFullView = (navId, view, opts = {}) => { setMobileVisit(true); handleNavSelect(navId, view, opts.tab, opts); };   // fase 3 · P7 — + preset
  const backToMobile = () => { setMobileVisit(false); handleNavSelect("home"); };
  const wantsTanya = activeView === "tanya-kn";
  const notifProps = {
    total: notifMeta.total, hasMore: notifMeta.has_more, currentUserRole: user?.role,
    onLoadMore: () => loadMoreNotifications(notifMeta.page + 1), onApprove: approveFromNotification,
  };
  // MD → MobileMdApp · sales/Admin Sales → MobileSalesApp · gudang → MobileWarehouseApp · lainnya → MobileOpsApp.
  if (wantMobile && !responsiveWorkspace) {
    return (
      <MobileAppSwitch user={user} token={token} entities={entities} selectedEntity={selectedEntity} onSelectEntity={onSelectEntity}
        notifications={notifications} unreadCount={unreadCount} notifProps={notifProps} onMarkAllRead={markAllNotificationsRead}
        onMarkRead={markNotificationRead} onPollNotifications={actions.loadNotifications}
        onOpenFull={openFullView} onLogout={logout} onForceDesktop={goDesktop} onNavigate={handleNavSelect} wantsTanya={wantsTanya}
        onOpenDocument={(l) => { setMobileVisit(true); openDocument(l); }} onNavigateTo={(v, o) => { setMobileVisit(true); navigateTo(v, o); }}
        actions={actions} settings={settings} data={data} loading={loading} cart={cart} setCart={setCart}
        selectedCustomer={selectedCustomer} setSelectedCustomer={setSelectedCustomer}
        selectedAddress={selectedAddress} setSelectedAddress={setSelectedAddress} notice={notice} paymentTerms={paymentTerms} />
    );
  }

  const pageMeta = PAGE_META[activeView] || { kicker: "Workspace", title: "Kain Nusantara" };
  // Restrukturisasi IA — tab bar sekunder bila view aktif bagian dari sebuah hub.
  const hubInfo = hubForView(activeView, user?.role);

  return (
    <EntityScopeProvider
      selectedEntity={selectedEntity}
      entities={switcherEntities}
      canSwitch={canSwitchEntity}
      pickEntity={onSelectEntity}
    >
    <div className={`app-shell layout-grid ${sidebarCollapsed ? "sidebar-hidden" : ""}`}>
      <a className="skip-link" href="#main-content">Skip to content</a>
      {wantMobile && (mobileVisit || activeView === "goods-receipts") && (
        <button type="button" className="m-back-float" onClick={backToMobile} data-testid="mobile-back-to-app"><Smartphone size={14} /> Kembali ke aplikasi HP</button>
      )}
      <Sidebar
        groups={nav}
        activeNavId={effectiveNavId}
        activeView={activeView}
        onSelect={handleNavSelect}
        user={user}
        onLogout={logout}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="app-main">
        <TopBar
          title={pageMeta.title}
          kicker={pageMeta.kicker}
          crumbs={breadcrumbFor(activeView, effectiveNavId, user?.role)}
          scopeLabel={groupScope ? "Semua Badan Usaha" : entityShortById(archivedActive ? archivedEntities : entities, selectedEntity)}
          onToggleSidebar={handleToggleSidebar}
          onAskKn={["admin", "manager", "sales_admin", "finance", "md", "warehouse_admin", "sales"].includes(user?.role) ? () => handleNavSelect("tanya-kn", "tanya-kn") : null}
          onSync={loadAll}
          syncing={loading}
          notice={notice}
          // G0-21 — CTA bilah pesan dulu "Selesaikan"/"Tinjau" yang membuka layar yang SAMA (ambigu); kini "Tutup".
          infoCta={{ label: "Tutup", onClick: () => setNotice("") }}
          entitySwitcher={<EntitySwitcher entities={switcherEntities} archived={canSwitchEntity ? archivedEntities : []} value={selectedEntity} onChange={onSelectEntity} canSwitch={canSwitchEntity} role={user?.role} homeEntityId={entityContext?.home_entity_id || ""} />}
          notificationCenter={
            <NotificationCenter
              notifications={notifications}
              unreadCount={unreadCount}
              total={notifMeta.total}
              hasMore={notifMeta.has_more}
              onLoadMore={() => loadMoreNotifications(notifMeta.page + 1)}
              canGenerate={roleIs(user?.role, ["admin", "manager"])}
              currentUserRole={user?.role}
              onMarkRead={markNotificationRead}
              onMarkAll={markAllNotificationsRead}
              onGenerate={generateNotifications}
              onApprove={approveFromNotification}
              onNavigate={(target, n) => {
                if (target === "purchasing" && n?.action_id && !n?.action_type) {
                  openDocument({ view: "purchasing", nav_id: "purchase-orders", focus_type: "purchase_order", focus_id: n.action_id });
                } else navigateTo(target);   // fase 3 · P1 — alias + sorotan menu lewat satu jalur
              }}
            />
          }
        />
        <main id="main-content" className="mx-auto w-full max-w-[1600px] px-4 pt-4 pb-24 md:px-5 md:pt-5 md:pb-24">
          <section data-testid="metrics-row" className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 no-print">
            {showHomeWidgets && <>
            <MetricCard testId="metric-products" icon={Archive} label="Produk Aktif" value={data.metrics?.products || 0} tone="rgba(0,122,255,.12)" hint="Buka katalog" onClick={() => showMetricDetail("products")} />
            {/* F-04 — stok per SATUAN (yard dan kg tidak dijumlahkan) + jumlah roll tersedia */}
            <MetricCard testId="metric-available" icon={Boxes} label="Jml Tersedia" value={formatUnitTotals(data.metrics?.available_by_unit, data.metrics?.available_qty)} tone="rgba(52,199,89,.14)" hint={data.metrics?.available_rolls != null ? `${formatQty(data.metrics.available_rolls)} roll · Lihat stok` : "Lihat stok"} onClick={() => showMetricDetail("available")} />
            <MetricCard testId="metric-reserved" icon={Clock3} label="Jml Dipesan" value={formatUnitTotals(data.metrics?.reserved_by_unit, data.metrics?.reserved_qty)} tone="rgba(175,82,222,.14)" hint="Lihat pesanan" onClick={() => showMetricDetail("reserved")} />
            <MetricCard testId="metric-orders" icon={PackageCheck} label="Pesanan Aktif" value={data.metrics?.active_orders || 0} tone="rgba(255,149,0,.14)" hint="Lihat pesanan" onClick={() => showMetricDetail("orders")} />
            <MetricCard testId="metric-warehouses" icon={Building2} label="Gudang" value={data.metrics?.warehouses || 0} tone="rgba(60,60,67,.10)" hint="Buka Operasi Gudang" onClick={() => showMetricDetail("warehouses")} />
            </>}
          </section>

          {/* UAT 24 Okt (audit UI tahap 2) — G0-09: dulu bilah biru berikon ✨ tampil KOSONG di setiap layar
              desktop-di-HP. Kini hanya bila ada pesan (sama seperti versi desktop di CoreWidgets). */}
          {notice && (
            <div className="md:hidden mt-3">
              <div data-testid="system-notice-mobile" className="info-ribbon">
                <Sparkles size={13} className="ribbon-icon" />
                <span>{notice}</span>
              </div>
            </div>
          )}

          <DetailDrawer detail={activeDetail} onClose={() => setActiveDetail(null)} onNavigate={(target) => { navigateTo(target); setActiveDetail(null); }} />

          {/* Onboarding Checklist Panel — hanya di home view (BUG #2 fix) */}
          {showOnboarding && showHomeWidgets && (
            <OnboardingPanel
              onboarding={onboarding}
              onDismiss={() => setShowOnboarding(false)}
              onUpdate={setOnboarding}
            />
          )}

          <PeriodUnlockBanner currentUser={user} onNavigate={(target) => navigateTo(target)} />

          {archivedActive && (
            <ArchivedReadOnlyBanner entity={archivedActive}
              onExit={() => onSelectEntity(entityContext?.home_entity_id || "all")} />
          )}

          {groupScope && (
            <ScopeReadOnlyBanner
              entities={switcherEntities}
              flash={scopeFlash}
              onPick={(id) => {
                const last = lastFocusRef.current;
                onSelectEntity(id);
                if (last && last.link.view === activeView && Date.now() - last.at < 10 * 60 * 1000) setTimeout(() => openDocument(last.link), 0);
              }}
            />
          )}

          {/* U-01 — key={selectedEntity}: ganti badan usaha me-remount layar (refetch) */}
          {/* U-04 — ErrorBoundary: satu layar rusak tidak mematikan seluruh aplikasi */}
          <ErrorBoundary resetKey={`${selectedEntity}:${activeView}`}>
          <AppViewRouter
            key={selectedEntity}
            hubInfo={hubInfo}
            activeView={activeView}
            onNavSelect={handleNavSelect}
            onNavigateTo={navigateTo}
            viewPreset={viewPreset}
            isComingSoon={isComingSoon}
            pageMeta={pageMeta}
            user={user}
            token={token}
            selectedEntity={selectedEntity}
            onSelectEntity={onSelectEntity}
            switcherEntities={switcherEntities}
            entities={entities}
            data={data}
            loading={loading}
            users={users}
            uoms={uoms}
            templates={templates}
            permissions={permissions}
            previewHtml={previewHtml}
            auditLogs={auditLogs}
            auditFilters={auditFilters}
            setAuditFilters={setAuditFilters}
            movements={movements}
            tasks={tasks}
            wmsInitialTab={wmsInitialTab}
            selectedProduct={selectedProduct}
            breakdown={breakdown}
            cart={cart}
            setCart={setCart}
            selectedCustomer={selectedCustomer}
            setSelectedCustomer={setSelectedCustomer}
            selectedAddress={selectedAddress}
            setSelectedAddress={setSelectedAddress}
            search={search}
            setSearch={setSearch}
            settings={settings}
            paymentTerms={paymentTerms}
            focusDoc={focusDoc}
            setFocusDoc={setFocusDoc}
            openDocument={openDocument}
            configFocus={configFocus}
            onConfigFocusConsumed={clearConfigFocus}
            traceAnchor={traceAnchor}
            onTraceAnchorConsumed={clearTraceAnchor}
            rndFocus={rndFocus}
            onRndFocusConsumed={clearRndFocus}
            caseFocus={caseFocus}
            onCaseFocusConsumed={clearCaseFocus}
            logisticsFocus={logisticsFocus}
            onLogisticsFocusConsumed={clearLogisticsFocus}
            setActiveDetail={setActiveDetail}
            lastDocument={lastDocument}
            lastLabel={lastLabel}
            actions={actions}
          />
          </ErrorBoundary>
        </main>
      </div>

      {/* Command Palette (Ctrl+K) — lompat cepat ke menu mana pun */}
      <CommandPalette role={user?.role} onNavigate={handleNavSelect} />

      {/* Guided Tour Component */}
      {activeTour && (
        <GuidedTour
          isActive={true}
          onClose={() => setActiveTour(null)}
          steps={activeTour.steps}
          tourId={activeTour.id}
          onComplete={() => {
            setActiveTour(null);
          }}
        />
      )}

      {/* Kembali ke tampilan HP sesudah memilih "Tampilan Desktop" di layar kecil. */}
      {/* UAT 24 Okt (audit UI tahap 2) — G0-12: dulu dua gaya berbeda per peran ("Tampilan HP" biru di tengah vs
          "← Kembali ke aplikasi HP" hitam di kiri) dan menutupi isi/kaki pop-up. Kini satu gaya (.m-back-float, kiri
          bawah, kecil) dan disembunyikan selama ada pop-up terbuka (styles/mobile.css). */}
      {forceDesktop && (
        <button type="button" onClick={goMobile} data-testid="switch-to-mobile-btn" className="m-back-float">
          <Smartphone size={14} /> Kembali ke aplikasi HP
        </button>
      )}

      {/* Floating Help Button */}
      <TourMenu
        userRole={user?.role}
        showMenu={showTourMenu}
        onToggleMenu={() => setShowTourMenu(!showTourMenu)}
        onSelectTour={(tour) => {
          setActiveTour(tour);
          setShowTourMenu(false);
        }}
      />
    </div>
    </EntityScopeProvider>
  );
}

export default App;
