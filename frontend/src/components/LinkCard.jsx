/**
 * LinkCard — kartu satu baris "<Hal> kini dikelola di <Menu › Layar>" + [Buka] (fase 3 · P1, pola tautan §1.2).
 *
 * Keputusan pemilik 26 Okt: layar/tabel DUPLIKAT tidak dihapus diam-diam, melainkan diganti TAUTAN ke layar
 * utama. Kartu ini memakai jalur navigasi bersama (`useAppNav().go` → alias + preset + sorotan menu) dan
 * HANYA menampilkan tombol bila peran aktif boleh membuka layar utama (`canOpen`, SSOT menu). Bila tidak
 * boleh, yang tampil ringkasan BACA-SAJA satu baris — bukan tabel duplikat, bukan tombol mati.
 *
 *   <LinkCard testId="em-doc-templates-link" what="Template dokumen" where="Pengaturan › Template Dokumen"
 *     view="pdf-templates" preset={{ tab: "dasar" }} summary="3 template aktif" />
 *   <LinkCard what="Skor mitra" where="Pesanan Pembelian › Kinerja Mitra Makloon" view="makloon-claim-recap"
 *     focus={{ type: "makloon_partner", id: partner.id }} label="Lihat skor" />
 *
 * Props: `what` · `where` (teks menu, mis. "Pengaturan › Template Dokumen") · `view` (boleh id lama/alias)
 *   · `preset` · `tab` · `focus` ({ type, id, number }) · `label` (bawaan "Buka") · `summary` (node ringkas,
 *   tampil di kedua mode) · `count` (lencana angka) · `icon` · `readOnlyText` (pengganti kalimat baca-saja)
 *   · `hideWhenDenied` (sembunyikan total bila tak berwenang) · `testId` (bawaan "link-card"; tombol
 *   `${testId}-open`, mode baca-saja `${testId}-readonly`) · `className`.
 */
import { ArrowRight, Link2 } from "lucide-react";
import { useAppNav } from "../context/AppNavContext";

export default function LinkCard({
  what = "", where = "", view, preset, tab, focus, label = "Buka", summary = null, count,
  icon: Icon = Link2, readOnlyText = "", hideWhenDenied = false, testId = "link-card", className = "",
}) {
  const { go, canOpen } = useAppNav();
  const allowed = !!view && canOpen(view);
  if (!allowed && hideWhenDenied) return null;

  const sentence = what
    ? <><b>{what}</b> kini dikelola di <b>{where}</b>.</>
    : <>Dikelola di <b>{where}</b>.</>;
  const badge = count !== undefined && count !== null && count !== ""
    ? <span className="link-card-count" data-testid={`${testId}-count`}>{count}</span> : null;

  if (!allowed) {
    return (
      <p className={`link-card link-card-readonly ${className}`.trim()} data-testid={`${testId}-readonly`}>
        <Icon size={14} aria-hidden="true" className="link-card-icon" />
        <span className="link-card-text">
          {readOnlyText || sentence}
          {badge}
          {summary ? <span className="link-card-summary"> · {summary}</span> : null}
        </span>
      </p>
    );
  }
  return (
    <div className={`link-card ${className}`.trim()} data-testid={testId}>
      <Icon size={14} aria-hidden="true" className="link-card-icon" />
      <span className="link-card-text">
        {sentence}
        {badge}
        {summary ? <span className="link-card-summary"> · {summary}</span> : null}
      </span>
      <button type="button" className="secondary-button link-card-open" data-testid={`${testId}-open`}
        onClick={() => go(view, { preset, tab, focus })}>
        {label} <ArrowRight size={13} aria-hidden="true" />
      </button>
    </div>
  );
}
