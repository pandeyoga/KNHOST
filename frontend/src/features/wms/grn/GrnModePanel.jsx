import { useState } from "react";
import { ArrowRightLeft, CheckCircle2, History, PackageCheck } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import useReceivingMode, { notifyReceivingModeChanged } from "../../../hooks/useReceivingMode";
import { ErrorBox } from "./GrnBits";
import { errText } from "./grnApi";

function Stat({ label, value, testId, tone = "" }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] px-2.5 py-1.5">
      <p className="text-[9.5px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
      <p data-testid={testId} className={`font-mono text-[15px] font-bold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

function EntityCard({ e, onSwitched }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const grn = e.mode === "grn";
  const target = grn ? "legacy" : "grn";
  const id = e.entity_id;
  const go = async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.put(`${API}/goods-receipts/mode`, { entity_id: id, mode: target, reason: reason.trim() });
      setOpen(false); setReason(""); onSwitched(r.data);
    } catch (x) { setErr(errText(x)); } finally { setBusy(false); }
  };
  return (
    <div data-testid={`grn-mode-card-${id}`} className={`space-y-3 rounded-xl border p-4 ${grn ? "border-[#BFE5DC] bg-[#F7FCFB]" : "border-[#EFF0F2] bg-white"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[13px] font-bold">{e.entity_name}</p>
          <span data-testid={`grn-mode-pill-${id}`} className={`mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${grn ? "bg-[#0F766E] text-white" : "bg-[#F2F2F7] text-[#3C3C43]"}`}>
            {grn ? <><PackageCheck size={11} /> Kedatangan Barang (GRN)</> : <><History size={11} /> Lama — per tugas Barang Masuk</>}
          </span>
        </div>
        <button data-testid={`grn-mode-switch-${id}`} className={grn ? "secondary-button" : "primary-button"} onClick={() => setOpen((x) => !x)}>
          <ArrowRightLeft size={13} /> {grn ? "Kembali ke mode lama" : "Beralih ke Kedatangan"}
        </button>
      </div>
      <div className="grid grid-cols-4 gap-2">
        <Stat label="Tugas menunggu barang" value={e.waiting_tasks} testId={`grn-mode-waiting-${id}`} />
        <Stat label="Sudah mulai di layar lama" value={e.started_legacy + e.legacy_in_flight.length} testId={`grn-mode-started-${id}`} tone={e.started_legacy + e.legacy_in_flight.length ? "text-[#B26A00]" : ""} />
        <Stat label="Kedatangan terbuka" value={e.open_grns} testId={`grn-mode-open-${id}`} />
        <Stat label="Kedatangan ditutup" value={e.closed_grns} testId={`grn-mode-closed-${id}`} tone={e.closed_grns ? "text-[#0F766E]" : ""} />
      </div>
      {grn && e.legacy_in_flight.length > 0 && (
        <div data-testid={`grn-mode-inflight-${id}`} className="rounded-lg border border-[#F1D08A] bg-[#FFF9EC] p-2.5 text-[11px]">
          <p className="font-semibold text-[#8A5300]">Tugas lama yang masih boleh diselesaikan di layar Barang Masuk ({e.legacy_in_flight.length}):</p>
          <ul className="mt-1 space-y-0.5">
            {e.legacy_in_flight.map((t) => <li key={t.id}>• {t.po_number} · {t.product_name} — {t.received_qty || 0}/{t.expected_qty} {t.unit} ({t.status})</li>)}
          </ul>
        </div>
      )}
      {open && (
        <div data-testid={`grn-mode-confirm-box-${id}`} className="space-y-2 rounded-lg border border-[#E3E8F2] bg-[#F7F9FC] p-3 text-[11px]">
          {target === "grn" ? (
            <ul className="space-y-0.5 text-[#3C3C43]">
              <li>• Barang dari supplier & makloon hanya masuk stok lewat Kedatangan Barang yang ditutup (surat jalan → hitung fisik → rekonsiliasi).</li>
              <li>• Tombol terima di layar lama (Barang Masuk, "Terima Hasil" MKO, aplikasi gudang) disembunyikan dan ditolak server.</li>
              <li>• {e.started_legacy} tugas yang sudah mulai diterima tetap boleh diselesaikan di layar lama.</li>
              {!e.closed_grns && <li className="font-semibold text-[#B26A00]">• Belum ada Kedatangan yang ditutup di badan usaha ini — disarankan uji coba dulu.</li>}
            </ul>
          ) : <p className="text-[#3C3C43]">Layar Barang Masuk lama aktif kembali untuk semua tugas. Kedatangan yang sedang berjalan tetap bisa diselesaikan.</p>}
          <textarea data-testid={`grn-mode-reason-${id}`} rows={2} className="w-full rounded-lg border border-[#E5E5EA] px-2 py-1.5 text-[11.5px] focus:border-[#0058CC] focus:outline-none"
            placeholder="Alasan perubahan (wajib, tercatat di audit)" value={reason} onChange={(x) => setReason(x.target.value)} />
          <ErrorBox text={err} />
          <div className="flex justify-end gap-2">
            <button className="text-[11px] font-semibold text-[#6B6B73]" onClick={() => setOpen(false)}>Batal</button>
            <button data-testid={`grn-mode-confirm-${id}`} className="primary-button" disabled={busy || reason.trim().length < 5} onClick={go}>
              <CheckCircle2 size={13} /> {target === "grn" ? "Ya, beralih ke Kedatangan" : "Ya, kembali ke mode lama"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** GRN Fase 7 — beralih penuh per badan usaha. */
export default function GrnModePanel() {
  const { data } = useReceivingMode();
  const [msg, setMsg] = useState("");
  const onSwitched = (r) => {
    setMsg(r.mode === "grn" ? `${r.entity_name} kini memakai Kedatangan Barang${r.legacy_in_flight_marked ? ` · ${r.legacy_in_flight_marked} tugas lama ditandai boleh selesai di layar lama` : ""}.` : `${r.entity_name} kembali ke mode lama.`);
    notifyReceivingModeChanged();
  };
  return (
    <div data-testid="grn-mode-panel" className="space-y-3">
      <p className="text-[11px] text-[#6B6B73]">Atur per badan usaha. Mode Kedatangan = satu pintu stok masuk dari supplier & makloon: setiap kedatangan dicatat dengan surat jalan, dihitung fisik, dan direkonsiliasi sebelum stok & jurnal terbentuk.</p>
      {msg && <p data-testid="grn-mode-msg" className="rounded-lg bg-[#E7F6F3] px-3 py-2 text-[11px] font-semibold text-[#0F766E]">{msg}</p>}
      <div className="grid gap-3 xl:grid-cols-2">{(data?.entities || []).map((e) => <EntityCard key={e.entity_id} e={e} onSwitched={onSwitched} />)}</div>
    </div>
  );
}
