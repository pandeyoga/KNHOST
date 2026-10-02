import { Loader2, MessageSquareText } from "lucide-react";
import { TanyaAnswer } from "./TanyaAnswer";
import { TanyaStreaming } from "./TanyaStreaming";

export function Suggestions({ items, notice, onRun }) {
  if (!items?.length) return null;
  return (
    <div className="tanya-suggest section-card" data-testid="tanya-suggestions">
      <div className="tanya-kicker"><MessageSquareText className="h-4 w-4" /> Template yang mungkin menjawab</div>
      {notice && <p className="tanya-note" data-testid="tanya-suggestions-notice">{notice}</p>}
      {items.map((t) => (
        <button key={t.id} type="button" className="tanya-chip" onClick={() => onRun(t)} data-testid={`tanya-suggestion-${t.id}`}>{t.title}</button>
      ))}
    </div>
  );
}

/** Percakapan berjalan: gelembung pertanyaan + jawaban bertahap / final (atau saran template saat AI mati). */
export function TanyaThread({ entries, statusText, answerProps, onRunTemplate }) {
  return (
    <div className="tanya-thread" data-testid="tanya-thread">
      {entries.map((e) => (
        <div key={e.id} className="tanya-thread" data-testid="tanya-thread-entry">
          <div className="tanya-bubble" data-testid="tanya-thread-question">
            {e.context && <div className="tanya-bubble-context" data-testid="tanya-thread-context">Dari halaman: {e.context.label}</div>}
            {e.context && <br />}
            {e.question}
          </div>
          {e.pending && !e.streamText && <div className="tanya-loading" data-testid="tanya-busy"><Loader2 className="h-5 w-5 animate-spin" /> {statusText}</div>}
          {e.pending && e.streamText && <TanyaStreaming text={e.streamText} statusText={statusText} />}
          {e.error && <div className="tanya-thread-error" data-testid="tanya-thread-error">Gagal dikirim: {e.error}</div>}
          {e.suggestions && <Suggestions items={e.suggestions} notice={e.notice} onRun={onRunTemplate} />}
          {e.answer && <TanyaAnswer answer={e.answer} {...answerProps} />}
        </div>
      ))}
    </div>
  );
}
