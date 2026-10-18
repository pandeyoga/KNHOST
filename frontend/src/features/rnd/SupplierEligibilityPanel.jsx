/** L03 LN-034 — kelayakan SKU per supplier: hasil terbaru, terdahulu, dan siklus berjalan (dari histori). */
import { useEffect, useState } from "react";
import { supplierEligibility } from "./rndApi";

const TONE = {
  pass: "bg-[#EAF7EF] text-[#1A7A3A]", fail_pending_pic: "bg-[#FDEDE7] text-[#C0392B]",
  fail_decided: "bg-[#FDEDE7] text-[#A8221A]", fail_override: "bg-[#FFF6E5] text-[#8C4A00]", open: "bg-[#F2F7FF] text-[#004099]",
};

function StateChip({ c, testId }) {
  return <span className={`rounded px-1.5 py-px text-[10px] font-bold ${TONE[c.state] || TONE.open}`} data-testid={testId}>{c.state_label}</span>;
}

function SupplierRow({ g }) {
  return (
    <li className="px-2.5 py-2 text-[11px]" data-testid={`elig-supplier-${g.supplier_id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <b className="text-[#1C1C1E]">{g.supplier_name || g.supplier_id}</b>
        <span className="text-[10px] uppercase text-[#8E8E93]">{g.partner_kind}</span>
        <span className={`ml-auto rounded-full px-2 py-px text-[10px] font-bold ${g.eligible ? "bg-[#1A7A3A] text-white" : "bg-[#F2F3F5] text-[#6B6B73]"}`}
          data-testid={`elig-status-${g.supplier_id}`}>{g.eligible ? "Layak" : "Belum layak"}</span>
      </div>
      <div className="mt-1 grid gap-0.5 text-[10.5px] text-[#3C3C43]">
        <p data-testid={`elig-latest-${g.supplier_id}`}>Terbaru: {g.latest
          ? <>{g.latest.number} · siklus {g.latest.cycle_no} · <StateChip c={g.latest} testId={`elig-latest-state-${g.supplier_id}`} /></>
          : <span className="text-[#8E8E93]">belum ada hasil</span>}</p>
        {g.previous.length > 0 && (
          <p data-testid={`elig-previous-${g.supplier_id}`}>Terdahulu: {g.previous.map((c) => (
            <span key={c.sample_id} className="mr-1.5 inline-flex items-center gap-1">{c.number} <StateChip c={c} /></span>))}</p>
        )}
        {g.open.length > 0 && (
          <p data-testid={`elig-open-${g.supplier_id}`}>Berjalan: {g.open.map((c) => `${c.number} (siklus ${c.cycle_no})`).join(", ")}</p>
        )}
      </div>
    </li>
  );
}

export default function SupplierEligibilityPanel({ productId, refreshKey = 0 }) {
  const [data, setData] = useState(null);
  const [denied, setDenied] = useState(false);
  useEffect(() => {
    setData(null); setDenied(false);
    if (!productId) return;
    supplierEligibility(productId).then(setData).catch(() => setDenied(true));
  }, [productId, refreshKey]);
  if (denied || !productId) return null;
  if (!data) return <div className="h-8 animate-pulse rounded-md bg-[#F2F2F5]" />;
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-white" data-testid="supplier-eligibility-panel">
      <p className="border-b border-[#F2F3F5] px-2.5 py-1.5 text-[10.5px] font-bold uppercase tracking-wide text-[#6B6B73]">Kelayakan per supplier</p>
      {data.suppliers.length === 0
        ? <p className="px-2.5 py-2 text-[11px] text-[#8E8E93]" data-testid="supplier-eligibility-empty">Belum ada uji ulang per supplier untuk SKU ini.</p>
        : <ul className="divide-y divide-[#F2F3F5]">{data.suppliers.map((g) => <SupplierRow key={g.supplier_id} g={g} />)}</ul>}
    </div>
  );
}
