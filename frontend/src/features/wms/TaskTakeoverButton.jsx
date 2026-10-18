import { useState } from "react";
import { UserCheck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { toast } from "sonner";

/** P01 IMP-20 — supervisor mengambil alih tugas lokasi lain dengan alasan tercatat. */
export function TaskTakeoverButton({ task, scope, onDone }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  if (!task || !scope?.supervisor) return null;
  const submit = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/wms/tasks/${task.id}/takeover`, { reason });
      toast.success("Tugas diambil alih — alasan tercatat di riwayat tugas.");
      setOpen(false); setReason(""); onDone?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengambil alih tugas.");
    } finally { setBusy(false); }
  };
  if (!open) return (
    <button data-testid="wms-task-takeover-button" className="secondary-button" onClick={() => setOpen(true)}>
      <UserCheck size={14} /> Ambil Alih
    </button>
  );
  return (
    <div className="flex w-full flex-wrap items-center gap-2" data-testid="wms-task-takeover-form">
      <input data-testid="wms-task-takeover-reason" className="form-input min-w-[220px] flex-1" value={reason}
             onChange={(e) => setReason(e.target.value)} placeholder="Alasan mengambil alih (wajib, min. 5 huruf)" />
      <button data-testid="wms-task-takeover-submit" className="primary-button" disabled={busy || reason.trim().length < 5} onClick={submit}>Simpan</button>
      <button data-testid="wms-task-takeover-cancel" className="secondary-button" onClick={() => setOpen(false)}>Batal</button>
    </div>
  );
}
