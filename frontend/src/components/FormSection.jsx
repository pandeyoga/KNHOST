/**
 * FormSection — bagian form BERNOMOR yang bisa dilipat (fase 3 · P1, L-10).
 *
 * KENAPA ADA: form panjang (Induk produk baru, Pelanggan CRM, Karyawan, Kontrak, Template Dokumen) tampil
 * sebagai satu dinding isian. Bagian bernomor ("1 Identitas · 2 Alamat · 3 Syarat bayar") memberi peta,
 * bagian yang jarang diubah bisa dilipat. Keputusan pemilik: form di HP TIDAK boleh diringkas — melipat
 * hanya MENYEMBUNYIKAN tampilan; isian tetap terpasang (nilai & validasi tidak hilang) dan bisa dibuka lagi.
 *
 *   <FormModal …>
 *     <FormSection number={1} title="Identitas" testId="cust-sec-id">…isian…</FormSection>
 *     <FormSection number={2} title="Syarat bayar" collapsible defaultOpen={false}
 *       summary={`${termin} hari · limit ${formatCurrency(limit)}`}>…isian…</FormSection>
 *   </FormModal>
 *
 * Props: `number` · `title` · `subtitle` · `summary` (tampil saat terlipat) · `required` (tanda wajib di judul)
 *   · `collapsible` (bawaan false) · `defaultOpen` (bawaan true) · `open` + `onToggle(next)` (mode terkendali)
 *   · `actions` (node di kanan kepala) · `testId` (tombol lipat `${testId}-toggle`, badan `${testId}-body`)
 *   · `className` · `children`.
 */
import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

export default function FormSection({
  number, title, subtitle = "", summary = null, required = false, collapsible = false, defaultOpen = true,
  open: openProp, onToggle, actions = null, testId, className = "", children,
}) {
  const [openState, setOpenState] = useState(defaultOpen);
  const open = collapsible ? (openProp ?? openState) : true;
  const bodyId = useId();
  const toggle = () => {
    const next = !open;
    if (openProp === undefined) setOpenState(next);
    onToggle?.(next);
  };
  const heading = (
    <>
      {number !== undefined && number !== null && number !== "" && (
        <span className="form-section-num" aria-hidden="true">{number}</span>
      )}
      <span className="form-section-titles">
        <span className="form-section-title">
          {title}{required ? <span className="form-section-req" aria-label="wajib"> *</span> : null}
        </span>
        {subtitle && <span className="form-section-sub">{subtitle}</span>}
        {!open && summary ? <span className="form-section-summary" data-testid={testId ? `${testId}-summary` : undefined}>{summary}</span> : null}
      </span>
    </>
  );
  return (
    <section className={`form-section ${open ? "is-open" : "is-closed"} ${className}`.trim()} data-testid={testId}>
      <div className="form-section-head">
        {collapsible ? (
          <button type="button" className="form-section-toggle" aria-expanded={open} aria-controls={bodyId}
            data-testid={testId ? `${testId}-toggle` : undefined} onClick={toggle}>
            {heading}
            <ChevronDown size={14} aria-hidden="true" className="form-section-chevron" />
          </button>
        ) : (
          <div className="form-section-toggle is-static">{heading}</div>
        )}
        {actions ? <div className="form-section-actions">{actions}</div> : null}
      </div>
      {/* Terlipat = disembunyikan, BUKAN dilepas: isian tetap terpasang sehingga nilainya tidak hilang. */}
      <div id={bodyId} className="form-section-body" hidden={!open} data-testid={testId ? `${testId}-body` : undefined}>
        {children}
      </div>
    </section>
  );
}
