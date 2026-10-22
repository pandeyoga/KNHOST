import KNSelect from "../../components/KNSelect";

// Satu jenis biaya logistik: cara kirim → penanggung → nominal (+PPN) → akun bayar (Finance) → PT pembeban.
// 23 Okt — setiap isian berlabel (dulu dropdown & kotak tanpa label yang membungkus ke baris kedua).
const L = ({ label, children, className = "" }) => (
  <label className={`block text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73] ${className}`}>
    {label}
    <div className="mt-1 normal-case tracking-normal">{children}</div>
  </label>
);

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
    <div className="border-t border-[#F2F3F5] pt-2.5" data-testid={`logistics-row-${type}`}>
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-semibold text-[#1C1C1E]">{label}</span>
        {v.journal_entry_number && <span className="rounded bg-[#EAF7EE] px-1.5 py-0.5 text-[10.5px] font-semibold text-[#1A7F37]" data-testid={`logistics-je-${type}`}>Jurnal {v.journal_entry_number}</span>}
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <L label="Cara kirim"><KNSelect data-testid={`logistics-mode-${type}`} disabled={locked} className="field text-xs" value={v.mode} options={modeOpts} onValueChange={setMode} /></L>
        {v.mode !== "pickup" && <L label="Ditanggung"><KNSelect data-testid={`logistics-bearer-${type}`} disabled={locked} className="field text-xs" value={v.bearer} options={bearerOpts} onValueChange={(b) => set({ bearer: b })} /></L>}
        {needsAmount && <L label="Ongkir (Rp)"><input data-testid={`logistics-amount-${type}`} disabled={locked} type="number" min={0} placeholder="0" className="field text-right tabular-nums" value={v.amount} onChange={(e) => set({ amount: e.target.value })} /></L>}
        {ctx.vat_enabled && companyPaid && <L label="PPN (Rp)"><input data-testid={`logistics-vat-${type}`} disabled={locked} type="number" min={0} placeholder="0" className="field text-right tabular-nums" value={v.vat_amount} onChange={(e) => set({ vat_amount: e.target.value })} /></L>}
        {companyPaid && <L label={ctx.can_post ? "Akun pembayaran" : "Akun pembayaran (dipilih Finance)"}><KNSelect searchable data-testid={`logistics-pay-${type}`} disabled={locked || !ctx.can_post} className="field text-xs" value={v.pay_account_code} options={payOpts} onValueChange={(c) => set({ pay_account_code: c })} /></L>}
        {needsAmount && <L label="PT pembeban"><KNSelect data-testid={`logistics-entity-${type}`} disabled={locked} className="field text-xs" value={v.charged_entity_id} options={entOpts} onValueChange={(e) => set({ charged_entity_id: e })} placeholder="Pilih PT" /></L>}
        <L label="Catatan" className="sm:col-span-2 lg:col-span-1"><input data-testid={`logistics-note-${type}`} disabled={locked} className="field" placeholder="opsional" value={v.note} onChange={(e) => set({ note: e.target.value })} /></L>
      </div>
    </div>
  );
}
