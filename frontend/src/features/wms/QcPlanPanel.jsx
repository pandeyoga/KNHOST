import { useEffect, useState } from "react";
import { ListChecks, Percent } from "lucide-react";
import axios, { API } from "../../services/apiClient";

// PG01 — pilihan rencana inspeksi: "Cek semua" (default) atau "Sampling" + cakupan tercatat.
export default function QcPlanPanel({ taskId, onCoverage, onOpenRolls }) {
  const [cov, setCov] = useState(null);
  const [mode, setMode] = useState("all");
  const [pct, setPct] = useState("10");
  const [min, setMin] = useState("1");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const apply = (c) => { setCov(c); onCoverage?.(c); };
  useEffect(() => {
    axios.get(`${API}/inbound/qc/tasks/${taskId}/plan`).then((r) => {
      apply(r.data); setMode(r.data.mode || "all");
      if (r.data.sample_pct) setPct(String(r.data.sample_pct));
      if (r.data.sample_min) setMin(String(r.data.sample_min));
    }).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat rencana QC"));
  }, [taskId]); // eslint-disable-line

  const save = async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.put(`${API}/inbound/qc/tasks/${taskId}/plan`,
        { mode, sample_pct: Number(pct) || 0, sample_min: Number(min) || 0 });
      apply(r.data);
    } catch (e) { setErr(e.response?.data?.detail || "Gagal menyimpan rencana QC"); } finally { setBusy(false); }
  };

  const dirty = cov && (mode !== cov.mode || (mode === "sampling"
    && (Number(pct) !== Number(cov.sample_pct) || Number(min) !== Number(cov.sample_min))));
  const opt = (v, label, Icon) => (
    <button type="button" data-testid={`qc-plan-mode-${v}`} onClick={() => setMode(v)}
      className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-[12px] font-semibold transition-colors ${mode === v ? "border-[#0058CC] bg-[#EEF4FF] text-[#0058CC]" : "border-[#EFF0F2] text-[#3C3C43] hover:bg-[#F7F8FA]"}`}>
      <Icon size={13} /> {label}
    </button>
  );

  return (
    <div className="grid gap-2 rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-3" data-testid="qc-plan-panel">
      <span className="text-[11px] font-bold uppercase text-[#6B6B73]">Rencana inspeksi</span>
      <div className="flex gap-2">{opt("all", "Cek semua", ListChecks)}{opt("sampling", "Sampling", Percent)}</div>
      {mode === "sampling" && (
        <div className="grid grid-cols-2 gap-2">
          <label className="grid gap-1 text-[11px] text-[#6B6B73]">% roll per lot
            <input data-testid="qc-plan-pct" type="number" min="1" max="100" className="form-input" value={pct} onChange={(e) => setPct(e.target.value)} />
          </label>
          <label className="grid gap-1 text-[11px] text-[#6B6B73]">Minimal roll
            <input data-testid="qc-plan-min" type="number" min="1" className="form-input" value={min} onChange={(e) => setMin(e.target.value)} />
          </label>
        </div>
      )}
      {dirty && (
        <button data-testid="qc-plan-save" className="btn-secondary btn-sm" onClick={save} disabled={busy}>
          {busy ? "Menyimpan…" : "Simpan rencana"}
        </button>
      )}
      {cov && (
        <div className="flex items-center justify-between gap-2 text-[12px]" data-testid="qc-plan-coverage">
          <span>
            Terinspeksi <b data-testid="qc-plan-inspected">{cov.inspected_rolls}</b>/{cov.total_rolls} roll · wajib{" "}
            <b data-testid="qc-plan-required">{cov.required_rolls}</b>
            {cov.mode === "sampling" && cov.met && cov.inspected_rolls < cov.total_rolls
              ? " · keputusan sampel berlaku untuk sisa lot" : ""}
          </span>
          <span data-testid="qc-plan-met" className={`rounded-full px-2 py-0.5 text-[10.5px] font-bold ${cov.met ? "bg-[#E7F7EC] text-[#1B7E3B]" : "bg-[#FFF1E0] text-[#8C4A00]"}`}>
            {cov.met ? "Cakupan terpenuhi" : "Belum terpenuhi"}
          </span>
        </div>
      )}
      {cov && (
        <button data-testid="qc-plan-open-rolls" className="btn-secondary btn-sm" onClick={onOpenRolls}>
          {cov.met ? "Lihat roll (inspeksi · tahan / lepas tahan)" : "Inspeksi roll (4-Point / grade manual)"}
        </button>
      )}
      {err && <p className="text-[11.5px] text-[#C0341D]" data-testid="qc-plan-error">{err}</p>}
    </div>
  );
}
