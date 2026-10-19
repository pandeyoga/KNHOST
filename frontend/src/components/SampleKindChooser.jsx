import { useState } from "react";
import { toast } from "@/hooks/use-toast";
import { BookOpen } from "lucide-react";
import { SAMPLE_KINDS, sampleLimit } from "../utils/sampleOrder";
import { formatQty } from "../utils/formatters";
import CatalogueCreateModal from "../features/samples/CatalogueCreateModal";
import { canCurrent } from "../config/roles";

/** L06 LN-060 — tiga jenis Pesanan Sample di POS: Standar · Hanger (per baris) · Catalogue (per artikel, pesanan sendiri). */
export default function SampleKindChooser({ product, kind, onKind, templateId = "", customerId = "", entityId = "", testIdPrefix = "quickview" }) {
  const [catOpen, setCatOpen] = useState(false);
  const unit = sampleLimit(product, kind).unit;
  const catOk = (product?.base_unit || "yard") === "yard";
  const canCreate = canCurrent("sample_order", "create");
  return (
    <div className="mt-2" data-testid={`${testIdPrefix}-sample-kinds`}>
      <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-[#9A5B00]">Jenis sample</p>
      <div className="grid grid-cols-3 gap-1.5">
        {Object.entries(SAMPLE_KINDS).map(([k, v]) => (
          <button key={k} type="button" data-testid={`${testIdPrefix}-sample-kind-${k}`} onClick={() => onKind(k)}
            className={`rounded-md border px-1.5 py-1.5 text-center text-[11px] font-semibold leading-tight ${kind === k ? "border-[#9A5B00] bg-[#9A5B00] text-white" : "border-[#F3D9A4] bg-white text-[#9A5B00]"}`}>
            {v.label}<span className="block text-[9.5px] font-medium opacity-80">maks {formatQty(sampleLimit(product, k).max_qty)} {unit}</span>
          </button>
        ))}
        <button type="button" data-testid={`${testIdPrefix}-sample-kind-catalogue`} onClick={() => setCatOpen(true)} disabled={!catOk || !canCreate}
          title={!canCreate ? "Tidak punya izin membuat Pesanan Sample" : catOk ? "Buat Pesanan Sample Catalogue untuk artikel ini" : "Catalogue hanya untuk kain woven (yard)"}
          className="rounded-md border border-[#F3D9A4] bg-white px-1.5 py-1.5 text-center text-[11px] font-semibold leading-tight text-[#9A5B00] disabled:opacity-40">
          <span className="inline-flex items-center gap-1"><BookOpen size={11} /> Catalogue</span>
          <span className="block text-[9.5px] font-medium opacity-80">1 yd/warna + 2 yd soft</span>
        </button>
      </div>
      <CatalogueCreateModal open={catOpen} onClose={() => setCatOpen(false)} entityId={entityId}
        initialTemplateId={templateId} initialCustomerId={customerId}
        onCreated={(so) => toast({ title: `${so?.number || "Pesanan sample"} (catalogue) dibuat`, description: "Lihat menu Pesanan Sample." })} />
    </div>
  );
}
