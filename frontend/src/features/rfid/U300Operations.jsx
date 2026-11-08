/**
 * Integrasi reader U300 (gate V2, patch Kubus + PREP-D1) — dibuka dari kartu perangkat di layar Perangkat RFID
 * (pop-up rincian). Isi: profil & protokol, kesehatan reader (AUD-MW-17), kunci gate tunggal (K-RFID-09: merah
 * terkunci hanya pelanggaran, kuning tanpa kunci), dokumen gate & sesi bertahap (K-RFID-10), riwayat lintasan dengan
 * daftar alasan, parameter gate (titik awal kalibrasi), dan simulator lintasan (admin). Antrean periksa = paket D2.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, Lock, RefreshCw, Upload } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import axios, { API } from "../../services/apiClient";
import { askConfirm } from "../../services/confirmService";
import { Pill, SectionCard, fmtTime } from "./rfidShared";
import U300DocSession from "./U300DocSession";
import U300PassageList from "./U300PassageList";
import { HEALTH, PARAM_LABEL, PROTOCOL, SCENARIOS, VERDICT, errorText, reasonText } from "./u300Labels";

function LatchPanel({ latch, busy, onAck }) {
  const [note, setNote] = useState("");
  if (!latch) {
    return <p className="text-[12px] text-[#1B7E3B]" data-testid="u300-latch-none">Gate tidak terkunci.</p>;
  }
  return (
    <div className="rounded-lg border border-[#F3C5BD] bg-[#FBE9E7] p-2 space-y-1" data-testid="u300-latch">
      <p className="text-[12px] font-semibold text-[#C0341D]"><Lock size={12} className="inline" /> Gate TERKUNCI sejak {fmtTime(latch.since)} · {(latch.passages || []).length} lintasan merah</p>
      <ul className="text-[11px] text-[#3C3C43] list-disc pl-4">
        {(latch.reason_codes || []).slice(0, 6).map((c) => <li key={c}>{reasonText(c)}</li>)}
      </ul>
      <div className="flex flex-wrap gap-2">
        <input aria-label="Catatan pemeriksaan kunci gate" placeholder="Hasil pemeriksaan fisik & dokumen" value={note}
          onChange={(e) => setNote(e.target.value)} className="field !py-1 text-[12px] w-72" />
        <button type="button" className="primary-button !py-1 text-[12px]" data-testid="u300-latch-ack"
          disabled={busy || note.trim().length < 5} onClick={() => onAck(latch, note).then((ok) => ok && setNote(""))}>
          Catat pemeriksaan &amp; buka kunci</button>
      </div>
      <p className="text-[10px] text-[#6B6B73]">Membuka kunci tidak mengubah hasil lintasan menjadi hijau dan tidak mengubah stok.</p>
    </div>
  );
}

function Health({ rules }) {
  const active = (rules || []).filter((r) => r.active);
  if (!rules?.length) return null;
  return (
    <div className="flex flex-wrap gap-1" data-testid="u300-health">
      {active.length === 0 ? <Pill color="green">Reader sehat</Pill>
        : active.map((r) => <Pill key={r.rule} color="orange" testId={`u300-health-${r.rule}`}>{HEALTH[r.rule] || r.rule}</Pill>)}
      {active.map((r) => <span key={`m-${r.rule}`} className="text-[11px] text-[#8A5A00]">{r.message}</span>)}
    </div>
  );
}

function Params({ params }) {
  if (!params) return null;
  return (
    <div data-testid="u300-params">
      <p className="text-[11px] text-[#6B6B73]">
        {params.calibration_status === "calibrated" ? "Parameter sudah terkalibrasi." : "Parameter = titik awal kalibrasi (belum diuji di lokasi)."}
        {" "}Ubah dengan menerbitkan versi profil baru.</p>
      <dl className="grid grid-cols-2 md:grid-cols-4 gap-x-3 gap-y-0.5 text-[11px]">
        {Object.entries(PARAM_LABEL).map(([k, label]) => (
          <div key={k} className="flex justify-between gap-2 border-b border-[#F2F2F7]">
            <dt className="text-[#6B6B73]">{label}</dt>
            <dd className="font-semibold">{typeof params[k] === "boolean" ? (params[k] ? "ya" : "tidak") : String(params[k] ?? "—")}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function U300Operations({ device, isAdmin }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [cursor, setCursor] = useState(null);
  const [previous, setPrevious] = useState([]);
  const [scenario, setScenario] = useState("full_load");
  const seq = useRef(0);
  const base = `${API}/rfid/v2/ops/devices/${encodeURIComponent(device.id)}`;
  const load = useCallback(async () => {
    const n = ++seq.current;
    try {
      const r = await axios.get(base, { params: { cursor: cursor || undefined, limit: 50 } });
      if (n === seq.current) { setData(r.data); setError(""); }
    } catch (e) { if (n === seq.current) setError(errorText(e)); }
  }, [base, cursor]);
  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => { clearInterval(timer); seq.current += 1; };
  }, [load]);
  const act = async (fn, done) => {
    setBusy(true); setError("");
    try { await fn(); if (done) setMsg(done); await load(); return true; }
    catch (e) { setError(errorText(e)); return false; }
    finally { setBusy(false); }
  };
  const gate = data?.config?.logical_gates?.[0];
  const ackLatch = (latch, note) => act(() => axios.post(`${base}/gate-latch/acknowledge`, {
    device_id: device.id, logical_gate_id: gate?.logical_gate_id, latch_id: latch.latch_id, note,
  }), "Kunci gate dibuka — pemeriksaan tercatat.");
  const ackPassage = (p, note) => act(() => axios.post(`${API}/rfid/v2/passages/${encodeURIComponent(p.local_passage_id)}/acknowledge`, {
    device_id: device.id, note, decision_id: p.decision?.decision_id,
  }), "Pemeriksaan lintasan tercatat.");
  const evidence = (p) => act(async () => {
    const r = await axios.get(`${base}/passages/${encodeURIComponent(p.local_passage_id)}/evidence`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const link = document.createElement("a");
    link.href = url; link.download = `bukti-lintasan-${p.local_passage_id.replace(/[^a-zA-Z0-9_-]/g, "_")}.json`;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  const upload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    await act(async () => {
      if (file.size > 1000000) throw new Error("Profil maksimal 1 MB.");
      let body;
      try { body = JSON.parse(await file.text()); } catch { throw new Error("Berkas profil bukan JSON yang valid."); }
      await axios.put(`${base}/config`, body);
    }, "Profil commissioning diterbitkan.");
  };
  const simulate = async () => {
    const label = SCENARIOS.find((s) => s.value === scenario)?.label || scenario;
    if (!(await askConfirm({
      title: "Jalankan simulasi lintasan?", confirmLabel: "Jalankan",
      message: `${label}. Lintasan & klaim ditandai SIMULASI, tetapi memakai dokumen aktif gudang ini (roll yang disimulasikan lewat tercatat sudah lewat).`,
    }))) return;
    let res;
    const ok = await act(async () => { res = (await axios.post(`${base}/simulate`, { scenario })).data; });
    if (ok && res) {
      const verdicts = res.passages.map((p) => VERDICT[p.decision.verdict]?.short || p.decision.verdict).join(", ");
      setMsg(`Simulasi selesai: ${verdicts}${res.as_expected ? " (sesuai harapan)" : " — TIDAK sesuai harapan, periksa alasan"}.`);
    }
  };
  const page = {
    canPrev: previous.length > 0, canNext: !!data?.next_cursor,
    prev: () => { setCursor(previous[previous.length - 1]); setPrevious(previous.slice(0, -1)); },
    next: () => { setPrevious([...previous, cursor]); setCursor(data.next_cursor); },
    reset: () => { setCursor(null); setPrevious([]); },
  };
  return (
    <section className="space-y-3" aria-label={`Integrasi reader U300 ${device.name}`} data-testid="u300-ops">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-[15px] font-semibold">Integrasi reader U300 — {device.name}</h2>
          <p className="text-[11px] text-[#6B6B73]">
            Profil {data?.config_version || "belum diterbitkan"} · kontrak {data?.contract_version || "—"} · sinyal terakhir {fmtTime(data?.last_heartbeat)}</p>
        </div>
        <span className="flex items-center gap-2">
          <Pill color={data?.protocol === "v2" ? "purple" : "gray"} testId="u300-protocol">{PROTOCOL[data?.protocol] || "—"}</Pill>
          <button type="button" className="secondary-button !py-1 text-[12px]" disabled={busy} onClick={load}>
            <RefreshCw size={12} /> Perbarui</button>
        </span>
      </div>
      {error && <ErrorNotice message={error} onRetry={load} />}
      {msg && <div className="rounded-lg bg-[#E7F7EC] px-3 py-2 text-[12px] font-semibold text-[#1B7E3B]" data-testid="u300-msg">{msg}</div>}
      <SectionCard title="Kesehatan reader" right={<Activity size={14} className="text-[#6B6B73]" />}>
        <Health rules={data?.health} />
        <p className="mt-1 text-[11px] text-[#6B6B73]">Antrean reader: {data?.telemetry?.pending_event_count ?? "belum ada laporan"} · radio {data?.telemetry?.radio_state || "—"} · laporan {fmtTime(data?.telemetry_at)}</p>
        {isAdmin && (
          <label className="mt-2 inline-flex cursor-pointer items-center gap-1 text-[12px] text-[#0058CC]">
            <Upload size={12} /> Unggah profil commissioning (JSON)
            <input type="file" accept=".json,application/json" disabled={busy} onChange={upload} className="hidden" data-testid="u300-upload" />
          </label>
        )}
      </SectionCard>
      {gate ? (
        <>
          <SectionCard title="Kunci gate"><LatchPanel latch={data?.gate_latch} busy={busy} onAck={ackLatch} /></SectionCard>
          <SectionCard title="Dokumen gate">
            <U300DocSession device={device} gate={gate} data={data} params={data?.gate_parameters} busy={busy} act={act} />
          </SectionCard>
          <SectionCard title="Parameter lintasan gate"><Params params={data?.gate_parameters} /></SectionCard>
          {isAdmin && (
            <SectionCard title="Simulator lintasan (tanpa perangkat)">
              <div className="flex flex-wrap items-center gap-2">
                <KNSelect data-testid="u300-scenario" value={scenario} onValueChange={setScenario} options={SCENARIOS}
                  className="field !py-1 !px-2 text-[12px] w-auto" />
                <button type="button" className="secondary-button !py-1 text-[12px]" disabled={busy} onClick={simulate}
                  data-testid="u300-simulate">Jalankan simulasi</button>
              </div>
            </SectionCard>
          )}
        </>
      ) : (
        <p className="text-[12px] text-[#6B6B73]" data-testid="u300-no-profile">Profil V2 belum diterbitkan — reader belum bisa dipakai sebagai gate V2.</p>
      )}
      <SectionCard title="Riwayat lintasan">
        <U300PassageList passages={data?.passages} busy={busy} onAcknowledge={ackPassage} onEvidence={evidence} page={page} />
        <p className="mt-2 text-[11px] text-[#6B6B73]">Merah = pelanggaran (gate terkunci) · Kuning = perlu diperiksa, barang jalan · Batal = lintasan kosong/mundur. Riwayat hanya menampilkan dokumen dalam cakupan akses Anda.</p>
      </SectionCard>
    </section>
  );
}
