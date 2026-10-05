import { useEffect, useMemo, useState } from "react";
import KNPager from "@/components/KNPager";

// Paginasi sisi-klien untuk tabel daftar yang datanya sudah dimuat penuh.
export default function usePagedRows(rows, { pageSize = 25, testId = "pager" } = {}) {
  const list = Array.isArray(rows) ? rows : [];
  const [page, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(list.length / pageSize));
  useEffect(() => { if (page > pages) setPage(1); }, [pages, page]);
  const pageRows = useMemo(() => list.slice((page - 1) * pageSize, page * pageSize), [list, page, pageSize]);
  const pager = <KNPager page={page} pageSize={pageSize} total={list.length} onChange={setPage} testId={testId} />;
  return { pageRows, pager, page, setPage };
}
