import { ArrowLeft } from "lucide-react";
import { useAppNav } from "../context/AppNavContext";

/**
 * BackToOriginBar — PK-44 (IA-11) · bilah "← Kembali ke {layar asal}" di atas layar aktif sesudah melompat ke dokumen
 * (Jejak Dokumen, panel Dokumen Terkait, kartu angka). `origin = { view, navId, tab, label, trace }` diisi
 * `useAppNavigation.openDocument` / tautan ber-`preset.from`; hilang saat pengguna memilih menu lain.
 * Bila layar sedang menampilkan rincian dokumen bertombol kembali (`DetailBack`), bilah ini mundur: rincian menampilkan
 * SATU baris "← Kembali ke {asal} · Daftar …" (dulu dua "Kembali" bertumpuk).
 */
export default function BackToOriginBar({ origin, onBack }) {
  const { detailBackCount } = useAppNav();
  if (!origin?.view || !onBack || detailBackCount > 0) return null;
  return (
    <div className="mb-3 flex items-center" data-testid="back-to-origin-bar">
      <button type="button" className="link-button" data-testid="back-to-origin" onClick={() => onBack(origin)}>
        <ArrowLeft size={14} aria-hidden="true" /> Kembali ke {origin.label || "layar sebelumnya"}
      </button>
    </div>
  );
}
