/**
 * PREP-D1 — riwayat lintasan gate U300 V2: hasil berwarna (Hijau/Kuning/Merah/Batal), daftar alasan (reason_codes,
 * istilah Indonesia), hitungan cocok/sisa/lain/lemah/latar, tindak lanjut & unduh bukti. Antrean periksa lengkap =
 * paket D2 (belum di sini).
 */
import { useState } from "react";
import { Pill } from "./rfidShared";
import { LEVEL_COLOR, reasonText, verdictInfo } from "./u300Labels";

function Reasons({ decision }) {
  const items = (decision?.reasons || []).filter((r) => r.level !== "INFO" || decision.verdict === "CANCELLED");
  const codes = items.length ? items : (decision?.reason_codes || []).map((code) => ({ code, level: "INFO" }));
  const seen = new Set();
  return (
    <ul className="space-y-0.5" data-testid="u300-reasons">
      {codes.filter((r) => (seen.has(r.code) ? false : seen.add(r.code))).slice(0, 6).map((r) => (
        <li key={r.code} className="flex items-center gap-1">
          <Pill color={LEVEL_COLOR[r.level] || "gray"}>{r.level === "RED" ? "pelanggaran" : r.level === "REVIEW" ? "periksa" : "info"}</Pill>
          <span className="text-[11px] text-[#3C3C43]">{reasonText(r.code)}</span>
        </li>
      ))}
    </ul>
  );
}

function Counts({ c }) {
  if (!c) return <span className="text-[11px] text-[#8E8E93]">—</span>;
  return (
    <span className="text-[11px] text-[#3C3C43]">
      cocok {c.matched} · sisa dokumen {c.pending}
      {c.extra ? ` · di luar dokumen ${c.extra}` : ""}{c.unknown ? ` · asing ${c.unknown}` : ""}
      {c.weak ? ` · lemah ${c.weak}` : ""}{c.background ? ` · latar ${c.background}` : ""}
    </span>
  );
}

export default function U300PassageList({ passages, busy, onAcknowledge, onEvidence, page }) {
  const [notes, setNotes] = useState({});
  if (!passages?.length) {
    return <p className="text-[12px] text-[#6B6B73]" data-testid="u300-passages-empty">Belum ada lintasan tercatat.</p>;
  }
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[12px]" data-testid="u300-passages">
          <thead><tr className="text-[11px] text-[#6B6B73]">
            <th className="p-2">Waktu</th><th className="p-2">Hasil</th><th className="p-2">Alasan</th>
            <th className="p-2">Roll</th><th className="p-2">Tindak lanjut</th>
          </tr></thead>
          <tbody>
            {passages.map((p) => {
              const v = verdictInfo(p.decision, p.state);
              const id = p.local_passage_id;
              const canAck = p.decision && p.decision.verdict !== "GREEN" && p.decision.verdict !== "CANCELLED" && !p.acknowledged;
              return (
                <tr key={id} className="border-t border-[#EFF0F2] align-top" data-testid={`u300-passage-${id}`}>
                  <td className="p-2">{new Date(p.created_at).toLocaleString("id-ID")}
                    {p.simulated && <div><Pill color="purple">simulasi</Pill></div>}
                    {p.decision?.sources?.length > 0 && <div className="text-[10px] text-[#6B6B73]">{p.decision.sources.map((s) => s.display_ref).join(", ")}</div>}
                  </td>
                  <td className="p-2"><Pill color={v.color} testId={`u300-verdict-${id}`}>{v.short}</Pill>
                    {p.decision?.verdict === "REVIEW" && <div className="text-[10px] text-[#8A5A00]">barang jalan · gate tidak terkunci</div>}
                    {p.decision?.binding_mode === "auto" && <div className="text-[10px] text-[#6B6B73]">dokumen auto-cocok</div>}
                  </td>
                  <td className="p-2"><Reasons decision={p.decision} /></td>
                  <td className="p-2"><Counts c={p.decision?.counts} /></td>
                  <td className="p-2 space-y-1">
                    {canAck && (
                      <div className="flex flex-wrap gap-1">
                        <input aria-label={`Catatan pemeriksaan ${id}`} placeholder="Hasil pemeriksaan" value={notes[id] || ""}
                          onChange={(e) => setNotes({ ...notes, [id]: e.target.value })} className="field !py-1 text-[11px] w-44" />
                        <button type="button" className="secondary-button !py-1 text-[11px]" data-testid={`u300-ack-${id}`}
                          disabled={busy || (notes[id] || "").trim().length < 5}
                          onClick={() => onAcknowledge(p, notes[id])}>Catat pemeriksaan</button>
                      </div>
                    )}
                    {p.acknowledged && <span className="text-[11px] text-[#1B7E3B]">Sudah diperiksa</span>}
                    {p.latch_release && !p.acknowledged && <span className="text-[11px] text-[#6B6B73]">Kunci gate sudah dilepas</span>}
                    <button type="button" className="secondary-button !py-1 text-[11px]" disabled={busy}
                      onClick={() => onEvidence(p)}>Unduh bukti</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="secondary-button !py-1 text-[11px]" disabled={busy || !page.canPrev} onClick={page.prev}>Halaman sebelumnya</button>
        <button type="button" className="secondary-button !py-1 text-[11px]" disabled={busy || !page.canNext} onClick={page.next}>Riwayat lebih lama</button>
        <button type="button" className="secondary-button !py-1 text-[11px]" disabled={busy || !page.canPrev} onClick={page.reset}>Kembali ke terbaru</button>
      </div>
    </div>
  );
}
