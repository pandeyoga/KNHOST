import { useState } from "react";
import { Users, Receipt, TrendingUp, ShieldCheck, SlidersHorizontal, Percent, KanbanSquare, MessageSquare } from "lucide-react";
import CustomerList from "./CustomerList";
import CollectionWorklist from "./CollectionWorklist";
import SalesForceDashboard from "./SalesForceDashboard";
import CreditOverridesPanel from "./CreditOverridesPanel";
import IncentiveSchemeEditor from "./IncentiveSchemeEditor";
import LeadsPipeline from "./LeadsPipeline";
import OmnichannelInteractions from "./OmnichannelInteractions";
import { can } from "../../config/roles";

/**
 * CrmView — modul Pelanggan / CRM + Sales Force (KN_17).
 * Sub-tab: Pelanggan · Penagihan · Sales Force · Rate Insentif · Skema (Arsip) · Approval Kredit.
 * Row-level scoping ditegakkan backend (sales hanya melihat miliknya).
 */
export default function CrmView({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  // PR-T7 (#12) — tab dari izin endpoint-nya, bukan nama peran: Skema (Arsip) = `sales_force.view` (skema & target
  // insentif), Persetujuan Kredit = `credit_override.approve` (keputusan izin lewat-batas kredit).
  const perms = currentUser?.permissions;
  const canSchemes = can(perms, "sales_force", "view");
  const canCredit = can(perms, "credit_override", "approve");
  const TABS = [
    { key: "customers", label: "Pelanggan", icon: Users },
    { key: "leads", label: "Prospek (Lead)", icon: KanbanSquare },
    { key: "interactions", label: "Interaksi", icon: MessageSquare },
    { key: "collection", label: "Penagihan", icon: Receipt },
    { key: "salesforce", label: "Kinerja Sales", icon: TrendingUp },
    ...(canSchemes ? [{ key: "schemes", label: "Skema (Arsip)", icon: SlidersHorizontal }] : []),
    ...(canCredit ? [{ key: "approvals", label: "Persetujuan Kredit", icon: ShieldCheck }] : []),
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
      {tab === "collection" && <CollectionWorklist currentUser={currentUser} selectedEntity={selectedEntity} />}
      {tab === "salesforce" && <SalesForceDashboard currentUser={currentUser} selectedEntity={selectedEntity} />}
      {tab === "schemes" && canSchemes && <IncentiveSchemeEditor currentUser={currentUser} selectedEntity={selectedEntity} />}
      {tab === "approvals" && canCredit && <CreditOverridesPanel currentUser={currentUser} />}
    </div>
  );
}
