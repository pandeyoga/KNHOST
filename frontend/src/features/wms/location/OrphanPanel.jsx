import { useEffect, useState } from "react";
import { AlertOctagon } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { q } from "./locUtils";

// Alamat yatim: roll fisik yang bin-nya tidak ada lagi di master. Koreksi wajib beralasan & tercatat.
export default function OrphanPanel({ whId, binOptions, onChanged }) {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const load = () => axios.get(`${API}/warehouses/${whId}/orphans`).then((r) => setRows(r.data.rolls)).catch((e) => setErr(apiErrorText(e)));
  useEffect(() => { if (whId) load(); }, [whId]); // eslint-disable-line
  if (err) return <p className="text-[12px] text-[#C0341D]">{err}</p>;
  if (!rows) return <div className="h-16 bg-[#F5F5F7] rounded animate-pulse" />;
  if (!rows.length) return <p data-testid="lp-orphans-empty" className="py-8 text-center text-[12px] text-[#6B6B73]">Tidak ada alamat yatim di gudang ini.</p>;
  return (
    <div className="space-y-2" data-testid="lp-orphans">
      <p className="text-[11.5px] text-[#6B6B73]">Roll ini tetap terhitung sebagai stok fisik. Cek fisik dulu, lalu koreksi alamatnya — barang tidak dipindah otomatis.</p>
      {rows.map((r) => <OrphanRow key={r.id} roll={r} binOptions={binOptions} onDone={() => { load(); onChanged?.(); }} />)}
    </div>
  );
}

function OrphanRow({ roll, binOptions, onDone }) {
  const [bin, setBin] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const submit = async () => {
    setErr("");
    try { await axios.post(`${API}/inventory/rolls/${roll.id}/fix-location`, { bin_id: bin, reason }); onDone(); }
    catch (e) { setErr(apiErrorText(e, "Gagal mengoreksi alamat")); }
  };
  return (
    <div data-testid={`lp-orphan-${roll.id}`} className="rounded-lg border border-[#F8D7D0] bg-[#FFF8F6] p-2 space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <AlertOctagon size={14} className="text-[#C0341D]" />
        <span className="text-[12px] font-semibold">{roll.roll_no} · {roll.sku}</span>
        <span className="text-[11px] text-[#6B6B73]">{q(roll.length_remaining)} {roll.unit} · alamat lama <code className="font-mono">{roll.bin_id}</code></span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <KNSelect data-testid={`lp-orphan-bin-${roll.id}`} value={bin} onValueChange={setBin}
          options={[{ value: "", label: "Kosongkan (kembali ke antrean)" }, ...binOptions]} className="field !py-1 !px-2 text-[12px] w-60" placeholder="Bin baru…" />
        <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Alasan koreksi (hasil cek fisik)" data-testid={`lp-orphan-reason-${roll.id}`}
          className="flex-1 min-w-[200px] rounded-md border border-[#E5E5EA] px-2 py-1 text-[11.5px]" />
        <button data-testid={`lp-orphan-fix-${roll.id}`} onClick={submit} disabled={reason.trim().length < 5}
          className="rounded-md bg-[#C0341D] px-3 py-1 text-[11.5px] font-semibold text-white disabled:opacity-40">Koreksi alamat</button>
      </div>
      {err && <p className="text-[11px] font-semibold text-[#C0341D]">{err}</p>}
    </div>
  );
}
