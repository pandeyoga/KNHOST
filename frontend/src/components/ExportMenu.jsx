/**
 * ExportMenu — FIX-4 (audit WMS-RFID 9 Nov · K-B4-07 · K-B3b-04 · EXP-01/02/03) — SATU tombol baku "Unduh ▾"
 * untuk setiap daftar: **Excel (.xlsx) bawaan + CSV**, lewat mesin Pusat Export (bukan CSV buatan tiap layar).
 *
 * Aturan yang dijamin (Standar UI Gudang v1 — `docs/KN_37_STANDAR_UI_GUDANG.md` §6):
 *  1. Isi berkas = saringan & cari yang sedang aktif + cakupan pengguna (PT, lokasi kerja / bilah "Lokasi: … ▾"
 *     lewat header `X-Location-Scope` yang sudah dipasang apiClient). Izin isi tetap dari modul sumber (server).
 *  2. ≤ 50.000 baris → berkas langsung terunduh; lebih → job latar Pusat Export + notifikasi (tidak dipotong diam-diam).
 *  3. Berkas XLSX punya lembar "Ringkasan": dataset, saringan, lokasi, PT, pengguna, waktu, jumlah baris.
 *  4. Gagal = bilah `ErrorNotice` yang menempel (keputusan pemilik P5), bukan toast.
 *  5. Daftar lama yang sudah punya CSV kolom-layar (`legacyCsv`, INV-UI-07) memakai itu untuk butir CSV — satu menu,
 *     dua format, tanpa varian tombol kedua.
 *
 * Props: dataset · label (kata benda, mis. "kedatangan") · scope ("work"|"active"|"all") · filters · search
 * (teks) · sort · dateRange · entityId · locationView · columns · legacyCsv (fungsi) · disabled · testId ·
 * unsupported (teks alasan: saringan layar yang belum bisa diikuti berkas server → butir Excel/CSV server dinonaktifkan
 * dengan alasan tertulis, bukan diam-diam mengunduh data yang lebih luas dari layar).
 */
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Download, FileSpreadsheet, FileText, Loader2 } from "lucide-react";
import axios, { API } from "../services/apiClient";
import { canCurrent } from "../config/roles";
import { useEscapeClose } from "../utils/escapeLayers";
import ErrorNotice from "./ErrorNotice";
import OkNotice from "./OkNotice";
import { notifySuccess } from "../utils/feedback";
import { apiErrorText } from "../utils/apiError";
import { EXPORT_FORMATS, buildExportSpec, exportFileName, fileNameFromDisposition } from "../utils/exportSpec";

/** Isi Blob sebagai teks (Blob.text bila ada; FileReader untuk peramban/jsdom lama). */
function blobText(b) {
  if (typeof b?.text === "function") return b.text();
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result || ""));
    r.onerror = reject;
    r.readAsText(b);
  });
}

/** Galat `responseType: blob` → teks: badan JSON server dibaca dulu supaya pesannya tidak hilang. */
async function blobErrorText(e) {
  const data = e?.response?.data;
  if (data && typeof Blob !== "undefined" && data instanceof Blob) {
    try {
      const parsed = JSON.parse(await blobText(data));
      return apiErrorText({ ...e, response: { ...e.response, data: parsed } }, "Gagal menyiapkan berkas unduhan.");
    } catch { /* bukan JSON */ }
  }
  return apiErrorText(e, "Gagal menyiapkan berkas unduhan.");
}

function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ExportMenu({
  dataset, label = "data", scope = "active", filters, search, sort, dateRange, entityId, locationView = false,
  columns, legacyCsv = null, disabled = false, testId = "export", className = "", unsupported = "", requires = null,
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const lastRef = useRef(null);
  const boxRef = useRef(null);
  // `requires` = [modul, aksi] izin LIHAT dataset sumber bila berbeda dari izin layar (mis. retur antar-PT →
  // interco_finance.view) — tombol tidak ditawarkan kepada yang pasti ditolak server.
  const server = !!dataset && canCurrent("data_export", "export") && (!requires || canCurrent(requires[0], requires[1]));

  // Esc menutup lapisan TERATAS saja (INV-UI-10) — menu ini di dalam pop-up tidak ikut menutup pop-up-nya.
  useEscapeClose(open, () => setOpen(false));
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (!server && !legacyCsv) return null;

  const options = EXPORT_FORMATS.filter((f) => (f.key === "xlsx" ? server : (server || legacyCsv)));

  async function run(format) {
    setOpen(false);
    setError("");
    setNotice("");
    lastRef.current = format;
    if (format === "csv" && legacyCsv) { await legacyCsv(); return; }
    setBusy(format);
    try {
      const body = buildExportSpec({ dataset, format, label, scope, filters, search, sort, dateRange, entityId, locationView, columns });
      const res = await axios.post(`${API}/export-center/quick`, body, { responseType: "blob" });
      if (res.status === 202) {
        const info = JSON.parse(await blobText(res.data));
        setNotice(info.message || "Ekspor besar diproses di latar — unduh di Pusat Export → Pekerjaan.");
        return;
      }
      const name = fileNameFromDisposition(res.headers?.["content-disposition"]) || exportFileName(label, format);
      saveBlob(res.data, name);
      const rows = res.headers?.["x-export-rows"];
      notifySuccess(`${rows ? `${Number(rows).toLocaleString("id-ID")} baris` : "Berkas"} diunduh`,
        format === "xlsx" ? "Excel — lembar Ringkasan memuat saringan & cakupan." : "CSV titik-koma untuk Excel Indonesia.");
    } catch (e) {
      setError(await blobErrorText(e));
    } finally {
      setBusy("");
    }
  }

  const single = options.length === 1;
  const blocked = (key) => !!unsupported && !(key === "csv" && legacyCsv);
  return (
    <div className={`kn-export ${className}`} ref={boxRef} data-testid={testId}>
      <button
        type="button"
        className="secondary-button btn-sm"
        data-testid={`${testId}-button`}
        disabled={disabled || !!busy || (single && blocked(options[0].key))}
        aria-haspopup={single ? undefined : "menu"}
        aria-expanded={single ? undefined : open}
        title={single && blocked(options[0].key) ? unsupported : `Unduh ${label} — mengikuti saringan, pencarian & cakupan lokasi/PT yang aktif`}
        onClick={() => (single ? run(options[0].key) : setOpen((v) => !v))}
      >
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
        {busy ? "Menyiapkan…" : single ? `Unduh ${options[0].key === "csv" ? "CSV" : "Excel"}` : "Unduh"}
        {!single && !busy && <ChevronDown size={14} />}
      </button>
      {open && (
        <div className="kn-export-menu" role="menu" data-testid={`${testId}-menu`}>
          {options.map((f) => (
            <button key={f.key} type="button" role="menuitem" className="kn-export-item"
              data-testid={`${testId}-${f.key}`} onClick={() => run(f.key)} disabled={blocked(f.key)}
              aria-disabled={blocked(f.key) || undefined}>
              {f.key === "xlsx" ? <FileSpreadsheet size={16} /> : <FileText size={16} />}
              <span><b>{f.label}</b><small>{blocked(f.key) ? unsupported
                : f.key === "csv" && legacyCsv ? "Kolom persis seperti tabel (pilih halaman ini / semua)." : f.hint}</small></span>
            </button>
          ))}
        </div>
      )}
      {notice && <div className="kn-export-notice"><OkNotice message={notice} onDismiss={() => setNotice("")} testId={`${testId}-job`} /></div>}
      {error && (
        <div className="kn-export-notice">
          <ErrorNotice message={error} onRetry={() => run(lastRef.current || "xlsx")} onDismiss={() => setError("")} testId={`${testId}-error`} />
        </div>
      )}
    </div>
  );
}
