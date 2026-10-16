/** P05 IMP-16 — random check QC: N roll Tersedia diambil acak & DITAHAN selama dicek. */
import { useEffect, useState } from "react";
import { Shuffle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import { apiText, createRandomCheck } from "./inspectionsApi";

export default function RandomCheckModal({ open, onClose, meta, onCreated }) {
  const [warehouses, setWarehouses] = useState([]);
  const [form, setForm] = useState({ warehouse_id: "", count: 3, assigned_to: "", remark: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) return;
    setErr("");
    axios.get(`${API}/warehouses`)
      .then((r) => setWarehouses((Array.isArray(r.data) ? r.data : r.data?.items || [])
        .map((w) => ({ value: w.id, label: [w.code, w.name].filter(Boolean).join(" · ") }))))
      .catch(() => setWarehouses([]));
  }, [open]);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  async function simpan() {
    setBusy(true); setErr("");
    try {
      const doc = await createRandomCheck({ ...form, count: Number(form.count) || 3 });
      onCreated?.(doc);
    } catch (e) {
      setErr(apiText(e, "Gagal membuat random check."));
    } finally { setBusy(false); }
  }

  return (
    <FormModal open={open} onClose={onClose} title="Random check stok (QC)"
      subtitle="Roll Tersedia dipilih acak dari gudang dan DITAHAN sampai SPK diputuskan."
      icon={Shuffle} testId="ins-random-modal" onSubmit={simpan} submitLabel="Ambil roll & tahan"
      busy={busy} error={err} submitTestId="ins-random-submit">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block sm:col-span-2">
          <span className="field-label">Gudang</span>
          <KNSelect data-testid="ins-random-warehouse" value={form.warehouse_id}
            onValueChange={(v) => set({ warehouse_id: v })} options={warehouses}
            className="field" placeholder="Pilih gudang" />
        </label>
        <label className="block">
          <span className="field-label">Jumlah roll (1–30)</span>
          <input data-testid="ins-random-count" type="number" min="1" max="30" className="field"
            value={form.count} onChange={(e) => set({ count: e.target.value })} />
        </label>
        <label className="block">
          <span className="field-label">Petugas QC (opsional)</span>
          <KNSelect data-testid="ins-random-assignee" value={form.assigned_to}
            onValueChange={(v) => set({ assigned_to: v })} options={meta?.officers || []}
            className="field" placeholder="Pilih petugas" />
        </label>
        <label className="block sm:col-span-2">
          <span className="field-label">Catatan</span>
          <textarea data-testid="ins-random-remark" className="field" rows={2}
            value={form.remark} onChange={(e) => set({ remark: e.target.value })} />
        </label>
      </div>
    </FormModal>
  );
}
