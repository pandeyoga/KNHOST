import { useState } from "react";
import GrnProfilesPanel from "../wms/grn/GrnProfilesPanel";
import GrnOcrSamplesPanel from "../wms/grn/GrnOcrSamplesPanel";
import GrnOcrUsagePanel from "../wms/grn/GrnOcrUsagePanel";
import GrnModePanel from "../wms/grn/GrnModePanel";

const OCR_ROLES = ["admin", "manager", "warehouse_admin"];
const TABS = [
  { key: "profiles", label: "Profil SJ", roles: OCR_ROLES, Panel: GrnProfilesPanel },
  { key: "samples", label: "Sampel Uji OCR", roles: OCR_ROLES, Panel: GrnOcrSamplesPanel },
  { key: "usage", label: "Biaya OCR", roles: OCR_ROLES, Panel: GrnOcrUsagePanel },
  { key: "mode", label: "Mode Penerimaan", roles: ["admin", "manager"], Panel: GrnModePanel },
];

/** Pengaturan › Gudang › Penerimaan & OCR — konfigurasi (bukan pekerjaan harian gudang). */
export default function ReceivingOcrSettings({ currentUser }) {
  const tabs = TABS.filter((t) => t.roles.includes(currentUser?.role));
  const [tab, setTab] = useState(tabs[0]?.key || "");
  const active = tabs.find((t) => t.key === tab) || tabs[0];
  if (!active) return <p className="empty-state">Anda tidak memiliki akses ke pengaturan penerimaan.</p>;
  return (
    <div data-testid="receiving-ocr-settings" className="space-y-3">
      <div className="tab-bar">
        {tabs.map((t) => (
          <button key={t.key} type="button" data-testid={`ocr-settings-tab-${t.key}`}
            className={`tab-button ${active.key === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>
      <active.Panel />
    </div>
  );
}
