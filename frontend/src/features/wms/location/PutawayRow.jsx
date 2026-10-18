import { useState } from "react";
import { ArrowRight, Sparkles, AlertTriangle, CheckCircle2 } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { q } from "./locUtils";

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

  return (
    <div data-testid={`lp-queue-${roll.id}`} className="rounded-lg bg-[#FAFAFB] p-2 space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex-1 min-w-[200px]">
          <p className="text-[12px] font-semibold">{roll.roll_no} · {roll.sku}</p>
          <p className="text-[11px] text-[#6B6B73]">{roll.product_name} — {q(roll.length_remaining)} {roll.unit} · Lot {roll.lot || "-"} · Grade {roll.grade || "A"}</p>
          {roll.blocked_reason && (
            <p data-testid={`lp-queue-blocked-${roll.id}`} className={`mt-0.5 inline-flex items-center gap-1 rounded px-1.5 text-[10.5px] font-semibold ${roll.ready ? "bg-[#EEF4FF] text-[#0058CC]" : "bg-[#FFF4E5] text-[#B45309]"}`}>
              <AlertTriangle size={11} /> {roll.ready ? "" : "Terhambat: "}{roll.blocked_reason}
            </p>
          )}
        </div>
        <button data-testid={`lp-suggest-${roll.id}`} onClick={loadSugg} disabled={!roll.ready}
          className="flex items-center gap-1 rounded-lg border border-[#D6E4FA] bg-white px-2.5 py-1.5 text-[11.5px] font-semibold text-[#0058CC] hover:bg-[#EEF4FF] disabled:opacity-40 transition-colors">
          <Sparkles size={13} /> Saran bin
        </button>
        <KNSelect data-testid={`lp-bin-select-${roll.id}`} value={bin} onValueChange={pick} options={binOptions}
          className="field !py-1 !px-2 text-[12px] w-60" placeholder="Pilih / scan bin…" />
        <button data-testid={`lp-assign-${roll.id}`} disabled={!bin || busy || !roll.ready || (check && check.blocks?.length > 0)} onClick={place}
          className="flex items-center gap-1 rounded-lg bg-[#0058CC] text-white px-3 py-1.5 text-[12px] font-semibold disabled:opacity-40 transition-opacity">
          Tempatkan <ArrowRight size={13} />
        </button>
      </div>
      {sugg && (
        <div data-testid={`lp-suggestions-${roll.id}`} className="flex flex-wrap items-center gap-1 text-[11px]">
          <span className="text-[#6B6B73]">{sugg.valid_count} bin sah:</span>
          {sugg.suggestions.length === 0 && <span className="text-[#B45309]">{(sugg.warehouse_blocks || [])[0] || "tidak ada bin yang lolos aturan/kapasitas"}</span>}
          {sugg.suggestions.map((s) => (
            <button key={s.bin_id} data-testid={`lp-suggestion-${roll.id}-${s.bin_code}`} onClick={() => pick(s.bin_id)} title={`${s.path} — ${s.reason}`}
              className={`rounded-full border px-2 py-0.5 font-mono transition-colors ${bin === s.bin_id ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#D6E4FA] bg-white hover:bg-[#EEF4FF]"}`}>
              {s.bin_code} <span className="font-sans opacity-70">· {s.reason}{s.capacity_rolls ? ` · sisa ${s.free_rolls}` : ""}</span>
            </button>
          ))}
        </div>
      )}
      {check && <CheckLine check={check} rollId={roll.id} />}
      {err && <p data-testid={`lp-queue-error-${roll.id}`} className="text-[11px] font-semibold text-[#C0341D]">{err}</p>}
      {capFull && canOverride && (
        <div className="flex items-center gap-1.5" data-testid={`lp-override-${roll.id}`}>
          <input value={reason} onChange={(e) => setReason(e.target.value)} data-testid={`lp-override-reason-${roll.id}`}
            placeholder="Alasan pengecualian kapasitas (wajib, tercatat)" className="flex-1 rounded-md border border-[#F5C26B] px-2 py-1 text-[11px]" />
          <button data-testid={`lp-override-submit-${roll.id}`} disabled={reason.trim().length < 5 || busy} onClick={place}
            className="rounded-md bg-[#B45309] px-2.5 py-1 text-[11px] font-semibold text-white disabled:opacity-40">Tempatkan dengan pengecualian</button>
        </div>
      )}
    </div>
  );
}

function CheckLine({ check, rollId }) {
  const c = check.capacity || {};
  const capTxt = c.limit ? `${c.count}/${c.limit} roll${c.over ? " — penuh" : ""}` : "kapasitas belum diatur";
  if (check.blocks?.length) {
    return <p data-testid={`lp-check-${rollId}`} className="text-[11px] text-[#C0341D]"><AlertTriangle size={11} className="inline" /> {check.blocks.join(" · ")}</p>;
  }
  return (
    <p data-testid={`lp-check-${rollId}`} className={`text-[11px] ${c.over ? "text-[#B45309]" : "text-[#1B7E3B]"}`}>
      <CheckCircle2 size={11} className="inline" /> {check.path} · {capTxt}
    </p>
  );
}
