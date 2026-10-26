/**
 * FinReportLink — tautan "Rincian di Laporan Keuangan →" (fase 3 · P4, D-10).
 *
 * KENAPA ADA: ringkasan laba-rugi dulu diulang di Dasbor Keuangan, BI Keuangan, Konsolidasi & pratinjau Tutup Buku
 * (Marjin Bersih & Posisi Kas masing-masing tampil 2× di Dasbor). Keputusan D-10: rincian laba-rugi HANYA di
 * Akuntansi & Pajak › Laporan › Laba-Rugi (`financial-statements`); layar lain menampilkan ringkasan + tautan ini.
 * Tautan lewat jalur navigasi bersama (`useAppNav().go`, preset tab). Peran yang tidak boleh membuka Laporan
 * Keuangan tidak melihat tombol mati — yang tampil kalimat sumber biasa.
 *
 *   <FinReportLink testId="tower-pl-link" />                       // tab Laba-Rugi
 *   <FinReportLink tab="bs" label="Neraca di Laporan Keuangan" />
 */
import { ArrowRight } from "lucide-react";
import { useAppNav } from "../../context/AppNavContext";

export default function FinReportLink({ tab = "pl", label = "Rincian di Laporan Keuangan", testId = "fin-report-link", className = "" }) {
  const { go, canOpen } = useAppNav();
  if (!canOpen("financial-statements")) {
    return (
      <span className={`text-[11px] text-[#8E8E93] ${className}`.trim()} data-testid={`${testId}-readonly`}>
        Rincian: Akuntansi & Pajak › Laporan
      </span>
    );
  }
  return (
    <button type="button" data-testid={testId}
      className={`inline-flex items-center gap-1 text-[11.5px] font-semibold text-[#0058CC] hover:underline ${className}`.trim()}
      onClick={() => go("financial-statements", { preset: { tab } })}>
      {label} <ArrowRight size={12} aria-hidden="true" />
    </button>
  );
}
