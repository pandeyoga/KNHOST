/**
 * UAT 24 Okt — P3.2 cetak SURAT PERINTAH KERJA sampel per supplier peserta (PDF memuat warna + Pantone /
 * konstruksi / gambar pattern PNG cetak), dan P4.3 kelompok labdip multi-warna (saudara per warna + kirim semua).
 */
import { useEffect, useState } from "react";
import { FileText, Layers } from "lucide-react";
import axios, { API } from "../../services/apiClient";

export async function openWorkOrder(sampleId, supplierId) {
  const r = await axios.get(`${API}/pdf/render/md_sample_work_order/${sampleId}`,
    { params: { supplier_id: supplierId, download: false }, responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export default function SampleWorkOrderBox({ sample, onOpenSample, onSendBatch, canSubmit, onError }) {
  const parts = sample.participants || [];
  const [siblings, setSiblings] = useState([]);
  useEffect(() => {
    if (!sample.color_batch_id) { setSiblings([]); return; }
    axios.get(`${API}/rnd/samples`, { params: { color_batch_id: sample.color_batch_id, limit: 50 } })
      .then((r) => setSiblings((r.data?.items || []).sort((a, b) => (a.color_batch_index || 0) - (b.color_batch_index || 0))))
      .catch(() => setSiblings([]));
  }, [sample.color_batch_id, sample.id, sample.status]);
  const print = async (sid) => {
    try { await openWorkOrder(sample.id, sid); } catch (e) { onError?.(e?.response?.status === 403 ? "Anda tidak berhak mencetak dokumen." : "Gagal membuat surat perintah."); }
  };
  return (
    <div className="grid gap-2">
      {parts.length > 0 && (
        <div className="rounded-lg border border-[#EFF0F2] p-2.5" data-testid="sample-work-orders">
          <p className="mb-1 flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]"><FileText size={11} /> Surat perintah kerja</p>
          <div className="grid gap-1">
            {parts.map((p) => (
              <button key={p.supplier_id} type="button" className="secondary-button !h-8 justify-start text-[11px]"
                data-testid={`sample-wo-print-${p.supplier_id}`} onClick={() => print(p.supplier_id)}>
                Cetak untuk {p.supplier_name}
              </button>
            ))}
          </div>
        </div>
      )}
      {sample.color_batch_id && (
        <div className="rounded-lg border border-[#E5DDF3] bg-[#FAF7FF] p-2.5" data-testid="sample-color-batch">
          <p className="mb-1 flex items-center gap-1 text-[10.5px] font-bold uppercase tracking-wide text-[#6B219A]">
            <Layers size={11} /> Labdip multi-warna · warna {sample.color_batch_index} dari {sample.color_batch_size}
          </p>
          <div className="grid gap-1">
            {siblings.map((s) => (
              <button key={s.id} type="button" disabled={s.id === sample.id} data-testid={`sample-batch-${s.id}`}
                onClick={() => onOpenSample?.(s.id)}
                className={`flex items-center gap-2 rounded px-2 py-1 text-left text-[11px] ${s.id === sample.id ? "bg-white font-bold" : "hover:bg-white"}`}>
                <span className="inline-block h-3 w-3 shrink-0 rounded-full border border-[#D9D9DE]" style={{ background: s.color_target?.hex || "#fff" }} />
                <span className="min-w-0 flex-1 truncate">{s.number} · {s.color_target?.name || "—"}{s.color_target?.pantone_code ? ` · ${s.color_target.pantone_code}` : ""}</span>
                <span className="text-[10px] text-[#6B6B73]">{s.status === "decided" ? `pemenang: ${s.decision?.supplier_name || "—"}` : s.status}</span>
              </button>
            ))}
          </div>
          {canSubmit && onSendBatch && siblings.some((s) => ["draft", "sent", "in_progress"].includes(s.status)) && (
            <button type="button" className="secondary-button mt-1.5 !h-8 w-full text-[11px]" data-testid="sample-batch-send" onClick={onSendBatch}>
              Kirim SEMUA warna ke supplier
            </button>
          )}
        </div>
      )}
    </div>
  );
}
