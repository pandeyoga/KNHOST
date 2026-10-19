import KNSelect from "../../components/KNSelect";

// Satu jenis biaya logistik: cara kirim → penanggung → nominal (+PPN) → akun bayar (Finance) → PT pembeban.
export default function LogisticsCostRow({ type, label, v, ctx, locked, onChange }) {
  const set = (patch) => onChange({ ...v, ...patch });
  const modeOpts = Object.entries(ctx.modes).map(([value, l]) => ({ value, label: l }));
  const bearerOpts = ctx.bearer_options.filter((o) => o.mode === v.mode).map((o) => ({ value: o.bearer, label: o.label }));
  const companyPaid = v.bearer === "company" && v.mode !== "pickup";
  const payOpts = [{ value: "", label: "Bawaan (Pemetaan Akun)" }, ...ctx.pay_accounts.map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` }))];
  const entOpts = ctx.entities.map((e) => ({ value: e.id, label: e.name }));
  const setMode = (mode) => set({ mode, bearer: ctx.bearer_options.find((o) => o.mode === mode)?.bearer || "company" });
  const needsAmount = v.mode !== "pickup" && !(v.mode === "third_party" && v.bearer === "customer");
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-[#F2F3F5] pt-2" data-testid={`logistics-row-${type}`}>
      <span className="w-56 font-medium">{label}</span>
      <div className="w-48"><KNSelect data-testid={`logistics-mode-${type}`} disabled={locked} className="field text-xs" value={v.mode} options={modeOpts} onValueChange={setMode} /></div>
      {v.mode !== "pickup" && <div className="w-56"><KNSelect data-testid={`logistics-bearer-${type}`} disabled={locked} className="field text-xs" value={v.bearer} options={bearerOpts} onValueChange={(b) => set({ bearer: b })} /></div>}
      {needsAmount && <input data-testid={`logistics-amount-${type}`} disabled={locked} type="number" min={0} placeholder="Rp" className="field w-28" value={v.amount} onChange={(e) => set({ amount: e.target.value })} />}
      {ctx.vat_enabled && companyPaid && <input data-testid={`logistics-vat-${type}`} disabled={locked} type="number" min={0} placeholder="PPN Rp" className="field w-24" value={v.vat_amount} onChange={(e) => set({ vat_amount: e.target.value })} />}
      {companyPaid && <div className="w-60" title={ctx.can_post ? "" : "Dipilih oleh Finance"}><KNSelect searchable data-testid={`logistics-pay-${type}`} disabled={locked || !ctx.can_post} className="field text-xs" value={v.pay_account_code} options={payOpts} onValueChange={(c) => set({ pay_account_code: c })} /></div>}
      {needsAmount && <div className="w-44"><KNSelect data-testid={`logistics-entity-${type}`} disabled={locked} className="field text-xs" value={v.charged_entity_id} options={entOpts} onValueChange={(e) => set({ charged_entity_id: e })} /></div>}
      <input data-testid={`logistics-note-${type}`} disabled={locked} className="field w-40" placeholder="Catatan" value={v.note} onChange={(e) => set({ note: e.target.value })} />
      {v.journal_entry_number && <span className="rounded bg-[#EAF7EE] px-1.5 py-0.5 text-[10.5px] font-semibold text-[#1A7F37]" data-testid={`logistics-je-${type}`}>Jurnal {v.journal_entry_number}</span>}
    </div>
  );
}
