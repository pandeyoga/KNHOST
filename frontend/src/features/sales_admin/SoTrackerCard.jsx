/**
 * SoTrackerCard — tabel SO aktif di setiap meja: status kini, tahap berikutnya, pemilik tahap.
 * Baris dengan `can_act` mendapat tombol aksi; selebihnya hanya info siapa yang menindaklanjuti.
 * Selesai/batal otomatis hilang (difilter server). 5 baris per halaman, paginasi di kartu.
 */
import { useCallback, useEffect, useState } from "react";
import { ClipboardList, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import usePagedRows from "@/hooks/usePagedRows";
import { formatCurrency } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { fmtWhen, ageTone } from "./workDeskApi";
import TableFilterBar, { useTableFilter } from "../../components/TableFilter";

// Trial 22 Okt (E7) — Pelacak SO: cari + filter status + urutan.
const TRACKER_SORTS = {
  server: { label: "Bawaan" },
  idle: { label: "Paling lama diam", cmp: (a, b) => Number(b.idle_days || 0) - Number(a.idle_days || 0) },
  newest: { label: "Terbaru dibuat", cmp: (a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")) },
  value: { label: "Nilai terbesar", cmp: (a, b) => Number(b.grand_total || 0) - Number(a.grand_total || 0) },
};

export default function SoTrackerCard({ desk = "me", selectedEntity = "all", onOpen, testPrefix = "desk" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { desk };
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      setData((await axios.get(`${API}/desks/so-tracker`, { params })).data); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat pelacak SO.")); }
    finally { setLoading(false); }
  }, [desk, selectedEntity]);
  useEffect(() => { load(); }, [load]);
  const all = data?.rows || [];
  const f = useTableFilter(all, {
    text: (r) => `${r.number || ""} ${r.customer_name || ""} ${r.sales_name || ""} ${r.next_step || ""} ${r.status_label || ""}`,
    status: (r) => (r.can_act ? "aksi" : r.status_label || ""),
    statusLabel: (s) => (s === "aksi" ? "Aksi di meja ini" : s), sorts: TRACKER_SORTS,
  });
  const rows = f.shown;
  const pg = usePagedRows(rows, { pageSize: 5, testId: `${testPrefix}-so-tracker-pager` });
  const p = `${testPrefix}-so-tracker`;
  return (
    <section className="section-card self-start" data-testid={p}>
      <div className="section-head">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <ClipboardList size={15} className="text-[#0058CC]" />
          <h2>Pelacak SO aktif</h2>
          <span className="rounded-full bg-[#EAF2FF] px-2 py-0.5 text-[10.5px] font-bold text-[#0058CC]" data-testid={`${p}-count`}>{data?.count ?? 0}</span>
          <span className="rounded-full bg-[#FFF4E5] px-2 py-0.5 text-[10.5px] font-bold text-[#8C4A00]" data-testid={`${p}-actionable`}>{data?.actionable ?? 0} aksi di meja ini</span>
        </div>
        <button className="icon-button" onClick={load} aria-label="Muat ulang pelacak SO" data-testid={`${p}-refresh`}>
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>
      <p className="px-3 pt-1.5 text-[11px] text-[#6B6B73]">SO baru muncul otomatis dan hilang setelah selesai/batal. Tombol aksi hanya muncul bila tahap berikutnya wewenang meja ini.</p>
      {error && <p className="px-3 py-2 text-[11.5px] text-[#C0392B]" data-testid={`${p}-error`}>{error}</p>}
      {all.length > 1 && <TableFilterBar f={f} testId={p} onChange={() => pg.setPage?.(1)} placeholder="Cari no. SO, pelanggan, sales, tahap…" />}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-[11.5px]">
          <thead><tr className="whitespace-nowrap border-b border-[#EFF0F2] text-left text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">
            <th className="px-3 py-2">SO</th><th className="px-2 py-2">Status</th><th className="px-2 py-2">Tahap berikutnya</th>
            <th className="px-2 py-2">Waktu</th><th className="px-2 py-2 text-right">Nilai</th><th className="px-3 py-2 text-right">Tindak lanjut</th>
          </tr></thead>
          <tbody className="divide-y divide-[#F4F5F7]">
            {loading && !data && <tr><td colSpan={6} className="px-3 py-6 text-center text-[#6B6B73]">Memuat…</td></tr>}
            {data && rows.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-[#6B6B73]" data-testid={`${p}-empty`}>{f.active ? "Tidak ada SO yang cocok dengan filter." : "Tidak ada SO aktif."}</td></tr>}
            {pg.pageRows.map((r) => <TrackerRow key={r.id} r={r} p={p} onOpen={onOpen} />)}
          </tbody>
        </table>
      </div>
      {rows.length > 5 && <div className="px-3 pb-2">{pg.pager}</div>}
    </section>
  );
}

function TrackerRow({ r, p, onOpen }) {
  const idle = ageTone(r.idle_days);
  return (
    <tr data-testid={`${p}-row-${r.id}`} className="h-[52px] hover:bg-[#FAFBFC]">
      <td className="px-3 py-1.5">
        <p className="font-bold text-[#0058CC]">{r.number}</p>
        <p className="max-w-[200px] truncate text-[11px] text-[#6B6B73]">{r.customer_name}{r.sales_name ? ` · ${r.sales_name}` : ""}</p>
        {/* Audit UI 24 Okt (118/144, HP) — kolom Tahap/Nilai/Tindak lanjut ada di luar layar 390px;
            ringkasannya + tombol aksi ditampilkan di bawah nomor SO khusus layar sempit. */}
        <div className="mt-1 grid gap-1 sm:hidden" data-testid={`${p}-m-${r.id}`}>
          <p className="text-[11px] text-[#31465F]">Berikutnya: <b>{r.next_step}</b> · {formatCurrency(r.grand_total)}</p>
          {r.can_act
            ? <button type="button" className="btn-secondary btn-xs w-fit" data-testid={`${p}-action-m-${r.id}`} onClick={() => onOpen?.(r)}>{r.action}</button>
            : <span className="text-[11px] text-[#6B6B73]">Menunggu {r.owner_label}</span>}
        </div>
      </td>
      <td className="px-2 py-1.5"><span className="whitespace-nowrap rounded-full border border-[#DCE3EC] bg-[#F7F9FC] px-2 py-0.5 text-[10.5px] font-bold text-[#31465F]" data-testid={`${p}-status-${r.id}`}>{r.status_label}</span></td>
      <td className="px-2 py-1.5"><p className="font-semibold text-[#1C1C1E]">{r.next_step}</p><p className="text-[10px] text-[#8E8E93]">oleh {r.owner_label}</p></td>
      <td className="px-2 py-1.5 text-[10.5px] text-[#31465F]" data-testid={`${p}-time-${r.id}`}>
        <p>Dibuat {fmtWhen(r.created_at)}</p>
        <p>Diperbarui {fmtWhen(r.updated_at)} <span className={`ml-1 rounded-full border px-1.5 text-[9px] font-bold ${idle.cls}`}>{idle.label}</span></p>
      </td>
      <td className="px-2 py-1.5 text-right tabular-nums font-semibold">{formatCurrency(r.grand_total)}</td>
      <td className="px-3 py-1.5 text-right">
        {r.can_act
          ? <button type="button" className="btn-secondary btn-xs" data-testid={`${p}-action-${r.id}`} onClick={() => onOpen?.(r)}>{r.action}</button>
          : <span className="text-[10.5px] text-[#6B6B73]" data-testid={`${p}-info-${r.id}`}>Menunggu {r.owner_label}</span>}
      </td>
    </tr>
  );
}
