import { useCallback, useEffect, useMemo, useState } from "react";
import { Save, Wand2 } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { SearchBox } from "../../components/ListControls";
import usePagedRows from "../../hooks/usePagedRows";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { internalPriceBulk, internalPriceMissing } from "./internalPriceApi";

const num = (v) => Number(String(v ?? "").replace(",", ".")) || 0;

/** Isi massal harga internal: pilih pasangan PT → tabel barang tanpa harga → isi harga → simpan sekaligus. */
export default function InternalPriceBulkPanel({ entities, initial = {}, canSet, onSaved }) {
  const [seller, setSeller] = useState(initial.seller || entities[0]?.id || "");
  const [buyer, setBuyer] = useState(initial.buyer || entities.find((e) => e.id !== (initial.seller || entities[0]?.id))?.id || "");
  const [q, setQ] = useState(initial.q || "");
  const [onlyStock, setOnlyStock] = useState(true);
  const [data, setData] = useState(null);
  const [prices, setPrices] = useState({});
  const [pct, setPct] = useState(70);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    if (!seller || !buyer || seller === buyer) { setData(null); return; }
    setLoading(true);
    try {
      setData(await internalPriceMissing({ seller_entity_id: seller, buyer_entity_id: buyer, only_stock: onlyStock }));
      setPrices({}); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat barang tanpa harga internal.")); }
    finally { setLoading(false); }
  }, [seller, buyer, onlyStock]);
  useEffect(() => { load(); }, [load]);

  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    const all = data?.rows || [];
    return t ? all.filter((r) => `${r.sku} ${r.product_name}`.toLowerCase().includes(t)) : all;
  }, [data, q]);
  const { pageRows, pager } = usePagedRows(rows, { pageSize: 20, testId: "ic-bulk-pager" });
  const filled = Object.entries(prices).filter(([, v]) => num(v) > 0);

  const fillPct = () => setPrices((cur) => {
    const next = { ...cur };
    rows.forEach((r) => { if (r.sell_price > 0 && !num(next[r.product_id])) next[r.product_id] = String(Math.round(r.sell_price * pct / 100)); });
    return next;
  });

  async function save() {
    setBusy(true); setError(""); setNotice("");
    try {
      const res = await internalPriceBulk({ seller_entity_id: seller, buyer_entity_id: buyer,
        items: filled.map(([product_id, v]) => ({ product_id, unit_price: num(v) })) });
      setNotice(`${res.count} harga internal tersimpan.`);
      await load(); onSaved?.();
    } catch (e) { setError(apiErrorText(e, "Gagal menyimpan harga internal.")); }
    finally { setBusy(false); }
  }

  const pick = (val, set, testId) => (
    <select data-testid={testId} className="field !h-9 text-[12px]" value={val} onChange={(e) => set(e.target.value)}>
      {entities.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
    </select>
  );

  return (
    <div data-testid="ic-bulk-panel" className="space-y-3">
      <ErrorNotice message={error} onDismiss={() => setError("")} testId="ic-bulk-error" />
      {notice && <p data-testid="ic-bulk-notice" className="rounded-lg bg-[#EAF7EF] px-3 py-2 text-[12px] font-semibold text-[#1B7F4B]">{notice}</p>}
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-[11px] font-semibold text-[#6B6B73]">PT penjual<div className="mt-1">{pick(seller, setSeller, "ic-bulk-seller")}</div></label>
        <span className="pb-2 text-[#9A9BA3]">→</span>
        <label className="text-[11px] font-semibold text-[#6B6B73]">PT pembeli<div className="mt-1">{pick(buyer, setBuyer, "ic-bulk-buyer")}</div></label>
        <label className="flex items-center gap-1.5 pb-2 text-[11.5px]">
          <input type="checkbox" data-testid="ic-bulk-only-stock" checked={onlyStock} onChange={(e) => setOnlyStock(e.target.checked)} />
          Hanya barang ber-stok di PT penjual
        </label>
      </div>
      {seller === buyer && <p className="text-[12px] text-[#C0392B]" data-testid="ic-bulk-same">PT penjual dan pembeli harus berbeda.</p>}
      <div className="flex flex-wrap items-center gap-2">
        <SearchBox value={q} onChange={setQ} placeholder="Cari SKU / nama barang…" testId="ic-bulk-search" />
        <span className="text-[11.5px] text-[#6B6B73]" data-testid="ic-bulk-count">
          {data ? `${data.total} barang belum punya harga · ${data.priced} sudah` : ""}
        </span>
        {canSet && (
          <div className="ml-auto flex items-center gap-1.5">
            <input data-testid="ic-bulk-pct" type="number" min={1} max={500} className="field !h-8 w-[70px] text-right text-[12px]"
              value={pct} onChange={(e) => setPct(num(e.target.value))} />
            <button className="secondary-button" data-testid="ic-bulk-fill-pct" onClick={fillPct} disabled={!rows.length || pct <= 0}>
              <Wand2 size={13} /> Isi % dari harga jual
            </button>
            <button className="primary-button" data-testid="ic-bulk-save" onClick={save} disabled={busy || !filled.length}>
              <Save size={13} /> {busy ? "Menyimpan…" : `Simpan ${filled.length} harga`}
            </button>
          </div>
        )}
      </div>
      <div className="overflow-x-auto rounded-xl border border-[#EFF0F2]">
        <table className="w-full text-[12px]">
          <thead className="bg-[#FAFBFC] text-left text-[10px] font-bold uppercase text-[#6B6B73]">
            <tr><th className="px-3 py-2">SKU / Barang</th><th className="px-3 py-2 text-right">Stok penjual</th>
              <th className="px-3 py-2 text-right">Harga jual penjual</th><th className="px-3 py-2 text-right">Harga internal</th></tr>
          </thead>
          <tbody className="divide-y divide-[#F2F2F5]">
            {loading ? <tr><td colSpan={4} className="py-8 text-center text-[#6B6B73]">Memuat…</td></tr>
              : !rows.length ? <tr><td colSpan={4} className="py-8 text-center text-[#6B6B73]" data-testid="ic-bulk-empty">Semua barang pada pasangan ini sudah punya harga internal.</td></tr>
              : pageRows.map((r) => (
                <tr key={r.product_id} data-testid={`ic-bulk-row-${r.product_id}`}>
                  <td className="px-3 py-1.5"><p className="font-mono text-[10.5px] text-[#8E8E93]">{r.sku}</p><p className="font-semibold">{r.product_name}</p></td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{formatQty(r.seller_stock)} {r.unit}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{r.sell_price > 0 ? formatCurrency(r.sell_price) : "—"}</td>
                  <td className="px-3 py-1.5 text-right">
                    <input data-testid={`ic-bulk-price-${r.product_id}`} type="number" min={0} disabled={!canSet}
                      className="field !h-8 w-[120px] text-right text-[12px]" placeholder="0" value={prices[r.product_id] || ""}
                      onChange={(e) => setPrices((cur) => ({ ...cur, [r.product_id]: e.target.value }))} />
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      {pager}
    </div>
  );
}
