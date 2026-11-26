/**
 * F-10 (keputusan owner Q-02, 2026-10-21) — termin bayar-sebelum-kirim (CBD / DP).
 * Menampilkan wajib-bayar sebelum kirim vs sudah dibayar, status Tertahan / Boleh kirim / Pengecualian, dan —
 * hanya untuk pemegang `order.release_unpaid` (bawaan Finance, Manager, Admin; diatur di Peran & Hak Akses) —
 * tombol beri / cabut pengecualian dengan alasan wajib. Server tetap penentu izin & aturannya.
 * Dipakai di detail SO dan di panel Ambil & Kirim (Barang Keluar).
 *
 * Lapor Bayar CBD & DP (LB-T7) — bila detail SO mengirim `order`: judul "Bayar sebelum gudang" untuk pesanan yang ditahan
 * bayar sebelum gudang (`pay_hold` atau wajib bayar dulu & belum dilepas), batas bayar + sisa hari, tombol "Lapor bayar"
 * (`payment_report.create`), daftar laporan (bukti, Terima/Tolak bagi `payment_report.decide`). Pencatat tanpa
 * `payment_report.decide` pada pesanan tertahan: server menolak kwitansi non-tunai 409 ("pakai Lapor bayar") tetapi
 * mengecualikan uang TUNAI baru — maka tombolnya jadi "Terima tunai" (formulir khusus tunai) bila
 * `pembayaran.sales_terima_tunai` mengizinkan, selain itu disembunyikan (LB-T8, R15 M3). `camera` = mode HP.
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { can } from "../../config/roles";
import { formatCurrency, formatDate } from "../../utils/formatters";
import ReceivePaymentModal from "../finance/payments/ReceivePaymentModal";   // MN-T3 — satu form terima pembayaran
import LaporBayarDialog from "./payReport/LaporBayarDialog";
import PayReportList from "./payReport/PayReportList";
import useSalesCashMode from "./payReport/useSalesCashMode";
import { listReports } from "./payReport/payReportApi";

export const fetchGate = (orderId) => axios.get(`${API}/sales-orders/${orderId}/dispatch-payment-gate`).then((r) => r.data);
export const releaseGate = (orderId, reason) =>
  axios.post(`${API}/sales-orders/${orderId}/dispatch-payment-release`, { reason }).then((r) => r.data);
export const revokeGate = (orderId, reason) =>
  axios.post(`${API}/sales-orders/${orderId}/dispatch-payment-release/revoke`, { reason }).then((r) => r.data);

const errText = (e, d) => e?.response?.data?.detail || d;

// Sama dengan `pay_hold_service.STATUS_SEBELUM_GUDANG` / `customer_service.DEAD_STATUSES` (server tetap penentu).
const STATUS_SEBELUM_GUDANG = ["reserved", "waiting_approval", "waiting_stock", "approved"];
const STATUS_MATI = ["cancelled", "draft", "expired", "rejected"];

/** Sisa hari sampai batas bayar (pembulatan ke atas; ≤ 0 = hari ini/lewat). */
export const sisaHari = (dueAt, now = Date.now()) => Math.ceil((Date.parse(dueAt) - now) / 86400000);
const teksBatas = (dueAt) => {
  const n = sisaHari(dueAt);
  const sisa = n > 0 ? `sisa ${n} hari` : n === 0 ? "berakhir hari ini" : `lewat ${-n} hari`;
  return `Batas bayar ${formatDate(dueAt)} · ${sisa}`;
};

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
                                                  customerId = "", customerName = "", order = null, camera = false }) {
  const [gate, setGate] = useState(initial || null);
  const [lapor, setLapor] = useState(false);       // LB-T7 — pop-up Lapor bayar
  const [reports, setReports] = useState(null);    // LB-T7 — `{items, bisa_lapor, bisa_putuskan}` | null
  const [paying, setPaying] = useState(false);   // cek UI UAT v3 (S2) — catat pembayaran CBD/DP langsung dari sini
  const [mode, setMode] = useState("");          // "" | "release" | "revoke"
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // R15 M3 — non-pemutus pada pesanan tertahan: kwitansi hanya untuk uang TUNAI baru, dan hanya bila PT mengizinkan sales
  // menerima tunai (`pembayaran.sales_terima_tunai` ≠ dilarang). Dibaca sekali per panel; hanya dipakai pesanan ber-`order`.
  const cash = useSalesCashMode(Boolean(order) && Boolean(gate?.applies) && !can(currentUser?.permissions, "payment_report", "decide"));
  const load = useCallback(() => {
    if (!orderId) return;
    fetchGate(orderId).then(setGate).catch(() => setGate(null));
  }, [orderId]);
  useEffect(() => { if (!initial) load(); }, [load, initial]);
  useEffect(() => { if (initial) setGate(initial); }, [initial]);
  const loadReports = useCallback(() => {
    if (!orderId || !order) return;
    listReports(orderId).then(setReports).catch(() => setReports(null));
  }, [orderId, order]);
  const gateApplies = Boolean(gate?.applies);
  useEffect(() => { if (gateApplies) loadReports(); }, [gateApplies, loadReports]);

  if (!gate?.applies) return null;
  const perms = currentUser?.permissions;
  const allowed = can(perms, "order", "release_unpaid");
  const canDecide = can(perms, "payment_report", "decide");
  const alive = !!order && !STATUS_MATI.includes(order.status);
  // Tertahan bayar sebelum gudang: penanda `pay_hold`, atau wajib bayar dulu dan belum dilepas ke gudang (R12).
  const held = !!order && (!!order.pay_hold || (STATUS_SEBELUM_GUDANG.includes(order.status) && !gate.released));
  const canReport = alive && gate.shortfall > 0 && can(perms, "payment_report", "create") && reports?.bisa_lapor !== false;
  // Pencatat tanpa `payment_report.decide` ditolak server (409) pada pesanan tertahan, KECUALI uang tunai baru (server
  // mengecualikannya) — maka tombolnya hanya muncul bila tunai diizinkan, dan formulirnya dibatasi cara bayar tunai.
  const cashOnly = held && !canDecide;
  const canReceipt = gate.blocked && !!customerId && can(perms, "ar_receipt", "create")
    && (!cashOnly || (cash.ready && cash.cashAllowed));
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
      {order && (
        <p className="text-fs-13 font-bold text-kn-text" data-testid={`${testPrefix}-title`}>
          {held ? "Bayar sebelum gudang" : "Bayar sebelum kirim"}
        </p>
      )}
      <GateSummary gate={gate} testPrefix={testPrefix} />
      {order?.pay_hold?.due_at && (
        <p className="text-fs-12 font-semibold text-kn-warning-text" data-testid={`${testPrefix}-batas`}>{teksBatas(order.pay_hold.due_at)}</p>
      )}
      {canReport && (
        <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid={`${testPrefix}-lapor-open`}
                onClick={() => setLapor(true)}>Lapor bayar</button>
      )}
      {lapor && (
        <LaporBayarDialog order={order} shortfall={gate.shortfall} camera={camera} onClose={() => setLapor(false)}
                          onDone={() => { setLapor(false); loadReports(); load(); onChanged?.(); }} />
      )}
      {order && reports && (
        <PayReportList reports={reports.items} canDecide={canDecide && reports.bisa_putuskan !== false}
                       canCreate={can(perms, "payment_report", "create") && reports.bisa_lapor !== false}
                       onChanged={() => { loadReports(); load(); onChanged?.(); }} />
      )}
      {canReceipt && (
        <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid={`${testPrefix}-receipt-open`}
                onClick={() => setPaying(true)}>{cashOnly ? "Terima tunai" : "Terima pembayaran"} ({formatCurrency(gate.shortfall)})</button>
      )}
      {paying && (
        <ReceivePaymentModal customerId={customerId} customerName={customerName} preselectOrderId={orderId} cashOnly={cashOnly}
                        onClose={() => setPaying(false)}
                        onDone={() => { setPaying(false); load(); onChanged?.(); }} />
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
