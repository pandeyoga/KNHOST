import usePagedRows from "@/hooks/usePagedRows";

// Paginasi baris tabel di dalam <tbody>: render 25 baris per halaman + baris pager.
export default function PagedRows({ rows, pageSize = 25, testId = "table-pager", children }) {
  const { pageRows, pager, page } = usePagedRows(rows, { pageSize, testId });
  const offset = (page - 1) * pageSize;
  const pages = Math.ceil((rows?.length || 0) / pageSize);
  return (
    <>
      {pageRows.map((row, i) => children(row, offset + i))}
      {pages > 1 && (
        <tr className="kn-pager-row">
          <td colSpan={99}>{pager}</td>
        </tr>
      )}
    </>
  );
}
