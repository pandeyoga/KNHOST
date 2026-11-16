// MP-T4a (K-62, K-66, K-67, K-69) — MD mencatat kain hasil langkah ini dikirim LANGSUNG dari mitranya ke mitra langkah
// berikut. Server: terima hasil langkah ini + kirim roll yang sama ke langkah berikut (jurnal yang sudah ada, saling
// menetralkan). Rincian roll boleh kosong — mitra yang hanya melapor jumlah (K-67) dicatat sebagai satu roll gabungan.
import { useState } from "react";
import { Plus, Send, Trash2 } from "lucide-react";
import FormModal from "../../../components/FormModal";
import axios, { API } from "../../../services/apiClient";

export default function MkoForwardModal({ mkoId, step, next, onClose, onDone }) {
  const [qty, setQty] = useState("");
  const [rolls, setRolls] = useState([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const unit = step.output_unit || step.input_unit || "";
  const sum = rolls.reduce((a, r) => a + (parseFloat(r.length) || 0), 0);
  const submit = async () => {
    setErr("");
    const q = parseFloat(qty);
    if (!(q > 0)) { setErr("Isi jumlah kain yang diteruskan."); return; }
    if (rolls.length && Math.abs(sum - q) > 0.5) { setErr(`Total panjang roll (${sum}) belum sama dengan jumlah (${q}).`); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/makloon-orders/${mkoId}/steps/${step.seq}/forward`, {
        actual_output_qty: q, note,
        rolls: rolls.filter((r) => parseFloat(r.length) > 0).map((r) => ({ length: parseFloat(r.length), lot: r.lot || "", grade: r.grade || "A" })),
      });
      onDone?.();
    } catch (e) {
      const d = e.response?.data?.detail;
      setErr(typeof d === "string" ? d : "Kain gagal diteruskan.");
    } finally { setBusy(false); }
  };
  return (
    <FormModal open onClose={onClose} size="md" icon={Send} testId="mko-forward-modal" busy={busy} error={err}
      title={`Teruskan ke ${next.makloon_name || `mitra langkah ${next.seq}`}`}
      subtitle={`Hasil langkah ${step.seq} (${step.stage_label || step.process_type}) dikirim langsung dari ${step.makloon_name || "mitra"} — tidak masuk gudang.`}
      onSubmit={submit} submitLabel="Teruskan" submitTestId="mko-forward-confirm">
      <div className="grid gap-3">
        <label className="text-fs-12 font-semibold">Jumlah diteruskan ({unit}) *
          <input className="field mt-1" data-testid="mko-forward-qty" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="mis. 190" />
        </label>
        <div>
          <p className="text-fs-12 font-semibold">Rincian roll dari surat jalan mitra (boleh kosong bila mitra hanya melapor jumlah)</p>
          {rolls.map((r, i) => (
            <div key={i} className="mt-1 grid grid-cols-[1fr_1fr_auto] gap-2">
              <input className="field" data-testid={`mko-forward-len-${i}`} inputMode="decimal" placeholder={`Panjang (${unit})`} value={r.length}
                onChange={(e) => setRolls(rolls.map((x, j) => (j === i ? { ...x, length: e.target.value } : x)))} />
              <input className="field" data-testid={`mko-forward-lot-${i}`} placeholder="Lot (boleh kosong)" value={r.lot}
                onChange={(e) => setRolls(rolls.map((x, j) => (j === i ? { ...x, lot: e.target.value } : x)))} />
              <button type="button" className="secondary-button" aria-label="Hapus roll" onClick={() => setRolls(rolls.filter((_, j) => j !== i))}><Trash2 size={13} /></button>
            </div>
          ))}
          <button type="button" className="secondary-button mt-1" data-testid="mko-forward-add-roll" onClick={() => setRolls([...rolls, { length: "", lot: "" }])}><Plus size={13} />Tambah roll</button>
          {rolls.length > 0 && <p className="mt-1 text-fs-12 text-kn-text-2">Total roll: {sum} {unit}</p>}
        </div>
        <label className="text-fs-12 font-semibold">Catatan
          <input className="field mt-1" data-testid="mko-forward-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="mis. SJ mitra no. 123, dikirim truk mitra" />
        </label>
      </div>
    </FormModal>
  );
}
