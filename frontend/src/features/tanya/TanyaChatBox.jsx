import { useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowUp, Building2, FileText, Loader2, X } from "lucide-react";

const MODES = [["umum", "Umum"], ["keuangan", "Keuangan"]];

/** AG-T2 — pilihan mode (hanya bila Asisten Keuangan menyala untuk akun ini) + banner PT mode Keuangan. */
function TanyaModeBar({ mode, onMode, financeScope, chatOn = true }) {
  const combined = financeScope?.combined;
  // Cek layar 14 Nov — mode Keuangan hanya menjawab lewat chat AI: selama chat belum menyala pilihannya mati dengan
  // alasan tertulis (bukan aktif lalu gagal saat dikirim).
  return (
    <div className="tanya-mode-bar" data-testid="tanya-mode-bar">
      <div className="tanya-mode" role="radiogroup" aria-label="Mode tanya" data-testid="tanya-mode">
        {MODES.map(([k, label]) => (
          <button key={k} type="button" role="radio" aria-checked={mode === k} data-testid={`tanya-mode-${k}`}
            disabled={k === "keuangan" && !chatOn}
            className={`tanya-mode-opt btn-sm ${mode === k ? "active" : ""}`} onClick={() => onMode(k)}>{label}</button>
        ))}
      </div>
      {!chatOn && (
        <span className="text-fs-12 text-kn-text-2" data-testid="tanya-finance-off-reason">
          Mode Keuangan aktif setelah chat AI menyala.
        </span>
      )}
      {mode === "keuangan" && chatOn && (
        <div className={`tanya-mode-scope ${combined ? "combined" : ""}`} data-testid="tanya-finance-scope">
          {combined ? <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> : <Building2 className="h-3.5 w-3.5" aria-hidden="true" />}
          <span>{combined ? "Semua PT — angka gabungan belum dieliminasi" : `Menjawab untuk: ${financeScope?.label || "PT aktif"}`}</span>
        </div>
      )}
    </div>
  );
}

/** Komposer gaya Claude: textarea tumbuh otomatis, tombol kirim bulat di dalam kotak. */
export function TanyaChatBox({ status, busy, statusText, onAsk, entityLabel, context, onClearContext,
  mode = "umum", onMode, financeScope }) {
  const [q, setQ] = useState("");
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [q]);
  useEffect(() => { if (context) ref.current?.focus(); }, [context]);
  const submit = (e) => {
    e.preventDefault();
    if (!q.trim() || busy) return;
    onAsk(q.trim());
    setQ("");
  };
  const finance = Boolean(status?.finance_enabled && status?.chat_enabled) && mode === "keuangan";
  const note = busy ? statusText || "Memproses…"
    : finance ? "Angka diperiksa terhadap data sebelum jawaban ditampilkan."
      : status?.chat_enabled ? `Jawaban memakai data ${entityLabel || "entitas aktif"} sesuai hak akses Anda.`
        : "Chat AI belum aktif — pertanyaan diarahkan ke laporan yang cocok.";
  const placeholder = context ? `Tanya tentang ${context.label || context.id}…`
    : finance ? "Tanya soal laba rugi, neraca, piutang, hutang, kas, pajak…"
      : "Tanya apa saja tentang penjualan, stok, piutang…";
  return (
    <form className="tanya-composer" onSubmit={submit} data-testid="tanya-chat-form">
      {status?.finance_enabled && onMode && (
        <TanyaModeBar mode={mode} onMode={onMode} financeScope={financeScope} chatOn={Boolean(status?.chat_enabled)} />
      )}
      {context && (
        <div className="tanya-context-chip" data-testid="tanya-context-chip">
          <FileText className="h-3.5 w-3.5" />
          <span>Konteks: <b>{context.label || context.id}</b></span>
          <button type="button" onClick={onClearContext} aria-label="Hapus konteks" data-testid="tanya-context-clear"><X className="h-3.5 w-3.5" /></button>
        </div>
      )}
      <div className="tanya-composer-box">
        <textarea ref={ref} value={q} rows={1} onChange={(e) => setQ(e.target.value)} data-testid="tanya-chat-input"
          className="tanya-composer-input" placeholder={placeholder}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) submit(e); }} />
        <button type="submit" className="tanya-send" disabled={busy || !q.trim()} aria-label="Kirim pertanyaan" data-testid="tanya-chat-submit">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" strokeWidth={2.5} />}
        </button>
      </div>
      <div className={`tanya-composer-note ${busy ? "busy" : ""}`} data-testid="tanya-chat-status">{note}</div>
    </form>
  );
}
