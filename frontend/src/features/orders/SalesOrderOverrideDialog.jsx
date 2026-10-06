import { useEffect, useState } from "react";
import { PencilLine, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { overlayDismiss } from "../../utils/overlayDismiss";
import { apiErrorText } from "../../utils/apiError";
import KNSelect from "../../components/KNSelect";
import { OverrideLinesEditor } from "./OverrideLinesEditor";

const num = (v) => (v === "" || v == null ? null : Number(v));

/**
 * 2026-10 — OVERRIDE SO (Admin Sales · Manager · Admin), hanya sebelum picking.
 * Header & baris langsung berlaku (tercatat amandemen); harga/diskon → menunggu
 * persetujuan Manager / Admin / Finance. POST /sales-orders/{id}/override.
 */
export default function SalesOrderOverrideDialog({ order, onClose, onDone }) {
  const [ctx, setCtx] = useState(null);
  const [terms, setTerms] = useState([]);
  const [header, setHeader] = useState({});
  const [lines, setLines] = useState({});
  const [adds, setAdds] = useState([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    axios.get(`${API}/sales-orders/${order.id}/override-context`).then((r) => setCtx(r.data))
      .catch((e) => setError(apiErrorText(e, "Gagal memuat data override.")));
    axios.get(`${API}/payment-terms`).then((r) => setTerms(Array.isArray(r.data) ? r.data : [])).catch(() => setTerms([]));
  }, [order.id]);

  const hv = (k) => header[k] ?? order[k] ?? "";
  const setH = (k, v) => setHeader((cur) => ({ ...cur, [k]: v }));
  const locked = ctx?.locked_reason;

  async function submit() {
    setBusy(true); setError("");
    try {
      const body = {
        note,
        header: Object.fromEntries(Object.entries(header).map(([k, v]) => [k, v ?? ""])),
        lines: Object.entries(lines).map(([product_id, v]) => ({
          product_id, remove: !!v.remove, quantity: num(v.quantity), price: num(v.price), discount_percent: num(v.discount_percent),
        })),
        add_items: adds.map((a) => ({ product_id: a.product_id, quantity: Number(a.quantity) || 0 })),
      };
      const res = await axios.post(`${API}/sales-orders/${order.id}/override`, body);
      const pa = res.data.price_amendment;
      onDone?.(`${order.number} diperbarui (${res.data.changes.length} perubahan langsung berlaku)`
        + (pa ? ` · harga/diskon menunggu persetujuan ${pa.number}` : ""));
    } catch (e) { setError(apiErrorText(e, "Override gagal disimpan.")); }
    finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 180 }} data-testid="so-override-dialog" {...overlayDismiss(onClose)}>
      <div className="modal-card" style={{ maxWidth: 720, maxHeight: "92vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="modal-title flex items-center gap-2"><PencilLine size={15} className="text-[#0058CC]" /> Edit / Override {order.number}</p>
            <p className="modal-subtitle">{order.customer_name} · perubahan langsung berlaku & tercatat sebagai amandemen. Harga/diskon menunggu persetujuan Manager / Admin / Finance.</p>
          </div>
          <button className="icon-button" onClick={onClose} data-testid="so-override-close"><X size={16} /></button>
        </div>
        {error && <div className="notice-bar danger mt-2" data-testid="so-override-error"><span>{error}</span></div>}
        {locked && <div className="notice-bar warning mt-2" data-testid="so-override-locked"><span>{locked}</span></div>}
        {ctx && !locked && (
          <div className="mt-3 space-y-3">
            <div className="grid gap-2 sm:grid-cols-2" data-testid="so-override-header">
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Alamat kirim</label>
                <KNSelect data-testid="override-address" className="field" value={hv("shipping_address_id")} onValueChange={(v) => setH("shipping_address_id", v)}
                  options={(ctx.addresses || []).map((a) => ({ value: a.id, label: `${a.label} — ${a.city || ""}` }))} />
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Termin bayar</label>
                <KNSelect data-testid="override-term" className="field" value={hv("payment_term_code")} onValueChange={(v) => setH("payment_term_code", v)}
                  options={terms.map((t) => ({ value: t.code, label: t.name }))} />
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Metode</label>
                <KNSelect data-testid="override-method" className="field" value={hv("fulfillment_method") || "kirim"} onValueChange={(v) => setH("fulfillment_method", v)}
                  options={[{ value: "kirim", label: "Dikirim" }, { value: "ambil", label: "Diambil di gudang" }]} />
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">{hv("fulfillment_method") === "ambil" ? "Tanggal ambil" : "Tanggal kirim (opsional)"}</label>
                {hv("fulfillment_method") === "ambil"
                  ? <input type="date" data-testid="override-pickup-date" className="field" value={hv("pickup_date")} onChange={(e) => setH("pickup_date", e.target.value)} />
                  : <input type="date" data-testid="override-delivery-date" className="field" value={hv("delivery_date")} onChange={(e) => setH("delivery_date", e.target.value)} />}
              </div>
              <textarea data-testid="override-notes" className="field sm:col-span-2" rows={2} placeholder="Catatan pesanan" value={hv("notes")} onChange={(e) => setH("notes", e.target.value)} />
            </div>
            <OverrideLinesEditor items={order.items || []} lines={lines} setLines={setLines} adds={adds} setAdds={setAdds} />
            <textarea data-testid="override-reason" className="field w-full" rows={2} placeholder="Alasan override (wajib, min. 5 karakter) — dikirim ke sales pemilik pesanan"
              value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="flex justify-end gap-2">
              <button className="secondary-button" data-testid="so-override-cancel" onClick={onClose}>Batal</button>
              <button className="primary-button" data-testid="so-override-submit" disabled={busy || note.trim().length < 5} onClick={submit}>
                {busy ? "Menyimpan…" : "Simpan Override"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
