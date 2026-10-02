/**
 * RfidPrintVerifyPanel (FASE R1) — cetak tag RFID massal + sesi verifikasi handheld.
 * Alur: pilih roll belum-ber-tag → Print Job (ZPL utk printer Chainway) → tandai
 * tercetak → verifikasi (expected vs scanned) → routing SIMPAN / CROSS-DOCK.
 */
import { useEffect, useRef, useState } from "react";
import { Printer, CheckCircle2, Download, ScanLine, PackageCheck, Zap, ArrowRight, X } from "lucide-react";
import DetailModal from "../../components/DetailModal";
import axios, { API } from "../../services/apiClient";
import { q, fmtTime, Pill, EmptyBox, SectionCard } from "./rfidShared";

const JOB_STATUS = {
  queued: ["blue", "Antre Cetak"], printed: ["orange", "Tercetak"],
  verified: ["green", "Terverifikasi"], verified_with_issues: ["red", "Verif. Bermasalah"],
};

export default function RfidPrintVerifyPanel({ whId, selectedEntity, onChanged }) {
  const [candidates, setCandidates] = useState([]);
  const [selected, setSelected] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [session, setSession] = useState(null);
  const [scanInput, setScanInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const load = async () => {
    setError("");
    try {
      const params = whId ? { warehouse_id: whId } : {};
      const [u, j] = await Promise.all([
        axios.get(`${API}/rfid/untagged-rolls`, { params }),
        axios.get(`${API}/rfid/print-jobs`, { params }),
      ]);
      setCandidates(u.data.rolls || []);
      setJobs(j.data.jobs || []);
    } catch (e) { setError(e.response?.data?.detail || e.message); }
  };
  useEffect(() => { load(); setSelected([]); setActiveJob(null); setSession(null); }, [whId, selectedEntity]); // eslint-disable-line

  const flashT = useRef(null);
  const flash = (m) => {
    setMsg(m);
    if (flashT.current) clearTimeout(flashT.current);
    flashT.current = setTimeout(() => setMsg(""), 3000);
  };
  const fail = (e, f) => setError(e.response?.data?.detail || f);

  const toggleSel = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const createJob = async () => {
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/rfid/print-jobs`, { roll_ids: selected });
      flash(`Print job ${r.data.job_number} dibuat — ${r.data.item_count} tag siap cetak.`);
      setSelected([]); await load(); openJob(r.data.id);
      onChanged && onChanged();
    } catch (e) { fail(e, "Gagal membuat print job"); } finally { setBusy(false); }
  };

  const openJob = async (jobId, keepSession = false) => {
    if (!keepSession) setSession(null);
    setError("");
    try {
      const r = await axios.get(`${API}/rfid/print-jobs/${jobId}`);
      setActiveJob(r.data);
      const s = await axios.get(`${API}/rfid/print-jobs`, { params: {} });
      setJobs(s.data.jobs || []);
    } catch (e) { fail(e, "Gagal memuat job"); }
  };

  const markPrinted = async () => {
    setBusy(true);
    try { await axios.post(`${API}/rfid/print-jobs/${activeJob.id}/mark-printed`); flash("Job ditandai tercetak — tempel tag ke roll fisik."); await openJob(activeJob.id); await load(); }
    catch (e) { fail(e, "Gagal tandai tercetak"); } finally { setBusy(false); }
  };

  const startVerify = async () => {
    setBusy(true);
    try { const r = await axios.post(`${API}/rfid/print-jobs/${activeJob.id}/verify/start`); setSession(r.data); }
    catch (e) { fail(e, "Gagal mulai verifikasi"); } finally { setBusy(false); }
  };

  // UX-02 — unduh lewat apiClient (membawa X-Entity-Id terpilih), bukan href mentah
  const downloadZpl = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/rfid/print-jobs/${activeJob.id}/zpl`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `${activeJob.job_number || activeJob.id}.zpl`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { fail(e, "Gagal mengunduh ZPL"); } finally { setBusy(false); }
  };

  const sendScan = async (epcs, source = "manual") => {
    setBusy(true);
    try { const r = await axios.post(`${API}/rfid/verify-sessions/${session.id}/scan`, { epcs, source }); setSession(r.data); setScanInput(""); }
    catch (e) { fail(e, "Gagal kirim scan"); } finally { setBusy(false); }
  };

  const completeVerify = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/rfid/verify-sessions/${session.id}/complete`);
      flash(r.data.result === "clean" ? "Verifikasi BERSIH — semua tag cocok."
        : r.data.result === "simulated" ? "Verifikasi SIMULASI — tidak dihitung sebagai bukti; status job & roll tidak berubah."
          : "Verifikasi selesai DENGAN MASALAH — cek missing/extra lalu ulangi verifikasi.");
      await openJob(activeJob.id, true); await load(); onChanged && onChanged();
      setSession(r.data);
    } catch (e) { fail(e, "Gagal selesaikan verifikasi"); } finally { setBusy(false); }
  };

  const setRouting = async (routing) => {
    setBusy(true);
    try {
      const ids = (activeJob.items || []).map((i) => i.roll_id);
      await axios.post(`${API}/rfid/rolls/set-routing`, { roll_ids: ids, routing });
      flash(routing === "cross_dock" ? "Roll ditandai CROSS-DOCK (langsung kirim, tidak di-putaway)." : "Roll ditandai SIMPAN (masuk antrean putaway).");
      onChanged && onChanged();
    } catch (e) { fail(e, "Gagal set routing"); } finally { setBusy(false); }
  };

  const scannedSet = new Set(session?.scanned_epcs || []);
  // Klaim printer (RF-15) — printer mana yang sedang mengerjakan job + sisa waktu klaim
  const [nowTs, setNowTs] = useState(Date.now());
  const anyLease = jobs.some((j) => j.lease && j.status === "queued");
  useEffect(() => {
    if (!anyLease) return undefined;
    const t = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(t);
  }, [anyLease]);
  const leaseInfo = (j) => {
    if (!j?.lease || j.status !== "queued") return null;
    const left = Math.round((new Date(j.lease.expires_at).getTime() - nowTs) / 1000);
    const who = j.lease.device_name || j.lease.device_id;
    return left > 0
      ? { live: true, low: left <= 60, text: `Dikerjakan ${who} · sisa klaim ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}${left <= 60 ? " — HAMPIR HABIS" : ""}` }
      : { live: false, text: `Klaim ${who} kedaluwarsa — bisa diambil printer lain` };
  };
  const leaseCls = (li) => (li.low || !li.live ? "bg-[#FFF4E5] text-[#8C4A00]" : "bg-[#EAF2FF] text-[#0058CC]");
  const RetryBadge = ({ j }) => ((j.print_attempts || 0) > 2 ? (
    <span data-testid={`rfid-job-retry-${j.id}`} title="Job ditarik printer berkali-kali tanpa konfirmasi cetak — cek printer/media"
      className="mt-0.5 ml-1 inline-block rounded bg-[#FBE9E7] px-1.5 text-[10px] font-bold text-[#C0341D]">
      Diulang {j.print_attempts}× — cek printer</span>) : null);

  return (
    <div className="space-y-3" data-testid="rfid-print-panel">
      {error && <div data-testid="rfid-print-error" className="rounded-lg bg-[#FBE9E7] px-3 py-2 text-[12px] font-semibold text-[#C0341D]">{error}</div>}
      {msg && <div data-testid="rfid-print-msg" className="rounded-lg bg-[#E7F7EC] px-3 py-2 text-[12px] font-semibold text-[#1B7E3B]">{msg}</div>}

      <div className="grid gap-3 lg:grid-cols-2">
        {/* Kandidat cetak */}
        <SectionCard title={`Roll Siap Cetak Tag (${candidates.length})`} right={
          <div className="flex gap-1.5">
            <button data-testid="rfid-print-selectall" className="secondary-button text-[11px]"
              onClick={() => setSelected(selected.length === candidates.length ? [] : candidates.map((r) => r.id))}>
              {selected.length === candidates.length && candidates.length ? "Batal semua" : "Pilih semua"}
            </button>
            <button data-testid="rfid-print-create" disabled={busy || selected.length === 0} onClick={createJob}
              className="flex items-center gap-1 rounded-lg bg-[#0058CC] px-3 py-1.5 text-[12px] font-semibold text-white disabled:opacity-40">
              <Printer size={13} /> Print Job ({selected.length})
            </button>
          </div>}>
          {candidates.length === 0 ? <EmptyBox icon={PackageCheck} text="Tidak ada roll tanpa tag di gudang ini." /> : (
            <div className="max-h-72 space-y-1 overflow-y-auto">
              {candidates.map((r) => (
                <label key={r.id} data-testid={`rfid-print-cand-${r.id}`}
                  className="flex cursor-pointer items-center gap-2 rounded-lg bg-[#FAFAFB] px-2 py-1.5 hover:bg-[#F0F4FA]">
                  <input type="checkbox" checked={selected.includes(r.id)} onChange={() => toggleSel(r.id)} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[12px] font-semibold">{r.roll_no} · {r.sku || "—"}</span>
                    <span className="block truncate text-[11px] text-[#6B6B73]">{r.product_name} — {q(r.length_remaining)} {r.unit} · Lot {r.lot || "—"}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
        </SectionCard>

        {/* Daftar job */}
        <SectionCard title={`Print Jobs (${jobs.length})`}>
          {jobs.length === 0 ? <EmptyBox icon={Printer} text="Belum ada print job." /> : (
            <div className="max-h-72 space-y-1 overflow-y-auto">
              {jobs.map((j) => {
                const [color, label] = JOB_STATUS[j.status] || ["gray", j.status];
                return (
                  <button key={j.id} data-testid={`rfid-job-${j.id}`} onClick={() => openJob(j.id)}
                    className={`flex w-full items-center gap-2 rounded-lg border px-2 py-1.5 text-left ${
                      activeJob?.id === j.id ? "border-[#0058CC] bg-[#EAF2FF]" : "border-[#F0F0F2] bg-white hover:bg-[#FAFAFB]"}`}>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[12px] font-bold">{j.job_number} <span className="font-normal text-[#6B6B73]">· {j.item_count} {j.kind === "qr_label" ? "label QR" : "tag"}</span>
                        {j.kind === "qr_label" && <span className="ml-1 rounded bg-[#EAF2FF] px-1 text-[9.5px] font-bold text-[#0058CC]" data-testid={`rfid-job-kind-${j.id}`}>QR</span>}</span>
                      <span className="block text-[10.5px] text-[#8E8E93]">{j.warehouse_name} · {fmtTime(j.created_at)} · {j.created_by}</span>
                      {leaseInfo(j) && (
                        <span data-testid={`rfid-job-lease-${j.id}`} data-low={leaseInfo(j).low ? "1" : "0"}
                          className={`mt-0.5 inline-block rounded px-1.5 text-[10px] font-semibold ${leaseCls(leaseInfo(j))}`}>
                          <Printer size={9} className="mr-0.5 inline" />{leaseInfo(j).text}</span>)}
                      {j.status === "queued" && <RetryBadge j={j} />}
                      {!j.lease && j.status === "printed" && j.printed_via === "device" && (
                        <span data-testid={`rfid-job-printedby-${j.id}`} className="mt-0.5 block text-[10px] text-[#1B7F4B]">Dicetak printer {j.printed_by_device}</span>)}
                    </span>
                    <Pill color={color}>{label}</Pill>
                  </button>
                );
              })}
            </div>
          )}
        </SectionCard>
      </div>

      {/* Detail job aktif + verifikasi — pop-up (INV-UI-08), bukan saudara di bawah daftar. */}
      {activeJob && (
        <DetailModal onClose={() => { setActiveJob(null); setSession(null); }} size="lg"
          label={`Rincian job cetak ${activeJob.job_number}`} testId="rfid-job-detail-modal">
        <SectionCard title={`${activeJob.job_number} — ${activeJob.item_count} ${activeJob.kind === "qr_label" ? "label QR (tanpa encode RFID)" : "tag"}`} right={
          <div className="flex flex-wrap gap-1.5">
            <button data-testid="rfid-job-close" onClick={() => { setActiveJob(null); setSession(null); }}
              className="secondary-button text-[11px]"><X size={12} /> Tutup</button>
            <button data-testid="rfid-job-zpl" disabled={busy} onClick={downloadZpl}
              className="secondary-button text-[11px]"><Download size={12} /> Unduh ZPL</button>
            {activeJob.status === "queued" && (
              <button data-testid="rfid-job-printed" disabled={busy} onClick={markPrinted}
                className="flex items-center gap-1 rounded-lg bg-[#FF9500] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                <Printer size={12} /> Tandai Tercetak
              </button>
            )}
            {["printed", "verified_with_issues"].includes(activeJob.status) && session?.status !== "open" && activeJob.kind !== "qr_label" && (
              <button data-testid="rfid-job-verify" disabled={busy} onClick={startVerify}
                className="flex items-center gap-1 rounded-lg bg-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                <ScanLine size={12} /> {activeJob.status === "printed" && !session ? "Mulai Verifikasi" : "Ulangi Verifikasi"}
              </button>
            )}
            {activeJob.status.startsWith("verified") && (
              <>
                <button data-testid="rfid-routing-store" disabled={busy} onClick={() => setRouting("store")}
                  className="flex items-center gap-1 rounded-lg bg-[#1B7F4B] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                  <PackageCheck size={12} /> SIMPAN KE RAK
                </button>
                <button data-testid="rfid-routing-crossdock" disabled={busy} onClick={() => setRouting("cross_dock")}
                  className="flex items-center gap-1 rounded-lg bg-[#6B219A] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                  <ArrowRight size={12} /> CROSS-DOCK
                </button>
              </>
            )}
          </div>}>
          {(() => { const li = leaseInfo(jobs.find((j) => j.id === activeJob.id) || activeJob); return li && (
            <p data-testid="rfid-job-detail-lease" className={`mb-2 rounded-lg px-3 py-1.5 text-[11.5px] font-semibold ${leaseCls(li)}`}>
              <Printer size={12} className="mr-1 inline" />{li.text} · percobaan ke-{activeJob.print_attempts || 1}
              {(activeJob.print_attempts || 0) > 2 && <span className="ml-1 text-[#C0341D]">· sudah diulang {activeJob.print_attempts}× — cek printer/media label</span>}</p>); })()}
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] text-[#8E8E93]">
                <th className="py-1.5 pr-2">EPC</th><th className="pr-2">Roll</th><th className="pr-2">Produk</th>
                {session && <th className="pr-2 text-center">Scan</th>}
              </tr></thead>
              <tbody>
                {(activeJob.items || []).map((i) => (
                  <tr key={i.roll_id} className="border-b border-[#F5F5F7]">
                    <td className="py-1.5 pr-2 font-mono text-[11px] font-semibold">{i.epc}</td>
                    <td className="pr-2">{i.roll_no}</td>
                    <td className="pr-2 text-[#6B6B73]">{i.sku} · {i.product_name}</td>
                    {session && (
                      <td className="pr-2 text-center">
                        {scannedSet.has(i.epc)
                          ? <CheckCircle2 size={14} className="mx-auto text-[#1B7F4B]" />
                          : <span className="text-[10px] text-[#8E8E93]">belum</span>}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {session && session.status === "open" && (
            <div className="mt-3 rounded-lg border border-[#DCE6F5] bg-[#F7FAFF] p-3" data-testid="rfid-verify-session">
              <p className="text-[12px] font-bold">Sesi Verifikasi Handheld — {session.matched_count ?? 0}/{session.expected_count ?? session.expected?.length} cocok</p>
              <p className="mb-2 text-[11px] text-[#6B6B73]">Tempel EPC hasil baca handheld Chainway (satu per baris), atau simulasi.</p>
              <textarea data-testid="rfid-verify-input" className="field h-16 w-full font-mono text-[11px]"
                placeholder="E2XX-XXXX-…" value={scanInput} onChange={(e) => setScanInput(e.target.value)} />
              <div className="mt-2 flex flex-wrap gap-1.5">
                <button data-testid="rfid-verify-send" disabled={busy || !scanInput.trim()}
                  onClick={() => sendScan(scanInput.split(/[\s,;]+/).filter(Boolean))}
                  className="rounded-lg bg-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                  Kirim Hasil Scan
                </button>
                <button data-testid="rfid-verify-simulate" disabled={busy}
                  onClick={() => sendScan((session.expected || []).map((e) => e.epc), "simulated")}
                  className="flex items-center gap-1 rounded-lg border border-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-[#0058CC] disabled:opacity-40">
                  <Zap size={12} /> Simulasi (tidak sah)
                </button>
                <button data-testid="rfid-verify-complete" disabled={busy} onClick={completeVerify}
                  className="ml-auto rounded-lg bg-[#1B7F4B] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                  Selesaikan Verifikasi
                </button>
              </div>
            </div>
          )}
          {session && session.status === "completed" && (
            <div className={`mt-3 rounded-lg p-3 text-[12px] ${session.result === "clean" ? "bg-[#E6F6EC] text-[#1B7F4B]" : "bg-[#FFF4E5] text-[#8C4A00]"}`}
              data-testid="rfid-verify-result">
              <p className="font-bold" data-testid="rfid-verify-result-label">{session.result === "clean" ? "✓ BERSIH — semua tag cocok dengan job"
                : session.result === "simulated" ? "⚠ SIMULASI — bukan bukti fisik, job & roll tidak berubah" : "⚠ Selesai dengan masalah"}</p>
              {session.missing?.length > 0 && <p className="mt-1">Missing ({session.missing.length}): <span className="font-mono text-[11px]">{session.missing.join(", ")}</span></p>}
              {session.extra?.length > 0 && <p className="mt-1">Extra ({session.extra.length}): <span className="font-mono text-[11px]">{session.extra.join(", ")}</span></p>}
            </div>
          )}
        </SectionCard>
        </DetailModal>
      )}
    </div>
  );
}
