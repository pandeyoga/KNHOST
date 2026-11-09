import { useEffect, useRef, useState } from "react";

/**
 * FIX-5 (B1b UI-46, B4 §3.8 "render hanya baris terlihat + buffer") — baris berat (pemilih bin, saran, tombol)
 * baru DIRENDER saat mendekati layar, lalu menetap. Dulu antrean Lokasi Rak merender semua baris sekaligus
 * (500 baris = 1.509 tombol, 12–21 dtk). Tanpa `IntersectionObserver` (peramban lama/uji) langsung dirender.
 */
export default function LazyMount({ children, eager = false, minHeight = 76, testId }) {
  const ref = useRef(null);
  const [shown, setShown] = useState(
    eager || typeof window === "undefined" || typeof window.IntersectionObserver === "undefined");
  useEffect(() => {
    if (shown || !ref.current) return undefined;
    const io = new window.IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        setShown(true);
        io.disconnect();
      }
    }, { rootMargin: "600px 0px" });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [shown]);
  if (shown) return children;
  return <div ref={ref} style={{ minHeight }} className="rounded-lg bg-[#FAFAFB]" aria-hidden="true" data-testid={testId} />;
}
