import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import KNSelect from "./KNSelect";

/**
 * Trial 22 Okt 2026 (E7, permintaan pemilik) — cari + filter status + urutan yang SERAGAM untuk tabel di semua meja
 * (antrean meja, Pelacak SO aktif, Keep & Pending). Penyaringan di sisi klien atas baris yang sudah dimuat meja.
 *
 * `text(row)`   → teks yang dicari (nomor, pelanggan, keterangan …)
 * `status(row)` → kunci status untuk chip filter (opsional); `statusLabel(key)` → label chip
 * `sorts`       → { kunci: { label, cmp } } — urutan pertama = bawaan server (tanpa cmp)
 * `initial`     → nilai awal { q, st, sort } (mis. dipulihkan dari sessionStorage); `sort` hanya dipakai bila kuncinya
 *                 ada di `sorts`. Hanya dibaca pada render pertama.
 */
export function useTableFilter(rows, { text, status, statusLabel = (s) => s, sorts = null, initial = {} } = {}) {
  const init = initial || {};
  const [q, setQ] = useState(() => (typeof init.q === "string" ? init.q : ""));
  const [st, setSt] = useState(() => (typeof init.st === "string" ? init.st : ""));
  const sortKeys = sorts ? Object.keys(sorts) : [];
  const [sort, setSort] = useState(() => (sortKeys.includes(init.sort) ? init.sort : sortKeys[0] || ""));
  const list = Array.isArray(rows) ? rows : [];
  const statuses = useMemo(() => {
    if (!status) return [];
    const m = new Map();
    list.forEach((r) => { const k = status(r); if (k) m.set(k, (m.get(k) || 0) + 1); });
    return [...m.entries()].map(([k, n]) => ({ key: k, label: statusLabel(k), n }));
  }, [list]); // eslint-disable-line react-hooks/exhaustive-deps
  const term = q.trim().toLowerCase();
  const shown = useMemo(() => {
    let out = list.filter((r) => (!st || status?.(r) === st) && (!term || String(text?.(r) || "").toLowerCase().includes(term)));
    const cmp = sorts?.[sort]?.cmp;
    if (cmp) out = [...out].sort(cmp);
    return out;
  }, [list, st, term, sort]); // eslint-disable-line react-hooks/exhaustive-deps
  const active = Boolean(term || st);
  return { q, setQ, st, setSt, sort, setSort, statuses, shown, active, sorts, reset: () => { setQ(""); setSt(""); } };
}

/**
 * Tinggi nyata bilah: `py-2` (16) + kontrol `h-8` (32) = 48 px — kartu antrean meja menghitung tinggi tetapnya dari sini.
 * `compact` (kartu setengah lebar): di ≥ 640 px tidak membungkus — cari menyusut (`min-w-0 flex-1`), dropdown dibatasi
 * lebarnya dan terpotong; di HP tetap boleh turun baris.
 */
export default function TableFilterBar({ f, testId, placeholder = "Cari…", onChange, searchTestId = "", compact = false }) {
  // Pola UI (04_POLA_UI §1.2, permintaan pemilik 16 Nov) — saringan status = DROPDOWN, sebaris dengan cari & urutan.
  // Dulu deret chip "Semua · Status A · n …" yang memakan baris sendiri dan berbeda dari layar lain.
  const set = (fn) => (v) => { fn(v); onChange?.(); };
  const total = f.statuses.reduce((n, s) => n + s.n, 0);
  const selectCls = `!h-8 ${compact ? "!w-auto max-w-[9.5rem] shrink-0" : "!w-auto"} rounded-lg border border-kn-field-border bg-white !px-2 !py-1 text-fs-12`;
  return (
    <div data-testid={`${testId}-filter`}
      className={`flex items-center gap-2 px-3 py-2 ${compact ? "flex-wrap sm:flex-nowrap" : "flex-wrap"}`}>
      <label className={`flex h-8 flex-1 items-center gap-1.5 rounded-lg border border-kn-field-border bg-white px-2 ${compact ? "min-w-[10rem] sm:min-w-0" : "min-w-[160px]"}`}>
        <Search size={13} className="shrink-0 text-kn-neutral" />
        <input data-testid={searchTestId || `${testId}-search`} value={f.q} onChange={(e) => set(f.setQ)(e.target.value)}
          placeholder={placeholder} aria-label={placeholder} className="w-full min-w-0 bg-transparent text-fs-12 outline-none" />
      </label>
      {f.statuses.length > 1 && (
        <KNSelect data-testid={`${testId}-status`} value={f.st} onValueChange={(v) => set(f.setSt)(v || "")} aria-label="Saring status"
          className={selectCls}
          options={[{ value: "", label: `Semua status (${total})` },
            ...f.statuses.map((s) => ({ value: s.key, label: `${s.label} (${s.n})` }))]} />
      )}
      {f.sorts && Object.keys(f.sorts).length > 1 && (
        <KNSelect data-testid={`${testId}-sort`} value={f.sort} onValueChange={(v) => set(f.setSort)(v)} aria-label="Urutan"
          className={selectCls}
          options={Object.entries(f.sorts).map(([k, v]) => ({ value: k, label: v.label }))} />
      )}
    </div>
  );
}
