/**
 * CreditDeskView (CR-T5) — Keuangan › Piutang › tab "Kredit & Plafon": DAFTAR KERJA pengendali kredit, enam antrean
 * dalam satu tab (dulu lima menu). `docs/blueprint/unit/CR-T5.md`, bagian Layar.
 *
 *  · Banner PT (L4). Mode "Semua PT" = gabungan hanya-baca berlabel "belum dieliminasi" (N3): tombol putus/terbit/catat
 *    mati dengan alasan TERTULIS di bilah sendiri.
 *  · Enam chip antrean berjumlah (`FilterChips`, ringkasan `GET /api/credit-desk/summary`): Menunggu keputusan, Ditahan,
 *    Jatuh tempo, Janji bayar, Kaji ulang, Denda. Daftar berhalaman dengan jumlah total (`PaginationBar`) + kotak cari.
 *  · Aksi per baris: "Buka kartu pelanggan" (semua — kartu pelanggan yang sama dengan CRM, dibuka di tempat);
 *    Setujui/Tolak (izin kredit: `credit_override.approve`; ubah profil: `credit_profile.approve`); Periksa ulang kredit
 *    (ditahan); Salin pengingat + Catat janji bayar (jatuh tempo); Terbitkan/Bebaskan (denda, `penalty.issue|waive`).
 *    Finance memegang `credit_profile.view` → melihat semua antrean tanpa tombol putus.
 *  · Kosong: "Tidak ada pekerjaan di antrean ini."; galat di tempat daftar dengan "Coba lagi".
 *  · Riwayat izin kredit & pengajuan profil (`CreditOverridesPanel`, `CreditProfileRequestsPanel`) dipakai ulang di bagian
 *    bawah (dulu isi tab ini; tab "Persetujuan Kredit" CRM sudah dipindah MN-T1).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Ban, ChevronDown, ChevronRight, History } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import ErrorNotice from "../../components/ErrorNotice";
import FilterSelect from "../../components/FilterSelect";   // pola UI 16 Nov — saringan dropdown (dulu FilterChips)
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import PaginationBar from "../../components/PaginationBar";
import ConfirmModal from "../../components/ConfirmModal";
import { SearchBox } from "../../components/ListPageParts";
import { useEntityScope } from "../../context/EntityScopeContext";
import useIntentKey from "../../hooks/useIntentKey";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { entityShort } from "../../utils/entityLabel";
import { formatCurrency } from "../../utils/formatters";
import { can } from "../../config/roles";
import Customer360Panel from "../crm/Customer360Panel";
import CreditOverridesPanel from "../crm/CreditOverridesPanel";
import CreditProfileRequestsPanel from "../crm/CreditProfileRequestsPanel";
import { PromiseModal } from "../crm/promiseUi";
import { fetchMeta, issuePenalty, waivePenalty } from "./payments/paymentApi";
import { CSV_COLUMNS, QUEUES, QueueTable, copyText } from "./creditDeskParts";

const PAGE_SIZE = 25;
const EMPTY = "Tidak ada pekerjaan di antrean ini.";
// Tombol baku "Unduh ▾" (KN_37 §6): antrean dihitung dari beberapa koleksi (izin kredit + pengajuan profil, jadwal
// tagihan, janji, profil, denda), jadi berkas Excel Pusat Export (satu dataset = satu koleksi; dataset izin kredit hanya
// sebagian antrean pertama) TIDAK ditawarkan — butirnya mati dengan alasan tertulis; CSV memakai kolom persis tabel.
const EXCEL_TIDAK_ADA = "Antrean ini dihitung dari beberapa sumber — berkas Excel belum tersedia. Pakai CSV (kolom persis seperti tabel).";

export default function CreditDeskView({ currentUser, selectedEntity }) {
  const perms = currentUser?.permissions;
  // Antrean = `credit_profile.view` (GET /api/credit-desk). Pembaca izin kredit saja (`credit_override.view`) tetap
  // melihat daftar izin kredit (riwayat di bawah), tanpa antrean.
  const canQueues = can(perms, "credit_profile", "view");
  const { entities } = useEntityScope() || {};
  const [queue, setQueue] = useState("menunggu_keputusan");
  const [summary, setSummary] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  const [expanded, setExpanded] = useState({});
  const [customer, setCustomer] = useState(null);     // kartu pelanggan yang dibuka
  const [decision, setDecision] = useState(null);     // {row, decision}
  const [promise, setPromise] = useState(null);       // baris jatuh tempo
  const [waive, setWaive] = useState(null);           // baris denda
  const [showHistory, setShowHistory] = useState(false);
  const issueIntent = useIntentKey("pnl-terbit");

  useEffect(() => { const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 300); return () => clearTimeout(t); },
    [search]);

  const loadSummary = useCallback(async () => {
    if (!canQueues) return;
    try { setSummary((await axios.get(`${API}/credit-desk/summary`)).data); } catch { setSummary(null); }
  }, [canQueues]);
  // Pelatihan 18 Nov (F06) — jawaban LAMA tidak boleh menimpa yang baru: daftar tanpa saringan (lebih lambat) dulu tiba
  // sesudah hasil pencarian sehingga kotak cari berisi "Latihan 23" tetapi tabel menampilkan semua pelanggan.
  const loadSeq = useRef(0);
  const load = useCallback(async () => {
    if (!canQueues) { setLoading(false); return; }
    const mine = ++loadSeq.current;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/credit-desk`, { params: { queue, page, page_size: PAGE_SIZE, q: q || undefined } });
      if (mine !== loadSeq.current) return;
      setData(r.data);
      setError("");
    } catch (e) {
      if (mine !== loadSeq.current) return;
      setData(null);
      setError(apiErrorText(e, "Daftar kerja kredit belum bisa dimuat."));
    } finally { if (mine === loadSeq.current) setLoading(false); }
  }, [queue, page, q, canQueues]);
  useEffect(() => { load(); }, [load, selectedEntity]);
  useEffect(() => { loadSummary(); }, [loadSummary, selectedEntity]);
  const refresh = useCallback(() => { load(); loadSummary(); }, [load, loadSummary]);
  // Unduh CSV "semua hasil": antrean yang sama + cari yang sama, per 100 baris (exportSpec tanpa dataset — antrean hasil
  // hitung beberapa koleksi, jadi Excel Pusat Export tidak ditawarkan; CSV kolom-layar tetap ada).
  const fetchAllRows = useCallback(async ({ onProgress, isCancelled } = {}) => {
    const out = [];
    for (let p = 1; ; p += 1) {
      const r = await axios.get(`${API}/credit-desk`, { params: { queue, page: p, page_size: 100, q: q || undefined } });
      out.push(...(r.data?.items || []));
      onProgress?.(out.length, r.data?.total || out.length);
      if (isCancelled?.() || out.length >= (r.data?.total || 0) || !(r.data?.items || []).length) return out;
    }
  }, [queue, q]);
  const done = (msg) => { setNotice(msg); setActionError(""); refresh(); };

  const combined = Boolean(data?.combined ?? summary?.combined);
  const ptName = (id) => entityShort((entities || []).find((e) => e && e.id === id), "PT");

  const ctx = {
    combined, busy, expanded, ptName,
    canApproveOverride: can(perms, "credit_override", "approve"),
    canApproveProfile: can(perms, "credit_profile", "approve"),
    canPromise: can(perms, "order", "update"),
    canIssue: can(perms, "penalty", "issue"),
    canWaive: can(perms, "penalty", "waive"),
    toggle: (id) => setExpanded((x) => ({ ...x, [id]: !x[id] })),
    openCustomer: (row) => setCustomer({ id: row.customer_id, name: row.customer_name }),
    onDecide: (row, d) => setDecision({ row, decision: d }),
    onPromise: (row) => setPromise(row),
    onWaive: (row) => setWaive(row),
    onRecheck: async (row) => {
      setBusy(row.id);
      try {
        await axios.post(`${API}/sales-orders/${row.order_id}/credit-recheck`);
        done(`Kredit pesanan ${row.order_number} diperiksa ulang.`);
      } catch (e) { setActionError(apiErrorText(e, "Periksa ulang kredit gagal.")); } finally { setBusy(""); }
    },
    onCopyReminder: async (row) => {
      setBusy(row.id);
      try {
        const r = await axios.get(`${API}/customers/${row.customer_id}/reminder-text`, { params: { entity_id: row.entity_id } });
        if (!r.data?.text) { setNotice(r.data?.note || "Tidak ada tagihan untuk diingatkan."); return; }
        const ok = await copyText(r.data.text);
        if (ok) setNotice(`Naskah pengingat ${row.customer_name} disalin — tempel di pesan ke pelanggan.`);
        else setActionError("Naskah belum bisa disalin otomatis. Buka kartu pelanggan › Rekening Koran › Salin pengingat.");
      } catch (e) { setActionError(apiErrorText(e, "Naskah pengingat belum bisa disusun.")); } finally { setBusy(""); }
    },
    onIssue: async (row) => {
      if (!(await askConfirm({
        title: `Terbitkan denda ${row.number}?`,
        message: `Denda ${formatCurrency(row.amount)} untuk ${row.customer_name} di ${ptName(row.entity_id)} diterbitkan dan dijurnal ke piutang denda.`,
        confirmLabel: "Terbitkan",
      }))) return;
      setBusy(row.id);
      try {
        await issueIntent.send({ id: row.id, aksi: "issue" }, (key) => issuePenalty(row.id, key));
        done(`Denda ${row.number} diterbitkan.`);
      } catch (e) { setActionError(apiErrorText(e, "Denda belum bisa diterbitkan.")); } finally { setBusy(""); }
    },
  };

  async function decide(reason) {
    const { row, decision: d } = decision;
    setBusy(row.id);
    try {
      if (row.kind === "izin_kredit") {
        await axios.post(`${API}/credit-overrides/${row.id}/decision`, { decision: d, reason: reason || "" });
      } else {
        await axios.post(`${API}/credit-profile-requests/${row.id}/decision`, { decision: d, note: reason || "" });
      }
      setDecision(null);
      done(`${row.kind === "izin_kredit" ? "Izin kredit" : "Pengajuan profil kredit"} ${row.customer_name} ${d === "approve" ? "disetujui" : "ditolak"}.`);
    } catch (e) {
      setDecision(null);
      setActionError(apiErrorText(e, "Keputusan belum bisa disimpan."));
      refresh();
    } finally { setBusy(""); }
  }

  if (customer) {
    return (
      <Customer360Panel customerId={customer.id} currentUser={currentUser} salesUsers={[]} selectedEntity={selectedEntity}
        onBack={() => { setCustomer(null); refresh(); }} onChanged={(m) => m && setNotice(m)}
        onError={(m) => setActionError(m)} />
    );
  }

  if (!canQueues) {
    return <div data-testid="credit-desk-view"><CreditOverridesPanel currentUser={currentUser} /></div>;
  }

  const rows = data?.items || [];
  const chips = QUEUES.map((x) => ({ key: x.key, label: x.label, count: summary ? summary[x.key] ?? 0 : undefined,
    testId: `credit-desk-chip-${x.key}` }));

  return (
    <div data-testid="credit-desk-view">
      {notice && (
        <div className="notice-bar success mb-2" role="status" data-testid="credit-desk-notice">
          <span>{notice}</span>
          <button type="button" className="icon-button" aria-label="Tutup" onClick={() => setNotice("")}>×</button>
        </div>
      )}
      <ErrorNotice message={actionError} onDismiss={() => setActionError("")} testId="credit-desk-action-error" />
      <EntityScopeBanner testId="credit-desk-scope" className="mb-2" />
      {combined && (
        <p className="mb-2 flex items-start gap-2 text-fs-12 text-kn-text-2" data-testid="credit-desk-combined-note">
          <Ban size={13} aria-hidden="true" className="mt-0.5 shrink-0" />
          Antrean gabungan, belum dieliminasi — hanya untuk melihat. Pilih satu PT di kepala aplikasi untuk memutus,
          menerbitkan denda, atau mencatat janji bayar.
        </p>
      )}

      <div className="section-card">
        <div className="section-body grid gap-2">
          <FilterSelect testId="credit-desk-chips" ariaLabel="Antrean kredit" value={queue} options={chips}
            onChange={(k) => { setQueue(k); setPage(1); setExpanded({}); }} />
          <SearchBox value={search} onChange={setSearch} testId="credit-desk-search"
            placeholder="Cari pelanggan, nomor pesanan, atau nota…" />
          {error ? (
            <ErrorNotice message={error} onRetry={load} testId="credit-desk-error" />
          ) : loading && !data ? (
            <p className="py-8 text-center text-fs-13 text-kn-text-2" data-testid="credit-desk-loading">Memuat antrean…</p>
          ) : rows.length === 0 ? (
            <p className="py-8 text-center text-fs-13 text-kn-text-2" data-testid="credit-desk-empty">{EMPTY}</p>
          ) : (
            <QueueTable queue={queue} rows={rows} ctx={ctx} />
          )}
          {!error && (data?.total || 0) > 0 && (
            <PaginationBar page={page} pageSize={PAGE_SIZE} total={data.total} loading={loading} label="baris"
              testId="credit-desk-pager" hasMore={page * PAGE_SIZE < data.total}
              onPrev={() => setPage((p) => Math.max(1, p - 1))} onNext={() => setPage((p) => p + 1)}
              exportConfig={{ columns: CSV_COLUMNS[queue], rows, fetchAll: fetchAllRows, filename: `antrean-kredit-${queue}` }}
              exportSpec={{ dataset: "credit_overrides", label: `antrean-kredit-${queue}`, unsupported: EXCEL_TIDAK_ADA }} />
          )}
        </div>
      </div>

      <div className="mt-3">
        <button type="button" className="ghost-button btn-sm" aria-expanded={showHistory} data-testid="credit-desk-history-toggle"
          onClick={() => setShowHistory((v) => !v)}>
          {showHistory ? <ChevronDown size={13} aria-hidden="true" /> : <ChevronRight size={13} aria-hidden="true" />}
          <History size={13} aria-hidden="true" />Riwayat izin kredit & pengajuan profil
        </button>
        {showHistory && (
          <div className="mt-2 grid gap-3" data-testid="credit-desk-history">
            <CreditOverridesPanel currentUser={currentUser} />
            <CreditProfileRequestsPanel currentUser={currentUser} />
          </div>
        )}
      </div>

      <ConfirmModal open={!!decision}
        title={decision ? `${decision.decision === "approve" ? "Setujui" : "Tolak"} ${decision.row.kind === "izin_kredit" ? "izin kredit" : "pengajuan profil kredit"}` : ""}
        message={decision ? `${decision.row.customer_name} · ${ptName(decision.row.entity_id)}${decision.row.amount > 0 ? ` · ${formatCurrency(decision.row.amount)}` : ""}` : ""}
        confirmLabel={decision?.decision === "approve" ? "Setujui" : "Tolak"} danger={decision?.decision === "reject"}
        withReason reasonLabel="Catatan keputusan" reasonRequired={decision?.decision === "reject"}
        onConfirm={decide} onCancel={() => setDecision(null)} testId="credit-desk-decision" />
      {promise && (
        <PromiseModal open customer={{ id: promise.customer_id, name: promise.customer_name }}
          defaultAmount={promise.total_outstanding} onClose={() => setPromise(null)}
          onDone={(m) => { setPromise(null); done(m); }} />
      )}
      {waive && <WaiveModal row={waive} ptName={ptName} onClose={() => setWaive(null)}
        onDone={(m) => { setWaive(null); done(m); }} />}
    </div>
  );
}

/** "Bebaskan" nota denda draf: alasan (daftar alasan denda) wajib + catatan (`POST /penalties/{id}/waive`). */
function WaiveModal({ row, ptName, onClose, onDone }) {
  const [reasons, setReasons] = useState([]);
  const [reasonCode, setReasonCode] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const intent = useIntentKey("pnl-bebas");
  useEffect(() => {
    (async () => {
      try { setReasons((await fetchMeta(row.entity_id || "")).reasons || []); } catch { setReasons([]); }
    })();
  }, [row.entity_id]);
  async function simpan() {
    if (!reasonCode) { setError("Pilih alasan pembebasan."); return; }
    setBusy(true); setError("");
    try {
      const body = { reason_code: reasonCode, note };
      await intent.send({ id: row.id, aksi: "waive", ...body }, (key) => waivePenalty(row.id, body, key));
      onDone(`Denda ${row.number} dibebaskan.`);
    } catch (e) { setError(apiErrorText(e, "Denda belum bisa dibebaskan.")); } finally { setBusy(false); }
  }
  return (
    <FormModal open onClose={onClose} title={`Bebaskan denda ${row.number}`} icon={Ban} size="sm" testId="credit-desk-waive"
      subtitle={`${row.customer_name} · ${ptName(row.entity_id)} · ${formatCurrency(row.amount)}`}
      onSubmit={simpan} submitLabel="Bebaskan" busy={busy} error={error}>
      <div className="grid gap-3">
        <div>
          <label className="field-label">Alasan <span className="text-kn-danger-text">*</span></label>
          <KNSelect value={reasonCode} onValueChange={setReasonCode} className="field" data-testid="credit-desk-waive-reason"
            placeholder="Pilih alasan" options={reasons.map((r) => ({ value: r.code, label: r.label }))} />
        </div>
        <div>
          <label className="field-label">Catatan <span className="font-normal text-kn-text-2">(opsional)</span></label>
          <textarea className="field" rows={2} value={note} data-testid="credit-desk-waive-note"
            onChange={(e) => setNote(e.target.value)} />
        </div>
      </div>
    </FormModal>
  );
}
