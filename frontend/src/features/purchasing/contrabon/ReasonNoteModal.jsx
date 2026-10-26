/**
 * FASE G-7 — modal **alasan + catatan** untuk sengketa & pembatalan kontrabon.
 *
 * Sengketa WAJIB berlabel (backend menolak tanpa `reason_code`); pembatalan cukup
 * catatan. Satu modal untuk keduanya supaya kalimat penolakan & jejaknya seragam.
 *
 * Fase 4 · R2 (L-03) — `.modal-card` buatan sendiri → `FormModal` baku. Isian & testid tetap.
 */
import { useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { KNSelect } from "../../../components/KNSelect";
import { apiErrorText } from "../../../utils/apiError";

const COPY = {
  dispute: {
    title: "Sengketakan kontrabon",
    subtitle: "Faktur supplier keliru — kontrabon ditahan sampai supplier mengoreksinya.",
    button: "Sengketakan",
    needReason: true,
    hint: "Setelah supplier mengoreksi faktur, kontrabon bisa diajukan ulang tanpa membuat "
      + "dokumen baru.",
  },
  cancel: {
    title: "Batalkan kontrabon",
    subtitle: "Faktur yang tertahan akan DILEPAS kembali sehingga bisa dikontrabon ulang.",
    button: "Batalkan kontrabon",
    needReason: false,
    hint: "Kontrabon yang sudah ada pembayarannya tidak bisa dibatalkan — pakai Pusat Kasus "
      + "Keuangan bila uangnya perlu dikoreksi.",
  },
};

export default function ReasonNoteModal({ cb, kind, meta, onClose, onDone, onError }) {
  const copy = COPY[kind] || COPY.dispute;
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const reasonOptions = useMemo(
    () => (meta?.reasons || []).map((r) => ({ value: r.code, label: r.label })), [meta]);

  async function submit() {
    setSaving(true); setErr("");
    try {
      const r = await axios.post(`${API}/contra-bons/${cb.id}/${kind}`, {
        reason_code: reason, note: note.trim(),
      });
      onDone(r.data);
    } catch (e) {
      setErr(apiErrorText(e));
      onError?.(e);
    } finally { setSaving(false); }
  }

  return (
    <FormModal open onClose={onClose} title={copy.title} icon={AlertTriangle}
      subtitle={`${cb.number} · ${cb.supplier_name} — ${copy.subtitle}`}
      testId={`cb-${kind}-modal`} busy={saving}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Tutup</button>
          <button type="button" className={kind === "cancel" ? "danger-button" : "primary-button"}
            data-testid={`cb-${kind}-submit`}
            disabled={saving || (copy.needReason && !reason)} onClick={submit}>
            {saving ? "Memproses…" : copy.button}
          </button>
        </div>
      )}>
      {err && (
        <ErrorNotice message={err} onDismiss={() => setErr("")} testId={`cb-${kind}-error`} />
      )}

      <div className="space-y-3">
        {copy.needReason && (
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
              Alasan berlabel (wajib)
            </label>
            <KNSelect data-testid={`cb-${kind}-reason`} value={reason} onValueChange={setReason}
              options={reasonOptions} className="field" placeholder="Pilih alasan" />
          </div>
        )}
        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Catatan</label>
          <textarea data-testid={`cb-${kind}-note`} className="textarea w-full" rows={3}
            value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="Ceritakan apa yang keliru supaya rekan lain paham tanpa bertanya." />
        </div>
        <p className="text-[10.5px] text-[#9A9BA3]">{copy.hint}</p>
      </div>
    </FormModal>
  );
}
