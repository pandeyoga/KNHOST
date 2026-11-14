/**
 * useFocusDoc — PK-44 (IA-04) · SATU pembaca fokus dokumen untuk layar tujuan tautan.
 *
 * Tautan dokumen (Jejak Dokumen, panel Dokumen Terkait, meja, rincian jurnal) membuka layar tujuan lewat
 * `openDocument(link)` → `focusDoc = { focus_type, focus_id, number, tab, origin, nonce }`. Dulu tiap layar menulis
 * pembacanya sendiri (dan ±13 layar tidak menulisnya sama sekali → tautan mendarat di daftar kosong). Kini:
 *
 *   const fokus = useFocusDoc(focusDoc, "vendor_bill", async (id) => {
 *     const r = await axios.get(`${API}/vendor-bills/${id}`); setDetail(r.data);
 *   }, onClearFocus);
 *   ...
 *   <FocusNotice {...fokus} />
 *
 * Bila `focusDoc.focus_type` termasuk `jenis` dan `focus_id` ada → `buka(focus_id, focusDoc)` dipanggil SEKALI lalu
 * `onClearFocus()`. `buka` boleh async: bila melempar galat (mis. 404 — dokumen tidak ada atau di luar PT aktif)
 * atau mengembalikan `false`, hook mengisi `pesan` "Dokumen {nomor} tidak ditemukan di PT ini." — bukan layar kosong.
 */
import { useEffect, useRef, useState } from "react";

export const pesanTidakDitemukan = (number) => `Dokumen ${number || "ini"} tidak ditemukan di PT ini.`;

/** Gulir ke baris yang disorot (dicari lewat `data-testid`) sesudah daftar digambar ulang. */
export function gulirKe(testId, tunda = 350) {
  if (typeof window === "undefined" || !testId) return;
  window.setTimeout(() => {
    const el = document.querySelector(`[data-testid="${testId}"]`);
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "center", behavior: "smooth" });
  }, tunda);
}

/** Kunci satu permintaan fokus (`nonce` membedakan klik ulang pada dokumen yang sama). */
export function kunciFokus(focusDoc, jenis) {
  const daftar = Array.isArray(jenis) ? jenis : [jenis];
  if (!focusDoc?.focus_id || !daftar.includes(focusDoc.focus_type)) return "";
  return `${focusDoc.focus_type}:${focusDoc.focus_id}:${focusDoc.nonce || ""}`;
}

export default function useFocusDoc(focusDoc, jenis, buka, onClearFocus) {
  const [pesan, setPesan] = useState("");
  const terakhir = useRef("");
  const bukaRef = useRef(buka);
  const clearRef = useRef(onClearFocus);
  bukaRef.current = buka;
  clearRef.current = onClearFocus;
  const kunci = kunciFokus(focusDoc, jenis);

  useEffect(() => {
    if (!kunci) { terakhir.current = ""; return; }
    if (terakhir.current === kunci) return;   // sekali per permintaan (termasuk efek ganda mode ketat React)
    terakhir.current = kunci;
    const fd = focusDoc;
    setPesan("");
    let hasil;
    try { hasil = bukaRef.current?.(fd.focus_id, fd); } catch (e) { hasil = Promise.reject(e); }
    Promise.resolve(hasil).then(
      (ok) => { if (ok === false) setPesan(pesanTidakDitemukan(fd.number)); },
      () => setPesan(pesanTidakDitemukan(fd.number)),
    );
    clearRef.current?.();
  }, [kunci]); // eslint-disable-line react-hooks/exhaustive-deps

  return { pesan, tutup: () => setPesan("") };
}
