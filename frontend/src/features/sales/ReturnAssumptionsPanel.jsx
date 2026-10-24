import { useEffect, useState } from "react";
import { Info } from "lucide-react";
import axios, { API } from "../../services/apiClient";


const GRADES = ["A", "A1", "A2", "B", "B1", "C", "BS"];
const DEF_FACTORS = { A: 100, A1: 95, A2: 90, B: 70, B1: 60, C: 40, BS: 10 };

// LN-091-T02 — % harga daftar per grade; selisih grade lama vs baru = kerugian turun grade.
function GradeFactors({ value, disabled, onChange }) {
  const v = { ...DEF_FACTORS, ...(value || {}) };
  return (
    <div className="flex flex-wrap items-end gap-2 text-[12px]" data-testid="return-assume-grade-factors">
      <span className="w-full text-[#8A4B08]">Harga daftar per grade (% dari harga produk) — dasar kerugian turun grade:</span>
      {GRADES.map((g) => (
        <label key={g} className="flex flex-col gap-1">{g}
          <input type="number" min={0} max={100} disabled={disabled} data-testid={`return-assume-grade-${g}`} value={v[g]}
            onChange={(e) => onChange({ ...v, [g]: Math.min(100, Math.max(0, Number(e.target.value) || 0)) })} className="field w-16" /></label>
      ))}
    </div>
  );
}

// LN-083 — asumsi sementara batas retur (KLR-08/KLR-09 menunggu owner); tersimpan di Pengaturan global.
export default function ReturnAssumptionsPanel({ canManage }) {
  const [f, setF] = useState(null);
  const [msg, setMsg] = useState("");
  useEffect(() => {
    axios.get(`${API}/settings/effective`).then((r) => setF({ customer_window_days: 21, supplier_window_days: 21,
      bill_first: true, supplier_reminder_days: 3, ...(r.data.returns || {}) })).catch(() => setF(null));
  }, []);
  if (!f) return null;
  const save = async () => {
    setMsg("");
    try {
      await axios.put(`${API}/settings`, { scope: "global", returns: { ...f,
        customer_window_days: Math.max(1, parseInt(f.customer_window_days, 10) || 21),
        supplier_window_days: Math.max(1, parseInt(f.supplier_window_days, 10) || 21),
        supplier_reminder_days: Math.max(0, parseInt(f.supplier_reminder_days, 10) || 0) } });
      setMsg("Batas umum tersimpan.");
    } catch (e) { setMsg(e.response?.data?.detail || e.message); }
  };
  const num = (k, label) => (
    <label className="flex flex-col gap-1 text-[12px]">{label}
      <input data-testid={`return-assume-${k}`} type="number" min={1} disabled={!canManage} value={f[k]}
             onChange={(e) => setF({ ...f, [k]: e.target.value })} className="field w-28" /></label>
  );
  return (
    <div data-testid="return-assumptions-panel" className="mb-4 rounded-xl border border-[#F5E0C3] bg-[#FDF6EC] p-3 space-y-2">
      <p className="flex items-start gap-2 text-[12px] text-[#8A4B08]"><Info size={14} className="mt-0.5 shrink-0" />
        <span><b>Batas retur umum (sementara)</b>: batas pelanggan dihitung dari tanggal Surat Jalan, batas supplier dari tanggal roll diterima di gudang — keduanya terpisah. Batas dinilai pada tanggal pengajuan (pelanggan) dan tanggal klaim dikirim (supplier). Hangtag hilang / kain dipotong hanya dicatat sebagai checklist + peringatan; Finance memutus saat penyelesaian. Kebijakan di daftar bawah boleh menimpa batas pelanggan ini.</span></p>
      <div className="flex flex-wrap items-end gap-3">
        {num("customer_window_days", "Pelanggan (hari dari SJ)")}
        {num("supplier_window_days", "Supplier (hari dari terima)")}
        {num("supplier_reminder_days", "Ingatkan PT pemasok (hari sebelum batas)")}
        <label className="flex items-center gap-1.5 text-[12px]"><input type="checkbox" data-testid="return-assume-bill_first" disabled={!canManage}
               checked={!!f.bill_first} onChange={(e) => setF({ ...f, bill_first: e.target.checked })} /> Potong tagihan SO asal dulu, sisanya refund/saldo</label>
      </div>
      <GradeFactors value={f.grade_price_factors} disabled={!canManage}
        onChange={(g) => setF({ ...f, grade_price_factors: g })} />
      <div className="flex flex-wrap items-center gap-3">
        {canManage && <button type="button" data-testid="return-assume-save" onClick={save} className="secondary-button">Simpan batas umum</button>}
        {msg && <span className="text-[12px]" data-testid="return-assume-msg">{msg}</span>}
      </div>
    </div>
  );
}
