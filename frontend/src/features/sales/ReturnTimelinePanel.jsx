/**
 * ReturnTimelinePanel — L08 LN-081 · satu timeline kasus retur dengan jalur terpisah:
 * izin · perjalanan masuk (scan berdokumen) · QC per roll · disposisi stok · uang ·
 * pengiriman pengganti. Lokasi roll hanya berubah lewat scan Terima / Kirim / Tiba.
 */
import { useCallback, useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { MapPin, Route, ScanLine } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import { notifySuccess } from "../../utils/feedback";
import { apiErrorText } from "../../utils/apiError";
import { Panel } from "../../components/DetailParts";
import { formatQty } from "../../utils/formatters";

const LANE_COLOR = {
  approval: "#6B219A", inbound: "#0058CC", qc: "#A05000",
  disposition: "#15803D", settlement: "#B42318", replacement: "#5B6472",
};
const SCAN_STAGES = [
  { value: "received", label: "Terima di gudang" },
  { value: "dispatched", label: "Kirim ke gudang lain (dalam perjalanan)" },
  { value: "arrived", label: "Tiba di gudang tujuan" },
];
const OPEN = ["pending_approval", "approved", "inspecting", "inspected"];

function stamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso).slice(0, 16)
    : d.toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function ScanForm({ ret, warehouses, onDone }) {
  const [stage, setStage] = useState("received");
  const [wh, setWh] = useState("");
  const [toWh, setToWh] = useState("");
  const [codes, setCodes] = useState("");
  const [carrier, setCarrier] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const opts = warehouses.filter((w) => w.usable_by_active !== false).map((w) => ({ value: w.id, label: w.name }));
  // Cek UI UAT v3 (S14) — roll sedang dalam perjalanan: gudang tujuan tinggal scan "Tiba"; tahap & gudang terisi otomatis.
  const transitTo = Object.values(ret?.roll_locations || {}).find((l) => l?.stage === "in_transit")?.to_warehouse_id || "";
  useEffect(() => { if (transitTo) { setStage("arrived"); setWh(transitTo); } }, [transitTo]);
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const list = codes.split(/[\s,;]+/).map((c) => c.trim()).filter(Boolean);
      const r = await axios.post(`${API}/sales-returns/${ret.id}/journey/scan`, {
        stage, codes: list, warehouse_id: wh, to_warehouse_id: stage === "dispatched" ? toWh : "", carrier,
      });
      notifySuccess("Scan tercatat", `${r.data.event.doc_no} · ${r.data.event.roll_ids.length} roll`);
      setCodes(""); onDone();
    } catch (e2) { setErr(apiErrorText(e2, "Scan gagal.")); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={submit} className="grid gap-2 rounded-lg border border-[#D9E4F5] bg-[#F7FAFF] p-2.5" data-testid="journey-scan-form">
      {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="journey-scan-error" />}
      <div className="grid gap-2 sm:grid-cols-3">
        <label><span className="field-label">Tahap scan</span>
          <KNSelect data-testid="journey-scan-stage" className="field" value={stage} onValueChange={setStage} options={SCAN_STAGES} /></label>
        <label><span className="field-label">{stage === "dispatched" ? "Dikirim dari gudang" : "Gudang tempat scan"}</span>
          <KNSelect data-testid="journey-scan-warehouse" className="field" value={wh} onValueChange={setWh} options={opts} placeholder="Pilih gudang" /></label>
        {stage === "dispatched" && (
          <label><span className="field-label">Gudang tujuan</span>
            <KNSelect data-testid="journey-scan-to-warehouse" className="field" value={toWh} onValueChange={setToWh} options={opts.filter((o) => o.value !== wh)} placeholder="Pilih tujuan" /></label>
        )}
      </div>
      <label><span className="field-label">Scan nomor roll / tag (pisahkan dengan Enter atau koma)</span>
        <textarea data-testid="journey-scan-codes" className="field" rows={2} value={codes}
          onChange={(e) => setCodes(e.target.value)} placeholder="RL-10124&#10;RL-10125" /></label>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <label><span className="field-label">Ekspedisi / sopir (opsional)</span>
          <input data-testid="journey-scan-carrier" className="field" value={carrier} onChange={(e) => setCarrier(e.target.value)} /></label>
        <button data-testid="journey-scan-submit" className="primary-button" disabled={busy || !wh || !codes.trim() || (stage === "dispatched" && !toWh)}>
          <ScanLine size={13} /> {busy ? "Mencatat…" : "Catat scan"}
        </button>
      </div>
    </form>
  );
}

function LaneTimeline({ lanes, events }) {
  if (!events.length) return <p className="text-[11px] text-[#8E8E93]">Belum ada kejadian.</p>;
  return (
    <ol className="relative ml-2 border-l border-[#E1E4EA]" data-testid="return-timeline-events">
      {events.map((e, i) => (
        <li key={i} className="mb-2 ml-3" data-testid={`timeline-event-${e.lane}-${i}`}>
          <span className="absolute -left-[5px] mt-1 h-2.5 w-2.5 rounded-full" style={{ background: LANE_COLOR[e.lane] }} />
          <div className="flex flex-wrap items-baseline gap-x-2 text-[11.5px]">
            <span className="rounded px-1.5 text-[9.5px] font-bold uppercase tracking-wide text-white" style={{ background: LANE_COLOR[e.lane] }}>
              {lanes[e.lane]}
            </span>
            <span className="font-semibold text-[#1C1C1E]">{e.title}</span>
            {e.doc_no && <span className="font-mono text-[10.5px] text-[#0058CC]">{e.doc_no}</span>}
            <span className="text-[10.5px] text-[#8E8E93]">{stamp(e.at)}{e.by ? ` · ${e.by}` : ""}</span>
          </div>
          {e.detail && <p className="text-[10.5px] text-[#5B6472]">{e.detail}</p>}
        </li>
      ))}
    </ol>
  );
}

function RollTable({ rolls }) {
  if (!rolls.length) return <p className="text-[11px] text-[#8E8E93]">Retur ini tidak memakai roll terkirim (baris lama).</p>;
  return (
    <div className="overflow-x-auto">
      <table className="data-table" data-testid="return-timeline-rolls" style={{ minWidth: 760 }}>
        {/* UAT 24 Okt (audit UI tahap 2) — G2-15 · P-12: kolom grade di sini = grade QC BARIS item (terburuk dari
            pemeriksaan baris, sama untuk semua roll baris itu), bukan grade per roll di SPK/Stok → diberi label sumber. */}
        <thead><tr><th>Roll</th><th>Klaim</th><th>Lokasi fisik</th><th>QC aktual</th>
          <th title="Grade terburuk hasil QC untuk baris item ini (sama untuk semua roll di baris). Grade per roll ada di panel SPK & Stok.">Grade QC baris</th>
          <th>Disposisi stok</th></tr></thead>
        <tbody>
          {rolls.map((r) => (
            <tr key={r.roll_id} data-testid={`timeline-roll-${r.roll_id}`}>
              <td className="font-mono">{r.roll_no}<div className="text-[10px] text-[#8E8E93]">{r.product_name}</div></td>
              <td className="tabular-nums">{formatQty(r.qty_claimed)} {r.unit}</td>
              <td data-testid={`timeline-roll-location-${r.roll_id}`}>
                <MapPin size={11} className="inline mr-1 text-[#0058CC]" />{r.location}
                {r.location_doc && <div className="font-mono text-[10px] text-[#8E8E93]">{r.location_doc}</div>}
              </td>
              <td className="tabular-nums">{r.qc_actual == null ? "—" : `${formatQty(r.qc_actual)} ${r.unit}`}</td>
              <td>{r.qc_grade || "—"}</td>
              <td>{r.stock_roll_no ? `${r.stock_roll_no} · ${r.stock_status} · ${r.stock_warehouse}` : "belum masuk stok"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UnitSummary({ summary }) {
  return (
    <div className="flex flex-wrap gap-2" data-testid="return-timeline-summary">
      {summary.per_unit.map((g) => (
        <div key={g.unit} className="rounded-lg border border-[#EFF0F2] bg-white px-2.5 py-1.5 text-[11px]" data-testid={`timeline-unit-${g.unit}`}>
          <b className="uppercase">{g.unit}</b> · klaim {formatQty(g.claimed)} · lolos QC {formatQty(g.accepted)} · diselesaikan {formatQty(g.settled)} · {g.rolls} roll
        </div>
      ))}
      <span className="self-center text-[10px] text-[#8E8E93]">{summary.value_basis}</span>
    </div>
  );
}

export default function ReturnTimelinePanel({ ret, canEdit = false, onChanged }) {
  const [data, setData] = useState(null);
  const [warehouses, setWarehouses] = useState([]);
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    try { setData((await axios.get(`${API}/sales-returns/${ret.id}/timeline`)).data); }
    catch (e) { setErr(apiErrorText(e, "Gagal memuat timeline retur.")); }
  }, [ret.id]);
  useEffect(() => { load(); }, [load, ret.updated_at]);
  useEffect(() => {
    axios.get(`${API}/warehouses`).then((r) => setWarehouses(Array.isArray(r.data) ? r.data : (r.data?.items || []))).catch(() => {});
  }, []);
  const canScan = canEdit && OPEN.includes(ret.status) && (data?.rolls || []).length > 0;
  return (
    <Panel icon={Route} title="Perjalanan & scan per roll" testId="return-timeline-panel">
      <div className="grid gap-3">
        {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="return-timeline-error" />}
        {!data && !err && <p className="text-[11.5px] text-[#6B6B73]" data-testid="return-timeline-loading">Memuat perjalanan retur…</p>}
        {data && <UnitSummary summary={data.summary} />}
        {canScan && <ScanForm ret={ret} warehouses={warehouses} onDone={() => { load(); onChanged?.(); }} />}
        {data && <RollTable rolls={data.rolls} />}
        {data && <LaneTimeline lanes={data.lanes} events={data.events} />}
      </div>
    </Panel>
  );
}
