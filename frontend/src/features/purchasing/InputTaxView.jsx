import { apiErrorText } from "../../utils/apiError";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import KNMonthPicker from "@/components/KNMonthPicker";
import { can } from "../../config/roles";
import { Percent, Plus, Ban, Layers, Landmark } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import { SearchBox } from "../../components/ListControls";
import FormModal from "../../components/FormModal";
import LinkCard from "../../components/LinkCard";
import ResponsiveTable from "../../components/ResponsiveTable";
import useViewPreset from "../../hooks/useViewPreset";
import InputTaxCreateModal from "./InputTaxCreateModal";

/**
 * InputTaxView (Fase 5.5 — P0-3) — Faktur Pajak Masukan (Input VAT).
 * Catat Faktur Pajak Masukan dari Vendor Bill ber-PPN (NSFP + dedupe).
 *
 * Fase 3 · P4 (D-20) — rekap PPN Masukan vs Keluaran dulu tampil DUA kali di layar ini (4 kartu ringkasan di atas +
 * tab "Rekap PPN" dengan urutan terbalik) dan sekali lagi di Pajak › Pajak (PPN & PPh). Kini rekap/posisi PPN hanya di
 * `cs-pajak`; layar ini = DAFTAR faktur masukan + satu baris "Posisi PPN periode ini" yang menautkan ke sana
 * (baca-saja bila peran tidak boleh membuka). Daftar bisa disaring per masa pajak — tautan dari Pajak membawa
 * periodenya (preset `{ period }`).
 * L-03: dialog Batal (`.modal-card`) → FormModal. Daftar grid lebar → ResponsiveTable (kartu di HP 390 px).
 */
const STATUS_TABS = [
  { key: "all", label: "Semua" },
  { key: "recorded", label: "Tercatat" },
  { key: "cancelled", label: "Batal" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
function fmtPeriod(p) {
  if (!p || p.length !== 7) return p || "—";
  const [y, m] = p.split("-");
  return `${MONTHS[Number(m) - 1] || m} ${y}`;
}

function currentPeriod() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function StatusPill({ status }) {
  const map = { recorded: ["pill-success", "Tercatat"], cancelled: ["pill-muted", "Batal"] };
  const [cls, label] = map[status] || ["pill-muted", status];
  return <span className={`status-pill ${cls}`}>{label}</span>;
}

export default function InputTaxView({ currentUser, selectedEntity }) {
  const [vouchers, setVouchers] = useState([]);
  const [bills, setBills] = useState([]);
  const [summary, setSummary] = useState(null);
  const preset = useViewPreset("input-tax", (p) => {
    if (p.period) { setPeriod(p.period); setPeriodFilter(p.period); }
  });
  const [period, setPeriod] = useState(() => preset?.period || currentPeriod());
  // "" = semua masa pajak; tautan dari Pajak (PPN & PPh) mengisi masa yang sama.
  const [periodFilter, setPeriodFilter] = useState(() => preset?.period || "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [cancelTarget, setCancelTarget] = useState(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelErr, setCancelErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");

  // FASE E-8 — pajak MASUKAN ada di sisi HUTANG: tetap manajer/admin (keputusan
  // pemilik: jangan diperluas ke Finance sendiri), tapi diputuskan oleh IZIN.
  const canCreate = can(currentUser?.permissions || {}, "input_tax", "create");

  useEffect(() => { loadAll(); }, [selectedEntity]); // eslint-disable-line
  useEffect(() => { loadSummary(); }, [period, selectedEntity]); // eslint-disable-line

  function entParams() {
    return (selectedEntity && selectedEntity !== "all") ? { entity_id: selectedEntity } : {};
  }

  async function loadAll() {
    setLoading(true);
    try {
      const [vRes, bRes] = await Promise.all([
        axios.get(`${API}/input-tax-invoices`, { params: entParams() }),
        axios.get(`${API}/input-tax-invoices/eligible-bills`, { params: entParams() }).catch(() => ({ data: [] })),
      ]);
      setVouchers(Array.isArray(vRes.data) ? vRes.data : []);
      setBills(Array.isArray(bRes.data) ? bRes.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat Faktur Pajak Masukan."));
    } finally { setLoading(false); }
  }

  async function loadSummary() {
    try {
      const params = { period, ...entParams() };
      const r = await axios.get(`${API}/tax/vat-summary`, { params });
      setSummary(r.data);
    } catch { setSummary(null); }
  }

  function onCreated(v) {
    setShowCreate(false);
    setNotice(`Faktur Masukan ${v.number} dicatat (NSFP ${v.nsfp}).`);
    loadAll(); loadSummary();
  }

  async function doCancel() {
    if (!cancelTarget || !cancelReason.trim()) return;
    setBusy(true); setCancelErr("");
    try {
      const r = await axios.post(`${API}/input-tax-invoices/${cancelTarget.id}/cancel`, { reason: cancelReason.trim() });
      setNotice(`${r.data.number}: faktur masukan dibatalkan.`);
      setCancelTarget(null); setCancelReason("");
      loadAll(); loadSummary();
    } catch (e) {
      setCancelErr(apiErrorText(e, "Gagal membatalkan."));
    } finally { setBusy(false); }
  }

  const inPeriod = useMemo(() => vouchers.filter((v) => !periodFilter || v.period === periodFilter),
    [vouchers, periodFilter]);
  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    return inPeriod.filter((v) => (tab === "all" || v.status === tab)
      && (!t || [v.number, v.nsfp, v.supplier_name, v.bill_number, v.po_number].some((x) => String(x || "").toLowerCase().includes(t))));
  }, [inPeriod, tab, q]);
  const counts = useMemo(() => STATUS_TABS.reduce((acc, t) => ({
    ...acc, [t.key]: t.key === "all" ? inPeriod.length : inPeriod.filter((v) => v.status === t.key).length,
  }), {}), [inPeriod]);

  const positionText = summary
    ? `${summary.position_label || (summary.position === "kurang_bayar" ? "Kurang Bayar" : summary.position === "lebih_bayar" ? "Lebih Bayar" : "Nihil")} ${formatCurrency(Math.abs(summary.net_ppn || 0))}`
    : "memuat…";

  const columns = [
    { key: "number", header: "Nomor", mobile: "title",
      render: (v) => <span className="text-[11.5px] font-bold text-[#0058CC]">{v.number}</span> },
    { key: "status", header: "Status", mobile: "badge", render: (v) => <StatusPill status={v.status} /> },
    { key: "nsfp", header: "NSFP / Supplier", mobile: "subtitle",
      render: (v) => (
        <div className="min-w-0">
          <p className="text-[12px] font-semibold tabular-nums" data-testid={`it-nsfp-${v.id}`}>{v.nsfp_display || v.nsfp}</p>
          <p className="text-[10.5px] text-[#6B6B73]">{v.supplier_name || "—"}</p>
        </div>
      ) },
    { key: "ppn_amount", header: "PPN", align: "right", priority: 1,
      render: (v) => <b className="tabular-nums">{formatCurrency(v.ppn_amount)}</b> },
    { key: "dpp", header: "DPP", align: "right", priority: 2, render: (v) => formatCurrency(v.dpp) },
    { key: "period", header: "Masa", priority: 3, render: (v) => fmtPeriod(v.period) },
    { key: "bill", header: "Tagihan / PO", priority: 4,
      render: (v) => (
        <div className="min-w-0">
          <p className="text-[11px]">{v.bill_number || "—"}</p>
          <p className="text-[10.5px] text-[#6B6B73]">{v.po_number || "—"}</p>
        </div>
      ) },
  ];

  return (
    <div data-testid="input-tax-view">
      {notice && <div className="notice-bar success" data-testid="it-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={loadAll} onDismiss={() => setError("")} testId="it-error" />

      {/* D-20 — SATU baris posisi PPN + tautan ke rekap PPN (Pajak › Pajak (PPN & PPh)). */}
      <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="it-ppn-position">
        <div className="w-[170px]">
          <KNMonthPicker data-testid="it-period-input" value={period} onChange={(v) => setPeriod(v || period)} />
        </div>
        <div className="min-w-0 flex-1">
          <LinkCard testId="it-ppn-link" icon={Landmark} view="cs-pajak" preset={{ tab: "ppn", period }}
            what="Rekap PPN Masukan vs Keluaran" where="Pajak › Pajak (PPN & PPh)" label="Buka rekap"
            summary={<span data-testid="it-ppn-position-text">Posisi PPN {fmtPeriod(period)}: <b className="tabular-nums">{positionText}</b></span>}
            readOnlyText={<>Rekap PPN dikelola di <b>Pajak › Pajak (PPN &amp; PPh)</b></>} />
        </div>
      </div>

      <div className="section-card mb-3">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Percent size={16} className="text-[#0058CC]" />
            <h2 data-testid="input-tax-title">Faktur Pajak Masukan</h2>
          </div>
          {canCreate && (
            <button data-testid="it-create-button" onClick={() => setShowCreate(true)} className="primary-button ml-auto">
              <Plus size={13} /> Catat Faktur Masukan
            </button>
          )}
        </div>
        <div className="section-body">
          <div className="tab-bar">
            {STATUS_TABS.map((t) => (
              <button key={t.key} data-testid={`it-tab-${t.key}`} className={`tab-button ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
                {t.label}<span className="tab-badge">{counts[t.key]}</span>
              </button>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <div className="min-w-[220px] flex-1">
              <SearchBox value={q} onChange={setQ} placeholder="Cari nomor / NSFP / supplier / tagihan…" testId="it-search" />
            </div>
            <div className="flex items-center gap-1.5" data-testid="it-period-filter">
              <span className="text-[11px] font-semibold text-[#6B6B73]">Masa</span>
              <div className="w-[150px]">
                <KNMonthPicker data-testid="it-period-filter-input" value={periodFilter} placeholder="Semua masa"
                  onChange={(v) => setPeriodFilter(v || "")} />
              </div>
              {periodFilter && (
                <button type="button" className="secondary-button !px-2 !py-1 text-[11px]" data-testid="it-period-filter-clear"
                  onClick={() => setPeriodFilter("")}>Semua masa</button>
              )}
            </div>
          </div>
        </div>
        <div className="px-3 pb-3">
          <ResponsiveTable testId="it-table" rows={filtered} rowKey="id" loading={loading}
            rowTestId={(v) => `it-row-${v.id}`} columns={columns}
            empty={(
              <div className="py-6 text-center text-[12px] text-[#6B6B73]" data-testid="it-empty">
                <Layers className="mx-auto mb-2 text-gray-300" size={28} />
                <p>Belum ada Faktur Pajak Masukan{tab !== "all" ? ` (${STATUS_TABS.find((t) => t.key === tab)?.label})` : ""}{periodFilter ? ` pada ${fmtPeriod(periodFilter)}` : ""}.</p>
                {canCreate && tab === "all" && <p className="mt-1 text-[11px]">Catat dari Tagihan Supplier ber-PPN untuk mengkreditkan PPN Masukan.</p>}
              </div>
            )}
            actions={canCreate ? (v) => (v.status === "recorded" ? (
              <button data-testid={`it-cancel-${v.id}`} onClick={() => { setCancelTarget(v); setCancelReason(""); setCancelErr(""); }}
                className="secondary-button !px-2 !py-1 text-[11px]"><Ban size={11} /> Batal</button>
            ) : null) : undefined} />
        </div>
      </div>

      <InputTaxCreateModal
        open={showCreate}
        bills={bills}
        onClose={() => setShowCreate(false)}
        onCreated={onCreated}
      />

      <FormModal open={!!cancelTarget} onClose={() => !busy && setCancelTarget(null)} size="sm" icon={Ban}
        testId="it-cancel-modal" title={`Batalkan Faktur Masukan ${cancelTarget?.number || ""}`}
        subtitle="NSFP dilepas & bisa dipakai ulang; tagihan supplier-nya kembali dapat dicatat."
        onSubmit={doCancel} submitLabel={busy ? "Memproses..." : "Konfirmasi Pembatalan"} cancelLabel="Batal"
        submitTestId="it-cancel-confirm" busy={busy} submitDisabled={!cancelReason.trim()} error={cancelErr}>
        <p className="mb-2 text-[12px] text-[#6B6B73]">NSFP {cancelTarget?.nsfp}</p>
        <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1" htmlFor="it-cancel-reason">
          Alasan pembatalan<span className="text-red-500"> *</span>
        </label>
        <textarea id="it-cancel-reason" data-testid="it-cancel-reason" value={cancelReason} onChange={(e) => setCancelReason(e.target.value)}
          className="field" rows={3} placeholder="mis. NSFP salah ketik" />
      </FormModal>
    </div>
  );
}
