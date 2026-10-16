import { Wallet } from "lucide-react";
import { fmtUsd } from "./tanyaFormat";

/** Kartu sisi: pemakaian anggaran AI Tanya KN bulan berjalan. */
export function TanyaBudgetCard({ budget }) {
  if (!budget) return null;
  const pct = budget.limit_usd ? Math.min(100, (budget.spent_usd / budget.limit_usd) * 100) : 0;
  const tone = budget.exceeded ? "bad" : pct >= 80 ? "warn" : "ok";
  return (
    <div className="tanya-budget" data-testid="tanya-budget-card">
      <div className="tanya-kicker"><Wallet className="h-4 w-4" /> Anggaran bulan ini</div>
      <div className="tanya-budget-value" data-testid="tanya-budget-spent">{fmtUsd(budget.spent_usd)}</div>
      <div className="tanya-note">dari {fmtUsd(budget.limit_usd)} · {pct.toLocaleString("id-ID", { maximumFractionDigits: 1 })}% terpakai</div>
      <div className="tanya-meter"><span className={`tanya-meter-fill ${tone}`} style={{ width: `${pct}%` }} /></div>
      {budget.exceeded && <div className="tanya-sched-err" data-testid="tanya-budget-exceeded">Anggaran habis — chat AI dimatikan sampai bulan depan.</div>}
      <p className="tanya-note">Anggaran dihitung dari chat, ringkasan AI, dan pemanasan cache Tanya KN. Harga model: {budget.price_version}.</p>
    </div>
  );
}
