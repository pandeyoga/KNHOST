import { useState } from "react";
import AmendmentProposeModal from "../../finance/amendments/AmendmentProposeModal";

/** Koreksi pesanan dari HP.
 *  Fase 4 · R1 — lembar HP ringkas (qty/harga/diskon per baris, alasan, catatan) DIGANTI form desktop
 *  `finance/amendments/AmendmentProposeModal` (keputusan pemilik: form input HP tidak diringkas). HP kini juga punya
 *  diskon tingkat pesanan, tautan bukti (nama + URL), banner prinsip & "dokumen sudah terbit", dan kartu dampak yang
 *  sama dengan penyetuju. FormModal tampil layar penuh di HP; akar pop-up tetap `m-amd-sheet`.
 *  Alur khusus HP diteruskan lewat prop `autoReason` (alasan dipilih otomatis dari jenis perubahan, bisa diganti).
 *  `onClose(selesai)` — `true` bila usulan sudah terkirim (pemanggil memuat ulang daftar/riwayat). */
export default function MobileAmendSheet({ order, user, onClose }) {
  const [done, setDone] = useState(false);
  return (
    <AmendmentProposeModal order={order} currentUser={user} autoReason testId="m-amd-sheet"
      onDone={() => setDone(true)} onClose={() => onClose?.(done)} />
  );
}
