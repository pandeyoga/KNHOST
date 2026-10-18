/** P03 — transfer antar gudang yang memenuhi SO ini (kaki 1 sebelum surat jalan pelanggan). */
import { useEffect, useState } from "react";
import { ArrowRightLeft } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { StatusBadge } from "../wms/transfer/transferConstants";

export default function OrderTransferLinks({ orderId }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    let on = true;
    if (!orderId) return undefined;
    axios.get(`${API}/transfers`, { params: { sales_order_id: orderId } })
      .then((r) => { if (on) setRows(Array.isArray(r.data) ? r.data : []); })
      .catch(() => { if (on) setRows([]); });
    return () => { on = false; };
  }, [orderId]);
  if (!rows.length) return null;
  return (
    <div data-testid="order-transfer-links" className="mb-2 space-y-1">
      <p className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Transfer pemenuhan</p>
      {rows.map((t) => (
        <div key={t.id} data-testid={`order-transfer-${t.id}`} className="flex items-center justify-between gap-2 rounded border border-[#E5EEFB] bg-white px-2 py-1.5">
          <p className="min-w-0 text-[10.5px]">
            <ArrowRightLeft size={10} className="mr-1 inline text-[#0058CC]" />
            <b>{t.code}</b> <span className="text-[#6B6B73]">{t.source_warehouse_name} → {t.dest_warehouse_name}</span>
          </p>
          <StatusBadge status={t.status} />
        </div>
      ))}
      <p className="text-[9.5px] text-[#8E8E93]">Barang tiba di gudang tujuan belum berarti terkirim ke pelanggan — lihat surat jalan di bawah.</p>
    </div>
  );
}
