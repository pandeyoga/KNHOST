import { useEffect, useState } from "react";
import { Loader2, MessageSquarePlus, Search, Trash2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { toast } from "../../hooks/use-toast";
import { deleteSession, fetchSessions } from "./tanyaApi";
import { fmtDateTime } from "./tanyaFormat";

function SessionRow({ s, active, onOpen, onDelete }) {
  const [confirm, setConfirm] = useState(false);
  return (
    <div className={`tanya-sess ${active ? "active" : ""}`} data-testid={`tanya-session-${s.id}`}>
      <button type="button" className="tanya-sess-main" onClick={() => onOpen(s.id)} data-testid={`tanya-session-open-${s.id}`}>
        <span className="tanya-tpl-title">{s.title || "Percakapan"}</span>
        <span className="tanya-tpl-prompt">{fmtDateTime(s.updated_at)} · {s.questions || 0} pertanyaan</span>
      </button>
      {confirm ? (
        <Button size="sm" variant="destructive" onClick={() => onDelete(s.id)} onBlur={() => setConfirm(false)} data-testid={`tanya-session-confirm-delete-${s.id}`}>Hapus?</Button>
      ) : (
        <Button size="sm" variant="ghost" onClick={() => setConfirm(true)} aria-label="Hapus percakapan" data-testid={`tanya-session-delete-${s.id}`}><Trash2 className="h-4 w-4" /></Button>
      )}
    </div>
  );
}

/** Riwayat percakapan: cari, buka & lanjutkan, hapus, mulai baru. `refreshKey` berubah → muat ulang. */
export function TanyaHistory({ activeId, refreshKey, onOpen, onNew, onDeleted }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState(null);
  useEffect(() => {
    const t = setTimeout(() => fetchSessions(q).then(setItems).catch(() => setItems([])), 250);
    return () => clearTimeout(t);
  }, [q, refreshKey]);
  const remove = async (id) => {
    try {
      await deleteSession(id);
      setItems((l) => l.filter((s) => s.id !== id));
      onDeleted(id);
      toast({ title: "Percakapan dihapus" });
    } catch {
      toast({ title: "Gagal menghapus percakapan", variant: "destructive" });
    }
  };
  return (
    <div className="tanya-history" data-testid="tanya-history">
      <Button className="w-full" onClick={onNew} data-testid="tanya-new-chat"><MessageSquarePlus className="h-4 w-4" /> Percakapan baru</Button>
      <div className="tanya-search">
        <Search className="h-4 w-4" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari percakapan…" data-testid="tanya-history-search" />
      </div>
      {items === null && <div className="tanya-loading"><Loader2 className="h-4 w-4 animate-spin" /> Memuat riwayat…</div>}
      {items?.length === 0 && <div className="tanya-note" data-testid="tanya-history-empty">{q ? "Tidak ada percakapan yang cocok." : "Belum ada percakapan."}</div>}
      {items?.map((s) => <SessionRow key={s.id} s={s} active={s.id === activeId} onOpen={onOpen} onDelete={remove} />)}
    </div>
  );
}
