import { useState } from "react";
import { Scissors } from "lucide-react";
import axios, { API } from "../../services/apiClient";

/** L04 LN-042 — potong uji MD Quality (default 0,25 yard) = mutasi pemakaian; roll kg wajib berat aktual. */
export default function MdqCutBox({ doc, line, onDone }) {
  const [yard, setYard] = useState("0.25");
  const [kg, setKg] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [done, setDone] = useState(null);
  const isKg = (line.unit || "").toLowerCase() === "kg";
  if (!line.roll_id) return null;
  const cutInfo = line.mdq_cut || done;
  if (cutInfo) {
    return <p className="rounded-lg bg-[#EAF7EF] px-3 py-2 text-[11.5px] text-[#0A6E47]" data-testid="mdq-cut-done">
      Sudah dipotong uji {cutInfo.qty} {cutInfo.unit} ({cutInfo.basis}) oleh {cutInfo.by}. Qty penerimaan tetap bruto.</p>;
  }
  const submit = async () => {
    setBusy(true); setMsg("");
    try {
      const { data } = await axios.post(`${API}/inspections/${doc.id}/lines/${line.id}/mdq-cut`, {
        cut_yard: parseFloat(yard.replace(",", ".")) || 0.25,
        weight_kg: isKg && kg ? parseFloat(kg.replace(",", ".")) : null,
      });
      setDone(data);
      onDone?.();
    } catch (e) { setMsg(e.response?.data?.detail || "Gagal mencatat potong uji."); }
    finally { setBusy(false); }
  };
  return (
    <div className="rounded-lg border border-[#EFF0F2] px-3 py-2 text-[11.5px]" data-testid="mdq-cut-box">
      <p className="mb-1 font-semibold"><Scissors size={12} className="mr-1 inline" />Potong uji MD Quality (waste, tidak dikirim)</p>
      <div className="flex flex-wrap items-center gap-1.5">
        <input className="field !w-16 !py-0.5 text-[11px]" value={yard} onChange={(e) => setYard(e.target.value)} data-testid="mdq-cut-yard" /> yard
        {isKg && <><input className="field !w-20 !py-0.5 text-[11px]" placeholder="berat kg" value={kg} onChange={(e) => setKg(e.target.value)} data-testid="mdq-cut-kg" /> kg aktual (timbang)</>}
        <button type="button" disabled={busy} className="secondary-button !py-0.5 text-[11px]" onClick={submit} data-testid="mdq-cut-submit">Catat potong</button>
      </div>
      {msg && <p className="mt-1 text-[#3C3C43]" data-testid="mdq-cut-msg">{msg}</p>}
    </div>
  );
}
