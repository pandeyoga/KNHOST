import { useState } from "react";
import { ChevronDown, ChevronRight, History, Pencil } from "lucide-react";
import { formatDateTime } from "../../../utils/formatters";

const SOURCE = { default: ["Bawaan", "bg-[#F4F4F6] text-[#5A5A63]"], global: ["Global", "bg-[#EAF2FF] text-[#0058CC]"], entity: ["Khusus PT", "bg-[#FFF4E5] text-[#B25E00]"] };
const STATUS = { ok: ["Lengkap", "text-[#1A7F37]"], unset: ["Belum diatur", "text-[#B42318]"], inactive: ["Akun nonaktif", "text-[#B42318]"] };

export function MappingRow({ row, canEdit, scoped, onEdit, onHistory }) {
  const [open, setOpen] = useState(false);
  const [src, srcCls] = SOURCE[row.source] || SOURCE.default;
  const [st, stCls] = STATUS[row.status] || STATUS.ok;
  return (
    <div data-testid={`glmap-row-${row.key}`} className="px-3 py-2.5">
      <div className="grid md:grid-cols-[1.7fr_1.4fr_110px_110px_150px] items-center gap-2">
        <button type="button" className="flex items-start gap-1 text-left min-w-0" onClick={() => setOpen(!open)} data-testid={`glmap-expand-${row.key}`}>
          {open ? <ChevronDown size={14} className="mt-0.5 shrink-0" /> : <ChevronRight size={14} className="mt-0.5 shrink-0" />}
          <span className="min-w-0"><span className="block text-[12px] font-semibold">{row.label}</span>
            <span className="block text-[10.5px] text-[#9A9BA3]">Dipakai saat {row.used_when}</span></span>
        </button>
        <span className="text-[12px]" data-testid={`glmap-account-${row.key}`}><b>{row.account_code}</b> · {row.account_name || "—"}</span>
        <span><span data-testid={`glmap-source-${row.key}`} className={`rounded px-1.5 py-0.5 text-[10.5px] font-semibold ${srcCls}`}>{src}</span></span>
        <span data-testid={`glmap-status-${row.key}`} className={`text-[11px] font-semibold ${stCls}`}>{st}</span>
        <span className="flex justify-end gap-1">
          <button type="button" className="icon-button" data-testid={`glmap-history-${row.key}`} onClick={onHistory} aria-label="Riwayat"><History size={13} /></button>
          {canEdit && <button type="button" className="secondary-button text-xs" data-testid={`glmap-edit-${row.key}`} onClick={onEdit}><Pencil size={12} /> {scoped ? "Atur PT" : "Ubah"}</button>}
        </span>
      </div>
      {open && <RowDetail row={row} />}
    </div>
  );
}

function RowDetail({ row }) {
  return (
    <div data-testid={`glmap-detail-${row.key}`} className="mt-2 ml-5 grid md:grid-cols-2 gap-3 rounded-md bg-[#FAFBFC] border border-[#EFF0F2] p-3 text-[11.5px]">
      <div>
        <p className="font-semibold mb-1">Contoh jurnal (Rp 100.000)</p>
        <table className="w-full"><tbody>
          <tr><td className="pr-2">Dr</td><td>{row.example.debit}</td><td className="text-right">100.000</td></tr>
          <tr><td className="pr-2 pl-3">Cr</td><td className="pl-3">{row.example.credit}</td><td className="text-right">100.000</td></tr>
        </tbody></table>
        <p className="mt-1 text-[#6B6B73]">Akun ini tampil di sisi yang sesuai kebutuhan "{row.label}".</p>
      </div>
      <div className="grid gap-1">
        <p><span className="text-[#6B6B73]">Fitur pemakai:</span> {row.used_by.join(", ")}</p>
        <p><span className="text-[#6B6B73]">Jenis akun diizinkan:</span> {row.allowed_type_labels.join(", ")}</p>
        <p><span className="text-[#6B6B73]">Akun bawaan:</span> {row.default}{row.source === "entity" ? ` · Global: ${row.global_code}` : ""}</p>
        <p className="text-[10.5px] text-[#9A9BA3]">Kode kebutuhan: {row.key}</p>
        {row.updated_by && <p className="text-[10.5px] text-[#9A9BA3]">Terakhir diubah {row.updated_by} · {formatDateTime(row.updated_at)}</p>}
      </div>
    </div>
  );
}
