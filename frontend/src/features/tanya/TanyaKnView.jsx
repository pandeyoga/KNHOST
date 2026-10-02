import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "../../hooks/use-toast";
import { entityShortById } from "../../utils/entityLabel";
import { PENDING_KEY } from "../../components/AskKnButton";
import { TanyaInsights } from "./TanyaInsights";
import { TanyaAnswer } from "./TanyaAnswer";
import { TanyaBudgetCard } from "./TanyaBudgetCard";
import { TanyaChatPane, TanyaWelcome, useFillHeight } from "./TanyaChatPane";
import { TanyaCostView } from "./TanyaCostView";
import { TanyaSaveTemplateDialog, TanyaScheduleDialog } from "./TanyaDialogs";
import { TanyaHistory } from "./TanyaHistory";
import { TanyaRulesStrip } from "./TanyaRulesStrip";
import { TanyaSchedules } from "./TanyaSchedules";
import { TanyaPeriodChips, TanyaTemplateGallery } from "./TanyaTemplateGallery";
import { TanyaThread } from "./TanyaThread";
import { deleteMyTemplate, fetchMyTemplates, fetchScheduleRun, fetchStatus, fetchTemplates, runTemplate } from "./tanyaApi";
import { useTanyaChat } from "./useTanyaChat";
import useIsMobile from "../../hooks/useIsMobile";
import "./tanya.css";

const TABS = [["reports", "Laporan"], ["insights", "Peringatan"], ["history", "Riwayat"], ["schedules", "Jadwal"], ["cost", "Biaya"]];
const MOBILE_Q = "(max-width: 900px)";
const initialTab = () => {
  const t = new URLSearchParams(window.location.search).get("tab");
  if (t === "chat" || TABS.some(([k]) => k === t)) return t;
  return typeof window !== "undefined" && window.matchMedia?.(MOBILE_Q).matches ? "chat" : "reports";
};

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
    try { const p = JSON.parse(raw); if (p?.question) { setTab("chat"); chat.ask(p.question, p.context || null); } } catch { /* abaikan */ }
  }, [catalog]); // eslint-disable-line react-hooks/exhaustive-deps

  const run = useCallback(async (tpl, p = period) => {
    setActive(tpl); setTplBusy(true);
    try {
      setTplAnswer({ kind: "template", data: await runTemplate(tpl.id, tpl.has_period ? { period: p } : {}) });
    } catch (e) {
      toast({ title: "Template gagal dijalankan", description: e?.response?.data?.detail || "", variant: "destructive" });
    } finally { setTplBusy(false); }
  }, [period]);

  const onPeriod = (p) => { setPeriod(p); if (active?.has_period) run(active, p); };
  const ask = (q) => { toMain(); setTplAnswer(null); setActive(null); chat.ask(q); };
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
        myTemplates={mine} onAskMine={ask} onDeleteMine={removeMine} />
    </>)}
    {view === "history" && (
      <TanyaHistory activeId={chat.sessionId} refreshKey={historyKey} onNew={() => { toMain(); chat.reset(); setTplAnswer(null); }}
        onOpen={(id) => { toMain(); setTplAnswer(null); setActive(null); chat.openSession(id); }}
        onDeleted={(id) => { if (id === chat.sessionId) chat.reset(); }} />
    )}
    {view === "schedules" && <TanyaSchedules refreshKey={schedKey} onOpenRun={(id) => { toMain(); openRun(id); }} />}
    {view === "insights" && <TanyaInsights canScan={!!status?.can_edit_rules} onAsk={ask} refreshKey={selectedEntity} />}
    {view === "cost" && <TanyaBudgetCard budget={status?.budget} />}
  </>);
  const scrollKey = `${chat.thread.length}|${lastEntry?.pending}|${(lastEntry?.streamText || "").length >> 7}|${!!lastEntry?.answer}|${lastEntry?.error || ""}|${tplAnswer ? 1 : 0}|${tplBusy}`;
  const prompts = catalog.templates.slice(0, 4).map((t) => ({ label: t.prompt || t.title, tpl: t }));
  const pick = (p) => (status?.chat_enabled ? ask(p.label) : (toMain(), run(p.tpl)));
  const composer = { status, busy, entityLabel, onAsk: ask,
    statusText: tplBusy ? `Menjalankan ${active?.title || "laporan"}…` : chat.statusText };
  const chatMain = (<TanyaChatPane scrollKey={scrollKey} composer={composer}>
    {tplAnswer && chat.thread.length > 0 && (
      <button type="button" className="tanya-chip tanya-back" onClick={() => { setTplAnswer(null); setActive(null); }} data-testid="tanya-back-to-chat">
        <ArrowLeft className="h-3.5 w-3.5 inline" /> Kembali ke percakapan
      </button>
    )}
    {tplBusy && !tplAnswer && <div className="tanya-loading" data-testid="tanya-busy"><Loader2 className="h-5 w-5 animate-spin" /> Menjalankan laporan…</div>}
    {tplAnswer && <div className={tplBusy ? "tanya-dim" : ""}><TanyaAnswer answer={tplAnswer} {...answerProps} /></div>}
    {!tplAnswer && chat.thread.length > 0 && <TanyaThread entries={chat.thread} statusText={chat.statusText} answerProps={answerProps} onRunTemplate={(t) => run(t)} />}
    {!tplAnswer && !tplBusy && !chat.thread.length && <TanyaWelcome prompts={prompts} onPick={pick} />}
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
        {view !== "chat" && view !== "cost" && <div className="section-card tanya-side">{side}</div>}
        {dialogs}
      </div>
    );
  }
  return (
    <div className="tanya-page" data-testid="tanya-kn-page">
      <TanyaRulesStrip status={status} />
      <div className="tanya-layout">
        <aside ref={sideRef} className="tanya-side section-card">{tabBar}{side}</aside>
        <main className="tanya-main">{view === "cost" ? <TanyaCostView /> : chatMain}</main>
      </div>
      {dialogs}
    </div>
  );
}
