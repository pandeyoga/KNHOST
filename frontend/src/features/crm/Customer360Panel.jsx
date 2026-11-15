import { AskKnButton } from "../../components/AskKnButton";
import KNDatePicker from "@/components/KNDatePicker";
import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { ArrowLeft, Edit3, UserCog, ShieldAlert, PhoneCall, MapPin, X } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import { CreditStatusPill, SegmentBadge, OutcomePill, fmtDate, money, paymentMethodLabel, payStatusLabel, lotPolicyLabel } from "./crmUtils";
import { docStatusLabel } from "../../utils/docStatus";
import { apiErrorText } from "../../utils/apiError";
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

const HIST_TABS = [
  { key: "orders", label: "Pesanan" },
  { key: "documents", label: "Dokumen" },
  { key: "prices", label: "Harga Khusus" },
  { key: "samples", label: "Sample" },
  { key: "followups", label: "Penagihan" },
];   // CR-T5 — tab "Izin Kredit" (CR-T3) pindah ke tab Kredit (bagian "Izin kredit"); + Tagihan, Rekening Koran

/** Detail pelanggan 360 — profil + kredit + riwayat + aksi. */
export default function Customer360Panel({ customerId, currentUser, salesUsers, selectedEntity, onBack, onChanged, onError }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("orders");
  const [showEdit, setShowEdit] = useState(false);
  const [modal, setModal] = useState(null); // 'reassign' | 'override' | 'followup'

  const canReassign = can(currentUser?.permissions, "sales_force", "assign");   // PR-T7 (#13) — = POST /customers/{id}/reassign
  const canAudit = can(currentUser?.permissions, "audit", "view");
  const canCredit = can(currentUser?.permissions, "credit_profile", "view");   // CR-T1 — tab Kredit
  const canAskCredit = can(currentUser?.permissions, "credit_override", "create");   // CR-T3 — = POST …/credit-override
  // CR-T5 — tab Tagihan (jadwal tagihan / nota denda) dan Rekening Koran (= izin endpoint masing-masing)
  const canBilling = can(currentUser?.permissions, "payment_plan", "view") || can(currentUser?.permissions, "penalty", "view");
  const canStatement = can(currentUser?.permissions, "credit_profile", "view") || can(currentUser?.permissions, "ar_receipt", "view");

  useEffect(() => { load(); }, [customerId]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/customers/${customerId}/360`);
      setData(r.data);
    } catch (e) {
      onError?.(apiErrorText(e, "Gagal memuat detail pelanggan."));
      onBack?.();
    } finally { setLoading(false); }
  }

  if (loading && !data) return <div className="section-card py-12 text-center text-[12px] text-[#6B6B73]" data-testid="customer-360-loading">Memuat detail pelanggan...</div>;
  if (!data) return null;

  const credit = data.credit || {};

  return (
    <div data-testid="customer-360-panel">
      <button data-testid="customer-360-back" onClick={onBack} className="secondary-button mb-3"><ArrowLeft size={13} /> Kembali ke daftar</button>

      {/* Header */}
      <div className="section-card mb-3">
        <div className="section-head">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="truncate" data-testid="customer-360-name">{data.name}</h2>
              <SegmentBadge segment={data.segment} />
              <CreditStatusPill status={credit.status || "active"} testId="customer-360-credit-status" />
            </div>
            <p className="text-[11px] text-[#6B6B73] mt-0.5">{data.code} · {data.city} · Sales: <b>{data.assigned_sales_name || "—"}</b></p>
          </div>
          <div className="flex items-center gap-1.5">
            <button data-testid="customer-360-edit" onClick={() => setShowEdit(true)} className="secondary-button"><Edit3 size={13} /> Ubah</button>
            <AskKnButton type="customer" id={data.id} label={data.name} />
            {canReassign && <button data-testid="customer-360-reassign" onClick={() => setModal("reassign")} className="secondary-button"><UserCog size={13} /> Pindah Sales</button>}
          </div>
        </div>
      </div>

      {/* CR-T5 — dua kolom mulai 1280 px; di 1024 px ditumpuk supaya tabel Tagihan/Rekening Koran memakai lebar penuh. */}
      <div className="grid gap-3 xl:grid-cols-[320px_1fr]">
        {/* Left: credit + profile */}
        <div className="space-y-3">
          {/* CR-T5 (K-31) — kotak Eksposur (nilai yang dipakai mesin = gerbang kredit) menggantikan empat ubin "Kontrol Kredit". */}
          <CustomerExposureBox customerId={data.id} selectedEntity={selectedEntity}>
            {/* CR-T3 — izin kredit juga melepas tahanan karena telat (bukan hanya lewat plafon): tombol untuk pemegang
                `credit_override.create`; tanpa izin itu ditulis siapa yang mengajukan. */}
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

          {/* Profile */}
          <div className="section-card">
            <div className="section-head"><h3 className="text-[12.5px] font-bold">Profil & Kontak</h3></div>
            <div className="section-body space-y-2 text-[11.5px]">
              <p className="text-[10px] uppercase text-[#9A9BA3] font-semibold">PIC Toko (pihak pelanggan)</p>
              {(data.contacts || []).length > 0 ? (data.contacts || []).map((ct, i) => (
                <div key={i} className="flex items-center gap-2"><PhoneCall size={12} className="text-[#6B6B73]" />
                  <span className="font-semibold">{ct.name}</span><span className="text-[#6B6B73]">{ct.role === "PIC" ? "PIC toko" : ct.role}</span>
                  <span className="text-[#9A9BA3] ml-auto">{ct.phone}</span></div>
              )) : <p className="text-[#9A9BA3]" data-testid="customer-360-pic">{data.pic_name} · {data.phone}</p>}
              {(data.addresses || []).map((ad, i) => (
                <div key={i} className="flex items-start gap-2"><MapPin size={12} className="text-[#6B6B73] mt-0.5" />
                  <span className="text-[#3C3C43]">{ad.address}, {ad.city}</span></div>
              ))}
              <div className="pt-2 border-t border-[#EFF0F2]">
                <p className="text-[10px] uppercase text-[#9A9BA3] font-semibold mb-1">Profil Pembayaran</p>
                {/* G2-08 — metode bayar berlabel (dulu "Default: TEMPO", "Metode: tunai, tempo"); termin/DP hanya bila metodenya dipakai. */}
                {(() => {
                  const pp = data.payment_profile || {};
                  const ms = pp.allowed_methods || [];
                  return (<>
                    <p data-testid="customer-360-pay-default">Metode utama: <b>{pp.default_method ? paymentMethodLabel(pp.default_method) : "—"}</b>
                      {ms.includes("tempo") && <> · Termin {pp.term_days ?? 0} hari</>}
                      {ms.includes("dp") && <> · DP {pp.dp_percent ?? 0}%</>}</p>
                    <p className="text-[10.5px] text-[#6B6B73]">Metode yang diizinkan: {ms.map(paymentMethodLabel).join(", ") || "—"}</p>
                  </>);
                })()}
              </div>
              {/* SALES REVAMP V2 — Tim sales (PIC + co-sales + split) */}
              <div className="pt-2 border-t border-[#EFF0F2]" data-testid="customer-360-sales-team">
                <p className="text-[10px] uppercase text-[#9A9BA3] font-semibold mb-1">Tim Sales (Split Insentif)</p>
                {(data.sales_team || []).length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {(data.sales_team || []).map((m, i) => (
                      <span key={i} data-testid={`customer-360-team-${i}`} className={`status-pill ${m.role === "pic" ? "status-confirmed" : "pill-muted"}`}>
                        {m.role === "pic" ? "Penanggung jawab · " : ""}{m.name || m.sales_id} · <b className="tabular-nums">{m.split_pct}%</b>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[10.5px] text-[#6B6B73]">Sales penanggung jawab tunggal: <b>{data.assigned_sales_name || "—"}</b> (100%)</p>
                )}
              </div>
              {/* SALES REVAMP V2 — Kebijakan lot */}
              <div className="pt-2 border-t border-[#EFF0F2]" data-testid="customer-360-lot-policy">
                <p className="text-[10px] uppercase text-[#9A9BA3] font-semibold mb-1">Kebijakan Lot</p>
                <p className="text-[10.5px] text-[#6B6B73]">
                  {lotPolicyLabel(data.lot_policy)}
                  {data.enforce_single_dye_lot ? " · Paksa 1 dye lot" : ""}
                </p>
              </div>
              {(data.tags || []).length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {data.tags.map((t) => <span key={t} className="status-pill pill-muted">{t}</span>)}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: history */}
        <div className="section-card self-start">
          <div className="section-head">
            <div className="flex items-center gap-3 flex-wrap">
              <h3 className="text-[12.5px] font-bold">Riwayat 360°</h3>
              {/* G2-08 — jumlah pesanan & nilai seumur hidup tanpa SO batal/kedaluwarsa (dihitung server). */}
              <span className="text-[11px] text-[#6B6B73]" data-testid="customer-360-ltv">
                {data.stats?.total_orders || 0} pesanan · nilai seumur hidup {money(data.stats?.lifetime_value)}
                {Number(data.stats?.cancelled_orders) > 0 ? ` · ${data.stats.cancelled_orders} batal tidak dihitung` : ""}
              </span>
            </div>
            <button data-testid="customer-360-followup" onClick={() => setModal("followup")} className="secondary-button text-[11px]">+ Tindak lanjut</button>
          </div>
          <div className="section-body">
            <div className="tab-bar mb-2">
              {HIST_TABS.map((t) => (
                <button key={t.key} data-testid={`customer-360-tab-${t.key}`} className={`tab-button ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
                  {t.label}<span className="tab-badge">{listFor(data, t.key).length}</span>
                </button>
              ))}
              {canCredit && (
                <button data-testid="customer-360-tab-credit" className={`tab-button ${tab === "credit" ? "active" : ""}`} onClick={() => setTab("credit")}>
                  Kredit
                </button>
              )}
              {canBilling && (
                <button data-testid="customer-360-tab-billing" className={`tab-button ${tab === "billing" ? "active" : ""}`} onClick={() => setTab("billing")}>
                  Tagihan
                </button>
              )}
              {canStatement && (
                <button data-testid="customer-360-tab-statement" className={`tab-button ${tab === "statement" ? "active" : ""}`} onClick={() => setTab("statement")}>
                  Rekening Koran
                </button>
              )}
              {canAudit && (
                <button data-testid="customer-360-tab-changes" className={`tab-button ${tab === "changes" ? "active" : ""}`} onClick={() => setTab("changes")}>
                  Riwayat Perubahan
                </button>
              )}
            </div>
            {tab === "credit" && canCredit
              ? <><CustomerCreditTab customer={data} currentUser={currentUser} selectedEntity={selectedEntity} onChanged={load} />
                <CustomerOverrideSection rows={data.credit_overrides || []} /></>
              : tab === "billing" && canBilling
                ? <CustomerBillingTab customer={data} currentUser={currentUser} selectedEntity={selectedEntity} />
              : tab === "statement" && canStatement
                ? <CustomerStatementTab customer={data} currentUser={currentUser} selectedEntity={selectedEntity} />
              : tab === "changes" && canAudit
                ? <AuditHistoryPanel entityType="customer" entityId={customerId} testIdPrefix="customer-360-changes" />
                : <HistoryTable data={data} tab={tab} />}
          </div>
        </div>
      </div>

      <CustomerColorsSection customerId={customerId} customerName={data.name} />

      {can(currentUser?.permissions, "customer", "delete") && data.status !== "merged" && (
        <CustomerMergeSection customer={data} onDone={(msg) => { onChanged?.(msg); load(); }} onError={onError} />
      )}

      <CustomerFormModal open={showEdit} editTarget={data} currentUser={currentUser} salesUsers={salesUsers}
        onClose={() => setShowEdit(false)}
        onSaved={(c) => { setShowEdit(false); onChanged?.(`Pelanggan ${c.name} diperbarui.`); load(); }}
        onError={onError} />

      {modal === "reassign" && <ReassignModal customer={data} salesUsers={salesUsers} onClose={() => setModal(null)}
        onDone={(msg) => { setModal(null); onChanged?.(msg); load(); }} onError={onError} />}
      <CreditOverrideModal open={modal === "override"} customer={data}
        entityId={selectedEntity && selectedEntity !== "all" ? selectedEntity : data.entity_id || ""}
        onClose={() => setModal(null)} onSaved={(msg) => { setModal(null); onChanged?.(msg); load(); }} />
      {modal === "followup" && <FollowupModal customer={data} onClose={() => setModal(null)}
        onDone={(msg) => { setModal(null); onChanged?.(msg); load(); }} onError={onError} />}
    </div>
  );
}

function listFor(data, tab) {
  return ({ orders: data.order_history, documents: data.document_history, prices: data.special_price_history,
    samples: data.sample_history, followups: data.collection_followups }[tab]) || [];
}

function HistoryTable({ data, tab }) {
  const rows = listFor(data, tab);
  if (rows.length === 0) return <div className="py-8 text-center text-[11.5px] text-[#9A9BA3]" data-testid="customer-360-history-empty">Belum ada data.</div>;
  return (
    <div className="divide-y divide-[#EFF0F2] max-h-[440px] overflow-y-auto" data-testid={`customer-360-history-${tab}`}>
      {tab === "orders" && rows.map((o) => (
        <div key={o.id} className="flex items-center justify-between py-2 text-[11.5px]">
          <div><p className="font-semibold text-[#0058CC]">{o.number}</p><p className="text-[10px] text-[#6B6B73]">{fmtDate(o.created_at)} · {docStatusLabel(o.status)}{["cancelled", "expired"].includes(o.status) ? "" : ` · ${payStatusLabel(o.payment_status)}`}</p></div>
          <div className="text-right"><p className="tabular-nums font-semibold">{formatCurrency(o.grand_total)}</p><p className="text-[10px] text-[#6B6B73] tabular-nums">bayar {formatCurrency(o.paid)}</p></div>
        </div>
      ))}
      {tab === "documents" && rows.map((d, i) => (
        <div key={i} className="flex items-center justify-between py-2 text-[11.5px]">
          <span className="font-semibold">{d.document_type || d.type || d.number || "Dokumen"}</span>
          <span className="text-[10px] text-[#6B6B73]">{fmtDate(d.created_at)}</span>
        </div>
      ))}
      {tab === "prices" && rows.map((p, i) => (
        <div key={i} className="flex items-center justify-between py-2 text-[11.5px]">
          <div><p className="font-semibold">{p.product_name || p.product_id}</p><p className="text-[10px] text-[#6B6B73]">{p.status_label || docStatusLabel(p.status)} · {fmtDate(p.created_at)}</p></div>
          <span className="tabular-nums font-semibold">{formatCurrency(p.approved_price || p.special_price || p.price)}</span>
        </div>
      ))}
      {tab === "samples" && rows.map((s) => (
        <div key={s.id} className="flex items-center justify-between py-2 text-[11.5px]" data-testid={`customer-360-sample-${s.id}`}>
          <div><p className="font-semibold">{s.product_name} <span className="font-mono text-[10px] text-[#6B6B73]">{s.sku}</span></p>
            <p className="text-[10px] text-[#6B6B73]">{s.number} · {s.length} {s.unit} · {s.status === "done" ? `dipotong ${fmtDate(s.cut_at)} (${s.child_roll_no})` : s.status === "cancelled" ? "dibatalkan" : "menunggu potong"}</p></div>
          <span className="tabular-nums font-semibold">{formatCurrency(s.amount)}</span>
        </div>
      ))}
      {tab === "followups" && rows.map((fu, i) => (
        <div key={i} className="flex items-start justify-between py-2 text-[11.5px] gap-2">
          <div className="min-w-0"><p className="truncate">{fu.note}</p><p className="text-[10px] text-[#6B6B73]">{fu.created_by} · {fmtDate(fu.created_at)}</p>
            {/* CR-T5 — janji bayar: tanggal + nominal + lencana status (dihitung server saat dibaca) */}
            {fu.promise_date && <p className="text-fs-12 text-kn-text" data-testid={`customer-360-promise-${fu.id}`}>{promiseText(fu, fmtDate)}</p>}</div>
          <div className="flex flex-wrap items-center justify-end gap-1">
            <OutcomePill outcome={fu.outcome} />
            {fu.promise_status && <PromiseStatusPill status={fu.promise_status} testId={`customer-360-promise-status-${fu.id}`} />}
          </div>
        </div>
      ))}
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
    if (!sid) { onError?.("Pilih sales tujuan."); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/customers/${customer.id}/reassign`, { assigned_sales_id: sid, reason });
      onDone?.("Pelanggan dipindahkan ke sales baru.");
    } catch (e) { onError?.(apiErrorText(e, "Gagal memindahkan pelanggan.")); } finally { setBusy(false); }
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
          placeholder="Pilih sales tujuan" options={(salesUsers || []).filter((s) => s.id !== customer.assigned_sales_id).map((s) => ({ value: s.id, label: s.name }))} />
      </div>
      <div>
        <MLabel optional>Alasan</MLabel>
        <input data-testid="reassign-reason" value={reason} onChange={(e) => setReason(e.target.value)} className="field" placeholder="mis. wilayah sales berubah" />
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
