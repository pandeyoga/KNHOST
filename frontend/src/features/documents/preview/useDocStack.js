/**
 * useDocStack (Meja gelombang 2) — tumpukan target + status muat untuk pratinjau dokumen.
 *
 * Dipakai `DocPreviewModal` (pop-up pratinjau mandiri) dan `DeskDocPanel` (pratinjau di dalam pop-up meja): keduanya
 * memuat isi registri DI DALAM satu `DetailModal`; `push(target)` dari isi menumpuk dokumen lain di tempat yang sama.
 *
 * Jaminan: `matches` hanya benar bila dokumen yang termuat milik target teratas; pemanggil merender `Body` hanya saat
 * `doc` ada (`doc` null selama `matches` salah), jadi sesudah push/back tidak pernah ada render dengan Body baru +
 * dokumen jenis lain.
 */
import { useCallback, useEffect, useState } from "react";
import { canPreview, previewFor } from "./docPreviewRegistry";

const GALAT_BAWAAN = "Dokumen tidak bisa dimuat.";

export default function useDocStack(initialTarget, perms) {
  const [stack, setStack] = useState([initialTarget]);
  const [state, setState] = useState({ key: "", loading: true, doc: null, error: "" });
  const [nonce, setNonce] = useState(0);
  const top = stack[stack.length - 1];
  const entry = previewFor(top?.docType);
  const topKey = `${top?.docType}|${top?.docId}|${top?.entityId || ""}`;

  useEffect(() => {
    let batal = false;
    if (!entry) { setState({ key: topKey, loading: false, doc: null, error: "Jenis dokumen ini belum punya pratinjau." }); return undefined; }
    setState({ key: topKey, loading: true, doc: null, error: "" });
    Promise.resolve()
      .then(() => entry.load(top.docId, { entityId: top.entityId }))
      .then((doc) => { if (!batal) setState({ key: topKey, loading: false, doc, error: "" }); })
      .catch((err) => { if (!batal) setState({ key: topKey, loading: false, doc: null, error: err || GALAT_BAWAAN }); });
    return () => { batal = true; };
  }, [entry, topKey, nonce]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Tanpa izin baca jenis itu, push diabaikan (bukan 403 di dalam pop-up); Body memakai `canPush` untuk memilih tombol/teks.
  const canPush = useCallback((docType) => canPreview(perms, docType), [perms]);
  const push = useCallback((t) => {
    if (t && t.docId && canPreview(perms, t.docType)) setStack((s) => [...s, t]);
  }, [perms]);
  const back = useCallback(() => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s)), []);
  const retry = useCallback(() => setNonce((n) => n + 1), []);

  const matches = state.key === topKey;
  return {
    top, entry, matches, canPush, push, back, retry, depth: stack.length,
    doc: matches ? state.doc : null,
    loading: !matches || state.loading,
    error: matches ? state.error : "",
  };
}
