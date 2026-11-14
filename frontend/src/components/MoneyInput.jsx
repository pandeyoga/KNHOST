import DecimalInput from "./DecimalInput";
import { parseDecimal } from "../utils/decimalInput";
import { formatCurrency } from "../utils/formatters";

/**
 * MoneyInput — isian rupiah seragam: awalan "Rp", keypad desimal, dan pratinjau
 * terformat ("Rp 1.250.000") di bawah kotak supaya nol-nya tidak salah hitung.
 *
 * PK-42 — awalan & pratinjau mengikuti Standar UI (KN_37 §2: huruf ≥ 12 px, warna teks minimum `kn-text-2`); dulu
 * 10–11 px berwarna #8E8E93 (gagal kontras AA).
 */
export default function MoneyInput({ value, onChange, className = "field", testId, hint, ...rest }) {
  const n = parseDecimal(value === null || value === undefined ? "" : String(value));
  const preview = value !== "" && value !== null && value !== undefined && !Number.isNaN(n) ? formatCurrency(n) : "";
  return (
    <div className="grid gap-0.5">
      <div className="relative">
        <DecimalInput {...rest} data-testid={testId} className={className} value={value} min={0}
          onChange={onChange} style={{ paddingLeft: 34 }} />
        <span className="pointer-events-none absolute left-2.5 top-1/2 z-10 -translate-y-1/2 text-fs-12 font-semibold text-kn-text-2">Rp</span>
      </div>
      {(preview || hint) && (
        <p className="text-fs-12 tabular-nums text-kn-text-2" data-testid={testId ? `${testId}-preview` : undefined}>
          {preview}{preview && hint ? " · " : ""}{hint || ""}
        </p>
      )}
    </div>
  );
}
