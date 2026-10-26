/**
 * TransferList — SATU daftar transfer (antar gudang + antar PT) dengan kolom "Jenis" (fase 3 · P5, D-16).
 *
 * Dulu: kartu antar gudang di Operasi Gudang + kartu ungu antar-PT di sub-tab tersendiri (transfer antar-PT tampil
 * di keduanya, dengan dua gaya tombol Setujui). Kini satu `ResponsiveTable` (tabel ≥641 px, kartu di HP); klik
 * baris membuka satu `TransferDetailModal` yang aksinya menyesuaikan jenis. Testid lama baris dipertahankan
 * (`transfer-card-<id>`, `transfer-code-<id>`, `transfer-route-<id>`).
 */
import { ArrowRight } from "lucide-react";
import ResponsiveTable from "../../../components/ResponsiveTable";
import QtyDual from "../../../components/QtyDual";
import { formatDate } from "../../../utils/formatters";
import { StatusBadge } from "./transferConstants";

/** Jenis transfer — record lama tanpa `transfer_kind` = antar gudang (sama dengan backend). */
export const transferKindOf = (t) => (t?.transfer_kind === "inter_entity" ? "inter_entity" : "intra_entity");
export const TRANSFER_KIND_LABEL = { intra_entity: "Antar gudang", inter_entity: "Antar PT" };

function KindPill({ t }) {
  const ic = transferKindOf(t) === "inter_entity";
  return (
    <span data-testid={`transfer-kind-${t.id}`} className={`status-pill ${ic ? "pill-purple" : "pill-muted"}`}>
      {TRANSFER_KIND_LABEL[transferKindOf(t)]}
    </span>
  );
}

function Route({ t }) {
  const ic = transferKindOf(t) === "inter_entity";
  return (
    <span data-testid={`transfer-route-${t.id}`} className="text-[#3C3C43]">
      {ic && (t.source_entity_name || t.dest_entity_name) ? (
        <>
          <b>{t.source_entity_name || "—"}</b> <ArrowRight size={11} className="inline" /> <b>{t.dest_entity_name || "—"}</b>
          {(t.source_warehouse_name || t.dest_warehouse_name) && (
            <span className="block text-[11px] text-[#8E8E93]">
              {t.source_warehouse_name || "—"} → {t.dest_warehouse_name || "—"}
            </span>
          )}
        </>
      ) : (
        <>{t.source_warehouse_name || "—"} <ArrowRight size={11} className="inline" /> {t.dest_warehouse_name || "—"}</>
      )}
    </span>
  );
}

function Items({ t }) {
  const items = t.items || [];
  if (!items.length) return <span className="text-[#8E8E93]">—</span>;
  const first = items[0];
  return (
    <span className="text-[#3C3C43]">
      {first.product_name || first.sku}
      {items.length > 1 ? <span className="text-[#8E8E93]"> +{items.length - 1} lainnya</span> : null}
      {items.length === 1 && (first.qty || first.qty_rolls) ? (
        <span className="block text-[11px] text-[#6B6B73]">
          <QtyDual rolls={first.qty_rolls} measure={first.qty} unit={first.unit} compact />
        </span>
      ) : null}
    </span>
  );
}

const COLUMNS = [
  { key: "code", header: "Kode", mobile: "title",
    render: (t) => <span data-testid={`transfer-code-${t.id}`} className="font-bold text-[#0058CC]">{t.code || "—"}</span> },
  { key: "kind", header: "Jenis", mobile: "badge", render: (t) => <KindPill t={t} /> },
  { key: "route", header: "Dari → ke", mobile: "subtitle", render: (t) => <Route t={t} /> },
  { key: "items", header: "Barang", priority: 1, render: (t) => <Items t={t} /> },
  { key: "requested_by", header: "Diajukan", priority: 2,
    render: (t) => (
      <span>{t.requested_by || "—"}
        {t.created_at ? <span className="block text-[11px] text-[#8E8E93]">{formatDate(t.created_at)}</span> : null}
      </span>
    ) },
  { key: "approved_by", header: "Disetujui", priority: 4, render: (t) => t.approved_by || "" },
  { key: "status", header: "Status", mobile: "badge", priority: 3, render: (t) => <StatusBadge status={t.status} /> },
];

export default function TransferList({ rows = [], loading = false, onOpen, emptyText = "Belum ada transfer." }) {
  return (
    <ResponsiveTable testId="transfer-list" rows={rows} rowKey="id" loading={loading} columns={COLUMNS}
      onRowClick={onOpen} rowTestId={(t) => `transfer-card-${t.id}`} empty={emptyText} />
  );
}
