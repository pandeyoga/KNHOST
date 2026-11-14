/**
 * Keputusan owner 2026-10-21 — Nota Kredit otomatis dari batal item Pesanan Khusus pada SO yang sudah terbit.
 * Nota lahir berstatus "Menunggu Finance"; pemegang `finance_amendment.review_credit_note` (bawaan Finance, Manager,
 * Admin) boleh mengoreksi nilainya (dengan alasan),
 * menerbitkan, atau membatalkannya. Server tetap penentu izin & aturannya.
 */
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { formatCurrency } from "../../../utils/formatters";
import { can } from "../../../config/roles";
import { errText, reviewCreditNote } from "./amendmentApi";
import { NoteStatusPill } from "./CreditNoteBadges";

// PK-32 — status nota memakai kosakata bersama (`CreditNoteBadges`: Menunggu Finance · Terbit · Selesai · Batal);
// kelebihan bayar dan bagian tertangguh dengan kalimat yang sama dengan nota amandemen.
export function OdCancelNoteInfo({ note }) {
  const pending = note.status === "pending_finance";
  return (
    <div className="mt-0.5 space-y-0.5 text-fs-12 text-kn-text-2" data-testid={`od-note-info-${note.id}`}>
      <NoteStatusPill note={note} testId={`od-note-status-${note.id}`} />
      {note.excess_payment > 0 && (
        <p data-testid={`od-note-excess-${note.id}`}>
          Kelebihan bayar {formatCurrency(note.excess_payment)} tetap sebagai uang muka pelanggan.
        </p>
      )}
      {Number(note.deferred_net || 0) > 0 && (
        <p data-testid={`od-note-deferred-${note.id}`}>
          {formatCurrency(note.deferred_net)} belum mengurangi pendapatan karena barangnya belum dikirim.
        </p>
      )}
      {pending && note.revenue_recognized && (
        <p>Pendapatan pesanan sudah diakui: saat diterbitkan dibuat jurnal koreksi pendapatan &amp; PPN.</p>
      )}
      {(note.corrections || []).map((c, i) => (
        <p key={i}>Dikoreksi {c.by}: {formatCurrency(c.from)} → {formatCurrency(c.to)} · {c.reason}</p>
      ))}
    </div>
  );
}

export default function OdCancelNoteActions({ note, currentUser, onDone }) {
  const [mode, setMode] = useState("");          // "" | "adjust" | "void"
  const [amount, setAmount] = useState(String(note.gross_amount ?? ""));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (note.status !== "pending_finance" || !can(currentUser?.permissions, "finance_amendment", "review_credit_note")) return null;

  const send = async (body) => {
    setBusy(true); setErr("");
    try { await reviewCreditNote(note.id, body); setMode(""); setReason(""); onDone?.(); }
    catch (e) { setErr(errText(e, "Gagal memproses nota.")); }
    finally { setBusy(false); }
  };
  return (
    <div className="mt-1 space-y-1" data-testid={`od-note-actions-${note.id}`}>
      <div className="flex flex-wrap gap-1">
        <button type="button" className="secondary-button !py-0.5 !text-[10px]" disabled={busy} data-testid={`od-note-issue-${note.id}`}
                onClick={() => send({ action: "issue" })}>Terbitkan</button>
        <button type="button" className="secondary-button !py-0.5 !text-[10px]" disabled={busy} data-testid={`od-note-adjust-${note.id}`}
                onClick={() => setMode(mode === "adjust" ? "" : "adjust")}>Koreksi nilai</button>
        <button type="button" className="secondary-button !py-0.5 !text-[10px] !text-[#A8221A]" disabled={busy} data-testid={`od-note-void-${note.id}`}
                onClick={() => setMode(mode === "void" ? "" : "void")}>Batalkan nota</button>
        {busy && <Loader2 size={12} className="animate-spin" />}
      </div>
      {mode && (
        <div className="space-y-1 rounded border border-[#E5EEFB] bg-white p-1.5">
          {mode === "adjust" && (
            <input className="field w-full !py-1 text-[10.5px]" inputMode="decimal" value={amount} data-testid={`od-note-amount-${note.id}`}
                   onChange={(e) => setAmount(e.target.value)} placeholder="Nilai nota (Rp, termasuk PPN)" />
          )}
          <input className="field w-full !py-1 text-[10.5px]" value={reason} data-testid={`od-note-reason-${note.id}`}
                 onChange={(e) => setReason(e.target.value)} placeholder="Alasan (min. 5 huruf)" />
          <button type="button" className="primary-button !py-0.5 !text-[10px]" disabled={busy || reason.trim().length < 5}
                  data-testid={`od-note-confirm-${note.id}`}
                  onClick={() => send(mode === "adjust" ? { action: "adjust", gross_amount: Number(amount), note: reason.trim() }
                                                        : { action: "void", note: reason.trim() })}>
            {mode === "adjust" ? "Simpan koreksi" : "Batalkan nota"}
          </button>
        </div>
      )}
      {err && <p className="text-[10px] text-[#A8221A]" data-testid={`od-note-error-${note.id}`}>{err}</p>}
    </div>
  );
}
