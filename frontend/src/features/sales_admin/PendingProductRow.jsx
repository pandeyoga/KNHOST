import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { formatDate, formatQty } from "../../utils/formatters";
import { docStatusLabel } from "../../utils/docStatus";

const MODE = { interco: "Transfer PT lain", reorder: "PR/PO supplier", makloon: "Produksi makloon", wait: "Tunggu barang datang" };

/** P04 IMP-03 — produk > kebutuhan SO > dokumen pemenuhan (tanpa nomor PO fiktif). */
export default function PendingProductRow({ p, onOpen, tp }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-lg border border-[#EFF0F2]" data-testid={`${tp}-pending-${p.product_id}`}>
      <button type="button" onClick={() => setOpen((v) => !v)} data-testid={`${tp}-pending-toggle-${p.product_id}`}
        className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-[#FAFBFC]">
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <div className="min-w-0 flex-1">
          <p className="truncate text-[12px] font-semibold">{p.product_name || p.sku}</p>
          <p className="text-[10.5px] text-[#8E8E93]">{p.sku} · {p.so_count} SO</p>
        </div>
        <span className="text-[12.5px] font-bold tabular-nums text-[#B26A00]" data-testid={`${tp}-pending-qty-${p.product_id}`}>
          kurang {formatQty(p.short_qty)} {p.unit}
        </span>
      </button>
      {open && (
        <ul className="divide-y divide-[#F2F3F5] border-t border-[#EFF0F2] bg-[#FAFBFC]">
          {p.orders.map((o) => (
            <li key={o.order_id} className="px-4 py-2" data-testid={`${tp}-pending-so-${o.order_id}`}>
              <div className="flex items-center gap-2">
                <button type="button" className="text-[11.5px] font-semibold text-[#0058CC] hover:underline" onClick={() => onOpen(o.order_id, o.number)}>{o.number}</button>
                <span className="text-[11px] text-[#6B6B73]">{o.customer_name} · {o.age_days} hari</span>
                <span className="ml-auto text-[11.5px] font-bold tabular-nums">{formatQty(o.short_qty)} {p.unit}</span>
              </div>
              {o.supply.length === 0 ? (
                /* UAT 24 Okt (audit UI tahap 2) — G2-29: kalimat jadi tautan ke SO (tempat "Putuskan pemenuhan"). */
                <p className="mt-0.5 text-[10.5px] text-[#8E8E93]" data-testid={`${tp}-pending-nosupply-${o.order_id}`}>Belum ada keputusan pemenuhan —{" "}
                  <button type="button" className="font-semibold text-[#0058CC] hover:underline" data-testid={`${tp}-pending-decide-${o.order_id}`}
                    onClick={() => onOpen(o.order_id, o.number)}>putuskan pemenuhan {o.number} →</button></p>
              ) : o.supply.map((s, i) => (
                <p key={i} className="mt-0.5 text-[10.5px] text-[#3C3C43]" data-testid={`${tp}-pending-supply-${o.order_id}-${i}`}>
                  {MODE[s.mode] || s.mode}: <b className="tabular-nums">{formatQty(s.qty)}</b>
                  {s.ref_number ? ` · ${s.ref_number}` : ""}{s.po_number ? ` → ${s.po_number}` : ""}
                  {s.note ? ` · ${s.note}` : ""} · ETA {s.eta ? formatDate(s.eta) : "belum diketahui"}
                  {(s.makloon_orders || []).map((m) => (
                    <span key={m.id} className="mt-0.5 block pl-3 text-[#5B3C00]" data-testid={`${tp}-pending-mko-${m.id}`}>
                      {m.number} ({docStatusLabel(m.status)}) · bahan {m.material_name}: dikunci {formatQty(m.material_reserved)} {m.material_unit}
                      {m.material_shortage > 0 ? ` · kurang ${formatQty(m.material_shortage)}` : ""}
                      {m.material_issued > 0 ? ` · dikirim ke mitra ${formatQty(m.material_issued)}` : ""}
                    </span>
                  ))}
                </p>
              ))}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
