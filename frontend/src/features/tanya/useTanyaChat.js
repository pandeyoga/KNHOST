import { useCallback, useState } from "react";
import { toast } from "../../hooks/use-toast";
import { askChat, chatErrorText, fetchSession } from "./tanyaApi";
import { turnsToThread } from "./tanyaFormat";

/** State percakapan Tanya KN: kirim pertanyaan (SSE), buka sesi lama, mulai baru. */
export function useTanyaChat(onSessionsChanged) {
  const [thread, setThread] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState("");
  const patch = (id, p) => setThread((t) => t.map((e) => (e.id === id ? { ...e, ...p } : e)));

  const ask = async (question, context = null) => {
    const id = `q-${Date.now()}`;
    setThread((t) => [...t, { id, question, context, pending: true }]);
    setBusy(true); setStatusText("Menghubungi asisten…");
    let text = "";
    let frame = null;
    const stopFrame = () => { if (frame) cancelAnimationFrame(frame); frame = null; };
    const flush = () => { frame = null; patch(id, { streamText: text }); };
    const rids = [];
    try {
      await askChat({ question, session_id: sessionId, ...(context ? { context } : {}) }, (ev) => {
        if (ev.type === "status") setStatusText(ev.text);
        if (ev.type === "delta") { text += ev.text; if (!frame) frame = requestAnimationFrame(flush); }
        if (ev.type === "delta_reset") { text = ""; stopFrame(); patch(id, { streamText: "" }); }
        if (ev.type === "result" && ev.result_id) rids.push(ev.result_id);
        if (ev.type !== "done") return;
        stopFrame();
        const final = typeof ev.text === "string" ? ev.text : text;
        if (ev.session_id) setSessionId(ev.session_id);
        if (ev.error) toast({ title: ev.error, variant: "destructive" });
        else if (ev.disabled) patch(id, { suggestions: ev.suggestions || [], notice: final, streamText: null });
        else patch(id, { streamText: null, answer: { kind: "chat", question, text: final, verification: ev.verification, sessionId: ev.session_id,
          resultIds: [...new Set([...rids, ...(ev.result_ids || [])])] } });
      });
    } catch (e) {
      toast({ title: "Pertanyaan gagal dikirim", description: chatErrorText(e), variant: "destructive" });
      patch(id, { error: chatErrorText(e) });
    } finally {
      stopFrame();
      patch(id, { pending: false, streamText: null });
      setBusy(false);
      onSessionsChanged?.();
    }
  };

  const openSession = useCallback(async (id) => {
    try {
      const s = await fetchSession(id);
      setThread(turnsToThread(s));
      setSessionId(id);
    } catch {
      toast({ title: "Percakapan tidak dapat dibuka", variant: "destructive" });
    }
  }, []);

  const reset = useCallback(() => { setThread([]); setSessionId(null); }, []);
  return { thread, sessionId, busy, statusText, ask, openSession, reset };
}
