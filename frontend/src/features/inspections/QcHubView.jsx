import { lazy, Suspense, useState } from "react";
import { StatusTabs } from "../../components/ListControls";
import { can } from "../../config/roles";

const QCInspection = lazy(() => import("../wms/QCInspection"));
const InspectionsView = lazy(() => import("./InspectionsView"));

const TABS = [
  { key: "queue", label: "Antrean QC Kedatangan", testKey: "queue" },
  { key: "docs", label: "Dokumen Inspeksi (INS)", testKey: "docs" },
];

/** QC & Inspeksi dalam SATU menu: antrean karantina kedatangan → dokumen inspeksi (SPK) & keputusan. */
export default function QcHubView({ initial = "queue", currentUser, selectedEntity, focusDoc, onClearFocus }) {
  // Antrean QC kedatangan = GET /inbound/qc/queue (wms.view ATAU qc.view — keputusan owner 2026-10-21);
  // tanpa keduanya hanya tab dokumen.
  const docsOnly = !(can(currentUser?.permissions, "wms", "view") || can(currentUser?.permissions, "qc", "view"));
  const [tab, setTab] = useState(docsOnly ? "docs" : initial);
  // F-14 — antrean karantina: "Putuskan di SPK" membuka SPK-nya di tab dokumen (satu keputusan).
  const [spkFocus, setSpkFocus] = useState(null);
  const openSpk = (spk) => { setSpkFocus({ focus_type: "inspection", focus_id: spk.id, number: spk.number || "" }); setTab("docs"); };
  return (
    <div data-testid="qc-hub-view">
      <StatusTabs tabs={docsOnly ? TABS.filter((t) => t.key === "docs") : TABS} value={tab} onChange={setTab} testIdPrefix="qc-hub-tab" />
      <div className="mt-3">
        <Suspense fallback={<div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat…</div>}>
          {tab === "queue"
            ? <QCInspection currentUser={currentUser} selectedEntity={selectedEntity} onOpenSpk={openSpk} />
            : <InspectionsView currentUser={currentUser} selectedEntity={selectedEntity} focusDoc={spkFocus || focusDoc}
                               onClearFocus={() => { setSpkFocus(null); onClearFocus?.(); }} />}
        </Suspense>
      </div>
    </div>
  );
}
