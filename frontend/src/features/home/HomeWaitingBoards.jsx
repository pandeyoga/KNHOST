/**
 * HomeWaitingBoards — papan "menunggu keputusan" untuk SEMUA beranda (Control Tower, Dasbor Manajer, Beranda Sales).
 *
 * Fase 3 · P3 (D-07/D-28, keputusan pemilik 26 Okt): papan **PO Custom** dan **Barang ditahan QC** di beranda kini
 * TAUTAN (`mode="link"`): tanpa tombol Setujui/Lepas, klik baris membuka dokumennya di layar utama (Pesanan Khusus
 * terfokus · SPK Inspeksi) — keputusan hanya di sana dengan SATU dialog (`services/approvalDecisions.js`). Papan
 * lain (kontrabon, retur antar-PT, tagihan, …) tetap bisa ditindak seperti dulu. Daftar papan tautan =
 * `HOME_LINK_BOARDS` (config/waitingBoards.js) supaya tiga beranda (dan beranda HP, P7) tidak berselisih.
 *
 * Dulu tiap beranda menggambar papannya sendiri dengan salinan prop yang sama; kini satu komponen.
 * Props: `boards` (hasil `selectWaitingBoards`) · `loading` · `unreadable` · `onRetry` · `onActed` · `onNavigate(view)`
 *   · `onOpenDocument(link)` (bawaan `useAppNav().openDocument`) · `entityId` · `showEntity` · `testId` (pembungkus)
 *   · `ids(board)` → `{ testIdBase, rowTestIdBase, gotoTestId }` · `look(board, look)` → `{ title, emptyText }`
 *   (penimpa teks per beranda, mis. "· pelanggan Anda") · `className`.
 */
import WaitingQueueBoard from "../../components/WaitingQueueBoard";
import { useAppNav } from "../../context/AppNavContext";
import { boardLook, boardRowLink, isLinkBoard, LINK_BOARD_PRESET } from "../../config/waitingBoards";

export default function HomeWaitingBoards({
  boards = [], loading = false, unreadable = false, onRetry, onActed, onNavigate, onOpenDocument,
  entityId = "all", showEntity = false, testId, ids, look: lookOverride, className = "grid gap-3",
}) {
  const nav = useAppNav();
  const openDoc = onOpenDocument || nav.openDocument;
  return (
    <div className={className} data-testid={testId}>
      {boards.map((b) => {
        const look = boardLook(b.key);
        const asLink = isLinkBoard(b.key);
        const own = ids ? ids(b) : {};
        const txt = lookOverride ? lookOverride(b, look) : {};
        // Tombol "Buka …" papan tautan membawa preset layar tujuan (Pesanan Khusus › Menunggu Persetujuan).
        const goto = (view) => {
          const preset = asLink ? LINK_BOARD_PRESET[b.key] : null;
          if (preset && nav.canOpen(view)) nav.go(view, { preset });
          else if (onNavigate) onNavigate(view);
        };
        return (
          <WaitingQueueBoard key={b.key} board={b} loading={loading}
            entityId={entityId} unreadable={unreadable} onRetry={onRetry} onActed={onActed}
            mode={asLink ? "link" : "act"}
            onOpenRow={asLink ? (row) => openDoc?.(boardRowLink(b, row)) : undefined}
            onNavigate={goto}
            showEntity={showEntity} icon={look.icon} accent={look.accent} gotoLabel={look.goto}
            title={txt.title || look.title} emptyText={txt.emptyText || look.empty}
            testIdBase={own.testIdBase} rowTestIdBase={own.rowTestIdBase} gotoTestId={own.gotoTestId} />
        );
      })}
    </div>
  );
}
