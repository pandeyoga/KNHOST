import { useState } from "react";
import { ClipboardList, Printer } from "lucide-react";
import { deliveryManifest } from "./logisticsApi";

// L07 LN-071 — manifest armada: semua SO + SJ + roll yang diangkut satu pengiriman.
export default function ManifestPanel({ deliveryId }) {
  const [m, setM] = useState(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(false);

  async function toggle() {
    if (open) { setOpen(false); return; }
    setOpen(true); setErr("");
    try { setM(await deliveryManifest(deliveryId)); } catch (e) { setErr(e.response?.data?.detail || "Gagal memuat manifest."); }
  }

  return (
    <div className="mt-3" data-testid="logistics-manifest">
      <button type="button" data-testid="logistics-manifest-toggle" className="secondary-button !py-1 !px-2 !text-[11px]" onClick={toggle}>
        <ClipboardList size={12} /> {open ? "Tutup manifest" : "Lihat manifest armada"}</button>
      {open && err && <p className="text-[11px] text-[#C0341D] mt-1" data-testid="logistics-manifest-error">{err}</p>}
      {open && m && (
        <div className="mt-2 rounded-lg border border-[#E1E4EA] p-2.5 print-area" data-testid="logistics-manifest-body">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <p className="text-[12px] font-bold">Manifest {m.number} · {m.mode_label}{m.vehicle_plate ? ` · ${m.vehicle_plate}` : ""}{m.driver_name ? ` · ${m.driver_name}` : ""}</p>
            <span className="text-[11px] text-[#6B6B73]" data-testid="logistics-manifest-totals">{m.totals.orders} pesanan · {m.totals.shipments} SJ · {m.totals.rolls} roll</span>
            <button type="button" className="icon-button" title="Cetak" data-testid="logistics-manifest-print" onClick={() => window.print()}><Printer size={13} /></button>
          </div>
          {m.orders.map((o) => (
            <div key={o.order_id} className="mt-2 border-t border-[#F0F1F3] pt-1.5" data-testid={`logistics-manifest-order-${o.order_id}`}>
              <p className="text-[11.5px] font-semibold">{o.order_number} · {o.customer_name}</p>
              {o.destination && <p className="text-[10.5px] text-[#6B6B73]">{o.destination}</p>}
              {o.shipments.map((s) => (
                <p key={s.shipment_id} className="text-[11px] mt-0.5" data-testid={`logistics-manifest-sj-${s.shipment_id}`}>
                  <span className="font-mono font-bold text-[#0058CC]">{s.shipment_no}</span> · {s.product_name} · {s.qty} {s.unit}
                  {s.is_partial ? " (sebagian)" : ""} · {s.warehouse_name}
                  <span className="block text-[10.5px] text-[#6B6B73] font-mono">{s.rolls.map((r) => r.roll_no || r.roll_id).join(", ")}</span></p>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
