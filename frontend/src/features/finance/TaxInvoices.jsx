import { apiErrorText } from "../../utils/apiError";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { can } from "../../config/roles";
import { FileText, RefreshCw, Search, Printer, Hash, Copy, Ban, Info, AlertTriangle, CheckCircle2, X, FilePen, History,
  Send, Trash2 } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import { docDpp, usesDppNilaiLain, dppFactorText, taxRuleRows } from "../../utils/taxBreakdown";
import DetailModal from "../../components/DetailModal";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import ErrorNotice from "../../components/ErrorNotice";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import FormModal from "../../components/FormModal";
import FilterSelect from "../../components/FilterSelect";   // pola UI 16 Nov — saringan dropdown (dulu FilterChips)
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPatch, moneyPost } from "../../utils/moneyRequest";
import useFocusDoc, { gulirKe } from "../../hooks/useFocusDoc";
import FocusNotice from "../../components/FocusNotice";
import { useEntityScope } from "../../context/EntityScopeContext";
import { useAppNav } from "../../context/AppNavContext";
import { ROW_TARGET } from "../sales_admin/workDeskApi";
import { moneyMessage } from "../../utils/moneyConfirm";
import TaxOutputRecon from "./TaxOutputRecon";

/**
 * Faktur Pajak Jual (Sub-fase 1.9 — tax_invoices / fkt_).
 * List + kelola Faktur Pajak: isi NSFP resmi, terbitkan PENGGANTI, BATALKAN, cetak dokumen.
 * Penerbitan awal dilakukan dari Order detail (manual, opsional). Respons BE = bare object/array.
 *
 * Fase 4 · R2 — L-03: pop-up NSFP/Pengganti/Batal (`div fixed inset-0`) → `FormModal` baku, galat di dalam pop-up
 * (`fkt-modal-error`); L-01: saringan status (tab) → `FilterChips` (testid `fkt-filter-*` tetap).
 *
 * TX-T1 — pilihan kode transaksi = daftar kode PT faktur (`tax.kode_transaksi_diizinkan`, dibaca dari
 * `GET /settings/effective?entity_id=`); tombol Rincian menampilkan "Aturan pajak saat terbit" (potret `tax_snapshot`)
 * dan data pajak pembeli; lencana "Data pajak belum lengkap" bila `data_incomplete` terisi. Status = ikon + teks + warna.
 *
 * TX-T2 (TX-05, K-32) — status Draf/Diganti + sakelar jenis Faktur · Dokumen retur; kolom "Sumber" (pesanan, surat
 * jalan, nota kredit — bisa dibuka, L8); baris draf: Terbitkan (pop-up tanggal faktur, kode transaksi, NSFP boleh
 * menyusul; konfirmasi menyebut PT dan PPN) dan Buang draf (alasan wajib); lencana data pajak belum lengkap membuka
 * kartu pelanggan; panel Pencocokan PPN keluaran per masa (`TaxOutputRecon`). Tabel tetap 8 kolom (status di bawah nomor).
 */
const FILTERS = [
  { id: "all", label: "Semua" },
  { id: "draf", label: "Draf" },
  { id: "normal", label: "Normal" },
  { id: "pengganti", label: "Pengganti" },
  { id: "diganti", label: "Diganti" },
  { id: "batal", label: "Batal" },
];
const KINDS = [
  { key: "faktur", label: "Faktur" },
  { key: "retur", label: "Dokumen retur" },
];
const isRetur = (f) => f.doc_kind === "retur";

// KN_37 §1.3 — status = ikon + teks + warna (token `kn-*`).
const STATUS_META = {
  draf: { label: "Draf", icon: FilePen, cls: "bg-kn-action-soft text-kn-action" },
  normal: { label: "Normal", icon: CheckCircle2, cls: "bg-kn-success-soft text-kn-success-text" },
  pengganti: { label: "Pengganti", icon: Copy, cls: "bg-kn-warning-soft text-kn-warning-text" },
  diganti: { label: "Diganti", icon: History, cls: "bg-kn-neutral-soft text-kn-neutral" },
  batal: { label: "Batal", icon: Ban, cls: "bg-kn-danger-soft text-kn-danger-text" },
};
const KURANG_LABEL = { identitas_pajak: "Identitas pajak (NPWP/NIK) belum diisi", alamat_pajak: "Alamat pajak belum diisi" };
const ID_LABEL = { npwp: "NPWP", nik: "NIK" };

function StatusPill({ status }) {
  const m = STATUS_META[status] || { label: status, icon: Info, cls: "bg-kn-neutral-soft text-kn-neutral" };
  const Icon = m.icon;
  return <span className={`status-pill ${m.cls}`} data-testid="fkt-status"><Icon size={12} aria-hidden="true" />{m.label}</span>;
}

function IncompletePill({ fkt, onOpen }) {
  if (!(fkt.data_incomplete || []).length) return null;
  const teks = (fkt.data_incomplete || []).map((k) => KURANG_LABEL[k] || k).join(" · ");
  const isi = <><AlertTriangle size={12} aria-hidden="true" />Data pajak belum lengkap</>;
  // TX-T2 — lencana membuka kartu pelanggan (lengkapi data pajak di sana).
  if (onOpen && fkt.customer_id) {
    return (
      <button type="button" className="link-button" data-testid={`fkt-incomplete-${fkt.id}`}
        title={`${teks} — buka kartu pelanggan`} onClick={() => onOpen(fkt)}>
        <span className="status-pill bg-kn-warning-soft text-kn-warning-text whitespace-nowrap">{isi}</span>
      </button>
    );
  }
  return (
    <span className="status-pill bg-kn-warning-soft text-kn-warning-text" data-testid={`fkt-incomplete-${fkt.id}`}
      title={teks}>{isi}</span>
  );
}

/** TX-T2 — kolom "Sumber": pesanan (bisa dibuka) + surat jalan / nota kredit di bawahnya. */
function SourceCell({ fkt, onOpenOrder }) {
  return (
    <div className="min-w-0">
      {fkt.order_id && onOpenOrder ? (
        <button type="button" className="link-button whitespace-nowrap" data-testid={`fkt-source-${fkt.id}`}
          onClick={() => onOpenOrder(fkt)}>{fkt.order_number || "Pesanan"}</button>
      ) : <span className="whitespace-nowrap">{fkt.order_number || "—"}</span>}
      {fkt.trigger === "surat_jalan" && fkt.shipment_no && (
        <span className="block text-fs-12 text-kn-text-2">Surat jalan <span className="whitespace-nowrap">{fkt.shipment_no}</span></span>
      )}
      {isRetur(fkt) && (
        <span className="block text-fs-12 text-kn-text-2">
          <span className="whitespace-nowrap">Nota {fkt.credit_note_number || "—"}</span>{" "}
          <span className="whitespace-nowrap">atas {fkt.ref_tax_invoice_number || "—"}</span>
        </span>
      )}
    </div>
  );
}

function buyerId(f) {
  const ct = f.customer_tax;
  if (ct && ct.id_number) return `${ID_LABEL[ct.id_type] || "NPWP"} ${ct.id_number}`;
  return f.customer_npwp ? `NPWP ${f.customer_npwp}` : "tanpa NPWP/NIK";
}

import PagedRows from "@/components/PagedRows";

export default function TaxInvoices({ currentUser = {}, focusDoc, onClearFocus }) {
  // FASE E-8 (E8.10b#2) — pajak keluaran adalah wilayah peran `finance`. Daftar peran
  // lama (`["manager","admin"]`) membuat Kasir/Finance melihat layarnya tetapi TANPA
  // satu pun tombol, padahal server sudah mengizinkan. Sekarang tiap tombol memakai
  // izin aksinya sendiri: batal TETAP manajer, sisanya boleh Finance.
  const perms = currentUser?.permissions || {};
  const canSetNsfp = can(perms, "tax_invoice", "update");
  const canReplace = can(perms, "tax_invoice", "replace");
  const canCancel = can(perms, "tax_invoice", "cancel");
  const canIssue = can(perms, "tax_invoice", "create");   // TX-T2 — terbitkan draf / bangun ulang draf
  const { entities } = useEntityScope();
  const nav = useAppNav();
  const openOrder = (f) => nav?.openDocument && nav.openDocument({ ...ROW_TARGET.sales_order, focus_id: f.order_id,
    number: f.order_number });
  const openCustomer = (f) => nav?.openDocument && nav.openDocument({ ...ROW_TARGET.customer, focus_id: f.customer_id,
    number: f.customer_name });

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [kind, setKind] = useState("faktur");   // TX-T2 — sakelar jenis dokumen
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState("");
  // PK-12 — satu kunci idempotensi per aksi faktur (NSFP / pengganti / batal).
  const nsfpIntent = useIntentKey("fktn");
  const replaceIntent = useIntentKey("fktr");
  const cancelIntent = useIntentKey("fktc");
  const issueIntent = useIntentKey("fkti");     // TX-T2 — terbitkan draf
  const discardIntent = useIntentKey("fktd");   // TX-T2 — buang draf

  // modal: { type: 'nsfp'|'replace'|'cancel'|'issue'|'discard', fkt }
  const [modal, setModal] = useState(null);
  const [dateVal, setDateVal] = useState("");   // TX-T2 — tanggal faktur saat menerbitkan draf
  const [nsfpVal, setNsfpVal] = useState("");
  const [kodeVal, setKodeVal] = useState("01");
  const [reasonVal, setReasonVal] = useState("");
  const [modalErr, setModalErr] = useState("");
  const [detail, setDetail] = useState(null);       // TX-T1 — faktur yang rinciannya dibuka
  const [kodeByPt, setKodeByPt] = useState({});     // TX-T1 — {entity_id: [kode transaksi PT]}

  // TX-T1 — daftar kode transaksi PT faktur (pengaturan per PT). Belum termuat → hanya kode faktur itu sendiri.
  const loadKode = async (entityId) => {
    if (!entityId || kodeByPt[entityId]) return;
    try {
      const r = await axios.get(`${API}/settings/effective`, { params: { entity_id: entityId } });
      const list = r.data?.tax?.kode_transaksi_diizinkan;
      if (Array.isArray(list)) setKodeByPt((m) => ({ ...m, [entityId]: list }));
    } catch {
      /* pilihan tetap kode faktur; server menolak kode di luar daftar PT */
    }
  };
  const kodeOptions = (fkt) => {
    const list = kodeByPt[fkt.entity_id] || [];
    const all = list.includes(fkt.kode_transaksi) || !fkt.kode_transaksi ? list : [fkt.kode_transaksi, ...list];
    return (all.length ? all : [fkt.kode_transaksi || kodeVal]).map((k) => ({ value: k, label: k }));
  };

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await axios.get(`${API}/tax-invoices`);
      setRows(Array.isArray(r.data) ? r.data : []);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat Faktur Pajak."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // PK-44 (IA-04) — tautan dokumen: saring ke nomor faktur + sorot barisnya (faktur tidak punya panel rincian).
  const [sorot, setSorot] = useState("");
  const fokus = useFocusDoc(focusDoc, "tax_invoice", async (id) => {
    const r = await axios.get(`${API}/tax-invoices/${id}`);
    setFilter("all"); setKind(r.data?.doc_kind === "retur" ? "retur" : "faktur");
    setSearch(r.data?.number || ""); setSorot(id);
    gulirKe(`fkt-row-${id}`);
  }, onClearFocus);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows
      .filter((f) => (kind === "retur" ? isRetur(f) : !isRetur(f)))
      .filter((f) => filter === "all" || f.status === filter)
      .filter((f) =>
        !q ||
        (f.number || "").toLowerCase().includes(q) ||
        (f.order_number || "").toLowerCase().includes(q) ||
        (f.customer_name || "").toLowerCase().includes(q) ||
        (f.nsfp || "").toLowerCase().includes(q) ||
        (f.shipment_no || "").toLowerCase().includes(q) ||
        (f.credit_note_number || "").toLowerCase().includes(q)
      );
  }, [rows, filter, kind, search]);
  const draftCount = rows.filter((f) => f.status === "draf" && (kind === "retur" ? isRetur(f) : !isRetur(f))).length;

  const openDoc = (id) => window.open(`/api/tax-invoices/${id}/document`, "_blank", "noopener,noreferrer");

  const openModal = (type, fkt) => {
    setModal({ type, fkt });
    if (type !== "cancel" && type !== "discard") loadKode(fkt.entity_id);
    setNsfpVal(fkt.nsfp || "");
    setKodeVal(fkt.kode_transaksi || "");
    setDateVal(String(fkt.faktur_date || "").slice(0, 10));
    setReasonVal("");
    setModalErr("");
  };
  const closeModal = () => setModal(null);

  const submitModal = async () => {
    if (!modal) return;
    const { type, fkt } = modal;
    setBusyId(fkt.id);
    setModalErr("");
    try {
      if (type === "nsfp") {
        if (!nsfpVal.trim()) { setModalErr("NSFP wajib diisi."); setBusyId(""); return; }
        const body = { nsfp: nsfpVal.trim(), kode_transaksi: kodeVal };
        await nsfpIntent.send({ id: fkt.id, ...body }, (k) => moneyPatch(`${API}/tax-invoices/${fkt.id}/nsfp`, body, k));
      } else if (type === "replace") {
        const body = { reason: reasonVal.trim(), kode_transaksi: kodeVal };
        await replaceIntent.send({ id: fkt.id, aksi: "replace", ...body },
          (k) => moneyPost(`${API}/tax-invoices/${fkt.id}/replace`, body, k));
      } else if (type === "cancel") {
        if (!reasonVal.trim()) { setModalErr("Alasan pembatalan wajib diisi."); setBusyId(""); return; }
        const body = { reason: reasonVal.trim() };
        await cancelIntent.send({ id: fkt.id, aksi: "cancel", ...body },
          (k) => moneyPost(`${API}/tax-invoices/${fkt.id}/cancel`, body, k));
      } else if (type === "issue") {
        const body = { faktur_date: dateVal || null, kode_transaksi: kodeVal || null, nsfp: nsfpVal.trim() || null };
        await issueIntent.send({ id: fkt.id, aksi: "issue", ...body },
          (k) => moneyPost(`${API}/tax-invoices/${fkt.id}/issue`, body, k));
      } else if (type === "discard") {
        if (!reasonVal.trim()) { setModalErr("Alasan membuang draf wajib diisi."); setBusyId(""); return; }
        const body = { reason: reasonVal.trim() };
        await discardIntent.send({ id: fkt.id, aksi: "discard", ...body },
          (k) => moneyPost(`${API}/tax-invoices/${fkt.id}/discard`, body, k));
      }
      closeModal();
      await load();
    } catch (e) {
      setModalErr(apiErrorText(e, "Operasi gagal."));
    } finally {
      setBusyId("");
    }
  };

  return (
    <div data-testid="tax-invoices-view" className="space-y-4">
      <div className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-[#0058CC]" />
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wide text-[#0058CC]">Pajak · PPN Keluaran</p>
              <h2 className="text-[15px] font-bold">Faktur Pajak Keluaran</h2>
            </div>
          </div>
          <button data-testid="fkt-refresh" className="btn-secondary" onClick={load} disabled={loading}>
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat ulang
          </button>
        </div>
        <div className="section-body space-y-3">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="fkt-error" />
          <FocusNotice {...fokus} testId="fkt-focus-notice" />
          <p className="text-[11.5px] text-[#6B6B73]">
            PT yang menerbitkan faktur <b>per pesanan</b>: faktur diterbitkan dari <b>detail Pesanan</b> (hanya PT PKP & transaksi ber-PPN).
            PT yang memilih <b>per surat jalan</b>: draf muncul sendiri tiap barang keluar — periksa lalu Terbitkan di sini.
            Di sini juga Anda mengisi NSFP resmi, menerbitkan faktur pengganti, atau membatalkan.
          </p>
          {/* Audit UI 24 Okt (066) → fase 4 · R2: saringan status = FilterChips (bukan tab; tab tingkat-2 milik Pusat Pajak). */}
          <div className="flex flex-wrap items-end gap-2">
            <FilterSelect testId="fkt-filter" ariaLabel="Saring status faktur" value={filter} onChange={setFilter}
              options={FILTERS.map((f) => ({ key: f.id, label: f.label,
                count: f.id === "draf" ? draftCount : undefined }))} />
            <FilterSelect testId="fkt-kind" ariaLabel="Jenis dokumen pajak" value={kind} onChange={(k) => k && setKind(k)}
              options={KINDS} />
            <div className="relative ml-auto w-full sm:w-[300px]">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-[#8E8E93]" />
              <input
                data-testid="fkt-search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Cari nomor, pesanan, pelanggan, NSFP"
                title="Cari nomor faktur, nomor pesanan, nama pelanggan, atau NSFP"
                className="w-full rounded-md border border-[#E5E5EA] bg-white py-1.5 pl-7 pr-2 text-[12px]"
              />
            </div>
          </div>

          <div className="overflow-x-auto rounded-md border border-kn-divider">
            {/* Cek layar KN_37 — 5 kolom agar muat di kartu 1024 px (±730 px) tanpa gulir: status & NSFP di bawah
                nomor, DPP · PPN · total satu kolom berlabel, ikon aksi satu kisi 3 kolom, kolom aksi lekat di kanan.
                Uji jalan TX-T2 (integrator): 8 kolom = 1069 px — DPP/PPN/total tertutup di 1024 px. */}
            <table className="data-table head-wrap" data-testid="fkt-table">
              <thead>
                <tr>
                  <th>No. Faktur · Status · NSFP</th>
                  <th>Sumber</th>
                  <th>Pembeli</th>
                  <th className="text-right" data-testid="fkt-col-total">DPP · PPN · Total</th>
                  <th className="col-sticky-end text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-kn-text-2">
                      {loading ? "Memuat…" : filter === "draf" && !search.trim() ? "Tidak ada draf faktur."
                        : (rows.length ? "Tidak ada faktur yang cocok dengan saringan." : "Belum ada Faktur Pajak.")}
                    </td>
                  </tr>
                ) : (
                  <PagedRows rows={filtered} testId="tax-invoices-pager">{(f) => {
                    const isDraft = f.status === "draf";
                    const isActive = !["batal", "diganti", "draf"].includes(f.status) && !f.replaced_by_id;
                    return (
                      <tr key={f.id} data-testid={`fkt-row-${f.id}`} className={f.id === sorot ? "row-focus" : undefined}>
                        <td>
                          <span className="block whitespace-nowrap font-bold text-kn-action">{f.number}</span>
                          <span className="mt-1 inline-block"><StatusPill status={f.status} /></span>
                          <span className="mt-1 block whitespace-nowrap text-fs-12" data-testid={`fkt-nsfp-text-${f.id}`}>
                            <span className="text-kn-text-2">NSFP </span>
                            {f.nsfp ? <span className="tabular-nums">{f.nsfp}</span>
                              : <span className="text-kn-warning-text">belum diisi</span>}
                          </span>
                        </td>
                        <td><SourceCell fkt={f} onOpenOrder={openOrder} /></td>
                        <td>
                          <span className="block max-w-[150px] truncate" title={f.customer_name}>{f.customer_name}</span>
                          <span className="block text-fs-12 text-kn-text-2">{buyerId(f)}</span>
                          <IncompletePill fkt={f} onOpen={openCustomer} />
                        </td>
                        {/* Keputusan pemilik K-03 (26 Okt) — DPP = harga sebelum PPN; rezim 12% → baris DPP nilai lain.
                            TX-T1 — pecahan dari potret pajak faktur (faktur lama: 11/12). */}
                        <td className="text-right tabular-nums">
                          <span className="block whitespace-nowrap" data-testid={`fkt-dpp-${f.id}`}>
                            <span className="text-fs-12 text-kn-text-2">DPP </span>{formatCurrency(docDpp(f))}
                          </span>
                          {usesDppNilaiLain(f) && (
                            <span className="block whitespace-normal text-fs-12 text-kn-text-2">
                              <span className="whitespace-nowrap">nilai lain ({dppFactorText(f)})</span>{" "}
                              <span className="whitespace-nowrap">{formatCurrency(f.dpp)}</span>
                            </span>
                          )}
                          <span className="block whitespace-nowrap" data-testid={`fkt-ppn-${f.id}`}>
                            <span className="text-fs-12 text-kn-text-2">PPN </span>{formatCurrency(f.ppn_amount)}
                          </span>
                          <span className="block whitespace-nowrap font-semibold" data-testid={`fkt-total-${f.id}`}>
                            <span className="text-fs-12 font-normal text-kn-text-2">Total </span>{formatCurrency(f.grand_total)}
                          </span>
                        </td>
                        <td className="col-sticky-end">
                          {/* Satu kisi 3 kolom: rincian, aksi dokumen (`contents` → tombolnya ikut kisi), cetak, aksi faktur. */}
                          <div className="grid grid-cols-[repeat(3,2rem)] justify-end gap-1">
                            <button type="button" data-testid={`fkt-detail-${f.id}`} className="icon-button" title="Rincian faktur & aturan pajak"
                              aria-label="Rincian faktur" onClick={() => setDetail(f)}>
                              <Info size={13} />
                            </button>
                            <DocumentActionsBar docType="tax_invoice" sourceId={f.id} entityId={f.entity_id}
                              number={f.number} label="Faktur Pajak" currentUser={currentUser}
                              compact autoCheckSignature={false} className="contents" />
                            <button data-testid={`fkt-print-${f.id}`} className="icon-button" title="Cetak Faktur (format lama)" onClick={() => openDoc(f.id)}>
                              <Printer size={13} />
                            </button>
                            {isDraft && canIssue && (
                              <button data-testid={`fkt-issue-${f.id}`} className="icon-button text-kn-action" title="Terbitkan draf"
                                aria-label="Terbitkan draf" onClick={() => openModal("issue", f)}>
                                <Send size={13} />
                              </button>
                            )}
                            {isDraft && canCancel && (
                              <button data-testid={`fkt-discard-${f.id}`} className="icon-button text-kn-danger-text" title="Buang draf"
                                aria-label="Buang draf" onClick={() => openModal("discard", f)}>
                                <Trash2 size={13} />
                              </button>
                            )}
                            {canSetNsfp && !isDraft && f.status !== "batal" && (
                              <button data-testid={`fkt-nsfp-${f.id}`} className="icon-button" title="Isi NSFP resmi" onClick={() => openModal("nsfp", f)}>
                                <Hash size={13} />
                              </button>
                            )}
                            {canReplace && isActive && !isRetur(f) && (
                              <button data-testid={`fkt-replace-${f.id}`} className="icon-button" title="Terbitkan Pengganti" onClick={() => openModal("replace", f)}>
                                <Copy size={13} />
                              </button>
                            )}
                            {canCancel && !isDraft && f.status !== "batal" && (
                              <button data-testid={`fkt-cancel-${f.id}`} className="icon-button text-kn-danger-text" title="Batalkan" onClick={() => openModal("cancel", f)}>
                                <Ban size={13} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  }}</PagedRows>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <TaxOutputRecon canRebuild={canIssue} />

      {detail && <TaxInvoiceDetail fkt={detail} onClose={() => setDetail(null)} />}

      {modal && (
        <FormModal open onClose={closeModal} size="sm"
          icon={{ cancel: Ban, replace: Copy, issue: Send, discard: Trash2 }[modal.type] || Hash}
          title={{ nsfp: "Isi NSFP Resmi", replace: "Terbitkan Faktur Pengganti", cancel: "Batalkan Faktur Pajak",
            issue: isRetur(modal.fkt) ? "Terbitkan Dokumen Pajak Retur" : "Terbitkan Draf Faktur",
            discard: "Buang Draf" }[modal.type]}
          subtitle={`${modal.fkt.number} · ${modal.fkt.order_number || "—"}`}
          testId="fkt-modal" busy={busyId === modal.fkt.id}
          footer={(
            <div className="flex justify-end gap-2">
              <button type="button" className="secondary-button" onClick={closeModal} disabled={busyId === modal.fkt.id}>Batal</button>
              <button type="button" data-testid="fkt-modal-submit"
                className={["cancel", "discard"].includes(modal.type) ? "danger-button whitespace-nowrap" : "primary-button whitespace-nowrap"}
                disabled={busyId === modal.fkt.id} onClick={submitModal}>
                {busyId === modal.fkt.id ? "Memproses…"
                  : { issue: "Terbitkan", discard: "Buang Draf" }[modal.type] || "Konfirmasi"}
              </button>
            </div>
          )}>
          <ErrorNotice message={modalErr} onDismiss={() => setModalErr("")} testId="fkt-modal-error" />
          {modal.type === "nsfp" && (
            <div className="space-y-2">
              <label className="field-label">Nomor Seri Faktur Pajak (16 digit)</label>
              <input data-testid="fkt-nsfp-input" value={nsfpVal} onChange={(e) => setNsfpVal(e.target.value)}
                placeholder="0100123456789012"
                className="field w-full tabular-nums" />
              <label className="field-label mt-2">Kode Transaksi</label>
              <KNSelect
                data-testid="fkt-kode-select"
                value={kodeVal}
                onValueChange={setKodeVal}
                className="field w-full"
                options={kodeOptions(modal.fkt)}
              />
              <p className="text-fs-12 text-kn-text-2">Pilihan = kode transaksi yang dipakai PT ini (Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak).</p>
            </div>
          )}

          {modal.type === "replace" && (
            <div className="space-y-2">
              <label className="field-label">Alasan Pengganti (opsional)</label>
              <input data-testid="fkt-reason-input" value={reasonVal} onChange={(e) => setReasonVal(e.target.value)}
                placeholder="mis. Koreksi alamat / nilai"
                className="field w-full" />
              <label className="field-label mt-2">Kode Transaksi</label>
              <KNSelect
                data-testid="fkt-kode-select"
                value={kodeVal}
                onValueChange={setKodeVal}
                className="field w-full"
                options={kodeOptions(modal.fkt)}
              />
              <p className="text-fs-12 text-kn-text-2">Pilihan = kode transaksi yang dipakai PT ini (Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak).</p>
              <p className="text-fs-12 text-kn-warning-text">Faktur lama ditandai diganti; faktur baru berstatus PENGGANTI.</p>
            </div>
          )}

          {modal.type === "issue" && (
            <div className="space-y-2" data-testid="fkt-issue-form">
              <label className="field-label">Tanggal faktur</label>
              <KNDatePicker data-testid="fkt-issue-date" value={dateVal} onChange={(v) => setDateVal(v || "")}
                placeholder="Tanggal faktur" />
              <p className="text-fs-12 text-kn-text-2">Bawaan = tanggal surat jalan / nota kreditnya. Masa pajak yang sudah ditandai dilaporkan ditolak.</p>
              <label className="field-label mt-2">Kode transaksi</label>
              <KNSelect data-testid="fkt-kode-select" value={kodeVal} onValueChange={setKodeVal} className="field w-full"
                options={kodeOptions(modal.fkt)} />
              <label className="field-label mt-2" htmlFor="fkt-issue-nsfp">NSFP (boleh menyusul)</label>
              <input id="fkt-issue-nsfp" data-testid="fkt-issue-nsfp" value={nsfpVal} onChange={(e) => setNsfpVal(e.target.value)}
                placeholder="0100123456789012" className="field w-full tabular-nums" />
              <p className="rounded-md bg-kn-neutral-soft px-3 py-2 text-fs-13" data-testid="fkt-issue-confirm">
                {moneyMessage({ effect: `${isRetur(modal.fkt) ? "Dokumen pajak retur" : "Faktur"} ${modal.fkt.number} diterbitkan; PPN-nya ${isRetur(modal.fkt) ? "mengurangi" : "masuk"} rekap PPN keluaran masa tanggal faktur.`,
                  amount: modal.fkt.ppn_amount, entityId: modal.fkt.entity_id, entities })}
              </p>
            </div>
          )}

          {modal.type === "discard" && (
            <div className="space-y-2">
              <label className="field-label" htmlFor="fkt-discard-reason">Alasan membuang draf (wajib)</label>
              <input id="fkt-discard-reason" data-testid="fkt-reason-input" value={reasonVal}
                onChange={(e) => setReasonVal(e.target.value)} placeholder="mis. Pelanggan minta faktur digabung"
                className="field w-full" />
              <p className="text-fs-12 text-kn-text-2">Draf yang dibuang tidak dibuat ulang otomatis; sumbernya tetap tampil di Pencocokan PPN keluaran.</p>
            </div>
          )}

          {modal.type === "cancel" && (
            <div className="space-y-2">
              <label className="field-label">Alasan Pembatalan (wajib)</label>
              <input data-testid="fkt-reason-input" value={reasonVal} onChange={(e) => setReasonVal(e.target.value)}
                placeholder="mis. Transaksi dibatalkan pelanggan"
                className="field w-full" />
            </div>
          )}
        </FormModal>
      )}
    </div>
  );
}


/** TX-T1 — rincian faktur: aturan pajak saat terbit (potret) + data pajak pembeli + kekurangannya. */
function TaxInvoiceDetail({ fkt, onClose }) {
  const aturan = taxRuleRows(fkt);
  const ct = fkt.customer_tax || {};
  const kurang = fkt.data_incomplete || [];
  return (
    <DetailModal open onClose={onClose} size="md" label={`Rincian Faktur Pajak ${fkt.number}`} testId="fkt-detail">
      <div className="section-card">
        <div className="section-head">
          <div className="min-w-0">
            <h2 className="text-fs-14 font-bold">Faktur Pajak {fkt.number}</h2>
            <p className="text-fs-12 text-kn-text-2">{fkt.order_number || "—"} · kode transaksi {fkt.kode_transaksi || "—"}</p>
          </div>
          <button type="button" className="icon-button" aria-label="Tutup" data-testid="fkt-detail-close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <div className="section-body space-y-3">
          <div className="flex flex-wrap items-center gap-2"><StatusPill status={fkt.status} /><IncompletePill fkt={fkt} /></div>
          <section data-testid="fkt-detail-rules">
            <h3 className="field-label">Aturan pajak saat terbit</h3>
            {aturan ? (
              <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-x-3 gap-y-1 text-fs-13">
                {aturan.map((r) => (
                  <div key={r.key} className="contents" data-testid={`fkt-rule-${r.key}`}>
                    <dt className="text-kn-text-2">{r.label}</dt><dd className="font-semibold">{r.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-fs-12 text-kn-text-2" data-testid="fkt-detail-rules-lama">
                Faktur ini terbit sebelum aturan pajak disimpan bersama faktur: tarif {Number(fkt.ppn_rate || 0)}%,
                DPP nilai lain {fkt.dpp_nilai_lain ? "11/12" : "tidak dipakai"}, dua angka di belakang koma.
              </p>
            )}
            <p className="mt-1 text-fs-12 text-kn-text-2">Mengubah pengaturan pajak sesudahnya tidak mengubah faktur ini.</p>
          </section>
          <section data-testid="fkt-detail-buyer">
            <h3 className="field-label">Pembeli menurut data pajak</h3>
            <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-x-3 gap-y-1 text-fs-13">
              <dt className="text-kn-text-2">Identitas</dt><dd className="font-semibold">{buyerId(fkt)}</dd>
              <dt className="text-kn-text-2">Nama</dt><dd>{ct.tax_name || fkt.customer_name || "—"}</dd>
              <dt className="text-kn-text-2">Alamat</dt><dd>{ct.tax_address || fkt.customer_address || "—"}</dd>
              <dt className="text-kn-text-2">Status PKP</dt>
              <dd>{ct.is_pkp === true ? "PKP" : ct.is_pkp === false ? "Bukan PKP" : "Belum diisi"}</dd>
            </dl>
            {kurang.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-fs-12 text-kn-warning-text" data-testid="fkt-detail-incomplete">
                {kurang.map((k) => <li key={k}>{KURANG_LABEL[k] || k}</li>)}
              </ul>
            )}
            {kurang.length > 0 && (
              <p className="mt-1 text-fs-12 text-kn-text-2">Lengkapi di data pelanggan (bagian Data pajak) lalu terbitkan pengganti bila perlu.</p>
            )}
          </section>
        </div>
      </div>
    </DetailModal>
  );
}
