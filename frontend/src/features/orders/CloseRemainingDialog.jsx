import { useEffect, useState } from "react";
import { PackageX } from "lucide-react";
import FormModal from "../../components/FormModal";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { alasanPersetujuan, diajukan, pesanDiajukan, pesanHasil } from "./cancelRequestUtil";

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
      onDone?.(pesanHasil(order, "close_remaining", res.data));
    } catch (e) { setError(apiErrorText(e, "Gagal menutup sisa pesanan.")); }
    finally { setBusy(false); }
  }

  return (
    <FormModal open onClose={onClose} title={`Tutup sisa ${order.number}?`} icon={PackageX} size="md"
      subtitle="Jumlah yang belum terkirim dihapus dari pesanan, reservasi dan tugas gudang sisanya dilepas, dan nilai pesanan turun ke nilai barang yang sudah terkirim."
      testId="close-remaining-dialog" onSubmit={submit} busy={busy}
      submitLabel={perluSetuju ? "Ajukan tutup sisa" : "Ya, Tutup Sisa"} cancelLabel="Kembali"
      submitTestId="close-remaining-confirm" cancelTestId="close-remaining-back"
      submitDisabled={memuat || terhalang || !p || reason.trim().length < 5}>
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
    </FormModal>
  );
}
