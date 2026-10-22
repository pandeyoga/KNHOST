import { useMemo, useState } from "react";
import { Search } from "lucide-react";

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
  const set = (fn) => (v) => { fn(v); onChange?.(); };
  return (
    <div data-testid={`${testId}-filter`} className="flex flex-wrap items-center gap-1.5 px-3 py-1.5">
      <label className="flex min-w-[160px] flex-1 items-center gap-1.5 rounded-lg border border-[#E5E5EA] bg-white px-2 py-1">
        <Search size={12} className="shrink-0 text-[#8E8E93]" />
        <input data-testid={searchTestId || `${testId}-search`} value={f.q} onChange={(e) => set(f.setQ)(e.target.value)}
          placeholder={placeholder} className="w-full bg-transparent text-[11px] outline-none" />
      </label>
      {f.statuses.length > 1 && (
        <div className="flex flex-wrap gap-1">
          <button type="button" data-testid={`${testId}-status-all`} onClick={() => set(f.setSt)("")}
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${!f.st ? "bg-[#0058CC] text-white" : "bg-[#F2F3F5] text-[#3C3C43]"}`}>Semua</button>
          {f.statuses.map((s) => (
            <button key={s.key} type="button" data-testid={`${testId}-status-${s.key}`} onClick={() => set(f.setSt)(s.key)}
              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${f.st === s.key ? "bg-[#0058CC] text-white" : "bg-[#F2F3F5] text-[#3C3C43]"}`}>
              {s.label} · {s.n}
            </button>
          ))}
        </div>
      )}
      {f.sorts && Object.keys(f.sorts).length > 1 && (
        <select data-testid={`${testId}-sort`} value={f.sort} onChange={(e) => set(f.setSort)(e.target.value)}
          className="rounded-lg border border-[#E5E5EA] bg-white px-1.5 py-1 text-[10.5px]">
          {Object.entries(f.sorts).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      )}
    </div>
  );
}
