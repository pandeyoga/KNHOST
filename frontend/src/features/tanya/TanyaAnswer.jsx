import { useEffect, useState } from "react";
import { AlertTriangle, BookmarkPlus, CalendarClock, ExternalLink, FileSpreadsheet, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "../../components/ui/button";
import { useAppNav } from "../../context/AppNavContext";
import ErrorBoundary from "../../components/ErrorBoundary";
import { toast } from "../../hooks/use-toast";
import { TanyaActionCard } from "./TanyaActionCard";
import { TanyaChart } from "./TanyaChart";
import { TanyaFeedback } from "./TanyaFeedback";
import { TanyaMarkdown } from "./TanyaMarkdown";
import { TanyaNarrative } from "./TanyaNarrative";
import { TanyaSummaryCards, TanyaTable } from "./TanyaTable";
import { downloadAnswerXlsx, fetchResult } from "./tanyaApi";
import { splitAnswer } from "./tanyaFormat";

function Block({ block, result }) {
  if (!result) return null;
  if (block.kind === "summary_cards") return <TanyaSummaryCards result={result} />;
  if (block.kind === "chart") return <TanyaChart result={result} spec={block} />;
  return <TanyaTable result={result} spec={block} />;
}

function MetaLine({ result, entityLabel }) {
  if (!result) return null;
  const def = (result.definition || "").split(" · ")[0];
  return (
    <div className="tanya-meta" data-testid="tanya-answer-meta">
      Periode {result.period?.label || "—"} · Entitas {entityLabel} · Definisi {def || "—"}
    </div>
  );
}

function ExportAll({ ids, title }) {
  const [busy, setBusy] = useState(false);
  if (!ids.length) return null;
  const go = async () => {
    setBusy(true);
    try { await downloadAnswerXlsx(ids, title); }
    catch { toast({ title: "Gagal mengunduh Excel", variant: "destructive" }); }
    finally { setBusy(false); }
  };
  return (
    <Button size="sm" variant="outline" onClick={go} disabled={busy} data-testid="tanya-answer-export">
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />} Unduh Excel{ids.length > 1 ? ` (${ids.length} sheet)` : ""}
    </Button>
  );
}

function useChatResults(answer, inText) {
  const [chatResults, setChatResults] = useState({});
  const ids = answer.kind === "chat" ? [...new Set([...inText, ...(answer.resultIds || [])])].join(",") : "";
  useEffect(() => {
    if (!ids) return;
    Promise.all(ids.split(",").map((id) => fetchResult(id).catch(() => null)))
      .then((docs) => setChatResults(Object.fromEntries(docs.filter(Boolean).map((d) => [d.result_id, d]))));
  }, [ids]);
  return chatResults;
}

function ChatParts({ parts, chatResults, onFollowup }) {
  return parts.map((p, i) => {
    if (p.kind === "text") return <TanyaMarkdown key={i} text={p.text} />;
    if (p.kind === "kn-followups") return (
      <div key={i} className="tanya-followups">
        {(Array.isArray(p.spec) ? p.spec : []).map((q, j) => (
          <button key={j} type="button" className="tanya-chip" onClick={() => onFollowup(q)} data-testid={`tanya-followup-${j}`}>{q}</button>
        ))}
      </div>
    );
    // KN-E44 — blok kn-* tidak valid tidak boleh meruntuhkan seluruh layar Tanya KN.
    if (!p.spec || typeof p.spec !== "object" || Array.isArray(p.spec)) return null;
    if (p.kind === "kn-action") return p.spec.proposal_id ? (
      <ErrorBoundary key={i} resetKey={p.spec.proposal_id}><TanyaActionCard proposalId={p.spec.proposal_id} /></ErrorBoundary>
    ) : null;
    const res = chatResults[p.spec.result_id];
    return res ? (
      <ErrorBoundary key={i} resetKey={p.spec.result_id}>
        <Block block={{ ...p.spec, kind: p.kind === "kn-chart" ? "chart" : "table" }} result={res} />
      </ErrorBoundary>
    ) : null;
  });
}

/** AG-T2 — lencana pemeriksa angka mode Keuangan (ikon + teks + warna). */
function FinanceVerifyPill({ ver }) {
  const ok = Boolean(ver?.ok);
  const Icon = ok ? ShieldCheck : AlertTriangle;
  return (
    <span className={`status-pill ${ok ? "bg-kn-success-soft text-kn-success-text" : "bg-kn-warning-soft text-kn-warning-text"}`}
      data-testid="tanya-finance-verify">
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {ok ? "Angka diperiksa: semua cocok dengan data" : "Angka tidak bisa dipastikan"}
    </span>
  );
}

/** AG-T2 — bagian Sumber jawaban keuangan: satu baris per hasil alat (disusun server), catatan, tombol ke layarnya. */
function FinanceSources({ sources }) {
  const { go, canOpen } = useAppNav();
  if (!sources?.length) return null;
  const open = (link) => go(link.view, {
    navId: link.nav_id || undefined, preset: link.tab ? { tab: link.tab } : undefined,
    focus: link.focus_id ? { type: link.focus_type, id: link.focus_id } : undefined,
  });
  return (
    <section className="tanya-sources" data-testid="tanya-sources">
      <div className="tanya-kicker">Sumber</div>
      <ul className="tanya-source-list">
        {sources.map((s, i) => (
          <li key={s.result_id || i} className="tanya-source" data-testid={`tanya-source-${i}`}>
            <div className="tanya-source-row">
              <span className="tanya-source-title" data-testid={`tanya-source-title-${i}`}>
                {[s.title, s.entity_label, s.period_label].filter(Boolean).join(" · ")}
              </span>
              {s.link?.view && canOpen(s.link.view) && (
                <button type="button" className="secondary-button btn-sm tanya-source-open" onClick={() => open(s.link)}
                  data-testid={`tanya-source-open-${i}`}>
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /> Buka di layar
                </button>
              )}
            </div>
            {s.notes?.length > 0 && (
              <ul className="tanya-source-notes" data-testid={`tanya-source-notes-${i}`}>
                {s.notes.map((n, j) => <li key={j}>{n}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Jawaban template (blok resep + narasi) atau chat (markdown + blok kn-*). Angka grafik/tabel selalu dari server. */
export function TanyaAnswer({ answer, entityLabel, onFollowup, aiEnabled, onSaveTemplate, onSchedule }) {
  const isTpl = answer.kind === "template";
  const parts = isTpl ? [] : splitAnswer(answer.text);
  const inText = parts.filter((p) => p.spec?.result_id).map((p) => p.spec.result_id);
  const chatResults = useChatResults(answer, inText);
  const results = isTpl ? answer.data.results : chatResults;
  const first = isTpl ? results[answer.data.blocks[0]?.result_id] : Object.values(chatResults)[0];
  const warnings = isTpl ? answer.data.warnings || [] : [];
  const ver = answer.verification;
  const finance = answer.mode === "keuangan";
  const extra = isTpl ? [] : Object.values(chatResults).filter((r) => !inText.includes(r.result_id) && r.columns?.length);
  const title = isTpl ? answer.data.template.title : answer.question;
  return (
    <article className={`tanya-answer section-card ${isTpl ? "is-tpl" : "is-chat"}`} data-testid="tanya-answer">
      <header className="tanya-answer-head">
        <div>
          <div className="tanya-kicker">{isTpl ? answer.data.template.group : finance ? "Asisten Keuangan" : "Jawaban asisten"}{answer.data?.cached ? " · dari cache" : ""}</div>
          <h2 className="tanya-answer-title">{title}</h2>
        </div>
        <div className="tanya-answer-actions">
          {isTpl && onSchedule && answer.data.template?.kind !== "finance_morning" && <Button size="sm" variant="outline" onClick={() => onSchedule(answer.data)} data-testid="tanya-answer-schedule"><CalendarClock className="h-4 w-4" /> Jadwalkan</Button>}
          {!isTpl && onSaveTemplate && <Button size="sm" variant="outline" onClick={() => onSaveTemplate(answer.question)} data-testid="tanya-answer-save-template"><BookmarkPlus className="h-4 w-4" /> Simpan sebagai template saya</Button>}
          <ExportAll ids={Object.keys(results || {})} title={title} />
          <TanyaFeedback payload={{ template_id: answer.data?.template?.id, session_id: answer.sessionId, result_ids: Object.keys(results || {}) }} />
        </div>
      </header>
      {isTpl && <TanyaNarrative data={answer.data} aiEnabled={aiEnabled} />}
      <ChatParts parts={parts} chatResults={chatResults} onFollowup={onFollowup} />
      {extra.length > 0 && <div className="tanya-kicker" data-testid="tanya-chat-supporting">Data pendukung</div>}
      {extra.map((r) => <TanyaTable key={r.result_id} result={r} />)}
      {isTpl && answer.data.blocks.map((b, i) => <Block key={i} block={b} result={results[b.result_id]} />)}
      {isTpl && !answer.data.blocks.length && (
        <div className="tanya-empty" data-testid="tanya-answer-empty">Template ini belum menghasilkan data untuk peran/periode Anda.</div>
      )}
      {warnings.length > 0 && (
        <ul className="tanya-warnings" data-testid="tanya-warnings">
          {warnings.map((w, i) => <li key={i}><AlertTriangle className="h-3.5 w-3.5" /> {w}</li>)}
        </ul>
      )}
      {finance && <FinanceSources sources={answer.sources} />}
      {finance && ver && <div className="tanya-finance-verify-bar"><FinanceVerifyPill ver={ver} /></div>}
      {!finance && ver && (
        <div className={`tanya-verify ${ver.ok ? "ok" : "bad"}`} data-testid="tanya-verification">
          <ShieldCheck className="h-4 w-4" /> {ver.ok ? `Semua angka terverifikasi (${ver.checked})` : `Angka belum terverifikasi: ${(ver.unmatched || []).join(", ")}`}
        </div>
      )}
      <MetaLine result={first} entityLabel={entityLabel} />
    </article>
  );
}
