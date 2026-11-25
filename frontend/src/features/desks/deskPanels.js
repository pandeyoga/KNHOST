// Registri panel rincian per jenis dokumen. Gelombang 2–3 mengisi `ref_type → Komponen`.
// Kontrak props panel: { row, queue, onAction(row, queue), onClose(), onOpenFull(row, queue) }.
export const DESK_PANELS = {};

export function panelFor(refType) {
  return (refType && DESK_PANELS[refType]) || null;
}
