/**
 * ReturnBookValue (PK-27 · IV-06) — rincian retur beli yang sudah disetujui: nilai buku roll yang keluar dari
 * persediaan dan selisihnya terhadap nilai nota debit (tanpa PPN). Retur lama tanpa `book_value` tidak menampilkan apa pun.
 * Bila selisih belum masuk jurnal (akun "Selisih nilai retur beli" belum dipetakan), alasannya ditulis di sampingnya.
 */
import { AlertTriangle } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";

export const TEKS_BELUM_JURNAL = "Selisih ini belum masuk jurnal karena akun \"Selisih nilai retur beli\" belum diatur di "
  + "Pemetaan Akun.";

export default function ReturnBookValue({ ret }) {
  if (!ret || typeof ret.book_value !== "number") return null;
  const diff = Number(ret.book_value_diff) || 0;
  const adaSelisih = Math.abs(diff) > 0.005;
  return (
    <div className="mb-2 rounded-md border border-kn-divider px-3 py-2 text-fs-12" data-testid="pr-book-value">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-kn-text-2">Nilai buku roll</span>
        <span className="tabular-nums font-semibold text-kn-text" data-testid="pr-book-value-amount">
          {formatCurrency(ret.book_value)}</span>
      </div>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-kn-text-2">Selisih terhadap nota</span>
        <span className="tabular-nums font-semibold text-kn-text" data-testid="pr-book-value-diff">
          {adaSelisih ? formatCurrency(diff) : "Tidak ada"}</span>
      </div>
      {adaSelisih && ret.book_value_posted === false && (
        <p className="mt-1 flex items-start gap-1 text-kn-warning-text" data-testid="pr-book-value-unposted">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />{TEKS_BELUM_JURNAL}</p>
      )}
    </div>
  );
}
