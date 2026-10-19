import { useEffect, useState } from "react";
import { Scissors } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { SAMPLE_KINDS, sampleLimit } from "../../utils/sampleOrder";

const SRC = { master_sampel: "master harga sample", harga_daftar: "harga daftar", manual_sampel: "harga manual" };

/** §3-C — baris "Jual sebagai sample" di checkout: quote harga sample + saran roll FIFO + harga manual. */
export function SampleLineFields({ item, onUpdateSample, billing = "", onToggleSample }) {
  const pid = item.product.id;
  const unit = item.product.base_unit || "meter";
  const len = Number(item.quantity || 0);
  const [quote, setQuote] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!(len > 0)) { setQuote(null); return undefined; }
    let cancelled = false;
    const t = setTimeout(() => axios.get(`${API}/sample-quote`, { params: { product_id: pid, length: len } })
      .then((r) => { if (cancelled) return; setQuote(r.data); setErr(""); onUpdateSample(pid, { sample_unit_price: Number(r.data.price_per_unit || 0), sample_source: r.data.source, suggested_roll_no: r.data.suggested_roll?.roll_no || "" }); })
      .catch(() => { if (!cancelled) setErr("Harga sample tidak bisa dimuat."); }), 300);
    return () => { cancelled = true; clearTimeout(t); };
  }, [pid, len]); // eslint-disable-line
  const manual = item.sample_price;
  const effective = Number(manual) > 0 ? Number(manual) : Number(quote?.price_per_unit || 0);
  const isFree = billing === "free";
  return (
    <div data-testid={`sample-fields-${pid}`} className="mt-2 rounded-md border border-[#F3D9A4] bg-[#FFF9EC] p-2 text-[11px]">
      <p className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-[#9A5B00]"><Scissors size={11} /> Sample {isFree ? "gratis" : billing === "paid" ? "berbayar" : ""} — permintaan potong ke gudang</p>
      {quote && (
        <p data-testid={`sample-quote-${pid}`} className="mt-1 text-[#3C3C43]">
          {!isFree && <>{SRC[quote.source] || quote.source}: <b>{formatCurrency(quote.price_per_unit)}</b>/{unit} · </>}
          {quote.suggested_roll ? <>saran FIFO <b>{quote.suggested_roll.roll_no}</b> (sisa {formatQty(quote.suggested_roll.length_remaining)})</> : <><b className="text-[#B23B14]">belum ada roll cukup panjang</b> (gudang memilih)</>}
        </p>
      )}
      <SampleKindPicker item={item} onUpdateSample={onUpdateSample} onToggleSample={onToggleSample} />
      {err && <p className="mt-1 text-[#B23B14]">{err}</p>}
      {isFree ? (
        <p data-testid={`sample-free-note-${pid}`} className="mt-1.5 text-[#126E2C]">Gratis — tidak ditagihkan (Rp 0).</p>
      ) : (
      <div className="mt-1.5 grid grid-cols-[1fr_auto] items-end gap-2">
        <div>
          <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Harga manual /{unit} (opsional)</label>
          <input data-testid={`sample-price-input-${pid}`} className="field" type="number" min="0" step="100" placeholder={quote ? String(quote.price_per_unit) : "0"}
            value={manual ?? ""} onChange={(e) => onUpdateSample(pid, { sample_price: e.target.value === "" ? null : Math.max(0, Number(e.target.value) || 0) })} />
        </div>
        <div className="text-right">
          <p className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Subtotal</p>
          <p data-testid={`sample-subtotal-${pid}`} className="text-[12px] font-semibold tabular-nums">{formatCurrency(effective * len)}</p>
        </div>
      </div>
      )}
    </div>
  );
}

/** L06 LN-060 — jenis sample (batas maksimal, tidak memaksa naik) + jalur ecer berbayar bila melebihi batas. */
function SampleKindPicker({ item, onUpdateSample, onToggleSample }) {
  const pid = item.product.id;
  const kind = item.sample_kind || "standard";
  const lim = sampleLimit(item.product, kind);
  const over = Number(item.quantity || 0) > lim.max_qty + 1e-6;
  return (
    <div className="mt-1.5" data-testid={`sample-kind-${pid}`}>
      <div className="flex flex-wrap items-center gap-1">
        {Object.entries(SAMPLE_KINDS).map(([k, v]) => (
          <button key={k} type="button" data-testid={`sample-kind-${pid}-${k}`} onClick={() => onUpdateSample(pid, { sample_kind: k })}
            className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors ${kind === k ? "border-[#9A5B00] bg-[#9A5B00] text-white" : "border-[#F3D9A4] bg-white text-[#9A5B00] hover:bg-[#FFF3D6]"}`}>
            {v.label} · maks {formatQty(sampleLimit(item.product, k).max_qty)} {lim.limit_unit || lim.unit}
          </button>
        ))}
      </div>
      {over && (
        <p data-testid={`sample-over-limit-${pid}`} className="mt-1 text-[#B23B14]">
          Melebihi batas sample {SAMPLE_KINDS[kind].label.toLowerCase()} — kurangi, atau jual sebagai <b>ecer berbayar</b> (pesanan biasa terpisah).
          {onToggleSample && <button type="button" data-testid={`sample-to-retail-${pid}`} className="ml-1 underline font-semibold" onClick={() => onToggleSample(pid)}>Jadikan ecer</button>}
        </p>
      )}
    </div>
  );
}
