/** L10 LN-100/LN-102 — stok per alamat: Zona → Lemari → Rak → Bin dari saldo roll; induk = jumlah anak, dipisah per satuan. */
import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { entityShortFromCtx } from "../../../utils/entityLabel";
import { q } from "./locUtils";

const KIND = { warehouse: "Gudang", zone: "Zona", lemari: "Lemari", rak: "Rak", bin: "Bin", unassigned: "", orphan: "", transit: "" };
const COLS = [["available", "Tersedia"], ["reserved", "Dipesan"], ["qc_hold", "QC/ditahan"], ["wip", "Proses"], ["in_transit", "Perjalanan"], ["total", "Total"]];

function Units({ byUnit, testId }) {
  const units = Object.entries(byUnit || {});
  if (!units.length) return <span className="text-[#B4B4BB]">—</span>;
  return (
    <div className="grid gap-0.5" data-testid={testId}>
      {units.map(([u, v]) => (
        <div key={u} className="grid grid-cols-6 gap-2 tabular-nums">
          {COLS.map(([k]) => <span key={k} className={`${k === "available" ? "font-semibold text-[#1A7A3A]" : k === "qc_hold" && v[k] ? "text-[#C0392B]" : ""}`}>{v[k] ? `${q(v[k])} ${u}` : "·"}</span>)}
        </div>
      ))}
    </div>
  );
}

function Node({ n, depth }) {
  const [open, setOpen] = useState(depth < 1);
  const kids = n.children || [];
  return (
    <>
      <div className="grid grid-cols-[minmax(220px,1.2fr)_70px_minmax(0,3fr)] items-start gap-2 border-b border-[#F2F3F5] px-2 py-1.5 text-[11.5px]"
        data-testid={`st-node-${n.id}`} style={{ paddingLeft: 8 + depth * 16 }}>
        <button type="button" className="flex items-center gap-1 text-left" onClick={() => setOpen(!open)} disabled={!kids.length} data-testid={`st-toggle-${n.id}`}>
          {kids.length ? (open ? <ChevronDown size={12} /> : <ChevronRight size={12} />) : <span className="w-3" />}
          {KIND[n.kind] && <span className="text-[10px] uppercase text-[#8E8E93]">{KIND[n.kind]}</span>}
          <b className={n.kind === "orphan" ? "text-[#C0392B]" : ""}>{n.name}</b>
        </button>
        <span className="tabular-nums" data-testid={`st-rolls-${n.id}`}>{n.rolls} roll</span>
        <div>
          <Units byUnit={n.by_unit} testId={`st-units-${n.id}`} />
          {n.address && <p className="text-[10px] text-[#6B6B73]" data-testid={`st-address-${n.id}`}>{n.address}</p>}
        </div>
      </div>
      {open && kids.map((c) => <Node key={c.id} n={c} depth={depth + 1} />)}
    </>
  );
}

export default function StockTreePanel({ whId, ownerOptions = [] }) {
  const [owner, setOwner] = useState("");
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!whId) return;
    setData(null); setErr("");
    axios.get(`${API}/warehouses/${whId}/stock-tree`, { params: { owner } }).then((r) => setData(r.data)).catch((e) => setErr(apiErrorText(e)));
  }, [whId, owner]);
  return (
    <div className="rounded-xl border border-[#EFF0F2] bg-white" data-testid="stock-tree-panel">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#EFF0F2] px-3 py-2">
        <p className="text-[12px] font-bold">Stok per alamat</p>
        <span className="text-[10.5px] text-[#6B6B73]">dari saldo roll · induk = jumlah anak · QC/ditahan tidak dihitung tersedia</span>
        <KNSelect data-testid="stock-tree-owner" className="field ml-auto !py-1 w-auto text-[12px]" value={owner} onValueChange={setOwner}
          options={[{ value: "", label: "Semua pemilik (sesuai akses)" }, ...ownerOptions]} />
      </div>
      {err && <p className="px-3 py-2 text-[12px] text-[#C0392B]" data-testid="stock-tree-error">{err}</p>}
      {!data && !err && <div className="m-3 h-10 animate-pulse rounded bg-[#F2F2F5]" />}
      {data && (
        <div className="overflow-x-auto">
          <div className="grid grid-cols-[minmax(220px,1.2fr)_70px_minmax(0,3fr)] gap-2 bg-[#FAFBFC] px-2 py-1 text-[10px] font-bold uppercase text-[#6B6B73]">
            <span>Alamat</span><span>Roll</span>
            <span className="grid grid-cols-6 gap-2">{COLS.map(([k, l]) => <span key={k}>{l}</span>)}</span>
          </div>
          <Node n={data.tree} depth={0} />
          {(data.tree.by_owner || []).length > 0 && (
            <div className="border-t border-[#EFF0F2] px-3 py-2 text-[11px]" data-testid="stock-tree-owners">
              <p className="mb-1 font-bold text-[#6B6B73]">Per pemilik (bukan lokasi)</p>
              {data.tree.by_owner.map((o) => (
                <div key={o.owner_entity_id || "none"} className="grid grid-cols-[160px_70px_minmax(0,3fr)] gap-2" data-testid={`stock-tree-owner-${o.owner_entity_id || "none"}`}>
                  <b>{ownerOptions.find((x) => x.value === o.owner_entity_id)?.label || entityShortFromCtx(o.owner_entity_id, "—")}</b>
                  <span>{o.rolls} roll</span><Units byUnit={o.by_unit} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
