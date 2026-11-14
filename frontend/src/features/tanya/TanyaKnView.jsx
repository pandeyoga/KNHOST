import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "../../hooks/use-toast";
import { entityFullById, entityShortById } from "../../utils/entityLabel";
import { PENDING_KEY, PRESETS as ASK_PRESETS } from "../../components/AskKnButton";
import { TanyaActions } from "./TanyaActions";
import { TanyaInsights } from "./TanyaInsights";
import { TanyaAnswer } from "./TanyaAnswer";
import { TanyaBudgetCard } from "./TanyaBudgetCard";
import { TanyaChatPane, TanyaWelcome, useFillHeight } from "./TanyaChatPane";
import { TanyaClosingPackCard, TanyaClosingPackResult } from "./TanyaClosingPack";
import { TanyaCostView } from "./TanyaCostView";
import { TanyaSaveTemplateDialog, TanyaScheduleDialog } from "./TanyaDialogs";
import { TanyaHistory } from "./TanyaHistory";
import { TanyaRulesStrip } from "./TanyaRulesStrip";
import { TanyaSchedules } from "./TanyaSchedules";
import { TanyaPeriodChips, TanyaTemplateGallery } from "./TanyaTemplateGallery";
import { TanyaThread } from "./TanyaThread";
import { buildClosingPack, deleteMyTemplate, downloadClosingPack, fetchMyTemplates, fetchScheduleRun, fetchStatus, fetchTemplates,
  runTemplate } from "./tanyaApi";
import { useTanyaChat } from "./useTanyaChat";
import useIsMobile from "../../hooks/useIsMobile";
import "./tanya.css";

// AG-T3 — tab "Tindakan" (kartu tindakan asisten) sesudah "Laporan"; daftarnya tampil di panel utama (enam kolom).
const TABS = [["reports", "Laporan"], ["actions", "Tindakan"], ["insights", "Peringatan"], ["history", "Riwayat"],
  ["schedules", "Jadwal"], ["cost", "Biaya"]];
const MOBILE_Q = "(max-width: 900px)";
const initialTab = () => {
  const t = new URLSearchParams(window.location.search).get("tab");
  if (t === "chat" || TABS.some(([k]) => k === t)) return t;
  return typeof window !== "undefined" && window.matchMedia?.(MOBILE_Q).matches ? "chat" : "reports";
};

const PACK_FAILED = "Paket tidak bisa disusun. Coba lagi.";
/** Galat permintaan paket: pesan server untuk isian/izin (400/403/409), selain itu kalimat baku. */
const packError = (e) => {
  let body = e?.response?.data;
  if (typeof body === "string") { try { body = JSON.parse(body); } catch { body = null; } }
  const st = e?.response?.status;
  return [400, 403, 409].includes(st) && typeof body?.detail === "string" ? body.detail : PACK_FAILED;
};

const FINANCE_PROMPTS = [
  "Berapa laba rugi bulan ini dibanding bulan lalu?",
  "Piutang mana yang sudah lewat jatuh tempo?",
  "Berapa saldo kas dan bank hari ini?",
  "Tagihan pemasok apa yang jatuh tempo minggu ini?",
];

export default function TanyaKnView({ selectedEntity, entities }) {
  const [status, setStatus] = useState(null);
  const [catalog, setCatalog] = useState(null);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState("mtd");
  const [active, setActive] = useState(null);
  const [tplAnswer, setTplAnswer] = useState(null);
  const [tplBusy, setTplBusy] = useState(false);
  const [tab, setTab] = useState(initialTab);
  const [historyKey, setHistoryKey] = useState(0);
  const [schedKey, setSchedKey] = useState(0);
  const [mine, setMine] = useState([]);
  const [scheduleTarget, setScheduleTarget] = useState(null);
  const [saveQuestion, setSaveQuestion] = useState(null);
  const [docCtx, setDocCtx] = useState(null);
  const [mode, setMode] = useState("umum");   // AG-T2 — "keuangan" hanya bila Asisten Keuangan menyala untuk akun ini
  const [pack, setPack] = useState(null);     // AG-T4 — {status: busy|error|done, done, total, period, pack, error}
  const [packDl, setPackDl] = useState(false);
  const chat = useTanyaChat(() => setHistoryKey((k) => k + 1));
  const compact = useIsMobile(900);
  const lastEntry = chat.thread[chat.thread.length - 1];
  const sideRef = useRef(null);
  useFillHeight(sideRef, 16, `${!!catalog}|${compact}`);
  useEffect(() => {
    document.body.classList.add("tanya-open");
    return () => document.body.classList.remove("tanya-open");
  }, []);
  const toMain = () => { if (compact) setTab("chat"); };

  const loadMine = () => fetchMyTemplates().then(setMine).catch(() => setMine([]));
  const openRun = useCallback(async (id) => {
    try {
      const r = await fetchScheduleRun(id);
      setActive(null);
      setTplAnswer({ kind: "template", data: { template: r.template, blocks: r.blocks || [], results: r.results || {}, warnings: r.warnings || [],
        narrative: r.narrative, narrative_source: r.narrative_source, params: r.params, scheduledAt: r.created_at } });
    } catch { toast({ title: "Laporan tidak ditemukan", variant: "destructive" }); }
  }, []);

  useEffect(() => {
    Promise.all([fetchStatus(), fetchTemplates()])
      .then(([s, t]) => { setStatus(s); setCatalog(t); })
      .catch((e) => setError(e?.response?.data?.detail || "Asisten analitik tidak dapat dimuat."));
    loadMine();
    const run = new URLSearchParams(window.location.search).get("run");
    if (run) openRun(run);
  }, [selectedEntity, openRun]);

  const pendingAsk = useRef(false);
  useEffect(() => {
    if (!catalog || pendingAsk.current) return;
    pendingAsk.current = true;
    const raw = sessionStorage.getItem(PENDING_KEY);
    if (!raw) return;
    sessionStorage.removeItem(PENDING_KEY);
    try {
      const p = JSON.parse(raw);
      if (p?.context) { setTab("chat"); setDocCtx(p.context); }
      // AG-T3 — konteks keuangan dibuka di mode Keuangan bila Asisten Keuangan & chat menyala untuk akun ini.
      const m = p?.mode === "keuangan" && status?.finance_enabled && status?.chat_enabled ? "keuangan" : "umum";
      if (m === "keuangan") setMode("keuangan");
      if (p?.question) chat.ask(p.question, p.context || null, m);
    } catch { /* abaikan */ }
  }, [catalog]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = useCallback(async (tpl, p = period) => {
    setPack(null); setActive(tpl); setTplBusy(true);
    try {
      setTplAnswer({ kind: "template", data: await runTemplate(tpl.id, tpl.has_period ? { period: p } : {}) });
    } catch (e) {
      toast({ title: "Template gagal dijalankan", description: e?.response?.data?.detail || "", variant: "destructive" });
    } finally { setTplBusy(false); }
  }, [period]);

  const onPeriod = (p) => { setPeriod(p); if (active?.has_period) run(active, p); };
  const askMode = status?.finance_enabled && status?.chat_enabled && mode === "keuangan" ? "keuangan" : "umum";
  const ask = (q) => { toMain(); setTplAnswer(null); setActive(null); setPack(null); chat.ask(q, docCtx, askMode); };
  const buildPack = async (p) => {   // AG-T4 — kemajuan per lembar dari server ("Menyusun paket… (i dari 12)")
    toMain(); setTplAnswer(null); setActive(null);
    setPack({ status: "busy", done: 0, total: 12, period: p });
    let got = null;
    let err = "";
    try {
      await buildClosingPack(p, (ev) => {
        if (ev.type === "progress") setPack((s) => ({ ...s, done: ev.done, total: ev.total }));
        if (ev.type === "done") { got = ev.pack || null; err = ev.error || ""; }
      });
      setPack(got ? { status: "done", pack: got, period: p } : { status: "error", error: err || PACK_FAILED, period: p });
    } catch (e) { setPack({ status: "error", error: packError(e), period: p }); }
  };
  const downloadPack = async (pk) => {
    setPackDl(true);
    try { await downloadClosingPack(pk); }
    catch { toast({ title: "Gagal mengunduh Excel", variant: "destructive" }); }
    finally { setPackDl(false); }
  };
  const removeMine = async (id) => { await deleteMyTemplate(id).catch(() => null); loadMine(); toast({ title: "Template pribadi dihapus" }); };
  const onSchedule = (data) => setScheduleTarget({ template: data.template, params: data.params,
    hasPeriod: !!catalog?.templates.find((t) => t.id === data.template.id)?.has_period });

  if (error) return <div className="tanya-error section-card" data-testid="tanya-error">{error}</div>;
  if (!catalog) return <div className="tanya-loading" data-testid="tanya-loading"><Loader2 className="h-5 w-5 animate-spin" /> Memuat asisten…</div>;
  const entityLabel = selectedEntity === "all" ? "Semua entitas" : entityShortById(entities || [], selectedEntity, "entitas aktif");
  const answerProps = { entityLabel, onFollowup: ask, aiEnabled: !!status?.narrative_ai, onSaveTemplate: setSaveQuestion, onSchedule };
  const busy = chat.busy || tplBusy;
  const view = !compact && tab === "chat" ? "reports" : tab;
  const tabs = compact ? [["chat", "Tanya"], ...TABS] : TABS;

  const financeScope = { combined: selectedEntity === "all", label: entityFullById(entities || [], selectedEntity, "PT aktif") };
  // AG-T4 — kartu Paket tutup buku (grup Keuangan) & jadwal ringkasan pagi: hanya bila Asisten Keuangan menyala untuk akun.
  const financeCard = status?.finance_enabled ? (
    <TanyaClosingPackCard combined={financeScope.combined} ptLabel={financeScope.label} busy={pack?.status === "busy"}
      onBuild={buildPack} />
  ) : null;
  const tabBar = (
    <div className="tanya-side-tabs" role="tablist">
      {tabs.map(([k, label]) => (
        <button key={k} type="button" role="tab" aria-selected={view === k} className={`tanya-side-tab ${view === k ? "active" : ""}`}
          onClick={() => setTab(k)} data-testid={`tanya-tab-${k}`}>{label}</button>
      ))}
    </div>
  );
  const side = (<>
    {view === "reports" && (<>
      <TanyaPeriodChips presets={catalog.period_presets} value={period} onChange={onPeriod} />
      <TanyaTemplateGallery groups={catalog.groups} templates={catalog.templates} activeId={active?.id} onRun={(t) => { toMain(); run(t); }}
        myTemplates={mine} onAskMine={ask} onDeleteMine={removeMine} financeCard={financeCard} />
    </>)}
    {view === "history" && (
      <TanyaHistory activeId={chat.sessionId} refreshKey={historyKey} onNew={() => { toMain(); chat.reset(); setTplAnswer(null); setDocCtx(null); }}
        onOpen={(id) => { toMain(); setTplAnswer(null); setActive(null); chat.openSession(id); }}
        onDeleted={(id) => { if (id === chat.sessionId) chat.reset(); }} />
    )}
    {view === "schedules" && <TanyaSchedules refreshKey={schedKey} onOpenRun={(id) => { toMain(); setPack(null); openRun(id); }}
      finance={status?.finance_enabled ? financeScope : null} />}
    {view === "insights" && <TanyaInsights canScan={!!status?.can_edit_rules} onAsk={ask} refreshKey={selectedEntity} />}
    {view === "cost" && <TanyaBudgetCard budget={status?.budget} />}
    {view === "actions" && (
      <p className="tanya-action-hint" data-testid="tanya-actions-side">
        Kartu tindakan yang disiapkan asisten untuk Anda. Tidak ada yang dijalankan sebelum Anda menyetujui kartunya.
      </p>
    )}
  </>);
  const scrollKey = `${chat.thread.length}|${lastEntry?.pending}|${(lastEntry?.streamText || "").length >> 7}|${!!lastEntry?.answer}|${lastEntry?.error || ""}|${tplAnswer ? 1 : 0}|${tplBusy}|${pack?.status || ""}`;
  // Cek layar 14 Nov — mode Keuangan: saran pembuka berupa pertanyaan keuangan (bukan laporan umum gudang/penjualan).
  // AG-T3 — dibuka dari "Tanya soal layar ini" di layar keuangan: saran pembuka = pertanyaan untuk konteks itu.
  const ctxPrompts = docCtx ? (ASK_PRESETS || {})[docCtx.type] : null;
  const prompts = askMode === "keuangan" && ctxPrompts?.length ? ctxPrompts.map((label) => ({ label }))
    : askMode === "keuangan" ? FINANCE_PROMPTS.map((label) => ({ label }))
    : catalog.templates.slice(0, 4).map((t) => ({ label: t.prompt || t.title, tpl: t }));
  const pick = (p) => (status?.chat_enabled ? ask(p.label) : (toMain(), run(p.tpl)));
  const composer = { status, busy, entityLabel, onAsk: ask, context: docCtx, onClearContext: () => setDocCtx(null),
    statusText: tplBusy ? `Menjalankan ${active?.title || "laporan"}…` : chat.statusText, mode: askMode, onMode: setMode,
    financeScope };
  const chatMain = (<TanyaChatPane scrollKey={scrollKey} composer={composer}>
    {(tplAnswer || pack) && chat.thread.length > 0 && (
      <button type="button" className="tanya-chip tanya-back" onClick={() => { setTplAnswer(null); setActive(null); setPack(null); }} data-testid="tanya-back-to-chat">
        <ArrowLeft className="h-3.5 w-3.5 inline" /> Kembali ke percakapan
      </button>
    )}
    {pack && <TanyaClosingPackResult state={pack} onRetry={() => buildPack(pack.period)} onDownload={downloadPack} downloading={packDl} />}
    {!pack && tplBusy && !tplAnswer && <div className="tanya-loading" data-testid="tanya-busy"><Loader2 className="h-5 w-5 animate-spin" /> Menjalankan laporan…</div>}
    {!pack && tplAnswer && <div className={tplBusy ? "tanya-dim" : ""}><TanyaAnswer answer={tplAnswer} {...answerProps} /></div>}
    {!pack && !tplAnswer && chat.thread.length > 0 && <TanyaThread entries={chat.thread} statusText={chat.statusText} answerProps={answerProps} onRunTemplate={(t) => run(t)} />}
    {!pack && !tplAnswer && !tplBusy && !chat.thread.length && <TanyaWelcome prompts={prompts} onPick={pick} />}
  </TanyaChatPane>);
  const dialogs = (<>
    <TanyaScheduleDialog target={scheduleTarget} periodPresets={catalog.period_presets} onClose={() => setScheduleTarget(null)}
      onSaved={() => { setSchedKey((k) => k + 1); setTab("schedules"); }} />
    <TanyaSaveTemplateDialog question={saveQuestion} onClose={() => setSaveQuestion(null)} onSaved={loadMine} />
  </>);

  if (compact) {
    return (
      <div className="tanya-page compact" data-testid="tanya-kn-page">
        <TanyaRulesStrip status={status} />
        {tabBar}
        {view === "chat" && <div className="tanya-main">{chatMain}</div>}
        {view === "cost" && <div className="tanya-main"><div className="section-card tanya-side">{side}</div><TanyaCostView /></div>}
        {view === "actions" && <div className="tanya-main"><div className="section-card section-pad"><TanyaActions refreshKey={selectedEntity} /></div></div>}
        {view !== "chat" && view !== "cost" && view !== "actions" && <div className="section-card tanya-side">{side}</div>}
        {dialogs}
      </div>
    );
  }
  return (
    <div className="tanya-page" data-testid="tanya-kn-page">
      <TanyaRulesStrip status={status} />
      <div className="tanya-layout">
        <aside ref={sideRef} className="tanya-side section-card">{tabBar}{side}</aside>
        <main className="tanya-main">{view === "cost" ? <TanyaCostView />
          : view === "actions" ? <div className="section-card section-pad"><TanyaActions refreshKey={selectedEntity} /></div>
            : chatMain}</main>
      </div>
      {dialogs}
    </div>
  );
}
