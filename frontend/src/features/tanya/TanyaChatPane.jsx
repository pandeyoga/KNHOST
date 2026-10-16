import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowDown, Sparkles } from "lucide-react";
import { TanyaChatBox } from "./TanyaChatBox";

/** Tinggi panel = sisa layar dari posisinya (pesan bergulir di dalam, komposer selalu di dasar — tak pernah tumpang tindih). */
export function useFillHeight(ref, gap = 16, ready = true) {
  useLayoutEffect(() => {
    const fit = () => {
      const el = ref.current;
      if (!el) return;
      const g = window.matchMedia("(max-width: 900px)").matches ? gap + 56 : gap;
      el.style.height = `${Math.max(380, window.innerHeight - el.getBoundingClientRect().top - window.scrollY - g)}px`;
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [ref, gap, ready]);
}

export function TanyaWelcome({ prompts, onPick }) {
  return (
    <div className="tanya-welcome" data-testid="tanya-empty-state">
      <div className="tanya-welcome-mark"><Sparkles className="h-5 w-5" /></div>
      <h2 className="tanya-welcome-title">Apa yang ingin Anda ketahui hari ini?</h2>
      <p className="tanya-welcome-sub">Angka dihitung server sesuai hak akses Anda — lengkap dengan grafik, tabel, dan unduhan Excel.</p>
      <div className="tanya-welcome-prompts">
        {prompts.map((p, i) => (
          <button key={i} type="button" className="tanya-welcome-prompt" onClick={() => onPick(p)} data-testid={`tanya-welcome-prompt-${i}`}>{p.label}</button>
        ))}
      </div>
    </div>
  );
}

/** Panel chat gaya Claude: area pesan bergulir + komposer menempel di bawah. */
export function TanyaChatPane({ children, scrollKey, composer }) {
  const paneRef = useRef(null);
  const scrollRef = useRef(null);
  const [atBottom, setAtBottom] = useState(true);
  useFillHeight(paneRef);
  const toBottom = (smooth = true) => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  useEffect(() => { if (atBottom) toBottom(); }, [scrollKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const onScroll = (e) => {
    const el = e.currentTarget;
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  };
  return (
    <div className="tanya-chat" ref={paneRef} data-testid="tanya-chat-pane">
      <div className="tanya-scroll" ref={scrollRef} onScroll={onScroll} data-testid="tanya-chat-scroll">
        <div className="tanya-col">{children}</div>
      </div>
      {!atBottom && (
        <button type="button" className="tanya-to-bottom" onClick={() => toBottom()} aria-label="Ke pesan terbaru" data-testid="tanya-scroll-bottom">
          <ArrowDown className="h-4 w-4" />
        </button>
      )}
      <div className="tanya-composer-wrap"><div className="tanya-col"><TanyaChatBox {...composer} /></div></div>
    </div>
  );
}
