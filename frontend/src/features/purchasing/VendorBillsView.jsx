import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Receipt, Plus, Send, Wallet, Scale, Clock, AlertTriangle, Loader2 } from "lucide-react";
import { PageHeader, MetricRow, SearchBox, StatusTabs } from "../../components/ListPageParts";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import EntityBadge from "../../components/EntityBadge";
import PaginationBar from "../../components/PaginationBar";
import { usePagedList } from "../../hooks/usePagedList";

// FASE P6 — kolom Unduh CSV (mengikuti kolom tabel vendor bill).
const CSV_COLUMNS = [
  { key: "bill_number", header: "Nomor Tagihan" },
  { key: "supplier_name", header: "Supplier" },
  { key: "po_number", header: "No. PO" },
  { header: "Jumlah Item", type: "int", get: (b) => b.items?.length || 0 },
  { key: "grand_total", header: "Total", type: "num" },
  { header: "Sisa", type: "num", get: (b) => Number(b.financials?.outstanding ?? b.outstanding ?? 0) },
  { key: "match_status", header: "Match" },
  { key: "status", header: "Status" },
  { key: "supplier_invoice_no", header: "Inv. Supplier" },
  { key: "due_date", header: "Jatuh Tempo", type: "date" },
];
import VendorBillCreateModal from "./VendorBillCreateModal";
import VendorBillDetailPanel from "./VendorBillDetailPanel";
import DetailModal from "../../components/DetailModal";

/**
 * VendorBillsView (Fase 5.2 — P0-2) — Tagihan Supplier (Vendor Bill) + 3-Way Matching.
 * AP berbasis bill posted. PO ↔ GR ↔ Bill dicocokkan dengan toleransi qty & harga.
 */
const TABS = [
  { key: "all", label: "Semua" },
  { key: "draft", label: "Draf" },
  { key: "pending_approval", label: "Menunggu Persetujuan" },
  { key: "posted", label: "Terposting (belum lunas)" },
  { key: "paid", label: "Lunas" },
  { key: "cancelled", label: "Dibatalkan" },
];

function StatusPill({ status }) {
  const map = {
    draft: ["pill-muted", "Draf"], pending_approval: ["pill-warning", "Menunggu Persetujuan"],
    posted: ["pill-info", "Terposting"], paid: ["pill-success", "Lunas"], cancelled: ["pill-danger", "Dibatalkan"],
  };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`}>{label}</span>;
}
function MatchPill({ status }) {
  const map = { matched: ["pill-success", "Cocok"], warning: ["pill-warning", "Selisih"], blocked: ["pill-danger", "Lebih tagih"] };
  const [cls, label] = map[status] || ["pill-muted", "—"];
  return <span className={`status-pill ${cls}`}>{label}</span>;
}

export default function VendorBillsView({ currentUser, selectedEntity }) {
  const [pos, setPos] = useState([]);
  const [summary, setSummary] = useState(null);
  const [counts, setCounts] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [detail, setDetail] = useState(null);

  const canApprove = ["admin", "manager"].includes(currentUser?.role);
  const canCreate = ["admin", "manager"].includes(currentUser?.role);

  // P2 — paginasi server-side; tab status jadi filter server, search q server-side.
  const params = useMemo(() => {
    const p = {};
    if (selectedEntity && selectedEntity !== "all") p.entity_id = selectedEntity;
    if (tab !== "all") p.status = tab;
    return p;
  }, [selectedEntity, tab]);
  const paged = usePagedList("/vendor-bills", { pageSize: 20, params, search });
  const filtered = paged.items;   // sudah difilter status di server
  const loading = paged.loading;

  useEffect(() => { loadMeta(); }, [selectedEntity]); // eslint-disable-line

  async function loadMeta() {
    try {
      const mp = (selectedEntity && selectedEntity !== "all") ? { entity_id: selectedEntity } : {};
      const [poRes, sRes, cRes] = await Promise.all([
        axios.get(`${API}/purchase-orders`, { params: mp }).catch(() => ({ data: [] })),
        axios.get(`${API}/vendor-bills/payables/summary`, { params: mp }).catch(() => ({ data: null })),
        axios.get(`${API}/vendor-bills/status-counts`, { params: mp }).catch(() => ({ data: {} })),
      ]);
      const poData = Array.isArray(poRes.data) ? poRes.data : (poRes.data?.items || []);
      // PO yang bisa ditagih: sudah disetujui/diterima (bukan draft/menunggu/batal/ditolak)
      const billable = poData.filter(
        (p) => !["waiting_approval", "rejected", "cancelled", "draft"].includes(p.status));
      setPos(billable);
      setSummary(sRes.data);
      setCounts(cRes.data || {});
    } catch (e) { /* non-blocking */ }
  }

  const reload = () => { paged.refresh(); loadMeta(); };

  async function refreshDetail(id) {
    try {
      const r = await axios.get(`${API}/vendor-bills/${id}`);
      setDetail(r.data);
    } catch { /* ignore */ }
  }

  function onCreated(bill, submitted) {
    setShowCreate(false);
    const msg = bill.status === "posted" ? "langsung di-posting (match bersih)"
      : bill.status === "pending_approval" ? "menunggu approval (ada selisih)" : "disimpan sebagai draft";
    setNotice(`Vendor Bill ${bill.bill_number} dibuat — ${msg}.`);
    reload();
  }

  async function onAction(action, data) {
    const labels = { submit: "disubmit", approve: "disetujui & posted", reject: "ditolak", cancel: "dibatalkan", pay: "pembayaran dicatat" };
    setNotice(`${data.bill_number}: ${labels[action] || action}.`);
    setDetail(data);
    reload();
  }

  async function quickAct(bill, action, body) {
    try {
      const urls = {
        submit: `${API}/vendor-bills/${bill.id}/submit`,
        approve: `${API}/vendor-bills/${bill.id}/approve`,
      };
      const r = await axios.post(urls[action], body || {});
      const labels = { submit: "disubmit", approve: "disetujui & posted" };
      setNotice(`${r.data.bill_number}: ${labels[action] || action}.`);
      reload();
    } catch (e) {
      setError(e.response?.data?.detail || `Gagal ${action}.`);
    }
  }

  return (
    <div data-testid="vendor-bills-view" className="view-container">
      {notice && <div className="notice-bar success" data-testid="vb-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      <ErrorNotice message={error || paged.error} onRetry={reload} onDismiss={() => setError("")} testId="vb-error" />

      <PageHeader icon={Receipt} title={<span data-testid="vendor-bills-title">Tagihan Supplier (Vendor Bill)</span>}
        subtitle="Tagihan dicocokkan PO ↔ penerimaan ↔ bill (3-way matching); yang terposting menjadi hutang usaha sampai dibayar."
        actions={canCreate && (
          <button data-testid="create-vendor-bill-button" onClick={() => setShowCreate(true)} className="primary-button">
            <Plus size={14} /> Buat Tagihan
          </button>
        )} />

      {summary && (
        <MetricRow testId="vb-summary" items={[
          { label: "Total hutang (AP)", value: formatCurrency(summary.total_outstanding), icon: Wallet, tone: "#C0392B", hint: "belum dibayar", testId: "vb-summary-total" },
          { label: "Umur 0–30 hari", value: formatCurrency(summary.aging?.["0-30"]), icon: Clock },
          { label: "31–60 hari", value: formatCurrency(summary.aging?.["31-60"]), icon: Clock },
          { label: "61–90 hari", value: formatCurrency(summary.aging?.["61-90"]), icon: AlertTriangle, tone: "#B26A00" },
          { label: "> 90 hari", value: formatCurrency(summary.aging?.[">90"]), icon: AlertTriangle, tone: "#C0392B" },
        ]} />
      )}

      <SearchBox value={search} onChange={setSearch} testId="vb-search" placeholder="Cari no. tagihan / supplier / PO / inv. supplier…" />
      <StatusTabs value={tab} onChange={setTab} testId={(k) => `vb-tab-${k}`}
        tabs={TABS.map((t) => ({ ...t, count: counts[t.key] || 0 }))} />

      {loading ? (
        <div className="loading-state"><Loader2 size={22} className="spin" /><p>Memuat tagihan supplier…</p></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state" data-testid="vb-empty">
          <Scale size={30} style={{ opacity: 0.3 }} />
          <p className="font-semibold">{search || tab !== "all" ? "Tidak ada tagihan yang cocok dengan filter ini." : "Belum ada tagihan supplier."}</p>
          {canCreate && tab === "all" && <p className="text-sm text-muted">Buat tagihan dari PO yang sudah diterima untuk memulai 3-way matching.</p>}
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table" style={{ minWidth: 980 }}>
            <thead>
              <tr><th>Nomor</th><th>Supplier / PO</th><th className="text-right">Total</th><th className="text-right">Sisa</th><th>Pencocokan</th><th>Status</th><th>Inv. supplier</th><th className="text-right">Aksi</th></tr>
            </thead>
            <tbody>
              {filtered.map((b) => (
                <tr key={b.id} data-testid={`vb-row-${b.id}`} onClick={() => setDetail(b)} className="cursor-pointer">
                  <td><span className="font-mono font-semibold">{b.bill_number}</span></td>
                  <td className="max-w-[340px]">
                    <p className="truncate font-medium">{b.supplier_name}</p>
                    <p className="flex items-center gap-1 truncate text-xs text-muted"><EntityBadge entityId={b.entity_id} /><span className="truncate">{b.po_number || "—"} · {b.items?.length || 0} item</span></p>
                  </td>
                  <td className="text-right font-semibold tabular-nums">{formatCurrency(b.grand_total)}</td>
                  <td className={`text-right tabular-nums ${(b.financials?.outstanding ?? b.outstanding) > 0 ? "text-red-600" : "text-muted"}`}>{formatCurrency(b.financials?.outstanding ?? b.outstanding)}</td>
                  <td><MatchPill status={b.match_status} /></td>
                  <td><StatusPill status={b.status} /></td>
                  <td className="text-xs text-muted">{b.supplier_invoice_no || "—"}</td>
                  <td className="text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-1.5">
                      {b.status === "draft" && (
                        <button data-testid={`vb-quick-submit-${b.id}`} onClick={() => quickAct(b, "submit")} className="secondary-button !px-2 !py-1 text-[11px]"><Send size={11} /> Kirim</button>
                      )}
                      {b.status === "pending_approval" && canApprove && (
                        <button data-testid={`vb-quick-approve-${b.id}`} onClick={() => quickAct(b, "approve")} className="primary-button !px-2 !py-1 text-[11px]">Setujui</button>
                      )}
                      {b.status === "posted" && (
                        <button data-testid={`vb-quick-pay-${b.id}`} onClick={() => setDetail(b)} className="secondary-button !px-2 !py-1 text-[11px]"><Wallet size={11} /> Bayar</button>
                      )}
                      <button className="link-button" onClick={() => setDetail(b)} data-testid={`vb-open-${b.id}`}>Detail →</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <PaginationBar
        testId="vb-pager" label="tagihan"
        page={paged.page} pageSize={paged.pageSize} total={paged.total}
        hasMore={paged.hasMore} loading={paged.loading}
        onPrev={paged.prev} onNext={paged.next} onPageSize={paged.setPageSize}
        exportConfig={{ columns: CSV_COLUMNS, rows: filtered,
          fetchAll: paged.fetchAll, filename: "tagihan-supplier" }}
      />

      <VendorBillCreateModal
        open={showCreate}
        pos={pos}
        selectedEntity={selectedEntity}
        onClose={() => setShowCreate(false)}
        onCreated={onCreated}
        onError={(m) => setError(m)}
      />

      {detail && (
        <DetailModal onClose={() => setDetail(null)}
          label="Rincian tagihan supplier" testId="vb-detail-modal">
          <VendorBillDetailPanel
            bill={detail}
            canApprove={canApprove}
            currentUser={currentUser}
            onClose={() => setDetail(null)}
            onAction={onAction}
            onError={(m) => setError(m)}
          />
        </DetailModal>
      )}
    </div>
  );
}
