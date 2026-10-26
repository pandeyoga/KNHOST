/**
 * DesignerKpiView (PS-18) — layar utama menu **Desainer › KPI Desainer**.
 *
 * Menjawab tiga pertanyaan pemilik tanpa satu pun angka diisi tangan:
 *   1. Desainer mana yang paling bisa diandalkan? (nilai komposit + peringkat)
 *   2. Siapa yang sering terlambat atau sering diulang kerjanya? (tepat waktu / diulang)
 *   3. Pekerjaan mana yang SEKARANG menggantung lewat tenggat, dan sudah dinaikkan
 *      ke siapa? (papan eskalasi aktif — bukan sekadar tanda merah)
 *
 * Menu ini SENGAJA dipisah dari menu R&D (keputusan pemilik): R&D mengurus
 * spesifikasi & permintaan sample, Desainer mengurus orang & karyanya.
 *
 * Fase 3 · P6 (D-08, keputusan pemilik 26 Okt) — SATU tempat menilai tim: PageTabs **Skor & SLA** (isi lama)
 * | **Pekerjaan DSR** (`DesignerReportPanel`, dulu tab "Rapor Desainer" di Permintaan Desain). Tautan
 * "Rapor desainer" di Permintaan Desain membuka layar ini dengan preset `{ tab: "dsr" }`. Angka milik
 * sendiri (desainer) ada di Profil Saya › KPI Saya.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Award, BarChart3, Download, FileSpreadsheet, FileText, Info, RefreshCw, Settings2, Users } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import LineFilter from "../../components/LineFilter";
import PageTabs from "../../components/PageTabs";
import useViewPreset from "../../hooks/useViewPreset";
import DesignerReportPanel from "../design/DesignerReportPanel";
import { formatCurrency } from "../../utils/formatters";
import { askConfirm } from "../../services/confirmService";
import { openConfig } from "../settings/config/configDeepLink";
import { errMsg } from "../rnd/rndMeta";
import DesignerKpiTable from "./DesignerKpiTable";
import DesignerKpiTrendChart from "./DesignerKpiTrendChart";
import DesignScoreTrendChart from "./DesignScoreTrendChart";
import DesignerSlaPanel from "./DesignerSlaPanel";
import { designerKpi, downloadDesignerKpi, downloadDesignerReport, runSlaEscalation, saveBlob, slaBoard } from "./designerApi";
import { gradeFormula, gradeMeta, num, PERIOD_OPTIONS } from "./designerMeta";
import { roleIs } from "../../config/roles";
import { actorLabel, isTechActor } from "../../utils/actorLabel";

const TABS = [
  { key: "score", label: "Skor & SLA", testId: "designer-kpi-tab-score" },
  { key: "dsr", label: "Pekerjaan DSR", testId: "designer-kpi-tab-dsr" },
];
const tabOf = (p) => (TABS.some((t) => t.key === p?.tab) ? p.tab : null);

export default function DesignerKpiView({ currentUser, selectedEntity }) {
  const preset = useViewPreset("designer-kpi", (p) => { const t = tabOf(p); if (t) setTab(t); });
  const [tab, setTab] = useState(() => tabOf(preset) || "score");
  const [dsrLine, setDsrLine] = useState("");
  const [dsrSearch, setDsrSearch] = useState("");
  const [period, setPeriod] = useState("30d");
  const [report, setReport] = useState(null);
  const [board, setBoard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [runInfo, setRunInfo] = useState(null);
  const [focusDesigner, setFocusDesigner] = useState("");
  const [division, setDivision] = useState(""); // "" = semua divisi (PS-17)
  const [showHow, setShowHow] = useState(false);
  const [exporting, setExporting] = useState("");
  const [exportMsg, setExportMsg] = useState(null);
  const [reportBusy, setReportBusy] = useState("");
  const [reportModal, setReportModal] = useState(null); // {designer, note} | null

  const canManage = roleIs(currentUser?.role, ["admin", "manager"]);

  const params = useMemo(() => {
    const p = {};
    if (selectedEntity && selectedEntity !== "all") p.entity_id = selectedEntity;
    return p;
  }, [selectedEntity]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [rep, brd] = await Promise.all([
        designerKpi({ ...params, period, division }),
        slaBoard(params).catch(() => null),
      ]);
      setReport(rep || null);
      setBoard(brd || null);
      setError("");
    } catch (e) {
      setError(errMsg(e, "Gagal memuat KPI desainer."));
    } finally {
      setLoading(false);
    }
  }, [params, period, division]);

  useEffect(() => { load(); }, [load]);

  /** Unduh laporan untuk rapat bulanan (CSV / Excel / PDF) — angka sama dengan layar. */
  async function download(format) {
    setExporting(format);
    setExportMsg(null);
    try {
      const res = await downloadDesignerKpi({ ...params, period, format });
      const disp = String(res.headers?.["content-disposition"] || "");
      const match = disp.match(/filename=([^;]+)/i);
      const name = (match ? match[1] : `kpi-desainer-${period}.${format}`).trim();
      saveBlob(res.data, name);
      setExportMsg({ ok: true, message: `Berkas ${name} berhasil diunduh.` });
    } catch (e) {
      setExportMsg({ ok: false, message: errMsg(e, "Gagal mengunduh laporan KPI.") });
    } finally { setExporting(""); }
  }

  /** Unduh RAPOR 1 halaman (PDF) untuk SATU desainer — dengan catatan evaluasi opsional. */
  async function downloadReport(designer, note = "") {
    setReportBusy(designer);
    setExportMsg(null);
    try {
      const res = await downloadDesignerReport({ ...params, period, designer, note });
      const disp = String(res.headers?.["content-disposition"] || "");
      const match = disp.match(/filename=([^;]+)/i);
      const name = (match ? match[1] : `rapor-${designer}.pdf`).trim();
      saveBlob(res.data, name);
      setExportMsg({ ok: true, message: `Rapor ${designer} berhasil diunduh (${name}).` });
      setReportModal(null);
    } catch (e) {
      setExportMsg({ ok: false, message: errMsg(e, `Gagal mengunduh rapor ${designer}.`) });
    } finally { setReportBusy(""); }
  }

  async function escalateNow() {
    // UAT 24 Okt (audit UI tahap 2) — G5-38: "Kirim peringatan sekarang" mengirim notifikasi/WA ke manajer →
    // minta konfirmasi dulu (dulu langsung jalan).
    const ok = await askConfirm({
      title: "Kirim peringatan SLA sekarang?",
      message: "Peringatan untuk ronde sample yang lewat tenggat dikirim ke manajer (dan admin bila sudah lama). Satu ronde hanya diperingatkan sekali per hari.",
      confirmLabel: "Kirim peringatan",
    });
    if (!ok) return;
    setBusy(true);
    setRunInfo(null);
    try {
      const run = await runSlaEscalation();
      const created = Number(run?.created || 0);
      setRunInfo({
        ok: run?.status === "success",
        message: run?.status === "success"
          ? (created > 0
            ? `${created} peringatan terkirim — ${run?.detail || ""}`
            : `Tidak ada peringatan baru: ${run?.detail || "semua sudah dikirim hari ini"}. `
              + "Satu ronde hanya diperingatkan sekali per hari.")
          : `Gagal menjalankan eskalasi: ${run?.error || "tidak diketahui"}`,
      });
      await load();
    } catch (e) {
      setRunInfo({ ok: false, message: errMsg(e, "Gagal menjalankan eskalasi SLA.") });
    } finally {
      setBusy(false);
    }
  }

  // Audit UI 24 Okt (048) — akun teknis (system-seed) bukan desainer: tidak diperingkat & tidak dihitung
  // "Desainer aktif". Peringkat dinomori ulang mengikuti urutan nilai komposit dari server.
  const items = (report?.items || []).filter((r) => !isTechActor(r.designer)).map((r, i) => ({ ...r, rank: i + 1 }));
  const techCount = (report?.items || []).length - items.length;
  const sum = report?.summary || {};
  const w = report?.weights || null;
  const bands = report?.grade_bands || [];
  const periodOpts = (report?.period_options?.length ? report.period_options
    : PERIOD_OPTIONS);
  const divisionOpts = [{ value: "", label: "Semua divisi" },
    ...((report?.divisions_present || []).map((d) => ({ value: d.id, label: d.name })))];
  // "Terbaik" hanya dari desainer yang punya bukti kerja pada periode ini (ronde sample atau versi desain).
  const best = items.find((r) => r.grade_score !== null && r.grade_score !== undefined
    && (Number(r.rounds || 0) > 0 || Number(r.design_versions || 0) > 0)) || null;

  return (
    <div className="grid gap-3" data-testid="designer-kpi-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")}
        testId="designer-kpi-error" />

      {/* ── Toolbar + ringkasan ─────────────────────────────────────────── */}
      <section className="section-card">
        <div className="section-head flex-wrap">
          <div className="flex items-center gap-2">
            <BarChart3 size={16} className="text-[#0058CC]" />
            <h2 data-testid="designer-kpi-title">KPI Desainer</h2>
          </div>
          {tab === "dsr" ? (
            <div className="flex flex-wrap items-center gap-2" data-testid="designer-kpi-dsr-toolbar">
              <LineFilter value={dsrLine} onChange={setDsrLine} storageKey="designer-kpi-dsr"
                allowed={currentUser?.allowed_line_codes} className="!py-1.5" testId="designer-kpi-dsr-line" />
              <input data-testid="designer-kpi-dsr-search" className="field !py-1.5 !text-[11.5px] w-full sm:w-52"
                placeholder="Cari nama desainer…" value={dsrSearch} onChange={(e) => setDsrSearch(e.target.value)} />
            </div>
          ) : (
          <div className="flex flex-wrap items-center gap-2">
            {/* G5-38: saringan divisi hanya tampil bila ada divisi (dulu "Semua divisi" sendirian). */}
            {divisionOpts.length > 1 && (
              <KNSelect data-testid="designer-kpi-division" value={division}
                onValueChange={setDivision} options={divisionOpts} className="field !w-[160px]" />
            )}
            <KNSelect data-testid="designer-kpi-period" value={period}
              onValueChange={setPeriod} options={periodOpts} className="field !w-[170px]" />
            <button className="secondary-button" onClick={load}
              data-testid="designer-kpi-refresh">
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat ulang
            </button>
            <button className="secondary-button" onClick={() => setShowHow((v) => !v)}
              data-testid="designer-kpi-how-toggle">
              <Info size={13} /> Cara nilai dihitung
            </button>
            <button className="secondary-button" onClick={() => download("xlsx")}
              disabled={Boolean(exporting)} data-testid="designer-kpi-export-xlsx"
              title="Unduh sebagai Excel (bisa diolah lagi)">
              <FileSpreadsheet size={13} className={exporting === "xlsx" ? "animate-pulse" : ""} />
              {exporting === "xlsx" ? "Menyiapkan…" : "Excel"}
            </button>
            <button className="secondary-button" onClick={() => download("pdf")}
              disabled={Boolean(exporting)} data-testid="designer-kpi-export-pdf"
              title="Unduh sebagai PDF siap cetak untuk rapat">
              <FileText size={13} className={exporting === "pdf" ? "animate-pulse" : ""} />
              {exporting === "pdf" ? "Menyiapkan…" : "PDF"}
            </button>
            <button className="secondary-button" onClick={() => download("csv")}
              disabled={Boolean(exporting)} data-testid="designer-kpi-export-csv"
              title="Unduh sebagai CSV">
              <Download size={13} className={exporting === "csv" ? "animate-pulse" : ""} /> CSV
            </button>
            {canManage && (
              <button className="secondary-button" data-testid="designer-kpi-policy-button"
                onClick={() => openConfig({ group: "rnd", key: "rnd.kpi_weight" })}
                title="Membuka keempat bobot sekaligus beserta jumlahnya (porsi dari 100%)">
                <Settings2 size={13} /> Ubah bobot nilai
              </button>
            )}
          </div>
          )}
        </div>
        <PageTabs testId="designer-kpi-tabs" value={tab} onChange={setTab} tabs={TABS} ariaLabel="KPI Desainer" className="!mb-0 px-3" />
        {tab === "score" && (
        <div className="section-body space-y-2">
          {exportMsg && (
            <div className={`notice-bar ${exportMsg.ok ? "success" : "danger"} !mb-0 !py-1.5`}
              data-testid="designer-kpi-export-result">
              <span className="text-[11.5px]">{exportMsg.message}</span>
              <button onClick={() => setExportMsg(null)}
                data-testid="designer-kpi-export-dismiss">Tutup</button>
            </div>
          )}
          <p className="text-[11.5px] text-[#6B6B73]" data-testid="designer-kpi-period-note">
            Periode: <b>{report?.period_label || "—"}</b>
            {report?.from_date ? ` (${report.from_date} s/d ${report.to_date})` : ""}
            {" · "}angka terbentuk sendiri dari ronde sample yang disetor beserta buktinya —
            tidak ada input manual.
          </p>

          {loading && !report ? (
            <p className="py-8 text-center text-[12px] text-[#6B6B73]"
              data-testid="designer-kpi-loading">Memuat KPI desainer…</p>
          ) : (
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-8"
              data-testid="designer-kpi-summary">
              <Kpi label="Desainer aktif" testId="designer-kpi-summary-designers"
                value={String(Math.max(0, (sum.designers ?? 0) - techCount))} />
              <Kpi label="Ronde dikerjakan" value={String(sum.rounds ?? 0)} tone="#0058CC" />
              <Kpi label="Tepat waktu" value={num(sum.on_time_pct, "%")}
                tone={(sum.on_time_pct ?? 0) >= 80 ? "#1B7F4B" : "#B26A00"} />
              <Kpi label="Kerja diulang" value={num(sum.rework_pct, "%")}
                tone={(sum.rework_pct ?? 0) <= 30 ? "#1B7F4B" : "#C0392B"} />
              <Kpi label="Nunggak lewat tenggat" value={String(sum.overdue_now ?? 0)}
                tone={(sum.overdue_now ?? 0) > 0 ? "#C0392B" : "#1B7F4B"} />
              <Kpi label="Biaya sample" value={formatCurrency(sum.cost_total || 0)} />
              <Kpi label="Nilai desain rata (0–2)" testId="designer-kpi-summary-design-score"
                value={sum.design_avg_score === null || sum.design_avg_score === undefined ? "—"
                  : `${String(sum.design_avg_score).replace(".", ",")} · ${sum.design_versions ?? 0} versi`}
                tone={(sum.design_avg_score ?? 0) >= 1.5 ? "#1B7F4B" : "#B26A00"} />
              <Kpi label="Revisi desain / ACC" testId="designer-kpi-summary-design-revisions"
                value={`${sum.design_revisions ?? 0} / ${sum.design_acc ?? 0}`}
                tone={(sum.design_revisions ?? 0) > (sum.design_acc ?? 0) ? "#C0392B" : "#1B7F4B"} />
            </div>
          )}

          {showHow && w && (
            <div className="rounded-lg border border-[#DCE7FF] bg-[#F5F9FF] p-2.5"
              data-testid="designer-kpi-how">
              <p className="mb-1 text-[11px] font-bold uppercase text-[#0058CC]">
                Cara nilai (grade) dihitung
              </p>
              <p className="text-[11.5px] leading-relaxed text-[#3C3C43]">
                {gradeFormula(w)}
              </p>
              <p className="mt-1 text-[11.5px] leading-relaxed text-[#6B6B73]">
                Bila satu komponen belum punya data (mis. belum ada ronde yang dinilai),
                bobotnya tidak dihitung nol — bobot sisanya disesuaikan, supaya desainer
                baru tidak langsung jatuh ke nilai terendah.
              </p>
              {canManage && (
                <button type="button" className="mt-1 text-[11.5px] font-semibold text-[#0058CC] hover:underline"
                  data-testid="designer-kpi-design-weight-link"
                  onClick={() => openConfig({ group: "rnd", key: "rnd.kpi_weight_design" })}>
                  Ubah bobot nilai desain (setelan {w.design ?? 0}) →
                </button>
              )}
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {bands.map((b) => {
                  const g = gradeMeta(b.letter);
                  return (
                    <span key={b.letter} className={`status-pill ${g.cls}`}
                      data-testid={`designer-kpi-band-${b.letter}`}>
                      {b.letter} · {b.min}+ · {b.meaning}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
        )}
      </section>

      {tab === "dsr" ? (
        <DesignerReportPanel selectedEntity={selectedEntity} line={dsrLine} search={dsrSearch} />
      ) : (
      <>
      {/* ── Tren per bulan: skor round sample (kiri) · nilai desain (kanan) ── */}
      <div className="grid gap-3 xl:grid-cols-2 [&>section]:min-w-0" data-testid="designer-kpi-trend-row">
        <DesignerKpiTrendChart params={params} testId="designer-kpi-trend" />
        <DesignScoreTrendChart params={params} testId="design-score-trend" />
      </div>

      {/* ── Desainer terbaik + tabel ────────────────────────────────────── */}
      <section className="section-card">
        <div className="section-head flex-wrap">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-[#0058CC]" />
            <h2>Peringkat kinerja desainer</h2>
          </div>
          {best && (
            <span className="flex flex-wrap items-center gap-1.5 text-[11.5px]"
              data-testid="designer-kpi-best">
              <Award size={13} className="text-[#B8860B]" />
              Terbaik periode ini: <b>{actorLabel(best.designer)}</b>
              <span className={`status-pill ${gradeMeta(best.grade_letter).cls}`}>
                {best.grade_letter} · {num(best.grade_score)}
              </span>
              <span className="text-[11px] text-[#6B6B73]" data-testid="designer-kpi-best-basis">
                dasar: {Number(best.rounds || 0)} ronde sample · {Number(best.design_versions || 0)} versi desain
              </span>
            </span>
          )}
        </div>
        <div className="section-body">
          {loading && !report ? (
            <p className="py-8 text-center text-[12px] text-[#6B6B73]"
              data-testid="designer-kpi-table-loading">Memuat tabel…</p>
          ) : (
            <>
              <DesignerKpiTable items={items} selected={focusDesigner}
                loading={loading && !report} onSelect={setFocusDesigner}
                onDownloadReport={(designer) => {
                  setExportMsg(null);
                  setReportModal({ designer, note: "" });
                }}
                downloadingReport={reportBusy} />
              {focusDesigner && (
                <p className="mt-2 text-[11px] text-[#0058CC]"
                  data-testid="designer-kpi-filter-note">
                  Papan eskalasi di bawah disaring untuk <b>{focusDesigner}</b> —
                  klik baris yang sama sekali lagi untuk melihat semuanya.
                </p>
              )}
              <p className="mt-2 text-[10.5px] leading-relaxed text-[#9A9BA3]">
                Penanggung jawab ronde = yang menyetor hasilnya; bila ronde masih berjalan
                dipakai yang membuka ronde tersebut. Kolom bisa diklik untuk mengurutkan.
                {techCount > 0 ? " Akun sistem (data awal) tidak ikut diperingkat." : ""}
              </p>
            </>
          )}
        </div>
      </section>

      {/* ── Papan eskalasi SLA (aktif) ──────────────────────────────────── */}
      <DesignerSlaPanel board={board} filterDesigner={focusDesigner} busy={busy}
        canManage={canManage} onEscalate={escalateNow} runInfo={runInfo} />
      </>
      )}

      {/* ── Modal: catatan evaluasi sebelum unduh Rapor PDF ─────────────────
          Fase 3 · P6 (L-03) — FormModal baku (dulu lapisan `fixed inset-0` buatan sendiri). */}
      <FormModal open={!!reportModal} onClose={() => !reportBusy && setReportModal(null)}
        title={`Rapor PDF — ${reportModal?.designer || ""}`} icon={FileText} size="md" testId="designer-report-modal"
        subtitle="Catatan evaluasi opsional — muncul sebagai kotak “Catatan Evaluasi” di rapor, siap ditandatangani."
        busy={Boolean(reportBusy)}
        footer={(
          <div className="flex items-center justify-end gap-2">
            <button type="button" className="secondary-button" disabled={Boolean(reportBusy)}
              data-testid="designer-report-cancel"
              onClick={() => setReportModal(null)}>Batal</button>
            <button type="button" className="primary-button" disabled={Boolean(reportBusy)}
              data-testid="designer-report-download"
              onClick={() => downloadReport(reportModal.designer, reportModal.note)}>
              <FileText size={13} className={reportBusy ? "animate-pulse" : ""} />
              {reportBusy ? "Menyiapkan…" : "Unduh PDF"}
            </button>
          </div>
        )}>
        {reportModal && (
          <label className="block">
            <span className="field-label">Catatan evaluasi (opsional)</span>
            <textarea
              data-testid="designer-report-note"
              value={reportModal.note}
              maxLength={1200}
              rows={5}
              onChange={(e) => setReportModal((m) => ({ ...m, note: e.target.value }))}
              placeholder={"Contoh:\nKonsistensi warna membaik. Perlu percepat setor <2 hari.\nTanda tangan: ................"}
              className="field !h-auto w-full resize-y text-[12px]" />
            <span className="mt-1 block text-[10px] text-[#9A9BA3]">{reportModal.note.length}/1200</span>
          </label>
        )}
      </FormModal>
    </div>
  );
}

function Kpi({ label, value, tone = "#1C1C1E", testId }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2" data-testid={testId}>
      <p className="text-[10.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="text-[13px] font-bold leading-tight tabular-nums" style={{ color: tone }}>
        {value}
      </p>
    </div>
  );
}
