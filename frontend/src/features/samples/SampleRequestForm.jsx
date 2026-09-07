import { useEffect, useState } from "react";
import { Scissors, Send } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import { formatCurrency } from "../../utils/formatters";

/** §3-C — SATU form permintaan sampel (sales, mobile & desktop). Harga per satuan roll × panjang. */
export default function SampleRequestForm({ compact = false, onSubmitted }) {
  const [custs, setCusts] = useState([]); const [prods, setProds] = useState([]);
  const [cid, setCid] = useState(""); const [pid, setPid] = useState("");
  const [length, setLength] = useState(""); const [method, setMethod] = useState("cash"); const [notes, setNotes] = useState("");
  const [quote, setQuote] = useState(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [done, setDone] = useState(null);
  useEffect(() => {
    axios.get(`${API}/customers`).then((r) => setCusts(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {});
    axios.get(`${API}/products`).then((r) => setProds(Array.isArray(r.data) ? r.data : r.data.items || [])).catch(() => {});
  }, []);
  const len = parseFloat(length);
  useEffect(() => {
    if (!pid || !(len > 0)) { setQuote(null); return undefined; }
    const t = setTimeout(() => axios.get(`${API}/sample-requests/quote`, { params: { product_id: pid, length: len } }).then((r) => setQuote(r.data)).catch(() => setQuote(null)), 300);
    return () => clearTimeout(t);
  }, [pid, len]);
  const submit = async () => {
    setErr("");
    if (!cid || !pid || !(len > 0)) { setErr("Pilih pelanggan, produk, dan isi panjang sampel."); return; }
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/sample-requests`, { customer_id: cid, product_id: pid, length: len, payment_method: method, notes });
      setDone(data); onSubmitted?.(data);
    } catch (e) { const d = e.response?.data?.detail; setErr((d && (d.message || d)) || "Gagal mengajukan sampel."); }
    finally { setBusy(false); }
  };
  if (done) {
    return (
      <div className="notice-bar success" data-testid="sample-submitted">
        <b>{done.number}</b> terkirim ke gudang — {done.length} {done.unit} × {formatCurrency(done.price_per_unit)} = <b>{formatCurrency(done.amount)}</b>
        {done.suggested_roll_no ? ` · saran roll FIFO ${done.suggested_roll_no}` : " · belum ada roll yang cukup panjang (gudang akan memilih)"}.
        <button type="button" className="ml-2 underline text-xs" onClick={() => { setDone(null); setLength(""); }} data-testid="sample-again">Ajukan lagi</button>
      </div>
    );
  }
  return (
    <div className={`space-y-3 ${compact ? "text-sm" : ""}`} data-testid="sample-request-form">
      <KNSelect data-testid="sample-customer" placeholder="Pilih pelanggan" value={cid} onValueChange={setCid} options={custs.map((c) => ({ value: c.id, label: c.name }))} />
      <KNSelect data-testid="sample-product" placeholder="Pilih produk (varian)" value={pid} onValueChange={setPid} options={prods.map((p) => ({ value: p.id, label: `${p.name}${p.variant_label ? ` · ${p.variant_label}` : ""} (${p.sku})` }))} />
      <div className="grid grid-cols-2 gap-2">
        <label className="field"><span>Panjang ({quote?.unit || prods.find((p) => p.id === pid)?.base_unit || "yard"})</span>
          <input type="number" step="0.1" min="0" value={length} onChange={(e) => setLength(e.target.value)} data-testid="sample-length" /></label>
        <KNSelect data-testid="sample-method" value={method} onValueChange={setMethod} className="field"
          options={[{ value: "cash", label: "Tunai" }, { value: "transfer", label: "Transfer" }]} />
      </div>
      {quote && (
        <div className="notice-bar info" data-testid="sample-quote">
          <Scissors size={14} className="inline mr-1" />{quote.length} {quote.unit} × {formatCurrency(quote.price_per_unit)} ({quote.source === "master_sampel" ? "master sampel" : "harga daftar"}) = <b>{formatCurrency(quote.amount)}</b>
          {quote.suggested_roll ? <> · saran FIFO <b>{quote.suggested_roll.roll_no}</b> (sisa {quote.suggested_roll.length_remaining})</> : <> · <b>tidak ada roll cukup panjang</b></>}
        </div>
      )}
      <input className="w-full rounded-md border p-2" placeholder="Catatan untuk gudang (opsional)" value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="sample-notes" />
      {err && <div className="notice-bar danger" data-testid="sample-error">{String(err)}</div>}
      <button type="button" className="primary-button w-full flex items-center justify-center gap-2" disabled={busy} onClick={submit} data-testid="sample-submit"><Send size={14} /> {busy ? "Mengirim…" : "Ajukan potong sampel"}</button>
    </div>
  );
}
