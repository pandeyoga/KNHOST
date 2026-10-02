/**
 * LoadingCheckPanel (FASE R4) — Final Loading Check: sweep handheld vs manifest SO
 * sebelum barang naik mobil. Hasil tidak bersih = dispatch DIBLOKIR backend.
 */
import { useEffect, useState } from "react";
import { ScanLine, Zap, CheckCircle, AlertTriangle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";

export const LoadingCheckPanel = ({ orderId, soNumber }) => {
  const [session, setSession] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [epcInput, setEpcInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [labelInput, setLabelInput] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [lastLog, setLastLog] = useState([]);

  const loadStatus = async () => {
    try {
      const r = await axios.get(`${API}/outbound/so/${orderId}/loading-check`);
      setSession(r.data.open_session);
      setLastResult(r.data.last_result);
      setLastLog(r.data.last_scan_log || []);
    } catch { /* noop */ }
  };
  useEffect(() => { if (orderId) loadStatus(); }, [orderId]); // eslint-disable-line

  const run = async (fn) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e) { setError(apiErrorText(e, "Gagal")); } finally { setBusy(false); }
  };
  const start = () => run(async () => {
    const r = await axios.post(`${API}/outbound/so/${orderId}/loading-check/start`);
    setSession(r.data);
  });
  const scan = (epcs, source = "manual") => run(async () => {
    const r = await axios.post(`${API}/outbound/loading-check/${session.id}/scan`, { epcs, source });
    setSession(r.data); setEpcInput("");
  });
  const complete = () => run(async () => {
    await axios.post(`${API}/outbound/loading-check/${session.id}/complete`);
    setSession(null); setLastResult(null); await loadStatus();
  });
  const scanLabel = () => run(async () => {
    const r = await axios.post(`${API}/outbound/loading-check/${session.id}/scan-label`, { code: labelInput });
    setSession(r.data); setLabelInput("");
  });
  const override = () => run(async () => {
    if (overrideReason.trim().length < 5) throw new Error("Alasan override minimal 5 karakter.");
    await axios.post(`${API}/outbound/so/${orderId}/loading-check/override`, { reason: overrideReason });
    setOverrideReason(""); await loadStatus();
  });
  const untagged = session?.untagged || [];
  const resolved = new Set(session?.untagged_resolved || []);

  if (!orderId) return null;
  return (
    <div data-testid="loading-check-panel" className="rounded-lg border border-[#D9D2F0] bg-[#F7F5FF] p-2.5 space-y-2">
      <p className="flex items-center gap-1.5 text-[11.5px] font-bold text-[#4B3B9E]">
        <ScanLine size={13} /> Pemeriksaan Muat Akhir (handheld vs SO {soNumber || ""})
      </p>
      {error && <p data-testid="lc-error" className="rounded bg-[#FBE9E7] px-2 py-1 text-[11px] font-semibold text-[#C0341D]">{error}</p>}

      {lastResult && !session && (
        <div data-testid="lc-last-result" className={`flex items-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-semibold ${
          lastResult.result === "clean" ? "bg-[#E6F6EC] text-[#1B7F4B]"
            : lastResult.result === "override" ? "bg-[#FFF4E5] text-[#8C4A00]" : "bg-[#FBE9E7] text-[#C0341D]"}`}>
          {["clean", "override"].includes(lastResult.result) ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
          {lastResult.result === "clean"
            ? `BERSIH — ${lastResult.matched}/${lastResult.expected} cocok. Dispatch dibuka selama roll tidak berubah.`
            : lastResult.result === "override"
              ? `OVERRIDE oleh ${lastResult.by}: ${lastResult.reason} — berlaku untuk ${lastResult.manifest?.length || 0} roll saat ini.`
              : lastResult.result === "simulated"
                ? "SIMULASI — bukan bukti fisik, dispatch DIBLOKIR. Ulangi dengan scan nyata atau override berizin."
                : `ADA SELISIH (missing ${lastResult.missing?.length || 0}, extra ${lastResult.extra?.length || 0}, tanpa tag ${lastResult.untagged_unresolved?.length || 0}) — dispatch DIBLOKIR, ulangi check.`}
        </div>
      )}

      <ScanHistory log={session ? session.scan_log || [] : lastLog} />

      {!session ? (
        <div className="flex flex-wrap items-center gap-1.5">
          <button data-testid="lc-start" disabled={busy} onClick={start}
            className="rounded-lg bg-[#4B3B9E] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
            {lastResult ? "Ulangi Loading Check" : "Mulai Loading Check"}
          </button>
          <input data-testid="lc-override-reason" value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)}
            placeholder="Alasan override (izin supervisor)" className="min-w-[180px] flex-1 rounded border border-[#D9D2F0] px-2 py-1 text-[10.5px]" />
          <button data-testid="lc-override" disabled={busy || overrideReason.trim().length < 5} onClick={override}
            className="rounded border border-[#B23B14] px-2.5 py-1 text-[10.5px] font-semibold text-[#B23B14] disabled:opacity-40">Override</button>
        </div>
      ) : (
        <div className="space-y-1.5">
          <p className="text-[11px] text-[#6B6B73]" data-testid="lc-progress">
            Cocok {session.matched_count ?? 0}/{session.expected_count ?? session.expected?.length} EPC
            {session.simulated && <span className="font-semibold text-[#B23B14]" data-testid="lc-simulated-warn"> · berisi scan SIMULASI (hasil tidak sah)</span>}
            {untagged.length > 0 && <span className="text-[#B23B14]" data-testid="lc-untagged-count"> · roll tanpa tag {resolved.size}/{untagged.length} terverifikasi label</span>}
            {session.not_committed_count > 0 && <span className="block font-semibold text-[#B23B14]" data-testid="lc-not-committed-warn">⚠ {session.not_committed_count} roll masih reserved (belum commit) — check bisa bersih tapi dispatch akan tertahan sampai roll di-commit</span>}
          </p>
          {untagged.length > 0 && (
            <div data-testid="lc-untagged" className="rounded border border-dashed border-[#D9D2F0] bg-white p-1.5 text-[10.5px]">
              <div className="flex flex-wrap gap-1">
                {untagged.map((u) => (
                  <span key={u.roll_id} data-testid={`lc-untagged-${u.roll_id}`}
                    className={`rounded px-1.5 py-0.5 font-semibold ${resolved.has(u.roll_id) ? "bg-[#E6F6EC] text-[#1B7F4B]" : "bg-[#FBE9E7] text-[#C0341D]"}`}>
                    {u.roll_no} · {u.reason}</span>))}
              </div>
              <div className="mt-1 flex gap-1">
                <input data-testid="lc-label-input" value={labelInput} onChange={(e) => setLabelInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && labelInput.trim()) scanLabel(); }}
                  placeholder="Scan label / no. roll tanpa tag" className="flex-1 rounded border border-[#D9D2F0] px-2 py-1 font-mono" />
                <button data-testid="lc-label-scan" disabled={busy || !labelInput.trim()} onClick={scanLabel}
                  className="rounded bg-[#4B3B9E] px-2.5 py-1 font-semibold text-white disabled:opacity-40">Verifikasi</button>
              </div>
            </div>
          )}
          <textarea data-testid="lc-input" className="h-12 w-full rounded border border-[#D9D2F0] px-2 py-1 font-mono text-[10.5px]"
            placeholder="Tempel EPC hasil sweep handheld…" value={epcInput} onChange={(e) => setEpcInput(e.target.value)} />
          <div className="flex flex-wrap gap-1.5">
            <button data-testid="lc-scan" disabled={busy || !epcInput.trim()}
              onClick={() => scan(epcInput.split(/[\s,;]+/).filter(Boolean))}
              className="rounded bg-[#4B3B9E] px-2.5 py-1 text-[10.5px] font-semibold text-white disabled:opacity-40">Kirim Scan</button>
            <button data-testid="lc-simulate" disabled={busy}
              onClick={() => scan((session.expected || []).map((e) => e.epc), "simulated")}
              title="Simulasi tidak membuka dispatch"
              className="flex items-center gap-1 rounded border border-[#4B3B9E] px-2.5 py-1 text-[10.5px] font-semibold text-[#4B3B9E] disabled:opacity-40">
              <Zap size={11} /> Simulasi (tidak sah)</button>
            <button data-testid="lc-complete" disabled={busy} onClick={complete}
              className="ml-auto rounded bg-[#1B7F4B] px-2.5 py-1 text-[10.5px] font-semibold text-white disabled:opacity-40">Selesaikan</button>
          </div>
        </div>
      )}
    </div>
  );
};

const SRC = { device: ["Perangkat", "bg-[#E6F6EC] text-[#1B7F4B]"], manual: ["Manual", "bg-[#EAF2FF] text-[#0058CC]"],
  simulated: ["Simulasi", "bg-[#FBE9E7] text-[#C0341D]"] };

const ScanHistory = ({ log }) => {
  const [open, setOpen] = useState(false);
  if (!log.length) return null;
  return (
    <div data-testid="lc-scan-history" className="rounded border border-[#D9D2F0] bg-white text-[10.5px]">
      <button data-testid="lc-scan-history-toggle" onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-2 py-1 font-semibold text-[#4B3B9E]">
        Riwayat scan ({log.length}) <span>{open ? "Sembunyikan" : "Lihat"}</span>
      </button>
      {open && (
        <div className="max-h-40 divide-y divide-[#F0EEF8] overflow-y-auto">
          {[...log].reverse().map((e, i) => {
            const [label, cls] = SRC[e.source] || [e.source, "bg-[#F5F5F7] text-[#6B6B73]"];
            return (
              <div key={`${e.at}-${i}`} data-testid={`lc-scan-log-${i}`} className="flex items-center gap-1.5 px-2 py-1">
                <span className={`rounded px-1 font-semibold ${cls}`}>{label}</span>
                <span className="font-semibold">{e.by || "—"}</span>
                {e.device_name && e.device_name !== e.by && <span className="text-[#6B6B73]">· {e.device_name}</span>}
                <span className="text-[#6B6B73]">· {e.count} EPC</span>
                <span className="ml-auto text-[#8E8E93]">{new Date(e.at).toLocaleString("id-ID")}</span>
              </div>);
          })}
        </div>)}
    </div>
  );
};

export default LoadingCheckPanel;
