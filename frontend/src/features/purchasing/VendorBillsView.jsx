import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { moneyPost } from "../../utils/moneyRequest";
import { confirmBillApprove } from "../../utils/moneyConfirm";
import { useEntityScope } from "../../context/EntityScopeContext";
import useIntentKey from "../../hooks/useIntentKey";
import { Receipt, Plus, Send, Wallet, Scale, Clock, AlertTriangle, Loader2 } from "lucide-react";
import { PageHeader, MetricRow, SearchBox, StatusTabs } from "../../components/ListPageParts";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import EntityGatedButton from "../../components/EntityGatedButton";   // PK-42 (UX-05)
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
import { can } from "../../config/roles";
import { useCanDecideMap } from "../../hooks/useCanDecide";   // KP-T4
import useFocusDoc from "../../hooks/useFocusDoc";
import FocusNotice from "../../components/FocusNotice";
import { SupplierCardLink } from "../finance/cards/partyCards";   // MN-T3 — nama pemasok → kartu pemasok
import PaySupplierModal from "../finance/payments/PaySupplierModal";   // MN-T3 — satu form Bayar pemasok

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
// PK-41 (RP-07) — judul kelompok umur hutang dari server (`aging_labels`); cadangan = judul baku.
const AP_LABELS = { not_due: "Belum jatuh tempo", "1-30": "1–30 hari", "31-60": "31–60 hari", "61-90": "61–90 hari", ">90": "> 90 hari" };
function apLabel(summary, key) {
  return (summary?.aging_labels || []).find((b) => b.key === key)?.label || AP_LABELS[key];
}

/** PK-41 (RP-07) — kartu pencocokan sisa tagihan ↔ saldo akun hutang (angka rupiah utuh satu baris). */
function ApReconciliation({ rec }) {
  const rp = (v, testId) => <b className="whitespace-nowrap tabular-nums text-kn-text" data-testid={testId}>{formatCurrency(v || 0)}</b>;
  const beda = Math.abs(Number(rec.unexplained || 0)) >= 0.005;
  return (
    <div className="section-card section-pad mt-2 text-fs-12 text-kn-text-2" data-testid="vb-ap-reconciliation">
      <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
        <span>Tagihan belum lunas</span>{" "}{rp(rec.bills_outstanding, "vb-rec-bills")}
        {" "}<span>+ Biaya masuk belum dibayar</span>{" "}{rp(rec.landed_cost_outstanding, "vb-rec-landed")}
        {" "}<span>− Nota debit belum dipotong</span>{" "}{rp(rec.debit_notes_open, "vb-rec-debit")}
        {" "}<span>=</span>{" "}{rp(rec.expected_gl, "vb-rec-expected")}
        {" "}<span aria-hidden="true">·</span>{" "}<span>Saldo akun hutang</span>{" "}{rp(rec.gl_balance, "vb-rec-gl")}
      </p>
      <p className={`mt-0.5 ${beda ? "text-kn-danger-text" : "text-kn-success-text"}`} data-testid="vb-rec-unexplained">
        {beda
          ? <>Selisih belum dijelaskan <b className="whitespace-nowrap tabular-nums">{formatCurrency(rec.unexplained)}</b> — telusuri jurnal ke akun hutang di luar tagihan, biaya masuk, dan retur beli.</>
          : "Cocok dengan saldo akun hutang."}
      </p>
    </div>
  );
}

function MatchPill({ status }) {
  const map = { matched: ["pill-success", "Cocok"], warning: ["pill-warning", "Selisih"], blocked: ["pill-danger", "Lebih tagih"] };
  const [cls, label] = map[status] || ["pill-muted", "—"];
  return <span className={`status-pill ${cls}`}>{label}</span>;
}

// KP-T4 — parameter pertanyaan "boleh memutus?" untuk tagihan yang menunggu persetujuan.
const vbDecideParams = (b) => (b.status === "pending_approval"
  ? { docKind: b.bill_type === "campaign_expense" ? "vendor_bill.kampanye" : "vendor_bill", entityId: b.entity_id,
    amount: b.grand_total || b.total_amount || 0 } : null);

export default function VendorBillsView({ currentUser, selectedEntity, focusDoc, onClearFocus, onOpenDocument }) {
  const { entities } = useEntityScope();
  const [pos, setPos] = useState([]);
  const [summary, setSummary] = useState(null);
  const [counts, setCounts] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [detail, setDetail] = useState(null);
  // PK-12 — aksi cepat baris (Kirim / Setujui): satu niat per aksi = satu Idempotency-Key; tombol mati selama menunggu.
  const [quickBusy, setQuickBusy] = useState("");
  const quickIntents = { submit: useIntentKey("vbsub"), approve: useIntentKey("vbapv") };

  const canCreate = can(currentUser?.permissions, "vendor_bill", "create");   // POST /vendor-bills
  const canPay = can(currentUser?.permissions, "vendor_bill", "pay");   // MN-T3 — = POST /vendor-bills/{id}/pay
  const [payBill, setPayBill] = useState(null);

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
  // KP-T4 — boleh setujui/tolak = jawaban server (izin + Aturan Persetujuan), bukan peringkat peran di layar.
  const decide = useCanDecideMap(detail ? [...filtered, detail] : filtered, vbDecideParams);
  const canApproveDoc = (b) => !!(b && decide[b.id]?.allowed);

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

  // PK-44 (IA-04) — tautan dokumen (Jejak / Dokumen Terkait) membuka rincian tagihan ber-id itu.
  const fokus = useFocusDoc(focusDoc, "vendor_bill", async (id) => {
    const r = await axios.get(`${API}/vendor-bills/${id}`);
    setDetail(r.data);
  }, onClearFocus);

  function onCreated(bill, submitted) {
    setShowCreate(false);
    const msg = bill.status === "posted" ? "langsung terposting (cocok bersih)"
      : bill.status === "pending_approval" ? "menunggu persetujuan (ada selisih)" : "disimpan sebagai draf";
    setNotice(`Tagihan ${bill.bill_number} dibuat — ${msg}.`);
    reload();
  }

  async function onAction(action, data) {
    const labels = { submit: "dikirim", approve: "disetujui & terposting", reject: "ditolak", cancel: "dibatalkan", pay: "pembayaran dicatat" };
    setNotice(`${data.bill_number}: ${labels[action] || action}.`);
    setDetail(data);
    reload();
  }

  async function quickAct(bill, action, body) {
    if (quickBusy) return;
    // PK-13 (UX-03) — Setujui memposting hutang: tanya dulu (Kirim tetap langsung).
    if (action === "approve" && !(await confirmBillApprove(bill, entities))) return;
    setQuickBusy(`${bill.id}:${action}`);
    try {
      const urls = {
        submit: `${API}/vendor-bills/${bill.id}/submit`,
        approve: `${API}/vendor-bills/${bill.id}/approve`,
      };
      const payload = body || {};
      const r = await quickIntents[action].send({ id: bill.id, aksi: action, ...payload },
        (k) => moneyPost(urls[action], payload, k));
      const labels = { submit: "dikirim", approve: "disetujui & terposting" };
      setNotice(`${r.data.bill_number}: ${labels[action] || action}.`);
      reload();
    } catch (e) {
      setError(e.response?.data?.detail || `Gagal ${action}.`);
    } finally { setQuickBusy(""); }
  }

  return (
    <div data-testid="vendor-bills-view" className="view-container">
      {notice && <div className="notice-bar success" data-testid="vb-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      <ErrorNotice message={error || paged.error} onRetry={reload} onDismiss={() => setError("")} testId="vb-error" />
      <FocusNotice {...fokus} testId="vb-focus-notice" />

      <PageHeader icon={Receipt} title={<span data-testid="vendor-bills-title">Tagihan Supplier</span>}
        subtitle="Tagihan dicocokkan PO ↔ penerimaan ↔ tagihan (3-way matching); yang terposting menjadi hutang usaha sampai dibayar."
        actions={canCreate && (
          <EntityGatedButton selectedEntity={selectedEntity} what="membuat tagihan pemasok"
            data-testid="create-vendor-bill-button" onClick={() => setShowCreate(true)} className="primary-button">
            <Plus size={14} /> Buat Tagihan
          </EntityGatedButton>
        )} />

      {/* PK-41 (RP-07) — kelompok umur = hari LEWAT jatuh tempo; kelompok pertama "Belum jatuh tempo" (judul dari server). */}
      {summary && (
        <MetricRow testId="vb-summary" items={[
          { label: "Total hutang (AP)", value: formatCurrency(summary.total_outstanding), icon: Wallet, tone: "#C0392B", hint: "belum dibayar", testId: "vb-summary-total" },
          { label: apLabel(summary, "not_due"), value: formatCurrency(summary.aging?.not_due), icon: Clock, testId: "vb-summary-not-due" },
          { label: `Lewat ${apLabel(summary, "1-30")}`, value: formatCurrency(summary.aging?.["1-30"]), icon: Clock, testId: "vb-summary-1-30" },
          { label: `Lewat ${apLabel(summary, "31-60")}`, value: formatCurrency(summary.aging?.["31-60"]), icon: Clock },
          { label: `Lewat ${apLabel(summary, "61-90")}`, value: formatCurrency(summary.aging?.["61-90"]), icon: AlertTriangle, tone: "#B26A00" },
          { label: `Lewat ${apLabel(summary, ">90")}`, value: formatCurrency(summary.aging?.[">90"]), icon: AlertTriangle, tone: "#C0392B" },
        ]} />
      )}
      {summary?.reconciliation && <ApReconciliation rec={summary.reconciliation} />}

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
                    <p className="truncate font-medium"><SupplierCardLink id={b.supplier_id} name={b.supplier_name}
                      perms={currentUser?.permissions} testId={`vb-supplier-card-${b.id}`} /></p>
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
                        <button data-testid={`vb-quick-submit-${b.id}`} onClick={() => quickAct(b, "submit")} disabled={!!quickBusy} className="secondary-button !px-2 !py-1 text-[11px]"><Send size={11} /> Kirim</button>
                      )}
                      {b.status === "pending_approval" && canApproveDoc(b) && (
                        <button data-testid={`vb-quick-approve-${b.id}`} onClick={() => quickAct(b, "approve")} disabled={!!quickBusy} className="primary-button !px-2 !py-1 text-[11px]">Setujui</button>
                      )}
                      {b.status === "posted" && canPay && (b.financials?.outstanding ?? b.outstanding) > 0.01 && (
                        <button data-testid={`vb-quick-pay-${b.id}`} onClick={() => setPayBill(b)} className="secondary-button btn-sm whitespace-nowrap"><Wallet size={12} /> Bayar</button>
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
            canApprove={canApproveDoc(detail)}
            decideHint={decide[detail.id]?.message || ""}
            currentUser={currentUser}
            onClose={() => setDetail(null)}
            onAction={onAction}
            onError={(m) => setError(m)}
            onOpenDocument={onOpenDocument}
          />
        </DetailModal>
      )}
      {payBill && (
        <PaySupplierModal target={{ type: "vendor_bill", id: payBill.id }} onClose={() => setPayBill(null)}
          onPaid={(data, msg) => { setPayBill(null); setNotice(msg || `${payBill.bill_number}: pembayaran dicatat.`); if (data?.id) reload(); }} />
      )}
    </div>
  );
}
