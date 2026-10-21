/**
 * F-10 (keputusan owner Q-02, 2026-10-21) — termin bayar-sebelum-kirim (CBD / DP).
 * Menampilkan wajib-bayar sebelum kirim vs sudah dibayar, status Tertahan / Boleh kirim / Pengecualian, dan —
 * hanya untuk pemegang `order.release_unpaid` (bawaan Finance, Manager, Admin; diatur di Peran & Hak Akses) —
 * tombol beri / cabut pengecualian dengan alasan wajib. Server tetap penentu izin & aturannya.
 * Dipakai di detail SO dan di panel Ambil & Kirim (Barang Keluar).
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { can } from "../../config/roles";
import { formatCurrency } from "../../utils/formatters";
import ARReceiptModal from "../crm/ARReceiptModal";

export const fetchGate = (orderId) => axios.get(`${API}/sales-orders/${orderId}/dispatch-payment-gate`).then((r) => r.data);
export const releaseGate = (orderId, reason) =>
  axios.post(`${API}/sales-orders/${orderId}/dispatch-payment-release`, { reason }).then((r) => r.data);
export const revokeGate = (orderId, reason) =>
  axios.post(`${API}/sales-orders/${orderId}/dispatch-payment-release/revoke`, { reason }).then((r) => r.data);

const errText = (e, d) => e?.response?.data?.detail || d;

export function GateSummary({ gate, testPrefix = "gate" }) {
  if (!gate?.applies) return null;
  const rel = gate.released;
  const tone = gate.blocked ? "border-[#F5C2C0] bg-[#FFF4F3] text-[#8E1F17]"
    : rel ? "border-[#FFE2B8] bg-[#FFF7EC] text-[#8C4A00]" : "border-[#BFE6CC] bg-[#F1FBF4] text-[#126E2C]";
  return (
    <div className={`rounded-lg border p-2.5 text-[11px] ${tone}`} data-testid={`${testPrefix}-summary`}>
      <p className="flex items-center gap-1.5 font-semibold" data-testid={`${testPrefix}-state`}>
        {gate.blocked ? <ShieldAlert size={13} /> : <ShieldCheck size={13} />}
        {gate.blocked ? "Tertahan — belum dibayar sesuai termin" : rel ? "Boleh kirim — pengecualian berizin" : "Boleh kirim — termin terpenuhi"}
      </p>
      <p className="mt-0.5">
        Termin <b>{gate.term_name}</b>: wajib dibayar {formatCurrency(gate.required)} ({gate.dp_percent}%) sebelum kirim ·
        sudah dibayar <b data-testid={`${testPrefix}-paid`}>{formatCurrency(gate.paid)}</b>
        {gate.shortfall > 0 && <> · kurang <b data-testid={`${testPrefix}-shortfall`}>{formatCurrency(gate.shortfall)}</b></>}
      </p>
      {rel && (
        <p className="mt-0.5" data-testid={`${testPrefix}-release-info`}>
          Pengecualian oleh {rel.by} ({new Date(rel.at).toLocaleString("id-ID")}): “{rel.reason}”
        </p>
      )}
      {gate.blocked && (
        <p className="mt-0.5 text-[10.5px]">Catat pembayaran di Uang Masuk, atau pemegang izin “Kirim tanpa lunas” memberi pengecualian dengan alasan.</p>
      )}
    </div>
  );
}

export default function DispatchPaymentGatePanel({ orderId, currentUser, onChanged, testPrefix = "so-gate", initial,
                                                  customerId = "", customerName = "" }) {
  const [gate, setGate] = useState(initial || null);
  const [paying, setPaying] = useState(false);   // cek UI UAT v3 (S2) — catat pembayaran CBD/DP langsung dari sini
  const [mode, setMode] = useState("");          // "" | "release" | "revoke"
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    if (!orderId) return;
    fetchGate(orderId).then(setGate).catch(() => setGate(null));
  }, [orderId]);
  useEffect(() => { if (!initial) load(); }, [load, initial]);
  useEffect(() => { if (initial) setGate(initial); }, [initial]);

  if (!gate?.applies) return null;
  const allowed = can(currentUser?.permissions, "order", "release_unpaid");
  const canReceipt = gate.blocked && !!customerId && can(currentUser?.permissions, "ar_receipt", "create");
  const send = async () => {
    setBusy(true); setErr("");
    try {
      const next = mode === "release" ? await releaseGate(orderId, reason.trim()) : await revokeGate(orderId, reason.trim());
      setGate(next); setMode(""); setReason(""); onChanged?.(next);
    } catch (e) { setErr(errText(e, "Gagal menyimpan pengecualian.")); }
    finally { setBusy(false); }
  };
  return (
    <div className="space-y-1.5" data-testid={testPrefix}>
      <GateSummary gate={gate} testPrefix={testPrefix} />
      {canReceipt && (
        <button type="button" className="primary-button !py-1 !text-[11px]" data-testid={`${testPrefix}-receipt-open`}
                onClick={() => setPaying(true)}>Catat pembayaran ({formatCurrency(gate.shortfall)})</button>
      )}
      {paying && (
        <ARReceiptModal customerId={customerId} customerName={customerName} preselectOrderId={orderId}
                        onClose={() => setPaying(false)}
                        onDone={() => { setPaying(false); load(); onChanged?.(); }}
                        onError={(msg) => setErr(msg)} />
      )}
      {allowed && (gate.blocked || gate.released) && (
        <div className="space-y-1">
          {!mode && (
            gate.blocked
              ? <button type="button" className="secondary-button !py-1 !text-[11px]" data-testid={`${testPrefix}-release-open`}
                        onClick={() => setMode("release")}>Beri pengecualian kirim</button>
              : <button type="button" className="secondary-button !py-1 !text-[11px] !text-[#A8221A]" data-testid={`${testPrefix}-revoke-open`}
                        onClick={() => setMode("revoke")}>Cabut pengecualian</button>
          )}
          {mode && (
            <div className="space-y-1 rounded border border-[#E5EEFB] bg-white p-1.5">
              <input className="field w-full !py-1 text-[11px]" value={reason} data-testid={`${testPrefix}-reason`}
                     onChange={(e) => setReason(e.target.value)}
                     placeholder={mode === "release" ? "Alasan pengecualian (min. 5 huruf) — mis. pelanggan transfer, bukti menyusul" : "Alasan mencabut (min. 5 huruf)"} />
              <div className="flex gap-1">
                <button type="button" className="primary-button !py-1 !text-[11px]" disabled={busy || reason.trim().length < 5}
                        data-testid={`${testPrefix}-confirm`} onClick={send}>
                  {busy && <Loader2 size={12} className="animate-spin" />} {mode === "release" ? "Simpan pengecualian" : "Cabut"}
                </button>
                <button type="button" className="secondary-button !py-1 !text-[11px]" onClick={() => { setMode(""); setReason(""); setErr(""); }}>Batal</button>
              </div>
            </div>
          )}
        </div>
      )}
      {err && <p className="text-[10.5px] text-[#A8221A]" data-testid={`${testPrefix}-error`}>{err}</p>}
    </div>
  );
}
