/**
 * MakloonLockBadge — FIX-9 (audit 9 Nov 2026 · B3a SSOT-4): panjang roll yang DIKUNCI cadangan bahan makloon.
 *
 * Sumber data: entri `length_reservations` bertipe "makloon" pada dokumen roll (`/inventory/rolls`) atau ringkasan
 * server `makloon_lock` ({qty, numbers}) di pemilih roll. Nomor MKO/PR hanya tampil bila server menyertakannya (roll
 * milik PT di luar izin penonton → tanpa nomor, keputusan B3a #7). Lencana = `StatusBadge` baku (kosakata
 * `utils/statusVocab.js`, ranah roll, kode `makloon_reserved`) — bukan chip buatan layar.
 *
 *   <MakloonLockBadge roll={r} />   → "Dicadangkan makloon · MKO-00005"            (roll terkunci penuh)
 *                                   → "Dicadangkan makloon · MKO-00005 · 20 yard"  (terkunci sebagian)
 */
import StatusBadge from "./StatusBadge";
import { formatQty } from "../utils/formatters";

export const makloonLockOf = (roll) => {
  if (!roll) return null;
  if (roll.makloon_lock) {
    const q = Number(roll.makloon_lock.qty) || 0;
    return q > 0 ? { qty: q, numbers: roll.makloon_lock.numbers || [] } : null;
  }
  const locks = (roll.length_reservations || []).filter((x) => x?.ref?.type === "makloon");
  const qty = locks.reduce((a, x) => a + (Number(x.qty) || 0), 0);
  if (qty <= 0) return null;
  const numbers = [...new Set(locks.map((x) => x.ref.number || x.ref.mko_number || x.ref.pr_number).filter(Boolean))];
  return { qty: Math.round(qty * 100) / 100, numbers };
};

export function MakloonLockBadge({ roll, unit, className = "" }) {
  const lk = makloonLockOf(roll);
  if (!lk) return null;
  const physical = Number(roll.physical_length ?? roll.length_remaining) || 0;
  const full = physical > 0 && lk.qty >= physical - 0.005;
  const docs = lk.numbers.join(", ");
  const u = unit || roll.unit || "";
  const part = full ? "" : ` · ${formatQty(lk.qty)}${u ? ` ${u}` : ""}`;
  return (
    <StatusBadge status="makloon_reserved" domain="roll" className={className}
      testId={`roll-makloon-lock-${roll.id}`}
      title={`${formatQty(lk.qty)} ${u} dikunci untuk makloon${docs ? ` (${docs})` : ""} — tidak bisa dijual, `
        + "dipindah, atau dipakai dokumen lain sampai dikirim ke mitra atau cadangannya dilepas."}
      label={`Dicadangkan makloon${docs ? ` · ${docs}` : ""}${part}`} />
  );
}

export default MakloonLockBadge;
