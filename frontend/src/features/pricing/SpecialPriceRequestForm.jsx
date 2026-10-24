import { useEffect, useRef, useState } from "react";
import { Paperclip, Send, ChevronDown, ChevronUp, Info } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import KNDatePicker from "@/components/KNDatePicker";
import MoneyInput from "@/components/MoneyInput";

/**
 * §3-B — SATU komponen permintaan harga khusus, dipakai di 4 pintu (POS, detail SO,
 * layar Persetujuan Harga, mobile). Bawaan: harga + bukti (WAJIB, ditegakkan backend);
 * jumlah minimum / berlaku sampai / "jadikan harga langganan" tersembunyi di "Atur lebih lanjut".
 * Alur: POST /price-approvals (draf) → POST attachments → POST /submit → onSubmitted(doc).
 *
 * Audit UI 24 Okt (002 / HP Minta Harga Khusus) — form ini boleh dirender SEBELUM pelanggan & produk dipilih
 * (pemilihnya di atas form, milik pemanggil). Dulu layar Persetujuan Harga MENGGANTI isi modal dengan form ini
 * setelah keduanya dipilih, sehingga isian yang sudah diketik hilang; kini form tetap terpasang dan isiannya
 * tidak hilang saat pelanggan/produk diganti. `allowDraft` menambah "Simpan sebagai Draf" (tanpa kirim; bukti
 * boleh menyusul dari kartu pengajuan).
 */
export default function SpecialPriceRequestForm({ product, customer, entityId = "", soId = "", defaultQty = 0, onSubmitted, onCancel, compact = false, allowDraft = false }) {
  const normalPrice = Number(product?.price || 0);
  const [price, setPrice] = useState("");
  const [file, setFile] = useState(null);
  const [more, setMore] = useState(false);
  const [minQty, setMinQty] = useState(defaultQty ? String(Math.round(defaultQty)) : "");
  const [validUntil, setValidUntil] = useState("");
  // Cek UI UAT v3 (S4) — tanpa SO, lingkup "pesanan ini saja" tidak punya pesanan untuk ditempeli: harga langganan.
  const [standing, setStanding] = useState(!soId);
  const [reason, setReason] = useState("");
  const [hint, setHint] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(null);
  const fileRef = useRef(null);
  const priceNum = parseFloat(price);

  useEffect(() => {
    if (!(priceNum > 0) || !product?.id) { setHint(null); return undefined; }
    const t = setTimeout(() => {
      axios.get(`${API}/price-approvals/hint`, { params: { product_id: product.id, price: priceNum, entity_id: entityId || "" } })
        .then((r) => setHint(r.data)).catch(() => setHint(null));
    }, 350);
    return () => clearTimeout(t);
  }, [priceNum, product?.id, entityId]);

  // asDraft=true → simpan draf saja (bukti opsional; dikirim nanti dari kartu pengajuan).
  const submit = async (asDraft = false) => {
    setErr("");
    if (!customer?.id) { setErr("Pilih pelanggan dulu."); return; }
    if (!product?.id) { setErr("Pilih produk dulu."); return; }
    if (!(priceNum > 0)) { setErr("Harga khusus harus lebih dari 0."); return; }
    if (normalPrice > 0 && priceNum >= normalPrice) { setErr("Harga khusus harus lebih rendah dari harga daftar."); return; }
    if (!asDraft && !file) { setErr("Bukti (tangkapan chat/penawaran) wajib dilampirkan."); return; }
    setBusy(true);
    try {
      const { data: draft } = await axios.post(`${API}/price-approvals`, {
        customer_id: customer.id, product_id: product.id, requested_price: priceNum,
        min_quantity: parseFloat(minQty) || 0, valid_until: standing ? (validUntil || "") : "",
        reason: reason || "", submit_now: false, entity_id: entityId || "",
        scope: standing ? "standing" : "order", so_id: soId || "",
      });
      if (file) {
        const fd = new FormData(); fd.append("file", file);
        await axios.post(`${API}/price-approvals/${draft.id}/attachments`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      if (asDraft) { onSubmitted?.(draft); return; }
      const { data: sent } = await axios.post(`${API}/price-approvals/${draft.id}/submit`);
      setDone(sent);
      onSubmitted?.(sent);
    } catch (e) {
      const d = e.response?.data?.detail;
      setErr((d && (d.message || d)) || "Gagal mengajukan harga khusus.");
    } finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="notice-bar success" data-testid="spr-submitted">
        <b>Terkirim — menunggu persetujuan.</b> {done.number ? `${done.number} · ` : ""}{formatCurrency(done.requested_price)} ·
        {done.scope === "standing" ? " harga langganan" : " untuk pesanan ini saja"} · penyetuju: {hint?.approver_label || "Manajer / Admin"} · diajukan baru saja.
      </div>
    );
  }
  const pct = normalPrice > 0 && priceNum > 0 ? Math.round((1 - priceNum / normalPrice) * 1000) / 10 : 0;
  return (
    <div className={`space-y-3 ${compact ? "text-sm" : ""}`} data-testid="special-price-request-form">
      {product?.id ? (
        <div className="text-xs text-[#6E6E73]" data-testid="spr-product-line">{product?.name} · harga daftar <b className="tabular-nums">{formatCurrency(normalPrice)}</b>{customer?.name ? ` · ${customer.name}` : ""}</div>
      ) : (
        <div className="text-xs text-[#6E6E73]" data-testid="spr-pick-hint">Pilih pelanggan dan produk dulu — harga daftar produk tampil di sini sebagai pembanding.</div>
      )}
      <label className="grid gap-1"><span className="field-label">Harga yang diminta pelanggan *</span>
        <MoneyInput value={price} onChange={setPrice} placeholder="0" testId="spr-price-input" /></label>
      {priceNum > 0 && (
        <div className={`notice-bar ${hint?.needs_manager ? "danger" : "success"} flex items-center gap-2`} data-testid="spr-hint">
          <Info size={14} /> <span>{pct}% di bawah harga daftar{hint ? ` — ${hint.verdict}` : ""}</span>
        </div>
      )}
      <div className="grid gap-1">
        <span className="field-label">Bukti chat / penawaran {allowDraft ? "(wajib saat diajukan)" : "*"}</span>
        <input ref={fileRef} type="file" accept="image/*,.pdf" className="hidden" data-testid="spr-file-input"
          onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button type="button" className="secondary-button w-full flex items-center justify-center gap-2" onClick={() => fileRef.current?.click()} data-testid="spr-file-btn">
          <Paperclip size={14} /> <span className="truncate">{file ? file.name : "Lampirkan bukti chat / penawaran"}</span>
        </button>
      </div>
      {!soId && (
        <p className="text-[11px] text-[#6B6B73]" data-testid="spr-standing-note">Belum ada pesanan → harga ini menjadi <b>harga langganan</b> pelanggan
          (otomatis dipakai di pesanan berikutnya; atur <i>Berlaku sampai</i> di bawah). Untuk satu pesanan saja: buat SO dulu, lalu ajukan dari kotak Persetujuan di SO.</p>
      )}
      <button type="button" className="text-xs text-[#0058CC] flex items-center gap-1" onClick={() => setMore((m) => !m)} data-testid="spr-more-toggle">
        {more ? <ChevronUp size={12} /> : <ChevronDown size={12} />} Atur lebih lanjut
      </button>
      {more && (
        <div className="space-y-2 rounded-md border border-[#E5E5EA] p-2">
          <label className="grid gap-1"><span className="field-label">Catatan / alasan</span><input className="field" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="spr-reason-input" /></label>
          <label className="grid gap-1"><span className="field-label">Jumlah minimum</span><input className="field tabular-nums" type="number" min="0" value={minQty} onChange={(e) => setMinQty(e.target.value)} data-testid="spr-minqty-input" /></label>
          {soId && (
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={standing} onChange={(e) => setStanding(e.target.checked)} data-testid="spr-standing-toggle" />
              Jadikan harga langganan pelanggan ini (berlaku untuk pesanan berikutnya)</label>
          )}
          {standing && <div className="grid gap-1"><span className="field-label">Berlaku sampai</span><KNDatePicker value={validUntil} onChange={setValidUntil} data-testid="spr-valid-until" /></div>}
        </div>
      )}
      {err && <div className="notice-bar danger" data-testid="spr-error">{String(err)}</div>}
      <div className="flex flex-wrap gap-2">
        {onCancel && <button type="button" className="secondary-button flex-1" disabled={busy} onClick={onCancel} data-testid="spr-cancel">Batal</button>}
        {allowDraft && (
          <button type="button" className="secondary-button flex-1 whitespace-nowrap" disabled={busy} onClick={() => submit(true)} data-testid="spr-save-draft">
            Simpan sebagai Draf
          </button>
        )}
        <button type="button" className="primary-button flex-1 flex items-center justify-center gap-2 whitespace-nowrap" disabled={busy} onClick={() => submit(false)} data-testid="spr-submit">
          <Send size={14} /> {busy ? "Mengirim…" : "Ajukan"}
        </button>
      </div>
    </div>
  );
}
