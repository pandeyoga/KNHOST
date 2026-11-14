import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronRight, Circle, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";

/**
 * EPIC6 — ProcessTimeline · GARIS TAHAPAN dokumen (pesanan / PO).
 *
 * Sumber: GET /api/documents/relations/{docType}/{docId} (`docType`: "sales_order" | "purchase_order").
 *
 * PK-44 (IA-13) — dulu panel kedua berisi daftar & tautan dokumen dengan peta tujuan tulis-tangan, berdampingan
 * dengan panel referensi tersimpan. Kini hanya garis tahapan (sudah ada / belum, berapa dokumen) yang dipasang di
 * kepala panel **Dokumen Terkait** (`trace/DocRefsPanel` `withStages`); daftar & tombol Buka = panel itu saja.
 * Tahap = ikon + teks + warna (bukan warna saja).
 */
export default function ProcessTimeline({ docType, docId }) {
  const [state, setState] = useState({ loading: true, error: "", stages: [] });

  const load = useCallback(() => {
    if (!docType || !docId) return () => {};
    let active = true;
    setState({ loading: true, error: "", stages: [] });
    axios.get(`${API}/documents/relations/${docType}/${docId}`)
      .then((r) => { if (active) setState({ loading: false, error: "", stages: r.data?.stages || [] }); })
      .catch((e) => {
        if (active) setState({ loading: false, error: e.response?.data?.detail || "Tahapan dokumen tidak bisa dimuat.", stages: [] });
      });
    return () => { active = false; };
  }, [docType, docId]);

  useEffect(() => load(), [load]);

  const { loading, error, stages } = state;
  if (loading) {
    return <p data-testid="process-timeline-loading" className="animate-pulse text-fs-12 text-kn-text-2">Memuat tahapan…</p>;
  }
  if (error) {
    return (
      <div data-testid="process-timeline-error" className="flex flex-wrap items-center gap-2 text-fs-12 text-kn-text-2">
        <span>{error}</span>
        <button type="button" className="link-button" onClick={load} data-testid="process-timeline-retry">
          <RefreshCw size={12} aria-hidden="true" /> Coba lagi
        </button>
      </div>
    );
  }
  return (
    <ol data-testid="process-timeline" aria-label="Tahapan dokumen" className="flex flex-wrap items-center gap-x-1 gap-y-1">
      {stages.map((stage, i) => {
        const n = (stage.docs || []).length;
        return (
          <li key={stage.key} data-testid={`process-stage-${stage.key}`} className="flex items-center gap-1">
            {i > 0 && <ChevronRight size={12} className="text-kn-text-2" aria-hidden="true" />}
            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-fs-12 font-semibold ${n
              ? "bg-kn-success-soft text-kn-success-text" : "bg-kn-neutral-soft text-kn-text-2"}`}
              title={n ? undefined : stage.empty_hint || ""}>
              {n ? <CheckCircle2 size={12} aria-hidden="true" /> : <Circle size={12} aria-hidden="true" />}
              {stage.label}
              <span data-testid={`process-stage-count-${stage.key}`}>{n ? `· ${n}` : "· belum"}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
