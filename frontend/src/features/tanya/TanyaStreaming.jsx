import { Loader2 } from "lucide-react";
import { TanyaMarkdown } from "./TanyaMarkdown";
import { splitAnswer } from "./tanyaFormat";

const CARET = "\u258D";

/** Potong blok ``` yang belum tertutup supaya JSON kn-* setengah jadi tidak dirender. */
function closedPart(text) {
  const n = (text.match(/```/g) || []).length;
  return n % 2 ? text.slice(0, text.lastIndexOf("```")) : text;
}

/** Jawaban yang sedang ditulis: teks tampil kata demi kata, grafik/tabel muncul utuh setelah jawaban selesai. */
export function TanyaStreaming({ text, statusText }) {
  const closed = closedPart(text);
  const parts = splitAnswer(closed);
  const last = parts.length - 1;
  return (
    <article className="tanya-answer tanya-streaming section-card" data-testid="tanya-streaming" aria-live="polite">
      <div className="tanya-kicker"><Loader2 className="h-3.5 w-3.5 animate-spin" /> {statusText || "Menulis jawaban…"}</div>
      {parts.map((p, i) => {
        if (p.kind === "text") return <TanyaMarkdown key={i} text={i === last ? `${p.text}${CARET}` : p.text} testId={`tanya-stream-text-${i}`} />;
        if (p.kind === "kn-followups") return null;
        return <div key={i} className="tanya-stream-block" data-testid={`tanya-stream-block-${i}`}>Menyiapkan {p.kind === "kn-chart" ? "grafik" : p.kind === "kn-action" ? "draf tindakan" : "tabel"}…</div>;
      })}
      {closed !== text && <div className="tanya-stream-block" data-testid="tanya-stream-block-pending">Menyiapkan data…</div>}
    </article>
  );
}
