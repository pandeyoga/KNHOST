/**
 * W2-REQ-05 — entitas pembeli PO tampil jelas + ganti cepat (hanya entitas yang diizinkan).
 * Draft form disimpan ke sessionStorage sebelum ganti entitas, lalu dipulihkan setelah layar dimuat ulang.
 */
import { Building2 } from "lucide-react";
import KNSelect from "../../../components/KNSelect";

export const PO_DRAFT_KEY = "kn_po_draft";

export const takePODraft = () => {
  try {
    const raw = sessionStorage.getItem(PO_DRAFT_KEY);
    sessionStorage.removeItem(PO_DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
};

export const POBuyerEntitySwitch = ({ selectedEntity, entities = [], formData, onSwitch }) => {
  const options = entities.filter((e) => e.id && e.id !== "all");
  const current = options.find((e) => e.id === selectedEntity);
  const change = (id) => {
    if (!id || id === selectedEntity) return;
    sessionStorage.setItem(PO_DRAFT_KEY, JSON.stringify({ formData, from: selectedEntity, to: id }));
    onSwitch?.(id);
  };
  return (
    <div data-testid="po-buyer-entity" className="flex flex-wrap items-center gap-2 rounded-md border border-[#DCE7F7] bg-[#F7FAFF] px-2.5 py-2 text-[11.5px]">
      <Building2 size={14} className="text-[#0058CC]" />
      <span className="text-[#6B6B73]">Entitas pembeli:</span>
      <b data-testid="po-buyer-entity-name">{current ? (current.short_name || current.legal_name || current.name) : "Pilih badan usaha dulu"}</b>
      {onSwitch && options.length > 1 && (
        <KNSelect data-testid="po-buyer-entity-switch" value={current ? selectedEntity : ""} onValueChange={change} placeholder="— pilih —"
          className="ml-auto !h-auto !w-auto rounded border border-[#DCE7F7] bg-white !px-2 !py-1 text-[11px]"
          options={options.map((e) => ({ value: e.id, label: e.short_name || e.legal_name || e.name }))} />
      )}
    </div>
  );
};
