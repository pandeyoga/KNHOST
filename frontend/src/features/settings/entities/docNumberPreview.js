/**
 * docNumberPreview.js — KP-T5: contoh nomor dokumen di wizard PT (langkah 3 Penomoran & Dokumen, ringkasan langkah 4).
 *
 * Contoh diambil dari tabel Penomoran Dokumen (`POST /api/doc-numbering/preview`, format grup yang berlaku, kode = isian
 * wizard, tanpa menaikkan penghitung). Tanpa akses baca pengaturan / galat → bentuk cadangan `KODE/SO-00001`.
 */
import { useEffect, useState } from "react";
import { previewDocNumbers } from "./entityApi";

/** Empat contoh langkah 3: [jenis tabel Penomoran Dokumen, label, bentuk cadangan]. */
export const PREVIEW_KINDS = [["so", "Pesanan penjualan", "SO-00001"], ["po", "Pesanan pembelian", "PO-00001"],
  ["fkt", "Faktur pajak", "FKT-00001"], ["ar", "Kwitansi", "AR-00001"]];

/** `contohNomor(kind, cadangan)` untuk kode PT `prefix`; meminta server hanya di langkah 3–4 (jeda 250 ms). */
export function useDocNumberPreview(step, prefix) {
  const [map, setMap] = useState({});
  useEffect(() => {
    if (step !== 3 && step !== 4) return undefined;
    let alive = true;
    const t = setTimeout(() => {
      Promise.resolve().then(() => previewDocNumbers(prefix || "KODE", PREVIEW_KINDS.map(([k]) => k)))
        .then((m) => { if (alive) setMap(m || {}); })
        .catch(() => { if (alive) setMap({}); });   // tanpa akses baca pengaturan: bentuk cadangan
    }, 250);
    return () => { alive = false; clearTimeout(t); };
  }, [step, prefix]);
  return (kind, cadangan) => map[kind] || `${prefix || "KODE"}/${cadangan}`;
}
