import { useEffect, useState } from "react";
import axios, { API } from "../services/apiClient";
import { formatQty } from "../utils/formatters";

/** P04 IMP-04 — ringkasan stok Sales: Reguler & BS terpisah; fisik/dikunci/bebas/datang/ATP tidak dicampur.
 *  FIX-2 (B3a STK-6/SSOT-4) — angka server kini definisi tunggal (Fisik termasuk dialokasikan/proses; Bebas dikurangi
 *  cadangan makloon); cadangan makloon ditampilkan bila ada. Kosakata layar lama (Fisik/Dikunci/Bebas) tidak diubah
 *  (K-13, K-B4-06). Huruf 12 px (B4: ≥ 12 px desktop). */
export default function SalesStockSummary({ productId, entityId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!productId) return;
    const params = { product_id: productId };
    if (entityId && entityId !== "all") params.entity_id = entityId;
    axios.get(`${API}/sales/stock-summary`, { params }).then((r) => setData(r.data)).catch(() => setData(null));
  }, [productId, entityId]);
  if (!data?.rows?.length) return null;
  const u = data.unit;
  return (
    <div data-testid="sales-stock-summary" className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2 text-[12px]">
      {data.rows.map((r) => (
        <div key={r.class} data-testid={`sales-stock-${r.class}`} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 py-0.5">
          <b className={r.class === "bs" ? "text-[#9A5B00]" : "text-[#1C1C1E]"}>{r.label}</b>
          <span>Fisik {formatQty(r.physical)} {u}</span>
          <span>Dikunci {formatQty(r.reserved)} {u}</span>
          <span className="font-semibold text-[#126E2C]" data-testid={`sales-stock-${r.class}-free`}>Bebas {formatQty(r.free)} {u}</span>
          {Number(r.makloon_reserved || 0) > 0 && (
            <span className="text-[#8C4A00]" data-testid={`sales-stock-${r.class}-makloon`} title="Bahan dicadangkan untuk order makloon — tidak bisa dijanjikan">
              Cadangan makloon {formatQty(r.makloon_reserved)} {u}
            </span>
          )}
          {r.class === "regular" && (
            <span title={data.atp_definition} data-testid="sales-stock-incoming">
              Datang {formatQty(r.incoming)} {u} (belum siap kirim) · Menunggu {formatQty(r.pending_demand)} {u} · ATP <b data-testid="sales-stock-atp">{formatQty(r.atp)}</b>
            </span>
          )}
          {r.group_free > 0 && <span className="text-[#6B6B73]">+ grup {formatQty(r.group_free)} (keputusan Admin Sales)</span>}
        </div>
      ))}
      {data.atp_definition && <div className="pt-0.5 text-[#6B6B73]" data-testid="sales-stock-atp-definition">{data.atp_definition}</div>}
    </div>
  );
}
