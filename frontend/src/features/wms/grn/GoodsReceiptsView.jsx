import { useCallback, useEffect, useState } from "react";
import { Plus, Settings } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { ErrorBox, GrnStatusBadge } from "./GrnBits";
import GrnCreateWizard from "./GrnCreateWizard";
import GrnDetail from "./GrnDetail";
import SupplierVariancePanel from "./SupplierVariancePanel";
import InboundScanInterface from "../InboundScanInterface";
import useReceivingMode from "../../../hooks/useReceivingMode";
import { SearchBox } from "../../../components/ListControls";
import { STATUS, errText, grnApi } from "./grnApi";

const FILTERS = [["", "Semua"], ["draft,review", "Tinjau SJ"], ["counting", "Hitung"], ["reconcile,closing", "Rekonsiliasi"], ["closed", "Ditutup"], ["rejected,cancelled", "Batal/Tolak"]];
const CREATE_ROLES = ["admin", "warehouse", "warehouse_admin"];
const LEGACY_ROLES = ["admin", "warehouse", "manager"];
const SETTINGS_ROLES = ["admin", "manager", "warehouse_admin"];
const mkoPreset = () => {
  const q = new URLSearchParams(window.location.search);
  return q.get("mko") ? { partner_type: "makloon", partner_id: q.get("makloon") || "", warehouse_id: q.get("wh") || "", po_ids: [q.get("mko")] } : null;
};

/** Operasi Gudang → Barang Masuk: Kedatangan (SJ & OCR) · Selisih Supplier · Scan Terima PO (mode lama). */
export default function GoodsReceiptsView({ currentUser, selectedEntity, focusDoc, onClearFocus, onOpenPO }) {
  const [tab, setTab] = useState("list");
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState(() => new URLSearchParams(window.location.search).get("grn") || "");
  const [wizard, setWizard] = useState(mkoPreset);
  const [legacyPo, setLegacyPo] = useState("");
  const [err, setErr] = useState("");
  const { isGrn, entityOf } = useReceivingMode();
  const grnOnly = selectedEntity && selectedEntity !== "all" && isGrn(selectedEntity) && !(entityOf(selectedEntity)?.legacy_in_flight || []).length;
  const showLegacy = LEGACY_ROLES.includes(currentUser?.role) && !grnOnly;
  const load = useCallback(() => grnApi.list({ status, q }).then(setRows).catch((e) => setErr(errText(e))), [status, q]);
  useEffect(() => { if (!openId) load(); }, [load, openId, selectedEntity]);
  useEffect(() => {
    if (!focusDoc?.focus_id) return;
    if (focusDoc.focus_type === "goods_receipt") setOpenId(focusDoc.focus_id);
    if (focusDoc.focus_type === "purchase_order" && focusDoc.tab === "inbound" && showLegacy) {
      setTab("legacy"); setLegacyPo(focusDoc.focus_id);
    } else if (focusDoc.focus_type === "purchase_order") {
      axios.get(`${API}/purchase-orders/${focusDoc.focus_id}`).then((r) => setWizard({
        partner_type: "supplier", partner_id: r.data.supplier_id, warehouse_id: r.data.warehouse_id, po_ids: [r.data.id],
      })).catch((e) => setErr(errText(e)));
    }
    onClearFocus?.();
  }, [focusDoc, onClearFocus]); // eslint-disable-line react-hooks/exhaustive-deps

  if (openId) return <div className="p-4 pb-28 lg:p-0 lg:pb-4"><GrnDetail grnId={openId} user={currentUser} onBack={() => setOpenId("")} /></div>;
  const tabs = [["list", "Kedatangan (SJ & OCR)"], ["variance", "Selisih Supplier"], ...(showLegacy ? [["legacy", "Scan Terima per PO"]] : [])];
  return (
    <div className="space-y-3 p-4 pb-28 lg:p-0 lg:pb-4" data-testid="goods-receipts-view">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="tab-bar !mb-0 flex-1">
          {tabs.map(([k, l]) => (
            <button key={k} type="button" data-testid={`grn-view-tab-${k}`} onClick={() => setTab(k)} className={`tab-button ${tab === k ? "active" : ""}`}>{l}</button>
          ))}
        </div>
        <div className="flex items-center gap-2 pb-1">
          {SETTINGS_ROLES.includes(currentUser?.role) && (
            <a data-testid="grn-open-ocr-settings" href="?view=settings-receiving-ocr" title="Profil SJ, Sampel Uji OCR, Biaya OCR & Mode Penerimaan ada di Pengaturan › Gudang"
              className="secondary-button !py-1 text-[11px]"><Settings size={12} /> Pengaturan OCR</a>
          )}
          {CREATE_ROLES.includes(currentUser?.role) && tab === "list" && (
            <button data-testid="grn-new-button" className="primary-button" onClick={() => setWizard({})}><Plus size={13} /> Kedatangan baru</button>
          )}
        </div>
      </div>
      <ErrorBox text={err} />
      {tab === "variance" ? <SupplierVariancePanel onOpenGrn={setOpenId} /> : tab === "legacy" ? (
        <div className="section-card" data-testid="grn-legacy-inbound">
          <div className="section-head">
            <div className="flex items-center gap-2 min-w-0">
              <span className="kicker">Scan Terima PO</span>
              <h2>Penerimaan per Pesanan Pembelian (scan per PO)</h2>
            </div>
            <span className="text-[11px] text-[#6B6B73]">Scan barcode di formulir tugas di bawah</span>
          </div>
          <div className="section-body">
            <InboundScanInterface user={currentUser} focusPoId={legacyPo} onFocusConsumed={() => setLegacyPo("")} onOpenPO={onOpenPO} />
          </div>
        </div>
      ) : (<>
        <div className="flex flex-wrap items-center gap-2">
          <SearchBox value={q} onChange={setQ} placeholder="Nomor GRN / SJ / mitra" testId="grn-search" />
          {FILTERS.map(([v, l]) => (
            <button key={l} data-testid={`grn-filter-${v || "all"}`} onClick={() => setStatus(v)}
              className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${status === v ? "border-[#0058CC] bg-[#EEF4FF] text-[#0058CC]" : "border-[#E5E5EA] text-[#3C3C43]"}`}>{l}</button>
          ))}
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
          {!rows.length && (
            <div className="empty-state col-span-full w-full" data-testid="grn-list-empty">
              <p className="font-semibold">Belum ada kedatangan{status ? ` berstatus ${STATUS[status.split(",")[0]]?.label || status}` : ""}.</p>
              <p className="text-sm text-muted" style={{ maxWidth: 480 }}>Catat barang yang tiba: foto Surat Jalan dibaca otomatis (OCR), lalu hitung fisik & rekonsiliasi dengan PO.</p>
              {CREATE_ROLES.includes(currentUser?.role) && <button className="primary-button" style={{ marginTop: 8 }} onClick={() => setWizard({})}><Plus size={13} /> Kedatangan baru</button>}
            </div>
          )}
        </div>
      </>)}
      {wizard && <GrnCreateWizard preset={wizard} onClose={() => setWizard(null)} onCreated={(g) => { setWizard(null); setOpenId(g.id); }} />}
    </div>
  );
}
