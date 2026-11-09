/** Riwayat Passage Gate — rombongan lewat per gate + siapa yang mengakui alarm & catatannya. */
import { useEffect, useState } from "react";
import { History } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { SectionCard, EmptyBox, Pill, fmtTime } from "./rfidShared";
import ExportMenu from "../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)

const VERDICT = { red: ["red", "MERAH"], green: ["green", "HIJAU"], info: ["gray", "INFO"] };

export default function GatePassageHistory({ gateId, whId, refreshKey }) {
  const [rows, setRows] = useState([]);
  const [next, setNext] = useState(null);
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState("");
  // FIX-8 (B1b UI-49/UI-50) — keadaan muat: "Memuat…" sebelum data datang; 403 = tanpa akses (bukan "belum ada").
  const [st, setSt] = useState({ loading: true, error: null });
  const load = async (before) => {
    if (!before) setSt((x) => ({ ...x, loading: true }));
    try {
      const r = await axios.get(`${API}/rfid/passages`, {
        params: { ...(gateId ? { device_id: gateId } : { warehouse_id: whId || undefined }), limit: 15, before } });
      setRows((prev) => (before ? [...prev, ...r.data.passages] : r.data.passages));
      setNext(r.data.next_before); setErr("");
      setSt({ loading: false, error: null });
    } catch (e) { setErr(apiErrorText(e, "Gagal memuat riwayat passage")); setSt({ loading: false, error: e }); }
  };
  useEffect(() => { load(); }, [gateId, whId, refreshKey]); // eslint-disable-line
  return (
    <SectionCard title="Riwayat Passage Gate" right={
      <ExportMenu dataset="rfid_passages" label="lintasan-gerbang" testId="rfid-passage-export"
        filters={[gateId ? ["device_id", "eq", gateId] : whId && ["warehouse_id", "eq", whId]]} sort={[{ key: "started_at", dir: "desc" }]} />}>
      {err && rows.length > 0 && <p className="mb-2 text-[12px] font-semibold text-[#C0341D]">{err}</p>}
      {rows.length === 0 ? <EmptyBox icon={History} loading={st.loading} error={st.error} onRetry={() => load()} what="riwayat lintasan"
        text="Belum ada rombongan yang lewat gate ini." testId="rfid-passage-state" /> : (
        <div data-testid="rfid-passage-history" className="space-y-1.5">
          {rows.map((p) => {
            const [color, label] = VERDICT[p.verdict] || VERDICT.info;
            return (
              <div key={p.id} data-testid={`rfid-passage-row-${p.id}`} className="rounded-lg bg-[#FAFAFB] px-3 py-2">
                <button className="flex w-full flex-wrap items-center gap-2 text-left" onClick={() => setOpen(open === p.id ? null : p.id)}
                  data-testid={`rfid-passage-toggle-${p.id}`}>
                  <Pill color={color}>{label}</Pill>
                  <span className="text-[12px] font-semibold">{p.device_name || "Perangkat tanpa nama"}</span>
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
