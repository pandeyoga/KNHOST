/**
 * UAT 24 Okt (P17) — muat berkas terlindung sebagai object URL lewat axios (membawa Authorization + X-Entity-Id).
 * `<img src>` / `<a href>` polos tidak membawa header badan usaha → berkas PT non-utama 403; token di URL (`?auth=`)
 * terekam di riwayat & log. Semua pratinjau lampiran memakai hook ini.
 */
import { useEffect, useState } from "react";
import axios from "axios";

const cache = new Map();   // url → { src, type }

export function kindOf(a) {
  const ct = String(a?.content_type || a?.mime || "").toLowerCase();
  const name = String(a?.filename || a?.original_filename || a?.name || "").toLowerCase();
  if (ct.startsWith("image/") || /\.(png|jpe?g|webp|gif|bmp|heic)$/.test(name)) return "image";
  if (ct.startsWith("video/") || /\.(mp4|mov|webm|m4v|3gp)$/.test(name)) return "video";
  if (ct === "application/pdf" || /\.pdf$/.test(name)) return "pdf";
  return "file";
}

export function fileNameOf(a) {
  return a?.filename || a?.original_filename || a?.name || "lampiran";
}

export async function fetchBlob(url) {
  const r = await axios.get(url, { responseType: "blob" });
  return r.data;
}

/** Unduh berkas asli (eksplisit) tanpa token di URL. */
export async function downloadFile(url, filename) {
  const blob = await fetchBlob(url);
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename || "lampiran";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 4000);
}

export function useBlobUrl(url, enabled = true) {
  const [state, setState] = useState(() => (cache.has(url) ? { src: cache.get(url).src, type: cache.get(url).type, status: "ok" }
    : { src: "", type: "", status: enabled && url ? "loading" : "idle" }));
  useEffect(() => {
    if (!enabled || !url) return undefined;
    if (cache.has(url)) { const c = cache.get(url); setState({ src: c.src, type: c.type, status: "ok" }); return undefined; }
    let alive = true;
    setState({ src: "", type: "", status: "loading" });
    fetchBlob(url)
      .then((blob) => {
        const src = URL.createObjectURL(blob);
        cache.set(url, { src, type: blob.type || "" });
        if (alive) setState({ src, type: blob.type || "", status: "ok" });
      })
      .catch(() => { if (alive) setState({ src: "", type: "", status: "error" }); });
    return () => { alive = false; };
  }, [url, enabled]);
  return state;
}
