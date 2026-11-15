/**
 * InspectionRequestToggle — penanda "minta inspeksi" SAAT PENERIMAAN (keputusan pemilik 10 Nov 2026, FIX-6 sisa).
 *
 * Server sudah ada: `POST /inbound/tasks/{id}/inspection-request` {requested, reason} — alasan K-14, CAS status tugas
 * (hanya sebelum barang lepas karantina), beraudit, roll tugas ikut ditandai. Roll bertanda dirutekan ke gedung berperan
 * inspeksi saat draf penempatan dibuat (`putaway_draft_service`). Penanda dari baris PO (`source=po_line`) tampil di
 * sini juga dan bisa dibatalkan dengan alasan yang sama.
 */
import { useState } from "react";
import { Eye } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { askReason } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";
import { notifySuccess } from "../../../utils/feedback";
import StatusBadge from "../../../components/StatusBadge";

// Sama dengan server: `inbound_task_state.RECEIVABLE` + "qc_pending" (sebelum barang lepas karantina).
export const INSPECTION_EDITABLE = ["waiting_goods", "receiving", "qc_check", "qc_pending"];

export default function InspectionRequestToggle({ task, onTaskUpdated, touch = false }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const mark = task?.inspection_request || null;
  const on = !!mark?.requested;
  const editable = INSPECTION_EDITABLE.includes(task?.status);
  if (!task || (!on && !editable)) return null;

  const toggle = async () => {
    const reason = await askReason({
      title: on ? "Batalkan minta inspeksi?" : "Minta inspeksi untuk penerimaan ini?",
      message: on
        ? "Roll penerimaan ini tidak lagi otomatis diarahkan ke gedung inspeksi."
        : "Roll penerimaan ini otomatis diarahkan ke gedung inspeksi saat draf penempatan rak dibuat.",
      reasonLabel: "Alasan (tercatat di audit)",
      confirmLabel: on ? "Batalkan penanda" : "Minta inspeksi",
    });
    if (!reason) return;
    setBusy(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/inbound/tasks/${task.id}/inspection-request`, { requested: !on, reason });
      onTaskUpdated?.({ ...task, inspection_request: data?.inspection_request || null });
      notifySuccess(on ? "Penanda inspeksi dibatalkan" : "Minta inspeksi dicatat",
        `${data?.rolls_marked || 0} roll ikut ${on ? "dilepas penandanya" : "ditandai"}.`);
    } catch (e) {
      setErr(apiErrorText(e, "Gagal menyimpan penanda minta inspeksi."));
    } finally { setBusy(false); }
  };

  const source = mark?.source === "po_line" ? "dari baris PO" : mark?.by ? `oleh ${mark.by}` : "";
  return (
    <div className="kn-inspect-row" data-testid={`inbound-inspection-${task.id}`}>
      <div className="kn-inspect-info">
        {on ? (
          <StatusBadge tone="special" icon="tag" label="Minta inspeksi" testId={`inbound-inspection-badge-${task.id}`} />
        ) : (
          <span className="kn-inspect-hint"><Eye size={14} aria-hidden="true" /> Roll langsung ke gedung simpan</span>
        )}
        {on && (source || mark?.reason) && (
          <span className="kn-inspect-hint">{[source, mark?.reason].filter(Boolean).join(" · ")}</span>
        )}
      </div>
      {editable && (
        <button type="button" className={touch ? "secondary-button btn-touch w-full" : "secondary-button btn-sm"} onClick={toggle} disabled={busy}
          data-testid={`inbound-inspection-toggle-${task.id}`}>
          {on ? "Batalkan minta inspeksi" : "Minta inspeksi"}
        </button>
      )}
      {err && <p className="kn-inspect-err" role="alert" data-testid={`inbound-inspection-error-${task.id}`}>{err}</p>}
    </div>
  );
}
