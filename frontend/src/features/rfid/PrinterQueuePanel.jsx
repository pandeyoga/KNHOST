/**
 * PREP-F — Antrean printer label RFID per gedung (Chainway CP30EN).
 * Tiga hal yang SENGAJA dipisah: kesehatan perangkat (connector ≠ printer) · status job & per label · verifikasi C72.
 * Butir "Perlu tindak lanjut" (tidak pasti / gagal / bertentangan / klaim habis saat mencetak) diputuskan operator
 * berizin dengan bukti — tidak ada cetak ulang otomatis.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ClipboardCheck, Printer, RefreshCw, Settings2 } from "lucide-react";
import DetailModal from "../../components/DetailModal";
import ErrorNotice from "../../components/ErrorNotice";
import FilterSelect from "../../components/FilterSelect";   // pola UI 16 Nov — saringan dropdown (dulu FilterChips)
import PaginationBar from "../../components/PaginationBar";
import axios, { API } from "../../services/apiClient";
import { canCurrent } from "../../config/roles";
import LabelPreview from "./LabelPreview";
import { PrinterProfileModal, ResolvePrintItemModal } from "./PrinterModals";
import { EmptyBox, Pill, SectionCard, fmtTime } from "./rfidShared";
import {
  EVIDENCE_SOURCE, FOLLOW_UP_CSV_COLUMNS, FOLLOW_UP_REASON, ITEM_STATUS, JOB_CSV_COLUMNS, JOB_STATUS, KIND_LABEL,
  RESULT_TEXT, ageText, epcTail, jobProgress, printerHealth,
} from "./printerLabels";

const PAGE = 20;
const FILTERS = [
  { key: "open", label: "Sedang berjalan", statuses: ["queued", "printing"] },
  { key: "review", label: "Perlu ditinjau", statuses: ["needs_review", "partial", "failed"] },
  { key: "done", label: "Tercetak", statuses: ["printed", "verified", "verified_with_issues"] },
  { key: "all", label: "Semua", statuses: null },
];

function usePaged(rows) {
  const [page, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  useEffect(() => { if (page > pages) setPage(1); }, [page, pages]);
  return { page, setPage, pages, pageRows: rows.slice((page - 1) * PAGE, page * PAGE) };
}

export function PrinterHealthCards({ warehouses = [], isAdmin, onProfile }) {
  const printers = warehouses.flatMap((w) => (w.printers || []).map((p) => ({ ...p, warehouse_name: w.warehouse_name })));
  if (!printers.length) return <EmptyBox icon={Printer} text="Belum ada printer label terdaftar di gudang ini." />;
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="printer-health">
      {printers.map((p) => {
        const h = printerHealth(p);
        return (
          <div key={p.id} className="rounded-xl border border-[#EFF0F2] bg-white p-3 text-[12px]" data-testid={`printer-health-${p.id}`}>
            <div className="flex items-center gap-2 font-bold"><Printer size={14} /> {p.name || p.code}
              <span className="ml-auto text-[10.5px] font-normal text-[#6B6B73]">{p.warehouse_name}</span></div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <Pill color={h.connector[0]} testId={`printer-health-conn-${p.id}`}>{h.connector[1]}</Pill>
              <Pill color={h.printer[0]} testId={`printer-health-state-${p.id}`}>{h.printer[1]}</Pill>
            </div>
            <div className="mt-1 text-[11px] text-[#6B6B73]">
              Connector terlihat {ageText(p.last_heartbeat)}{p.connector?.version ? ` · v${p.connector.version}` : ""}
              {p.connector?.host ? ` · PC ${p.connector.host}` : ""}</div>
            <div className="text-[11px] text-[#6B6B73]">Printer dicek {ageText(p.printer_checked_at)}
              {p.printer_detail ? ` · ${p.printer_detail}` : ""}</div>
            <div className="text-[11px] text-[#6B6B73]">Label terakhir terkonfirmasi {ageText(p.last_confirmed_output_at)}</div>
            {p.connector?.ledger?.pending_results > 0 && (
              <div className="text-[11px] font-semibold text-[#8C4A00]">{p.connector.ledger.pending_results} hasil menunggu terkirim ke ERP</div>)}
            {p.connector_conflict && (
              <div className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-[#C0341D]" data-testid={`printer-health-conflict-${p.id}`}>
                <AlertTriangle size={12} /> Dua connector memakai key printer yang sama — matikan salah satu.</div>)}
            <button type="button" className="secondary-button mt-2 !py-1 text-[11px]" data-testid={`printer-profile-open-${p.id}`}
              onClick={() => onProfile(p.id)}><Settings2 size={12} /> {isAdmin ? "Profil & kalibrasi" : "Lihat profil"}</button>
          </div>
        );
      })}
    </div>
  );
}

export function PrintJobDetail({ jobId, onClose, onChanged }) {
  const [job, setJob] = useState(null);
  const [err, setErr] = useState("");
  const [preview, setPreview] = useState(null);
  const [resolveRow, setResolveRow] = useState(null);
  const canApprove = canCurrent("wms", "approve");
  const load = useCallback(async () => {
    try { setJob((await axios.get(`${API}/rfid/print-jobs/${jobId}`)).data); setErr(""); }
    catch (e) { setErr(e); }
  }, [jobId]);
  useEffect(() => { load(); }, [load]);
  const showPreview = async (it) => {
    try {
      const { data } = await axios.post(`${API}/rfid/printers/label-preview`, { job_id: jobId, item_id: it.item_id });
      setPreview({ ...data, roll_no: it.roll_no });
    } catch (e) { setErr(e); }
  };
  if (err && !job) return <ErrorNotice message={err} onRetry={load} />;
  if (!job) return <div className="p-4 text-[12px] text-[#6B6B73]">Memuat job…</div>;
  const [jc, jl] = JOB_STATUS[job.status] || ["gray", job.status];
  const lv = job.last_verify;
  const followReason = (it) => {
    if (it.conflict) return "conflict";
    if (it.status === "unknown") return "unknown";
    if (it.status === "failed" && !it.resolution) return "failed";
    if (it.stale) return "stale_started";
    return null;
  };
  return (
    <SectionCard testId="print-job-detail" title={`${job.job_number} — ${KIND_LABEL[job.kind] || job.kind} · ${job.item_count} label`}
      right={<button type="button" className="secondary-button !py-1 text-[11px]" onClick={onClose} data-testid="print-job-detail-close">Tutup</button>}>
      {err && <ErrorNotice message={err} onRetry={load} />}
      <div className="grid gap-2 text-[12px] sm:grid-cols-3" data-testid="print-job-dims">
        <div className="rounded-lg bg-[#F7F7F9] p-2"><div className="text-[10.5px] text-[#6B6B73]">Status job</div>
          <Pill color={jc} testId="print-job-status">{jl}</Pill><div className="mt-1 text-[11px]">{jobProgress(job)}</div></div>
        <div className="rounded-lg bg-[#F7F7F9] p-2"><div className="text-[10.5px] text-[#6B6B73]">Printer / klaim</div>
          {job.lease ? (<div className="text-[11px]" data-testid="print-job-lease">{job.lease.device_name || "perangkat tanpa nama"} ·
            {job.lease_live ? ` klaim berlaku s/d ${fmtTime(job.lease.expires_at)}` : " klaim habis"}
            {job.lease.renew_count ? ` · diperpanjang ${job.lease.renew_count}×` : ""}</div>)
            : <div className="text-[11px]">{job.printed_by_device ? `Dicetak ${job.printed_by_device}` : job.printed_via === "manual" ? "Ditandai tercetak manual" : "Belum diklaim printer"}</div>}
          <div className="text-[10.5px] text-[#6B6B73]">Diklaim {job.print_attempts || 0}× {(job.attempts || []).some((a) => a.kind === "reclaim") ? "· pernah diambil alih printer lain" : ""}</div></div>
        <div className="rounded-lg bg-[#F7F7F9] p-2"><div className="text-[10.5px] text-[#6B6B73]">Verifikasi handheld (C72)</div>
          <div className="text-[11px]" data-testid="print-job-verify">{!lv ? "Belum diverifikasi — tercetak belum berarti terverifikasi."
            : lv.result === "clean" ? `Bersih · ${fmtTime(lv.at)}` : lv.result === "simulated" ? "Simulasi (bukan bukti)" : `Bermasalah · ${fmtTime(lv.at)}`}</div></div>
      </div>
      {job.reason_note && <p className="mt-2 text-[11px] text-[#6B6B73]">Alasan: {job.reason_note}</p>}
      {job.reprint_of && <p className="text-[11px] text-[#6B6B73]">Cetak ulang dari job {job.reprint_of.job_number}</p>}
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-[12px]" data-testid="print-job-items">
          <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] text-[#8E8E93]">
            <th className="py-1.5 pr-2">Roll</th><th className="pr-2">EPC</th><th className="pr-2">Status label</th>
            <th className="pr-2">Cetak · chip</th><th className="pr-2">Bukti</th><th className="pr-2" /></tr></thead>
          <tbody>
            {(job.items || []).map((it) => {
              const [ic, il] = ITEM_STATUS[it.status] || ["gray", it.status || "—"];
              const fr = followReason(it);
              return (
                <tr key={it.item_id || it.roll_id} className="border-b border-[#F5F5F7] align-top" data-testid={`print-item-${it.item_id}`}>
                  <td className="py-1.5 pr-2 font-semibold">{it.roll_no}<div className="text-[10.5px] font-normal text-[#6B6B73]">{it.sku}</div></td>
                  <td className="pr-2 font-mono text-[11px]" title={it.epc || ""}>{epcTail(it.epc)}</td>
                  <td className="pr-2"><Pill color={ic}>{il}</Pill>
                    {fr && <div className="text-[10.5px] font-semibold text-[#C0341D]">{FOLLOW_UP_REASON[fr]}</div>}
                    {it.resolution && <div className="text-[10.5px] text-[#6B6B73]">Diputuskan {it.resolution.by}</div>}
                    {it.superseded_by && <div className="text-[10.5px] text-[#6B6B73]">Diganti job {it.superseded_by.job_number}</div>}</td>
                  <td className="pr-2 text-[11px]">{RESULT_TEXT[it.print_status] || "—"} · {RESULT_TEXT[it.encode_status] || "—"}</td>
                  <td className="pr-2 text-[11px] text-[#6B6B73]">{EVIDENCE_SOURCE[it.evidence?.source] || it.evidence?.source || "—"}
                    {it.evidence?.detail ? <div className="max-w-[220px] truncate" title={it.evidence.detail}>{it.evidence.detail}</div> : null}</td>
                  <td className="pr-2 whitespace-nowrap">
                    <button type="button" className="secondary-button !px-2 !py-0.5 text-[10.5px]" data-testid={`print-item-preview-${it.item_id}`}
                      onClick={() => showPreview(it)}>Pratinjau</button>
                    {fr && canApprove && (
                      <button type="button" className="secondary-button ml-1 !px-2 !py-0.5 text-[10.5px]" data-testid={`print-item-resolve-${it.item_id}`}
                        onClick={() => setResolveRow({ ...it, reason: fr, job_id: job.id, job_number: job.job_number, kind: job.kind,
                          chip_written: it.encode_status === "confirmed" && it.print_status === "failed" })}>Tinjau</button>)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {preview && (
        <div className="mt-3 rounded-lg border border-[#EFF0F2] p-2" data-testid="print-job-preview">
          <div className="mb-1 text-[11.5px] font-semibold">Pratinjau label {preview.roll_no}</div>
          {preview.layout ? <LabelPreview layout={preview.layout} /> : <p className="text-[11px]">{preview.note}</p>}
          {preview.zpl && <details className="mt-1 text-[11px]"><summary className="cursor-pointer text-[#0058CC]">ZPL</summary>
            <pre className="max-h-40 overflow-auto rounded bg-[#F7F7F9] p-2 font-mono text-[10.5px]">{preview.zpl}</pre></details>}
        </div>)}
      {resolveRow && <ResolvePrintItemModal row={resolveRow} onClose={() => setResolveRow(null)}
        onDone={async () => { setResolveRow(null); await load(); onChanged?.(); }} />}
    </SectionCard>
  );
}

export default function PrinterQueuePanel({ whId, isAdmin = false }) {
  const [filter, setFilter] = useState("open");
  const [jobs, setJobs] = useState([]);
  const [follow, setFollow] = useState([]);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openJob, setOpenJob] = useState(null);
  const [resolveRow, setResolveRow] = useState(null);
  const [profileId, setProfileId] = useState(null);
  const canApprove = canCurrent("wms", "approve");
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = whId ? { warehouse_id: whId } : {};
      const [q, f, s] = await Promise.all([
        axios.get(`${API}/rfid/printers/queue`, { params: { ...params, limit: 500 } }),
        axios.get(`${API}/rfid/printers/follow-up`, { params }),
        axios.get(`${API}/rfid/printer-status`, { params }),
      ]);
      setJobs(q.data.jobs || []); setFollow(f.data.items || []); setStatus(s.data); setError(null);
    } catch (e) { setError(e); } finally { setLoading(false); }
  }, [whId]);
  useEffect(() => { load(); }, [load]);
  const flt = FILTERS.find((x) => x.key === filter) || FILTERS[0];
  const shown = useMemo(() => (flt.statuses ? jobs.filter((j) => flt.statuses.includes(j.status)) : jobs), [jobs, flt]);
  const jp = usePaged(shown);
  const fp = usePaged(follow);
  const countOf = (f) => (f.statuses ? jobs.filter((j) => f.statuses.includes(j.status)).length : jobs.length);
  return (
    <div className="space-y-3" data-testid="printer-queue-panel">
      {error && <ErrorNotice message={error} onRetry={load} />}
      <SectionCard testId="printer-queue-health" title="Kesehatan printer & connector"
        right={<button type="button" className="secondary-button !py-1 text-[12px]" onClick={load} disabled={loading} data-testid="printer-queue-refresh">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Muat ulang</button>}>
        <PrinterHealthCards warehouses={status?.warehouses || []} isAdmin={isAdmin} onProfile={setProfileId} />
        <p className="mt-2 text-[10.5px] text-[#6B6B73]">Connector aktif ≠ printer siap: connector berjalan di PC gudang dan
          melaporkan status printer secara terpisah. Bila internet putus, antrean tertahan dan hasil cetak disimpan di PC lalu dikirim saat tersambung.</p>
      </SectionCard>

      <SectionCard testId="printer-follow-up" title={`Perlu tindak lanjut (${follow.length})`}>
        {follow.length === 0 ? <EmptyBox icon={ClipboardCheck} text="Tidak ada label yang hasilnya tidak pasti atau gagal." /> : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]" data-testid="printer-follow-up-list">
                <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] text-[#8E8E93]">
                  <th className="py-1.5 pr-2">Roll</th><th className="pr-2">Job</th><th className="pr-2">Alasan</th>
                  <th className="pr-2">Cetak · chip</th><th className="pr-2">Mulai</th><th className="pr-2" /></tr></thead>
                <tbody>
                  {fp.pageRows.map((r) => (
                    <tr key={`${r.job_id}-${r.item_id}`} className="border-b border-[#F5F5F7]" data-testid={`printer-follow-up-${r.item_id}`}>
                      <td className="py-1.5 pr-2 font-semibold">{r.roll_no}<div className="font-mono text-[10.5px] font-normal">{epcTail(r.epc)}</div></td>
                      <td className="pr-2">{r.job_number}<div className="text-[10.5px] text-[#6B6B73]">{r.warehouse_name}</div></td>
                      <td className="pr-2"><Pill color={r.reason === "failed" ? "red" : "orange"}>{FOLLOW_UP_REASON[r.reason] || r.reason}</Pill>
                        {r.chip_written && <div className="text-[10.5px] font-semibold text-[#C0341D]">chip sudah tertulis</div>}</td>
                      <td className="pr-2 text-[11px]">{RESULT_TEXT[r.print_status] || "—"} · {RESULT_TEXT[r.encode_status] || "—"}</td>
                      <td className="pr-2 text-[11px]">{fmtTime(r.started_at)}</td>
                      <td className="pr-2 whitespace-nowrap">
                        <button type="button" className="secondary-button !px-2 !py-0.5 text-[10.5px]" onClick={() => setOpenJob(r.job_id)}
                          data-testid={`printer-follow-up-job-${r.item_id}`}>Job</button>
                        {canApprove && <button type="button" className="secondary-button ml-1 !px-2 !py-0.5 text-[10.5px]"
                          data-testid={`printer-follow-up-resolve-${r.item_id}`} onClick={() => setResolveRow(r)}>Tinjau</button>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!canApprove && <p className="mt-1 text-[10.5px] text-[#6B6B73]" data-testid="printer-follow-up-noperm">
              Keputusan hanya oleh Admin Gudang / Manajer (izin persetujuan).</p>}
            <PaginationBar page={fp.page} pageSize={PAGE} total={follow.length} hasMore={fp.page < fp.pages}
              onPrev={() => fp.setPage((p) => Math.max(1, p - 1))} onNext={() => fp.setPage((p) => Math.min(fp.pages, p + 1))}
              testId="printer-follow-up-pager" label="label"
              exportConfig={{ columns: FOLLOW_UP_CSV_COLUMNS, rows: fp.pageRows, fetchAll: async () => follow,
                filename: "tindak-lanjut-printer" }} />
          </>
        )}
      </SectionCard>

      <SectionCard testId="printer-jobs" title="Antrean job cetak">
        <FilterSelect testId="printer-jobs-filter" value={filter} onChange={(k) => { setFilter(k); jp.setPage(1); }}
          options={FILTERS.map((f) => ({ key: f.key, label: f.label, count: countOf(f) }))} />
        {shown.length === 0 ? <EmptyBox icon={Printer} text="Tidak ada job untuk saringan ini." /> : (
          <>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-[12px]" data-testid="printer-jobs-list">
                <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] text-[#8E8E93]">
                  <th className="py-1.5 pr-2">Job</th><th className="pr-2">Status</th><th className="pr-2">Label</th>
                  <th className="pr-2">Printer</th><th className="pr-2">Dibuat</th></tr></thead>
                <tbody>
                  {jp.pageRows.map((j) => {
                    const [c, l] = JOB_STATUS[j.status] || ["gray", j.status];
                    return (
                      <tr key={j.id} className="cursor-pointer border-b border-[#F5F5F7] hover:bg-[#FAFAFB]" data-testid={`printer-job-${j.id}`}
                        onClick={() => setOpenJob(j.id)}>
                        <td className="py-1.5 pr-2 font-semibold">{j.job_number}<div className="text-[10.5px] font-normal text-[#6B6B73]">{KIND_LABEL[j.kind] || j.kind} · {j.warehouse_name}</div></td>
                        <td className="pr-2"><Pill color={c}>{l}</Pill>{j.review_open > 0 && <div className="text-[10.5px] font-semibold text-[#C0341D]">{j.review_open} perlu tindak lanjut</div>}</td>
                        <td className="pr-2 text-[11px]">{jobProgress(j)}</td>
                        <td className="pr-2 text-[11px]">{j.lease ? `${j.lease.device_name || "perangkat tanpa nama"}${j.lease_live ? "" : " (klaim habis)"}` : j.printed_by_device || "—"}</td>
                        <td className="pr-2 text-[11px]">{fmtTime(j.created_at)}<div className="text-[10.5px] text-[#6B6B73]">{j.created_by}</div></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <PaginationBar page={jp.page} pageSize={PAGE} total={shown.length} hasMore={jp.page < jp.pages}
              onPrev={() => jp.setPage((p) => Math.max(1, p - 1))} onNext={() => jp.setPage((p) => Math.min(jp.pages, p + 1))}
              testId="printer-jobs-pager" label="job"
              exportConfig={{ columns: JOB_CSV_COLUMNS, rows: jp.pageRows, fetchAll: async () => shown, filename: "antrean-printer" }} />
          </>
        )}
      </SectionCard>

      {openJob && (
        <DetailModal open onClose={() => setOpenJob(null)} size="xl" label="Rincian job cetak" testId="print-job-modal" showClose={false}>
          <PrintJobDetail jobId={openJob} onClose={() => setOpenJob(null)} onChanged={load} />
        </DetailModal>
      )}
      {resolveRow && <ResolvePrintItemModal row={resolveRow} onClose={() => setResolveRow(null)}
        onDone={async () => { setResolveRow(null); await load(); }} />}
      {profileId && <PrinterProfileModal deviceId={profileId} isAdmin={isAdmin} onClose={() => setProfileId(null)} onSaved={load} />}
    </div>
  );
}
