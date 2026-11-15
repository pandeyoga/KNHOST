/**
 * PREP-D1 — dokumen gate: auto-cocok (AUD-MW-15) / binding manual + progres sesi dokumen bertahap (K-RFID-10):
 * per dokumen roll sudah lewat vs belum; roll yang belum lewat dinilai saat dokumen ditutup (kuning, bukan alarm).
 */
import { useEffect, useState } from "react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import axios, { API } from "../../services/apiClient";
import { askConfirm } from "../../services/confirmService";
import { Pill } from "./rfidShared";
import { SOURCE_KINDS, errorText } from "./u300Labels";

function SessionRow({ s, busy, onClose }) {
  const [open, setOpen] = useState(false);
  const pct = s.total ? Math.round((s.passed / s.total) * 100) : 0;
  return (
    <li className="rounded-lg border border-[#EFF0F2] p-2" data-testid={`u300-session-${s.source_ref.source_id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[12px] font-semibold">{s.source_ref.display_ref}</span>
        <span className="flex items-center gap-1">
          <Pill color={s.status === "complete" ? "green" : s.status === "closed" ? "gray" : "info"}>
            {s.status === "complete" ? "semua roll lewat" : s.status === "closed" ? "sesi ditutup" : "berjalan"}</Pill>
          <span className="text-[11px] text-[#3C3C43]">{s.passed}/{s.total} roll lewat · sisa {s.remaining}</span>
        </span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-[#F2F2F7]"><div className="h-1.5 rounded bg-[#34C759]" style={{ width: `${pct}%` }} /></div>
      {s.close && (
        <p className="mt-1 text-[11px]" data-testid="u300-session-close">
          {s.close.verdict === "GREEN" ? "Ditutup: semua roll sudah lewat." : `Ditutup dengan ${s.close.missing_count} roll belum lewat — masuk pemeriksaan (kuning).`}
        </p>
      )}
      <div className="mt-1 flex flex-wrap gap-2">
        <button type="button" className="secondary-button !py-0.5 text-[11px]" onClick={() => setOpen(!open)}>
          {open ? "Sembunyikan roll" : "Lihat roll"}</button>
        {!s.close && <button type="button" className="secondary-button !py-0.5 text-[11px]" disabled={busy}
          data-testid={`u300-session-close-${s.source_ref.source_id}`} onClick={() => onClose(s)}>Tutup sesi dokumen</button>}
      </div>
      {open && (
        <ul className="mt-1 max-h-40 overflow-y-auto text-[11px]">
          {s.rolls.map((r) => (
            <li key={r.roll_id} className="flex justify-between border-t border-[#F2F2F7] py-0.5">
              <span>{r.roll_no || "Roll tanpa nomor"}</span>
              <span className={r.passed ? "text-[#1B7E3B]" : "text-[#8A5A00]"}>
                {r.passed ? `lewat${r.review ? " (diperiksa)" : ""}` : "belum lewat"}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export default function U300DocSession({ device, gate, data, params, busy, act }) {
  const base = `${API}/rfid/v2/ops/devices/${encodeURIComponent(device.id)}`;
  const fixedDir = gate?.direction === "in" || gate?.direction === "out" ? gate.direction : "out";
  const [kind, setKind] = useState(fixedDir === "in" ? "putaway" : "shipment");
  const [sources, setSources] = useState([]);
  const [picked, setPicked] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    setPicked([]); setSources([]);
    axios.get(`${base}/sources`, { params: { source_type: kind, direction: fixedDir } })
      .then((r) => { if (alive) { setSources(r.data.sources || []); setError(""); } })
      .catch((e) => { if (alive) setError(errorText(e)); });
    return () => { alive = false; };
  }, [base, kind, fixedDir]);
  const toggle = (id, on) => setPicked((cur) => (on ? (kind === "shipment" ? [...cur, id].slice(0, 20) : [id]) : cur.filter((x) => x !== id)));
  const binding = (data?.bindings || [])[0];
  const bind = () => act(() => axios.post(`${base}/manifest`, {
    logical_gate_id: gate.logical_gate_id, direction: fixedDir,
    sources: picked.map((id) => ({ source_type: kind, source_id: id })),
  }));
  const release = () => act(() => axios.delete(`${base}/manifest`, { params: { logical_gate_id: gate.logical_gate_id } }));
  const closeSession = async (s) => {
    if (!(await askConfirm({
      title: `Tutup sesi ${s.source_ref.display_ref}?`, confirmLabel: "Tutup sesi",
      message: s.remaining
        ? `${s.remaining} roll belum lewat gate. Roll itu dicatat "belum lewat" untuk diperiksa (kuning) — gate tidak terkunci.`
        : "Semua roll sudah lewat. Penutupan dicatat sebagai bukti dokumen selesai.",
    }))) return;
    await act(() => axios.post(
    `${API}/rfid/v2/ops/doc-sessions/${s.source_ref.source_type}/${encodeURIComponent(s.source_ref.source_id)}/close`,
    { direction: s.direction, note: "Ditutup dari panel gate" }));
  };
  const kinds = SOURCE_KINDS.filter((k) => fixedDir === "out" || ["putaway", "wh_transfer", "repair_order"].includes(k.value));
  return (
    <div className="space-y-2" data-testid="u300-doc-session">
      {error && <ErrorNotice message={error} onDismiss={() => setError("")} />}
      <p className="text-[12px]">
        {binding
          ? <>Dokumen dipilih manual: <b>{binding.source_ref.display_ref}</b> ({binding.roll_ids.length} roll).</>
          : params?.auto_match
            ? "Tanpa pilihan manual — gate mencocokkan otomatis ke dokumen aktif gudang & arah ini."
            : "Auto-cocok dimatikan di parameter gate — pilih dokumen sebelum barang lewat."}
        {binding && <button type="button" className="secondary-button !py-0.5 ml-2 text-[11px]" disabled={busy} onClick={release}
          data-testid="u300-release-binding">Lepas pilihan</button>}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <KNSelect data-testid="u300-source-kind" value={kind} onValueChange={setKind} options={kinds}
          className="field !py-1 !px-2 text-[12px] w-auto" />
        <button type="button" className="primary-button !py-1 text-[12px]" disabled={busy || !picked.length} onClick={bind}
          data-testid="u300-bind">Gunakan {picked.length || ""} dokumen</button>
      </div>
      <fieldset className="max-h-40 overflow-y-auto rounded-lg border border-[#EFF0F2] p-2">
        <legend className="px-1 text-[11px] text-[#6B6B73]">Dokumen aktif yang akan lewat (SJ boleh digabung s.d. 20)</legend>
        {sources.length === 0 && <p className="text-[11px] text-[#6B6B73]">Belum ada dokumen aktif untuk gudang dan arah ini.</p>}
        {sources.map((s) => (
          <label key={s.id} className="flex items-center gap-2 text-[12px]">
            <input type="checkbox" checked={picked.includes(s.id)} disabled={busy} onChange={(e) => toggle(s.id, e.target.checked)} />
            {s.label}
          </label>
        ))}
      </fieldset>
      <h3 className="text-[12px] font-semibold">Sesi dokumen bertahap</h3>
      {(data?.sessions || []).length === 0
        ? <p className="text-[11px] text-[#6B6B73]">Belum ada dokumen yang sedang dimuat lewat gate ini.</p>
        : <ul className="space-y-2">{data.sessions.map((s) => <SessionRow key={`${s.source_ref.source_type}:${s.source_ref.source_id}`} s={s} busy={busy} onClose={closeSession} />)}</ul>}
    </div>
  );
}
