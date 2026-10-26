/**
 * SampleListTable — mode **Daftar** layar Sample R&D. Fase 3 · P6 (L-04/L-07): `ResponsiveTable` → tabel di
 * layar lebar, kartu di HP 390 px (dulu tabel `minWidth: 760` menggulir seluruh halaman ke samping).
 * Testid baris tetap `rnd-sample-row-<id>`; tombol nomor `rnd-sample-open-<id>`, Detail `rnd-sample-detail-<id>`.
 */
import EntityBadge from "../../components/EntityBadge";
import ResponsiveTable from "../../components/ResponsiveTable";
import { formatDateId } from "../../components/KNDatePicker";
import { RevisionBadge, sampleRevisionCount } from "../../components/RevisionProgress";
import { TypeBadge } from "./SampleBoardCard";
import { sampleStatusMeta } from "./rndMeta";
import { sampleTypesOf } from "./sampleTypeMeta";

export default function SampleListTable({ rows, types, onOpen }) {
  const columns = [
    { key: "number", header: "Nomor", mobile: "title",
      render: (s) => <button type="button" className="link-button font-semibold" data-testid={`rnd-sample-open-${s.id}`}
        onClick={(e) => { e.stopPropagation(); onOpen(s.id); }}>{s.number}</button> },
    { key: "title", header: "Judul", mobile: "subtitle",
      render: (s) => (
        <span className="block min-w-0">
          <span className="line-clamp-1 text-[#3C3C43]">{s.title}</span>
          <span className="flex items-center gap-1 text-[10px] text-[#8E8E93]"><EntityBadge entityId={s.entity_id} />{s.spec_number || ""}{s.so_number ? ` · ${s.so_number}` : ""}</span>
        </span>
      ) },
    { key: "types", header: "Jenis", priority: 1,
      render: (s) => <span className="flex flex-wrap gap-1" data-testid={`rnd-sample-types-${s.id}`}>{sampleTypesOf(s).map((c) => <TypeBadge key={c} code={c} types={types} />)}</span> },
    { key: "suppliers", header: "Supplier", priority: 2,
      value: (s) => (s.participants || []).map((p) => p.supplier_name).join(", ") },
    { key: "target", header: "Target", priority: 3,
      render: (s) => {
        const overdue = (s.rounds || []).some((r) => r.overdue);
        return s.target_date
          ? <span className={overdue ? "font-semibold text-[#A8221A]" : ""}>{formatDateId(s.target_date, "dd MMM yyyy")}</span> : "—";
      } },
    { key: "status", header: "Status", mobile: "badge",
      render: (s) => { const meta = sampleStatusMeta(s); return <span className={`status-pill ${meta.cls}`} data-testid={`rnd-sample-status-${s.id}`}>{meta.label}</span>; } },
    { key: "revision", header: "Ronde", priority: 4,
      render: (s) => <RevisionBadge count={sampleRevisionCount(s)} testId={`rnd-sample-revision-${s.id}`} /> },
  ];
  return (
    <div className="section-card">
      <ResponsiveTable testId="rnd-sample" rows={rows} rowKey="id" columns={columns} onRowClick={(s) => onOpen(s.id)}
        actions={(s) => <button type="button" className="link-button" data-testid={`rnd-sample-detail-${s.id}`} onClick={() => onOpen(s.id)}>Detail</button>} />
    </div>
  );
}
