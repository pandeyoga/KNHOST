import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronDown, MapPin, AlertTriangle, Lock } from "lucide-react";
import axios, { API, setLocationScope } from "../services/apiClient";
import { can } from "../config/roles";

export const LOCATION_SCOPE_KEY = "kn_loc_scope";

/** Bilah cakupan hanya untuk akun yang melihat tugas/stok gudang atau pengiriman. */
export const showsLocationScope = (user) => {
  const p = user?.permissions || {};
  return !!user && (can(p, "wms", "view") || can(p, "product", "view") || can(p, "logistics", "view"));
};

/**
 * Pilihan cakupan lokasi (state App). Header `X-Location-Scope` dipasang SINKRON saat render (seperti token & PT)
 * supaya permintaan pertama layar anak sudah membawanya. Disimpan di `kn_loc_scope` dan DIHAPUS saat logout (UI-39):
 * pengguna berikutnya di HP bersama selalu mulai dari lokasi kerjanya sendiri.
 */
export function useLocationChoice() {
  const [choice, setChoiceState] = useState(() => { try { return localStorage.getItem(LOCATION_SCOPE_KEY) || ""; } catch { return ""; } });
  const ref = useRef(undefined);
  if (ref.current !== choice) { ref.current = choice; setLocationScope?.(choice); }
  const setChoice = useCallback((v) => {
    const val = v || "";
    try { if (val) localStorage.setItem(LOCATION_SCOPE_KEY, val); else localStorage.removeItem(LOCATION_SCOPE_KEY); } catch { /* penyimpanan tak tersedia */ }
    setLocationScope?.(val);
    setChoiceState(val);
  }, []);
  return { choice, setChoice };
}

/**
 * LocationScopeBar — bilah cakupan "Lokasi: Soreang ▾" (FIX-1, audit WMS-RFID 9 Nov · K-B1-01 · pola B4 [2]).
 *
 * Aturan yang dijamin:
 *  1. Cakupan AKTIF selalu terlihat (app bar desktop & HP) — daftar tugas & stok/roll WMS-RFID memakai cakupan ini.
 *  2. Bawaan = LOKASI KERJA akun. "Semua lokasi" / lokasi lain hanya lewat pilihan eksplisit di sini (bukan saringan
 *     yang terlupa). Petugas gudang berpagar hanya bisa mempersempit di dalam lokasinya (opsi lain tidak ditawarkan).
 *  3. Akun tanpa lokasi kerja: label jujur "Semua lokasi — lokasi kerja belum diatur" + anjuran ke admin (Pengguna),
 *     tidak diam-diam "semua".
 * Nilai: "" = lokasi kerja · "all" · "site:<id>" · "wh:<id>" (dikirim server lewat header X-Location-Scope).
 */
export function useLocationScopeSummary(choice) {
  const [summary, setSummary] = useState(null);
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/location-scope`).then((r) => { if (alive) setSummary(r.data); }).catch(() => { if (alive) setSummary({}); });
    return () => { alive = false; };
  }, [choice]);
  return summary;
}

export default function LocationScopeBar({ value = "", onChange, compact = false, testId = "location-scope-bar" }) {
  const summary = useLocationScopeSummary(value);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);
  if (!summary || !summary.view) return null;
  const view = summary.view || {};
  const unset = view.mode === "unset";
  const restricted = !!summary.restricted;
  const homeLabel = summary.home_label || "";
  const options = (summary.options || []).map((o) => (o.kind === "home"
    ? { ...o, label: summary.home_set ? `Lokasi kerja saya · ${homeLabel}` : "Lokasi kerja saya (belum diatur)" }
    : o));
  const current = view.choice || "";
  const pick = (v) => { setOpen(false); if (v !== current) onChange?.(v); };
  const label = restricted && view.mode === "restricted" ? (view.label || homeLabel) : (view.label || "—");
  const canPick = options.length > 1;
  return (
    <div className={`entity-switcher location-scope-bar${compact ? " location-scope-compact" : ""}`} ref={ref} data-testid={testId}>
      <button type="button" className="entity-switcher-trigger" data-testid={`${testId}-trigger`}
        onClick={() => canPick && setOpen((v) => !v)} aria-haspopup="listbox" aria-expanded={open}
        title={unset ? "Lokasi kerja akun Anda belum diatur — minta admin mengisinya di Pengaturan › Pengguna & Hak Akses › Akun."
          : restricted ? "Anda dibatasi ke lokasi tugas ini." : "Cakupan lokasi daftar tugas & stok gudang"}
        style={canPick ? undefined : { cursor: "default" }}>
        {unset ? <AlertTriangle size={14} className="text-[#8C4A00]" /> : <MapPin size={14} />}
        <span className="entity-switcher-label" data-testid={`${testId}-label`}>Lokasi: {label}</span>
        {restricted && <Lock size={12} aria-label="dibatasi" />}
        {canPick && <ChevronDown size={13} className={open ? "rotate-180 transition-transform" : "transition-transform"} />}
      </button>
      {unset && !compact && (
        // Cek visual 14 Nov: teks ini tidak bisa menyusut → bilah atas meluap 117 px di 1024 px (halaman bergulir mendatar).
        // `location-unset-text` disembunyikan di bawah 1280 px; ikon peringatan, tooltip, dan petunjuk di menu tetap ada.
        <span className="location-unset-text text-[11.5px] font-semibold text-[#8C4A00] ml-1" data-testid={`${testId}-unset`}>
          Lokasi kerja belum diatur — minta admin mengisinya di Pengguna
        </span>
      )}
      {open && (
        <div className="entity-switcher-menu" role="listbox" data-testid={`${testId}-menu`}>
          {unset && (
            <p className="entity-switcher-empty" data-testid={`${testId}-unset-hint`}>
              Lokasi kerja akun belum diatur — admin mengaturnya di Pengaturan › Pengguna & Hak Akses › Akun. Sementara itu semua lokasi tampil.
            </p>
          )}
          {options.map((o) => (
            <button key={o.value || "home"} type="button" role="option" aria-selected={o.value === current}
              data-testid={`${testId}-opt-${o.value || "home"}`}
              className={`entity-switcher-item ${o.value === current ? "active" : ""}`}
              onClick={() => pick(o.value)}>
              <span className="truncate">{o.label}</span>
              {o.value === current && <Check size={14} className="shrink-0 text-[#007AFF]" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
