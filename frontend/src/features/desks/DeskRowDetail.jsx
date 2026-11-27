import { ExternalLink } from "lucide-react";
import DetailModal from "../../components/DetailModal";
import { useEntityScope } from "../../context/EntityScopeContext";
import { entityShortById } from "../../utils/entityLabel";
import { ageText, badgeLabel } from "../sales_admin/workDeskApi";
import { GenericPanel } from "./GenericDeskPanel";
import { panelFor } from "./deskPanels";

const isi = (v) => v !== undefined && v !== null && v !== "";

/** Pop-up rincian umum baris meja; jenis dokumen yang punya panel di registri memakai panelnya. */
export default function DeskRowDetail({ row, queue: queueProp, testPrefix = "desk", inPlace = () => false, currentUser, traceEnabled = true, onAction, onOpenFull, onClose, onRowChanged }) {
  const queue = queueProp || {};
  const p = testPrefix;
  const { entities } = useEntityScope();
  const pt = entityShortById(entities, row.entity_id, "");
  const ptShown = row.entity_id ? pt : "";
  const Panel = panelFor(row, queue);
  const sub = [ptShown, badgeLabel(row.badge), isi(row.age_days) || row.age_kind === "overdue" ? ageText(row) : ""].filter(Boolean).join(" · ");
  const run = (r) => { onClose && onClose(); onAction && onAction(r, queue); };
  // Sama dengan tombol baris di kartu: baris tanpa aksi sendiri memakai aksi antreannya.
  // `action_kind: "view"` ("Lihat") = membuka pop-up ini saja; tak ada aksi utama lagi (ubah → "Buka layar penuh").
  // `decide_payment_report` (LB-T8) = keputusan Terima/Tolak ada DI panel (`PayReportQueuePanel`), bukan tombol kaki.
  // `row._openFullLabel` — nama tujuan "Buka layar penuh" bila meja tahu tempatnya (F1: "Buka Rekonsiliasi").
  const actionLabel = (row.action_kind === "view" || row.action_kind === "decide_payment_report") ? "" : row.action || queue.action_label || "";
  const more = Array.isArray(row._moreActions) ? row._moreActions : [];

  return (
    <DetailModal framed size="md" testId={`${p}-detail`} label={`Rincian ${row.number}`} onClose={onClose}>
      <div className="grid gap-3">
        <div className="pr-6">
          <h2 data-testid={`${p}-detail-title`} className="text-fs-16 font-semibold text-kn-text break-words">{`${row.number} · ${row.title}`}</h2>
          {sub && <p data-testid={`${p}-detail-subtitle`} className="text-fs-12 text-kn-text-2">{sub}</p>}
        </div>
        {Panel
          ? <Panel row={row} queue={queue} currentUser={currentUser} traceEnabled={traceEnabled} testPrefix={p} pt={ptShown} onAction={onAction} onClose={onClose} onOpenFull={onOpenFull} onRowChanged={onRowChanged} />
          : <GenericPanel row={row} queue={queue} p={p} pt={ptShown} />}
        <div className="flex flex-wrap items-center gap-2 border-t border-kn-divider pt-3">
          {actionLabel && (
            <button type="button" className="primary-button btn-sm" data-testid={`${p}-detail-action`} onClick={() => run(row)}>
              {actionLabel}
              {!inPlace(row) && <ExternalLink size={14} className="ml-1" data-testid={`${p}-detail-action-nav`} title="Pindah ke layar lain" aria-hidden="true" />}
            </button>
          )}
          {more.map((a, i) => (
            <button key={i} type="button" className="secondary-button btn-sm" data-testid={`${p}-detail-action-${i}`} onClick={() => run(a.row)}>{a.label}</button>
          ))}
          {onOpenFull && (
            <button type="button" className="link-button" data-testid={`${p}-detail-open-full`}
              onClick={() => { onClose && onClose(); onOpenFull(row, queue); }}>{row._openFullLabel || "Buka layar penuh"}</button>
          )}
        </div>
      </div>
    </DetailModal>
  );
}
