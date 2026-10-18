import { useEffect, useState } from "react";
import { ClipboardCheck, ListChecks, Printer, RefreshCw } from "lucide-react";
import { tripCandidates, tripCheck, tripPickingList } from "./logisticsApi";

// L07 LN-070 — picking list per gudang sumber untuk beberapa SO sekaligus + cek kesiapan berangkat.
function ReadyTable({ check }) {
  return (
    <div className="rounded-lg border border-[#E1E4EA] p-2.5" data-testid="trip-check-result">
      <p className={`text-[12px] font-bold ${check.ready ? "text-[#1F7A45]" : "text-[#C0341D]"}`} data-testid="trip-check-status">
        {check.ready ? "Semua pesanan siap berangkat" : "Belum siap — perbaiki dulu baris merah"}</p>
      {check.rows.map((r) => (
        <p key={`${r.order_id}-${r.warehouse_id}`} className="text-[11px] mt-1" data-testid={`trip-check-row-${r.order_id}-${r.warehouse_id}`}>
          <span className={`status-pill ${r.ready ? "pill-success" : "pill-danger"}`}>{r.ready ? "Siap" : "Tertahan"}</span>{" "}
          <b>{r.order_number}</b> · {r.warehouse_name}{r.reason ? ` — ${r.reason}` : ""}</p>
      ))}
    </div>
  );
}

function WarehouseBlock({ w }) {
  return (
    <div className="rounded-lg border border-[#E1E4EA] p-2.5" data-testid={`picking-wh-${w.warehouse_id}`}>
      <p className="text-[12px] font-bold">{w.warehouse_name} <span className="text-[11px] font-normal text-[#6B6B73]">· {w.picked_count}/{w.roll_count} roll sudah diambil</span></p>
      <table className="w-full text-[11px] mt-1.5">
        <thead><tr className="text-left text-[#6B6B73]"><th>Bin</th><th>Roll</th><th>Pesanan</th><th>Produk</th><th className="text-right">Qty</th><th>Status</th></tr></thead>
        <tbody>
          {w.rolls.map((r) => (
            <tr key={r.roll_id} className="border-t border-[#F0F1F3]" data-testid={`picking-roll-${r.roll_id}`}>
              <td className="font-mono">{r.bin || "-"}</td><td className="font-mono font-semibold">{r.roll_no}</td>
              <td>{r.order_number}</td><td>{r.product_name}</td>
              <td className="text-right tabular-nums">{r.length} {r.unit}</td>
              <td>{r.picked ? "Diambil" : "Belum"}{!r.tagged ? " · tanpa tag" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TripPlannerPanel({ params }) {
  const [cands, setCands] = useState([]);
  const [sel, setSel] = useState([]);
  const [list, setList] = useState(null);
  const [check, setCheck] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => tripCandidates(params).then(setCands).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat pesanan."));
  useEffect(() => { load(); }, [params]); // eslint-disable-line
  const toggle = (id) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  async function run() {
    setBusy(true); setErr("");
    try { const [l, c] = await Promise.all([tripPickingList(sel), tripCheck(sel)]); setList(l); setCheck(c); }
    catch (e) { setErr(e.response?.data?.detail || "Gagal menyusun picking list."); }
    finally { setBusy(false); }
  }

  return (
    <div className="grid gap-3" data-testid="trip-planner">
      <div className="rounded-lg border border-[#E1E4EA] p-2.5">
        <div className="flex items-center gap-2"><p className="text-[12px] font-bold flex items-center gap-1"><ListChecks size={13} /> Pesanan dengan tugas ambil terbuka</p>
          <button className="icon-button ml-auto" data-testid="trip-refresh" onClick={load}><RefreshCw size={13} /></button></div>
        {cands.length === 0 ? <p className="text-[11.5px] text-[#9A9BA3] mt-1" data-testid="trip-empty">Tidak ada pesanan yang menunggu diambil.</p> : (
          <div className="mt-1.5 grid gap-1 max-h-[220px] overflow-auto">
            {cands.map((c) => (
              <label key={c.order_id} className="flex items-center gap-2 text-[11.5px] cursor-pointer" data-testid={`trip-order-${c.order_id}`}>
                <input type="checkbox" className="h-4 w-4 accent-[#0058CC]" checked={sel.includes(c.order_id)} onChange={() => toggle(c.order_id)} />
                <b>{c.order_number}</b><span className="text-[#6B6B73]">{c.customer_name} · {c.warehouses.join(", ")}</span>
                {c.fulfillment_method === "ambil" && <span className="status-pill pill-purple">Ambil sendiri</span>}
              </label>
            ))}
          </div>
        )}
        <div className="flex gap-2 mt-2">
          <button className="primary-button" data-testid="trip-build" disabled={!sel.length || busy} onClick={run}><ClipboardCheck size={13} /> {busy ? "Menyusun…" : `Susun picking list & cek (${sel.length})`}</button>
          {list && <button className="secondary-button" data-testid="trip-print" onClick={() => window.print()}><Printer size={13} /> Cetak</button>}
        </div>
        {err && <p className="text-[11px] text-[#C0341D] mt-1" data-testid="trip-error">{err}</p>}
      </div>
      {check && <ReadyTable check={check} />}
      {list && (<>
        <p className="text-[10.5px] text-[#6B6B73]" data-testid="trip-note">{list.note}</p>
        {list.warehouses.map((w) => <WarehouseBlock key={w.warehouse_id} w={w} />)}
      </>)}
    </div>
  );
}
