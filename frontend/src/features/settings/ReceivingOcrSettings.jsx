import { useState } from "react";
import PageTabs from "../../components/PageTabs";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import GrnProfilesPanel from "../wms/grn/GrnProfilesPanel";
import GrnOcrSamplesPanel from "../wms/grn/GrnOcrSamplesPanel";
import GrnOcrUsagePanel from "../wms/grn/GrnOcrUsagePanel";
import GrnModePanel from "../wms/grn/GrnModePanel";
import useViewPreset from "../../hooks/useViewPreset";
import { can } from "../../config/roles";

// PR-T7 (#20) — tiap tab memakai izin endpoint-nya (dulu daftar nama peran). Profil SJ & Sample Uji OCR = tab pengaturan
// (ubah profil `PATCH /goods-receipts/dn-profiles/*`, kelola sample `/ocr-samples/*`) = goods_receipt.review; Biaya OCR
// `GET /goods-receipts/usage` = goods_receipt.approve; Mode Penerimaan `PUT /goods-receipts/mode` = goods_receipt.configure.
const TABS = [
  { key: "profiles", label: "Profil SJ", perm: ["goods_receipt", "review"], Panel: GrnProfilesPanel },
  { key: "samples", label: "Sample Uji OCR", perm: ["goods_receipt", "review"], Panel: GrnOcrSamplesPanel },
  { key: "usage", label: "Biaya OCR", perm: ["goods_receipt", "approve"], Panel: GrnOcrUsagePanel },
  { key: "mode", label: "Mode Penerimaan", perm: ["goods_receipt", "configure"], Panel: GrnModePanel },
];

/** Pengaturan › Gudang, Pembelian & Produksi › Penerimaan Barang — konfigurasi (bukan pekerjaan harian gudang). */
export default function ReceivingOcrSettings({ currentUser }) {
  const tabs = TABS.filter((t) => can(currentUser?.permissions, ...t.perm));
  // KF-T4 — kartu Pengaturan "Cara mencatat barang datang" menautkan ke sini dengan preset `{ tab: "mode" }`.
  const preset = useViewPreset("settings-receiving-ocr", (p) => { if (tabs.some((t) => t.key === p.tab)) setTab(p.tab); });
  const [tab, setTab] = useState(() => (tabs.some((t) => t.key === preset?.tab) ? preset.tab : tabs[0]?.key || ""));
  const active = tabs.find((t) => t.key === tab) || tabs[0];
  if (!active) return <p className="empty-state">Anda tidak memiliki akses ke pengaturan penerimaan.</p>;
  return (
    <div data-testid="receiving-ocr-settings" className="space-y-3">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
      {/* Fase 3 · P2 (L-01) — bilah tab baku (PageTabs); testid `ocr-settings-tab-<key>` tetap. */}
      <PageTabs testId="ocr-settings-tabs" tabTestId={(k) => `ocr-settings-tab-${k}`} value={active.key} onChange={setTab}
        ariaLabel="Penerimaan Barang" tabs={tabs.map((t) => ({ key: t.key, label: t.label }))} />
      <active.Panel />
    </div>
  );
}
