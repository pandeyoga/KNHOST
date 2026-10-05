import { useMemo, useState } from "react";
import { SearchBox } from "@/components/ListControls";
import usePagedRows from "@/hooks/usePagedRows";

const text = (row, fields) => (!fields
  ? Object.values(row || {}).filter((v) => typeof v === "string" || typeof v === "number")
  : typeof fields === "function" ? [fields(row)] : fields.map((f) => row?.[f]))
  .flat().map((v) => String(v ?? "")).join(" ").toLowerCase();

/** Cari + paginasi seragam untuk daftar di sisi klien. `fields`: kunci / fungsi row→teks (kosong = semua teks baris). */
export default function useListSearch(rows, fields = null, { pageSize = 25, testId = "list", placeholder = "Cari…" } = {}) {
  const [q, setQ] = useState("");
  const list = Array.isArray(rows) ? rows : [];
  const term = q.trim().toLowerCase();
  const shown = useMemo(() => (term ? list.filter((r) => text(r, fields).includes(term)) : list),
    [list, term]); // eslint-disable-line react-hooks/exhaustive-deps
  const { pageRows, pager } = usePagedRows(shown, { pageSize, testId: `${testId}-pager` });
  const searchBox = <SearchBox value={q} onChange={setQ} placeholder={placeholder} testId={`${testId}-search`} />;
  const toolbar = (
    <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2" data-testid={`${testId}-toolbar`}>
      {searchBox}{shown.length > pageSize ? pager : null}
    </div>
  );
  return { q, setQ, shown, pageRows, pager: shown.length > pageSize ? pager : null, searchBox, toolbar };
}
