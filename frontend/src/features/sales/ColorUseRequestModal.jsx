/** ColorUseRequestModal — minta izin manajer memakai warna milik pelanggan untuk produk umum / pelanggan lain. */
import { useEffect, useState } from "react";
import { Lock, Send, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import { overlayDismiss } from "@/utils/overlayDismiss";

export default function ColorUseRequestModal({ color, ownerId, ownerName, onClose, onDone }) {
  const [customers, setCustomers] = useState([]);
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [context, setContext] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    axios.get(`${API}/customers`).then((r) => setCustomers((Array.isArray(r.data) ? r.data : r.data?.items || []).filter((c) => c.id !== ownerId))).catch(() => {});
  }, [ownerId]);

  const submit = async () => {
    setSaving(true); setError("");
    try {
      await axios.post(`${API}/color-library/${color.id}/use-requests`, { target_customer_id: target, reason, context });
      onDone(`Permintaan izin ${color.code} dikirim ke manajer.`);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal mengirim permintaan izin.");
      setSaving(false);
    }
  };

  return (
    <div data-testid="color-use-request-modal" className="fixed inset-0 z-[170] flex items-center justify-center bg-black/50 p-4" {...overlayDismiss(onClose)}>
      <div className="w-full max-w-[440px] overflow-hidden rounded-xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-3">
          <h2 className="flex items-center gap-2 text-[14px] font-bold"><Lock size={15} className="text-[#B45309]" /> Minta izin pakai warna</h2>
          <button className="icon-button" onClick={onClose} aria-label="Tutup" data-testid="color-use-request-close"><X size={18} /></button>
        </div>
        <div className="space-y-3 p-4 text-[12px]">
          <div className="flex items-center gap-3 rounded-lg border border-[#FDE68A] bg-[#FFFBEB] p-2">
            <div className="h-10 w-10 shrink-0 rounded" style={{ backgroundColor: color.hex }} />
            <p className="leading-snug"><b>{color.code}</b> · {color.name}<br /><span className="text-[#92400E]">Milik {ownerName} (eksklusif). Pemakaian lain butuh persetujuan manajer.</span></p>
          </div>
          <ErrorNotice message={error} onDismiss={() => setError("")} testId="color-use-request-error" />
          <label className="block">
            <span className="mb-1 block text-[10px] font-bold uppercase text-[#8E8E93]">Dipakai untuk</span>
            <KNSelect data-testid="color-use-request-target" className="field" value={target} onValueChange={setTarget} searchable
              options={[{ value: "", label: "Produk umum (semua pelanggan)" }, ...customers.map((c) => ({ value: c.id, label: `Pelanggan: ${c.name}` }))]} />
          </label>
          <label className="block">
            <span className="mb-1 block text-[10px] font-bold uppercase text-[#8E8E93]">Keperluan (opsional)</span>
            <input data-testid="color-use-request-context" className="field w-full" placeholder="mis. SKU / nomor pesanan" value={context} onChange={(e) => setContext(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-[10px] font-bold uppercase text-[#8E8E93]">Alasan *</span>
            <textarea data-testid="color-use-request-reason" className="field min-h-[72px] w-full" placeholder="Jelaskan kenapa warna ini perlu dipakai…" value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
        </div>
        <div className="flex justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
          <button className="secondary-button" onClick={onClose}>Batal</button>
          <button data-testid="color-use-request-submit" className="primary-button" onClick={submit} disabled={saving || reason.trim().length < 5}>
            <Send size={13} /> {saving ? "Mengirim…" : "Kirim ke manajer"}
          </button>
        </div>
      </div>
    </div>
  );
}
