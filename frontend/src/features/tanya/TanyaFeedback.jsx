import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import { toast } from "../../hooks/use-toast";
import { sendFeedback } from "./tanyaApi";

/** 👍 langsung tersimpan; 👎 membuka kolom komentar (bahan set evaluasi). */
export function TanyaFeedback({ payload }) {
  const [sent, setSent] = useState("");
  const [asking, setAsking] = useState(false);
  const [comment, setComment] = useState("");
  const send = async (rating, text = "") => {
    try {
      await sendFeedback({ ...payload, rating, comment: text });
      setSent(rating); setAsking(false);
      toast({ title: "Terima kasih, masukan tersimpan" });
    } catch {
      toast({ title: "Masukan gagal disimpan", variant: "destructive" });
    }
  };
  return (
    <div className="tanya-feedback-wrap">
      <div className="tanya-feedback">
        <Button size="sm" variant={sent === "up" ? "default" : "ghost"} onClick={() => send("up")} data-testid="tanya-feedback-up" aria-label="Jawaban membantu"><ThumbsUp className="h-4 w-4" /></Button>
        <Button size="sm" variant={sent === "down" || asking ? "default" : "ghost"} onClick={() => setAsking((v) => !v)} data-testid="tanya-feedback-down" aria-label="Jawaban kurang tepat"><ThumbsDown className="h-4 w-4" /></Button>
      </div>
      {asking && (
        <div className="tanya-feedback-box" data-testid="tanya-feedback-comment-box">
          <Textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Apa yang kurang tepat? (opsional)" data-testid="tanya-feedback-comment" />
          <Button size="sm" onClick={() => send("down", comment)} data-testid="tanya-feedback-submit">Kirim masukan</Button>
        </div>
      )}
    </div>
  );
}
