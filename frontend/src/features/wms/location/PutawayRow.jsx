import { useState } from "react";
import { ArrowRight, Sparkles, AlertTriangle, Check, CheckCircle2 } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { q } from "./locUtils";
import RollCheckChips from "../../../components/RollCheckChips";
import StatusBadge from "../../../components/StatusBadge";

// Satu roll di antrean: saran bin valid → cek kelayakan → tempatkan (server revalidasi) → pengecualian kapasitas.
export default function PutawayRow({ roll, binOptions, canOverride, onDone }) {
  const [bin, setBin] = useState("");
  const [sugg, setSugg] = useState(null);
  const [check, setCheck] = useState(null);
  const [err, setErr] = useState("");
  const [capFull, setCapFull] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const loadSugg = async () => {
    setErr("");
    try { setSugg((await axios.get(`${API}/inventory/putaway/suggest`, { params: { roll_id: roll.id } })).data); }
    catch (e) { setErr(apiErrorText(e, "Gagal memuat saran bin")); }
  };
  const pick = async (b) => {
    setBin(b); setCheck(null); setCapFull(false); setErr("");
    if (!b) return;
    try { setCheck((await axios.get(`${API}/inventory/putaway/evaluate`, { params: { roll_id: roll.id, bin: b } })).data); }
    catch (e) { setErr(apiErrorText(e, "Gagal memeriksa bin")); }
  };
  const place = async () => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/inventory/putaway`, { roll_id: roll.id, bin_id: bin, ...(capFull ? { override_reason: reason } : {}) });
      onDone?.();
    } catch (e) {
      setCapFull(e.response?.data?.detail?.code === "BIN_CAPACITY_FULL");
      setErr(apiErrorText(e, "Gagal menempatkan roll"));
    } finally { setBusy(false); }
  };

  // Pola UI (pemilik 16 Nov — M29): satu baris tabel berkolom — Roll · Barang & cek · Bin tujuan · Aksi — dengan
  // saran/cek/galat di baris bawahnya (dulu kartu abu bertumpuk dengan tombol buatan sendiri).
  return (
    <div data-testid={`lp-queue-${roll.id}`} className="kn-putaway-row">
      <div className="kn-putaway-roll">
        {roll.roll_no}
        <span className="block font-mono text-fs-12 font-normal text-kn-text-2">{roll.sku}</span>
      </div>
      <div className="min-w-0">
        <p className="truncate text-kn-neutral" title={roll.product_name}>
          {roll.product_name} — {q(roll.length_remaining)} {roll.unit} · Lot {roll.lot || "-"} · Grade {roll.grade || "A"}
        </p>
        <RollCheckChips roll={roll} testId={`putaway-check-${roll.id}`} />
        {roll.blocked_reason && (
          <StatusBadge tone={roll.ready ? "info" : "warning"} icon="alert" className="mt-0.5" testId={`lp-queue-blocked-${roll.id}`}>
            {roll.ready ? "" : "Terhambat: "}{roll.blocked_reason}
          </StatusBadge>
        )}
      </div>
      <div className="kn-putaway-bin">
        <div className="min-w-0 flex-1">
          <KNSelect data-testid={`lp-bin-select-${roll.id}`} value={bin} onValueChange={pick} options={binOptions}
            aria-label={`Bin tujuan ${roll.roll_no}`} className="field w-full" placeholder="Pilih / scan bin…" />
        </div>
        <button type="button" data-testid={`lp-suggest-${roll.id}`} onClick={loadSugg} disabled={!roll.ready}
          className="secondary-button btn-sm" title="Saran bin yang lolos aturan & kapasitas">
          <Sparkles size={14} /> Saran
        </button>
      </div>
      <div className="flex justify-end">
        <button type="button" data-testid={`lp-assign-${roll.id}`} disabled={!bin || busy || !roll.ready || (check && check.blocks?.length > 0)}
          onClick={place} className="primary-button btn-sm">
          Tempatkan <ArrowRight size={14} />
        </button>
      </div>
      <div className="kn-putaway-extra">
        {sugg && (
          <div data-testid={`lp-suggestions-${roll.id}`} className="flex flex-wrap items-center gap-1">
            <span>{sugg.valid_count} bin sah:</span>
            {sugg.suggestions.length === 0 && <span className="text-kn-warning-text">{(sugg.warehouse_blocks || [])[0] || "tidak ada bin yang lolos aturan/kapasitas"}</span>}
            {sugg.suggestions.map((s) => (
              <button type="button" key={s.bin_id} data-testid={`lp-suggestion-${roll.id}-${s.bin_code}`} onClick={() => pick(s.bin_id)}
                title={`${s.path} — ${s.reason}`} aria-pressed={bin === s.bin_id} className="secondary-button btn-sm">
                {bin === s.bin_id && <Check size={14} aria-hidden="true" />}
                <span className="font-mono">{s.bin_code}</span> · {s.reason}{s.capacity_rolls ? ` · sisa ${s.free_rolls}` : ""}
              </button>
            ))}
          </div>
        )}
        {check && <CheckLine check={check} rollId={roll.id} />}
        {err && <p data-testid={`lp-queue-error-${roll.id}`} className="font-semibold text-kn-danger-text">{err}</p>}
        {capFull && canOverride && (
          <div className="flex flex-wrap items-center gap-1.5" data-testid={`lp-override-${roll.id}`}>
            <input value={reason} onChange={(e) => setReason(e.target.value)} data-testid={`lp-override-reason-${roll.id}`}
              aria-label="Alasan pengecualian kapasitas" placeholder="Alasan pengecualian kapasitas (wajib, tercatat)"
              className="field min-w-[220px] flex-1" />
            <button type="button" data-testid={`lp-override-submit-${roll.id}`} disabled={reason.trim().length < 5 || busy} onClick={place}
              className="danger-button btn-sm">Tempatkan dengan pengecualian</button>
          </div>
        )}
      </div>
    </div>
  );
}

function CheckLine({ check, rollId }) {
  const c = check.capacity || {};
  const capTxt = c.limit ? `${c.count}/${c.limit} roll${c.over ? " — penuh" : ""}` : "kapasitas belum diatur";
  if (check.blocks?.length) {
    return <p data-testid={`lp-check-${rollId}`} className="text-kn-danger-text"><AlertTriangle size={12} className="inline" /> {check.blocks.join(" · ")}</p>;
  }
  return (
    <p data-testid={`lp-check-${rollId}`} className={c.over ? "text-kn-warning-text" : "text-kn-success-text"}>
      <CheckCircle2 size={12} className="inline" /> {check.path} · {capTxt}
    </p>
  );
}
