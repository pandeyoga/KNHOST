import { useEffect, useState } from "react";
import { Inbox, AlarmClock, ArrowRight } from "lucide-react";
import axios, { API } from "../../services/apiClient";

const entityParam = (sel) => (sel && sel !== "all" ? (sel.id || sel) : "");

/** Kartu tampil (ada isi) — aturan yang SAMA dengan penyembunyian kartu ini. */
export const returnSummaryHasContent = (d) => Boolean(d && (d.incoming || d.rolls || d.due_soon));

/**
 * Ringkasan retur internal (`GET /return-dispositions/summary`). `undefined` = sedang dimuat; `null` = tidak dimuat
 * (`enabled` false) atau gagal. Meja gelombang 1 — meja memakai hook ini supaya tab Pantau tahu apakah kartu benar-benar
 * tampil (kartu kosong menyembunyikan diri) sebelum memutuskan "Tidak ada pantauan".
 */
export function useReturnDeskSummary(selectedEntity, { enabled = true, refreshKey = 0 } = {}) {
  const [d, setD] = useState(enabled ? undefined : null);
  const ent = entityParam(selectedEntity);
  useEffect(() => {
    if (!enabled) { setD(null); return undefined; }
    let live = true;
    setD(undefined);
    axios.get(`${API}/return-dispositions/summary`, { params: ent ? { entity_id: ent } : {} })
      .then((r) => { if (live) setD(r.data); }).catch(() => { if (live) setD(null); });
    return () => { live = false; };
  }, [ent, enabled, refreshKey]);
  return d;
}

// LN-093 — kartu Beranda tim PT pemasok (mis. CST): retur internal masuk, roll menunggu keputusan,
// dan roll yang batas retur suppliernya tinggal ≤ N hari. Tersembunyi bila semuanya nol.
// `summary` (opsional) = data yang sudah dimuat pemanggil (`useReturnDeskSummary`); tanpa itu kartu memuat sendiri.
export default function ReturnDeskSummaryCard({ selectedEntity, onNavigate, summary }) {
  const own = useReturnDeskSummary(selectedEntity, { enabled: summary === undefined });
  const d = summary === undefined ? own : summary;
  if (!returnSummaryHasContent(d)) return null;
  const open = () => { sessionStorage.setItem("interco_tab", "return-inbox"); onNavigate?.("interco-transactions"); };
  const stat = (n, label, testid, warn) => (
    <div className="min-w-[120px]" data-testid={testid}>
      <p className={`text-2xl font-semibold tabular-nums ${warn && n ? "text-[#C62828]" : "text-[#1D1D1F]"}`}>{n}</p>
      <p className="text-[11px] text-[#6E6E73]">{label}</p>
    </div>
  );
  return (
    <section className="section-card mb-4 border-l-4 border-l-[#B45309]" data-testid="return-desk-summary">
      <div className="flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-2">
          <Inbox size={18} className="text-[#B45309]" />
          <div>
            <p className="text-sm font-semibold">Meja retur internal</p>
            <p className="text-[11px] text-[#6E6E73]">Retur dari PT grup yang wajib diterima & roll yang menunggu keputusan</p>
          </div>
        </div>
        {stat(d.incoming, "retur internal masuk", "return-desk-incoming")}
        {stat(d.rolls, "roll menunggu keputusan", "return-desk-rolls")}
        {stat(d.due_soon, "batas supplier dekat", "return-desk-due", true)}
        <button type="button" onClick={open} data-testid="return-desk-open"
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-[#1D1D1F] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#3A3A3C]">
          Buka Retur Masuk <ArrowRight size={13} />
        </button>
      </div>
      {d.due_items?.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-[11px] text-[#8A4B08]" data-testid="return-desk-due-list">
          {d.due_items.map((x) => (
            <li key={`${x.roll_no}-${x.deadline}`} className="inline-flex items-center gap-1.5 pr-4">
              <AlarmClock size={11} /> {x.roll_no} · {x.return_number} · batas {x.deadline} ({x.days_left === 0 ? "hari ini" : `${x.days_left} hari lagi`})
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
