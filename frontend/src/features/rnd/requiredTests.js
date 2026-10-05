/** W2-REQ-03 — uji wajib SKU hasil MD: PERINGATAN (bukan blokir); kurang ACC → minta alasan override. */
import { askReason } from "../../services/confirmService";
import { specRequiredTests } from "./rndApi";

// "" = lengkap · string = alasan override · null = pengguna membatalkan
export async function overrideReasonFor(gap, what) {
  if (!gap?.missing?.length) return "";
  return askReason({
    title: "Uji wajib belum ACC",
    message: `Belum ACC: ${gap.missing.join(", ")}. ${what} tetap bisa dilanjutkan — alasan Anda akan tercatat di riwayat.`,
    confirmLabel: "Lanjutkan dengan alasan",
  });
}

export async function specOverride(specId, what) {
  const gap = await specRequiredTests(specId).catch(() => null);
  return overrideReasonFor(gap, what);
}
