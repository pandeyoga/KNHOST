/**
 * ClosingParts — bagian layar Tutup Buku (`ClosingView`): `Labeled`, `MiniStat`, dan (MN-T2) `ClosingSections` = dua
 * SEKSI LIPAT di bawah pratinjau: "Persediaan vs buku besar" (`InventoryReconTab`) dan "Akun sementara"
 * (`SuspensePanel`) — dulu tab ke-4 & ke-5 layar Jurnal & Buku Besar.
 * Isi seksi dimuat hanya saat dibuka. Dibuka oleh tombol "Buka" daftar periksa (`stok_cocok` / `suspense_nol`,
 * `link = {view: "closing", preset: {seksi}}`) atau preset navigasi `{ seksi }` (termasuk preset lama Jurnal
 * `{tab: "recon" | "suspense"}` yang dialihkan GeneralLedger).
 *
 *   const seksi = useClosingSections(entityId);
 *   seksi.buka("akun-sementara");
 *   <ClosingSections ctl={seksi} entityId={entityId} entities={entities} onError={setError} onNotice={setNotice} />
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeftRight, Boxes, ChevronDown, ChevronRight } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import useViewPreset from "../../hooks/useViewPreset";
import InventoryReconTab from "./InventoryReconTab";
import SuspensePanel from "./SuspensePanel";

/** Kunci seksi = `preset.seksi` daftar periksa. */
export const CLOSING_SECTIONS = [
  { key: "persediaan", label: "Persediaan vs buku besar", icon: Boxes,
    hint: "Nilai stok (buku pembantu) dibanding saldo akun persediaan per PT." },
  { key: "akun-sementara", label: "Akun sementara", icon: ArrowLeftRight,
    hint: "Saldo akun penampung (Suspense 1-9999) harus nol sebelum tutup buku; reklasifikasi di sini." },
];
const KEYS = CLOSING_SECTIONS.map((x) => x.key);

export function useClosingSections(entityId) {
  const [terbuka, setTerbuka] = useState({});
  const [accounts, setAccounts] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const refs = useRef({});
  const buka = useCallback((key) => {
    if (!KEYS.includes(key)) return;
    setTerbuka((s) => ({ ...s, [key]: true }));
    window.setTimeout(() => refs.current[key]?.scrollIntoView?.({ block: "start", behavior: "smooth" }), 50);
  }, []);
  const toggle = useCallback((key) => setTerbuka((s) => ({ ...s, [key]: !s[key] })), []);
  useViewPreset("closing", (p) => { if (p.seksi) buka(p.seksi); });   // navigasi ber-preset (juga saat layar dipasang)
  const akunTerbuka = !!terbuka["akun-sementara"];
  useEffect(() => {
    if (!akunTerbuka || !entityId) return;
    axios.get(`${API}/gl/accounts`, { params: { entity_id: entityId } })
      .then((r) => setAccounts(Array.isArray(r.data) ? r.data : [])).catch(() => setAccounts([]));
  }, [akunTerbuka, entityId]);
  return { terbuka, buka, toggle, accounts, refreshKey, bump: () => setRefreshKey((k) => k + 1), refs };
}

export default function ClosingSections({ ctl, entityId, entities = [], onError, onNotice }) {
  return (
    <div className="mb-4 grid gap-2" data-testid="closing-sections">
      {CLOSING_SECTIONS.map((sx) => {
        const buka = !!ctl.terbuka[sx.key];
        const Icon = sx.icon;
        return (
          <section key={sx.key} ref={(el) => { ctl.refs.current[sx.key] = el; }}
            className="rounded-lg border border-kn-divider" data-testid={`closing-section-${sx.key}`} data-open={buka ? "1" : "0"}>
            <button type="button" aria-expanded={buka} data-testid={`closing-section-${sx.key}-toggle`}
              className="ghost-button w-full items-start justify-start text-left" onClick={() => ctl.toggle(sx.key)}>
              {buka ? <ChevronDown size={14} aria-hidden="true" className="mt-0.5 shrink-0" />
                : <ChevronRight size={14} aria-hidden="true" className="mt-0.5 shrink-0" />}
              <Icon size={14} aria-hidden="true" className="mt-0.5 shrink-0 text-kn-text-2" />
              <span className="min-w-0">
                <span className="block text-fs-13 font-bold text-kn-text">{sx.label}</span>
                <span className="block text-fs-12 text-kn-text-2">{sx.hint}</span>
              </span>
            </button>
            {buka && (
              <div className="border-t border-kn-divider p-3" data-testid={`closing-section-${sx.key}-body`}>
                {sx.key === "persediaan" ? (
                  <InventoryReconTab refreshKey={ctl.refreshKey} onError={onError} onNotice={onNotice}
                    onChanged={ctl.bump} selectedEntity={entityId} entities={entities} />
                ) : (
                  <SuspensePanel refreshKey={ctl.refreshKey} accounts={ctl.accounts} entities={entities}
                    selectedEntity={entityId} onNotice={onNotice} onChanged={ctl.bump} />
                )}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

// Dipindah dari ClosingView (MN-T2, batas 500 baris); huruf ≥ 12 px dan warna token (KN_37).
export function Labeled({ label, children }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">{label}</span>
      {children}
    </div>
  );
}

export function MiniStat({ label, value, tone = "text-kn-text" }) {
  return (
    <div className="rounded-md border border-kn-divider px-3 py-2 bg-white">
      <p className="text-fs-12 font-bold uppercase tracking-wide text-kn-text-2">{label}</p>
      <p className={`text-fs-13 font-bold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}
