/**
 * DeskDocPanel (Meja gelombang 2) — panel pop-up meja yang memuat rincian dokumen dari registri pratinjau.
 *
 *  · Atas: SEMUA fakta baris dari pembangun yang sama dengan panel umum, kecuali yang sudah di judul/subjudul (lencana, PT, umur); tabel kurang stok tetap, tabel barang-per-gudang tidak diulang (ada di pratinjau).
 *  · Bawah: `Body` registri untuk dokumen itu, dimuat DI DALAM pop-up meja (`useDocStack`). Panel TIDAK membuka
 *    `DocPreviewModal`, jadi hanya ada satu `DetailModal`. `push` dari isi (mis. alokasi kwitansi → pesanan) menumpuk
 *    di panel ini dengan "‹ Kembali" sendiri.
 *  · Tanpa `docId`, jenis tak punya pratinjau, atau tanpa izin baca jenis itu → panel umum gelombang 1.
 *  · Galat muat → `ErrorNotice` di panel (fakta baris tetap tampil), dengan "Coba lagi".
 *  · Kaki pop-up (aksi baris, "Buka layar penuh") digambar `DeskRowDetail`, bukan di sini; "Jejak" ada di panel.
 */
import ErrorNotice from "../../components/ErrorNotice";
import { openTrace } from "../documents/trace/traceDeepLink";
import { canPreview } from "../documents/preview/docPreviewRegistry";
import useDocStack from "../documents/preview/useDocStack";
import { GenericPanel } from "./GenericDeskPanel";
import { permsOf } from "./deskPerms";

// Sudah ada di judul/subjudul pop-up (lencana, PT, umur) → tidak diulang di panel.
const DI_JUDUL = ["badge", "entity_id", "age"];

function DocBody({ row, queue, currentUser, docType, docId, p, pt }) {
  const perms = permsOf(currentUser);
  const { top, entry, doc, loading, error, push, back, canPush, depth, retry } =
    useDocStack({ docType, docId, number: row.number, ...(row.entity_id ? { entityId: row.entity_id } : {}) }, perms);
  const Body = entry?.Body;
  const nomor = doc?.number || top?.number || "";
  const judul = [entry?.label || "Dokumen", nomor].filter(Boolean).join(" · ");
  return (
    <div className="grid gap-3" data-testid={`${p}-doc-panel`}>
      {depth === 1 && <GenericPanel row={row} queue={queue} p={p} pt={pt} except={DI_JUDUL} withOrderLines={false} />}
      {depth > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="link-button" data-testid={`${p}-doc-back`} onClick={back}>‹ Kembali</button>
          <h3 className="min-w-0 break-words text-fs-14 font-semibold text-kn-text" data-testid={`${p}-doc-title`}>{judul}</h3>
        </div>
      )}
      {error && <ErrorNotice message={error} onRetry={retry} testId="doc-preview-error" />}
      {loading && <p className="py-4 text-center text-fs-12 text-kn-text-2" role="status" data-testid="doc-preview-loading">Memuat…</p>}
      {doc && Body && <Body doc={doc} push={push} canPush={canPush} currentUser={currentUser} />}
      {top?.docId && (
        <div>
          <button type="button" className="link-button" data-testid={`${p}-doc-trace`}
            onClick={() => openTrace({ docType: top.docType, docId: top.docId, number: nomor })}>Jejak</button>
        </div>
      )}
    </div>
  );
}

export default function DeskDocPanel({ row, queue, currentUser, docType, docId, testPrefix = "desk", pt = "" }) {
  const dapat = docId && docType && canPreview(permsOf(currentUser), docType);
  if (!dapat) return <GenericPanel row={row} queue={queue} p={testPrefix} pt={pt} />;
  return <DocBody row={row} queue={queue} currentUser={currentUser} docType={docType} docId={docId} p={testPrefix} pt={pt} />;
}
