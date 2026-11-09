/** RollsTable — daftar roll fisik (Roll-as-SSOT, Fase 0.5) + Pegging (Sub-fase 1.7). */
import { useState } from "react";
import { Layers, Anchor, Route } from "lucide-react";
import { formatQty, RollStatusBadge, MakloonLockBadge } from "./inventoryConstants";
import RollJourneyPopup from "../RollJourneyPopup";
import RollHoldControl from "./RollHoldControl";
import RollCheckChips from "../../../components/RollCheckChips";

import PagedRows from "@/components/PagedRows";
import EmptyState, { listStateKind } from "../../../components/EmptyState";   // FIX-8 — keadaan daftar baku

/** Kolom yang boleh disembunyikan lewat "Tampilan" (FIX-8, K-B4-12) — kunci = `saved_view_service.LISTS`. */
export const ROLL_OPTIONAL_COLUMNS = [
  { key: "owner", label: "Pemilik" }, { key: "warehouse", label: "Gudang" }, { key: "lot", label: "Lot" },
  { key: "dye_lot", label: "Dye Lot" }, { key: "grade", label: "Grade" }, { key: "weight", label: "Berat" },
  { key: "pegging", label: "Pegging" },
];
import StatusBadge from "../../../components/StatusBadge";   // FIX-8 — lencana baku

export default function RollsTable({
  loading, rolls = [], canPeg = false, onPeg, onUnpeg, busyRollId = null, onChanged,
  hidden = [], error = null, onRetry, filtered = false, onReset,
}) {
  const [journeyFor, setJourneyFor] = useState(null);
  const show = (key) => !hidden.includes(key);
  const colCount = 12 - ROLL_OPTIONAL_COLUMNS.filter((c) => hidden.includes(c.key)).length;
  // FIX-8 (B4 §3.10 · B1b UI-49/UI-50) — memuat · kosong · saringan kosong · galat · tanpa izin = EmptyState baku.
  const state = listStateKind({ loading, error, count: rolls.length, filtered });
  return (
    <div className="bg-white rounded-xl border border-[#EFF0F2] overflow-hidden" data-testid="rolls-table">
      <div className="overflow-x-auto">
        <table className="w-full text-[11.5px]">
          <thead>
            <tr className="bg-[#FAFBFC] border-b border-[#EFF0F2]">
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Roll No</th>
              <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Produk</th>
              {show("owner") && <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Pemilik</th>}
              {show("warehouse") && <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Gudang</th>}
              {show("lot") && <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Lot</th>}
              {show("dye_lot") && <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Dye Lot</th>}
              {show("grade") && <th className="text-center px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Grade</th>}
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Panjang</th>
              {show("weight") && <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Berat</th>}
              <th className="px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Status</th>
              {show("pegging") && <th className="text-left px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Pegging</th>}
              <th className="text-right px-3 py-2 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EFF0F2]">
            {state && (
              <EmptyState asRow colSpan={colCount} kind={state} what="roll" error={error} onRetry={onRetry} onReset={onReset}
                icon={Layers} title={state === "empty" ? "Tidak ada roll" : undefined} testId="rolls-table-state" />
            )}
            <PagedRows rows={rolls} testId="rolls-table-pager">{(r) => {
              const ear = r.earmarked_for;
              const busy = busyRollId === r.id;
              return (
                <tr key={r.id} data-testid={`roll-row-${r.id}`} className={`transition-colors ${ear ? "bg-[#FBF7FF] hover:bg-[#F6EDFF]" : "hover:bg-[#FAFBFC]"}`}>
                  <td className="px-3 py-2 font-bold text-[#007AFF] tabular-nums">
                    {r.roll_no}
                    {/* FASE SL — alias supplier (telusur balik komplain warna → dye lot pabrik) */}
                    {(r.supplier_roll_no || r.supplier_sku) && (
                      <p data-testid={`roll-supplier-alias-${r.id}`} className="mt-0.5 font-mono text-[9.5px] font-normal text-[#6B6B73]">
                        {r.supplier_roll_no ? `sup: ${r.supplier_roll_no}` : ""}{r.supplier_roll_no && r.supplier_sku ? " · " : ""}{r.supplier_sku || ""}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <p className="font-medium">{r.product_name}</p>
                    <p className="text-[10px] text-[#8E8E93]">{r.sku}</p>
                  </td>
                  {show("owner") && (
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center rounded-md bg-[#EEF2FF] px-1.5 py-0.5 text-[10px] font-semibold text-[#4338CA]">
                      {r.owner_entity_name}
                    </span>
                  </td>
                  )}
                  {show("warehouse") && (
                  <td className="px-3 py-2">
                    <p className="font-medium">{r.warehouse_name}</p>
                    <p className="text-[10px] text-[#8E8E93]">{r.warehouse_city}</p>
                  </td>
                  )}
                  {show("lot") && (
                  <td className="px-3 py-2 font-mono text-[10.5px] text-[#3C3C43]"
                    data-testid={`roll-lot-${r.id}`}>
                    {r.lot}
                    {/* Fase C — tanda roll belum bertaut lot kelas satu (mode peringatan) */}
                    {!r.lot_id && (
                      <StatusBadge tone="warning" title="Roll belum bertaut lot kelas satu — buka Lot & Silsilah untuk menambal"
                        className="ml-1">tanpa lot</StatusBadge>
                    )}
                  </td>
                  )}
                  {show("dye_lot") && (
                  <td className="px-3 py-2 font-mono text-[10.5px] text-[#6B219A]" data-testid={`roll-dyelot-${r.id}`}>
                    {r.dye_lot || "—"}
                    {r.supplier_lot && r.supplier_lot !== r.dye_lot && (
                      <span className="ml-1 text-[9px] text-[#8E8E93]">sup {r.supplier_lot}</span>
                    )}
                  </td>
                  )}
                  {show("grade") && (
                  <td className="px-3 py-2 text-center font-semibold">
                    {r.grade || "-"}
                    {Array.isArray(r.defects) && r.defects.length > 0 && (
                      <StatusBadge tone="danger" title={r.defects.join(", ")} className="ml-1" testId={`roll-defects-${r.id}`}>
                        {r.defects.length} cacat
                      </StatusBadge>
                    )}
                  </td>
                  )}
                  <td className="px-3 py-2 text-right font-bold tabular-nums">
                    {formatQty(r.length_remaining)} <span className="text-[9px] text-[#8E8E93]">{r.unit}</span>
                  </td>
                  {show("weight") && (
                  <td className="px-3 py-2 text-right tabular-nums" data-testid={`roll-weight-${r.id}`}>
                    {/* FASE U — UKURAN KEDUA roll. Roll kain sering diukur DUA kali:
                        panjang (yard/meter) dan berat (kg). `secondary_measures`
                        adalah petanya (satuan → nilai) dan `weight_kg` tetap sumber
                        untuk kg. Satuan lain yang sudah tersimpan ikut ditampilkan —
                        tanpa ini angka yang SUDAH ada di basis data tidak pernah
                        terlihat siapa pun, dan penimbangnya menyimpulkan datanya hilang. */}
                    {(() => {
                      const sec = r.secondary_measures && typeof r.secondary_measures === "object"
                        ? r.secondary_measures : {};
                      const kg = Number(sec.kg ?? r.weight_kg) || 0;
                      const extra = Object.entries(sec)
                        .filter(([u, v]) => u !== "kg" && Number(v) > 0);
                      if (!kg && extra.length === 0) return <span className="text-[#C7C7CC]">—</span>;
                      return (
                        <>
                          {kg > 0 && <>{formatQty(kg)} <span className="text-[9px] text-[#8E8E93]">kg</span></>}
                          {extra.map(([u, v]) => (
                            <span key={u} className="ml-1 text-[10px] text-[#6B6B73]">
                              {formatQty(v)} {u}
                            </span>
                          ))}
                        </>
                      );
                    })()}
                  </td>
                  )}
                  <td className="px-3 py-2">
                    <RollStatusBadge status={r.status} />
                    {/* FIX-9 — panjang dikunci cadangan makloon (MKO/PR pemiliknya) */}
                    <MakloonLockBadge roll={r} className="ml-1" />
                    {/* UAT 24 Okt (P11.4) — status cek MD Quality & 4-point per roll */}
                    <RollCheckChips roll={r} testId={`roll-check-${r.id}`} className="mt-1" />
                  </td>
                  {show("pegging") && (
                  <td className="px-3 py-2">
                    {ear ? (
                      <span
                        data-testid={`roll-earmark-badge-${r.id}`}
                        title={ear.note ? `Catatan: ${ear.note}` : `Di-peg untuk ${ear.name}`}
                        className="inline-flex items-center gap-1 rounded-md bg-[#F3E8FF] px-1.5 py-0.5 text-[10px] font-semibold text-[#6B219A] max-w-[150px]"
                      >
                        <Anchor size={9} className="shrink-0" />
                        <span className="truncate">{ear.name}</span>
                      </span>
                    ) : (
                      <span className="text-[#C7C7CC]">—</span>
                    )}
                  </td>
                  )}
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button
                      data-testid={`roll-journey-btn-${r.id}`}
                      onClick={() => setJourneyFor(r.id)}
                      title="Jejak Barang — timeline lengkap roll ini"
                      className="mr-1.5 inline-flex items-center gap-1 rounded-md border border-[#CFE0F5] bg-white px-2 py-1 text-[10.5px] font-semibold text-[#0058CC] hover:bg-[#F0F6FF]"
                    >
                      <Route size={10} /> Jejak
                    </button>
                    {!ear && <RollHoldControl roll={r} onChanged={onChanged} />}
                    {!canPeg && <span className="text-[#C7C7CC]">—</span>}
                    {canPeg && ear && (
                      <button
                        data-testid={`roll-unpeg-btn-${r.id}`}
                        onClick={() => onUnpeg?.(r)}
                        disabled={busy}
                        className="inline-flex items-center gap-1 rounded-md border border-[#E5C7F5] bg-white px-2 py-1 text-[10.5px] font-semibold text-[#6B219A] hover:bg-[#FBF7FF] disabled:opacity-50"
                      >
                        <Anchor size={10} /> {busy ? "…" : "Lepas"}
                      </button>
                    )}
                    {canPeg && !ear && r.status === "available" && (
                      <button
                        data-testid={`roll-peg-btn-${r.id}`}
                        onClick={() => onPeg?.(r)}
                        disabled={busy}
                        className="inline-flex items-center gap-1 rounded-md border border-[#D6CCF0] bg-white px-2 py-1 text-[10.5px] font-semibold text-[#6B219A] hover:bg-[#FBF7FF] disabled:opacity-50"
                      >
                        <Anchor size={10} /> Peg
                      </button>
                    )}
                    {canPeg && !ear && r.status !== "available" && (
                      <span className="text-[#C7C7CC]">—</span>
                    )}
                  </td>
                </tr>
              );
            }}</PagedRows>
          </tbody>
        </table>
      </div>
      {journeyFor && <RollJourneyPopup rollId={journeyFor} onClose={() => setJourneyFor(null)} />}
    </div>
  );
}
