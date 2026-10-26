/**
 * SampleBoard — mode **Papan** layar Sample R&D (kolom per status yang masih berjalan).
 * Diekstrak dari `RndSamplesView` (fase 3 · P6) supaya layar gabungan tetap di bawah 500 baris; isi & testid
 * sama dengan papan sebelumnya.
 */
import { SAMPLE_BOARD_ACTIVE, SAMPLE_BOARD_ORDER, SAMPLE_STATUS_META } from "./rndMeta";
import SampleBoardCard from "./SampleBoardCard";

const DOT = { "pill-muted": "bg-[#B4B4BB]", "pill-info": "bg-[#0058CC]", "pill-warning": "bg-[#E08A00]", "pill-success": "bg-[#1A7A3A]", "pill-danger": "bg-[#C62828]" };

export default function SampleBoard({ rows, types, statusFilter, onOpen, onShowList }) {
  const grouped = {};
  SAMPLE_BOARD_ORDER.forEach((s) => { grouped[s] = []; });
  (rows || []).forEach((r) => { (grouped[r.status] = grouped[r.status] || []).push(r); });
  // 23 Okt — saringan status di luar kolom aktif (mis. "Pemenang dipilih") dulu membuat papan kosong
  // semua padahal hitungannya 2; kolom status itu kini ikut tampil saat disaring.
  const cols = statusFilter && !SAMPLE_BOARD_ACTIVE.includes(statusFilter) ? [...SAMPLE_BOARD_ACTIVE, statusFilter] : SAMPLE_BOARD_ACTIVE;
  const offBoard = (rows || []).filter((r) => !SAMPLE_BOARD_ACTIVE.includes(r.status) && r.status !== statusFilter);
  const offBoardText = Object.entries(offBoard.reduce((a, r) => ({ ...a, [r.status]: (a[r.status] || 0) + 1 }), {}))
    .map(([st, n]) => `${(SAMPLE_STATUS_META[st] || { label: st }).label}: ${n}`).join(", ");

  return (
    <>
      <div data-testid="rnd-samples-board" className="grid grid-flow-col auto-cols-[minmax(215px,1fr)] gap-2 overflow-x-auto pb-1">
        {cols.map((s) => {
          const meta = SAMPLE_STATUS_META[s] || { label: s, cls: "pill-muted" };
          const list = grouped[s] || [];
          return (
            <div key={s} data-testid={`rnd-samples-col-${s}`} className="rounded-xl border border-[#EFF0F2] bg-[#FAFBFC] p-2">
              <p className="mb-1.5 flex items-center justify-between text-[10.5px] font-bold uppercase tracking-wide text-[#6B6B73]">
                <span className="flex items-center gap-1.5">
                  <span className={`inline-block h-2 w-2 rounded-full ${DOT[meta.cls] || DOT["pill-muted"]}`} />
                  {meta.label}
                </span>
                <span data-testid={`rnd-samples-col-count-${s}`} className="rounded-full bg-white px-1.5 tabular-nums">{list.length}</span>
              </p>
              <div className="grid gap-1.5">
                {list.map((r) => <SampleBoardCard key={r.id} s={r} types={types} onOpen={() => onOpen(r.id)} />)}
                {list.length === 0 && <p className="px-1 py-1.5 text-[10.5px] text-[#B4B4BB]">— kosong —</p>}
              </div>
            </div>
          );
        })}
      </div>
      {/* Audit UI 24 Okt — papan hanya memuat kolom yang masih berjalan; sample selesai dulu "hilang" tanpa keterangan. */}
      {offBoard.length > 0 && (
        <p data-testid="rnd-samples-offboard-note" className="text-[11px] text-[#6B6B73]">
          {offBoard.length} permintaan sudah selesai ({offBoardText}) dan tidak tampil di papan.{" "}
          <button type="button" className="link-button" data-testid="rnd-samples-offboard-open" onClick={onShowList}>Lihat di tab Daftar</button>
        </p>
      )}
    </>
  );
}
