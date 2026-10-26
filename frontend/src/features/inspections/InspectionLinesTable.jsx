/**
 * InspectionLinesTable — tabel "Barang yang diperiksa" di pop-up rincian SPK Inspeksi (+ tombol per baris).
 *
 * Fase 4 · R3 — diekstrak dari `InspectionDetailPanel.jsx` (658 baris, > batas 500) TANPA mengubah perilaku:
 * markup, testid, teks, dan gerbang tombol sama persis; aksi tetap dimiliki panel (dioper sebagai callback).
 */
import { Lock, LockOpen, XCircle } from "lucide-react";
import QtyDual from "../../components/QtyDual";
import { INS_COLOR_LABEL, INS_HANDFEEL_LABEL, resultPill } from "./inspectionsApi";

export default function InspectionLinesTable({
  doc, lines, open, busy, mdOnly, isMdKind, isRandom, isQc4,
  canMdq, canQc, canInspectAll, canReleaseHold, onOpenLine, onRelease, onReject,
}) {
  const bukaBaris = onOpenLine;
  const lepasTahanan = onRelease;
  const tolakBarang = onReject;
  return (
    <div className="section-card section-pad">
      <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-[#9A9BA3]">
        Barang yang diperiksa
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-[11.5px]">
          <thead>
            <tr className="bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73]">
              <th className="px-2 py-1.5 text-left">Roll / Artikel</th>
              <th className="px-2 py-1.5 text-right">Jumlah</th>
              <th className="px-2 py-1.5 text-right">Poin</th>
              <th className="px-2 py-1.5 text-left">Grade</th>
              <th className="px-2 py-1.5 text-left">Warna</th>
              <th className="px-2 py-1.5 text-left">Handfeel</th>
              <th className="px-2 py-1.5 text-right">Aksi</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((ln) => (
              <tr key={ln.id} data-testid={`ins-line-${ln.id}`}
                className="border-b border-[#F2F2F5] last:border-0">
                <td className="px-2 py-1.5">
                  <span className="font-semibold text-[#1C1C1E]">{ln.roll_no || ln.sku || "—"}</span>
                  <span className="block text-[10px] text-[#8E8E93]">{ln.article || ""}</span>
                  {ln.hold ? (
                    <span data-testid={`ins-line-hold-${ln.id}`} className="status-pill pill-danger mt-0.5">
                      <Lock size={9} className="mr-0.5 inline" /> DITAHAN
                    </span>
                  ) : null}
                  {ln.random_check_result ? (
                    <span data-testid={`ins-line-rc-${ln.id}`}
                      className={`status-pill mt-0.5 ${ln.random_check_result === "lulus" ? "pill-success" : "pill-danger"}`}>
                      Random check {ln.random_check_result.toUpperCase()}
                    </span>
                  ) : null}
                  {ln.md_quality_decision?.action === "reject" ? (
                    <span data-testid={`ins-line-mdq-rejected-${ln.id}`} className="status-pill pill-danger mt-0.5">
                      Ditolak MD Quality
                    </span>
                  ) : null}
                  {(ln.md_quality_by || ln.qc_by) ? (
                    <span className="block text-[10px] text-[#8E8E93]">
                      {ln.md_quality_by ? `MDQ: ${ln.md_quality_by}` : ""}
                      {ln.md_quality_by && ln.qc_by ? " · " : ""}
                      {ln.qc_by ? `QC: ${ln.qc_by}` : ""}
                    </span>
                  ) : null}
                </td>
                <td className="px-2 py-1.5 text-right">
                  <QtyDual rolls={ln.qty_rolls} measure={ln.quantity} unit={ln.unit}
                    testId={`ins-line-qty-${ln.id}`} compact />
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">
                  {ln.points_snapshot === null || ln.points_snapshot === undefined
                    ? "—" : ln.points_snapshot}
                </td>
                <td className="px-2 py-1.5">
                  {ln.grade_after
                    ? <span data-testid={`ins-line-grade-${ln.id}`}>
                        {ln.grade_before || "—"} &rarr; <strong>{ln.grade_after}</strong>
                        {ln.grade_rule?.status === "candidate_unvalidated" && <span data-testid={`ins-line-grade-candidate-${ln.id}`} title="Hasil lama sebelum aturan grade diputuskan" className="ml-1 rounded-full bg-[#FFF6E5] px-1.5 py-0.5 text-[9.5px] font-semibold text-[#B26A00]">kandidat</span>}
                        {ln.grade_rule?.grade_source && <span data-testid={`ins-line-grade-source-${ln.id}`} className="ml-1 rounded-full bg-[#EEF4FF] px-1.5 py-0.5 text-[9.5px] font-semibold text-[#0058CC]">{ln.grade_rule.grade_source === "user" ? "diisi QC" : "saran sistem"}</span>}
                      </span>
                    // 23 Okt — sebelum QC tampil jelas "belum QC" (dulu grade lama roll tampil seolah hasil periksa).
                    : (ln.grade_before
                      ? <span className="text-[#9A9BA3]" title="Grade roll saat ini — belum diperiksa QC" data-testid={`ins-line-grade-pending-${ln.id}`}>{ln.grade_before} · belum QC</span>
                      : "—")}
                </td>
                <td className="px-2 py-1.5">
                  <span className={`status-pill ${resultPill(ln.color_result)}`}>
                    {INS_COLOR_LABEL[ln.color_result] || "Belum diperiksa"}
                  </span>
                </td>
                <td className="px-2 py-1.5">
                  <span className={`status-pill ${resultPill(ln.handfeel_result)}`}>
                    {INS_HANDFEEL_LABEL[ln.handfeel_result] || "Belum diperiksa"}
                  </span>
                </td>
                <td className="px-2 py-1.5 text-right">
                  <div className="flex flex-wrap justify-end gap-1">
                    {/* F-13 (keputusan owner Q-06b) — MD Quality hanya sesudah SPK ditugaskan (bukan draft) */}
                    {canMdq && open && doc.status !== "draft" && (
                      <button data-testid={`ins-line-mdq-${ln.id}`} className="link-button"
                        onClick={() => bukaBaris(ln, "md_quality")}>
                        {ln.md_quality_at ? "Ubah MD Quality" : "MD Quality"}
                      </button>
                    )}
                    {/* Cek UI UAT v3 (S6) — SPK QC Pesanan / retur: peran QC (qc.inspect) dulu tidak punya tombol sama
                        sekali (hanya "Isi hasil" untuk inspection.inspect). Kini QC 4-point tampil bila "Isi hasil" tidak. */}
                    {canQc && ln.roll_id && !mdOnly && (isMdKind || isRandom || isQc4 || !canInspectAll) && ["assigned", "in_progress"].includes(doc.status) && (
                      <button data-testid={`ins-line-qc-${ln.id}`} className="link-button"
                        onClick={() => bukaBaris(ln, "qc")}>
                        {ln.qc_at ? "Ubah QC 4-point" : "QC 4-point"}
                      </button>
                    )}
                    {canInspectAll && !isMdKind && !isRandom && !isQc4 && open && doc.status !== "draft" && (
                      <button data-testid={`ins-line-inspect-${ln.id}`} className="link-button"
                        onClick={() => bukaBaris(ln, "")}>
                        {ln.inspected_at ? "Ubah hasil" : "Isi hasil"}
                      </button>
                    )}
                    {ln.hold && canReleaseHold && (
                      <button data-testid={`ins-line-release-${ln.id}`} className="link-button"
                        disabled={busy} onClick={() => lepasTahanan(ln)}>
                        <LockOpen size={11} className="mr-0.5 inline" /> Lepas tahanan
                      </button>
                    )}
                    {ln.hold && canReleaseHold && ln.md_quality_decision?.action !== "reject" && (
                      <button data-testid={`ins-line-reject-${ln.id}`} className="link-button !text-[#C62828]"
                        disabled={busy} onClick={() => tolakBarang(ln)}>
                        <XCircle size={11} className="mr-0.5 inline" /> Tolak barang
                      </button>
                    )}
                    {ln.hold && !canReleaseHold && (
                      <span data-testid={`ins-line-hold-note-${ln.id}`} className="text-[10px] text-[#B45309]">
                        {isRandom ? "dilepas saat SPK diputuskan" : "menunggu keputusan MD Quality / manajer"}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {lines.length === 0 && (
              <tr><td colSpan={7} className="px-2 py-3 text-center text-[11px] text-[#8E8E93]">
                SPK ini belum punya baris barang — biasanya karena roll penerimaannya
                belum dibuat. Muat ulang setelah penerimaan selesai.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      {lines.some((l) => l.hold) && (
        <p data-testid="ins-hold-explainer" className="mt-1.5 text-[11px] text-[#B45309]">
          {isRandom
            ? "Roll random check DITAHAN selama dicek. Saat SPK diputuskan: roll lulus otomatis dilepas, roll yang barisnya “tolak” (atau SPK ditolak) tetap ditahan; grade mengikuti hasil 4-point."
            : "Barang yang DITAHAN tidak bisa ditempatkan ke rak (putaway) sebelum MD Quality (atau manajer) melepasnya ber-alasan — supaya barang menyimpang tidak terjual diam-diam."}
        </p>
      )}
    </div>
  );
}
