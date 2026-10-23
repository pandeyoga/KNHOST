import { createContext, useContext, useEffect, useRef } from "react";

/**
 * Tombol "Kembali" tunggal untuk subhalaman HP (menu Lainnya).
 *
 * 23 Okt — rincian di dalam subhalaman (OD, retur, pelanggan, prospek) dulu menampilkan DUA tombol kembali
 * bertumpuk: "← Kembali" milik kepala halaman (ke menu Lainnya) dan "← Pesanan khusus" milik rincian (ke daftar).
 * Kini rincian mendaftarkan aksi kembalinya ke kepala halaman; selama rincian terbuka, "Kembali" di kepala
 * halaman kembali ke daftar, dan rincian tidak menggambar tombol keduanya.
 */
export const SubpageBackContext = createContext(null);

/** Daftarkan `onBack` ke kepala subhalaman. Mengembalikan `true` bila kepala halaman mengambil alih
 *  (tombol kembali milik rincian tidak perlu digambar). Di luar subhalaman → `false`.
 *  `active=false` → tidak mendaftar (mis. daftar yang rinciannya belum dibuka). */
export function useSubpageBack(onBack, active = true) {
  const ctx = useContext(SubpageBackContext);
  const ref = useRef(onBack);
  ref.current = onBack;
  useEffect(() => {
    if (!ctx || !active) return undefined;
    const fn = () => ref.current?.();
    ctx.push(fn);
    return () => ctx.pop(fn);
  }, [ctx, active]);
  return !!ctx;
}
