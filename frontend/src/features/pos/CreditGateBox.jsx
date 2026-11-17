/**
 * CR-T3 — kotak kredit checkout (desktop & HP): hasil SATU mesin gerbang kredit (`GET /customers/{id}/credit-status` →
 * `gate`). Empat baris eksposur (piutang terkirim, pesanan belum dikirim, giro belum cair, titipan), pesanan ini, Plafon,
 * Sisa plafon, dan pesan alasan — angka yang DIPAKAI mesin (L6), termasuk komponen yang tidak dihitung pengaturan PT.
 * Tertahan → tombol "Ajukan izin kredit" (`CreditOverrideRequest`); ditolak termin → petunjuk pilih termin lain.
 */
import { AlertTriangle, CheckCircle2, Info, RefreshCw, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import CreditOverrideRequest from "./CreditOverrideRequest";

const HASIL = {
  lolos: { label: "Kredit aman", cls: "status-done", Icon: CheckCircle2 },
  peringatan: { label: "Peringatan kredit", cls: "status-pending", Icon: AlertTriangle },
  tahan: { label: "Kredit tertahan", cls: "status-rejected", Icon: ShieldAlert },
  tolak: { label: "Termin ditolak", cls: "status-rejected", Icon: XCircle },
};
const IKON_ALASAN = { tahan: ShieldAlert, tolak: XCircle, peringatan: AlertTriangle, keterangan: Info };

export function gateBlocked(credit) {
  if (!credit) return false;
  if (credit.gate) return ["tahan", "tolak"].includes(credit.gate.result);
  return !!credit.blocked && !credit.has_approved_override;
}

function Baris({ label, value, note = "", strong = false, testId }) {
  return (
    <div className="flex items-baseline justify-between gap-2" data-testid={testId}>
      <span className="text-kn-text-2">{label}{note && <span className="ml-1 text-fs-12">({note})</span>}</span>
      <span className={`tabular-nums ${strong ? "font-bold text-kn-text" : "text-kn-text"}`}>{value}</span>
    </div>
  );
}

export default function CreditGateBox({ credit, customer, amount = 0, entityId = "", testId = "credit-gate-box", onRecheck = null }) {
  const g = credit?.gate;
  if (!g) return null;
  if (!g.checked) {
    return (
      <div className="rounded-md border border-kn-divider bg-white p-2.5 text-fs-12 text-kn-text-2" data-testid={testId}>
        <ShieldCheck size={13} className="mr-1 inline" aria-hidden="true" /> Kredit tidak diperiksa saat pesanan dibuat (pengaturan PT ini).
      </div>
    );
  }
  const meta = HASIL[g.result] || HASIL.lolos;
  const e = g.exposure || {};
  const c = g.counted || {};
  const lim = g.limit || {};
  const limit = Number(lim.credit_limit || 0);
  const lifted = g.result === "lolos" && g.override;
  return (
    <div className="rounded-md border border-kn-divider bg-white p-2.5 text-fs-12" data-testid={testId}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`status-pill ${meta.cls} whitespace-nowrap`} data-testid={`${testId}-result`}>
          <meta.Icon size={12} aria-hidden="true" /> {meta.label}
        </span>
        {lifted && <span className="text-kn-success-text" data-testid={`${testId}-override`}>Izin kredit disetujui dipakai pesanan ini (sisa {formatCurrency(g.override.remaining_amount ?? g.override.amount)}).</span>}
      </div>
      <div className="mt-2 grid gap-0.5" data-testid={`${testId}-rows`}>
        <Baris label="Piutang barang terkirim" value={formatCurrency(e.ar_delivered)} testId={`${testId}-ar`} />
        <Baris label="Pesanan belum dikirim" value={c.open_orders === false ? "tidak dihitung" : formatCurrency(e.open_orders)} testId={`${testId}-open`} />
        <Baris label="Giro belum cair" value={c.giro === false ? "tidak dihitung" : formatCurrency(e.giro_outstanding)} testId={`${testId}-giro`} />
        <Baris label="Titipan pelanggan" note="mengurangi" value={c.deposit === false ? "tidak dihitung" : `− ${formatCurrency(e.deposit)}`} testId={`${testId}-deposit`} />
        <Baris label="Pesanan ini" value={formatCurrency(e.this_order)} testId={`${testId}-this`} />
        <div className="my-1 border-t border-kn-divider" />
        <Baris label="Eksposur" value={formatCurrency(e.total)} strong testId={`${testId}-total`} />
        <Baris label="Plafon" value={limit > 0 ? formatCurrency(limit) : "Tanpa batas"} testId={`${testId}-limit`} />
        <Baris label="Sisa plafon" value={limit > 0 ? formatCurrency(lim.available) : "—"} testId={`${testId}-available`} />
      </div>
      {(g.reasons || []).length > 0 && (
        <ul className="mt-2 space-y-0.5" data-testid={`${testId}-reasons`}>
          {g.reasons.map((r) => {
            const Ic = IKON_ALASAN[r.result] || Info;
            return (
              <li key={r.code} className={`flex items-start gap-1.5 ${r.result === "tahan" || r.result === "tolak" ? "text-kn-danger-text" : r.result === "peringatan" ? "text-kn-warning-text" : "text-kn-text-2"}`}>
                <Ic size={12} className="mt-0.5 shrink-0" aria-hidden="true" /> <span>{r.message}</span>
              </li>
            );
          })}
        </ul>
      )}
      {g.pay_before_ship && (
        <p className="mt-2 text-kn-warning-text" data-testid={`${testId}-pay-first`}>
          Pelanggan sedang ditahan kredit — pesanan bayar-dulu ini boleh dibuat, barang dikirim sesudah dibayar penuh.
        </p>
      )}
      {g.result === "tahan" && (
        <>
          <p className="mt-2 text-kn-danger-text" data-testid={`${testId}-blocked-note`}>Pesanan belum bisa dibuat: kredit tertahan.</p>
          {!(g.reasons || []).some((r) => r.code === "BLOKIR_MANUAL")
            ? <CreditOverrideRequest customer={customer} amount={amount} entityId={entityId}
                afterHint={onRecheck ? "setelah izin disetujui, tekan Periksa ulang kredit lalu Buat Sales Order." : undefined} />
            : <p className="mt-1 text-kn-text-2">Blokir manual tidak dilepas izin kredit — buka blokir lewat pengajuan perubahan kredit di kartu pelanggan.</p>}
          {onRecheck && (
            <button type="button" className="ghost-button btn-sm mt-1.5 whitespace-nowrap" data-testid={`${testId}-recheck`}
              onClick={onRecheck}>
              <RefreshCw size={12} aria-hidden="true" /> Periksa ulang kredit
            </button>
          )}
        </>
      )}
      {g.result === "tolak" && (
        <p className="mt-2 text-kn-danger-text" data-testid={`${testId}-term-note`}>Pilih termin yang diizinkan untuk pelanggan ini.</p>
      )}
    </div>
  );
}
