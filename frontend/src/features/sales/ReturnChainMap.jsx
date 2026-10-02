/**
 * ReturnChainMap — diagram visual rantai retur (pelanggan → retur pelanggan → retur
 * antar-PT → retur ke supplier / disimpan). Dipakai di dalam ReturnChainPanel.
 * Read-only: hanya menggambar `steps` & `rolls` dari GET /api/returns/chain/{id}.
 */
import { ArrowDown, ArrowRight, Boxes, Building2, EyeOff, Factory, Truck, User, Warehouse } from "lucide-react";

const TONE = {
  sales_return: { ring: "border-[#F5C9A6]", head: "bg-[#FFE9D6] text-[#8C4A00]", Icon: Building2 },
  interco_return: { ring: "border-[#BDE5CC]", head: "bg-[#D9F3E4] text-[#0F6B52]", Icon: Truck },
  purchase_return: { ring: "border-[#CBD9F5]", head: "bg-[#DCE7FB] text-[#123E8C]", Icon: Factory },
  kept: { ring: "border-[#E5E5EA]", head: "bg-[#ECECF0] text-[#3C3C43]", Icon: Warehouse },
};
const fmtQty = (n) => Number(n || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 });

function Terminal({ icon: Icon, label, sub, testId }) {
  return (
    <div data-testid={testId} className="flex flex-col items-center text-center shrink-0 w-[92px]">
      <span className="inline-flex h-10 w-10 items-center justify-center rounded-full border-2 border-dashed border-[#C7C7CC] bg-white text-[#6E6E73]"><Icon size={16} /></span>
      <span className="mt-1 text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</span>
      {sub && <span className="text-[10.5px] leading-tight text-[#3C3C43] line-clamp-2">{sub}</span>}
    </div>
  );
}

function Connector({ label }) {
  return (
    <div className="flex items-center justify-center shrink-0 sm:w-[84px] sm:flex-col sm:pt-4" data-testid="return-chain-map-connector">
      <span className="hidden sm:flex items-center w-full"><i className="h-px flex-1 bg-[#C7C7CC]" /><ArrowRight size={12} className="text-[#8E8E93] -ml-1" /></span>
      <ArrowDown size={12} className="sm:hidden text-[#8E8E93]" />
      {label && <span className="mt-0.5 max-w-[80px] break-all text-center font-mono text-[9.5px] leading-tight text-[#8E8E93]" title={label}>{label}</span>}
    </div>
  );
}

function StageNode({ step, current }) {
  const tone = TONE[step.stage] || TONE.kept;
  const Icon = tone.Icon;
  return (
    <div data-testid={`return-chain-map-node-${step.stage}`}
         className={`relative w-[168px] shrink-0 rounded-lg border-2 bg-white ${step.redacted ? "border-dashed" : ""} ${tone.ring} ${current ? "ring-2 ring-[#0058CC] ring-offset-1 shadow-md" : "shadow-sm"}`}>
      {current && <span data-testid="return-chain-map-current" className="absolute -top-2 left-2 rounded-full bg-[#0058CC] px-1.5 text-[8.5px] font-bold uppercase tracking-wide text-white">dokumen ini</span>}
      <div className={`flex items-center gap-1.5 rounded-t-md px-2 py-1 text-[10px] font-bold uppercase tracking-wide ${tone.head}`}>
        <Icon size={11} /> <span className="truncate">{step.stage_label}</span>
        {step.redacted && <EyeOff size={10} className="ml-auto shrink-0" title="Milik badan usaha lain — ringkasan" />}
      </div>
      <div className="px-2 py-1.5 text-[11px] leading-snug">
        {step.number ? <b className="block font-mono text-[11.5px]">{step.number}</b> : <b className="block text-[#8E8E93]">—</b>}
        {step.entity_name && <span className="block truncate text-[#3C3C43]">{step.entity_name}</span>}
        {step.stage === "interco_return" && step.party && <span className="block truncate text-[#0F6B52]">→ {step.party}</span>}
        <span className="mt-0.5 flex items-center justify-between gap-1 text-[10px] text-[#6E6E73]">
          <span className="truncate">{step.status || ""}</span>
          <span className="shrink-0">{step.date ? String(step.date).slice(0, 10) : ""}</span>
        </span>
      </div>
    </div>
  );
}

export default function ReturnChainMap({ steps = [], rolls = [], currentId }) {
  if (!steps.length) return null;
  const first = steps[0];
  const last = steps[steps.length - 1];
  const supplierStep = steps.find((s) => s.stage === "purchase_return");
  const totalQty = rolls.reduce((a, r) => a + Number(r.qty || 0), 0);
  const unit = rolls[0]?.unit || "";
  const holder = last.stage === "kept" ? last.entity_name : rolls[0]?.owner_entity_name;
  const connectorLabel = (s) => s.warehouse_transfer_code || (s.stage === "purchase_return" && s.po_number) || "";
  return (
    <div data-testid="return-chain-map" className="mb-3 overflow-x-auto rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-3">
      <div className="flex flex-col items-center gap-1 sm:flex-row sm:items-start sm:gap-0 sm:min-w-max">
        {first.stage === "sales_return" && (<>
          <Terminal icon={User} label="Pelanggan" sub={first.party} testId="return-chain-map-customer" />
          <Connector label={first.order_number} />
        </>)}
        {steps.map((s, i) => (
          <div key={`${s.stage}-${s.doc_id || i}`} className="flex flex-col items-center sm:flex-row sm:items-start">
            {i > 0 && <Connector label={connectorLabel(s)} />}
            <StageNode step={s} current={!!currentId && (s.doc_id === currentId || s.counterpart_doc_id === currentId)} />
          </div>
        ))}
        {supplierStep && last.stage !== "kept" && (<>
          <Connector />
          <Terminal icon={Factory} label="Supplier" sub={supplierStep.party} testId="return-chain-map-supplier" />
        </>)}
        {rolls.length > 0 && (<>
          <Connector label={`${fmtQty(totalQty)} ${unit}`} />
          <Terminal icon={Boxes} label="Barang kini" sub={holder ? `di ${holder}` : `${rolls.length} roll`} testId="return-chain-map-goods" />
        </>)}
      </div>
    </div>
  );
}
