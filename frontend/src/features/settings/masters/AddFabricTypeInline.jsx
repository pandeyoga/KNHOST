import { useState } from "react";
import { Plus } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";
import useUomConversions from "../../../hooks/useUomConversions";
import { uomSelectOptions } from "../../../utils/uomCatalog";

/** L01 — tambah jenis kain yang ditolak impor langsung ke master (dengan satuan kendali). */
export default function AddFabricTypeInline({ value, onAdded, onError }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(value.charAt(0).toUpperCase() + value.slice(1));
  const [uom, setUom] = useState("meter");
  const [busy, setBusy] = useState(false);
  // Fase 3 · P2 — satuan kendali dari MASTER satuan (INV-UOM-02), bukan daftar yang diketik di kode.
  useUomConversions();
  const uomOpts = uomSelectOptions({ dimensions: ["length", "weight"], extra: [uom] })
    .map((o) => ({ ...o, label: `kendali ${o.label}` }));
  const save = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/master/fabric-types`, { code: value.toLowerCase().replace(/[^a-z0-9_]/g, "_").replace(/^_+|_+$/g, ""), name: name.trim(), control_uom: uom });
      setOpen(false);
      onAdded?.();
    } catch (e) { onError?.(e.response?.data?.detail || "Gagal menambah jenis kain."); }
    finally { setBusy(false); }
  };
  if (!open) {
    return (
      <button type="button" className="ml-1 inline-flex items-center gap-0.5 rounded-full bg-white px-2 py-0.5 text-[10.5px] font-semibold text-[#0A6E47]"
        onClick={() => setOpen(true)} data-testid={`cds-add-fabric-${value}`}><Plus size={10} /> Tambah ke master</button>
    );
  }
  return (
    <span className="ml-1 inline-flex flex-wrap items-center gap-1" data-testid={`cds-add-fabric-form-${value}`}>
      <input className="field !w-32 !py-0.5 text-[11px]" value={name} onChange={(e) => setName(e.target.value)} data-testid={`cds-add-fabric-name-${value}`} />
      <KNSelect className="field !w-auto !py-0.5 text-[11px]" value={uom} onValueChange={setUom} data-testid={`cds-add-fabric-uom-${value}`} aria-label="Satuan kendali"
        options={uomOpts} />
      <button type="button" disabled={busy || !name.trim()} className="primary-button !py-0.5 text-[11px]" onClick={save} data-testid={`cds-add-fabric-save-${value}`}>Simpan</button>
      <button type="button" className="secondary-button !py-0.5 text-[11px]" onClick={() => setOpen(false)}>Batal</button>
    </span>
  );
}
