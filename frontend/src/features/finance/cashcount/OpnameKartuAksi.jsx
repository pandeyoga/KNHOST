/**
 * OpnameKartuAksi — Kas & Bank bagian 3 (Tugas 4b): tombol **Opname** di kaki kartu rekening Rekening & Saldo (§5.4).
 *
 * Hanya untuk rekening TUNAI aktif (`account_type="cash"`; rekening bank dicocokkan lewat Rekonsiliasi Bank), pemegang
 * `cash.create` (penghitung), dan bila layar Opname Kas bisa dibuka. Klik → Kas & Bank › Opname Kas dengan pop-up Hitung
 * terisi rekening ini (preset `{hitung, account_id}`; daftar tersaring ke rekening yang sama). Komponen ini HANYA tombolnya:
 * kaki kartu satu untuk semua aksi kartu (`RekeningKasParts.RekeningKartuAksi`, bersama Isi ulang — tinjauan akhir Minor 1:
 * dulu dua kaki bertumpuk ber-testid kembar). Tanpa aksi → tidak merender apa pun.
 */
import { Calculator } from "lucide-react";
import { can } from "../../../config/roles";
import { useAppNav } from "../../../context/AppNavContext";

export const bolehOpname = (a, perms) => a?.account_type === "cash" && a?.is_active !== false && can(perms, "cash", "create");

/** Tombol Opname ditawarkan: aturan rekening & izin (`bolehOpname`) + layar Opname Kas bisa dibuka (`canOpen`). */
export const tampilOpname = (a, perms, canOpen) => bolehOpname(a, perms) && typeof canOpen === "function"
  && Boolean(canOpen("cash-counts"));

export default function OpnameKartuAksi({ a, perms, currentUser }) {
  const { go, canOpen } = useAppNav();
  if (!tampilOpname(a, perms ?? currentUser?.permissions, canOpen)) return null;
  return (
    <button type="button" className="secondary-button btn-sm" data-testid={`bank-opname-${a.id}`}
      title="Hitung uang fisik rekening ini dan cocokkan dengan saldo bukunya"
      onClick={() => go("cash-counts", { preset: { hitung: a.id, account_id: a.id } })}>
      <Calculator size={13} aria-hidden="true" /> Opname
    </button>
  );
}
