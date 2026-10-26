import { lazy, Suspense, useState } from "react";
import PageTabs from "../../components/PageTabs";
import { can } from "../../config/roles";

const QCInspection = lazy(() => import("../wms/QCInspection"));
const InspectionsView = lazy(() => import("./InspectionsView"));

const TABS = [
  { key: "queue", label: "Antrean QC Kedatangan" },
  { key: "docs", label: "Dokumen Inspeksi (INS)" },
];

/** QC & Inspeksi dalam SATU menu: antrean karantina kedatangan → dokumen inspeksi (SPK) & keputusan.
 *  `bare` (menu Kualitas, 23 Okt) — tab hub yang menavigasi, jadi tab dalam disembunyikan dan "Putuskan di SPK"
 *  memakai `onOpenSpk` pemanggil (pindah ke tab SPK Inspeksi).
 *  Fase 4 · R3 (L-01) — tab dalam (hanya tampil tanpa `bare`) = `PageTabs` baku (dulu StatusTabs); testid
 *  `qc-hub-tab-queue`/`qc-hub-tab-docs` tetap. Rute menu memakai `bare` → hanya satu tingkat tab (HubTabs). */
export default function QcHubView({ initial = "queue", currentUser, selectedEntity, focusDoc, onClearFocus, bare = false, onOpenSpk }) {
  // Antrean QC kedatangan = GET /inbound/qc/queue (wms.view ATAU qc.view — keputusan owner 2026-10-21);
  // tanpa keduanya hanya tab dokumen.
  const docsOnly = !(can(currentUser?.permissions, "wms", "view") || can(currentUser?.permissions, "qc", "view"));
  const [tab, setTab] = useState(docsOnly ? "docs" : initial);
  // F-14 — antrean karantina: "Putuskan di SPK" membuka SPK-nya di tab dokumen (satu keputusan).
  const [spkFocus, setSpkFocus] = useState(null);
  const openSpk = (spk) => {
    if (bare && onOpenSpk) { onOpenSpk(spk); return; }
    setSpkFocus({ focus_type: "inspection", focus_id: spk.id, number: spk.number || "" }); setTab("docs");
  };
  return (
    <div data-testid="qc-hub-view">
      {!bare && <PageTabs tabs={TABS.map((t) => ({ ...t, hidden: docsOnly && t.key !== "docs" }))} value={tab} onChange={setTab}
        testId="qc-hub-tab" ariaLabel="QC & Inspeksi" />}
      <div className={bare ? "" : "mt-3"}>
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
