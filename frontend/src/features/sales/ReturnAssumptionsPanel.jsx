import { useEffect, useState } from "react";
import { Info } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";

const K8 = [{ value: "pending", label: "Belum diputuskan — tandai pending" }, { value: "review", label: "Asumsi: wajib diperiksa" },
  { value: "reject", label: "Asumsi: tolak" }];
const K9 = [{ value: "pending", label: "Belum diputuskan — tandai pending" }, { value: "request", label: "Asumsi: cukup pengajuan dalam batas" },
  { value: "goods_received", label: "Asumsi: barang harus tiba dalam batas" }];

const K1 = [{ value: "pending", label: "Belum diputuskan (KLR-01)" }, { value: "defect_only", label: "Asumsi: hanya bagian cacat" },
  { value: "defect_plus_shorter", label: "Asumsi: cacat + sisi pendek" }, { value: "whole_roll", label: "Asumsi: seluruh roll" }];
const K2 = [{ value: "pending", label: "Belum diputuskan (KLR-02)" }, { value: "line_price", label: "Asumsi: harga jual SO" },
  { value: "net_after_discount", label: "Asumsi: harga neto setelah diskon" }];
const K6 = [{ value: "pending", label: "Belum diputuskan — wajib pengecualian QC" }, { value: "approved_exception", label: "Asumsi: boleh dengan persetujuan" }];

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
      klr08_hangtag_cut: "pending", klr09_end_event: "pending", bill_first: true, cutloss_return_part: "pending",
      cutloss_value_basis: "pending", discount_mode: "pending", ...(r.data.returns || {}) })).catch(() => setF(null));
  }, []);
  if (!f) return null;
  const save = async () => {
    setMsg("");
    try {
      await axios.put(`${API}/settings`, { scope: "global", returns: { ...f,
        customer_window_days: Math.max(1, parseInt(f.customer_window_days, 10) || 21),
        supplier_window_days: Math.max(1, parseInt(f.supplier_window_days, 10) || 21) } });
      setMsg("Asumsi tersimpan.");
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
        <span><b>ASUMSI SEMENTARA</b>: batas customer dihitung dari SJ, batas supplier per penerimaan roll di gudang. Keduanya independen. Aturan hangtag/kain dipotong (KLR-08) dan kejadian akhir batas (KLR-09) menunggu keputusan owner.</span></p>
      <div className="flex flex-wrap items-end gap-3">
        {num("customer_window_days", "Customer (hari dari SJ)")}
        {num("supplier_window_days", "Supplier (hari dari terima)")}
        <div className="w-64 flex flex-col gap-1 text-[12px]">KLR-08 hangtag hilang / kain dipotong
          <KNSelect data-testid="return-assume-klr08" value={f.klr08_hangtag_cut} options={K8} searchable={false} disabled={!canManage}
                    onValueChange={(v) => setF({ ...f, klr08_hangtag_cut: v })} /></div>
        <div className="w-64 flex flex-col gap-1 text-[12px]">KLR-09 kejadian akhir batas
          <KNSelect data-testid="return-assume-klr09" value={f.klr09_end_event} options={K9} searchable={false} disabled={!canManage}
                    onValueChange={(v) => setF({ ...f, klr09_end_event: v })} /></div>
        {[["cutloss_return_part", "Cutloss: bagian dikembalikan", K1], ["cutloss_value_basis", "Cutloss: basis nilai", K2],
          ["discount_mode", "Diskon tanpa barang kembali", K6]].map(([k, l, o]) => (
          <div key={k} className="w-60 flex flex-col gap-1 text-[12px]">{l}
            <KNSelect data-testid={`return-assume-${k}`} value={f[k]} options={o} searchable={false} disabled={!canManage}
                      onValueChange={(v) => setF({ ...f, [k]: v })} /></div>
        ))}
        <label className="flex items-center gap-1.5 text-[12px]"><input type="checkbox" data-testid="return-assume-bill_first" disabled={!canManage}
               checked={!!f.bill_first} onChange={(e) => setF({ ...f, bill_first: e.target.checked })} /> Potong tagihan SO asal dulu, sisanya refund/saldo</label>
      </div>
      <GradeFactors value={f.grade_price_factors} disabled={!canManage}
        onChange={(g) => setF({ ...f, grade_price_factors: g })} />
      <div className="flex flex-wrap items-center gap-3">
        {canManage && <button type="button" data-testid="return-assume-save" onClick={save} className="primary-button">Simpan asumsi</button>}
        {msg && <span className="text-[12px]" data-testid="return-assume-msg">{msg}</span>}
      </div>
    </div>
  );
}
