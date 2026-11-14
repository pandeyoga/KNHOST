import { useEffect, useState } from "react";
import { PencilLine, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { overlayDismiss } from "../../utils/overlayDismiss";
import { apiErrorText } from "../../utils/apiError";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import { OverrideLinesEditor } from "./OverrideLinesEditor";
import { accountText, PESAN_REKENING_KOSONG } from "../pos/CheckoutPaymentDestination";

const num = (v) => (v === "" || v == null ? null : Number(v));

// PK-38 (FX-16) — sama dengan server (`so_override_service.lebih_longgar`): persen wajib-bayar sebelum kirim turun, atau
// sama dan hari tempo bertambah. Termin tak dikenal = 0 % / 0 hari.
const bentuk = (t) => ({ dp: Number(t?.dp_percent) || 0, hari: Number(t?.net_days) || 0 });
export function terminLebihLonggar(lama, baru) {
  const a = bentuk(lama); const b = bentuk(baru);
  return b.dp < a.dp || (b.dp === a.dp && b.hari > a.hari);
}
export const PETUNJUK_TERMIN_MATI = "Butuh akses pengecualian kirim sebelum bayar";
export const PERINGATAN_TERMIN_LONGGAR = "Termin ini lebih longgar. Pesanan bisa dikirim sebelum dibayar; perubahan dicatat atas nama Anda.";

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
  // PK-38 — termin yang lebih longgar dari termin pesanan sekarang mati bila server bilang pelaku tidak berizin.
  const termNow = ctx?.current_term || null;
  const longgar = (t) => Boolean(termNow) && t.code !== termNow.code && terminLebihLonggar(termNow, t);
  const termOptions = terms.map((t) => {
    const mati = longgar(t) && !ctx?.can_loosen_term;
    return { value: t.code, label: mati ? `${t.name} — ${PETUNJUK_TERMIN_MATI}` : t.name, disabled: mati };
  });
  const termPicked = terms.find((t) => t.code === header.payment_term_code);
  const warnLoosen = Boolean(termPicked) && Boolean(ctx?.can_loosen_term) && longgar(termPicked);
  // PM-T2 — cara bayar & rekening tujuan: pilihan dari server (daftar induk + rekening penerimaan PT pesanan).
  const payMethod = hv("payment_method_code");
  const payRow = (ctx?.payment_methods || []).find((m) => m.code === payMethod) || null;
  const accRows = (ctx?.receiving_accounts || {})[payMethod] || [];
  const pickMethod = (v) => {
    const rows = (ctx?.receiving_accounts || {})[v] || [];
    const def = rows.find((a) => a.is_default) || (rows.length === 1 ? rows[0] : null);
    setHeader((cur) => ({ ...cur, payment_method_code: v, receiving_account_id: def ? def.id : "" }));
  };

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
                  options={termOptions} />
                {warnLoosen && (
                  <p data-testid="override-term-loosen-warning" className="mt-1 text-fs-12 text-kn-warning-text">{PERINGATAN_TERMIN_LONGGAR}</p>
                )}
              </div>
              <div>
                <span className="field-label">Cara bayar</span>
                <KNSelect data-testid="override-payment-method" className="field" value={payMethod} onValueChange={pickMethod}
                  options={[{ value: "", label: "Belum ditentukan" },
                    ...(ctx.payment_methods || []).map((m) => ({ value: m.code, label: m.name }))]} />
              </div>
              <div>
                <span className="field-label">Rekening tujuan</span>
                {payRow?.needs_account !== "bank" ? (
                  <p className="text-fs-12 text-kn-text-2" data-testid="override-account-none">
                    {payMethod ? "Cara bayar ini tidak memakai rekening bank." : "Pilih cara bayar dulu."}
                  </p>
                ) : accRows.length === 0 ? (
                  <p className="text-fs-12 text-kn-warning-text" data-testid="override-account-empty">{PESAN_REKENING_KOSONG}</p>
                ) : (
                  <KNSelect data-testid="override-receiving-account" className="field" value={hv("receiving_account_id")}
                    placeholder="Pilih rekening tujuan" onValueChange={(v) => setH("receiving_account_id", v)}
                    options={accRows.map((a) => ({ value: a.id, label: accountText(a) }))} />
                )}
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">Metode</label>
                <KNSelect data-testid="override-method" className="field" value={hv("fulfillment_method") || "kirim"} onValueChange={(v) => setH("fulfillment_method", v)}
                  options={[{ value: "kirim", label: "Dikirim" }, { value: "ambil", label: "Diambil di gudang" }]} />
              </div>
              <div>
                <label className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">{hv("fulfillment_method") === "ambil" ? "Tanggal ambil" : "Tanggal kirim (opsional)"}</label>
                {hv("fulfillment_method") === "ambil"
                  ? <KNDatePicker data-testid="override-pickup-date" value={hv("pickup_date")} onChange={(v) => setH("pickup_date", v)} />
                  : <KNDatePicker data-testid="override-delivery-date" value={hv("delivery_date")} onChange={(v) => setH("delivery_date", v)} />}
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
