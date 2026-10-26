import KNDatePicker from "@/components/KNDatePicker";
import apiErrorText from "../../utils/apiError";
import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { CalendarDays, Plus, Timer } from "lucide-react";
import FormModal from "../../components/FormModal";
import PageTabs from "../../components/PageTabs";
import { formatDate } from "../../utils/formatters";
import { LEAVE_TYPE_LABEL, REQ_STATUS, wibToday, countWorkdays } from "./leaveUtils";
import LeaveRequestFields from "./LeaveRequestFields";

// ESS — kartu Cuti & Lembur Saya (menggantikan placeholder H3 "Sisa Cuti").
// Fase 3 · P6 (L-03) — isian cuti = komponen yang SAMA dengan Cuti & Izin (HRD) (`LeaveRequestFields`);
// pilihan Cuti/Lembur di dalam pop-up = PageTabs baku (dulu dua tombol pil buatan sendiri).
export function MyLeaveCard() {
  const [data, setData] = useState(null);
  const [ot, setOt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("cuti");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  // form cuti
  const [type, setType] = useState("cuti_tahunan");
  const [from, setFrom] = useState(wibToday());
  const [to, setTo] = useState(wibToday());
  const [reason, setReason] = useState("");
  // form lembur
  const [otDate, setOtDate] = useState(wibToday());
  const [otHours, setOtHours] = useState("2");
  const [otReason, setOtReason] = useState("");

  useEffect(() => { load(); }, []); // eslint-disable-line
  async function load() {
    setLoading(true);
    try {
      const [a, b] = await Promise.all([
        axios.get(`${API}/hr/leave-requests/me`),
        axios.get(`${API}/hr/overtime/me`),
      ]);
      setData(a.data || null); setOt(b.data || null);
    } catch (_) { /* noop */ } finally { setLoading(false); }
  }

  function openModal() { setErr(""); setMsg(""); setTab("cuti"); setType("cuti_tahunan"); setFrom(wibToday()); setTo(wibToday()); setReason(""); setOtDate(wibToday()); setOtHours("2"); setOtReason(""); setOpen(true); }

  async function submitLeave() {
    const days = countWorkdays(from, to);
    if (days < 1) { setErr("Rentang harus mengandung minimal 1 hari kerja."); return; }
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/hr/leave-requests/me`, { leave_type: type, date_from: from, date_to: to, reason });
      setMsg("Pengajuan cuti terkirim, menunggu persetujuan."); await load();
      setTimeout(() => setOpen(false), 900);
    } catch (e) { setErr(apiErrorText(e, "Gagal mengajukan cuti.")); }
    finally { setBusy(false); }
  }
  async function submitOt() {
    const h = parseFloat(otHours);
    if (!(h > 0 && h <= 12)) { setErr("Jam lembur harus > 0 dan ≤ 12."); return; }
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/hr/overtime/me`, { date: otDate, hours: h, reason: otReason });
      setMsg("Pengajuan lembur terkirim, menunggu persetujuan."); await load();
      setTimeout(() => setOpen(false), 900);
    } catch (e) { setErr(apiErrorText(e, "Gagal mengajukan lembur.")); }
    finally { setBusy(false); }
  }

  const bal = data?.balance;
  const leaves = data?.requests || [];
  const otReqs = ot?.requests || [];
  const history = [
    ...leaves.map((l) => ({ ...l, kind: "leave" })),
    ...otReqs.map((o) => ({ ...o, kind: "ot" })),
  ].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")).slice(0, 5);

  return (
    <div className="section-card !p-4" data-testid="ess-leave-card">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2"><CalendarDays size={15} className="text-[#0058CC]" /><h3 className="text-[12.5px] font-bold">Cuti & Lembur Saya</h3></div>
      </div>
      {loading ? (
        <p className="text-[12px] text-[#6B6B73] py-3" data-testid="ess-leave-loading">Memuat...</p>
      ) : (
        <div data-testid="ess-leave-content">
          <div className="rounded-lg bg-[#F7F8FA] p-2.5 mb-2">
            <p className="text-[10px] uppercase font-semibold text-[#9A9BA3]">Sisa Cuti Tahun Ini</p>
            <p className="text-[20px] font-bold tabular-nums text-[#1F7A45] leading-tight" data-testid="ess-leave-balance">{bal ? bal.remaining : "—"} <span className="text-[11px] font-medium text-[#6B6B73]">/ {bal ? bal.entitlement : "—"} hari</span></p>
            {bal && <p className="text-[10.5px] text-[#6B6B73]">Terpakai {bal.used} · pending {bal.pending}</p>}
          </div>
          <div className="flex gap-2">
            <button data-testid="ess-leave-request-button" onClick={openModal} className="primary-button flex-1 justify-center !py-1.5"><Plus size={13} /> Ajukan</button>
          </div>
          {history.length === 0 ? (
            <p className="text-[10.5px] text-[#9A9BA3] mt-3 pt-2 border-t border-[#EFF0F2]" data-testid="ess-leave-history-empty">Belum ada pengajuan cuti / lembur.</p>
          ) : (
            <div className="mt-3 pt-2 border-t border-[#EFF0F2]">
              <p className="text-[10px] uppercase font-semibold text-[#9A9BA3] mb-1">Riwayat Terakhir</p>
              <div className="space-y-1 max-h-[120px] overflow-y-auto" data-testid="ess-leave-history">
                {history.map((h) => {
                  const s = REQ_STATUS[h.status] || REQ_STATUS.pending;
                  return (
                    <div key={h.kind + h.id} className="flex items-center justify-between text-[11px] gap-2">
                      <span className="flex items-center gap-1 min-w-0">{h.kind === "ot" ? <Timer size={11} className="text-[#B7791F] shrink-0" /> : <CalendarDays size={11} className="text-[#0058CC] shrink-0" />}
                        <span className="truncate">{h.kind === "ot" ? `Lembur ${h.hours} jam · ${formatDate(h.date)}` : `${LEAVE_TYPE_LABEL[h.leave_type] || h.leave_type} · ${formatDate(h.date_from)}`}</span></span>
                      <span className={`status-pill ${s.cls}`}>{s.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* UAT 24 Okt (audit UI tahap 2) — G5-30: pop-up standar FormModal (×, deskripsi, kaki terpisah, penanda
          wajib) seperti versi admin; dulu `.modal-card` polos. */}
      <FormModal open={open} onClose={() => { if (!busy) setOpen(false); }} title="Ajukan Cuti / Lembur"
        subtitle="Diajukan atas nama Anda; menunggu persetujuan atasan/HRD." icon={CalendarDays} size="sm"
        testId="ess-leave-modal" busy={busy} error={err}
        footer={(
          <div className="flex items-center justify-end gap-2">
            <button type="button" className="secondary-button" onClick={() => setOpen(false)} disabled={busy}>Batal</button>
            {tab === "cuti"
              ? <button type="button" data-testid="ess-leave-submit" className="primary-button" onClick={submitLeave} disabled={busy}>{busy ? "Mengirim…" : "Ajukan Cuti"}</button>
              : <button type="button" data-testid="ess-ot-submit" className="primary-button" onClick={submitOt} disabled={busy}>{busy ? "Mengirim…" : "Ajukan Lembur"}</button>}
          </div>
        )}>
            <PageTabs testId="ess-leave-modal-tabs" value={tab} onChange={(t) => { setTab(t); setErr(""); }} ariaLabel="Jenis pengajuan"
              tabs={[{ key: "cuti", label: "Cuti / Izin", testId: "ess-leave-modal-tab-cuti" }, { key: "lembur", label: "Lembur", testId: "ess-leave-modal-tab-lembur" }]} />
            {msg && <div className="notice-bar success !mb-2 !py-1.5" data-testid="ess-leave-modal-msg"><span className="text-[11.5px]">{msg}</span></div>}

            {tab === "cuti" ? (
              <LeaveRequestFields type={type} from={from} to={to} reason={reason} testPrefix="ess-leave"
                onChange={(k, v) => ({ type: setType, from: setFrom, to: setTo, reason: setReason })[k](v)} />
            ) : (
              <div className="grid gap-2.5">
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="grid gap-1"><label className="field-label">Tanggal <span className="req">*</span></label>
                    <KNDatePicker data-testid="ess-ot-date" value={otDate} onChange={setOtDate} /></div>
                  <div className="grid gap-1"><label className="field-label">Jam (maks 12) <span className="req">*</span></label>
                    <input data-testid="ess-ot-hours" type="number" step="0.5" min="0" max="12" className="form-input" value={otHours} onChange={(e) => setOtHours(e.target.value)} /></div>
                </div>
                <div className="grid gap-1"><label className="field-label">Alasan (opsional)</label>
                  <textarea data-testid="ess-ot-reason" className="form-input" rows="2" value={otReason} onChange={(e) => setOtReason(e.target.value)} placeholder="mis. menyelesaikan stok opname" /></div>
              </div>
            )}
      </FormModal>
    </div>
  );
}
