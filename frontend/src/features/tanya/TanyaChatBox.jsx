import { useEffect, useRef, useState } from "react";
import { ArrowUp, Loader2 } from "lucide-react";

/** Komposer gaya Claude: textarea tumbuh otomatis, tombol kirim bulat di dalam kotak. */
export function TanyaChatBox({ status, busy, statusText, onAsk, entityLabel }) {
  const [q, setQ] = useState("");
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [q]);
  const submit = (e) => {
    e.preventDefault();
    if (!q.trim() || busy) return;
    onAsk(q.trim());
    setQ("");
  };
  const note = busy ? statusText || "Memproses…"
    : status?.chat_enabled ? `Jawaban memakai data ${entityLabel || "entitas aktif"} sesuai hak akses Anda.`
      : "Chat AI belum aktif — pertanyaan diarahkan ke laporan yang cocok.";
  return (
    <form className="tanya-composer" onSubmit={submit} data-testid="tanya-chat-form">
      <div className="tanya-composer-box">
        <textarea ref={ref} value={q} rows={1} onChange={(e) => setQ(e.target.value)} data-testid="tanya-chat-input"
          className="tanya-composer-input" placeholder="Tanya apa saja tentang penjualan, stok, piutang…"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) submit(e); }} />
        <button type="submit" className="tanya-send" disabled={busy || !q.trim()} aria-label="Kirim pertanyaan" data-testid="tanya-chat-submit">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" strokeWidth={2.5} />}
        </button>
      </div>
      <div className={`tanya-composer-note ${busy ? "busy" : ""}`} data-testid="tanya-chat-status">{note}</div>
    </form>
  );
}
