/**
 * PeriodUnlockView (FINANCE · FASE G-5) — Buka Periode Berotoritas (Unlock).
 *
 * Alur resmi membuka periode TERTUTUP untuk koreksi/posting MUNDUR:
 *   usul (alasan wajib) → setujui (pengusul ≠ penyetuju — KONTROL GANDA)
 *     → jendela berbatas waktu (config periode.unlock_window_hours, bawaan 24 jam)
 *       → jurnal yang lahir di jendela ditandai backdated_in_unlock
 *         → lewat batas = tertutup sendiri (auto-reclose).
 * Sumber: /api/finance/period-unlocks/* & /api/finance/closing. Gaya modul Closing.
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Unlock, Lock, ShieldCheck, ShieldAlert, Clock, Building2,
  CheckCircle2, XCircle, AlertTriangle, History, Timer, FileStack,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import useListSearch from "@/hooks/useListSearch";
import KNSelect from "../../components/KNSelect";
import { askConfirm, askReason } from "@/services/confirmService";
import { can } from "../../config/roles";
import EntityRequiredNotice from "../../components/EntityRequiredNotice";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import { MetricRow } from "../../components/ListPageParts";

function fmtDateTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("id-ID", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function fmtCountdown(secs) {
  if (!secs || secs <= 0) return "berakhir";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (h >= 1) return `${h}j ${m}m lagi`;
  const s = secs % 60;
  return `${m}m ${s}d lagi`;
}

const STATUS_BADGE = {
  pending: { label: "Menunggu Persetujuan", cls: "bg-[#FDF3E7] text-[#B26B00]", icon: Clock },
  approved: { label: "Terbuka (Aktif)", cls: "bg-[#E6F6EC] text-[#1B7F4B]", icon: ShieldCheck },
  reclosed: { label: "Terkunci Lagi", cls: "bg-[#F3EAFB] text-[#6B219A]", icon: Lock },
  expired: { label: "Kedaluwarsa", cls: "bg-[#EFF0F2] text-[#6B6B73]", icon: Timer },
  rejected: { label: "Ditolak", cls: "bg-[#FDEDE7] text-[#C0392B]", icon: XCircle },
};

export default function PeriodUnlockView({ selectedEntity, entities = [], currentUser }) {
  const canManage = can(currentUser?.permissions, "period", "unlock");   // Sisir gerbang peran (2026-10-20) — semua aksi buka periode = period.unlock
  const entityOptions = useMemo(
    () => entities.filter((e) => !e.is_group).map((e) => ({ value: e.id, label: e.short_name || e.legal_name || e.id })),
    [entities]);

  // Fase 3 · P4 (D-14) — PT diambil dari pemilih di HEADER (satu sumber); pemilih lokal `plu-entity-select` dihapus.
  // Header "Semua badan usaha" → EntityRequiredNotice (memilih PT = mengganti header). Akun satu-PT tidak terpengaruh.
  const entityId = useMemo(() => {
    if (selectedEntity && selectedEntity !== "all") return selectedEntity;
    return entityOptions.length === 1 ? entityOptions[0].value : "";
  }, [selectedEntity, entityOptions]);
  const entityLabel = entityOptions.find((e) => e.value === entityId)?.label || entityId;

  const [closings, setClosings] = useState([]);
  const [requests, setRequests] = useState([]);
  const srch = useListSearch(requests, null, { testId: "plu", placeholder: "Cari periode / alasan / pengusul…" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);

  const [selPeriod, setSelPeriod] = useState("");   // "type:key"
  const [reason, setReason] = useState("");

  // Detak per detik untuk countdown jendela aktif.
  useEffect(() => {
    const t = setInterval(() => setTick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const load = useCallback(async () => {
    if (!entityId) { setClosings([]); setRequests([]); setLoading(false); return; }
    setLoading(true); setError("");
    try {
      const [cRes, rRes] = await Promise.all([
        axios.get(`${API}/finance/closing`, { params: { entity_id: entityId } }),
        axios.get(`${API}/finance/period-unlocks`, { params: { entity_id: entityId } }),
      ]);
      setClosings(Array.isArray(cRes.data) ? cRes.data : []);
      setRequests(Array.isArray(rRes.data) ? rRes.data : []);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data buka periode."));
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  useEffect(() => { load(); }, [load]);

  // Periode TERTUTUP yang belum punya usul hidup (pending/approved) → bisa diusulkan.
  const livePeriods = useMemo(() => new Set(
    requests.filter((r) => ["pending", "approved"].includes(r.status)).map((r) => `${r.period_type}:${r.period_key}`)
  ), [requests]);

  const closedOptions = useMemo(() => closings
    .filter((c) => c.status === "closed")
    .map((c) => ({ value: `${c.period_type}:${c.period_key}`, label: `${c.period_label}${livePeriods.has(`${c.period_type}:${c.period_key}`) ? " · (ada usul aktif)" : ""}` })),
    [closings, livePeriods]);

  const activeCount = requests.filter((r) => r.is_active_now).length;
  // G1-16 — jendela disetujui yang batas waktunya sudah lewat (yang akan ditutup tombol "Tutup yang kedaluwarsa").
  const expiredOpenCount = requests.filter((r) => r.status === "approved" && !r.is_active_now).length;
  const pendingCount = requests.filter((r) => r.status === "pending").length;

  const doRequest = async () => {
    if (!selPeriod) { setError("Pilih periode tertutup yang ingin dibuka."); return; }
    if (!reason.trim()) { setError("Alasan membuka periode WAJIB diisi."); return; }
    const [period_type, period_key] = selPeriod.split(":");
    setError(""); setNotice(""); setBusy(true);
    try {
      await axios.post(`${API}/finance/period-unlocks`, { period_type, period_key, entity_id: entityId, reason: reason.trim() });
      setNotice("Usul buka periode dikirim. Perlu disetujui admin/manager LAIN (kontrol ganda) agar jendela terbuka.");
      setReason(""); setSelPeriod("");
      load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal mengirim usul buka periode."));
    } finally { setBusy(false); }
  };

  const doApprove = async (r) => {
    setError(""); setNotice(""); setBusy(true);
    try {
      const res = await axios.post(`${API}/finance/period-unlocks/${r.id}/approve`);
      setNotice(`Periode ${res.data.period_label} DIBUKA hingga ${fmtDateTime(res.data.window_until)} (${res.data.window_hours} jam). Posting mundur kini diizinkan sementara.`);
      load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal menyetujui usul."));
    } finally { setBusy(false); }
  };

  const doReject = async (r) => {
    // FASE P5 — dulu `window.prompt`: alasan opsional, tapi tak bisa diberi konteks apa pun.
    const rsn = await askReason({
      title: "Tolak usul buka periode?",
      message: "Periode tetap tertutup; pengusul melihat alasan Anda pada daftar usulnya.",
      reasonLabel: "Alasan menolak (opsional)",
      reasonRequired: false,
      confirmLabel: "Tolak Usul",
      danger: true,
      testId: "period-reject-confirm",
    });
    if (rsn === null) return;
    setError(""); setNotice(""); setBusy(true);
    try {
      await axios.post(`${API}/finance/period-unlocks/${r.id}/reject`, { reason: rsn });
      setNotice("Usul buka periode ditolak.");
      load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal menolak usul."));
    } finally { setBusy(false); }
  };

  const doReclose = async () => {
    if (!(await askConfirm({
      danger: true,
      title: `Tutup ${expiredOpenCount} jendela buka periode yang kedaluwarsa?`,
      message: "Periode yang dibuka sementara dikunci kembali; jurnal baru pada periode itu akan ditolak.",
      confirmLabel: "Tutup Jendela",
    }))) return;
    setError(""); setNotice(""); setBusy(true);
    try {
      const res = await axios.post(`${API}/finance/period-unlocks/reclose-expired`);
      setNotice(res.data.reclosed ? `${res.data.reclosed} jendela unlock yang lewat batas ditutup.` : "Tidak ada jendela yang perlu ditutup.");
      load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal menutup jendela kedaluwarsa."));
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="period-unlock-view">
      <DesktopOnlyNotice testId="plu-desktop-notice" what="Buka Periode" />
      {/* KPI ringkas — Fase 3 · P4 (L-08): MetricRow baku (nol netral). */}
      <div className="mb-3">
        <MetricRow testId="plu-kpi" items={[
          { label: "Jendela Aktif", value: activeCount, icon: Unlock, tone: "#1B7F4B", testId: "plu-kpi-active" },
          { label: "Menunggu Persetujuan", value: pendingCount, icon: Clock, tone: "#B26B00", testId: "plu-kpi-pending" },
          { label: "Periode Tertutup", value: closedOptions.length, icon: Lock, testId: "plu-kpi-closed" },
          { label: "Total Riwayat", value: requests.length, icon: FileStack, testId: "plu-kpi-total" },
        ]} />
      </div>

      <div className="section-card">
        {/* Audit UI 24 Okt (134 HP): kepala kartu dulu satu baris kaku → judul pecah satu kata
            per baris & pemilih entitas terpotong. Sekarang boleh membungkus. */}
        <div className="section-head flex-wrap gap-2">
          <div className="flex min-w-[200px] flex-1 items-center gap-2">
            <ShieldCheck size={15} className="flex-shrink-0 text-[#6B219A]" />
            <h3 className="text-[13px] font-bold text-[#1C1C1E]">Buka Periode — Kontrol Ganda</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2 ml-auto">
            <button data-testid="plu-reclose-expired" className="btn-secondary text-[11px] py-1 px-2 inline-flex items-center gap-1" onClick={doReclose} disabled={busy || !canManage || expiredOpenCount === 0} title={expiredOpenCount === 0 ? "Tidak ada jendela yang lewat batas" : "Tutup jendela yang sudah lewat batas"}>
              <Timer size={12} /> Tutup yang kedaluwarsa
            </button>
            {entityId && (
              <span className="inline-flex items-center gap-1 text-[11.5px] text-[#6B6B73]" data-testid="plu-entity-label"
                title="Badan usaha mengikuti pilihan di kepala aplikasi">
                <Building2 size={12} aria-hidden="true" /> <b className="text-[#1C1C1E]">{entityLabel}</b>
              </span>
            )}
            <button data-testid="plu-refresh" className="icon-button" onClick={load} aria-label="Muat ulang" title="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>

        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="plu-error" />
          {notice && (
            <div data-testid="plu-notice" className="mb-3 rounded-md bg-[#E6F6EC] border border-[#BDE5CC] text-[#1B7F4B] text-[12px] px-3 py-2 flex items-center gap-2">
              <CheckCircle2 size={14} />{notice}
              <button className="ml-auto" onClick={() => setNotice("")} aria-label="Tutup">✕</button>
            </div>
          )}

          {/* Penjelasan aturan */}
          <div className="mb-4 rounded-md bg-[#FBF4FF] border border-[#E3CCF3] text-[#6B219A] text-[11px] px-3 py-2 flex items-start gap-2" data-testid="plu-rule-note">
            <ShieldAlert size={14} className="mt-0.5 shrink-0" />
            <span>
              Periode yang sudah <b>ditutup terkunci penuh</b> — jurnal/koreksi mundur <b>ditolak</b> kecuali ada jendela unlock aktif.
              Membuka periode <b>wajib dua orang</b> (pengusul ≠ penyetuju) dan otomatis <b>tertutup kembali</b> saat jendela waktunya habis.
            </span>
          </div>

          {!entityId ? (
            <div data-testid="plu-no-entity">
              <EntityRequiredNotice when what="buka periode" testId="plu-entity-required" />
            </div>
          ) : (
            <>
              {/* Form usul */}
              <div className="rounded-lg border border-[#EFF0F2] p-3 mb-4 bg-[#FCFCFD]">
                <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93] mb-2">Ajukan Buka Periode</p>
                {closedOptions.length === 0 ? (
                  <p className="text-[12px] text-[#9A9BA3]" data-testid="plu-no-closed">Belum ada periode tertutup pada entitas ini. Tutup buku dulu di menu <b>Tutup Buku (Closing)</b>.</p>
                ) : (
                  <div className="flex flex-wrap items-end gap-3">
                    <Labeled label="Periode Tertutup">
                      <div className="w-[240px]">
                        <KNSelect data-testid="plu-period-select" className="field py-1.5 text-[12px]" value={selPeriod}
                          onValueChange={setSelPeriod} placeholder="Pilih periode…" options={closedOptions} />
                      </div>
                    </Labeled>
                    <Labeled label="Alasan (wajib)">
                      <input data-testid="plu-reason-input" value={reason} onChange={(e) => setReason(e.target.value)}
                        placeholder="mis. koreksi salah posting akun beban"
                        className="field py-1.5 text-[12px] w-[320px]" />
                    </Labeled>
                    <button data-testid="plu-request-btn" onClick={doRequest} disabled={busy || !canManage}
                      className="btn-primary text-[12px] py-1.5 px-4 inline-flex items-center gap-1">
                      <Unlock size={13} /> Ajukan Usul
                    </button>
                  </div>
                )}
                {!canManage && <p className="mt-2 text-[11px] text-[#C0392B]">Mengusulkan & menyetujui buka periode butuh izin buka periode (period.unlock).</p>}
              </div>

              {/* Riwayat usul */}
              <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93] mb-2 flex items-center gap-1"><History size={12} /> Riwayat & Antrean Usul</p>
              {srch.toolbar}
              {loading ? (
                <div className="grid gap-2" data-testid="plu-loading">{[0, 1, 2].map((i) => <div key={i} className="h-10 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
              ) : srch.shown.length === 0 ? (
                <div data-testid="plu-empty" className="py-10 text-center text-[12px] text-[#8E8E93]">
                  <Unlock size={26} className="mx-auto mb-2 text-gray-300" />Belum ada usul buka periode untuk entitas ini.
                </div>
              ) : (
                <div className="overflow-auto rounded-md border border-[#EFF0F2]">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                        <th className="px-3 py-2">Periode</th>
                        <th className="px-3 py-2">Alasan</th>
                        <th className="px-3 py-2 text-center">Status</th>
                        <th className="px-3 py-2">Pengusul</th>
                        <th className="px-3 py-2">Penyetuju</th>
                        <th className="px-3 py-2 text-center">Jendela</th>
                        <th className="px-3 py-2 text-center">JE Mundur</th>
                        <th className="px-3 py-2 text-right">Aksi</th>
                      </tr>
                    </thead>
                    <tbody>
                      {srch.pageRows.map((r) => {
                        const badge = STATUS_BADGE[r.status] || STATUS_BADGE.pending;
                        const BadgeIcon = badge.icon;
                        const isRequester = currentUser?.id && currentUser.id === r.requested_by_id;
                        const secsLeft = r.window_seconds_left || 0;
                        return (
                          <tr key={r.id} data-testid={`plu-row-${r.id}`} className="border-b border-[#F5F5F7] last:border-0 align-top">
                            <td className="px-3 py-2 font-semibold text-[#1C1C1E] whitespace-nowrap">{r.period_label}</td>
                            <td className="px-3 py-2 text-[#6B6B73] max-w-[220px]"><span className="line-clamp-2">{r.reason}</span>
                              {r.status === "rejected" && r.reject_reason && <span className="block text-[10px] text-[#C0392B] mt-0.5">Ditolak: {r.reject_reason}</span>}
                            </td>
                            <td className="px-3 py-2 text-center">
                              <span className={`text-[10px] font-bold rounded-full px-2 py-0.5 inline-flex items-center gap-1 ${badge.cls}`}><BadgeIcon size={10} /> {badge.label}</span>
                            </td>
                            <td className="px-3 py-2 text-[11px] text-[#6B6B73]">{r.requested_by}<br /><span className="text-[10px] text-[#9A9BA3]">{fmtDateTime(r.requested_at)}</span></td>
                            <td className="px-3 py-2 text-[11px] text-[#6B6B73]">{r.approved_by || "—"}{r.approved_at && <><br /><span className="text-[10px] text-[#9A9BA3]">{fmtDateTime(r.approved_at)}</span></>}</td>
                            <td className="px-3 py-2 text-center text-[11px]">
                              {r.is_active_now
                                ? <span data-testid={`plu-countdown-${r.id}`} className="font-bold text-[#1B7F4B] inline-flex items-center gap-1"><Clock size={11} /> {fmtCountdown(secsLeft)}</span>
                                : r.window_until ? <span className="text-[#9A9BA3]">s.d. {fmtDateTime(r.window_until)}</span> : "—"}
                            </td>
                            <td className="px-3 py-2 text-center tabular-nums text-[#6B6B73]">{(r.je_ids || []).length || "—"}</td>
                            <td className="px-3 py-2 text-right whitespace-nowrap">
                              {r.status === "pending" && canManage ? (
                                <div className="inline-flex items-center gap-1 justify-end">
                                  <button data-testid={`plu-approve-${r.id}`} onClick={() => doApprove(r)} disabled={busy || isRequester}
                                    title={isRequester ? "Kontrol ganda: pengusul tidak boleh menyetujui usulnya sendiri" : "Setujui"}
                                    className={`btn-secondary text-[11px] py-1 px-2 inline-flex items-center gap-1 ${isRequester ? "opacity-40 cursor-not-allowed" : "text-[#1B7F4B]"}`}>
                                    <CheckCircle2 size={12} /> Setujui
                                  </button>
                                  <button data-testid={`plu-reject-${r.id}`} onClick={() => doReject(r)} disabled={busy}
                                    className="btn-secondary text-[11px] py-1 px-2 inline-flex items-center gap-1 text-[#C0392B]">
                                    <XCircle size={12} /> Tolak
                                  </button>
                                </div>
                              ) : <span className="text-[10px] text-[#C9C9CE]">—</span>}
                              {r.status === "pending" && isRequester && (
                                <div className="text-[9px] text-[#B26B00] mt-0.5 flex items-center gap-1 justify-end"><AlertTriangle size={9} /> perlu orang lain</div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="mt-2 text-[11px] text-[#9A9BA3]">Jurnal mundur yang diposting selama jendela terbuka membuat penutupan periode <b>kedaluwarsa (perlu ditutup ulang)</b> — tutup ulang di menu Tutup Buku agar laporan sinkron kembali.</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Labeled({ label, children }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</span>
      {children}
    </div>
  );
}
