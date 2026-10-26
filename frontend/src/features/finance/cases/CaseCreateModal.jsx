/**
 * FASE G-9 — CaseCreateModal: laporkan kasus keuangan baru (manual).
 *
 * Jenis kasus dipilih dari playbook yang DIKIRIM BACKEND, sehingga layar tidak pernah
 * menawarkan jenis yang tidak punya mesin penyelesaian.
 *
 * Fase 4 · R2 (L-03) — `.modal-overlay` + `.modal-panel` buatan sendiri → `FormModal` baku (layar penuh 1 kolom di HP —
 * Kasus Keuangan dibuka juga dari aplikasi HP). Isian, galat di dalam pop-up & testid tetap (`case-create-modal` kini
 * kartu pop-up, `case-create-*`).
 */
import MoneyInput from "../../../components/MoneyInput";
import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { KNSelect } from "../../../components/KNSelect";
import { apiErrorText } from "../../../utils/apiError";
import { parseDecimal } from "../../../utils/decimalInput";

export default function CaseCreateModal({ playbooks, customers, suppliers, onClose,
  onCreated, onError }) {
  const [caseType, setCaseType] = useState(playbooks[0]?.code || "");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [saving, setSaving] = useState(false);
  // KN-G9-ERR-SILENT — modal wajib menampilkan penolakannya sendiri (bilah error layar
  // induk tertutup modal ini), mis. 403 "kasus PT lain" atau 400 "kasus kembar".
  const [err, setErr] = useState("");

  const pb = useMemo(() => playbooks.find((p) => p.code === caseType) || null,
    [playbooks, caseType]);
  const typeOptions = useMemo(
    () => playbooks.map((p) => ({ value: p.code, label: p.label })), [playbooks]);
  // UAT 24 Okt (audit UI tahap 2) — G1-36: nama kembar (QA Cust A/B ×2) tak bisa dibedakan → "Nama · Kode · Kota".
  const partyLabel = (x) => [x.name || x.id, x.code, x.city].filter(Boolean).join(" · ");
  const custOptions = useMemo(
    () => customers.map((c) => ({ value: c.id, label: partyLabel(c) })), [customers]);
  const supOptions = useMemo(
    () => suppliers.map((s) => ({ value: s.id, label: partyLabel(s) })), [suppliers]);
  // G1-36 — isian wajib: jenis kasus & cerita kejadian (≥ 5 huruf).
  // Keputusan pemilik B4 (26 Okt) — nominal OPSIONAL: boleh kosong/0 (mis. kasus dokumen/data tanpa angka);
  // server memang menerima 0 (`amount ≥ 0`) → batas waktu memakai tingkat nominal terendah.
  const amountNum = parseDecimal(String(amount ?? "")) || 0;
  const canSubmit = !!caseType && amountNum >= 0 && description.trim().length >= 5;

  async function submit() {
    setSaving(true); setErr("");
    try {
      const r = await axios.post(`${API}/finance-cases`, {
        case_type: caseType,
        title: title.trim() || pb?.label || "",
        description: description.trim(),
        amount: amountNum,
        customer_id: customerId,
        supplier_id: supplierId,
      });
      onCreated(r.data);
    } catch (e) {
      setErr(apiErrorText(e));
      onError?.(e);
    } finally { setSaving(false); }
  }

  return (
    <FormModal open onClose={onClose} icon={Plus} title="Laporkan kasus keuangan" testId="case-create-modal"
      busy={saving}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Batal</button>
          <button type="button" className="primary-button" data-testid="case-create-submit"
            disabled={saving || !canSubmit} onClick={submit}
            title={canSubmit ? undefined : "Lengkapi jenis kasus dan cerita kejadian (minimal 5 huruf)"}>
            {saving ? "Menyimpan…" : "Buat kasus"}
          </button>
        </div>
      )}>
      {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="case-create-error" />}
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
            Jenis kasus <span className="text-[#C0392B]">*</span>
          </label>
          <KNSelect data-testid="case-create-type" value={caseType}
            onValueChange={setCaseType} options={typeOptions} />
          {pb && (
            <p className="mt-1 rounded-md bg-[#F2F7FF] px-2 py-1.5 text-[11px] text-[#1C1C1E]">
              {pb.question}
            </p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
            Judul singkat <span className="font-normal text-[#8E8E93]">(opsional — bawaan: nama jenis kasus)</span>
          </label>
          <input data-testid="case-create-title" className="input-field w-full"
            value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder={pb?.label || "Ringkas masalahnya dalam satu baris"} />
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
            Nominal yang dipertaruhkan (Rp) <span className="font-normal text-[#8E8E93]">(opsional)</span>
          </label>
          <MoneyInput testId="case-create-amount" className="input-field w-full" value={amount} onChange={setAmount} placeholder="Boleh dikosongkan" />
          <p className="mt-1 text-[10px] text-[#8E8E93]">
            Nominal menentukan batas waktu penyelesaian & apakah perlu persetujuan. Kosong = Rp 0 (batas waktu tingkat terendah).
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
              Pelanggan <span className="font-normal text-[#8E8E93]">(opsional)</span>
            </label>
            <KNSelect data-testid="case-create-customer" value={customerId}
              onValueChange={setCustomerId} options={custOptions} searchable
              placeholder="Pilih pelanggan" />
          </div>
          <div>
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
              Supplier <span className="font-normal text-[#8E8E93]">(opsional)</span>
            </label>
            <KNSelect data-testid="case-create-supplier" value={supplierId}
              onValueChange={setSupplierId} options={supOptions} searchable
              placeholder="Pilih supplier" />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">
            Ceritakan kejadiannya <span className="text-[#C0392B]">*</span>
          </label>
          <textarea data-testid="case-create-desc" className="textarea w-full" rows={3}
            value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder="Mis. pelanggan bilang sudah transfer 2× untuk faktur yang sama." />
        </div>
      </div>
    </FormModal>
  );
}
