/** PREP-A — tabel pratinjau lembar perbaikan master: ringkasan per tindakan + galat/peringatan per baris. */
import { useState } from "react";
import { ACTION_LABEL } from "./masterCleanupApi";

const MAX_SHOWN = 300;

export default function MasterCleanupPreview({ pv }) {
  const [onlyIssues, setOnlyIssues] = useState(false);
  const s = pv.summary || {};
  const rows = (pv.rows || []).filter((r) => !onlyIssues || r.errors.length || r.warnings.length);
  return (
    <div className="space-y-2">
      <p data-testid="mc-summary" className="flex flex-wrap gap-x-3 gap-y-1">
        <span><b>{pv.source_filename || "Lembar"}</b> · {s.rows_read} baris dibaca · {s.pertahankan} dipertahankan</span>
        {["GANTI_NAMA", "GANTI_KODE", "GABUNG_KE", "NONAKTIFKAN"].map((a) => (
          <span key={a} data-testid={`mc-summary-${a}`}>{ACTION_LABEL[a]}: <b>{s[a] || 0}</b></span>
        ))}
        <span data-testid="mc-summary-errors" className={s.errors ? "font-semibold text-[#C0392B]" : "text-[#0A7A3B]"}>Galat: {s.errors || 0}</span>
        <span data-testid="mc-summary-warnings" className="text-[#8C4A00]">Peringatan: {s.warnings || 0}</span>
      </p>
      {(pv.general_errors || []).length > 0 && (
        <ul data-testid="mc-general-errors" className="list-disc pl-5 text-[#C0392B]">
          {pv.general_errors.map((t) => <li key={t}>{t}</li>)}
        </ul>
      )}
      <label className="inline-flex items-center gap-1.5 text-[11.5px]">
        <input type="checkbox" data-testid="mc-only-issues" checked={onlyIssues} onChange={(e) => setOnlyIssues(e.target.checked)} />
        Hanya baris bergalat/peringatan
      </label>
      <div className="max-h-[420px] overflow-auto">
        <table data-testid="mc-rows" className="w-full text-[11.5px]">
          <thead className="sticky top-0 bg-[#F7F7F9] text-left text-[10.5px] uppercase text-[#8E8E93]">
            <tr><th className="px-2 py-1.5">Baris</th><th className="px-2 py-1.5">SKU · nama</th><th className="px-2 py-1.5">Tindakan</th><th className="px-2 py-1.5">Rincian / alasan</th></tr>
          </thead>
          <tbody>
            {rows.slice(0, MAX_SHOWN).map((r) => (
              <tr key={`${r.row}-${r.sku}`} data-testid={`mc-row-${r.row}`} className="border-t border-[#F0F0F3] align-top">
                <td className="px-2 py-1.5 tabular-nums">{r.row}</td>
                <td className="px-2 py-1.5"><span className="font-mono">{r.sku || "—"}</span>{r.name ? ` · ${r.name}` : ""}</td>
                <td className={`px-2 py-1.5 font-semibold ${r.errors.length ? "text-[#C0392B]" : "text-[#0A7A3B]"}`}>{ACTION_LABEL[r.tindakan] || r.tindakan}</td>
                <td className="px-2 py-1.5">
                  {r.detail && <div>{r.detail}</div>}
                  {r.errors.map((t) => <div key={t} data-testid={`mc-row-error-${r.row}`} className="text-[#C0392B]">✗ {t}</div>)}
                  {r.warnings.map((t) => <div key={t} className="text-[#8C4A00]">! {t}</div>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > MAX_SHOWN && <p className="py-1 text-[#8E8E93]">… {rows.length - MAX_SHOWN} baris lagi (pakai saringan “hanya bergalat”).</p>}
        {!rows.length && <p data-testid="mc-rows-empty" className="py-2 text-[#8E8E93]">Tidak ada baris bertindakan.</p>}
      </div>
    </div>
  );
}
