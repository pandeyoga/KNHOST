/**
 * DeskFrame — kerangka bersama setiap meja kerja (Meja Admin Sales · Meja Keuangan · Meja Gudang · Meja Sample ·
 * Meja MD · Meja Saya), meja gelombang 1 (spek 2026-11-25 §5.1).
 *
 *  · SATU kepala = judul halaman di bilah atas. Penjelasan meja (`help`) dan daftar "Bukan wewenang meja ini"
 *    (`notMine`) masuk ke ikon ? di samping judul (`usePageHelp`), bukan kotak di atas antrean.
 *  · Tab "Antrean" (bawaan) | "Pantau" (`PageTabs`); tab aktif diingat per meja di sessionStorage `kn.meja.<deskKey>`
 *    (bidang `tab`). Hanya panel aktif yang dirender: `${p}-antrean` / `${p}-pantau`; Pantau tanpa isi →
 *    `${p}-pantau-empty`.
 *  · `tabsInHub` (R4): meja yang sudah menjadi tab hub (Meja Keuangan di Beranda Keuangan) TIDAK menggambar tab sendiri
 *    — tab Pantau-nya tab hub saudara; meja hanya menggambar panel `tab` yang dipilih hub (tanpa tab tingkat ketiga).
 *  · Muat ulang global (tombol muat ulang bilah atas → `MUAT_ULANG_EVENT`) → `onReload()`.
 *  · Kembali dari layar lain (`markDeskReturn`) → gulir dipulihkan saat `ready` (`useDeskScrollRestore`).
 */
import { useEffect, useRef, useState } from "react";
import PageTabs from "../../components/PageTabs";
import { usePageHelp } from "../../context/PageHelpContext";
import { MUAT_ULANG_EVENT } from "../../utils/refreshSignal";
import { pageStateKey, readDeskState, useDeskScrollRestore, writeDeskState } from "./deskSession";

/** Grid kartu antrean: satu kolom, dua kolom di layar lebar; kartu tidak diregangkan (tinggi tetap, `items-start`). */
export const DESK_GRID_CLASS = "grid grid-cols-1 items-start gap-3 xl:grid-cols-2";

const TABS = [
  { key: "antrean", label: "Antrean" },
  { key: "pantau", label: "Pantau" },
];
const asTab = (t) => (t === "pantau" ? "pantau" : "antrean");
const isEmptyNode = (n) => n === null || n === undefined || n === false
  || (Array.isArray(n) && n.every(isEmptyNode));

export default function DeskFrame({
  deskKey, testPrefix, help, notMine = [], antrean, pantau = null, ready = true, onReload,
  tabsInHub = false, tab: hubTab = "antrean",
}) {
  const p = testPrefix;
  const stateKey = pageStateKey(deskKey);
  const [ownTab, setOwnTab] = useState(() => asTab(readDeskState(stateKey).tab));
  const tab = tabsInHub ? asTab(hubTab) : ownTab;
  const pick = (t) => { setOwnTab(asTab(t)); writeDeskState(stateKey, { tab: asTab(t) }); };

  const list = Array.isArray(notMine) ? notMine.filter(Boolean) : [];
  usePageHelp(
    <>
      {help}
      {list.length > 0 && <><br /><b>Bukan wewenang meja ini:</b> {list.join(" · ")}</>}
    </>,
    `${deskKey}|${list.join("|")}`,
  );

  const reloadRef = useRef(onReload);
  reloadRef.current = onReload;
  useEffect(() => {
    const onSignal = () => reloadRef.current?.();
    window.addEventListener(MUAT_ULANG_EVENT, onSignal);
    return () => window.removeEventListener(MUAT_ULANG_EVENT, onSignal);
  }, []);

  useDeskScrollRestore(deskKey, ready);

  return (
    <div data-testid={`${p}-frame`} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {!tabsInHub && (
        <PageTabs testId={`${p}-tabs`} value={tab} onChange={pick} tabs={TABS} ariaLabel="Tab meja" />
      )}
      {tab === "antrean" ? (
        <div data-testid={`${p}-antrean`}>{antrean}</div>
      ) : (
        <div data-testid={`${p}-pantau`}>
          {isEmptyNode(pantau) ? (
            <div data-testid={`${p}-pantau-empty`}
              className="section-card section-pad text-center text-fs-13 text-kn-text-2">
              Tidak ada pantauan untuk meja ini.
            </div>
          ) : pantau}
        </div>
      )}
    </div>
  );
}
