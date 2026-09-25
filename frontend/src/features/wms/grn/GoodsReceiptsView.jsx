import { useCallback, useEffect, useState } from "react";
import { Plus, Search } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { ErrorBox, GrnStatusBadge, inputCls } from "./GrnBits";
import GrnCreateWizard from "./GrnCreateWizard";
import GrnDetail from "./GrnDetail";
import GrnOcrUsagePanel from "./GrnOcrUsagePanel";
import SupplierVariancePanel from "./SupplierVariancePanel";
import { STATUS, errText, grnApi } from "./grnApi";

const FILTERS = [["", "Semua"], ["draft,review", "Tinjau SJ"], ["counting", "Hitung"], ["reconcile,closing", "Rekonsiliasi"], ["closed", "Ditutup"], ["rejected,cancelled", "Batal/Tolak"]];
const CREATE_ROLES = ["admin", "warehouse", "warehouse_admin"];
const USAGE_ROLES = ["admin", "manager", "warehouse_admin"];

/** Gudang → Kedatangan Barang (GRN): satu surat jalan · satu mitra · hitung fisik · rekonsiliasi. */
export default function GoodsReceiptsView({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  const [tab, setTab] = useState("list");
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState(() => new URLSearchParams(window.location.search).get("grn") || "");
  const [wizard, setWizard] = useState(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => grnApi.list({ status, q }).then(setRows).catch((e) => setErr(errText(e))), [status, q]);
  useEffect(() => { if (!openId) load(); }, [load, openId, selectedEntity]);
  useEffect(() => {
    if (!focusDoc?.focus_id) return;
    if (focusDoc.focus_type === "goods_receipt") setOpenId(focusDoc.focus_id);
    if (focusDoc.focus_type === "purchase_order") {
      axios.get(`${API}/purchase-orders/${focusDoc.focus_id}`).then((r) => setWizard({
        partner_type: "supplier", partner_id: r.data.supplier_id, warehouse_id: r.data.warehouse_id, po_ids: [r.data.id],
      })).catch((e) => setErr(errText(e)));
    }
    onClearFocus?.();
  }, [focusDoc, onClearFocus]);

  if (openId) return <div className="p-4"><GrnDetail grnId={openId} user={currentUser} onBack={() => setOpenId("")} /></div>;
  return (
    <div className="space-y-3 p-4" data-testid="goods-receipts-view">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1 rounded-lg bg-[#F2F2F7] p-0.5 text-[11px] font-semibold">
          {[["list", "Kedatangan"], ["variance", "Selisih Supplier"], ...(USAGE_ROLES.includes(currentUser?.role) ? [["usage", "Biaya OCR"]] : [])].map(([k, l]) => (
            <button key={k} data-testid={`grn-view-tab-${k}`} onClick={() => setTab(k)} className={`rounded-md px-3 py-1.5 ${tab === k ? "bg-white text-[#0058CC] shadow-sm" : "text-[#6B6B73]"}`}>{l}</button>
          ))}
        </div>
        {CREATE_ROLES.includes(currentUser?.role) && (
          <button data-testid="grn-new-button" className="primary-button" onClick={() => setWizard({})}><Plus size={13} /> Kedatangan baru</button>
        )}
      </div>
      <ErrorBox text={err} />
      {tab === "usage" ? <GrnOcrUsagePanel /> : tab === "variance" ? <SupplierVariancePanel onOpenGrn={setOpenId} /> : (<>
        <div className="flex flex-wrap items-center gap-2">
          {FILTERS.map(([v, l]) => (
            <button key={l} data-testid={`grn-filter-${v || "all"}`} onClick={() => setStatus(v)}
              className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${status === v ? "border-[#0058CC] bg-[#EEF4FF] text-[#0058CC]" : "border-[#E5E5EA] text-[#3C3C43]"}`}>{l}</button>
          ))}
          <div className="relative ml-auto w-64">
            <Search size={13} className="absolute left-2 top-2 text-[#8E8E93]" />
            <input data-testid="grn-search" className={`${inputCls} pl-7`} placeholder="Nomor GRN / SJ / mitra" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3" data-testid="grn-list">
          {rows.map((r) => (
            <button key={r.id} data-testid={`grn-card-${r.id}`} onClick={() => setOpenId(r.id)}
              className="rounded-xl border border-[#EFF0F2] bg-white p-3 text-left transition-shadow hover:shadow-md">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[12px] font-bold">{r.number}</span>
                <GrnStatusBadge status={r.status} />
              </div>
              <p className="mt-1 text-[12px] font-semibold">{r.partner_name}</p>
              <p className="text-[10.5px] text-[#6B6B73]">SJ <span className="font-mono">{r.dn_number || "-"}</span> · {r.lines} baris · {r.pages} halaman</p>
              {r.open_blockers > 0 && <p className="mt-1 text-[10.5px] font-semibold text-[#B4231F]">{r.open_blockers} selisih pemblokir</p>}
              <p className="mt-1 text-[10px] text-[#8E8E93]">{(r.created_at || "").slice(0, 16).replace("T", " ")} · {r.created_by}</p>
            </button>
          ))}
          {!rows.length && <p className="text-[11px] text-[#6B6B73]" data-testid="grn-list-empty">Belum ada kedatangan {status ? `berstatus ${STATUS[status.split(",")[0]]?.label || status}` : ""}.</p>}
        </div>
      </>)}
      {wizard && <GrnCreateWizard preset={wizard} onClose={() => setWizard(null)} onCreated={(g) => { setWizard(null); setOpenId(g.id); }} />}
    </div>
  );
}
