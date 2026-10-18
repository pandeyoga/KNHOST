/** Temuan lama #12 — daftar roll stok awal yang belum ber-HPP + isian cepat. */
import { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function OpeningCostAlert({ refreshKey }) {
  const [data, setData] = useState({ total: 0, rows: [] });
  const [open, setOpen] = useState(false);
  const [vals, setVals] = useState({});
  const [msg, setMsg] = useState("");
  const load = () => axios.get(`${API}/inventory/rolls-without-cost`).then((r) => setData(r.data)).catch(() => {});
  useEffect(() => { load(); }, [refreshKey]);
  if (!data.total) return null;
  const save = async (id) => {
    try {
      await axios.patch(`${API}/inventory/rolls/${id}/opening-cost`, { unit_cost: vals[id] });
      setMsg("HPP tersimpan."); load();
    } catch (e) { setMsg(e.response?.data?.detail || "Gagal menyimpan HPP."); }
  };
  return (
    <div data-testid="opening-cost-alert" className="mb-2.5 rounded-lg border border-[#F1D08A] bg-[#FFF6E0] p-2.5 text-[11px]">
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold text-[#7A5B00]">{data.total} roll stok awal belum punya HPP — lengkapi sebelum go-live (laba & nilai persediaan salah).</p>
        <button data-testid="opening-cost-toggle" className="secondary-button" onClick={() => setOpen((v) => !v)}>{open ? "Tutup" : "Lengkapi"}</button>
      </div>
      {open && (
        <ul className="mt-2 space-y-1">
          {data.rows.map((r) => (
            <li key={r.id} className="flex items-center gap-2" data-testid={`opening-cost-row-${r.id}`}>
              <span className="flex-1 font-mono">{r.roll_no} · {r.product_name || r.sku} · {r.quantity} {r.unit}</span>
              <input type="number" className="field w-32 tabular-nums" placeholder="HPP / satuan" value={vals[r.id] ?? ""}
                onChange={(e) => setVals({ ...vals, [r.id]: e.target.value })} data-testid={`opening-cost-input-${r.id}`} />
              <button className="primary-button" disabled={!(parseFloat(vals[r.id]) > 0)} onClick={() => save(r.id)} data-testid={`opening-cost-save-${r.id}`}>Simpan</button>
            </li>
          ))}
        </ul>
      )}
      {msg && <p className="mt-1 text-[#6B6B73]" data-testid="opening-cost-msg">{msg}</p>}
    </div>
  );
}
