import { formatCurrency, formatQty } from "../../utils/formatters";

const num = (v) => Math.max(0, Number(String(v).replace(",", ".")) || 0);

function QtyRow({ label, hint, max, value, onChange, testId }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 py-1">
      <div className="min-w-0">
        <p className="text-[12px] font-semibold text-[#1C1C1E]">{label}</p>
        {hint && <p className="text-[10.5px] text-[#6B6B73]">{hint}</p>}
      </div>
      <div className="flex items-center gap-1.5">
        <input data-testid={testId} type="number" min={0} step="0.01" className="field !h-8 w-[110px] text-right text-[12px]"
          value={value || ""} placeholder="0" disabled={max <= 0} onChange={(e) => onChange(num(e.target.value))} />
        <button type="button" data-testid={`${testId}-max`} disabled={max <= 0} onClick={() => onChange(max)}
          className="rounded-full border border-[#E5E5EA] px-2 py-0.5 text-[10px] font-bold text-[#0058CC] disabled:opacity-40">maks</button>
      </div>
    </div>
  );
}

function PriceState({ line, o, canSet, onPrice, requested }) {
  const key = `${line.product_id}-${o.entity_id}`;
  if (o.price_ready) {
    return <p data-testid={`fulfill-ic-price-${key}`} className="-mt-0.5 mb-1 text-[10.5px] text-[#1B7F4B]">Harga internal {formatCurrency(o.unit_price)} / {line.unit}</p>;
  }
  return (
    <div className="-mt-0.5 mb-1 flex flex-wrap items-center gap-1.5">
      <span data-testid={`fulfill-ic-price-missing-${key}`} className="rounded-full bg-[#FFF4E0] px-2 py-0.5 text-[10px] font-bold text-[#8A5300]">Belum ada harga internal</span>
      {canSet ? (
        <button type="button" data-testid={`fulfill-create-price-${key}`} onClick={() => onPrice("create", o)}
          className="rounded-full border border-[#CBDFFF] bg-[#F2F7FF] px-2 py-0.5 text-[10px] font-bold text-[#0058CC]">Buat harga internal</button>
      ) : (
        <button type="button" data-testid={`fulfill-request-price-${key}`} disabled={requested} onClick={() => onPrice("request", o)}
          className="rounded-full border border-[#E5E5EA] px-2 py-0.5 text-[10px] font-bold text-[#3C3C43] disabled:opacity-50">{requested ? "Permintaan terkirim" : "Minta harga internal"}</button>
      )}
    </div>
  );
}

/** Satu baris kekurangan: qty dari stok · per PT lain · PO supplier · tunggu barang datang. */
export default function FulfillmentLineCard({ line, value, onChange, canSetPrice, onPrice, requested = {} }) {
  const v = value || { stock: 0, reorder: 0, wait: 0, ic: {} };
  const used = v.stock + v.reorder + v.wait + Object.values(v.ic).reduce((s, q) => s + q, 0);
  const left = Math.round((line.backorder_qty - used) * 100) / 100;
  const room = (cur) => Math.max(0, Math.round((left + cur) * 100) / 100);
  const pid = line.product_id;
  const proposed = new Set((line.proposal || []).map((p) => p.entity_id));
  return (
    <div className="rounded-xl border border-[#EFF0F2] bg-white p-3" data-testid={`fulfill-line-${pid}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[#F2F2F5] pb-2">
        <p className="text-[13px] font-bold">{line.product_name} <span className="font-mono text-[10.5px] text-[#8E8E93]">{line.sku}</span></p>
        <p className="text-[11.5px]">Kekurangan <b data-testid={`fulfill-short-${pid}`}>{formatQty(line.backorder_qty)} {line.unit}</b>
          {line.planned_qty > 0 && <span className="ml-2 text-[#8A5300]">· sudah direncanakan sebelumnya {formatQty(line.planned_qty)}</span>}</p>
      </div>
      <QtyRow label="Ambil dari stok sendiri" testId={`fulfill-stock-${pid}`} value={v.stock}
        max={Math.min(line.own_available, room(v.stock))} onChange={(q) => onChange({ ...v, stock: q })}
        hint={line.own_by_warehouse.length ? line.own_by_warehouse.map((w) => `${w.warehouse_name} ${formatQty(w.available_qty)}`).join(" · ") : "Tidak ada stok tersedia di entitas penjual."} />
      {line.other_entities.map((o) => (
        <div key={o.entity_id}>
          <QtyRow label={`Transfer dari ${o.entity_name}`} testId={`fulfill-ic-${pid}-${o.entity_id}`}
            value={v.ic[o.entity_id]} max={o.price_ready === false ? 0 : Math.min(o.available, room(v.ic[o.entity_id] || 0))}
            hint={`Stok tersedia ${formatQty(o.available)}${proposed.has(o.entity_id) ? " · diusulkan sales (roll pilihan)" : ""}`}
            onChange={(q) => onChange({ ...v, ic: { ...v.ic, [o.entity_id]: q } })} />
          <PriceState line={line} o={o} canSet={canSetPrice} onPrice={(kind, ent) => onPrice?.(kind, line, ent)}
            requested={!!requested[`${pid}-${o.entity_id}`]} />
        </div>
      ))}
      <QtyRow label="PO ke supplier (lewat PR)" testId={`fulfill-reorder-${pid}`} value={v.reorder}
        max={room(v.reorder)} onChange={(q) => onChange({ ...v, reorder: q })} hint="Membuat Permintaan Pembelian bertaut pesanan ini." />
      <QtyRow label="Tunggu barang datang" testId={`fulfill-wait-${pid}`} value={v.wait}
        max={Math.min(line.incoming_total, room(v.wait))} onChange={(q) => onChange({ ...v, wait: q })}
        hint={line.incoming_total > 0 ? `Perkiraan sisa barang masuk untuk SO ini ${formatQty(line.incoming_total)}${line.incoming_claimed_by_older > 0 ? ` (${formatQty(line.incoming_claimed_by_older)} sudah untuk SO lebih lama)` : ""}${line.promise_date ? ` · perkiraan ${String(line.promise_date).slice(0, 10)}` : ""} — tidak dijamin` : line.incoming_claimed_by_older > 0 ? "Barang masuk terjadwal sudah diperkirakan untuk SO yang lebih lama." : "Tidak ada barang masuk terjadwal."} />
      <p data-testid={`fulfill-left-${pid}`} className={`mt-1 text-right text-[11px] font-semibold ${left < -0.005 ? "text-[#C0392B]" : left > 0.005 ? "text-[#8A5300]" : "text-[#1B7F4B]"}`}>
        {left < -0.005 ? `Melebihi kekurangan ${formatQty(-left)}` : left > 0.005 ? `Sisa tetap backorder: ${formatQty(left)} ${line.unit}` : "Terpenuhi penuh"}
      </p>
    </div>
  );
}
