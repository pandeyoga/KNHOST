/**
 * useDeepLinks — satu pintu semua **deep-link global** aplikasi.
 *
 * KENAPA DIGABUNG: repo ini punya beberapa jembatan "buka layar X dari mana pun" yang
 * polanya identik (event global + `nonce` + minta App berpindah view):
 *   · `kn-open-config`       → Pengaturan (kelompok domain / Semua pengaturan)   (FASE G-0, fase 3 · P2)
 *   · `kn-open-trace`        → Jejak Dokumen          (FASE G-4)
 *   · `kn-open-rnd`          → hub R&D & Desain       (FASE F)
 *   · `kn-open-finance-case` → Pusat Kasus Keuangan   (FASE G-9)
 * Menyatukannya membuat App.js tidak menumpuk boilerplate yang sama berkali-kali, dan
 * penambahan deep-link berikutnya cukup di SATU tempat.
 *
 * Catatan urutan hook: semuanya dipanggil dengan urutan tetap, jadi aman dipakai
 * di dalam komponen (aturan hooks tidak dilanggar).
 */
import { useEffect, useRef } from "react";
import useConfigDeepLink from "./useConfigDeepLink";
import useRndDeepLink from "./useRndDeepLink";
import useTraceDeepLink from "./useTraceDeepLink";
import useCaseDeepLink from "./useCaseDeepLink";
import useLogisticsDeepLink from "./useLogisticsDeepLink";
import { resolveDeepLinkTarget } from "../config/navigationConfig";
import { configTargetFor } from "../features/settings/config/configGroupViews";

/**
 * Fase 3 · P2 (P16-K1) — tujuan `openConfig({ key, group })`: layar Pengaturan DOMAIN yang memuat kelompok itu
 * (`settings-cfg-*`, kunci `commission.*` → Komisi & Insentif) bila peran boleh membukanya; selain itu "Semua
 * pengaturan" seperti dulu (mis. MD — batas baca K-11 dijaga server di layar itu).
 */
export function configDeepLinkTarget(focus, role) {
  const t = configTargetFor(focus || {});
  if (t.view !== "settings-config" && role && resolveDeepLinkTarget(t.view, role)) return t;
  return { view: "settings-config", nav: "settings-system" };
}

export default function useDeepLinks({ setActiveNavId, setActiveView, setSidebarOpen, ready, onOpenOrder, role }) {
  const go = (navId, view) => {
    setActiveNavId(navId);
    setActiveView(view);
    setSidebarOpen(false);
  };
  const roleRef = useRef(role);
  roleRef.current = role;
  const goRef = useRef(go);
  goRef.current = go;
  // Navigasi Pengaturan diputuskan SESUDAH kunci/kelompok diketahui (efek di bawah), bukan di pendengar event.
  const [configFocus, clearConfigFocus] = useConfigDeepLink(() => {});
  const configNonce = configFocus?.nonce || 0;
  useEffect(() => {
    if (!configNonce) return;
    const t = configDeepLinkTarget(configFocus, roleRef.current);
    goRef.current(t.nav, t.view);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configNonce]);
  // Jangkar dari QR dokumen cetak baru boleh dibuka setelah login (`ready`).
  const [traceAnchor, clearTraceAnchor] = useTraceDeepLink(
    () => go("document-center", "doc-trace"), ready);
  const [rndFocus, clearRndFocus] = useRndDeepLink(
    (view) => go("rnd-hub", view || "rnd-samples"));
  const [caseFocus, clearCaseFocus] = useCaseDeepLink(
    () => go("finance-cases", "finance-cases"));
  // FB-02 — `kn-open-logistics` → Modul Logistik; `kn-open-order` → detail Pesanan (SO).
  const [logisticsFocus, clearLogisticsFocus] = useLogisticsDeepLink(
    () => go("logistics", "logistics"), onOpenOrder);

  return {
    configFocus, clearConfigFocus,
    traceAnchor, clearTraceAnchor,
    rndFocus, clearRndFocus,
    caseFocus, clearCaseFocus,
    logisticsFocus, clearLogisticsFocus,
  };
}
