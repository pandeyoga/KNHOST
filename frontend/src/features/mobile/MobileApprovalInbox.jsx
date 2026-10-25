import { useCallback, useEffect, useState } from "react";
import { Check, X, Tag, Package } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { apiErrorText, isForbiddenError } from "../../utils/apiError";
import { askReason } from "../../services/confirmService";
import { discountInfo } from "../sales/priceApprovals/priceApprovalText";

const asList = (d) => (Array.isArray(d) ? d : d?.items || []);
const SPECIAL_WAITING = ["pending_approval", "submitted", "pending"];
// UAT 24 Okt (audit UI tahap 2, G5-08) — 403 dulu ditelan jadi daftar kosong ("Tidak ada … yang menunggu"), seolah
// semua beres. Kini 403 dibedakan dari kosong dan disebut terang.
const loadErr = (e, what) => (isForbiddenError(e) ? `Anda tidak punya akses ke ${what}.` : apiErrorText(e, `${what} tidak bisa dimuat.`));

/**
 * Daftar harga khusus & pesanan khusus yang menunggu — dipakai tab Persetujuan DAN tab Notifikasi (lencana
 * "Putuskan di HP" hanya untuk dokumen yang memang ada di daftar ini). Hanya memuat daftar yang boleh diputus peran.
 */
export function usePendingApprovals({ canPrice = true, canSpecial = true } = {}) {
  const [prices, setPrices] = useState(canPrice ? null : []);
  const [specials, setSpecials] = useState(canSpecial ? null : []);
  const [errors, setErrors] = useState({});
  const reload = useCallback(() => {
    if (canPrice) {
      axios.get(`${API}/price-approvals`, { params: { status: "pending" } })
        .then((r) => { setPrices(asList(r.data).filter((p) => p.status === "pending")); setErrors((x) => ({ ...x, price: "" })); })
        .catch((e) => { setPrices([]); setErrors((x) => ({ ...x, price: loadErr(e, "harga khusus") })); });
    }
    if (canSpecial) {
      axios.get(`${API}/special-orders`)
        .then((r) => { setSpecials(asList(r.data).filter((s) => SPECIAL_WAITING.includes(s.status))); setErrors((x) => ({ ...x, special: "" })); })
        .catch((e) => { setSpecials([]); setErrors((x) => ({ ...x, special: loadErr(e, "pesanan khusus") })); });
    }
  }, [canPrice, canSpecial]);
  useEffect(reload, [reload]);
  return { prices, specials, errors, reload, loading: prices === null || specials === null };
}

/** Inbox persetujuan HP (manajer/finance): harga khusus & pesanan khusus — setujui/tolak langsung dari HP. */
export default function MobileApprovalInbox({ canPrice = true, canSpecial = true, focusId = "" }) {
  const { prices, specials, errors, reload, loading } = usePendingApprovals({ canPrice, canSpecial });
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState("");
  useEffect(() => {
    if (!focusId || loading) return;
    document.querySelector(`[data-focus-id="${focusId}"]`)?.scrollIntoView?.({ block: "center" });
  }, [focusId, loading]);
  // Dialog dibatalkan → kembalikan null tanpa pesan galat.
  const act = async (key, fn, okText) => {
    setBusy(key); setMsg(null);
    try { const done = await fn(); if (done === false) return; setMsg({ ok: true, text: okText }); reload(); }
    catch (e) { setMsg({ ok: false, text: apiErrorText(e, "Keputusan gagal disimpan.") }); }
    finally { setBusy(""); }
  };
  // G5-56 — dialog HP setara papan desktop: judul bernomor/berpelanggan, nilai Rp, catatan opsional, tombol berkata kerja.
  const approvePrice = (p) => act(p.id, async () => {
    const note = await askReason({
      title: `Setujui harga khusus · ${p.customer_name || ""}`,
      message: `${p.product_name || ""} · ${formatCurrency(p.requested_price)}/${p.unit || "satuan"} (pembanding ${formatCurrency(p.normal_price)}/${p.unit || "satuan"})`,
      confirmLabel: "Setujui", reasonLabel: "Catatan (opsional)", reasonRequired: false,
    });
    if (note === null) return false;
    await axios.post(`${API}/price-approvals/${p.id}/approve`, { decision_notes: note.trim() || "Disetujui dari HP" });
    return true;
  }, "Harga khusus disetujui.");
  const rejectPrice = (p) => act(p.id, async () => {
    const reason = await askReason({
      title: `Tolak harga khusus · ${p.customer_name || ""}`,
      message: `${p.product_name || ""} · ${formatCurrency(p.requested_price)}/${p.unit || "satuan"}`,
      confirmLabel: "Tolak", danger: true, reasonLabel: "Alasan penolakan",
    });
    if (reason === null) return false;
    await axios.post(`${API}/price-approvals/${p.id}/reject`, { decision_notes: reason });
    return true;
  }, "Harga khusus ditolak.");
  const approveSpecial = (s) => act(s.id, async () => {
    const note = await askReason({
      title: `Setujui ${s.number || "pesanan khusus"} · ${s.customer_name || ""}`,
      message: [s.custom_item?.description, Number(s.total_amount) > 0 ? formatCurrency(s.total_amount) : ""].filter(Boolean).join(" · "),
      confirmLabel: "Setujui", reasonLabel: "Catatan (opsional)", reasonRequired: false,
    });
    if (note === null) return false;
    await axios.post(`${API}/special-orders/${s.id}/approve`, { notes: note.trim() || "Disetujui dari HP" });
    return true;
  }, "Pesanan khusus disetujui.");
  const rejectSpecial = (s) => act(s.id, async () => {
    const reason = await askReason({
      title: `Tolak ${s.number || "pesanan khusus"} · ${s.customer_name || ""}`,
      message: [s.custom_item?.description, Number(s.total_amount) > 0 ? formatCurrency(s.total_amount) : ""].filter(Boolean).join(" · "),
      confirmLabel: "Tolak", danger: true, reasonLabel: "Alasan penolakan",
    });
    if (reason === null) return false;
    await axios.post(`${API}/special-orders/${s.id}/reject`, { reason });
    return true;
  }, "Pesanan khusus ditolak.");
  const errList = [errors.price, errors.special].filter(Boolean);
  const what = [canPrice && "harga khusus", canSpecial && "pesanan khusus"].filter(Boolean).join(" / ");
  return (
    <div className="space-y-2 p-3" data-testid="mo-inbox">
      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"} text-xs`} data-testid="mo-inbox-msg">{msg.text}</div>}
      {errList.map((t) => <div key={t} className="notice-bar warning text-xs" data-testid="mo-inbox-error">{t}</div>)}
      {loading && <p className="text-xs text-[#6E6E73]" data-testid="mo-inbox-loading">Memuat antrean…</p>}
      {!loading && !errList.length && !prices.length && !specials.length && <p className="p-6 text-center text-sm text-[#6E6E73]" data-testid="mo-inbox-empty">Tidak ada {what} yang menunggu.</p>}
      {(prices || []).map((p) => (
        <div key={p.id} data-focus-id={p.id} className={`m-card p-3 ${focusId === p.id ? "ring-2 ring-[#0058CC]" : ""}`} data-testid={`mo-price-${p.id}`}>
          <div className="flex items-center gap-2 text-[13px]"><Tag size={14} className="text-[#B25E00]" /><b className="flex-1 truncate">{p.customer_name}</b><span className="text-[10px] text-[#6E6E73]">{p.sales_name || p.requested_by_name || ""}</span></div>
          <p className="text-[12px] mt-1">{p.product_name} · min {formatQty(p.min_quantity)} {p.unit || ""}</p>
          <p className="text-[12px] tabular-nums"><s className="text-[#6E6E73]">{formatCurrency(p.normal_price)}</s> → <b>{formatCurrency(p.requested_price)}</b>{p.unit ? `/${p.unit}` : ""} {(() => { const d = discountInfo(p.discount_percent ?? (p.normal_price ? ((p.normal_price - p.requested_price) / p.normal_price) * 100 : 0)); return d ? <span className="text-[#B25E00]">({d.long})</span> : null; })()}{p.scope === "standing" ? " · berlaku terus" : " · pesanan ini"}</p>
          {p.reason && <p className="text-[11px] text-[#6E6E73] mt-0.5">{p.reason}</p>}
          <div className="mt-2 flex gap-2">
            <button className="primary-button flex-1 py-2 flex items-center justify-center gap-1" disabled={busy === p.id} onClick={() => approvePrice(p)} data-testid={`mo-price-approve-${p.id}`}><Check size={14} /> Setujui</button>
            <button className="secondary-button flex-1 py-2 flex items-center justify-center gap-1" disabled={busy === p.id} onClick={() => rejectPrice(p)} data-testid={`mo-price-reject-${p.id}`}><X size={14} /> Tolak</button>
          </div>
        </div>
      ))}
      {(specials || []).map((s) => (
        <div key={s.id} data-focus-id={s.id} className={`m-card p-3 ${focusId === s.id ? "ring-2 ring-[#0058CC]" : ""}`} data-testid={`mo-special-${s.id}`}>
          <div className="flex items-center gap-2 text-[13px]"><Package size={14} className="text-[#0058CC]" /><b className="flex-1 truncate">{s.number || "Pesanan khusus"} · {s.customer_name}</b></div>
          <p className="text-[12px] mt-1">{s.custom_item?.description || "-"} · {formatQty(s.custom_item?.quantity)} {s.custom_item?.unit}{s.custom_item?.target_price ? ` · target ${formatCurrency(s.custom_item.target_price)}/${s.custom_item?.unit || "satuan"}` : ""}</p>
          <div className="mt-2 flex gap-2">
            <button className="primary-button flex-1 py-2 flex items-center justify-center gap-1" disabled={busy === s.id} onClick={() => approveSpecial(s)} data-testid={`mo-special-approve-${s.id}`}><Check size={14} /> Setujui</button>
            <button className="secondary-button flex-1 py-2 flex items-center justify-center gap-1" disabled={busy === s.id} onClick={() => rejectSpecial(s)} data-testid={`mo-special-reject-${s.id}`}><X size={14} /> Tolak</button>
          </div>
        </div>
      ))}
    </div>
  );
}
