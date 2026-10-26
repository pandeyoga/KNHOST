import { useState, useEffect } from "react";
import { Layers, ArrowLeftRight, ClipboardCheck, Activity } from "lucide-react";
import InventoryStockView from "./InventoryStockView";
import TransferManagement from "./TransferManagement";
import StockOpnameTab from "./StockOpnameTab";
import WmsHealthDashboard from "./WmsHealthDashboard";
import WaitingBoardsStrip from "../../components/WaitingBoardsStrip";
import { can } from "../../config/roles";
import useViewPreset from "../../hooks/useViewPreset";
import { useAppNav } from "../../context/AppNavContext";

export default function OperationsView({
  data,
  movements,
  tasks,
  entities = [],
  selectedEntity = "all",
  onGenerateLabel,
  onCreateInboundTask,
  onCreateOutboundTasks,
  onScanTask,
  onAdvanceTask,
  onShowDetail,
  onNavigate,
  token,
  user,
  defaultTab,
  focusDoc,
  onClearFocus,
  onOpenDocument,
}) {
  const [wmsTab, setWmsTab] = useState(defaultTab || "stok");
  // T6 DIBAYAR (2026-06c): keputusan dari papan di atas harus ikut menyegarkan
  // DAFTAR di bawahnya (Transfer & Stock Opname memuat datanya sendiri), supaya
  // satu dokumen tidak tampil "menunggu ACC" di layar yang sama (INV-HOME-01).
  const [boardsVersion, setBoardsVersion] = useState(0);
  // Fase 3 · P5 — D-16: satu daftar transfer dengan saringan Jenis (dulu sub-tab "Antar gudang | Antar entitas (PT)"
  // yang menampilkan transfer antar-PT DUA kali). D-15: metode stock opname (hitung fisik | sapu RFID).
  const [transferKind, setTransferKind] = useState("all");
  const [opnameMethod, setOpnameMethod] = useState("count");
  const [opnameWarehouse, setOpnameWarehouse] = useState("");
  const { go } = useAppNav();

  // Sync tab when deep-link navigation from sidebar changes defaultTab
  useEffect(() => {
    if (defaultTab && defaultTab !== wmsTab) setWmsTab(defaultTab);
  }, [defaultTab]); // eslint-disable-line
  // Preset navigasi (alias `interco-transfers` → {tab:"transfer", kind:"inter_entity"}; tautan Lokasi RFID →
  // {tab:"cycle", method:"rfid", warehouse}). Diterapkan sekali per navigasi; pilihan manual tidak ditimpa.
  useViewPreset("operations", (p) => {
    if (p.tab) setWmsTab(p.tab);
    if (p.kind) setTransferKind(p.kind);
    if (p.method) setOpnameMethod(p.method);
    if (p.warehouse !== undefined) setOpnameWarehouse(p.warehouse || "");
  });
  const WMS_TABS = [
    // 2026-10 — Barang Masuk (termasuk Scan Terima PO mode lama) & Barang Keluar kini tab hub sendiri.
    { id: "stok",     label: "Stok",        icon: Layers,        desc: "Lihat qty per gudang" },
    { id: "transfer", label: "Transfer",     icon: ArrowLeftRight, desc: "Pindah antar gudang / antar PT" },
    { id: "cycle",    label: "Stock Opname",  icon: ClipboardCheck, desc: "Hitung fisik stok (atau sapu RFID)" },
    { id: "health",   label: "Kesehatan",  icon: Activity, desc: "Ringkasan insiden, opname & antrean per gudang" },
  ];
  // AUDIT SALES vs ADMIN SALES (2026-08-15) — tab disaring per IZIN, bukan per peran.
  // Admin Sales diberi `wms.view` supaya bisa MEMANTAU progres gudang, tetapi tab
  // "Stock Opname" memanggil `/cycle-count/sessions` yang menuntut
  // `inventory.cycle_count` — izin yang tidak (dan tidak seharusnya) ia punya. Dulu
  // tabnya tetap tampil, diklik, lalu 403: pengguna menabrak dinding tanpa alasan.
  // Daftar di atas SENGAJA tetap lengkap (gate `check_nav_map.py` CHECK 2 membacanya);
  // yang disaring adalah apa yang DIRENDER.
  const perms = user?.permissions || {};
  const TAB_PERMISSION = { cycle: ["inventory", "cycle_count"] };
  const visibleTabs = WMS_TABS.filter((t) => {
    const need = TAB_PERMISSION[t.id];
    return !need || can(perms, need[0], need[1]);
  });
  const activeTab = visibleTabs.some((t) => t.id === wmsTab)
    ? wmsTab
    : (visibleTabs[0]?.id || "stok");
  return (
    <div data-testid="operations-view">
      {/* Papan keputusan yang MENAHAN BARANG (2026-06) — ditempel di atas tab supaya
          terlihat di tab mana pun petugas berada. Angkanya milik backend.
          Fase 3 · P5 — D-28 (keputusan pemilik 26 Okt): papan "Barang ditahan QC" kini TAUTAN — klik baris membuka
          SPK-nya di Kualitas › SPK Inspeksi (saringan "Hanya yang DITAHAN"), satu-satunya tempat keputusan
          lepas/tolak. Papan transfer & opname tetap bisa ditindak di sini. */}
      <WaitingBoardsStrip endpoint="/home/warehouse" entityId={selectedEntity}
        primaryKey="transfer" testIdPrefix="wms-home"
        scopeNote="Antrean ACC · semua gudang (filter gudang di bawah hanya untuk daftar stok)"
        linkKeys={["inspection_hold"]}
        onOpenDocument={(link) => onOpenDocument?.({ ...link, preset: { hold: true } })}
        onActed={() => setBoardsVersion((v) => v + 1)}
        onNavigate={(view, key) => {
          const tab = { transfer: "transfer", cycle_count: "cycle" }[key];
          if (tab) setWmsTab(tab);
          else if (key === "inspection_hold") go("inspections", { preset: { hold: true } });
          else if (onNavigate) onNavigate(view);
        }} />

      {/* Tab Bar */}
      <div className="flex items-center gap-0.5 overflow-x-auto pb-0 mb-3 border-b border-[#EFF0F2]">
        {visibleTabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button key={tab.id} onClick={() => setWmsTab(tab.id)}
              data-testid={`wms-tab-${tab.id}`}
              title={tab.desc}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-[12px] font-medium whitespace-nowrap transition-all border-b-2 -mb-px ${
                activeTab === tab.id
                  ? "border-[#007AFF] text-[#007AFF] bg-blue-50/50"
                  : "border-transparent text-[#6B6B73] hover:text-[#3C3C43] hover:bg-[#FAFBFC]"
              }`}>
              <Icon size={13} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* STOK TAB — inventory balances per warehouse + rolls (Roll-as-SSOT) */}
      {activeTab === "stok" && (
        <InventoryStockView
          warehouses={data.warehouses || []}
          products={data.products || []}
          entities={entities}
          customers={data.customers || []}
          selectedEntity={selectedEntity}
          user={user}
        />
      )}

      {/* TRANSFER TAB — D-16: satu daftar (antar gudang + antar PT) dengan kolom & saringan Jenis.
          T6: papan di atas boleh memaksa daftar ini memuat ulang. */}
      {activeTab === "transfer" && (
        <div className="section-card">
          <div className="section-body">
            <TransferManagement key={`transfer-${boardsVersion}`} user={user}
              kind={transferKind} onKindChange={setTransferKind}
              focusTransferId={focusDoc?.focus_type === "warehouse_transfer" ? focusDoc.focus_id : ""}
              onFocusConsumed={onClearFocus} />
          </div>
        </div>
      )}

      {/* STOCK OPNAME TAB — D-15: satu alur, dua metode (hitung fisik · sapu RFID). */}
      {activeTab === "cycle" && (
        <StockOpnameTab method={opnameMethod} onMethodChange={setOpnameMethod}
          warehouseId={opnameWarehouse} onWarehouseChange={setOpnameWarehouse}
          warehouses={data.warehouses || []} selectedEntity={selectedEntity}
          cycleKey={`cycle-${boardsVersion}`}
          cycleCountProps={{
            token, warehouses: data.warehouses || [], products: data.products || [], userRole: user?.role,
            focusSessionId: focusDoc?.focus_type === "cycle_count" ? focusDoc.focus_id : "",
            onFocusConsumed: onClearFocus,
          }} />
      )}

      {/* KESEHATAN TAB — ringkasan insiden, opname & antrean per gudang */}
      {activeTab === "health" && (
        <WmsHealthDashboard selectedEntity={selectedEntity} />
      )}
    </div>
  );
}
