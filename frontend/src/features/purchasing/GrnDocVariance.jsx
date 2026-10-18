import { useEffect, useState } from "react";
import { PackageSearch } from "lucide-react";
import { grnApi } from "../wms/grn/grnApi";
import { formatQty } from "../../utils/formatters";

const RES_LABEL = { accept_note: "diterima dgn catatan", claim_supplier: "klaim supplier", claim_makloon: "klaim makloon", reject_goods: "barang ditolak" };

/** Pencocokan tagihan (baca-saja): qty surat jalan vs hitung fisik per baris PO / langkah MKO dari kedatangan tertutup. */
export default function GrnDocVariance({ poId, mkoId, stepSeq, testId = "grn-doc-variance" }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!poId && !mkoId) return;
    const params = poId ? { po_id: poId } : { mko_id: mkoId, ...(stepSeq != null ? { step_seq: stepSeq } : {}) };
    grnApi.docVariance(params).then(setData).catch((e) => setErr(e?.response?.status === 403 ? "" : "Gagal memuat data kedatangan."));
  }, [poId, mkoId, stepSeq]);
  if (!data && !err) return null;
  const rows = data?.rows || [];
  return (
    <div data-testid={testId} className="rounded-md border border-[#EFF0F2]">
      <div className="flex items-center justify-between border-b border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5">
        <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase text-[#6B6B73]"><PackageSearch size={13} /> Surat jalan vs hitung fisik (Kedatangan)</span>
        {data?.claims > 0 && <span data-testid={`${testId}-claims`} className="rounded-full bg-[#FDECEC] px-2 py-0.5 text-[10px] font-semibold text-[#B4231F]">{data.claims} baris diklaim</span>}
      </div>
      {err && <p className="px-2.5 py-2 text-[11px] text-[#B4231F]">{err}</p>}
      {data && !rows.length && <p data-testid={`${testId}-empty`} className="px-2.5 py-2 text-[11px] text-[#6B6B73]">Belum ada kedatangan (GRN) tertutup untuk dokumen ini — penerimaan lewat jalur lama tidak punya angka surat jalan.</p>}
      {rows.length > 0 && (<>
        <div className="flex flex-wrap gap-2 px-2.5 py-2">
          {data.summary.map((s) => (
            <div key={`${s.product_id}-${s.role}`} data-testid={`${testId}-sum-${s.product_id}-${s.role}`} className="rounded-md border border-[#EFF0F2] px-2 py-1 text-[10.5px]">
              <p className="font-semibold">{s.product_name}{s.role === "byproduct" ? " · barang sisa" : ""}</p>
              <p className="tabular-nums">SJ {formatQty(s.declared_qty)} · hitung {formatQty(s.counted_qty)} {s.unit} ·{" "}
                <b className={s.diff_qty < 0 ? "text-[#B4231F]" : s.diff_qty > 0 ? "text-[#B26A00]" : "text-[#0F766E]"}>{s.diff_qty > 0 ? "+" : ""}{formatQty(s.diff_qty)}</b></p>
            </div>
          ))}
        </div>
        <table className="w-full text-[10.5px]">
          <thead className="bg-[#FAFBFC] text-[9.5px] uppercase text-[#6B6B73]">
            <tr>{["Kedatangan / SJ", "Barang (nama di SJ → KN)", "SJ", "Hitung", "Selisih", "Roll SJ/hitung", "Status"].map((h) => <th key={h} className="px-2 py-1 text-left">{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.grn_id}-${r.line_no}`} data-testid={`${testId}-row-${r.grn_number}-${r.line_no}`} className="border-t border-[#EFF0F2]">
                <td className="px-2 py-1"><span className="font-mono font-semibold">{r.grn_number}</span><span className="block text-[#6B6B73]">SJ {r.dn_number || "-"} · {r.dn_date || ""}</span></td>
                <td className="px-2">{r.supplier_text && <span className="block font-mono text-[#6B6B73]">{r.supplier_text}</span>}→ {r.product_name}{r.role === "byproduct" ? " (sisa)" : ""}</td>
                <td className="px-2 tabular-nums">{r.declared_qty == null ? "-" : formatQty(r.declared_qty)} {r.unit}</td>
                <td className="px-2 tabular-nums font-semibold">{formatQty(r.counted_qty)} {r.unit}</td>
                <td className={`px-2 tabular-nums font-semibold ${r.diff_qty < 0 ? "text-[#B4231F]" : r.diff_qty > 0 ? "text-[#B26A00]" : "text-[#0F766E]"}`}>
                  {r.diff_qty == null ? "-" : `${r.diff_qty > 0 ? "+" : ""}${formatQty(r.diff_qty)}`}{r.diff_pct ? ` (${r.diff_pct}%)` : ""}
                </td>
                <td className="px-2 tabular-nums">{r.declared_rolls ?? "-"} / {r.counted_rolls ?? 0}</td>
                <td className="px-2">{r.resolutions.length ? r.resolutions.map((a) => RES_LABEL[a] || a).join(", ") : r.classes.includes("match") ? "cocok" : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </>)}
    </div>
  );
}
