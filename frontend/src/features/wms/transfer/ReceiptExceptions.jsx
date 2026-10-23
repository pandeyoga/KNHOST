/** P03 — exception transfer (hilang, roll salah, rusak, aturan): lapor dengan alasan, supervisor menyelesaikan. */
import { useState } from "react";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { askReason } from "../../../services/confirmService";
import ErrorNotice from "../../../components/ErrorNotice";
import KNSelect from "../../../components/KNSelect";

const KIND = { missing: "Hilang / tidak tiba", wrong_roll: "Roll salah", damaged: "Rusak", rule_violation: "Aturan gudang", other: "Lainnya" };

export default function ReceiptExceptions({ transfer, data, open, isSup, rolls = [], onDone }) {
  const [rollId, setRollId] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const transit = rolls.filter((r) => r.state === "in_transit");

  const reportMissing = async () => {
    setErr("");
    try {
      const r = await axios.post(`${API}/transfers/${transfer.id}/exceptions`, { kind: "missing", roll_id: rollId, reason });
      setReason(""); setRollId(""); onDone(r.data.summary);
    } catch (e) { setErr(apiErrorText(e, "Gagal mencatat exception.")); }
  };
  const resolve = async (exc, action) => {
    const why = await askReason({
      title: action === "return_to_source" ? "Kembalikan roll ke gudang asal?" : "Tutup exception dengan catatan?",
      message: action === "return_to_source" ? "Roll keluar dari perjalanan dan kembali tercatat di gudang asal (komitmen SO tetap)." : "Exception ditutup; catatan tersimpan.",
      reasonLabel: "Alasan", confirmLabel: "Simpan", testId: `exc-resolve-confirm-${exc.id}` });
    if (why === null) return;
    setErr("");
    try {
      const r = await axios.post(`${API}/transfers/${transfer.id}/exceptions/${exc.id}/resolve`, { action, reason: why });
      onDone(r.data.summary);
    } catch (e) { setErr(apiErrorText(e, "Gagal menyelesaikan exception.")); }
  };

  return (
    <div data-testid="transfer-exceptions" className="space-y-2">
      <h5 className="text-[11px] font-bold uppercase tracking-wide text-[#3C3C43]">Pengecualian ({data.open_exceptions} terbuka)</h5>
      {(data.exceptions || []).map((e) => (
        <div key={e.id} data-testid={`transfer-exc-${e.id}`} className={`rounded-md border px-2 py-1 text-[11px] ${e.status === "open" ? "border-[#F1C4C1] bg-[#FDF1F0]" : "border-[#E5E5EA] bg-white"}`}>
          <b>{KIND[e.kind] || e.kind}</b> {e.roll_no || e.code} — {e.reason}
          <span className="block text-[10px] text-[#6B6B73]">PIC {e.by} · {String(e.at || "").slice(0, 16).replace("T", " ")}
            {e.status !== "open" && ` · selesai: ${e.resolution} oleh ${e.resolved_by} (${e.resolution_reason})`}</span>
          {e.status === "open" && isSup && (
            <span className="mt-1 flex gap-2">
              {e.roll_id && ["missing", "rule_violation"].includes(e.kind) && (
                <button data-testid={`exc-return-${e.id}`} onClick={() => resolve(e, "return_to_source")} className="text-[#0058CC] underline">Kembalikan ke gudang asal</button>
              )}
              {!["missing", "rule_violation"].includes(e.kind) && (
                <button data-testid={`exc-close-${e.id}`} onClick={() => resolve(e, "close_note")} className="text-[#0058CC] underline">Tutup dengan catatan</button>
              )}
            </span>
          )}
        </div>
      ))}
      {open && transit.length > 0 && (
        <div className="flex flex-wrap gap-1">
          <KNSelect data-testid="exc-missing-roll" value={rollId} onValueChange={setRollId} aria-label="Roll tidak tiba"
            className="!h-auto !w-auto rounded border border-gray-200 text-[11px]"
            options={[{ value: "", label: "Roll tidak tiba…" }, ...transit.map((r) => ({ value: r.roll_id, label: r.roll_no }))]} />
          <input data-testid="exc-missing-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Keterangan / bukti (wajib)"
            className="flex-1 rounded border border-gray-200 px-1 text-[11px]" />
          <button data-testid="exc-missing-submit" disabled={!rollId} onClick={reportMissing} className="rounded bg-[#FF9500] px-2 text-[11px] text-white disabled:opacity-40">Laporkan hilang</button>
        </div>
      )}
      <ErrorNotice message={err} onDismiss={() => setErr("")} testId="transfer-exc-error" />
    </div>
  );
}
