import { AskKnButton } from "../../components/AskKnButton";
import KNDatePicker from "@/components/KNDatePicker";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Edit3, UserCog, ShieldAlert, PhoneCall, MapPin, X, Wallet, Plus } from "lucide-react";
import { DetailBack } from "../../components/DetailParts";   // satu tombol kembali (gabung dengan layar asal)
import { formatCurrency } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import FilterChips from "../../components/FilterChips";
import PagedRows from "../../components/PagedRows";
import { CreditStatusPill, SegmentBadge, OutcomePill, fmtDate, money, paymentMethodLabel, payStatusLabel, lotPolicyLabel } from "./crmUtils";
import { docStatusLabel } from "../../utils/docStatus";
import { apiErrorText } from "../../utils/apiError";
import { CONTOH_ALASAN, TEKS_BERHASIL_PINDAH, TEKS_GAGAL_PINDAH, TEKS_PILIH_SALES, reassignCustomer, salesTujuanOptions } from "./customerReassign";
import CustomerFormModal from "./CustomerFormModal";
import CustomerColorsSection from "./CustomerColorsSection";
import CustomerMergeSection from "./CustomerMergeSection";
import AuditHistoryPanel from "../../components/AuditHistoryPanel";
import { can } from "../../config/roles";
import ScopedRulesSection from "../settings/config/ScopedRulesSection";   // KF-T5
import CustomerCreditTab from "./CustomerCreditTab";   // CR-T1
import CreditOverrideModal from "./CreditOverrideModal";   // CR-T3 — pop-up izin kredit baku
// CR-T5 — kotak Eksposur, tab Tagihan & Rekening Koran, bagian Izin kredit, janji bayar
import CustomerExposureBox from "./CustomerExposureBox";
import CustomerStatementTab from "./CustomerStatementTab";
import CustomerBillingTab, { CustomerOverrideSection } from "./CustomerBillingTab";
import { PromiseFields, PromiseStatusPill, promiseError, promiseText } from "./promiseUi";
// MN-T3 — kartu pelanggan: kepala empat angka, enam bagian per `sections_allowed`, satu form terima pembayaran.
import { CustomerCardHead, CustomerCasesSection, CustomerPaymentsSection } from "./CustomerCardSections";
import ReceivePaymentModal, { TEKS_PILIH_PT } from "../finance/payments/ReceivePaymentModal";
import { useEntityScope } from "../../context/EntityScopeContext";
import { entityShortById } from "../../utils/entityLabel";

/** MN-T3 — bagian kartu (urutan tampil). `sec` = kunci `sections_allowed` server (izin sumber, K-18). */
export const CARD_SECTIONS = [
  { key: "tagihan", label: "Tagihan & Jadwal" },
  { key: "pembayaran", label: "Pembayaran" },
  { key: "denda_kasus", label: "Denda & Kasus" },
  { key: "tindak_lanjut", label: "Tindak Lanjut" },
  { key: "rekening_koran", label: "Rekening Koran" },
  { key: "riwayat", label: "Riwayat Lain" },
];

const HIST_TABS = [
  { key: "orders", label: "Pesanan" },
  { key: "documents", label: "Dokumen" },
  { key: "prices", label: "Harga Khusus" },
  { key: "samples", label: "Sample" },
];   // MN-T3 — isi tab lama, kini chip di bagian "Riwayat Lain"; "Penagihan" = bagian "Tindak Lanjut"

/**
 * Kartu pelanggan (dulu "Detail pelanggan 360") — MN-T3.
 *  · `variant="card"`: dibuka dari baris mana pun lewat `openCustomerCard(id)` (pop-up rincian `PartyCardHost`).
 *  · `variant="page"` (bawaan): daftar pelanggan CRM & meja Kredit & Plafon — komponen sama, ditambah kolom kiri
 *    (Eksposur, aturan khusus, profil) dan dua bagian pengelolaan yang sudah ada: "Kredit" (CR-T1) dan
 *    "Riwayat Perubahan" (audit).
 * Kepala: nama, PT, empat angka (bagian `ringkasan`), tombol "Terima pembayaran" (`ar_receipt.create`; Semua PT → mati
 * + alasan tertulis di bilah sendiri). Bagian di luar `sections_allowed` tidak ditampilkan dan tidak dimuat.
 */
export default function Customer360Panel({ customerId, currentUser, salesUsers, selectedEntity, onBack, onChanged, onError,
  variant = "page" }) {
  const isCard = variant === "card";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState("");
  const [section, setSection] = useState("");
  const [hist, setHist] = useState("orders");
  const [showEdit, setShowEdit] = useState(false);
  const [modal, setModal] = useState(null); // 'reassign' | 'override' | 'followup' | 'receive'
  const [notice, setNotice] = useState("");
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;

  const canReassign = can(perms, "sales_force", "assign");   // PR-T7 (#13) — = POST /customers/{id}/reassign
  const canAudit = can(perms, "audit", "view");
  const canCredit = can(perms, "credit_profile", "view");   // CR-T1 — bagian Kredit (halaman CRM)
  const canAskCredit = can(perms, "credit_override", "create");   // CR-T3 — = POST …/credit-override
  const canReceive = can(perms, "ar_receipt", "create");   // MN-T3 — = POST /ar-receipts
  const allPt = !selectedEntity || selectedEntity === "all";

  useEffect(() => { load(); }, [customerId]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/customers/${customerId}/360`);
      setData(r.data); setLoadErr("");
    } catch (e) {
      const msg = apiErrorText(e, "Kartu pelanggan belum bisa dimuat.");
      if (isCard) setLoadErr(msg);
      else { onError?.(msg); onBack?.(); }
    } finally { setLoading(false); }
  }

  const sections = useMemo(() => {
    const ok = new Set(data?.sections_allowed || []);
    const list = CARD_SECTIONS.filter((s) => ok.has(s.key));
    if (!isCard && canCredit) list.push({ key: "kredit", label: "Kredit" });
    if (!isCard && canAudit) list.push({ key: "perubahan", label: "Riwayat Perubahan" });
    return list;
  }, [data, isCard, canCredit, canAudit]);
  const active = sections.some((s) => s.key === section) ? section : sections[0]?.key || "";

  if (loading && !data) return <div className="section-card section-pad text-center text-fs-12 text-kn-text-2" data-testid="customer-360-loading">Memuat kartu pelanggan…</div>;
  if (loadErr) return <div className="section-card section-pad text-fs-13 text-kn-danger-text" role="alert" data-testid="customer-360-error">{loadErr}</div>;
  if (!data) return null;

  const credit = data.credit || null;
  const allowed = new Set(data.sections_allowed || []);
  const ptLabel = entityShortById(entities, data.entity_id, "");
  const headEntity = allPt ? (ptLabel || "PT pelanggan") : entityShortById(entities, selectedEntity, "");
  const done = (msg) => { setModal(null); setNotice(msg || ""); onChanged?.(msg); load(); };

  const receiveBtn = canReceive && (
    <button type="button" data-testid="customer-360-receive" className="primary-button btn-sm whitespace-nowrap" disabled={allPt}
      onClick={() => setModal("receive")}><Wallet size={13} aria-hidden="true" /> Terima pembayaran</button>
  );

  const body = (
    <div className="section-card self-start" data-testid="customer-360-sections">
      <div className="section-head">
        <FilterChips testId="customer-360-section" ariaLabel="Bagian kartu pelanggan" value={active} onChange={setSection}
          options={sections} chipTestId={(k) => `customer-360-tab-${k}`} />
        {active === "tindak_lanjut" && (
          <button data-testid="customer-360-followup" onClick={() => setModal("followup")} className="secondary-button btn-sm whitespace-nowrap">
            <Plus size={13} aria-hidden="true" /> Tindak lanjut</button>
        )}
      </div>
      <div className="section-body">
        {!sections.length && <p className="py-4 text-center text-fs-12 text-kn-text-2" data-testid="customer-360-no-sections">Anda belum punya akses ke bagian keuangan pelanggan ini.</p>}
        {active === "tagihan" && <CustomerBillingTab customer={data} currentUser={currentUser} selectedEntity={selectedEntity} show="schedule" />}
        {active === "pembayaran" && <CustomerPaymentsSection customerId={data.id} selectedEntity={selectedEntity} />}
        {active === "denda_kasus" && (
          <div className="grid gap-3">
            {can(perms, "penalty", "view") && <CustomerBillingTab customer={data} currentUser={currentUser} selectedEntity={selectedEntity} show="penalty" />}
            {can(perms, "finance_case", "view") && <CustomerCasesSection customerId={data.id} />}
          </div>
        )}
        {active === "tindak_lanjut" && <HistoryTable data={data} tab="followups" />}
        {active === "rekening_koran" && <CustomerStatementTab customer={data} currentUser={currentUser} selectedEntity={selectedEntity} />}
        {active === "riwayat" && (
          <div className="grid gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <FilterChips testId="customer-360-hist" ariaLabel="Riwayat lain" value={hist} onChange={setHist}
                options={HIST_TABS.map((t) => ({ ...t, count: listFor(data, t.key).length }))} chipTestId={(k) => `customer-360-hist-${k}`} />
              <span className="text-fs-12 text-kn-text-2" data-testid="customer-360-ltv">
                {data.stats?.total_orders || 0} pesanan · nilai seumur hidup {money(data.stats?.lifetime_value)}
                {Number(data.stats?.cancelled_orders) > 0 ? ` · ${data.stats.cancelled_orders} batal tidak dihitung` : ""}
              </span>
            </div>
            <HistoryTable data={data} tab={hist} />
          </div>
        )}
        {active === "kredit" && canCredit && (
          <><CustomerCreditTab customer={data} currentUser={currentUser} selectedEntity={selectedEntity} onChanged={load} />
            <CustomerOverrideSection rows={data.credit_overrides || []} /></>
        )}
        {active === "perubahan" && canAudit && <AuditHistoryPanel entityType="customer" entityId={customerId} testIdPrefix="customer-360-changes" />}
      </div>
    </div>
  );

  return (
    <div data-testid={isCard ? "customer-card-panel" : "customer-360-panel"}>
      {!isCard && <DetailBack onBack={onBack} label="Kembali ke daftar" testId="customer-360-back" className="secondary-button btn-sm mb-3" iconSize={13} />}
      {notice && (
        <div className="notice-bar success mb-3" data-testid="customer-360-notice">
          <span>{notice}</span><button type="button" onClick={() => setNotice("")} aria-label="Tutup">×</button>
        </div>
      )}

      {/* Kepala kartu: nama · PT · status, tombol di sisi kanan; angka di bilah sendiri (tidak menjejali kepala). */}
      <div className="section-card mb-3">
        <div className="section-head">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate" data-testid="customer-360-name">{data.name}</h2>
              <SegmentBadge segment={data.segment} />
              {credit && <CreditStatusPill status={credit.status || "active"} testId="customer-360-credit-status" />}
            </div>
            <p className="mt-0.5 text-fs-12 text-kn-text-2">
              {[data.code, data.city].filter(Boolean).join(" · ")}{ptLabel ? ` · PT ${ptLabel}` : ""} · Sales: <b>{data.assigned_sales_name || "—"}</b>
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-1.5">
            {receiveBtn}
            {!isCard && <button data-testid="customer-360-edit" onClick={() => setShowEdit(true)} className="secondary-button btn-sm whitespace-nowrap"><Edit3 size={13} /> Ubah</button>}
            {!isCard && <AskKnButton type="customer" id={data.id} label={data.name} />}
            {!isCard && canReassign && <button data-testid="customer-360-reassign" onClick={() => setModal("reassign")} className="secondary-button btn-sm whitespace-nowrap"><UserCog size={13} /> Pindah Sales</button>}
          </div>
        </div>
        {canReceive && allPt && (
          <p className="section-body pt-0 text-fs-12 text-kn-text-2" data-testid="customer-360-receive-reason">{TEKS_PILIH_PT}</p>
        )}
        {allowed.has("ringkasan") && (
          <div className="section-body pt-0">
            <CustomerCardHead customer={data} selectedEntity={selectedEntity} entityLabel={allPt ? headEntity : ""} />
          </div>
        )}
      </div>

      {isCard ? body : (
        /* CR-T5 — dua kolom mulai 1280 px; di 1024 px ditumpuk supaya tabel bagian memakai lebar penuh. */
        <div className="grid gap-3 xl:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            {/* CR-T5 (K-31) — kotak Eksposur (nilai yang dipakai mesin = gerbang kredit). */}
            <CustomerExposureBox customerId={data.id} selectedEntity={selectedEntity}>
              {canAskCredit ? (
                <div className="px-3 pb-3">
                  <button data-testid="customer-360-override" onClick={() => setModal("override")} className="secondary-button btn-sm w-full justify-center whitespace-nowrap">
                    <ShieldAlert size={13} /> Ajukan izin kredit
                  </button>
                </div>
              ) : (
                <p className="px-3 pb-3 text-fs-12 text-kn-text-2" data-testid="customer-360-override-none">Izin kredit diajukan pemegang akses mengajukan izin kredit.</p>
              )}
            </CustomerExposureBox>
            {/* KF-T5 — aturan Pusat Pengaturan yang bisa dibedakan per pelanggan (denda, masa tenggang, selisih bayar). */}
            <ScopedRulesSection scopeType="customer" scopeId={data.id} scopeLabel={data.name} entityId={data.entity_id || ""} />
            <ProfileCard data={data} />
          </div>
          {body}
        </div>
      )}

      {!isCard && can(perms, "color", "view") && <CustomerColorsSection customerId={customerId} customerName={data.name} />}

      {!isCard && can(perms, "customer", "delete") && data.status !== "merged" && (
        <CustomerMergeSection customer={data} onDone={(msg) => { onChanged?.(msg); load(); }} onError={onError} />
      )}

      {!isCard && (
        <CustomerFormModal open={showEdit} editTarget={data} currentUser={currentUser} salesUsers={salesUsers}
          onClose={() => setShowEdit(false)}
          onSaved={(c) => { setShowEdit(false); onChanged?.(`Pelanggan ${c.name} diperbarui.`); load(); }}
          onError={onError} />
      )}

      {modal === "receive" && (
        <ReceivePaymentModal customerId={data.id} customerName={data.name} onClose={() => setModal(null)} onDone={(m) => done(m)} />
      )}
      {modal === "reassign" && <ReassignModal customer={data} salesUsers={salesUsers} onClose={() => setModal(null)}
        onDone={(msg) => done(msg)} onError={onError} />}
      <CreditOverrideModal open={modal === "override"} customer={data}
        entityId={selectedEntity && selectedEntity !== "all" ? selectedEntity : data.entity_id || ""}
        onClose={() => setModal(null)} onSaved={(msg) => done(msg)} />
      {modal === "followup" && <FollowupModal customer={data} onClose={() => setModal(null)}
        onDone={(msg) => done(msg)} onError={onError || ((m) => setNotice(m))} />}
    </div>
  );
}

function ProfileCard({ data }) {
  const pp = data.payment_profile || {};
  const ms = pp.allowed_methods || [];
  return (
    <div className="section-card">
      <div className="section-head"><h3 className="text-fs-13 font-bold">Profil & Kontak</h3></div>
      <div className="section-body space-y-2 text-fs-12">
        <p className="field-label">PIC Toko (pihak pelanggan)</p>
        {(data.contacts || []).length > 0 ? (data.contacts || []).map((ct, i) => (
          <div key={i} className="flex items-center gap-2"><PhoneCall size={12} className="text-kn-text-2" aria-hidden="true" />
            <span className="font-semibold">{ct.name}</span><span className="text-kn-text-2">{ct.role === "PIC" ? "PIC toko" : ct.role}</span>
            <span className="ml-auto text-kn-text-2">{ct.phone}</span></div>
        )) : <p className="text-kn-text-2" data-testid="customer-360-pic">{data.pic_name} · {data.phone}</p>}
        {(data.addresses || []).map((ad, i) => (
          <div key={i} className="flex items-start gap-2"><MapPin size={12} className="mt-0.5 text-kn-text-2" aria-hidden="true" />
            <span>{ad.address}, {ad.city}</span></div>
        ))}
        <div className="border-t border-kn-divider pt-2">
          <p className="field-label">Profil Pembayaran</p>
          <p data-testid="customer-360-pay-default">Metode utama: <b>{pp.default_method ? paymentMethodLabel(pp.default_method) : "—"}</b>
            {ms.includes("tempo") && <> · Termin {pp.term_days ?? 0} hari</>}
            {ms.includes("dp") && <> · DP {pp.dp_percent ?? 0}%</>}</p>
          <p className="text-kn-text-2">Metode yang diizinkan: {ms.map(paymentMethodLabel).join(", ") || "—"}</p>
        </div>
        <div className="border-t border-kn-divider pt-2" data-testid="customer-360-sales-team">
          <p className="field-label">Tim Sales (Split Insentif)</p>
          {(data.sales_team || []).length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {(data.sales_team || []).map((m, i) => (
                <span key={i} data-testid={`customer-360-team-${i}`} className={`status-pill ${m.role === "pic" ? "status-confirmed" : "status-draft"}`}>
                  {m.role === "pic" ? "Penanggung jawab · " : ""}{m.name || m.sales_id} · <b className="tabular-nums">{m.split_pct}%</b>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-kn-text-2">Sales penanggung jawab tunggal: <b>{data.assigned_sales_name || "—"}</b> (100%)</p>
          )}
        </div>
        <div className="border-t border-kn-divider pt-2" data-testid="customer-360-lot-policy">
          <p className="field-label">Kebijakan Lot</p>
          <p className="text-kn-text-2">{lotPolicyLabel(data.lot_policy)}{data.enforce_single_dye_lot ? " · Paksa 1 dye lot" : ""}</p>
        </div>
        {(data.tags || []).length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {data.tags.map((t) => <span key={t} className="status-pill status-draft">{t}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

function listFor(data, tab) {
  return ({ orders: data.order_history, documents: data.document_history, prices: data.special_price_history,
    samples: data.sample_history, followups: data.collection_followups }[tab]) || [];
}

function HistoryTable({ data, tab }) {
  const rows = listFor(data, tab);
  if (rows.length === 0) return <div className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="customer-360-history-empty">Belum ada data.</div>;
  const Row = ({ r }) => (
    <>
      {tab === "orders" && (
        <div className="flex items-center justify-between gap-2 py-2 text-fs-12">
          <div className="min-w-0"><p className="font-semibold text-kn-action">{r.number}</p><p className="text-kn-text-2">{fmtDate(r.created_at)} · {docStatusLabel(r.status)}{["cancelled", "expired"].includes(r.status) ? "" : ` · ${payStatusLabel(r.payment_status)}`}</p></div>
          <div className="text-right"><p className="whitespace-nowrap font-semibold tabular-nums">{formatCurrency(r.grand_total)}</p><p className="whitespace-nowrap tabular-nums text-kn-text-2">bayar {formatCurrency(r.paid)}</p></div>
        </div>
      )}
      {tab === "documents" && (
        <div className="flex items-center justify-between gap-2 py-2 text-fs-12">
          <span className="font-semibold">{r.document_type || r.type || r.number || "Dokumen"}</span>
          <span className="text-kn-text-2">{fmtDate(r.created_at)}</span>
        </div>
      )}
      {tab === "prices" && (
        <div className="flex items-center justify-between gap-2 py-2 text-fs-12">
          <div className="min-w-0"><p className="font-semibold">{r.product_name || r.product_id}</p><p className="text-kn-text-2">{r.status_label || docStatusLabel(r.status)} · {fmtDate(r.created_at)}</p></div>
          <span className="whitespace-nowrap font-semibold tabular-nums">{formatCurrency(r.approved_price || r.special_price || r.price)}</span>
        </div>
      )}
      {tab === "samples" && (
        <div className="flex items-center justify-between gap-2 py-2 text-fs-12" data-testid={`customer-360-sample-${r.id}`}>
          <div className="min-w-0"><p className="font-semibold">{r.product_name} <span className="font-mono text-kn-text-2">{r.sku}</span></p>
            <p className="text-kn-text-2">{r.number} · {r.length} {r.unit} · {r.status === "done" ? `dipotong ${fmtDate(r.cut_at)} (${r.child_roll_no})` : r.status === "cancelled" ? "dibatalkan" : "menunggu potong"}</p></div>
          <span className="whitespace-nowrap font-semibold tabular-nums">{formatCurrency(r.amount)}</span>
        </div>
      )}
      {tab === "followups" && (
        <div className="flex items-start justify-between gap-2 py-2 text-fs-12">
          <div className="min-w-0"><p className="truncate">{r.note}</p><p className="text-kn-text-2">{r.created_by} · {fmtDate(r.created_at)}</p>
            {/* CR-T5 — janji bayar: tanggal + nominal + lencana status (dihitung server saat dibaca) */}
            {r.promise_date && <p className="text-kn-text" data-testid={`customer-360-promise-${r.id}`}>{promiseText(r, fmtDate)}</p>}</div>
          <div className="flex flex-wrap items-center justify-end gap-1">
            <OutcomePill outcome={r.outcome} />
            {r.promise_status && <PromiseStatusPill status={r.promise_status} testId={`customer-360-promise-status-${r.id}`} />}
          </div>
        </div>
      )}
    </>
  );
  return (
    <div data-testid={`customer-360-history-${tab}`}>
      <p className="mb-1 text-fs-12 text-kn-text-2" data-testid={`customer-360-history-${tab}-total`}>{rows.length} baris</p>
      <table className="w-full"><tbody className="divide-y divide-kn-divider">
        <PagedRows rows={rows} pageSize={10} testId={`customer-360-history-${tab}-pager`}>{(r, i) => (
          <tr key={r.id || i}><td><Row r={r} /></td></tr>
        )}</PagedRows>
      </tbody></table>
    </div>
  );
}

// G2-10 — tombol aksi di KAKI pop-up (dulu menempel di badan tanpa pemisah).
function MiniModal({ title, icon, children, footer, onClose, testId }) {
  return (
    <div className="modal-overlay" data-testid={testId} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal-card" style={{ maxWidth: 440, width: "92vw" }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#EFF0F2]">
          <div className="flex items-center gap-2">{icon}<h2 className="text-[14px] font-bold">{title}</h2></div>
          <button onClick={onClose} className="icon-button" aria-label="Tutup"><X size={16} /></button>
        </div>
        <div className="p-4 space-y-3">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">{footer}</div>}
      </div>
    </div>
  );
}

const MLabel = ({ children, req = false, optional = false }) => (
  <label className="mb-1 block text-[11px] font-semibold text-[#4A4B53]">{children}{req && <span className="text-red-500"> *</span>}{optional && <span className="font-normal text-[#9A9BA3]"> (opsional)</span>}</label>
);

function ReassignModal({ customer, salesUsers, onClose, onDone, onError }) {
  const [sid, setSid] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    if (!sid) { onError?.(TEKS_PILIH_SALES); return; }
    setBusy(true);
    try {
      await reassignCustomer(customer.id, { assigned_sales_id: sid, reason });
      onDone?.(TEKS_BERHASIL_PINDAH);
    } catch (e) { onError?.(apiErrorText(e, TEKS_GAGAL_PINDAH)); } finally { setBusy(false); }
  }
  return (
    <MiniModal title="Pindahkan ke Sales Lain" icon={<UserCog size={16} className="text-[#0058CC]" />} onClose={onClose} testId="reassign-modal"
      footer={<>
        <button onClick={onClose} className="secondary-button">Batal</button>
        <button data-testid="reassign-submit" disabled={busy || !sid} onClick={go} className="primary-button">{busy ? "Memindahkan…" : "Pindahkan"}</button>
      </>}>
      <div>
        <MLabel req>Sales tujuan</MLabel>
        <KNSelect value={sid} onValueChange={setSid} className="field" data-testid="reassign-sales-select"
          placeholder="Pilih sales tujuan" options={salesTujuanOptions(salesUsers, customer.assigned_sales_id)} />
      </div>
      <div>
        <MLabel optional>Alasan</MLabel>
        <input data-testid="reassign-reason" value={reason} onChange={(e) => setReason(e.target.value)} className="field" placeholder={CONTOH_ALASAN} />
      </div>
    </MiniModal>
  );
}

function FollowupModal({ customer, onClose, onDone, onError }) {
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState("contacted");
  const [next, setNext] = useState("");
  const [promiseDate, setPromiseDate] = useState("");   // CR-T5 — wajib bila "Dijanjikan bayar"
  const [promiseAmount, setPromiseAmount] = useState("");
  const [busy, setBusy] = useState(false);
  async function go() {
    if (!note.trim()) { onError?.("Catatan follow-up wajib diisi."); return; }
    const janji = outcome === "promised" ? promiseError(promiseDate, promiseAmount) : "";
    if (janji) { onError?.(janji); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/customers/${customer.id}/followups`, {
        customer_id: customer.id, note, outcome, next_action_date: next,
        ...(outcome === "promised" ? { promise_date: promiseDate, promise_amount: Number(promiseAmount) } : {}) });
      onDone?.("Follow-up penagihan dicatat.");
    } catch (e) { onError?.(apiErrorText(e, "Gagal menyimpan tindak lanjut.")); } finally { setBusy(false); }
  }
  return (
    <MiniModal title="Catat Tindak Lanjut Penagihan" icon={<PhoneCall size={16} className="text-[#0058CC]" />} onClose={onClose} testId="followup-modal"
      footer={<>
        <button onClick={onClose} className="secondary-button">Batal</button>
        <button data-testid="followup-submit" disabled={busy || !note.trim()} onClick={go} className="primary-button">{busy ? "Menyimpan…" : "Simpan"}</button>
      </>}>
      <div>
        <MLabel req>Hasil kontak / catatan</MLabel>
        <textarea data-testid="followup-note" value={note} onChange={(e) => setNote(e.target.value)} className="field" rows="2" placeholder="mis. janji transfer Jumat" />
      </div>
      <div>
        <MLabel>Hasil</MLabel>
        <KNSelect value={outcome} onValueChange={setOutcome} className="field" data-testid="followup-outcome"
          options={[{ value: "contacted", label: "Dihubungi" }, { value: "promised", label: "Dijanjikan bayar" },
            { value: "paid", label: "Sudah bayar" }, { value: "no_response", label: "Tak ada respon" }, { value: "escalated", label: "Eskalasi" }]} />
      </div>
      {outcome === "promised" && (
        <PromiseFields date={promiseDate} amount={promiseAmount} onDate={setPromiseDate} onAmount={setPromiseAmount}
          testIdPrefix="followup-promise" />
      )}
      <div>
        <MLabel optional>Tindak lanjut berikutnya</MLabel>
        <KNDatePicker data-testid="followup-next" value={next} onChange={setNext} />
      </div>
    </MiniModal>
  );
}
