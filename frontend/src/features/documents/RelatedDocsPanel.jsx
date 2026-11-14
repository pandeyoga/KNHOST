// RelatedDocsPanel — grup dokumen CETAK turunan sebuah record (SO/PO/PR/Faktur).
// Menampilkan beberapa DocumentActionsBar (Pratinjau · Unduh · E-Sign · WA) berlabel,
// sehingga user bisa mencetak dokumen operasional langsung dari detail-view.
// PK-44 (IA-13) — judul "Cetak Dokumen" (isinya daftar cetak, bukan relasi); relasi = panel "Dokumen Terkait".
import DocumentActionsBar from "./DocumentActionsBar";
import { FileStack } from "lucide-react";

export default function RelatedDocsPanel({
  title = "Cetak Dokumen",
  docs = [],
  sourceId,
  entityId,
  number,
  currentUser,
  onChanged,
}) {
  const list = (docs || []).filter(Boolean);
  if (!sourceId || list.length === 0) return null;
  return (
    <div data-testid="related-docs-panel" className="rounded-lg border border-kn-divider bg-white p-3">
      <p className="mb-2 flex items-center gap-1.5 text-fs-13 font-bold text-kn-text">
        <FileStack size={14} className="text-kn-action" aria-hidden="true" /> {title}
      </p>
      <div className="space-y-2">
        {list.map((d) => (
          <div
            key={d.docType}
            data-testid={`related-doc-${d.docType}`}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-kn-divider bg-white px-2 py-1.5"
          >
            <span className="min-w-[130px] text-fs-12 font-semibold text-kn-neutral">
              {d.label}
            </span>
            <DocumentActionsBar
              docType={d.docType}
              sourceId={sourceId}
              entityId={entityId}
              number={number}
              label={d.label}
              currentUser={currentUser}
              onChanged={onChanged}
              compact
              autoCheckSignature={false}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
