import { useState } from "react";
import { Banknote } from "lucide-react";
import FormModal from "../../components/FormModal";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";
import { approveSamplePayment } from "./sampleApi";
import { cekUangMasukSample } from "./samplePayment";

/**
 * SamplePaymentApproveDialog — setujui pembayaran sample dengan pemeriksaan uang masuk (Meja gelombang 1, Task 11).
 * Satu pop-up untuk daftar Pesanan Sample dan Meja Sample. Uang kurang → peringatan + tombol "Tetap setujui";
 * galat tampil di dalam pop-up dan pop-up tetap terbuka.
 *
 * order: { id, number, title | customer_name, sample_billing, grand_total, paid_total, sample_payment_status }
 */
export default function SamplePaymentApproveDialog({ order, onClose, onDone, testId = "sample-approve" }) {
  const o = order || {};
  const ulang = o.sample_payment_status === "reapproval_required";
  const { total, masuk, kurang } = cekUangMasukSample(o);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const kirim = async () => {
    if (busy) return;
    setBusy(true); setErr("");
    try {
      const hasil = await approveSamplePayment(o.id);
      onDone?.(hasil);
    } catch (e) {
      setErr(apiErrorText(e, "Aksi gagal."));
    } finally {
      setBusy(false);
    }
  };

  const pihak = o.title || o.customer_name || "";
  return (
    <FormModal open onClose={onClose} size="sm" icon={Banknote}
      title={ulang ? "Setujui ulang tagihan sample?" : "Setujui pembayaran sample?"}
      subtitle={[o.number, pihak].filter(Boolean).join(" · ")} testId={testId} busy={busy} error={err}
      footer={(
        <div className="flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>Batal</button>
          <button type="button" data-testid={`${testId}-submit`}
            className={kurang > 0 ? "danger-button whitespace-nowrap" : "primary-button whitespace-nowrap"}
            disabled={busy} onClick={kirim}>
            {busy ? "Memproses…" : kurang > 0 ? "Tetap setujui" : "Setujui pembayaran"}
          </button>
        </div>
      )}>
      <div className="space-y-2">
        <dl className="rounded-md border border-kn-border px-3 py-2 text-fs-13 space-y-1">
          <div className="flex justify-between gap-3">
            <dt className="text-kn-text-2">Total tagihan</dt>
            <dd className="text-right tabular-nums" data-testid={`${testId}-total`}>{formatCurrency(total)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-kn-text-2">Uang tercatat masuk</dt>
            <dd className="text-right tabular-nums" data-testid={`${testId}-paid`}>{formatCurrency(masuk)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-kn-text-2">Kekurangan</dt>
            <dd className="text-right tabular-nums" data-testid={`${testId}-short-amount`}>{kurang > 0 ? formatCurrency(kurang) : "lunas"}</dd>
          </div>
        </dl>
        {kurang > 0 && (
          <p className="rounded-md bg-kn-neutral-soft px-3 py-2 text-fs-13" data-testid={`${testId}-short`}>
            {`Uang yang tercatat masuk untuk ${o.number} baru ${formatCurrency(masuk)} dari ${formatCurrency(total)} (kurang ${formatCurrency(kurang)}). Tetap setujui pembayaran dan lepas ke gudang?`}
          </p>
        )}
      </div>
    </FormModal>
  );
}
