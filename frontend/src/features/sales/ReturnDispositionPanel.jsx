import { useCallback, useEffect, useState } from "react";
import { GitBranch, Loader2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ReturnCameraButton from "./ReturnCameraButton";

const STAGE = {
  awaiting_release: ["Tunggu lepas karantina", "#8E8E93"],
  internal_pending: ["Tahap 1 · tunggu keputusan", "#B45309"],
  kept_internal: ["Disimpan pemilik", "#1B7F4B"],
  internal_in_progress: ["Retur internal berjalan", "#0058CC"],
  supplier_pending: ["Tahap 2 · tunggu keputusan", "#B45309"],
  supplier_keep: ["Disimpan sebagai stok", "#1B7F4B"],
  supplier_supplier_return: ["Retur ke supplier", "#0058CC"],
  supplier_dispose: ["BS dibuang", "#C62828"],
  closed: ["Selesai", "#6B6B73"],
  no_internal_origin: ["Bukan dari PT internal", "#8E8E93"],
  other_owner: ["Pemilik lain", "#8E8E93"],
};
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;

export function DispositionRow({ r, checked, onToggle }) {
  const [label, color] = STAGE[r.stage] || [r.stage, "#6B6B73"];
  const actionable = r.stage === "internal_pending" || r.stage === "supplier_pending";
  return (
    <tr data-testid={`disposition-row-${r.roll_id}`}>
      <td className="px-2 py-1.5">{actionable && <input type="checkbox" data-testid={`disposition-check-${r.roll_id}`} checked={checked} onChange={onToggle} />}</td>
      <td className="px-2 py-1.5 font-medium">{r.roll_no || r.roll_id}<span className="block text-[10px] text-[#8E8E93]">grade {r.grade || "—"} · {r.status}{r.sellable ? "" : " · belum siap jual"}</span></td>
      <td className="px-2 py-1.5 text-right tabular-nums">{r.qty} {r.unit}</td>
      <td className="px-2 py-1.5" data-testid={`disposition-owner-${r.roll_id}`}>{r.owner_name}</td>
      <td className="px-2 py-1.5 text-[10.5px] text-[#6E6E73]">{r.seller_name ? `${r.seller_name} → ${r.buyer_name} · ${r.origin_interco_number}` : "—"}
        {r.supplier_name ? <span className="block">{r.supplier_name}{r.po_number ? ` · ${r.po_number}` : ""}</span> : null}</td>
      <td className="px-2 py-1.5 text-[10.5px]" data-testid={`disposition-deadline-${r.roll_id}`}>
        {r.supplier_deadline || "—"}{r.supplier_window_expired ? <b className="block text-[#C62828]">lewat</b> : null}</td>
      <td className="px-2 py-1.5"><span className="rounded-full px-2 py-0.5 text-[10.5px] font-semibold" style={{ background: `${color}18`, color }}
        data-testid={`disposition-stage-${r.roll_id}`}>{label}</span>
        {(r.internal?.interco_return_number || r.supplier?.purchase_return_numbers) && (
          <span className="block text-[10px] font-mono text-[#6E6E73]">{r.internal?.interco_return_number}{r.supplier?.purchase_return_numbers ? ` ${r.supplier.purchase_return_numbers}` : ""}</span>)}
        {r.supplier?.auto && <span className="block text-[10px] text-[#6E6E73]">otomatis: masa supplier lewat</span>}</td>
    </tr>
  );
}

export function DispositionActionBar({ returnId, imgs, stage, sel, rows, onDone, onPhoto }) {
  const [reason, setReason] = useState("");
  const [photos, setPhotos] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const expired = rows.some((r) => sel.includes(r.roll_id) && r.supplier_window_expired);
  const one = rows.find((r) => sel.includes(r.roll_id)) || {};
  const go = async (decision) => {
    setBusy(true); setMsg("");
    try {
      const path = stage === "internal_pending" ? "internal" : "supplier";
      const { data } = await axios.post(`${API}/sales-returns/${returnId}/disposition/${path}`, { roll_ids: sel, decision, reason, attachment_ids: photos });
      setMsg((data.interco_returns || []).map((x) => x.number).join(", ") || (data.purchase_returns || []).map((x) => x.number).join(", ") || "Keputusan tersimpan.");
      setReason(""); setPhotos([]); onDone();
    } catch (e) { setMsg(errText(e)); } finally { setBusy(false); }
  };
  const btn = (decision, label, testid, disabled) => (
    <button type="button" data-testid={testid} disabled={busy || disabled || !sel.length} onClick={() => go(decision)}
      className="secondary-button !py-1 text-[11.5px] disabled:opacity-40">{label}</button>
  );
  return (
    <div className="mt-2 space-y-2 rounded-lg border border-[#EDEEF1] bg-[#FAFBFC] p-2.5" data-testid="disposition-actions">
      <input data-testid="disposition-reason" className="field w-full text-xs" placeholder="Alasan keputusan (min. 5 huruf)" value={reason} onChange={(e) => setReason(e.target.value)} />
      <div className="flex flex-wrap items-center gap-2">
        {stage === "internal_pending" ? <>
          {btn("keep", `Simpan di ${one.owner_name || "pemilik"}`, "disposition-keep-internal")}
          {btn("return_internal", `Kembalikan ke ${one.seller_name || "PT pemasok"}`, "disposition-return-internal")}
        </> : <>
          {btn("keep", "Simpan sebagai stok", "disposition-keep-stock")}
          {btn("supplier_return", "Retur ke supplier", "disposition-supplier-return", expired)}
          {btn("dispose", "Buang BS", "disposition-dispose", !photos.length)}
        </>}
        {busy && <Loader2 size={13} className="spin" />}
      </div>
      {stage === "supplier_pending" && (
        <div className="flex flex-wrap gap-3 text-[11px]">
          <span className="text-[#6E6E73]">Foto bukti buang BS:</span>
          <ReturnCameraButton returnId={returnId} uploadUrl={`${API}/sales-returns/${returnId}/disposition/photos`} testId="disposition-camera"
            onUploaded={(att) => { setPhotos((p) => [...p, att.id]); onPhoto?.(); }} />
          {!imgs.length && <span className="text-[#8E8E93]">belum ada foto di lampiran</span>}
          {imgs.map((a) => <label key={a.id} className="inline-flex items-center gap-1"><input type="checkbox" data-testid={`disposition-photo-${a.id}`}
            checked={photos.includes(a.id)} onChange={() => setPhotos((p) => (p.includes(a.id) ? p.filter((x) => x !== a.id) : [...p, a.id]))} />{a.filename}</label>)}
        </div>
      )}
      {expired && <p className="text-[11px] text-[#C62828]" data-testid="disposition-expired-note">Masa retur supplier sudah lewat — hanya bisa disimpan sebagai stok.</p>}
      {stage === "internal_pending" && <p className="text-[11px] text-[#6E6E73]">Retur internal: PT pemasok wajib menerima; lokasi fisik di gudang bersama tidak berubah, hanya pemiliknya.</p>}
      {msg && <p className="text-[11px]" data-testid="disposition-msg">{msg}</p>}
    </div>
  );
}

export default function ReturnDispositionPanel({ ret, canApprove, onChanged }) {
  const [data, setData] = useState(null);
  const [sel, setSel] = useState([]);
  const load = useCallback(() => {
    axios.get(`${API}/sales-returns/${ret.id}/disposition`).then((r) => { setData(r.data); setSel([]); }).catch(() => setData(null));
  }, [ret.id]);
  useEffect(() => { load(); }, [load, ret.status]);
  const rows = data?.rows || [];
  if (!rows.some((r) => r.stage !== "no_internal_origin")) return null;
  const selStage = rows.find((r) => r.roll_id === sel[0])?.stage;
  const imgs = [...(ret.attachments || []), ...(ret.disposition_photos || [])]
    .filter((a) => !a.is_deleted && (a.content_type || "").startsWith("image/"));
  const toggle = (r) => setSel((s) => (s.includes(r.roll_id) ? s.filter((x) => x !== r.roll_id)
    : (selStage && selStage !== r.stage ? [r.roll_id] : [...s, r.roll_id])));
  return (
    <div className="section-card" data-testid="return-disposition-panel">
      <div className="section-header inline-flex items-center gap-1.5"><GitBranch size={14} /> Tujuan barang retur (antar-PT → supplier)</div>
      <p className="px-1 text-[11px] text-[#6E6E73]">Tahap 1: PT pembeli memilih simpan atau kembalikan ke PT pemasok. Tahap 2: PT pemasok memilih simpan, retur ke supplier (maks. {data.supplier_window_days} hari dari terima), atau buang BS dengan foto.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]" data-testid="disposition-table">
          <thead className="bg-[#FAFBFC] text-[10px] uppercase text-[#8E8E93]"><tr>
            <th /><th className="px-2 py-1.5 text-left">Roll</th><th className="px-2 py-1.5 text-right">Jumlah</th><th className="px-2 py-1.5 text-left">Pemilik</th>
            <th className="px-2 py-1.5 text-left">Asal</th><th className="px-2 py-1.5 text-left">Batas supplier</th><th className="px-2 py-1.5 text-left">Tahap</th></tr></thead>
          <tbody className="divide-y divide-[#F2F2F5]">
            {rows.map((r) => <DispositionRow key={r.roll_id} r={r} checked={sel.includes(r.roll_id)} onToggle={() => toggle(r)} />)}
          </tbody>
        </table>
      </div>
      {canApprove && sel.length > 0 && <DispositionActionBar returnId={ret.id} imgs={imgs} stage={selStage} sel={sel} rows={rows} onDone={load} onPhoto={onChanged} />}
    </div>
  );
}
