/**
 * previewParts (Meja gelombang 2) — bagian bersama isi pratinjau dokumen: baris fakta, tabel barang, ringkasan total.
 * Dipakai semua `bodies/*` supaya semua jenis dokumen tampil serupa (huruf: label 12/400, nilai 13/600, label kolom 12/600).
 */

/** Pasangan label–nilai. `items` = [{ key, label, content }]; item dengan `content` kosong dilewati. */
export function PreviewFacts({ items = [], testId = "doc-preview-facts" }) {
  const rows = items.filter((i) => i && i.content !== "" && i.content !== null && i.content !== undefined && i.content !== false);
  if (!rows.length) return null;
  return (
    <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2" data-testid={testId}>
      {rows.map((i) => (
        <div key={i.key} className="flex items-baseline gap-2" data-testid={`${testId}-${i.key}`}>
          <dt className="shrink-0 text-fs-12 text-kn-text-2">{i.label}</dt>
          <dd className="min-w-0 break-words text-fs-13 font-semibold text-kn-text">{i.content}</dd>
        </div>
      ))}
    </dl>
  );
}

const ALIGN = { right: "text-right", center: "text-center" };

/** Tabel baris. `columns` = [{ key, label, align?, render?(row) }]; sel tanpa `render` menampilkan `row[key]`. */
export function PreviewLines({ columns = [], rows = [], testId = "doc-preview-lines", empty = "Belum ada baris." }) {
  if (!rows.length) return <p className="text-fs-12 text-kn-text-2" data-testid={`${testId}-empty`}>{empty}</p>;
  return (
    <div className="overflow-x-auto" data-testid={testId}>
      <table className="w-full text-fs-13">
        <thead>
          <tr className="border-b border-kn-divider">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`py-1 pr-2 text-fs-12 font-semibold text-kn-text-2 ${ALIGN[c.align] || "text-left"}`}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => (
            <tr key={r.id || r.line_id || r.product_id || idx} className="border-b border-kn-divider align-top last:border-0" data-testid={`${testId}-row-${idx}`}>
              {columns.map((c) => (
                <td key={c.key} className={`py-1.5 pr-2 font-normal text-kn-text ${ALIGN[c.align] || "text-left"}`}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Ringkasan total. `rows` = [{ label, value, strong? }] — baris `strong` memakai nilai 13/600, lainnya 13/400. */
export function PreviewTotals({ rows = [], testId = "doc-preview-totals" }) {
  const shown = rows.filter((r) => r && r.value !== "" && r.value !== null && r.value !== undefined);
  if (!shown.length) return null;
  return (
    <dl className="ml-auto grid w-full max-w-xs gap-1" data-testid={testId}>
      {shown.map((r, idx) => (
        <div key={`${r.label}-${idx}`} className="flex items-baseline justify-between gap-3">
          <dt className="text-fs-12 text-kn-text-2">{r.label}</dt>
          <dd className={`text-fs-13 tabular-nums text-kn-text ${r.strong ? "font-semibold" : "font-normal"}`}>{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}
