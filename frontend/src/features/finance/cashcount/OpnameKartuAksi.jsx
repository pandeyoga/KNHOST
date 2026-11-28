/**
 * OpnameKartuAksi — Kas & Bank bagian 3 (Tugas 4b): aksi **Opname** di kaki kartu rekening Rekening & Saldo (§5.4).
 *
 * Hanya untuk rekening TUNAI aktif (`account_type="cash"`; rekening bank dicocokkan lewat Rekonsiliasi Bank), pemegang
 * `cash.create` (penghitung), dan bila layar Opname Kas bisa dibuka. Klik → Kas & Bank › Opname Kas dengan pop-up Hitung
 * terisi rekening ini (preset `{hitung, account_id}`; daftar tersaring ke rekening yang sama). Dirender SEBAGAI SAUDARA
 * tombol kartu (bukan di dalamnya — tidak ada tombol di dalam tombol); tanpa aksi → tidak merender apa pun.
 */
import { Calculator } from "lucide-react";
import { can } from "../../../config/roles";
import { useAppNav } from "../../../context/AppNavContext";

export const bolehOpname = (a, perms) => a?.account_type === "cash" && a?.is_active !== false && can(perms, "cash", "create");

export default function OpnameKartuAksi({ a, currentUser }) {
  const { go, canOpen } = useAppNav();
  if (!bolehOpname(a, currentUser?.permissions) || !canOpen("cash-counts")) return null;
  return (
    <div className="flex justify-end border-t border-kn-divider px-3.5 py-1.5" data-testid={`bank-card-actions-${a.id}`}>
      <button type="button" className="secondary-button btn-sm" data-testid={`bank-opname-${a.id}`}
        title="Hitung uang fisik rekening ini dan cocokkan dengan saldo bukunya"
        onClick={() => go("cash-counts", { preset: { hitung: a.id, account_id: a.id } })}>
        <Calculator size={13} aria-hidden="true" /> Opname
      </button>
    </div>
  );
}
