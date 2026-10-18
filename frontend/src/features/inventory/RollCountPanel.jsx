/** L10 LN-101 — opname per roll: scope node → scan → rekonsiliasi → finalisasi (wewenang ACC). */
import { useEffect, useMemo, useState } from "react";
import { ScanLine, CheckCircle2 } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import RollReconcileTable from "./RollReconcileTable";
import UnknownRollForm from "./UnknownRollForm";

function nodeOptions(zones = []) {
  const out = [{ value: "", label: "Seluruh gudang" }];
  zones.forEach((z) => {
    out.push({ value: z.id, label: `Zona ${z.name}` });
    (z.racks || []).forEach((r) => {
      out.push({ value: r.id, label: `  ${z.name} › ${r.name}` });
      (r.levels || []).forEach((l) => out.push({ value: l.id, label: `    ${z.name} › ${r.name} › ${l.name}` }));
    });
  });
  return out;
}

export default function RollCountPanel({ session, canApprove, products = [], onChanged }) {
  const sid = session.id;
  const [loc, setLoc] = useState(null);
  const [rec, setRec] = useState(null);
  const [node, setNode] = useState("");
  const [scan, setScan] = useState({ code: "", bin_id: "", measured_qty: "", tag: "ok" });
  const [reason, setReason] = useState("");
  const [zeroCost, setZeroCost] = useState("");
  const [specs, setSpecs] = useState({});
  const [owners, setOwners] = useState([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const open = session.status === "open";

  const load = () => axios.get(`${API}/cycle-count/sessions/${sid}/roll-reconcile`).then((r) => setRec(r.data)).catch((e) => setErr(apiErrorText(e)));
  useEffect(() => {
    load();
    axios.get(`${API}/warehouses/${session.warehouse_id}/locations`).then((r) => setLoc(r.data)).catch(() => setLoc(null));
    axios.get(`${API}/entities`).then((r) => setOwners((Array.isArray(r.data) ? r.data : r.data?.items || [])
      .map((e) => ({ value: e.id, label: e.short_name || e.name || e.id })))).catch(() => setOwners([]));
  }, [sid]); // eslint-disable-line

  const binOpts = useMemo(() => (loc?.bins || []).map((b) => ({ value: b.bin_id, label: `${b.code} — ${b.path}` })), [loc]);
  const run = async (fn, okMsg) => {
    setErr(""); setMsg("");
    try { const r = await fn(); if (okMsg) setMsg(typeof okMsg === "function" ? okMsg(r.data) : okMsg); await load(); onChanged?.(); return r.data; }
    catch (e) { setErr(apiErrorText(e)); return null; }
  };
  const snapshot = () => run(() => axios.post(`${API}/cycle-count/sessions/${sid}/roll-scope`, { node_id: node }), (d) => `Snapshot dibekukan: ${d.expected_rolls} roll diharapkan.`);
  const doScan = async () => {
    if (!scan.code || !scan.bin_id) { setErr("Isi kode roll dan bin tempat roll ditemukan"); return; }
    const d = await run(() => axios.post(`${API}/cycle-count/sessions/${sid}/roll-scans`, scan),
      (x) => (x.duplicate ? x.message : `Tercatat: ${x.scan.roll_no || x.scan.code} (${(x.scan.kinds || []).map((k) => rec?.labels?.[k] || k).join(", ")})`));
    if (d) setScan((s) => ({ ...s, code: "", measured_qty: "", tag: "ok" }));
  };
  const unknownLines = (rec?.lines || []).filter((l) => l.kinds.includes("unknown") && !l.adjustment);
  const recountMissing = (rollId) => run(() => axios.post(`${API}/cycle-count/sessions/${sid}/roll-missing-recount`, { roll_id: rollId }),
    "Hitung ulang tercatat — roll akan dihapus dari stok saat finalisasi disetujui.");
  const finalize = () => {
    const new_rolls = Object.entries(specs).filter(([, v]) => v.product_id && v.owner_entity_id)
      .map(([scan_id, v]) => ({ scan_id, product_id: v.product_id, owner_entity_id: v.owner_entity_id, qty: v.qty === "" ? null : v.qty }));
    return run(() => axios.post(`${API}/cycle-count/sessions/${sid}/roll-finalize`, { reason, new_rolls, zero_cost_reason: zeroCost }),
      (d) => (d.recount?.length ? d.message : "Opname per roll difinalisasi sesuai SOP — koreksi diterapkan sekali."));
  };

  return (
    <div className="rounded-md border border-[#EFF0F2] bg-white p-3 grid gap-3" data-testid="roll-count-panel">
      <div className="flex items-center gap-2">
        <ScanLine size={15} className="text-[#0058CC]" />
        <h3 className="text-[13px] font-bold">Opname per Roll (scan)</h3>
        {rec?.enabled && <span className="text-[11px] text-[#6B6B73]" data-testid="roll-count-scope">· {rec.node_label} · snapshot {String(rec.snapshot_at).slice(0, 16).replace("T", " ")}</span>}
      </div>
      {err && <p className="text-[12px] text-[#C0392B]" data-testid="roll-count-error">{err}</p>}
      {msg && <p className="text-[12px] font-semibold text-[#1B7E3B]" data-testid="roll-count-msg">{msg}</p>}
      {open && !(rec?.lines || []).length && (
        <div className="flex flex-wrap gap-2 items-center">
          <KNSelect data-testid="roll-count-node" className="field flex-1 min-w-48" value={node} onValueChange={setNode} options={nodeOptions(loc?.zones)} />
          <button className="secondary-button" data-testid="roll-count-snapshot" onClick={snapshot}>{rec?.enabled ? "Ganti scope & snapshot ulang" : "Bekukan snapshot scope"}</button>
        </div>
      )}
      {open && rec?.enabled && (
        <div className="flex flex-wrap gap-2 items-center rounded bg-[#FAFBFC] p-2">
          <input className="field w-44" placeholder="Scan / ketik kode roll" value={scan.code} data-testid="roll-scan-code"
            onChange={(e) => setScan({ ...scan, code: e.target.value })} onKeyDown={(e) => e.key === "Enter" && doScan()} />
          <KNSelect data-testid="roll-scan-bin" className="field flex-1 min-w-48" value={scan.bin_id} placeholder="Bin tempat ditemukan"
            onValueChange={(v) => setScan({ ...scan, bin_id: v })} options={binOpts} />
          <input className="field w-28" type="number" min="0" placeholder="Qty fisik" value={scan.measured_qty} data-testid="roll-scan-qty"
            onChange={(e) => setScan({ ...scan, measured_qty: e.target.value })} />
          <KNSelect data-testid="roll-scan-tag" className="field w-40" value={scan.tag} onValueChange={(v) => setScan({ ...scan, tag: v })}
            options={[{ value: "ok", label: "Tag baik" }, { value: "damaged", label: "Tag rusak" }, { value: "unreadable", label: "Tidak terbaca (manual)" }]} />
          <button className="primary-button" data-testid="roll-scan-submit" onClick={doScan}>Catat</button>
        </div>
      )}
      {rec?.enabled && <RollReconcileTable rec={rec} open={open} onRecount={recountMissing}
        binName={(id) => (loc?.bins || []).find((b) => b.bin_id === id)?.code} />}
      {open && rec?.enabled && canApprove && <UnknownRollForm lines={unknownLines} products={products} owners={owners} specs={specs} setSpecs={setSpecs} />}
      {open && rec?.enabled && canApprove && (
        <div className="flex flex-wrap gap-2 items-center border-t border-[#F0F1F3] pt-2">
          <input className="field flex-1 min-w-48" placeholder="Alasan finalisasi (min. 5 karakter)" value={reason} data-testid="roll-finalize-reason" onChange={(e) => setReason(e.target.value)} />
          <input className="field w-56" placeholder="Alasan biaya nol (bila roll baru tanpa biaya acuan)" value={zeroCost} data-testid="roll-finalize-zero-cost" onChange={(e) => setZeroCost(e.target.value)} />
          <button className="primary-button !bg-green-600 !border-green-600" data-testid="roll-finalize-button" onClick={finalize}><CheckCircle2 size={13} /> Finalisasi &amp; terapkan</button>
        </div>
      )}
    </div>
  );
}
