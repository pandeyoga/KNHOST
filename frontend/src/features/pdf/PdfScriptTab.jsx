// PdfScriptTab — naskah pembuka/penutup per jenis dokumen dengan placeholder {{token}}.
// Pola sipro `ScriptForm`: chip placeholder (klik = sisip), peringatan token asing HIDUP saat mengetik.
// KP-T6 — `mark(kunci)` = tanda "khusus PT ini" (lapisan PT); token berketerangan (`note`, mis. {{rekening_bank}}) dijelaskan.
import { useMemo, useRef } from "react";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";

const TOKEN_RE = /{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}/g;

export function unknownTokens(text, placeholders) {
  const known = new Set((placeholders || []).map((p) => p.token));
  const out = new Set();
  for (const m of String(text || "").matchAll(TOKEN_RE)) if (!known.has(m[1])) out.add(m[1]);
  return [...out];
}

function ScriptField({ label, hint, value, onChange, placeholders, testId, mark = null }) {
  const ref = useRef(null);
  const unknown = useMemo(() => unknownTokens(value, placeholders), [value, placeholders]);
  const insert = (token) => {
    const el = ref.current;
    const ins = `{{${token}}}`;
    if (!el) { onChange(`${value || ""}${ins}`); return; }
    const start = el.selectionStart ?? (value || "").length;
    const end = el.selectionEnd ?? start;
    const next = `${(value || "").slice(0, start)}${ins}${(value || "").slice(end)}`;
    onChange(next);
    requestAnimationFrame(() => { el.focus(); el.setSelectionRange(start + ins.length, start + ins.length); });
  };
  return (
    <div className="grid gap-1.5">
      <label className="text-[11px] font-bold uppercase tracking-[0.03em] text-[#6B6B73]">{label}{mark}</label>
      <textarea ref={ref} data-testid={testId} className={`form-input min-h-[96px] leading-relaxed ${unknown.length ? "!border-[#E0A800]" : ""}`}
        value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={hint} />
      <div className="flex flex-wrap gap-1">
        {(placeholders || []).map((p) => (
          <button key={p.token} type="button" data-testid={`${testId}-chip-${p.token}`} title={p.label}
            className="rounded-full border border-[#C9DDF7] bg-[#EFF4FF] px-2 py-0.5 font-mono text-[10.5px] text-[#0058CC] hover:bg-[#DCE9FB]"
            onClick={() => insert(p.token)}>{`{{${p.token}}}`}</button>
        ))}
      </div>
      {unknown.length > 0 ? (
        <p data-testid={`${testId}-unknown`} className="flex items-center gap-1 text-[11px] font-semibold text-[#8C4A00]">
          <AlertTriangle size={12} /> Placeholder tidak dikenal: {unknown.map((t) => `{{${t}}}`).join(", ")} — tidak akan terisi & ditolak saat simpan.
        </p>
      ) : value ? (
        <p className="flex items-center gap-1 text-[11px] text-[#1F7A45]"><CheckCircle2 size={12} /> Semua placeholder dikenal.</p>
      ) : null}
    </div>
  );
}

export default function PdfScriptTab({ config, patch, placeholders, mark = () => null }) {
  const notes = (placeholders || []).filter((p) => p.note);
  return (
    <div className="grid gap-3">
      <div className="flex items-start gap-2 rounded-lg bg-[#EFF4FF] px-3 py-2 text-[11.5px] text-[#0058CC]">
        <Info size={14} className="mt-0.5 shrink-0" />
        <span>Naskah tercetak pada dokumen NYATA. Klik chip untuk menyisipkan nilai dari dokumen (nomor, pihak, total…). Placeholder asing ditolak — dokumen resmi tidak boleh terbit dengan <code>{"{{apa_saja}}"}</code> mentah.</span>
      </div>
      <ScriptField label="Teks pembuka" testId="pdf-intro-text" value={config.intro_text} onChange={(v) => patch("intro_text", v)}
        placeholders={placeholders} mark={mark("intro_text")}
        hint="mis. Kepada Yth. {{pihak}}, bersama ini kami sampaikan {{judul}} No. {{nomor}} tertanggal {{tanggal}}." />
      <ScriptField label="Teks penutup" testId="pdf-closing-note" value={config.closing_note} onChange={(v) => patch("closing_note", v)}
        placeholders={placeholders} mark={mark("closing_note")}
        hint="mis. Pembayaran ke {{rekening_bank}} a.n. {{perusahaan}}. Terima kasih atas kepercayaan Anda." />
      {notes.length > 0 && (
        <ul className="grid gap-1 rounded-lg border border-kn-divider px-3 py-2 text-fs-12 text-kn-text-2" data-testid="pdf-token-notes">
          {notes.map((p) => (
            <li key={p.token} data-testid={`pdf-token-note-${p.token}`}>
              <code className="text-kn-action">{`{{${p.token}}}`}</code> — {p.note}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
