// P17 — pita "badan usaha terarsip: baca saja" (keputusan pemilik: arsip tetap bisa dibuka).
import { Archive, LogOut } from "lucide-react";

import { entityFull } from "../utils/entityLabel";

export default function ArchivedReadOnlyBanner({ entity, onExit }) {
  return (
    <div data-testid="archived-readonly-banner" className="scope-readonly-banner">
      <Archive size={14} className="shrink-0 text-[#8C4A00]" />
      <div className="min-w-0 flex-1">
        <p className="scope-readonly-title">
          <strong data-testid="archived-readonly-name">{entityFull(entity)}</strong> sudah diarsipkan — data hanya bisa dibaca.
        </p>
        <p className="scope-readonly-text">
          Dokumen lama tetap bisa dilihat dan dicetak. Menyimpan, mengubah, atau membuat transaksi baru ditolak.
        </p>
      </div>
      <div className="scope-readonly-actions">
        <button type="button" data-testid="archived-readonly-exit" className="scope-readonly-pick" onClick={onExit}>
          <LogOut size={11} /> Kembali ke badan usaha aktif
        </button>
      </div>
    </div>
  );
}
