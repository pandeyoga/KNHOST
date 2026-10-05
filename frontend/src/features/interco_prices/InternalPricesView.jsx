import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeftRight, RefreshCw } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import InternalPriceBulkPanel from "./InternalPriceBulkPanel";
import { internalPriceAccess, internalPriceSummary } from "./internalPriceApi";

export const entitiesFromSummary = (summary) => {
  const m = new Map();
  (summary?.pairs || []).forEach((p) => { m.set(p.seller_entity_id, p.seller_name); m.set(p.buyer_entity_id, p.buyer_name); });
  return [...m.entries()].map(([id, name]) => ({ id, name }));
};

/** Ringkasan "barang ber-stok tanpa harga internal" per pasangan PT (dua arah). */
export function InternalPriceSummary({ summary, onPick }) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="ic-price-summary">
      {(summary?.pairs || []).map((p) => (
        <button key={`${p.seller_entity_id}-${p.buyer_entity_id}`} type="button" onClick={() => onPick?.(p)}
          data-testid={`ic-price-pair-${p.seller_entity_id}-${p.buyer_entity_id}`}
          className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2 text-left hover:border-[#0058CC]">
          <p className="text-[11px] font-semibold text-[#3C3C43]">{p.seller_name} → {p.buyer_name}</p>
          <p className={`text-[14px] font-bold tabular-nums ${p.missing ? "text-[#B26A00]" : "text-[#1B7F4B]"}`}>
            {p.missing ? `${p.missing} tanpa harga` : "Lengkap"}
          </p>
          <p className="text-[10px] text-[#8E8E93]">dari {p.stocked} barang ber-stok</p>
        </button>
      ))}
    </div>
  );
}

function urlInitial() {
  const sp = new URLSearchParams(window.location.search);
  return { seller: sp.get("seller") || "", buyer: sp.get("buyer") || "", q: sp.get("q") || "" };
}

export default function InternalPricesView() {
  const [summary, setSummary] = useState(null);
  const [access, setAccess] = useState({});
  const [pair, setPair] = useState(urlInitial);
  const [error, setError] = useState("");
  const entities = useMemo(() => entitiesFromSummary(summary), [summary]);

  const load = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([internalPriceSummary(), internalPriceAccess()]);
      setSummary(s); setAccess(a); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat harga internal.")); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div data-testid="internal-prices-view" className="space-y-3">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="internal-prices-error" />
      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2"><ArrowLeftRight size={16} className="text-[#0058CC]" />
            <h2 data-testid="internal-prices-title">Harga Internal Antar-PT</h2></div>
          <button className="secondary-button" onClick={load} data-testid="internal-prices-refresh"><RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body space-y-3">
          <p className="text-[11.5px] text-[#6B6B73]">Harga yang dipakai saat barang dipindah antar-PT (transfer pemenuhan pesanan). Ditetapkan oleh MD, Finance, atau Admin; berlaku per arah PT penjual → pembeli.</p>
          <InternalPriceSummary summary={summary} onPick={(p) => setPair({ seller: p.seller_entity_id, buyer: p.buyer_entity_id, q: "" })} />
        </div>
      </div>
      {entities.length > 1 && (
        <div className="section-card"><div className="section-body">
          <InternalPriceBulkPanel key={`${pair.seller}-${pair.buyer}`} entities={entities} initial={pair} canSet={!!access.can_set} onSaved={load} />
        </div></div>
      )}
    </div>
  );
}
