// PaymentBadge — SATU kamus status bayar untuk daftar, panel ringkas, dan detail SO.
// Tiga keadaan: Lunas · Bayar Sebagian (opsional dengan sisa) · Belum bayar.
// Dulu `partial` jatuh ke "Belum bayar" (bohong) atau tampil mentah "partial" (Inggris).
import { Check } from "lucide-react";
import { formatCurrency } from "../utils/formatters";
import { billingTotal } from "../utils/orderBilling";   // PK-32 — nilai tagihan (+ tagihan tambahan nota debit)

export default function PaymentBadge({ order, showRemaining = false, className = "", testId = "payment-badge" }) {
  const ps = String(order?.payment_status || "").toLowerCase();
  const paid = Number(order?.paid_total || 0);
  const grand = billingTotal(order);
  const partial = ps === "partial" || (ps !== "paid" && paid > 0);
  const remaining = Math.max(grand - paid, 0);

  if (ps === "paid") {
    return (
      <span data-testid={testId}
            className={`inline-flex items-center gap-0.5 rounded-full border border-[#BFE6CE] bg-[#E6F6EC] px-1.5 py-0.5 text-[9.5px] font-bold text-[#1B7F4B] ${className}`}>
        <Check size={10} /> Lunas
      </span>
    );
  }
  if (partial) {
    // Cek visual 14 Nov: "Bayar Sebagian · sisa Rp …" di dalam satu pil membulat dan di kolom sempit (daftar pesanan)
    // pecah menjadi gumpalan oval tiga baris. Kini pil hanya "Bayar Sebagian" (tidak pindah baris); sisanya teks biasa
    // di sampingnya, boleh turun baris.
    return (
      <span data-testid={testId} className={`inline-flex flex-wrap items-center gap-x-1 ${className}`}>
        <span className="inline-flex items-center whitespace-nowrap rounded-full border border-[#F5D9A8] bg-[#FFF4E5] px-1.5 py-0.5 text-[9.5px] font-bold text-[#8A5300]">
          Bayar Sebagian
        </span>
        {showRemaining && remaining > 0 && (
          <span className="whitespace-nowrap text-fs-12 font-semibold text-kn-warning-text">sisa {formatCurrency(remaining)}</span>
        )}
      </span>
    );
  }
  return (
    <span data-testid={testId}
          className={`inline-flex items-center rounded-full border border-[#E2E2E7] bg-[#F2F2F5] px-1.5 py-0.5 text-[9.5px] font-bold text-[#6E6E73] ${className}`}>
      Belum bayar
    </span>
  );
}
