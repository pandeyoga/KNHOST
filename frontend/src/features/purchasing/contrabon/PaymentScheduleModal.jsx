/**
 * FASE G-7 — modal **jadwalkan pembayaran** kontrabon yang sudah disetujui.
 * Tanggal rencana inilah yang dipakai KPI “jatuh tempo ≤ 7 hari” di layar induk.
 *
 * Fase 3 · P4 (L-03) — `.modal-card` buatan sendiri → `FormModal` baku (layar penuh 1 kolom di HP). Isian tetap.
 */
import { useEffect, useMemo, useState } from "react";
import KNDatePicker from "@/components/KNDatePicker";
import { CalendarCheck } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { KNSelect } from "../../../components/KNSelect";
import { apiErrorText } from "../../../utils/apiError";
import { METHOD_OPTIONS, fmtDate, todayISO } from "./contraBonApi";

export default function PaymentScheduleModal({ cb, onClose, onSaved, onError }) {
  const cur = cb.schedule || {};
  const [when, setWhen] = useState(cur.planned_payment_date || cb.due_date || todayISO());
  const [method, setMethod] = useState(cur.method || "transfer");
  const [accountId, setAccountId] = useState(cur.bank_account_id || "");
  const [notes, setNotes] = useState(cur.notes || "");
  const [accounts, setAccounts] = useState([]);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await axios.get(`${API}/bank-accounts`);
        const list = Array.isArray(r.data) ? r.data : (r.data?.items || []);
        if (alive) setAccounts(list);
      } catch (e) { if (alive) setErr(apiErrorText(e)); }
    })();
    return () => { alive = false; };
  }, []);

  const accountOptions = useMemo(() => accounts.map((a) => ({
    value: a.id, label: `${a.name}${a.bank_name ? ` · ${a.bank_name}` : ""}`,
  })), [accounts]);

  async function save() {
    setSaving(true); setErr("");
    try {
      const r = await axios.post(`${API}/contra-bons/${cb.id}/schedule`, {
        planned_payment_date: when,
        method,
        bank_account_id: accountId,
        notes: notes.trim(),
      });
      onSaved(r.data);
    } catch (e) {
      setErr(apiErrorText(e));
      onError?.(e);
    } finally { setSaving(false); }
  }

  // Fase 3 · P4 — sengaja TANPA `onSubmit` (bukan <form>): tombol × di ErrorNotice tidak ber-`type`, jadi di
  // dalam <form> ia ikut mengirim. Aksi lewat `footer`.
  return (
    <FormModal open onClose={onClose} title="Jadwalkan pembayaran" icon={CalendarCheck}
      subtitle={`${cb.number} · ${cb.supplier_name}${cb.due_date ? ` — jatuh tempo faktur ${fmtDate(cb.due_date)}` : ""}`}
      testId="cb-schedule-modal" busy={saving}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Batal</button>
          <button type="button" className="primary-button" data-testid="cb-schedule-save"
            disabled={saving || !when} onClick={save}>
            {saving ? "Menyimpan…" : "Simpan jadwal bayar"}
          </button>
        </div>
      )}>
      {err && (
        <ErrorNotice message={err} onDismiss={() => setErr("")} testId="cb-schedule-error" />
      )}

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
            Tanggal rencana pembayaran (wajib)
          </label>
          <KNDatePicker data-testid="cb-schedule-date" value={when} onChange={setWhen} clearable={false} />
          <p className="mt-1 text-[10px] text-[#8E8E93]">
            Tanggal ini yang dipakai KPI “jatuh tempo ≤ 7 hari” dan proyeksi arus kas.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Cara bayar</label>
            <KNSelect data-testid="cb-schedule-method" value={method} onValueChange={setMethod}
              options={METHOD_OPTIONS} className="field" />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
              Rekening rencana
            </label>
            <KNSelect data-testid="cb-schedule-account" value={accountId}
              onValueChange={setAccountId} options={accountOptions} className="field"
              placeholder="Pilih rekening" />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Catatan</label>
          <textarea data-testid="cb-schedule-notes" className="textarea w-full" rows={2}
            value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="Mis. dibayar bersama batch transfer Selasa pagi." />
        </div>
      </div>
    </FormModal>
  );
}
