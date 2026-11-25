/**
 * PageHelpContext — isi ikon ? di samping judul halaman (meja gelombang 1, spek 2026-11-25 §5.1).
 *
 * Kepala meja lama (judul kedua, paragraf alur, kotak "Bukan wewenang meja ini") dihapus; penjelasannya pindah ke SATU
 * ikon ? di samping judul halaman di bilah atas. Layar yang terpasang menyetel isinya lewat `usePageHelp`; `TopBar`
 * menggambar `PageHelpButton` (via `titleAddon`).
 *
 *   usePageHelp(<>Alur …</>, "sales_admin|…");   // selama terpasang: isi ? = node; dilepas saat unmount
 *
 * Efek `usePageHelp` hanya bergantung pada `key` (bukan `node`, yang dibuat ulang tiap render) agar tidak berputar:
 * isi baru dipasang saat `key` berubah. Di luar `PageHelpProvider` (mis. uji komponen, aplikasi HP) hook ini tidak
 * berbuat apa-apa dan tombolnya tidak tampil.
 */
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { HelpTip } from "../components/ListPageParts";

// Dua konteks: penyetel (stabil) dan isi. Layar yang menyetel tidak ikut dirender ulang saat isinya berubah.
const SetHelpContext = createContext(null);
const HelpContext = createContext(null);

export function PageHelpProvider({ children }) {
  const [help, setHelp] = useState(null);   // { token, node } | null
  return (
    <SetHelpContext.Provider value={setHelp}>
      <HelpContext.Provider value={help}>{children}</HelpContext.Provider>
    </SetHelpContext.Provider>
  );
}

/** Selama komponen terpasang, isi ? halaman = `node`; dipasang ulang hanya bila `key` berubah. */
export function usePageHelp(node, key) {
  const setHelp = useContext(SetHelpContext);
  const nodeRef = useRef(node);
  nodeRef.current = node;
  useEffect(() => {
    if (!setHelp) return undefined;
    const token = {};
    setHelp({ token, node: nodeRef.current });
    // Hanya melepas isi miliknya sendiri — layar lain yang sudah memasang isinya tidak terhapus.
    return () => setHelp((cur) => (cur && cur.token === token ? null : cur));
  }, [setHelp, key]);
}

/** Ikon ? halaman (di `TopBar`); `null` bila tidak ada isi. */
export function PageHelpButton() {
  const help = useContext(HelpContext);
  if (!help || !help.node) return null;
  return <HelpTip text={help.node} testId="page-help" label="Tentang layar ini" />;
}
