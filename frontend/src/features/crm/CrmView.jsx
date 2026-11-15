import { useState } from "react";
import { Users, KanbanSquare, MessageSquare } from "lucide-react";
import CustomerList from "./CustomerList";
import LeadsPipeline from "./LeadsPipeline";
import OmnichannelInteractions from "./OmnichannelInteractions";

/**
 * CrmView — modul Pelanggan / CRM (KN_17).
 * Sub-tab: Pelanggan · Prospek · Interaksi. Row-level scoping ditegakkan backend (sales hanya melihat miliknya).
 *
 * MN-T1 — empat sub-tab keuangan/insentif PINDAH (komponennya tidak berubah, kini tab hub sendiri):
 * Penagihan → Keuangan › Piutang › Penagihan & Penerimaan (`collection-worklist`), Persetujuan Kredit → Keuangan ›
 * Piutang › Kredit & Plafon (`credit-overrides`), Kinerja Sales → SDM › Kinerja & Insentif › Kinerja Sales
 * (`sales-performance`), Skema (Arsip) → SDM › Kinerja & Insentif › Skema (Arsip) (`incentive-schemes`).
 * Gerbang izinnya (PR-T7) kini di katalog akses tab tersebut + tombol memutus kredit (`credit_override.approve`).
 * KM-T5 — Kinerja Sales & Skema (Arsip) dicabut juga dari SDM › Kinerja & Insentif (layar lama dihapus; alias ke Capaian
 * dan Target & Aturan). CRM tetap tiga sub-tab ini; tidak ada sub-tab insentif.
 */
export default function CrmView({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  const TABS = [
    { key: "customers", label: "Pelanggan", icon: Users },
    { key: "leads", label: "Prospek (Lead)", icon: KanbanSquare },
    { key: "interactions", label: "Interaksi", icon: MessageSquare },
  ];
  const [tab, setTab] = useState("customers");

  return (
    <div data-testid="crm-view">
      <div className="tab-bar mb-3">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button key={t.key} data-testid={`crm-tab-${t.key}`}
              className={`tab-button ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
              <Icon size={13} /> {t.label}
            </button>
          );
        })}
      </div>

      {tab === "customers" && <CustomerList currentUser={currentUser} selectedEntity={selectedEntity} focusDoc={focusDoc} onClearFocus={onClearFocus} />}
      {tab === "leads" && <LeadsPipeline currentUser={currentUser} selectedEntity={selectedEntity} />}
      {tab === "interactions" && <OmnichannelInteractions currentUser={currentUser} selectedEntity={selectedEntity} />}
    </div>
  );
}
