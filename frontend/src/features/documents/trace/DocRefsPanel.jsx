/**
 * DocRefsPanel — FASE G-4 · panel **Dokumen Terkait** untuk layar detail.
 *
 * Dipasang di detail SO / PO / Tagihan Pemasok / Kontrabon / Penerimaan Barang.
 * Menjawab pertanyaan yang dulu harus dijawab manual: "surat ini berasal dari mana,
 * dan surat apa saja yang lahir darinya?" — plus satu klik ke **Jejak Dokumen**
 * untuk melihat seluruh rantainya.
 *
 * PK-44 (IA-13) — SATU-SATUNYA panel relasi di detail dokumen (dulu tiga: cetak, linimasa proses, referensi).
 * Sumber daftar: `GET /documents/refs/...` (referensi tersimpan + jurnal/kas turunan); tujuan tombol **Buka** dari peta
 * yang sama dengan Jejak Dokumen (`doc_refs_service.link_of`). `withStages` (pesanan & PO) menampilkan garis tahapan
 * (`ProcessTimeline`, tanpa daftar/tautan) di bilah tersendiri di bawah judul. `onOpenDocument` dari layar induk;
 * tanpa itu dipakai jalur navigasi bersama (`AppNavContext`) bila panel berada di dalam aplikasi desktop.
 */
import { useCallback, useEffect, useState } from "react";
import { ExternalLink, GitBranch, Loader2, Lock, RefreshCw, Route } from "lucide-react";
import { canOpenNode, errText, fetchRefs, relFamily } from "./traceApi";
import { openTrace } from "./traceDeepLink";
import { docStatusLabel } from "../../../utils/docStatus";
import { useAppNav } from "../../../context/AppNavContext";
import ErrorNotice from "../../../components/ErrorNotice";
import ProcessTimeline from "../ProcessTimeline";

/** Nada relasi → kelas token (bukan hex): asal-usul = aksi, turunan = berhasil, koreksi = bahaya. */
const REL_CLASS = {
  upstream: "bg-kn-action-soft text-kn-action",
  downstream: "bg-kn-success-soft text-kn-success-text",
  correction: "bg-kn-danger-soft text-kn-danger-text",
};
const STAGE_TYPES = ["sales_order", "purchase_order"];

export default function DocRefsPanel({ docType, docId, onOpenDocument, compact = false, withStages = false }) {
  const nav = useAppNav();
  const open = onOpenDocument || (nav.role ? nav.openDocument : null);
  const [rows, setRows] = useState([]);
  const [number, setNumber] = useState("");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    if (!docType || !docId) return;
    setLoading(true);
    try {
      const res = await fetchRefs(docType, docId);
      setRows(res.refs || []);
      setNumber(res.number || "");
      setErr("");
    } catch (e) {
      setErr(errText(e, "Gagal memuat dokumen terkait."));
      setRows([]);
    } finally { setLoading(false); }
  }, [docType, docId]);

  useEffect(() => { load(); }, [load]);

  const upstream = rows.filter((r) => relFamily(r.rel) !== "downstream");
  const downstream = rows.filter((r) => relFamily(r.rel) === "downstream");

  // 23 Okt — fungsi render (bukan komponen di dalam render): tombol "Buka" tidak dibuat ulang tiap render.
  const renderRow = (r) => (
    <div key={`${r.rel}-${r.doc_id}`} data-testid={`docrefs-row-${r.doc_id}`}
      className="flex items-center justify-between gap-2 rounded-md border border-kn-divider bg-white px-2 py-1.5">
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-1.5">
          <span className={`shrink-0 rounded px-1.5 py-0.5 text-fs-12 font-semibold ${REL_CLASS[relFamily(r.rel)]}`}>
            {r.rel_label || r.rel}
          </span>
          {/* G5-51 — id teknis tidak ditampilkan bila dokumen tak bernomor; status berlabel. */}
          <span className="truncate text-fs-13 font-bold text-kn-text" title={r.doc_number ? undefined : r.doc_id}>
            {r.doc_number || "(tanpa nomor)"}
          </span>
        </div>
        <p className="truncate text-fs-12 text-kn-text-2">
          {r.label}{r.status ? ` · ${docStatusLabel(r.status)}` : ""}{r.alive === false ? " · dokumen sudah tidak ada" : ""}
          {r.note ? ` · ${r.note}` : ""}
        </p>
      </div>
      {r.link?.view && open && r.alive !== false && (canOpenNode(r) ? (
        <button type="button" className="secondary-button btn-sm shrink-0" data-testid={`docrefs-open-${r.doc_id}`}
          onClick={() => open(r.link)}>
          <ExternalLink size={12} aria-hidden="true" /> Buka
        </button>
      ) : (
        /* PK-17 (K-18) — dokumen yang modulnya di luar izin peran: alasannya ditulis, bukan tombol mati bertooltip. */
        <span className="flex shrink-0 items-center gap-1 text-fs-12 text-kn-text-2" data-testid={`docrefs-noaccess-${r.doc_id}`}>
          <Lock size={12} aria-hidden="true" /> Tanpa akses lihat
        </span>
      ))}
    </div>
  );

  return (
    <div data-testid="doc-refs-panel" className="rounded-lg border border-kn-divider bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-fs-13 font-bold text-kn-text">
          <GitBranch size={14} className="text-kn-action" aria-hidden="true" /> Dokumen Terkait
          {rows.length > 0 && (
            <span className="rounded-full bg-kn-action-soft px-1.5 text-fs-12 font-bold text-kn-action" data-testid="docrefs-count">
              {rows.length}
            </span>
          )}
        </p>
        <div className="flex items-center gap-1.5">
          <button type="button" className="icon-button" title="Muat ulang" aria-label="Muat ulang dokumen terkait"
            data-testid="docrefs-refresh" onClick={load}>
            {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          </button>
          <button type="button" className="secondary-button btn-sm" data-testid="docrefs-open-trace"
            onClick={() => openTrace({ docType, docId, number })}>
            <Route size={12} aria-hidden="true" /> Lihat seluruh jejak
          </button>
        </div>
      </div>

      {withStages && STAGE_TYPES.includes(docType) && (
        <div className="mt-2 border-t border-kn-divider pt-2">
          <ProcessTimeline docType={docType} docId={docId} />
        </div>
      )}

      <div className="mt-2">
        {loading && (
          <p className="animate-pulse py-3 text-center text-fs-12 text-kn-text-2">Memuat dokumen terkait…</p>
        )}

        {!loading && err && <ErrorNotice message={err} onRetry={load} testId="docrefs-error" />}

        {!loading && !err && rows.length === 0 && (
          <p data-testid="docrefs-empty" className="py-2 text-fs-12 text-kn-text-2">
            Belum ada surat lain yang tertaut ke dokumen ini.
          </p>
        )}

        {!loading && !err && rows.length > 0 && (
          <div className="space-y-2">
            {upstream.length > 0 && (
              <div className="space-y-1">
                {!compact && <p className="text-fs-12 font-bold text-kn-text-2">Berasal dari</p>}
                {upstream.map((r) => renderRow(r))}
              </div>
            )}
            {downstream.length > 0 && (
              <div className="space-y-1">
                {!compact && <p className="text-fs-12 font-bold text-kn-text-2">Menurunkan</p>}
                {downstream.map((r) => renderRow(r))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
