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
  // Sisir gerbang peran (2026-10-20): antrean QC kedatangan = GET /inbound/qc/queue (wms.view); tanpa izin itu hanya tab dokumen.
  const docsOnly = !can(currentUser?.permissions, "wms", "view");
  const [tab, setTab] = useState(docsOnly ? "docs" : initial);
  return (
    <div data-testid="qc-hub-view">
      <StatusTabs tabs={docsOnly ? TABS.filter((t) => t.key === "docs") : TABS} value={tab} onChange={setTab} testIdPrefix="qc-hub-tab" />
      <div className="mt-3">
        <Suspense fallback={<div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat…</div>}>
          {tab === "queue"
            ? <QCInspection currentUser={currentUser} selectedEntity={selectedEntity} />
            : <InspectionsView currentUser={currentUser} selectedEntity={selectedEntity} focusDoc={focusDoc} onClearFocus={onClearFocus} />}
        </Suspense>
      </div>
    </div>
  );
}
