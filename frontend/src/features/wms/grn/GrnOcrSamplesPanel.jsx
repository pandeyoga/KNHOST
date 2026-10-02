import { useCallback, useEffect, useState } from "react";
import { FlaskConical, GraduationCap, Pencil, Play, Trash2 } from "lucide-react";
import { askConfirm } from "../../../services/confirmService";
import { ErrorBox } from "./GrnBits";
import GrnOcrRunReport from "./GrnOcrRunReport";
import GrnOcrSampleEditor from "./GrnOcrSampleEditor";
import { errText, sampleApi } from "./grnApi";

const TARGET = 20;

function Thumb({ id }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let obj = "";
    sampleApi.fileBlob(id, 1).then((b) => { obj = URL.createObjectURL(b); setUrl(obj); }).catch(() => {});
    return () => { if (obj) URL.revokeObjectURL(obj); };
  }, [id]);
  return url ? <img src={url} alt="" className="h-16 w-16 rounded-lg object-cover" /> : <span className="h-16 w-16 rounded-lg bg-[#F2F2F7]" />;
}

function SampleCard({ s, checked, onCheck, onEdit, onDelete }) {
  const a = s.answer || {};
  const n = (a.lines || []).filter((l) => !l.is_non_stock).length;
  const r = s.last_result;
  return (
    <div data-testid={`ocr-sample-${s.id}`} className={`flex min-w-0 gap-3 rounded-xl border bg-white p-2.5 ${checked ? "border-[#0058CC]" : "border-[#EFF0F2]"}`}>
      <input type="checkbox" data-testid={`ocr-sample-check-${s.id}`} checked={checked} onChange={onCheck} className="mt-1" />
      <Thumb id={s.id} />
      <div className="min-w-0 flex-1 text-[11px]">
        <p className="truncate font-semibold">{s.label}</p>
        <p className="truncate text-[10.5px] text-[#6B6B73]">SJ <span className="font-mono">{a.dn_number || "—"}</span> · {a.dn_date || "tanpa tanggal"} · {n} baris{s.source_grn_number ? ` · dari ${s.source_grn_number}` : ""}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          {r && <span data-testid={`ocr-sample-last-${s.id}`} className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${r.ok === r.total ? "bg-[#E7F6F3] text-[#0F766E]" : "bg-[#FFF6E5] text-[#B26A00]"}`}>terakhir {r.ok}/{r.total} benar</span>}
          <button data-testid={`ocr-sample-edit-${s.id}`} onClick={onEdit} className="inline-flex items-center gap-1 font-semibold text-[#0058CC]"><Pencil size={11} /> Jawaban</button>
          <button data-testid={`ocr-sample-delete-${s.id}`} onClick={onDelete} className="inline-flex items-center gap-1 font-semibold text-[#B4231F]"><Trash2 size={11} /> Hapus</button>
        </div>
      </div>
    </div>
  );
}

/** Sampel Uji OCR: SJ nyata + kunci jawaban → ukur ketepatan baca AI sebelum dipakai harian. */
export default function GrnOcrSamplesPanel() {
  const [samples, setSamples] = useState([]);
  const [sel, setSel] = useState([]);
  const [run, setRun] = useState(null);
  const [edit, setEdit] = useState(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => Promise.all([sampleApi.list(), sampleApi.runs()]).then(([s, runs]) => {
    setSamples(s);
    if (runs[0]) sampleApi.run(runs[0].id).then(setRun);
  }).catch((e) => setErr(errText(e))), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (run?.status !== "running") return undefined;
    const t = setInterval(() => sampleApi.run(run.id).then((r) => { setRun(r); if (r.status !== "running") sampleApi.list().then(setSamples); }).catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [run?.status, run?.id]);
  const start = async () => { setErr(""); try { setRun(await sampleApi.startRun(sel)); } catch (e) { setErr(errText(e)); } };
  const remove = async (s) => {
    if (!(await askConfirm({ title: "Hapus sampel?", message: `"${s.label}" tidak ikut diuji lagi. Foto di kedatangan asal tetap ada.`, confirmLabel: "Hapus" }))) return;
    try { await sampleApi.del(s.id); setSamples((xs) => xs.filter((x) => x.id !== s.id)); setSel((xs) => xs.filter((x) => x !== s.id)); } catch (e) { setErr(errText(e)); }
  };
  const busy = run?.status === "running";
  return (
    <div className="space-y-3" data-testid="ocr-samples-panel">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-[#EFF0F2] bg-white p-3">
        <div className="max-w-2xl space-y-1 text-[11px] text-[#3C3C43]">
          <p className="flex items-center gap-1.5 text-[12.5px] font-bold text-[#1C1C1E]"><FlaskConical size={14} /> Sampel Uji OCR</p>
          <p>Kumpulan surat jalan nyata beserta jawaban yang benar. Jalankan uji untuk mengukur ketepatan baca sebelum dipakai harian. Target: nomor SJ ≥ 98%, qty & satuan ≥ 95%.</p>
          <p className="text-[#0F766E]"><GraduationCap size={12} className="mr-1 inline -mt-0.5" />Tambah sampel dari kedatangan yang sudah dicek (tombol <b>Jadikan sampel uji</b>) — koreksi Anda sekaligus menjadi petunjuk AI untuk SJ mitra yang sama.</p>
          <div className="flex items-center gap-2 pt-1">
            <div className="h-1.5 w-40 overflow-hidden rounded-full bg-[#EFF0F2]"><div className="h-full rounded-full bg-[#0058CC]" style={{ width: `${Math.min(100, (samples.length / TARGET) * 100)}%` }} /></div>
            <span data-testid="ocr-samples-count" className="text-[10.5px] font-semibold">{samples.length}/{TARGET} sampel disarankan</span>
          </div>
        </div>
        <button data-testid="ocr-samples-run" className="primary-button max-sm:w-full max-sm:justify-center" disabled={busy || !samples.length} onClick={start}>
          <Play size={13} /> {sel.length ? `Uji ${sel.length} sampel terpilih` : "Uji semua sampel"}
        </button>
      </div>
      <ErrorBox text={err} />
      {run && <GrnOcrRunReport run={run} />}
      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        {samples.map((s) => <SampleCard key={s.id} s={s} checked={sel.includes(s.id)} onCheck={() => setSel((xs) => (xs.includes(s.id) ? xs.filter((x) => x !== s.id) : [...xs, s.id]))}
          onEdit={() => setEdit(s)} onDelete={() => remove(s)} />)}
      </div>
      {!samples.length && <p data-testid="ocr-samples-empty" className="text-[11px] text-[#6B6B73]">Belum ada sampel di badan usaha ini.</p>}
      {edit && <GrnOcrSampleEditor sample={edit} onClose={() => setEdit(null)} onSaved={(s) => { setSamples((xs) => xs.map((x) => (x.id === s.id ? s : x))); setEdit(null); }} />}
    </div>
  );
}
