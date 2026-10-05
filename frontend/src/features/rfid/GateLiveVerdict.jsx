/**
 * GateLiveVerdict (UX-01 / P09) — verdict gate dari SERVER per passage (red-dominant, alarm terkunci
 * sampai diakui). Data basi / gagal ambil / heartbeat lama → TIDAK TERHUBUNG — TAHAN, bukan hijau lama.
 */
import { useEffect, useRef, useState } from "react";
import { Radio, WifiOff } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { fmtTime } from "./rfidShared";

const FETCH_STALE_S = 15;
const HEARTBEAT_STALE_S = 120;

export function useGateStatus(gateId, enabled, onNewRed) {
  const [data, setData] = useState(null);
  const [lastOk, setLastOk] = useState(0);
  const [fetchError, setFetchError] = useState("");
  const [now, setNow] = useState(Date.now());
  const seen = useRef(null);
  const load = async () => {
    if (!gateId) return;
    try {
      const r = await axios.get(`${API}/rfid/gate/${gateId}/status`);
      setData(r.data); setLastOk(Date.now()); setFetchError("");
      const p = r.data.passage;
      if (p && p.verdict === "red" && seen.current !== null && seen.current !== p.id + p.red_count) onNewRed?.();
      seen.current = p ? p.id + p.red_count : "";
    } catch (e) { setFetchError(apiErrorText(e, "Gagal mengambil status gate")); }
  };
  useEffect(() => {
    seen.current = null; setData(null); setLastOk(0);
    if (!enabled || !gateId) return undefined;
    load();
    const t = setInterval(load, 4000);
    const c = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(t); clearInterval(c); };
  }, [gateId, enabled]); // eslint-disable-line
  const fetchAge = lastOk ? Math.round((now - lastOk) / 1000) : null;
  const hb = data?.device?.heartbeat_age_s;
  const offline = !lastOk || fetchAge > FETCH_STALE_S;
  const deviceStale = data && (data.device.status !== "online" || !data.device.enabled || hb == null || hb > HEARTBEAT_STALE_S);
  const p = data?.passage;
  let state = "waiting";
  if (offline) state = "unknown";
  else if (deviceStale) state = "device_offline";
  else if (p && data.latched) state = "red";
  else if (p && !p.expired) state = p.verdict;
  return { data, state, fetchAge, fetchError, reload: load };
}

const LOOK = {
  red: ["#C0341D", "✕ MERAH — TAHAN"], green: ["#1B7F4B", "✓ HIJAU — LOLOS"], info: ["#0058CC", "INFO"],
  unknown: ["#5B5B66", "TIDAK TERHUBUNG — TAHAN"], device_offline: ["#8C4A00", "GATE OFFLINE — TAHAN"],
  waiting: ["#101418", "Menunggu passage…"],
};

export default function GateLiveVerdict({ gate, status, big = false, onAcked }) {
  const { data, state, fetchAge, fetchError, reload } = status;
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [bg, label] = LOOK[state] || LOOK.waiting;
  const p = data?.passage;
  const ack = async () => {
    setBusy(true); setErr("");
    try { await axios.post(`${API}/rfid/passages/${p.id}/acknowledge`, { note }); setNote(""); await reload(); onAcked?.(); }
    catch (e) { setErr(apiErrorText(e, "Gagal mengakui alarm")); } finally { setBusy(false); }
  };
  const showPassage = p && ["red", "green", "info"].includes(state);
  return (
    <div data-testid={big ? "rfid-kiosk-full-panel" : "rfid-gate-kiosk"} data-state={state}
      className={`${big ? "flex h-full flex-col items-center justify-center" : "rounded-2xl p-6"} text-center text-white transition-colors ${state === "red" ? "kn-kiosk-blink" : ""}`}
      style={{ background: bg }}>
      <p className={`${big ? "absolute left-6 top-6 text-[14px]" : "mb-2 text-[11px]"} flex items-center gap-2 font-semibold opacity-85`} data-testid="rfid-gate-health">
        {state === "unknown" ? <WifiOff size={14} /> : <Radio size={14} className="animate-pulse" />}
        {gate ? gate.code : "Gate"} · heartbeat {data?.device?.heartbeat_age_s ?? "—"} dtk lalu · data {fetchAge ?? "—"} dtk lalu
        {fetchError && <span className="rounded bg-black/25 px-1.5">{fetchError}</span>}
      </p>
      <p data-testid={big ? "rfid-kiosk-full-verdict" : "rfid-kiosk-verdict"}
        className={`${big ? "text-7xl sm:text-8xl" : "text-4xl sm:text-5xl"} font-black tracking-wide`}>{label}</p>
      {showPassage && (
        <div className={big ? "mt-6 max-w-4xl" : "mt-2"}>
          <p className={`${big ? "text-2xl" : "text-[14px]"} font-bold`} data-testid="rfid-passage-summary">
            Passage {fmtTime(p.started_at)} · {p.reads?.length || 0} roll · merah {p.red_count} · hijau {p.green_count}
            {data.latched && " · ALARM TERKUNCI"}
          </p>
          <div className={`mt-2 space-y-0.5 ${big ? "text-lg" : "text-[12px]"} opacity-95`}>
            {(p.reads || []).slice(0, 8).map((r) => (
              <p key={r.id} data-testid={`rfid-passage-read-${r.id}`}>
                {r.result === "red" ? "✕" : r.result === "green" ? "✓" : "•"} {r.roll_no || r.epc} —{" "}
                <b data-testid={`rfid-passage-action-${r.id}`}>{r.action || r.reason}</b>
                {r.action && <span className="opacity-75"> ({r.reason})</span>}
              </p>))}
          </div>
          {data.latched && (
            <div className="mx-auto mt-3 flex max-w-xl gap-1.5" data-testid="rfid-passage-ack-box">
              <input data-testid="rfid-passage-ack-note" value={note} onChange={(e) => setNote(e.target.value)}
                placeholder="Tindak lanjut (min. 5 karakter)" className="flex-1 rounded px-2 py-1 text-[12px] text-black" />
              <button data-testid="rfid-passage-ack" disabled={busy || note.trim().length < 5} onClick={ack}
                className="rounded bg-black/30 px-3 py-1 text-[12px] font-semibold disabled:opacity-40">Akui alarm</button>
            </div>)}
          {err && <p className="mt-1 text-[12px] font-semibold">{err}</p>}
        </div>
      )}
      {state === "unknown" && <p className="mt-2 text-[13px] opacity-90">Koneksi ke server terputus — jangan loloskan barang sampai status kembali.</p>}
      {state === "device_offline" && <p className="mt-2 text-[13px] opacity-90">Reader gate tidak mengirim heartbeat — periksa perangkat.</p>}
    </div>
  );
}
