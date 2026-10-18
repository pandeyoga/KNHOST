/** L03 LN-034 — ringkasan siklus uji ulang di rincian sample: supplier, acuan, hasil teknis, keputusan PIC. */
import { Gavel } from "lucide-react";

export default function RevalidationBox({ sample, canPic, onPic, busy }) {
  const rv = sample.revalidation || {};
  const d = sample.decision || {};
  const pic = sample.pic_decision;
  const failed = d.result === "fail";
  return (
    <div className={`rounded-lg border p-3 text-[11.5px] ${failed ? "border-[#F5C6BE] bg-[#FFF8F6]" : "border-[#CDE9D6] bg-[#F4FCF6]"}`} data-testid="reval-box">
      <p className="font-bold text-[#1C1C1E]" data-testid="reval-box-supplier">
        Uji ulang {sample.product_sku} × {rv.supplier_name || "—"} · siklus {rv.cycle_no || 1}
      </p>
      <p className="mt-0.5 text-[#3C3C43]">Alasan siklus: {rv.reason || "—"}</p>
      <p className="text-[#3C3C43]" data-testid="reval-box-reference">
        Acuan: {rv.reference ? `${rv.reference.number} (siklus ${rv.reference.cycle_no}, ${rv.reference.result === "pass" ? "lulus" : rv.reference.result === "fail" ? "gagal" : "—"})` : "siklus pertama"}
      </p>
      {d.result && (
        <p className="mt-1" data-testid="reval-box-result">
          Hasil teknis: <b className={failed ? "text-[#C0392B]" : "text-[#1A7A3A]"}>{d.result_label}</b>
          {d.note ? ` — “${d.note}”` : ""} · tanpa harga & tanpa kontrak baru
          {d.contract_number ? <span data-testid="reval-box-contract"> · referensi kontrak <b>{d.contract_number}</b> (tidak diubah)</span> : null}
        </p>
      )}
      {sample.status === "pending_pic" && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="rounded bg-[#C0392B] px-2 py-0.5 text-[10px] font-bold text-white" data-testid="reval-box-pending-pic">Menunggu keputusan PIC</span>
          {canPic && (
            <button className="primary-button !py-1 text-[11px]" disabled={busy} data-testid="reval-pic-decide-button" onClick={onPic}>
              <Gavel size={12} /> Putuskan tindak lanjut
            </button>
          )}
        </div>
      )}
      {pic && (
        <p className="mt-1.5 text-[#3C3C43]" data-testid="reval-box-pic">
          Keputusan PIC: <b>{pic.action_label}</b> oleh {pic.by} — {pic.reason}
          {pic.scope?.documents?.length ? ` · dokumen: ${pic.scope.documents.join(", ")}` : ""}
          {pic.retest_number ? ` · siklus baru ${pic.retest_number}` : ""} · hasil tetap <b>GAGAL</b>
        </p>
      )}
    </div>
  );
}
