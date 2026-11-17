/** Kerangka layar daftar seragam (pola UI `docs/blueprint/04_POLA_UI.md` §2.A): judul satu baris (+ ?), kartu angka
 *  yang bisa diklik, bilah daftar (cari · dropdown · jumlah · aksi), tab status lama. */
import { useEffect, useRef, useState } from "react";
import { HelpCircle, Search, X } from "lucide-react";
import { useEscapeClose } from "@/utils/escapeLayers";

/** Ikon "?" — penjelasan dibuka saat diklik, bukan paragraf yang dipajang (pola UI §1.4). */
export function HelpTip({ text, testId, label = "Penjelasan" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  // Esc lewat tumpukan lapisan bersama (`useEscapeClose`, penjaga verify_escape_layers): bila ? dibuka di dalam pop-up,
  // Esc menutup catatan ? dulu, bukan pop-up di bawahnya.
  useEscapeClose(open, () => setOpen(false));
  useEffect(() => {
    if (!open) return undefined;
    const off = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", off);
    return () => document.removeEventListener("mousedown", off);
  }, [open]);
  if (!text) return null;
  return (
    <span className="relative inline-flex" ref={ref}>
      <button type="button" aria-label={label} aria-expanded={open} data-testid={testId}
        className="icon-button btn-sm text-kn-neutral hover:text-kn-action"
        onClick={() => setOpen((v) => !v)}>
        <HelpCircle size={15} />
      </button>
      {open && (
        <span role="note" data-testid={testId ? `${testId}-text` : undefined}
          className="absolute left-0 top-6 z-30 w-[300px] max-w-[80vw] rounded-lg border border-kn-divider bg-white p-2.5 text-left text-fs-12 font-normal normal-case leading-relaxed tracking-normal text-kn-text shadow-lg">
          {text}
        </span>
      )}
    </span>
  );
}

/** Kepala halaman SATU BARIS: judul (+ ? berisi keterangan) · aksi. `subtitle` lama tidak dipajang lagi — masuk ke ?. */
export function PageHeader({ icon: Icon, title, subtitle, help, actions, testId }) {
  return (
    <div className="view-header" data-testid={testId}>
      <div className="flex min-w-0 items-center gap-2">
        <h1 className="view-title flex items-center gap-2">{Icon && <Icon size={20} />} {title}</h1>
        <HelpTip text={help || subtitle} testId={testId ? `${testId}-help` : undefined} />
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Bilah daftar SATU BARIS (pola UI §2.A): cari + dropdown saringan + jumlah di kiri, aksi (Unduh, + Buat …) di kanan —
 *  tombol buat dekat dengan tabelnya. Di HP turun baris dengan urutan yang sama. */
export function ListToolbar({ children, actions, count, testId }) {
  return (
    <div className="mb-2 flex flex-wrap items-center gap-2" data-testid={testId}>
      {children}
      {count != null && <span className="whitespace-nowrap text-fs-12 text-kn-text-2" data-testid={testId ? `${testId}-count` : undefined}>{count}</span>}
      {actions && <div className="ml-auto flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Nilai nol ("0", "Rp 0", "0,00", "0 roll") — fase 3 · P1 (L-08): angka nol tampil NETRAL, bukan merah/hijau. */
export function isZeroMetric(value) {
  if (value === 0) return true;
  if (typeof value !== "string") return false;
  return /^(Rp\s?)?0([.,]0+)?\s*(%|[A-Za-z]\w*)?$/.test(value.trim());
}

/** Cek layar MN-T2 (Beranda 1024 px): "-Rp 236.048.300" patah sesudah tanda minus ("-" sebaris sendiri) — tanda minus
 *  dan "Rp" dikunci satu baris; isi teks tidak berubah. */
function metricText(value) {
  if (typeof value !== "string" || !/^-\s*Rp/.test(value)) return value;
  const m = value.match(/^(-\s*Rp)(.*)$/s);
  return <><span className="whitespace-nowrap">{m[1]}</span>{m[2]}</>;
}

export function MetricRow({ items, testId }) {
  // Cek layar 15 Nov (1024 px): lima/enam kartu sebaris di layar 1024 memotong label & rupiah ("Rp 19.599…"). Lima kartu
  // 3+2 sampai xl, enam kartu 3+3 sampai 2xl (pola kartu KPI keuangan).
  const cols = { 3: "sm:grid-cols-3", 4: "sm:grid-cols-4", 5: "sm:grid-cols-3 xl:grid-cols-5",
    6: "sm:grid-cols-3 2xl:grid-cols-6" }[items.length] || "sm:grid-cols-4";   // PK-41 — enam kartu (umur hutang)
  return (
    <div data-testid={testId} className={`grid grid-cols-2 gap-2 ${cols}`}>
      {items.map(({ label, value, icon: Icon, hint, tone, testId: tid, onClick, active }, i) => {
        // Pola UI §1.5 — kartu angka harus berguna: `onClick` = saringan cepat (kartu aktif bergaris biru).
        const Tag = onClick ? "button" : "div";
        return (
        <Tag key={label} type={onClick ? "button" : undefined} onClick={onClick} aria-pressed={onClick ? Boolean(active) : undefined}
          className={`metric-card${onClick ? " text-left transition-colors hover:border-kn-action" : ""}${active ? " !border-kn-action ring-1 ring-kn-action" : ""}`}
          data-testid={tid || (testId ? `${testId}-${i}` : undefined)}>
          {Icon && <div className="metric-icon"><Icon size={16} /></div>}
          <div className="metric-body">
            <div className="metric-label">{label}</div>
            {/* L-08 — warna `tone` hanya untuk angka yang ADA; nol berwarna merah/hijau dibaca sebagai peringatan. */}
            <div className={`metric-value tabular-nums ${isZeroMetric(value) ? "metric-zero" : ""}`.trim()}
              style={tone && !isZeroMetric(value) ? { color: tone } : undefined}>{metricText(value)}</div>
            {hint && <div className="metric-hint">{hint}</div>}
          </div>
        </Tag>
        );
      })}
    </div>
  );
}

/**
 * SearchInput — FIX-8 (B4 §3.13 "satu versi kotak cari"): SATU implementasi kotak cari. Dulu ada tiga: `SearchBox`
 * di sini, `SearchBox` kedua di `ListControls.jsx` (ikon & ukuran tombol hapus beda), dan kotak buatan layar
 * (Stok, Transfer). `SearchBox` = kotak ini di dalam bilah saring + anak (saringan) di sebelahnya.
 * `ariaLabel` bawaan = placeholder (isian berlabel, G-FORM-08).
 */
export function SearchInput({ value, onChange, placeholder, testId, ariaLabel, className = "" }) {
  return (
    <div className={`search-box${className ? ` ${className}` : ""}`}>
      <Search size={14} aria-hidden="true" />
      <input data-testid={testId} type="text" placeholder={placeholder} value={value ?? ""}
        aria-label={ariaLabel || placeholder || "Cari"} onChange={(e) => onChange(e.target.value)} />
      {value ? (
        <button type="button" aria-label="Hapus pencarian" data-testid={testId ? `${testId}-clear` : undefined}
          onClick={() => onChange("")}><X size={14} /></button>
      ) : null}
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder, testId, ariaLabel, children }) {
  return (
    <div className="filter-bar">
      <SearchInput value={value} onChange={onChange} placeholder={placeholder} testId={testId} ariaLabel={ariaLabel} />
      {children}
    </div>
  );
}

/**
 * StatusTabs — SATU implementasi tab status (FIX-8; dulu dua: di sini & `ListControls.jsx`).
 * tabs: [{ key, label, count?, testKey? }] · `testId(key)` (fungsi) ATAU `testIdPrefix` (→ `${prefix}-${key|all}`,
 * bilah `${prefix}-bar`) · `showZero` = angka 0 tetap tampil (perilaku `ListControls` lama).
 */
export function StatusTabs({ tabs, value, onChange, testId, groupTestId, testIdPrefix, showZero = false }) {
  const tid = (t) => (typeof testId === "function" ? testId(t.key)
    : testIdPrefix ? `${testIdPrefix}-${t.testKey || t.key || "all"}` : undefined);
  return (
    <div className="tab-bar" data-testid={groupTestId || (testIdPrefix ? `${testIdPrefix}-bar` : undefined)}>
      {tabs.map((t) => (
        <button key={t.key || "all"} type="button" data-testid={tid(t)}
          className={`tab-button ${value === t.key ? "active" : ""}`} onClick={() => onChange(t.key)}>
          {t.label}
          {(showZero ? t.count != null : Boolean(t.count)) ? <span className="tab-badge">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
