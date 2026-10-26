/**
 * MyDesignerKpiSection — **Profil Saya › KPI Saya** (fase 3 · P6, D-08): SATU tempat angka kerja milik sendiri.
 *
 * Dulu rapor desainer ada di tiga tempat: Permintaan Desain › "Rapor Desainer"/"Rapor Saya", Desainer › KPI
 * Desainer, dan Profil Saya › KPI Saya (R&D). Keputusan pemilik 26 Okt: menilai TIM = KPI Desainer (tab
 * Pekerjaan DSR); diri SENDIRI = di sini, satu kartu bertab:
 *  · "Ronde sample R&D" — `MyDesignerKpiCard` (`/rnd/reports/my-kpi`);
 *  · "Pekerjaan DSR"   — `MyDesignerReportPanel` (`/design/reports/mine`).
 * Privasi tetap dijaga SERVER: kedua endpoint hanya mengirim baris milik pemanggil (+ rata-rata tim tanpa nama).
 *
 * Tautan "Rapor Saya" di Permintaan Desain membuka `hr-my-profile` dengan preset `{ section: "kpi", tab: "dsr" }`
 * → bagian ini digulir ke pandangan dan tab DSR aktif. Tidak bergantung pada data karyawan (desainer tanpa
 * profil HR tetap melihat angkanya).
 */
import { useEffect, useRef, useState } from "react";
import { BarChart3 } from "lucide-react";
import PageTabs from "../../components/PageTabs";
import useViewPreset from "../../hooks/useViewPreset";
import { can, roleIs } from "../../config/roles";
import MyDesignerReportPanel from "../design/MyDesignerReportPanel";
import { MyDesignerKpiCard } from "./MyDesignerKpiCard";

/** Siapa yang melihat bagian ini (G5-30: hanya peran yang mengerjakan desain/ronde sample R&D). */
export function showMyDesignerKpi(user) {
  return roleIs(user?.role, ["designer", "md", "sample_admin", "md_quality"]) || can(user?.permissions, "design_request", "deliver");
}

/** Tab DSR hanya untuk yang DITUGASI permintaan desain (dulu tab "Rapor Saya" = desainer, `own_only`). */
export function showMyDsrReport(user) {
  if (roleIs(user?.role, ["designer"])) return true;
  return can(user?.permissions, "design_request", "deliver") && !roleIs(user?.role, ["admin", "manager", "sales_admin", "md"]);
}

export default function MyDesignerKpiSection({ currentUser, selectedEntity = "all" }) {
  const showDsr = showMyDsrReport(currentUser);
  const ref = useRef(null);
  const [focusNonce, setFocusNonce] = useState(null);
  const preset = useViewPreset("hr-my-profile", (p) => {
    if (p?.section !== "kpi") return;
    if (p.tab === "dsr" || p.tab === "rnd") setTab(p.tab === "dsr" && showDsr ? "dsr" : "rnd");
    setFocusNonce(p.nonce ?? Date.now());
  });
  const [tab, setTab] = useState(() => (preset?.section === "kpi" && preset?.tab === "dsr" && showDsr ? "dsr" : "rnd"));

  // Dibuka dari tautan → bagian ini digulir ke pandangan (halaman Profil Saya cukup panjang).
  useEffect(() => {
    if (focusNonce === null) return;
    const el = ref.current;
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [focusNonce]);

  if (!showMyDesignerKpi(currentUser)) return null;

  return (
    <section ref={ref} className="grid gap-2" data-testid="ess-kpi-section" aria-label="KPI Saya">
      <div className="flex flex-wrap items-center gap-2">
        <BarChart3 size={15} className="text-[#0058CC]" />
        <h2 className="text-[13px] font-bold">KPI Saya — hanya angka Anda</h2>
      </div>
      <PageTabs testId="ess-kpi-tabs" value={tab} onChange={setTab} ariaLabel="KPI Saya"
        tabs={[
          { key: "rnd", label: "Ronde sample R&D", testId: "ess-kpi-tab-rnd" },
          { key: "dsr", label: "Pekerjaan DSR", testId: "ess-kpi-tab-dsr", hidden: !showDsr },
        ]} />
      {tab === "dsr" && showDsr
        ? <MyDesignerReportPanel selectedEntity={selectedEntity} />
        : <MyDesignerKpiCard />}
    </section>
  );
}
