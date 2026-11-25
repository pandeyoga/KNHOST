/**
 * DocPreviewModal + DocPreviewHost (Meja gelombang 2) — pop-up pratinjau dokumen (`DetailModal`), isi dari registri.
 *
 *  · Tumpukan target internal: `push(target)` dari isi membuka dokumen lain DI DALAM pop-up yang sama (tidak menumpuk
 *    dua `DetailModal`); "‹ Kembali" muncul bila tumpukan > 1. Esc / klik latar menutup seluruhnya.
 *  · Galat muat (404, jaringan, 403 bila izin berubah) → `ErrorNotice` di dalam pop-up dengan "Coba lagi".
 *  · Kaki: "Jejak" (Jejak Dokumen) dan "Buka layar penuh" (pindah layar → ikon `ExternalLink`, pola `DeskRowDetail`).
 *  · `DocPreviewHost` dipasang SEKALI di `AppViewRouter`, membaca `useAppNav().docPreview`.
 */
import { useCallback, useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import DetailModal from "../../../components/DetailModal";
import ErrorNotice from "../../../components/ErrorNotice";
import { useAppNav } from "../../../context/AppNavContext";
import { openTrace } from "../trace/traceDeepLink";
import { canPreview, previewFor } from "./docPreviewRegistry";

const GALAT_BAWAAN = "Dokumen tidak bisa dimuat.";

export default function DocPreviewModal({ target, onClose, currentUser }) {
  const nav = useAppNav();
  const [stack, setStack] = useState([target]);
  // `key` = docType+docId+PT yang dimuat state ini; Body hanya dirender bila cocok dengan target teratas, jadi sesudah
  // push/back tidak pernah ada render dengan Body baru + dokumen jenis lain.
  const [state, setState] = useState({ key: "", loading: true, doc: null, error: "" });
  const [nonce, setNonce] = useState(0);
  const top = stack[stack.length - 1];
  const entry = previewFor(top?.docType);
  const topKey = `${top?.docType}|${top?.docId}|${top?.entityId || ""}`;
  const perms = currentUser?.permissions;

  useEffect(() => {
    let batal = false;
    if (!entry) { setState({ key: topKey, loading: false, doc: null, error: "Jenis dokumen ini belum punya pratinjau." }); return undefined; }
    setState({ key: topKey, loading: true, doc: null, error: "" });
    Promise.resolve()
      .then(() => entry.load(top.docId, { entityId: top.entityId }))
      .then((doc) => { if (!batal) setState({ key: topKey, loading: false, doc, error: "" }); })
      .catch((err) => { if (!batal) setState({ key: topKey, loading: false, doc: null, error: err || GALAT_BAWAAN }); });
    return () => { batal = true; };
  }, [entry, topKey, nonce]);

  // Tanpa izin baca jenis itu, push diabaikan (bukan 403 di dalam pop-up); Body memakai `canPush` untuk memilih tombol/teks.
  const canPush = useCallback((docType) => canPreview(perms, docType), [perms]);
  const push = useCallback((t) => {
    if (t && t.docId && canPreview(perms, t.docType)) setStack((s) => [...s, t]);
  }, [perms]);
  const back = () => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s));

  const cocok = state.key === topKey;
  const doc = cocok ? state.doc : null;
  const number = doc?.number || top?.number || "";
  const title = [entry?.label || "Dokumen", number].filter(Boolean).join(" · ");
  const Body = entry?.Body;
  const full = entry?.full && doc ? entry.full(doc) : null;

  return (
    <DetailModal framed size="md" testId="doc-preview" label={`Pratinjau ${title}`} onClose={onClose}>
      <div className="grid gap-3">
        <div className="flex flex-wrap items-center gap-2 pr-6">
          {stack.length > 1 && (
            <button type="button" className="link-button" data-testid="doc-preview-back" onClick={back}>‹ Kembali</button>
          )}
          <h2 className="min-w-0 break-words text-fs-16 font-semibold text-kn-text" data-testid="doc-preview-title">{title}</h2>
        </div>
        {cocok && state.error && <ErrorNotice message={state.error} onRetry={() => setNonce((n) => n + 1)} testId="doc-preview-error" />}
        {(!cocok || state.loading) && <p className="py-6 text-center text-fs-12 text-kn-text-2" role="status" data-testid="doc-preview-loading">Memuat…</p>}
        {doc && Body && <Body doc={doc} push={push} canPush={canPush} currentUser={currentUser} />}
        <div className="flex flex-wrap items-center gap-2 border-t border-kn-divider pt-3">
          {top?.docId && (
            <button type="button" className="link-button" data-testid="doc-preview-trace"
              onClick={() => openTrace({ docType: top.docType, docId: top.docId, number })}>Jejak</button>
          )}
          {full && (
            <button type="button" className="secondary-button btn-sm" data-testid="doc-preview-full"
              onClick={() => { nav.openDocument(full); onClose && onClose(); }}>
              Buka layar penuh
              <ExternalLink size={14} className="ml-1" title="Pindah ke layar lain" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </DetailModal>
  );
}

export function DocPreviewHost({ currentUser }) {
  const { docPreview, closeDocPreview } = useAppNav();
  if (!docPreview) return null;
  return <DocPreviewModal key={docPreview.nonce} target={docPreview} onClose={closeDocPreview} currentUser={currentUser} />;
}
