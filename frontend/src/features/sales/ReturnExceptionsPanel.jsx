import { Panel } from "../../components/DetailParts";
import { useState } from "react";
import { ShieldAlert, Check, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ReturnCameraButton from "./ReturnCameraButton";
import { formatDateTime } from "../../utils/formatters";

const KINDS = [
  { value: "window", label: "Di luar batas waktu retur" },
  { value: "discount_no_goods", label: "Diskon tanpa barang kembali (QC exception)" },
];
const STATUS = { pending: ["Menunggu keputusan", "#B45309"], approved: ["Disetujui", "#1B7F4B"], rejected: ["Ditolak", "#C62828"] };
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;

function RequestForm({ ret, onDone, onPhoto }) {
  const photos = (ret.attachments || []).filter((a) => !a.is_deleted && (a.content_type || "").startsWith("image/"));
  const [f, setF] = useState({ kind: "window", reason: "", attachment_ids: [] });
  const [err, setErr] = useState("");
  const toggle = (id) => setF((x) => ({ ...x, attachment_ids: x.attachment_ids.includes(id) ? x.attachment_ids.filter((i) => i !== id) : [...x.attachment_ids, id] }));
  const captured = (att) => { setF((x) => ({ ...x, attachment_ids: [...x.attachment_ids, att.id] })); onPhoto?.(); };
  const submit = async () => {
    setErr("");
    try { await axios.post(`${API}/sales-returns/${ret.id}/exceptions`, f); setF({ kind: f.kind, reason: "", attachment_ids: [] }); onDone(); }
    catch (e) { setErr(errText(e)); }
  };
  return (
    <div className="space-y-2" data-testid="return-exception-form">
      <div className="w-80"><KNSelect data-testid="return-exception-kind" value={f.kind} options={KINDS} searchable={false} onValueChange={(v) => setF({ ...f, kind: v })} /></div>
      <textarea data-testid="return-exception-reason" className="field w-full text-sm" rows={2} value={f.reason}
                placeholder="Alasan pengecualian (min. 10 karakter)" onChange={(e) => setF({ ...f, reason: e.target.value })} />
      <div className="text-xs">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <p className="font-semibold">Foto bukti:</p>
          <ReturnCameraButton returnId={ret.id} onUploaded={captured} testId="return-exception-camera" />
        </div>
        {!photos.length && <p className="text-[#8E8E93]" data-testid="return-exception-no-photo">Belum ada foto. Ambil foto langsung dari kamera, atau unggah di bagian Lampiran retur.</p>}
        <div className="flex flex-wrap gap-3">
          {photos.map((a) => (
            <label key={a.id} className="inline-flex items-center gap-1">
              <input type="checkbox" data-testid={`return-exception-photo-${a.id}`} checked={f.attachment_ids.includes(a.id)} onChange={() => toggle(a.id)} /> {a.filename}
            </label>
          ))}
        </div>
      </div>
      <button type="button" data-testid="return-exception-submit" onClick={submit} className="primary-button text-xs">Ajukan pengecualian</button>
      {err && <p className="text-xs text-[#C62828]" data-testid="return-exception-error">{err}</p>}
    </div>
  );
}

function ExceptionRow({ ret, x, canApprove, onDone }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const [label, color] = STATUS[x.status] || [x.status, "#6B6B73"];
  const decide = async (approve) => {
    setErr("");
    try { await axios.post(`${API}/sales-returns/${ret.id}/exceptions/${x.id}/decide`, { approve, note }); onDone(); }
    catch (e) { setErr(errText(e)); }
  };
  return (
    <div className="py-2 text-xs space-y-1" data-testid={`return-exception-${x.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <b>{x.label}</b>
        <span className="rounded-full px-2 py-0.5 font-semibold" style={{ background: `${color}18`, color }} data-testid={`return-exception-status-${x.id}`}>{label}</span>
        <span className="text-[#6B6B73]">oleh {x.requested_by} · {formatDateTime(x.requested_at)} · {x.attachment_ids.length} foto</span>
      </div>
      <p>{x.reason}</p>
      {x.decided_by && <p className="text-[#6B6B73]">Diputuskan {x.decided_by}{x.decision_note ? `: ${x.decision_note}` : ""}</p>}
      {x.status === "pending" && canApprove && (
        <div className="flex flex-wrap items-center gap-2">
          <input data-testid={`return-exception-note-${x.id}`} className="field text-xs w-64" placeholder="Catatan keputusan" value={note} onChange={(e) => setNote(e.target.value)} />
          <button type="button" data-testid={`return-exception-approve-${x.id}`} onClick={() => decide(true)} className="inline-flex items-center gap-1 rounded-lg bg-[#1B7F4B] text-white px-3 py-1 font-semibold"><Check size={12} /> Setujui</button>
          <button type="button" data-testid={`return-exception-reject-${x.id}`} onClick={() => decide(false)} className="inline-flex items-center gap-1 rounded-lg border border-[#C62828] text-[#C62828] px-3 py-1 font-semibold"><X size={12} /> Tolak</button>
        </div>
      )}
      {err && <p className="text-[#C62828]">{err}</p>}
    </div>
  );
}

export default function ReturnExceptionsPanel({ ret, canApprove, onChanged }) {
  const [open, setOpen] = useState(false);
  const list = ret.exceptions || [];
  const flags = ret.condition_flags || {};
  const terminal = ["rejected", "cancelled", "refund_settled", "credit_settled", "nego_settled", "settled"].includes(ret.status);
  return (
    <Panel icon={ShieldAlert} title="Pengecualian retur" testId="return-exceptions-panel"
      right={!terminal && <button type="button" data-testid="return-exception-toggle" onClick={() => setOpen(!open)} className="link-button text-xs font-semibold">{open ? "Tutup" : "Ajukan pengecualian"}</button>}>
      {(flags.hangtag_missing || flags.cut_by_customer) && (
        <p className="mb-1.5 text-xs text-[#8A4B08]" data-testid="return-condition-flags-view">
          Kondisi: {[flags.hangtag_missing && "hangtag hilang", flags.cut_by_customer && "kain dipotong", flags.replacement_proof && "ada bukti pengganti"].filter(Boolean).join(", ")} · Finance memutus saat penyelesaian
        </p>
      )}
      {open && <RequestForm ret={ret} onPhoto={() => onChanged?.()} onDone={() => { setOpen(false); onChanged?.(); }} />}
      <div className="divide-y divide-[#F0F0F3]">
        {list.map((x) => <ExceptionRow key={x.id} ret={ret} x={x} canApprove={canApprove} onDone={() => onChanged?.()} />)}
      </div>
      {!list.length && !open && <p className="text-xs text-[#8E8E93]">Belum ada pengecualian. Wajib bila retur lewat batas atau diskon tanpa barang kembali.</p>}
    </Panel>
  );
}
