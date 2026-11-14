/**
 * KP-T4 — pop-up ubah Aturan Persetujuan untuk SATU jenis dokumen pada satu lapisan (Semua PT / satu PT).
 * Mengganti seluruh baris lapisan itu sekaligus (`PUT /api/approval-policies/{doc_kind}`), alasan wajib, versi dicek
 * server (409 bila sudah diubah orang lain). Pilihan penyetuju: semua peran registry (termasuk peran kustom) atau
 * "Semua pemegang akses".
 */
import { useEffect, useState } from "react";
import { Plus, Settings, Trash2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import MoneyInput from "../../components/MoneyInput";
import { parseDecimal } from "../../utils/decimalInput";
import { ANY_HOLDER_LABEL, draftFromView, payloadFromDraft } from "./approvalPolicyHelpers";

const tierBaru = () => ({ min: "0", max: "", roles: [], any_holder: false });

export default function ApprovalPolicyEditor({ open, kind, entityId, entityLabel, roles = [], mode = "edit",
  onClose, onSaved }) {
  const [draft, setDraft] = useState([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open && kind) {
      setDraft(draftFromView(kind));
      setReason("");
      setError("");
    }
  }, [open, kind]);

  if (!open || !kind) return null;
  const hasAmount = !!kind.has_amount;
  const ubahLevel = (i, patch) => setDraft((d) => d.map((lv, j) => (j === i ? { ...lv, ...patch } : lv)));
  const ubahTier = (i, k, patch) => setDraft((d) => d.map((lv, j) => (j !== i ? lv
    : { ...lv, tiers: lv.tiers.map((t, n) => (n === k ? { ...t, ...patch } : t)) })));
  const tambahTier = (i) => setDraft((d) => d.map((lv, j) => (j === i ? { ...lv, tiers: [...lv.tiers, tierBaru()] } : lv)));
  const hapusTier = (i, k) => setDraft((d) => d.map((lv, j) => (j === i ? { ...lv, tiers: lv.tiers.filter((_, n) => n !== k) } : lv)));
  const tambahLevel = () => setDraft((d) => [...d, { level: (d.length ? Math.max(...d.map((x) => Number(x.level) || 0)) : 0) + 1,
    label: "", tiers: [tierBaru()] }]);
  const hapusLevel = (i) => setDraft((d) => d.filter((_, j) => j !== i));
  const togglePeran = (i, k, rid) => {
    const t = draft[i].tiers[k];
    const have = t.roles.includes(rid);
    ubahTier(i, k, { roles: have ? t.roles.filter((x) => x !== rid) : [...t.roles, rid] });
  };

  const simpan = async () => {
    if ((reason || "").trim().length < 5) { setError("Alasan perubahan wajib diisi (min. 5 karakter)."); return; }
    setBusy(true);
    setError("");
    try {
      const body = payloadFromDraft(draft, { entityId, version: mode === "create" ? 0 : kind.version,
        reason: reason.trim(), hasAmount, parse: parseDecimal });
      const r = await axios.put(`${API}/approval-policies/${kind.doc_kind}`, body);
      onSaved && onSaved(r.data);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : (e?.message || "Gagal menyimpan aturan."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormModal open={open} onClose={onClose} icon={Settings} size="lg" testId="appol-editor"
      title={mode === "create" ? `Buat aturan khusus PT ini — ${kind.label}` : `Ubah aturan — ${kind.label}`}
      subtitle={`Berlaku untuk: ${entityLabel}`} onSubmit={simpan} submitLabel="Simpan aturan" busy={busy}
      error={error} submitTestId="appol-editor-save">
      {draft.map((lv, i) => (
        <fieldset key={`lv-${i}`} className="section-card mb-3" data-testid={`appol-ed-level-${i}`}>
          <div className="flex flex-wrap items-end gap-2 mb-2">
            <label className="text-fs-12">
              <span className="block text-kn-text-2 mb-1">Jenjang</span>
              <input className="field w-20" type="number" min={1} value={lv.level}
                data-testid={`appol-ed-levelno-${i}`} onChange={(e) => ubahLevel(i, { level: e.target.value })} />
            </label>
            <label className="text-fs-12 flex-1">
              <span className="block text-kn-text-2 mb-1">Nama jenjang</span>
              <input className="field" value={lv.label} placeholder="mis. Direksi"
                data-testid={`appol-ed-label-${i}`} onChange={(e) => ubahLevel(i, { label: e.target.value })} />
            </label>
            <button type="button" className="btn-ghost btn-sm" onClick={() => hapusLevel(i)}
              data-testid={`appol-ed-del-level-${i}`}><Trash2 size={13} /> Hapus jenjang</button>
          </div>
          {lv.tiers.map((t, k) => (
            <div key={`t-${k}`} className="border-t border-kn-divider pt-2 mt-2" data-testid={`appol-ed-tier-${i}-${k}`}>
              {hasAmount && (
                <div className="grid gap-2 sm:grid-cols-2 mb-2">
                  <label className="text-fs-12">
                    <span className="block text-kn-text-2 mb-1">Mulai dari (Rp)</span>
                    <MoneyInput value={t.min} onChange={(v) => ubahTier(i, k, { min: v })} testId={`appol-ed-min-${i}-${k}`} />
                  </label>
                  <label className="text-fs-12">
                    <span className="block text-kn-text-2 mb-1">Sampai di bawah (Rp) — kosong = tanpa batas</span>
                    <MoneyInput value={t.max} onChange={(v) => ubahTier(i, k, { max: v })} testId={`appol-ed-max-${i}-${k}`} />
                  </label>
                </div>
              )}
              <label className="flex items-center gap-2 text-fs-12 mb-1">
                <input type="checkbox" checked={t.any_holder} data-testid={`appol-ed-any-${i}-${k}`}
                  onChange={(e) => ubahTier(i, k, { any_holder: e.target.checked })} />
                {ANY_HOLDER_LABEL}
              </label>
              {!t.any_holder && (
                <div className="grid gap-1 sm:grid-cols-3" data-testid={`appol-ed-roles-${i}-${k}`}>
                  {roles.map((r) => (
                    <label key={r.id} className="flex items-center gap-2 text-fs-12">
                      <input type="checkbox" checked={t.roles.includes(r.id)}
                        data-testid={`appol-ed-role-${i}-${k}-${r.id}`} onChange={() => togglePeran(i, k, r.id)} />
                      {r.label}
                    </label>
                  ))}
                </div>
              )}
              {!t.any_holder && t.roles.length === 0 && (
                <p className="text-fs-12 text-kn-text-2 mt-1">Tanpa peran = rentang ini tidak butuh persetujuan.</p>
              )}
              {lv.tiers.length > 1 && (
                <button type="button" className="btn-ghost btn-sm mt-1" onClick={() => hapusTier(i, k)}
                  data-testid={`appol-ed-del-tier-${i}-${k}`}><Trash2 size={13} /> Hapus rentang</button>
              )}
            </div>
          ))}
          {hasAmount && (
            <button type="button" className="btn-secondary btn-sm mt-2" onClick={() => tambahTier(i)}
              data-testid={`appol-ed-add-tier-${i}`}><Plus size={13} /> Tambah rentang</button>
          )}
        </fieldset>
      ))}
      <button type="button" className="btn-secondary btn-sm mb-3" onClick={tambahLevel} data-testid="appol-ed-add-level">
        <Plus size={13} /> Tambah jenjang
      </button>
      <label className="text-fs-12 block">
        <span className="block text-kn-text-2 mb-1">Alasan perubahan (wajib, tercatat di riwayat)</span>
        <textarea className="field" rows={2} value={reason} data-testid="appol-ed-reason"
          onChange={(e) => setReason(e.target.value)} />
      </label>
    </FormModal>
  );
}
