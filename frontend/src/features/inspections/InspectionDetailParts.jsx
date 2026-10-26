/**
 * InspectionDetailParts — bagian pop-up rincian SPK Inspeksi yang tidak memegang aksi sendiri.
 *
 * Fase 4 · R3 — diekstrak dari `InspectionDetailPanel.jsx` (658 baris, > batas 500) TANPA mengubah perilaku:
 * markup, testid, dan teks sama persis. `InspectionLinesTable.jsx` memegang tabel baris pemeriksaan.
 */
import { CalendarClock } from "lucide-react";

// Cek UI UAT v3 (S8) — waktu dulu dipotong dari ISO UTC ("2026-10-21 19:57" padahal WIB 22 Okt 02.57).
export const localTs = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso).slice(0, 16).replace("T", " ");
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

// UAT 24 Okt (audit UI tahap 2) — kartu `.section-card` tanpa padding di dalam pop-up memotong huruf awal
// ("INDAKAN", "IWAYAT") → semua kartu di panel ini memakai `section-pad`; nilai panjang dibungkus, tidak terpotong di HP.
export function Row({ label, children, testId }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1">
      <span className="shrink-0 text-[11px] text-[#6B6B73]">{label}</span>
      <span data-testid={testId} className="min-w-0 break-words text-[11.5px] font-semibold text-[#1C1C1E] text-right">
        {children}
      </span>
    </div>
  );
}

/** Pemilih roll untuk "Buat SPK QC 4-point" dari SPK MD Quality (`pick` = daftar roll_id terpilih). */
export function Qc4Picker({ lines, pick, setPick, busy, onSubmit }) {
  return (
    <div data-testid="ins-qc4-picker" className="section-card section-pad grid gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] font-bold text-[#1C1C1E]">Pilih roll untuk SPK QC 4-point
          <span className="ml-1 font-normal text-[#6B6B73]">({pick.length} dari {lines.filter((ln) => ln.roll_id).length} roll)</span></p>
        <div className="flex gap-2 text-[11px] font-bold text-[#0058CC]">
          <button type="button" data-testid="ins-qc4-all" onClick={() => setPick(lines.filter((ln) => ln.roll_id).map((ln) => ln.roll_id))}>Semua</button>
          <button type="button" data-testid="ins-qc4-none" onClick={() => setPick([])}>Kosongkan</button>
        </div>
      </div>
      <div className="max-h-[220px] overflow-y-auto rounded-lg border border-[#EFF0F2]">
        {lines.filter((ln) => ln.roll_id).map((ln) => (
          <label key={ln.id} className="flex cursor-pointer items-center gap-2 border-b border-[#F6F6F8] px-2 py-1 text-[11.5px] last:border-0">
            <input type="checkbox" data-testid={`ins-qc4-roll-${ln.roll_id}`} checked={pick.includes(ln.roll_id)}
              onChange={() => setPick((cur) => (cur.includes(ln.roll_id) ? cur.filter((x) => x !== ln.roll_id) : [...cur, ln.roll_id]))} />
            <span className="font-mono font-semibold">{ln.roll_no || ln.sku}</span>
            <span className="text-[#6B6B73]">{ln.quantity} {ln.unit}{ln.lot ? ` · lot ${ln.lot}` : ""}</span>
            {ln.md_quality_at && <span className="ml-auto rounded-full bg-[#E8F6EE] px-1.5 text-[10px] font-bold text-[#1B7F4B]">MDQ ✓</span>}
          </label>
        ))}
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" className="secondary-button !h-8" onClick={() => setPick(null)}>Batal</button>
        <button type="button" data-testid="ins-qc4-submit" className="primary-button !h-8" disabled={busy || pick.length === 0}
          onClick={onSubmit}>Buat SPK untuk {pick.length} roll</button>
      </div>
    </div>
  );
}

/** Riwayat SPK (terbaru di atas). */
export function InspectionHistory({ doc }) {
  return (
    <div className="section-card section-pad">
      <p className="text-[11px] font-bold uppercase tracking-wide text-[#9A9BA3]">Riwayat</p>
      <div data-testid="ins-detail-history" className="mt-1 grid gap-1">
        {(doc.history || []).slice().reverse().map((h, i) => (
          <div key={`${h.at}-${i}`} className="flex items-start gap-2 text-[11px]">
            <CalendarClock size={12} className="mt-0.5 shrink-0 text-[#9A9BA3]" />
            <span className="text-[#3C3C43]">
              <strong>{h.label}</strong> · {h.actor} · {localTs(h.at)}
              {h.note ? <span className="text-[#6B6B73]"> — {h.note}</span> : null}
            </span>
          </div>
        ))}
        {(doc.history || []).length === 0 && (
          <p className="text-[11px] text-[#8E8E93]">Belum ada riwayat.</p>
        )}
      </div>
    </div>
  );
}
