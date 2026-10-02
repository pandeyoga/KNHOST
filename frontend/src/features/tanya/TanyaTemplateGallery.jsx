import { Bookmark, ChevronRight, Trash2 } from "lucide-react";
import { PERIOD_LABELS } from "./tanyaFormat";

export function TanyaPeriodChips({ presets, value, onChange }) {
  return (
    <div className="tanya-periods" role="radiogroup" aria-label="Periode">
      {presets.map((p) => (
        <button key={p} type="button" role="radio" aria-checked={value === p}
          className={`tanya-chip ${value === p ? "active" : ""}`} onClick={() => onChange(p)} data-testid={`tanya-period-${p}`}>
          {PERIOD_LABELS[p] || p}
        </button>
      ))}
    </div>
  );
}

function MyTemplates({ items, onAsk, onDelete }) {
  if (!items?.length) return null;
  return (
    <section className="tanya-group" data-testid="tanya-my-templates">
      <div className="tanya-group-title">Template saya</div>
      {items.map((t) => (
        <div key={t.id} className="tanya-sess">
          <button type="button" className="tanya-sess-main" onClick={() => onAsk(t.question)} data-testid={`tanya-my-template-${t.id}`}>
            <span className="tanya-tpl-title"><Bookmark className="h-3.5 w-3.5 inline" /> {t.title}</span>
            {t.title !== t.question && <span className="tanya-tpl-prompt">{t.question}</span>}
          </button>
          <button type="button" className="tanya-icon-btn" onClick={() => onDelete(t.id)} aria-label="Hapus template" data-testid={`tanya-my-template-delete-${t.id}`}><Trash2 className="h-4 w-4" /></button>
        </div>
      ))}
    </section>
  );
}

export function TanyaTemplateGallery({ groups, templates, activeId, onRun, myTemplates, onAskMine, onDeleteMine }) {
  return (
    <nav className="tanya-gallery" data-testid="tanya-template-gallery">
      <MyTemplates items={myTemplates} onAsk={onAskMine} onDelete={onDeleteMine} />
      {groups.map((g) => {
        const list = templates.filter((t) => t.group === g);
        if (!list.length) return null;
        return (
          <section key={g} className="tanya-group">
            <div className="tanya-group-title">{g}</div>
            {list.map((t) => (
              <button key={t.id} type="button" className={`tanya-tpl ${activeId === t.id ? "active" : ""}`}
                onClick={() => onRun(t)} data-testid={`tanya-template-${t.id}`}>
                <span>
                  <span className="tanya-tpl-title">{t.title}</span>
                  <span className="tanya-tpl-prompt">{t.prompt}</span>
                </span>
                <ChevronRight className="h-4 w-4" />
              </button>
            ))}
          </section>
        );
      })}
    </nav>
  );
}
