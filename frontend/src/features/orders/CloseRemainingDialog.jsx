import { useEffect, useState } from "react";
import { PackageX, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { overlayDismiss } from "../../utils/overlayDismiss";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { alasanPersetujuan, diajukan, pesanDiajukan } from "./cancelRequestUtil";

/** BTP-4/6 — Tutup sisa pesanan `partially_shipped`: yang belum terkirim dilepas, nilai pesanan turun ke yang sudah
 *  terkirim, uang berlebih jadi titipan. Dialog menampilkan ringkasan sebelum → sesudah dari `cancel-check` (tanpa
 *  tulisan) + daftar penghalang bila tidak boleh; wajib setuju → "Ajukan tutup sisa" (server 202). */
export default function CloseRemainingDialog({ order, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [check, setCheck] = useState(null);
  const [memuat, setMemuat] = useState(true);

  useEffect(() => {
    let hidup = true;
    (async () => {
      try {
        const res = await axios.get(`${API}/sales-orders/${order.id}/cancel-check`, { params: { action: "close_remaining" } });
        if (hidup) setCheck(res?.data || null);
      } catch (e) { if (hidup) setError(apiErrorText(e, "Gagal memeriksa pesanan.")); }
      finally { if (hidup) setMemuat(false); }
    })();
    return () => { hidup = false; };
  }, [order.id]);

  const p = check?.preview || null;
  const terhalang = p ? p.allowed === false : false;
  const perluSetuju = Boolean(check?.needs_approval) && !check?.can_self_approve;
  const titip = Number(p?.excess_to_deposit || 0);

  async function submit() {
    setBusy(true); setError("");
    try {
      const res = await axios.post(`${API}/sales-orders/${order.id}/close-remaining`, { reason: reason.trim() });
      if (diajukan(res)) { onDone?.(pesanDiajukan(order, res.data)); return; }
      const t = Number(res.data?.advance_to_deposit || 0);
      onDone?.(`${order.number}: sisa pesanan ditutup, stok dilepas.`
        + (t > 0 ? ` ${formatCurrency(t)} menjadi titipan pelanggan.` : ""));
    } catch (e) { setError(apiErrorText(e, "Gagal menutup sisa pesanan.")); }
    finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 180 }} data-testid="close-remaining-dialog" {...overlayDismiss(onClose)}>
      <div className="modal-card" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <p className="modal-title flex items-center gap-2"><PackageX size={15} className="text-[#C0392B]" /> Tutup sisa {order.number}?</p>
          <button className="icon-button" onClick={onClose} data-testid="close-remaining-close"><X size={16} /></button>
        </div>
        <p className="modal-subtitle mt-1">Jumlah yang belum terkirim dihapus dari pesanan, reservasi dan tugas gudang sisanya
          dilepas, dan nilai pesanan turun ke nilai barang yang sudah terkirim.</p>
        {memuat && <p className="mt-2 text-[11px] text-[#8E8E93]" data-testid="close-remaining-loading">Memeriksa pesanan…</p>}
        {terhalang && (
          <div className="notice-bar danger mt-2" data-testid="close-remaining-blockers">
            <span>Sisa belum bisa ditutup:</span>
            <ul className="mt-1 list-disc pl-4">{(p.blockers || []).map((b, i) => <li key={i}>{b}</li>)}</ul>
          </div>
        )}
        {p && !terhalang && (
          <div className="mt-2 space-y-2">
            <table className="w-full text-[11px]" data-testid="close-remaining-lines">
              <thead><tr className="text-left text-[#8E8E93]"><th>Barang</th><th className="text-right">Dipesan → terkirim</th></tr></thead>
              <tbody>
                {(p.lines || []).map((l, i) => (
                  <tr key={l.product_id || i} className="border-t border-[#EFF0F2]">
                    <td className="py-1">{l.product_name}</td>
                    <td className="py-1 text-right">{formatQty(l.qty_ordered)} → {formatQty(l.qty_shipped)} {l.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[12px]" data-testid="close-remaining-total">
              Nilai pesanan: <b>{formatCurrency(p.grand_total_before)}</b> → <b>{formatCurrency(p.grand_total_after)}</b>
              {" "}(sisa dibatalkan {formatCurrency(p.remaining_value)})
            </p>
            {titip > 0 && (
              <p className="text-[12px] text-[#9A5B00]" data-testid="close-remaining-deposit">
                {formatCurrency(titip)} dari pembayaran jadi titipan pelanggan.
              </p>
            )}
            {perluSetuju && (
              <div className="notice-bar warning" data-testid="close-remaining-approval-note">
                <span>Perlu persetujuan karena {alasanPersetujuan(check.basis, order).join(" dan ")}. Stok sisa tetap dipesan sampai diputus.</span>
              </div>
            )}
          </div>
        )}
        {error && <div className="notice-bar danger mt-2" data-testid="close-remaining-error"><span>{error}</span></div>}
        <textarea data-testid="close-remaining-reason" className="field mt-3 w-full" rows={3} placeholder="Alasan tutup sisa (wajib, min. 5 karakter)"
          value={reason} onChange={(e) => setReason(e.target.value)} />
        <div className="mt-3 flex justify-end gap-2">
          <button className="secondary-button" onClick={onClose} data-testid="close-remaining-back">Kembali</button>
          <button className="primary-button !bg-[#C0392B]" data-testid="close-remaining-confirm"
            disabled={busy || memuat || terhalang || !p || reason.trim().length < 5} onClick={submit}>
            {busy ? "Memproses…" : (perluSetuju ? "Ajukan tutup sisa" : "Ya, Tutup Sisa")}
          </button>
        </div>
      </div>
    </div>
  );
}
