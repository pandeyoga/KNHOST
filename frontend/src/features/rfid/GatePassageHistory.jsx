/** Riwayat Passage Gate — rombongan lewat per gate + siapa yang mengakui alarm & catatannya. */
import { useEffect, useState } from "react";
import { History } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { SectionCard, EmptyBox, Pill, fmtTime } from "./rfidShared";

const VERDICT = { red: ["red", "MERAH"], green: ["green", "HIJAU"], info: ["gray", "INFO"] };

export default function GatePassageHistory({ gateId, whId, refreshKey }) {
  const [rows, setRows] = useState([]);
  const [next, setNext] = useState(null);
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState("");
  const load = async (before) => {
    try {
      const r = await axios.get(`${API}/rfid/passages`, {
        params: { ...(gateId ? { device_id: gateId } : { warehouse_id: whId || undefined }), limit: 15, before } });
      setRows((prev) => (before ? [...prev, ...r.data.passages] : r.data.passages));
      setNext(r.data.next_before); setErr("");
    } catch (e) { setErr(apiErrorText(e, "Gagal memuat riwayat passage")); }
  };
  useEffect(() => { load(); }, [gateId, whId, refreshKey]); // eslint-disable-line
  return (
    <SectionCard title="Riwayat Passage Gate">
      {err && <p className="mb-2 text-[12px] font-semibold text-[#C0341D]">{err}</p>}
      {rows.length === 0 ? <EmptyBox icon={History} text="Belum ada rombongan yang lewat gate ini." /> : (
        <div data-testid="rfid-passage-history" className="space-y-1.5">
          {rows.map((p) => {
            const [color, label] = VERDICT[p.verdict] || VERDICT.info;
            return (
              <div key={p.id} data-testid={`rfid-passage-row-${p.id}`} className="rounded-lg bg-[#FAFAFB] px-3 py-2">
                <button className="flex w-full flex-wrap items-center gap-2 text-left" onClick={() => setOpen(open === p.id ? null : p.id)}
                  data-testid={`rfid-passage-toggle-${p.id}`}>
                  <Pill color={color}>{label}</Pill>
                  <span className="text-[12px] font-semibold">{p.device_name || p.device_id}</span>
                  <span className="text-[11px] text-[#6B6B73]">{fmtTime(p.started_at)} · {p.reads?.length || 0} roll · merah {p.red_count} · hijau {p.green_count}</span>
                  <span className="ml-auto text-[11px]" data-testid={`rfid-passage-ack-info-${p.id}`}>
                    {p.acknowledged_at
                      ? <span className="text-[#1B7F4B]">Diakui {p.acknowledged_by} · {fmtTime(p.acknowledged_at)}</span>
                      : p.verdict === "red" ? <b className="text-[#C0341D]">Belum diakui</b> : <span className="text-[#8E8E93]">—</span>}
                  </span>
                </button>
                {p.acknowledge_note && <p className="mt-0.5 text-[11px] text-[#3A3A3C]" data-testid={`rfid-passage-note-${p.id}`}>Catatan: {p.acknowledge_note}</p>}
                {open === p.id && (
                  <div className="mt-1.5 space-y-0.5 border-t border-[#EFEFF2] pt-1.5 text-[11px]">
                    {(p.reads || []).map((r) => (
                      <p key={r.id}>{r.result === "red" ? "✕" : r.result === "green" ? "✓" : "•"} <b>{r.roll_no || r.epc}</b> — {r.action || r.reason}</p>))}
                  </div>)}
              </div>);
          })}
          {next && <button data-testid="rfid-passage-more" onClick={() => load(next)} className="secondary-button text-[11px]">Muat lebih lama</button>}
        </div>)}
    </SectionCard>
  );
}
