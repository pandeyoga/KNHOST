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
 */
export function useTableFilter(rows, { text, status, statusLabel = (s) => s, sorts = null } = {}) {
  const [q, setQ] = useState("");
  const [st, setSt] = useState("");
  const sortKeys = sorts ? Object.keys(sorts) : [];
  const [sort, setSort] = useState(sortKeys[0] || "");
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

export default function TableFilterBar({ f, testId, placeholder = "Cari…", onChange, searchTestId = "" }) {
  // Pola UI (04_POLA_UI §1.2, permintaan pemilik 16 Nov) — saringan status = DROPDOWN, sebaris dengan cari & urutan.
  // Dulu deret chip "Semua · Status A · n …" yang memakan baris sendiri dan berbeda dari layar lain.
  const set = (fn) => (v) => { fn(v); onChange?.(); };
  const total = f.statuses.reduce((n, s) => n + s.n, 0);
  return (
    <div data-testid={`${testId}-filter`} className="flex flex-wrap items-center gap-2 px-3 py-2">
      <label className="flex min-w-[160px] flex-1 items-center gap-1.5 rounded-lg border border-kn-field-border bg-white px-2 py-1">
        <Search size={13} className="shrink-0 text-kn-neutral" />
        <input data-testid={searchTestId || `${testId}-search`} value={f.q} onChange={(e) => set(f.setQ)(e.target.value)}
          placeholder={placeholder} aria-label={placeholder} className="w-full bg-transparent text-fs-12 outline-none" />
      </label>
      {f.statuses.length > 1 && (
        <KNSelect data-testid={`${testId}-status`} value={f.st} onValueChange={(v) => set(f.setSt)(v || "")} aria-label="Saring status"
          className="!h-auto !w-auto rounded-lg border border-kn-field-border bg-white !px-2 !py-1 text-fs-12"
          options={[{ value: "", label: `Semua status (${total})` },
            ...f.statuses.map((s) => ({ value: s.key, label: `${s.label} (${s.n})` }))]} />
      )}
      {f.sorts && Object.keys(f.sorts).length > 1 && (
        <KNSelect data-testid={`${testId}-sort`} value={f.sort} onValueChange={(v) => set(f.setSort)(v)} aria-label="Urutan"
          className="!h-auto !w-auto rounded-lg border border-kn-field-border bg-white !px-2 !py-1 text-fs-12"
          options={Object.entries(f.sorts).map(([k, v]) => ({ value: k, label: v.label }))} />
      )}
    </div>
  );
}
