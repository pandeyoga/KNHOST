import { formatDate, formatDateTime } from "../../utils/formatters";

const fmt = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 });

function cell(col, v) {
  if (v === null || v === undefined || v === "") return <span className="text-[#C7C7CC]">—</span>;
  if (col.type === "money") return `Rp ${fmt.format(v)}`;
  if (col.type === "number") return fmt.format(v);
  if (col.type === "bool") return v ? "Ya" : "Tidak";
  // UAT 24 Okt (audit UI tahap 2) — dulu potongan stempel UTC ("2026-10-24 18:30"); kini WIB berformat Indonesia.
  if (col.type === "datetime") return formatDateTime(v);
  if (col.type === "date") return formatDate(v);
  return String(v);
}

export default function PreviewTable({ data, datasetId = "", scopeText = "" }) {
  if (!data) return null;
  return (
    <div data-testid="export-preview" className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-[#6B6B73]">
        <span data-testid="export-preview-total"><b className="text-[#1C1C1E]">{fmt.format(data.total)}</b> baris cocok</span>
        <span>menampilkan {data.shown}</span>
        <span>Grain: {data.grain}</span>
        {/* G5-52 — cakupan baris disebut (angka bisa beda dari layar lain yang hanya badan usaha aktif / tanpa SO sampel). */}
        {scopeText && <span data-testid="export-preview-scope">Cakupan: {scopeText}{datasetId === "sales_orders" ? " · termasuk pesanan sampel & batal" : ""}</span>}
      </div>
      <p data-testid="export-preview-filter" className="text-[11.5px] text-[#6B6B73]">
        Filter: {data.filter_text} · Periode: {data.date_text} · Urutan: {data.sort_text}
      </p>
      <div className="overflow-x-auto rounded-lg border border-[#EFF0F2]">
        <table className="min-w-full text-[12px]">
          <thead className="bg-[#F7F7F9]">
            <tr>{data.columns.map((c) => <th key={c.key} className="text-left font-semibold text-[#3A3A3C] px-2.5 py-2 whitespace-nowrap">{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {data.rows.map((r, i) => (
              <tr key={i} data-testid={`export-preview-row-${i}`} className="border-t border-[#F0F0F3]">
                {data.columns.map((c) => (
                  <td key={c.key} className={`px-2.5 py-1.5 whitespace-nowrap ${["money", "number"].includes(c.type) ? "text-right tabular-nums" : ""}`}>
                    {cell(c, r[c.key])}
                  </td>
                ))}
              </tr>
            ))}
            {!data.rows.length && <tr><td className="px-3 py-6 text-center text-[#8E8E93]" colSpan={data.columns.length}>Tidak ada data yang cocok.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
