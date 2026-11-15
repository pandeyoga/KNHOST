/**
 * PM-T4 — titipan tunai sales: label status (ikon + teks + warna), umur, dan teks bersama layar Kas & Bank › Titipan
 * Sales, kartu HP "Titipan Saya", dan form kwitansi. Server: `backend/services/cash_holding_service.py`.
 */
import { AlertTriangle, Ban, CheckCircle2, Clock, Wallet, XCircle } from "lucide-react";
import { docStatusLabel } from "../../../utils/docStatus";

/** Label Indonesia status titipan & setoran (kode mentah tidak pernah tampil). */
export const CASH_HOLDING_LABELS = {
  dipegang: "Dipegang", sebagian_disetor: "Sebagian disetor", disetor: "Disetor", batal: "Batal",
  diajukan: "Diajukan", diterima: "Diterima", ditolak: "Ditolak", dibatalkan: "Dibatalkan",
};

const STATUS_LOOK = {
  dipegang: { icon: Wallet, cls: "bg-kn-warning-soft text-kn-warning-text" },
  sebagian_disetor: { icon: Clock, cls: "bg-kn-action-soft text-kn-action" },
  disetor: { icon: CheckCircle2, cls: "bg-kn-success-soft text-kn-success-text" },
  batal: { icon: Ban, cls: "bg-kn-neutral-soft text-kn-text-2" },
  diajukan: { icon: Clock, cls: "bg-kn-action-soft text-kn-action" },
  diterima: { icon: CheckCircle2, cls: "bg-kn-success-soft text-kn-success-text" },
  ditolak: { icon: XCircle, cls: "bg-kn-danger-soft text-kn-danger-text" },
  dibatalkan: { icon: Ban, cls: "bg-kn-neutral-soft text-kn-text-2" },
};

/** → { label, icon, cls } untuk `status-pill`. */
export function cashHoldingStatus(status) {
  const look = STATUS_LOOK[status] || { icon: Clock, cls: "bg-kn-neutral-soft text-kn-text" };
  return { label: docStatusLabel(status, CASH_HOLDING_LABELS), ...look };
}

export const OVERDUE_LOOK = { label: "Lewat tenggat", icon: AlertTriangle, cls: "bg-kn-danger-soft text-kn-danger-text" };

/** Umur sejak `iso` dalam bahasa sehari-hari: "hari ini" / "1 hari" / "3 hari". */
export function ageText(iso, now = Date.now()) {
  const t = Date.parse(iso || "");
  if (Number.isNaN(t)) return "—";
  const days = Math.floor((now - t) / 86400000);
  return days <= 0 ? "hari ini" : `${days} hari`;
}

/** Teks bantu tunai di form kwitansi menurut mode yang berlaku untuk akun ini (server: `/cash-holdings/me/summary`). */
export const TEKS_TITIPAN = "Uang tunai ini dicatat sebagai titipan di tangan Anda sampai disetor ke kasir atau bank.";
export const TEKS_SEMUA_PT = "Pilih satu PT dulu";
export const TEKS_TANPA_IZIN_TERIMA = "Menerima setoran butuh akses menerima setoran titipan.";
export const TEKS_SETORAN_SENDIRI = "Setoran Anda sendiri — diterima orang lain.";
export const TEKS_SETORAN_DIAJUKAN = "Setoran diajukan. Serahkan uangnya ke kasir.";
