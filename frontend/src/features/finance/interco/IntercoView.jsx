/**
 * FASE G-6 / G-6b — **TRANSAKSI ANTAR ENTITAS** (jual-beli antar-PT dalam grup).
 *
 * Masalah nyata yang diselesaikan layar ini: PT KSC menjual kain ke CV Kanda
 * dengan HARGA KHUSUS dan margin — bukan sekadar pindah gudang. Sebelum fase ini
 * antar-PT hidup sebagai `warehouse_transfers` at-cost sehingga tidak ada harga,
 * tidak ada margin, dan **tidak ada saldo antar-PT**.
 *
 *   1. Daftar Transaksi — dokumen kembar (SO+SJ+Invoice / PO+Vendor Bill)
 *   2. Saldo Antar-PT   — "CV Kanda utang berapa ke KSC?" + pengingat (G-6b)
 *   3. Settlement       — pelunasan sekaligus banyak transaksi (US6)
 *   4. Retur Antar-PT   — jalan resmi sesudah barangnya berpindah (G-6b)
 *   5. Rapor Margin     — margin grup: sudah vs belum terealisasi (G-6b)
 *
 * Pola UI 16 Nov (04_POLA_UI §2.A · masukan pemilik M35/M36): kepala SATU baris (keterangan di ?), kartu angka = jalan
 * cepat (klik → tab/daftar tersaring), status = dropdown (deret tab status dicabut), dan SATU tombol buat per layar di
 * bilah daftarnya: "+ Transaksi Baru" di Daftar Transaksi, "Buat Pelunasan" di Settlement, "Pinjaman Baru" di Pinjaman.
 * Dulu empat tombol (Muat ulang · Buat Pelunasan · Kontrak Internal · Transaksi Baru) di kepala halaman; Kontrak Internal
 * kini dibuka dari pop-up Transaksi Baru (isian Mode Harga).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  RefreshCw, ArrowRightLeft, Layers, Wallet, CheckCircle2, FileClock, Undo2, TrendingUp,
} from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import FocusNotice from "../../../components/FocusNotice";
import useFocusDoc, { gulirKe } from "../../../hooks/useFocusDoc";
import { formatCurrency } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { moneyPost } from "../../../utils/moneyRequest";
import useIntentKey from "../../../hooks/useIntentKey";
import { askConfirm } from "../../../services/confirmService";
import { can } from "../../../config/roles";
import useViewPreset from "../../../hooks/useViewPreset";   // PK-43 — tautan daftar periksa tutup buku membuka tab saldo
import IntercoCreateModal from "./IntercoCreateModal";
import IntercoSettlementModal from "./IntercoSettlementModal";
import IntercoRefundModal from "./IntercoRefundModal";   // PK-31 (IC-07) — refund retur sesudah lunas
import IntercoPaymentSchedule from "./IntercoPaymentSchedule";
import IntercoDetailPanel from "./IntercoDetailPanel";
import InternalContractWizardModal from "./InternalContractWizardModal";
import IntercoCancelModal from "./IntercoCancelModal";
import IntercoTaxModal from "./IntercoTaxModal";
import IntercoReturnModal from "./IntercoReturnModal";
import IntercoReturnsPanel from "./IntercoReturnsPanel";
import IntercoReturnInbox from "./IntercoReturnInbox";
import IntercoMarginPanel from "./IntercoMarginPanel";
// FASE E-7 (E7f) — pinjaman uang antar-PT (dokumen kembar + eliminasi non-dagang).
import IntercoLoansPanel from "./IntercoLoansPanel";
import IntercoChargesPanel from "./IntercoChargesPanel";   // KM-T4 — tagihan insentif antar-PT (tab Pinjaman Antar-PT)
import { TransactionsPanel, BalancesPanel, SettlementsPanel } from "./IntercoPanels";
import DetailModal from "../../../components/DetailModal";
import DesktopOnlyNotice from "../../../components/DesktopOnlyNotice";
import { PageHeader, MetricRow } from "../../../components/ListPageParts";
import { OPEN_STATUS_FILTER } from "./intercoApi";

const TABS = [
  { id: "transactions", label: "Daftar Transaksi", icon: ArrowRightLeft },
  { id: "balances",     label: "Saldo Antar-PT",   icon: Wallet },
  { id: "settlements",  label: "Settlement",       icon: Layers },
  { id: "schedule",     label: "Jadwal Bayar",     icon: Layers },
  // G1-32 — "Retur Antar-PT" sama dengan judul halaman; sub-tab = arah retur.
  { id: "returns",      label: "Retur Keluar",     icon: Undo2 },
  { id: "return-inbox", label: "Retur Masuk",      icon: Undo2 },
  { id: "loans",        label: "Pinjaman Antar-PT", icon: Wallet },
  { id: "margin",       label: "Rapor Margin",     icon: TrendingUp },
];

// PK-17 — petunjuk kartu saldo bila server menyembunyikannya (`summary.finance_hidden`).
const FINANCE_HIDDEN_HINT = "khusus izin keuangan antar-PT";

// Keterangan halaman (dulu paragraf di bawah judul + keterangan panjang di tiap kartu) — kini di ikon ?.
export const TEKS_ANTAR_PT = "Jual-beli antar-PT dengan harga internal & margin. Dokumen kembar (PO internal ↔ "
  + "SO+Surat Jalan+Invoice) + faktur pajak internal + saldo pasangan PT + pelunasan (netting) + retur — barang fisik tetap "
  + "lewat jalur gudang. Kartu piutang/utang = posisi BERSIH dua arah per pasangan PT (keputusan K-07); angka bruto per "
  + "dokumen ada di Jadwal Bayar. Dokumen terbuka = dikonfirmasi s/d difakturkan, belum lunas (draf tidak dihitung). "
  + "Rugi belum terealisasi tidak dieliminasi (konservatisme). Kontrak internal (harga tetap) dibuat dari pop-up "
  + "Transaksi Baru.";

// Tab yang bicara UANG antar-PT — dipagari izin `interco_finance` (E-0/E0.8f).
const MONEY_TABS = ["balances", "settlements", "schedule", "loans", "margin"];
// L08 — tab retur tampil di menu Retur terpadu (view `interco-returns`), bukan di layar transaksi.
const RETURN_TABS = ["returns", "return-inbox"];

// PK-44 (IA-04) — jenis dokumen antar-PT → [tab = jalur API rincian, `data-testid` baris yang disorot].
const FOCUS_TAB = { interco_transaction: ["transactions", ""], interco_settlement: ["settlements", "interco-set"],
  interco_return: ["returns", "interco-ret"], interco_loan: ["loans", "loan-row"],
  interco_charge: ["loans", "charge-row"] };   // KM-T4 — tagihan insentif antar-PT (rincian `GET /interco/charges/{id}`)

export default function IntercoView({ currentUser, selectedEntity, entities = [], only = null, focusDoc, onClearFocus }) {
  const [tab, setTab] = useState(() => {
    const hint = new URLSearchParams(window.location.search).get("tab") || sessionStorage.getItem("interco_tab");
    sessionStorage.removeItem("interco_tab");
    return (only && !only.includes(hint) ? only[0] : hint) || "transactions";
  });
  useViewPreset(only ? "" : "interco-transactions", (p) => { if (p.tab) setTab(p.tab); });
  const [rows, setRows] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [returns, setReturns] = useState([]);
  const [margin, setMargin] = useState(null);
  const [summary, setSummary] = useState(null);
  const [fStatus, setFStatus] = useState("");
  const [fRole, setFRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [showSettle, setShowSettle] = useState(null);
  const [showRefund, setShowRefund] = useState(null);
  const [showContract, setShowContract] = useState(null);
  const [detailId, setDetailId] = useState(null);
  const [cancelDoc, setCancelDoc] = useState(null);
  const [taxDoc, setTaxDoc] = useState(null);
  const [returnDoc, setReturnDoc] = useState(null);
  // PK-12 — aksi baris (langkah transaksi, aksi retur, pengingat) berkunci Idempotency-Key per niat. Tombolnya ada di
  // panel anak; `sending` menolak klik kedua selama jawaban belum datang.
  const advanceIntent = useIntentKey("ic-step");
  const retIntent = useIntentKey("icr-aksi");
  const remindIntent = useIntentKey("ic-ingat");
  const sending = useRef(false);

  const role = (currentUser?.role || "").toLowerCase();
  // FASE E-8 (E8.1) — wewenang dibaca dari IZIN EFEKTIF pengguna (dikirim server saat
  // login), bukan dari daftar nama peran. Dulu `["admin","manager"].includes(role)`:
  // begitu peran `sales_admin` lahir dengan izin `interco.create`, tombolnya tetap mati
  // padahal server mengizinkan — pengguna menyangka dirinya tidak berwenang.
  const perms = currentUser?.permissions || {};
  const canWrite = can(perms, "interco", "create");
  // Cek UI UAT v3 (S7) — tombol langkah mengikuti izin AKSI-nya di server (confirm=approve, tugas gudang=ship,
  // faktur=invoice). Dulu [Buat Tugas Gudang] tampil untuk Admin Sales (ditolak interco.ship) & tersembunyi bagi Gudang.
  const STEP_PERM = { confirm: "approve", "warehouse-task": "ship", invoice: "invoice" };
  const canStep = (step) => (step?.action ? can(perms, "interco", STEP_PERM[step.action] || "create") : canWrite);
  // Sisi UANG antar-PT (saldo pasangan PT, settlement/netting, pinjaman, rapor margin)
  // dipagari izin TERSENDIRI `interco_finance` sejak E-0/E0.8f. Tanpa penyaringan tab
  // di bawah, peran yang hanya mengurus BARANG (Admin Sales, gudang) akan membuka tab
  // yang pasti 403 — layar penuh galat merah yang bukan salah penggunanya.
  const canMoney = can(perms, "interco_finance", "view");
  // Audit UI 24 Okt (035) — dibuka dari menu Retur (view `interco-returns`): layar ini berkonteks RETUR,
  // bukan halaman "Transaksi Antar Entitas" utuh (dulu judul, KPI uang, Settlement & Transaksi Baru ikut tampil).
  const returnsMode = Array.isArray(only) && only.length > 0 && only.every((t) => RETURN_TABS.includes(t));
  const tabs = TABS.filter((t) => (canMoney || !MONEY_TABS.includes(t.id))
    && (only ? only.includes(t.id) : !RETURN_TABS.includes(t.id)));
  // `selectedEntity` dari App adalah ID string ("all" = semua PT); objek {id} tetap didukung.
  // Dulu hanya membaca `.id` → selalu "" → penjual bawaan = PT pertama & daftar tidak ikut PT aktif.
  const entityId = typeof selectedEntity === "string"
    ? (selectedEntity === "all" ? "" : selectedEntity)
    : (selectedEntity?.id || "");

  useEffect(() => {
    // Kalau tab aktif ternyata tidak boleh dilihat peran ini, pindahkan ke tab pertama
    // yang sah (mis. deep-link `&tab=margin` dibuka Admin Sales).
    if (!tabs.some((t) => t.id === tab)) setTab(tabs[0]?.id || "transactions");
  }, [tabs, tab]);

  const refresh = useCallback(async () => {
    setBusy(true); setErr("");
    try {
      if (returnsMode) {   // menu Retur: cukup daftar retur antar-PT (tanpa ringkasan uang/transaksi)
        const rt = await axios.get(`${API}/interco/returns`, { params: { entity_id: entityId } });
        setReturns(rt.data || []);
        return;
      }
      const params = { entity_id: entityId, status: fStatus, role: fRole };
      const money = (url, cfg) => (canMoney
        ? axios.get(url, cfg)
        : Promise.resolve({ data: null }));
      const [s, t, a, st, rt, mg] = await Promise.all([
        axios.get(`${API}/interco/summary`, { params: { entity_id: entityId } }),
        axios.get(`${API}/interco/transactions`, { params }),
        money(`${API}/interco/accounts`),
        money(`${API}/interco/settlements`, { params: { entity_id: entityId } }),
        axios.get(`${API}/interco/returns`, { params: { entity_id: entityId } }),
        money(`${API}/interco/margin-report`, { params: { entity_id: entityId } }),
      ]);
      setSummary(s.data);
      setRows(t.data || []);
      setAccounts(a.data || []);
      setSettlements(st.data || []);
      setReturns(rt.data || []);
      setMargin(mg.data || null);
    } catch (e) { setErr(apiErrorText(e)); }
    finally { setBusy(false); }
  }, [entityId, fStatus, fRole, canMoney, returnsMode]);

  useEffect(() => { refresh(); }, [refresh]);

  const showMsg = (t) => { setMsg(t); setTimeout(() => setMsg(""), 4000); };

  const LANGKAH_PESAN = {
    confirm: "dikonfirmasi — jurnal terbit di kedua buku PT",
    ship: "ditandai terkirim",
    invoice: "difakturkan (faktur internal terbit)",
    "warehouse-task": "punya tugas gudang — minta gudang menyetujui perpindahannya",
  };

  const advance = async (doc, action) => {
    if (!action || sending.current) return;
    // UAT 24 Okt (audit UI tahap 2) — G1-29: Konfirmasi menerbitkan jurnal di DUA buku PT → wajib dialog.
    if (action === "confirm") {
      const seller = doc.seller_entity_name || "PT penjual";
      const buyer = doc.buyer_entity_name || "PT pembeli";
      const ok = await askConfirm({
        danger: true,
        title: `Konfirmasi ${doc.number}?`,
        message: `Jurnal terbit di buku ${seller} (piutang antar-PT) dan ${buyer} (utang antar-PT) senilai `
          + `${formatCurrency(doc.grand_total || 0)}. Setelah dikonfirmasi, pembatalan harus membalik jurnal.`,
        confirmLabel: "Konfirmasi & Terbitkan Jurnal",
      });
      if (!ok || sending.current) return;
    }
    sending.current = true;
    setBusy(true); setErr("");
    try {
      const r = await advanceIntent.send({ id: doc.id, aksi: action, note: "" },
        (k) => moneyPost(`${API}/interco/transactions/${doc.id}/${action}`, { note: "" }, k));
      if (action === "warehouse-task") {
        showMsg(`Tugas gudang ${r.data?.code || ""} terbit untuk ${doc.number} — `
                + "gudang yang menyetujui perpindahan barangnya");
      } else {
        showMsg(`Transaksi ${doc.number} ${LANGKAH_PESAN[action] || action}`);
      }
      refresh();
    } catch (e) { setErr(apiErrorText(e)); }
    finally { sending.current = false; setBusy(false); }
  };

  const retAct = async (ret, action, body = { note: "" }, okMsg = "") => {
    if (sending.current) return;
    sending.current = true;
    setBusy(true); setErr("");
    try {
      const r = await retIntent.send({ id: ret.id, aksi: action, ...body },
        (k) => moneyPost(`${API}/interco/returns/${ret.id}/${action}`, body, k));
      showMsg(okMsg || `Retur ${ret.number} diperbarui`);
      if (action === "warehouse-task") {
        showMsg(`Tugas gudang balik ${r.data?.code || ""} terbit untuk ${ret.number} — `
                + "gudang yang menyetujui pengembalian barangnya");
      }
      refresh();
    } catch (e) { setErr(apiErrorText(e)); }
    finally { sending.current = false; setBusy(false); }
  };

  const remind = async (acc) => {
    if (sending.current) return;
    sending.current = true;
    setBusy(true); setErr("");
    try {
      const r = await remindIntent.send(
        { id: `${acc.from_entity_id}|${acc.to_entity_id}`, aksi: "remind", note: "" },
        (k) => moneyPost(`${API}/interco/accounts/${acc.from_entity_id}/${acc.to_entity_id}/remind`,
          { note: "" }, k));
      const d = r.data || {};
      showMsg(d.deduped
        ? `Pengingat untuk ${d.payer_entity_name} → ${d.payee_entity_name} sudah ada `
          + "dan belum dibaca — tidak dikirim dua kali"
        : `Pengingat terkirim: saldo ${formatCurrency(d.outstanding)} menganggur `
          + `${d.idle_days} hari (batas ${d.limit_days} hari)`);
      refresh();
    } catch (e) { setErr(apiErrorText(e)); }
    finally { sending.current = false; setBusy(false); }
  };

  // K-07 — angka utama = posisi BERSIH dua arah per pasangan PT; bruto per dokumen di keterangan kartu & Jadwal Bayar.
  // PK-17 (IA-09) — tanpa izin keuangan antar-PT server mengosongkan saldo (`finance_hidden`).
  const hidden = Boolean(summary?.finance_hidden);
  const unrealized = margin?.totals?.unrealized_margin || 0;
  const openFilter = tab === "transactions" && fStatus === OPEN_STATUS_FILTER;
  const kpiCards = [
    { testId: "interco-kpi-receivable", label: "Piutang antar-PT (bersih)", icon: Wallet, tab: "balances",
      value: hidden ? "—" : formatCurrency((summary?.net_receivable ?? summary?.total_receivable) || 0),
      hint: hidden ? FINANCE_HIDDEN_HINT : `bruto ${formatCurrency(summary?.total_receivable || 0)}`,
      isActive: tab === "balances", go: () => setTab("balances") },
    { testId: "interco-kpi-payable", label: "Utang antar-PT (bersih)", icon: Wallet, tab: "schedule",
      value: hidden ? "—" : formatCurrency((summary?.net_payable ?? summary?.total_payable) || 0),
      hint: hidden ? FINANCE_HIDDEN_HINT : `bruto ${formatCurrency(summary?.total_payable || 0)}`,
      isActive: tab === "schedule", go: () => setTab("schedule") },
    { testId: "interco-kpi-open", label: "Dokumen terbuka", icon: FileClock, tab: "transactions",
      value: String(summary?.open_documents || 0), hint: "belum lunas",
      isActive: openFilter,
      go: () => { setTab("transactions"); setFStatus(openFilter ? "" : OPEN_STATUS_FILTER); } },
    { testId: "interco-kpi-unrealized", label: "Margin belum terealisasi", icon: TrendingUp, tab: "margin",
      value: formatCurrency(unrealized), hint: unrealized < 0 ? "rugi — tidak dieliminasi" : "dieliminasi saat konsolidasi",
      isActive: tab === "margin", go: () => setTab("margin") },
  ];

  // PK-44 (IA-04) — tautan dokumen: pindah ke tab jenisnya; transaksi → rinciannya, lainnya → baris disorot.
  const [sorot, setSorot] = useState("");
  const fokus = useFocusDoc(focusDoc, Object.keys(FOCUS_TAB), async (id, fd) => {
    const [t, row] = FOCUS_TAB[fd.focus_type];
    await axios.get(`${API}/interco/${fd.focus_type === "interco_charge" ? "charges" : t}/${id}`);
    if (!tabs.some((x) => x.id === t)) return false;   // tab di luar izin/menu layar ini
    setTab(t);
    if (row) { setSorot(id); gulirKe(`${row}-${id}`, 600); } else setDetailId(id);
  }, onClearFocus);

  return (
    <>
    {/* Fase 3 · P4 (L-04 kelas C) — akuntansi grup: di HP cukup banner "paling nyaman di desktop" (layar tetap
        jalan). Di luar wadah `space-y-*` supaya banner yang tersembunyi di desktop tidak menambah jarak atas. */}
    {!returnsMode && <DesktopOnlyNotice testId="interco-desktop-notice" what="Antar Entitas (grup)" />}
    <div className="space-y-3" data-testid="interco-view">
      {returnsMode ? (
        <>
          <PageHeader icon={Undo2} testId="interco-returns-header"
            title={<span data-testid="interco-returns-title">Retur Antar-PT</span>}
            subtitle="Retur barang yang sudah berpindah antar-PT dalam grup: retur yang diajukan PT Anda (keluar) dan retur yang masuk ke PT Anda."
            actions={(
              <button onClick={refresh} disabled={busy} data-testid="interco-refresh-btn" className="secondary-button">
                <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Muat ulang
              </button>
            )} />
          <MetricRow testId="interco-returns-stats" items={[
            { label: "Total retur antar-PT", value: returns.length, icon: Undo2, hint: "keluar & masuk" },
            { label: "Draf", value: returns.filter((r) => r.status === "draft").length, icon: Layers, hint: "menunggu persetujuan rekan" },
            { label: "Disetujui", value: returns.filter((r) => r.status === "approved").length, icon: CheckCircle2, hint: "barang belum kembali" },
            { label: "Barang sudah kembali", value: returns.filter((r) => r.status === "completed").length, icon: CheckCircle2, tone: "#1B7F4B" },
          ]} />
        </>
      ) : (
      <>
      <PageHeader icon={ArrowRightLeft} testId="interco-header"
        title={<span data-testid="interco-title">Transaksi Antar-PT</span>} help={TEKS_ANTAR_PT}
        actions={(
          <button type="button" onClick={refresh} disabled={busy} data-testid="interco-refresh-btn" className="icon-button"
            aria-label="Muat ulang" title="Muat ulang">
            <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
          </button>
        )} />

      {/* Kartu angka = jalan cepat (pola UI §1.5): piutang → Saldo Antar-PT, utang → Jadwal Bayar, dokumen terbuka →
          Daftar Transaksi tersaring "Terbuka", margin → Rapor Margin. Tab di luar izin → kartu tanpa klik. */}
      <MetricRow testId="interco-kpis" items={kpiCards.map((c) => ({
        label: c.label, value: c.value, hint: c.hint, icon: c.icon, testId: c.testId,
        active: c.isActive,
        onClick: tabs.some((t) => t.id === c.tab) ? c.go : undefined,
      }))} />
      </>
      )}

      {err && <ErrorNotice message={err} onDismiss={() => setErr("")} />}
      <FocusNotice {...fokus} testId="interco-focus-notice" />
      {msg && (
        <div className="notice-bar success" data-testid="interco-msg">
          <CheckCircle2 size={14} /> {msg}
        </div>
      )}

      {/* Tab = pindah LAYAR (Daftar Transaksi, Saldo, Settlement, …), bukan saringan. Tetap bilah lama: berkas ini juga
          dirender sebagai tab hub `interco-returns`, jadi `PageTabs` di sini = tab tingkat ketiga (INV-UI-14). */}
      <div className="border-b border-[#E5E5EA] flex gap-1 flex-wrap">
        {tabs.map((t) => {
          const I = t.icon;
          const active = tab === t.id;
          return (
            <button key={t.id} onClick={() => setTab(t.id)} data-testid={`interco-tab-${t.id}`}
                    className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition ${
                      active ? "border-[#0F172A] text-[#0F172A]"
                             : "border-transparent text-[#6E6E73] hover:text-[#1D1D1F]"}`}>
              <I size={15} /> {t.label}
              {t.id === "returns" && returns.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] bg-[#F2F2F5] text-[#5A5A60]">
                  {returns.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {tab === "transactions" && (
        <TransactionsPanel
          rows={rows} fStatus={fStatus} fRole={fRole}
          setFStatus={setFStatus} setFRole={setFRole}
          onAdvance={advance} onView={(r) => setDetailId(r.id)}
          onCancel={(r) => setCancelDoc(r)}
          onTax={(r) => setTaxDoc(r)} onReturn={(r) => setReturnDoc(r)}
          canWrite={canWrite}
          canStep={canStep}
          onCreate={canWrite ? () => setShowCreate(true) : undefined}
        />
      )}
      {tab === "balances" && (
        <BalancesPanel
          accounts={accounts} canWrite={canWrite} onRemind={remind}
          netPairs={summary?.net_pairs}
          onNetting={(a) => setShowSettle({ open: true, from: a.from_entity_id,
                                            to: a.to_entity_id })}
          canRefund={can(perms, "interco", "settle")}
          onRefund={(a) => setShowRefund({ payer: a.from_entity_id, payee: a.to_entity_id })}
        />
      )}
      {tab === "settlements" && (
        <SettlementsPanel rows={settlements} focusId={sorot}
          onCreate={can(perms, "interco", "settle") ? () => setShowSettle({ open: true }) : undefined} />
      )}
      {tab === "schedule" && <IntercoPaymentSchedule selectedEntity={selectedEntity} entities={entities} />}
      {tab === "returns" && (
        <IntercoReturnsPanel
          rows={returns} canWrite={canWrite} focusId={sorot} loading={busy}
          canDecideRolls={can(perms, "interco", "decide_rolls")} activeEntityId={entityId}
          onChanged={refresh}
          onApprove={async (r) => {
            // G1-32 — Setujui menerbitkan nota retur + nota kredit (jurnal pembalik) di dua buku PT.
            const ok = await askConfirm({
              danger: true,
              title: `Setujui retur ${r.number}?`,
              message: "Nota retur & nota kredit terbit dan jurnal pembalik dibuat di buku kedua PT "
                + `(nilai ${formatCurrency(r.total_value ?? r.grand_total ?? r.subtotal ?? 0)}).`,
              confirmLabel: "Setujui Retur",
            });
            if (ok) retAct(r, "approve", { note: "" }, `Retur ${r.number} disetujui — jurnal pembalik terbit di kedua buku PT`);
          }}
          onTask={(r) => retAct(r, "warehouse-task", { note: "" })}
          onCancel={(r, reason) => retAct(r, "cancel", { reason },
            `Draf retur ${r.number} dibatalkan`)}
        />
      )}
      {tab === "return-inbox" && (
        <IntercoReturnInbox entityId={entityId}
          canAct={can(perms, "interco", "approve") || can(perms, "interco", "receive") || can(perms, "sales_return", "approve")} />
      )}
      {tab === "loans" && (
        <div className="space-y-6">
          <IntercoLoansPanel entities={entities} entityId={entityId} canWrite={canWrite} focusId={sorot} />
          <IntercoChargesPanel entityId={entityId} focusId={sorot}
            allowedEntityIds={Array.isArray(currentUser?.allowed_entity_ids) ? currentUser.allowed_entity_ids : null} />
        </div>
      )}
      {tab === "margin" && <IntercoMarginPanel report={margin} entityId={entityId} />}

      {showCreate && (
        <IntercoCreateModal
          entities={entities} currentEntityId={entityId}
          canOverride={can(perms, "interco", "override_terms")}
          onOpenContract={({ seller, buyer }) => { setShowCreate(false); setShowContract({ open: true, seller, buyer, fromCreate: true }); }}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); showMsg("Transaksi antar-PT diterbitkan"); refresh(); }}
        />
      )}
      {showSettle?.open && (
        <IntercoSettlementModal
          entities={entities} presetPayerEntityId={showSettle.from || entityId} presetPayeeEntityId={showSettle.to || ""}
          onClose={() => setShowSettle(null)}
          onCreated={() => { setShowSettle(null); showMsg("Pelunasan antar-PT terbit"); refresh(); }}
        />
      )}
      {showRefund && (
        <IntercoRefundModal
          entities={entities} presetPayerEntityId={showRefund.payer} presetPayeeEntityId={showRefund.payee}
          onClose={() => setShowRefund(null)}
          onCreated={(r) => {
            setShowRefund(null);
            showMsg(`Pengembalian dana ${r?.number || ""} ${formatCurrency(r?.total_applied || 0)} tercatat — kas & jurnal terbit di kedua PT`);
            refresh();
          }}
        />
      )}
      {showContract?.open && (
        <InternalContractWizardModal
          entities={entities} sellerEntityId={showContract.seller || entityId}
          buyerEntityId={showContract.buyer || ""}
          onClose={() => setShowContract(null)}
          onCreated={() => {
            const lanjut = Boolean(showContract.fromCreate);
            setShowContract(null); showMsg("Kontrak internal diterbitkan"); refresh();
            if (lanjut) setShowCreate(true);   // kembali ke pop-up Transaksi Baru yang tadi membuka wizard
          }}
        />
      )}
      {detailId && (
        <DetailModal onClose={() => setDetailId(null)}
          label="Rincian transaksi antar-PT" testId="interco-detail-modal">
          <IntercoDetailPanel intercoId={detailId} currentUser={currentUser} onClose={() => setDetailId(null)} />
        </DetailModal>
      )}
      {cancelDoc && (
        <IntercoCancelModal
          doc={cancelDoc} onClose={() => setCancelDoc(null)}
          onCancelled={(res) => {
            setCancelDoc(null);
            const n = res?.reversed_journals || 0;
            showMsg(n > 0
              ? `Transaksi dibatalkan — ${n} jurnal dibalik di kedua buku PT`
              : "Draf transaksi dibatalkan");
            refresh();
          }}
        />
      )}
      {taxDoc && (
        <IntercoTaxModal
          doc={taxDoc} onClose={() => setTaxDoc(null)}
          onDone={() => { showMsg("Faktur pajak internal diperbarui"); refresh(); }}
        />
      )}
      {returnDoc && (
        <IntercoReturnModal
          doc={returnDoc} onClose={() => setReturnDoc(null)}
          onCreated={(res) => {
            setReturnDoc(null);
            showMsg(`Retur ${res?.returner?.number || ""} dibuat sebagai draf — minta rekan `
                    + "lain menyetujuinya (pembuat ≠ penyetuju). Lihat di menu Retur › Retur Antar-PT");
            if (tabs.some((t) => t.id === "returns")) setTab("returns");
            refresh();
          }}
        />
      )}
    </div>
    </>
  );
}
