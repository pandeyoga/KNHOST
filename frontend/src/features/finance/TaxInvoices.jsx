import { apiErrorText } from "../../utils/apiError";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { can } from "../../config/roles";
import { FileText, RefreshCw, Search, Printer, Hash, Copy, Ban } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import { docDpp, usesDppNilaiLain } from "../../utils/taxBreakdown";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import DocumentActionsBar from "../documents/DocumentActionsBar";
import FormModal from "../../components/FormModal";
import FilterChips from "../../components/FilterChips";

/**
 * Faktur Pajak Jual (Sub-fase 1.9 — tax_invoices / fkt_).
 * List + kelola Faktur Pajak: isi NSFP resmi, terbitkan PENGGANTI, BATALKAN, cetak dokumen.
 * Penerbitan awal dilakukan dari Order detail (manual, opsional). Respons BE = bare object/array.
 *
 * Fase 4 · R2 — L-03: pop-up NSFP/Pengganti/Batal (`div fixed inset-0`) → `FormModal` baku, galat di dalam pop-up
 * (`fkt-modal-error`); L-01: saringan status (tab) → `FilterChips` (testid `fkt-filter-*` tetap).
 */
const FILTERS = [
  { id: "all", label: "Semua" },
  { id: "normal", label: "Normal" },
  { id: "pengganti", label: "Pengganti" },
  { id: "batal", label: "Batal" },
];

const STATUS_LABEL = { normal: "Normal", pengganti: "Pengganti", batal: "Batal" };

const STATUS_STYLE = {
  normal: "bg-[#E5F6EC] text-[#1B7A43]",
  pengganti: "bg-[#FFF3CD] text-[#8A6D00]",
  batal: "bg-[#FDE2E2] text-[#9B1C1C]",
};

import PagedRows from "@/components/PagedRows";

export default function TaxInvoices({ currentUser = {} }) {
  // FASE E-8 (E8.10b#2) — pajak keluaran adalah wilayah peran `finance`. Daftar peran
  // lama (`["manager","admin"]`) membuat Kasir/Finance melihat layarnya tetapi TANPA
  // satu pun tombol, padahal server sudah mengizinkan. Sekarang tiap tombol memakai
  // izin aksinya sendiri: batal TETAP manajer, sisanya boleh Finance.
  const perms = currentUser?.permissions || {};
  const canSetNsfp = can(perms, "tax_invoice", "update");
  const canReplace = can(perms, "tax_invoice", "replace");
  const canCancel = can(perms, "tax_invoice", "cancel");

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState("");

  // modal: { type: 'nsfp'|'replace'|'cancel', fkt }
  const [modal, setModal] = useState(null);
  const [nsfpVal, setNsfpVal] = useState("");
  const [kodeVal, setKodeVal] = useState("01");
  const [reasonVal, setReasonVal] = useState("");
  const [modalErr, setModalErr] = useState("");

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

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows
      .filter((f) => filter === "all" || f.status === filter)
      .filter((f) =>
        !q ||
        (f.number || "").toLowerCase().includes(q) ||
        (f.order_number || "").toLowerCase().includes(q) ||
        (f.customer_name || "").toLowerCase().includes(q) ||
        (f.nsfp || "").toLowerCase().includes(q)
      );
  }, [rows, filter, search]);

  const openDoc = (id) => window.open(`/api/tax-invoices/${id}/document`, "_blank", "noopener,noreferrer");

  const openModal = (type, fkt) => {
    setModal({ type, fkt });
    setNsfpVal(fkt.nsfp || "");
    setKodeVal(fkt.kode_transaksi || "01");
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
        await axios.patch(`${API}/tax-invoices/${fkt.id}/nsfp`, { nsfp: nsfpVal.trim(), kode_transaksi: kodeVal });
      } else if (type === "replace") {
        await axios.post(`${API}/tax-invoices/${fkt.id}/replace`, { reason: reasonVal.trim(), kode_transaksi: kodeVal });
      } else if (type === "cancel") {
        if (!reasonVal.trim()) { setModalErr("Alasan pembatalan wajib diisi."); setBusyId(""); return; }
        await axios.post(`${API}/tax-invoices/${fkt.id}/cancel`, { reason: reasonVal.trim() });
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
          <p className="text-[11.5px] text-[#6B6B73]">
            Faktur Pajak diterbitkan dari <b>detail Pesanan</b> (opsional — pajak tidak wajib, hanya untuk entitas PKP & transaksi ber-PPN).
            Di sini Anda mengisi NSFP resmi, menerbitkan faktur pengganti, atau membatalkan.
          </p>
          {/* Audit UI 24 Okt (066) → fase 4 · R2: saringan status = FilterChips (bukan tab; tab tingkat-2 milik Pusat Pajak). */}
          <div className="flex flex-wrap items-end gap-2">
            <FilterChips testId="fkt-filter" ariaLabel="Saring status faktur" value={filter} onChange={setFilter}
              options={FILTERS.map((f) => ({ key: f.id, label: f.label }))} />
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

          <div className="overflow-x-auto rounded-md border border-[#EFF0F2]">
            <table className="w-full min-w-[900px] text-[11.5px]">
              <thead className="bg-[#FAFBFC] text-[#6B6B73]">
                <tr className="whitespace-nowrap">
                  <th className="px-2.5 py-2 text-left font-bold uppercase tracking-wide text-[11px]">No. Faktur</th>
                  <th className="px-2.5 py-2 text-left font-bold uppercase tracking-wide text-[11px]">NSFP</th>
                  <th className="px-2.5 py-2 text-left font-bold uppercase tracking-wide text-[11px]">Pesanan</th>
                  <th className="px-2.5 py-2 text-left font-bold uppercase tracking-wide text-[11px]">Pembeli</th>
                  <th className="px-2.5 py-2 text-right font-bold uppercase tracking-wide text-[11px]">DPP</th>
                  <th className="px-2.5 py-2 text-right font-bold uppercase tracking-wide text-[11px]">PPN</th>
                  <th className="px-2.5 py-2 text-right font-bold uppercase tracking-wide text-[11px]" data-testid="fkt-col-total">Total (termasuk PPN)</th>
                  <th className="px-2.5 py-2 text-center font-bold uppercase tracking-wide text-[11px]">Status</th>
                  <th className="px-2.5 py-2 text-right font-bold uppercase tracking-wide text-[11px]">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-2.5 py-6 text-center text-[#8E8E93]">
                      {loading ? "Memuat…" : "Belum ada Faktur Pajak."}
                    </td>
                  </tr>
                ) : (
                  <PagedRows rows={filtered} testId="tax-invoices-pager">{(f) => {
                    const isActive = f.status !== "batal" && !f.replaced_by_id;
                    return (
                      <tr key={f.id} data-testid={`fkt-row-${f.id}`} className="border-t border-[#EFF0F2] hover:bg-[#F8FAFD]">
                        <td className="px-2.5 py-2 font-bold text-[#0058CC]">{f.number}</td>
                        <td className="px-2.5 py-2 text-[#3C3C43]">
                          {f.nsfp ? (
                            <span className="tabular-nums">{f.nsfp}</span>
                          ) : (
                            <span className="text-[#B23B14]">belum diisi</span>
                          )}
                        </td>
                        <td className="px-2.5 py-2">{f.order_number}</td>
                        <td className="px-2.5 py-2">
                          <span className="block truncate max-w-[160px]">{f.customer_name}</span>
                          <span className="text-[11px] text-[#8E8E93]">{f.customer_npwp || "tanpa NPWP"}</span>
                        </td>
                        {/* Keputusan pemilik K-03 (26 Okt) — DPP = harga sebelum PPN; rezim 12% → baris DPP nilai lain (11/12).
                            Dulu kolom DPP berisi nilai 11/12 tanpa keterangan. */}
                        <td className="px-2.5 py-2 text-right tabular-nums" data-testid={`fkt-dpp-${f.id}`}>
                          {formatCurrency(docDpp(f))}
                          {usesDppNilaiLain(f) && (
                            <span className="block whitespace-nowrap text-[10.5px] text-[#8E8E93]">nilai lain (11/12) {formatCurrency(f.dpp)}</span>
                          )}
                        </td>
                        <td className="px-2.5 py-2 text-right tabular-nums">{formatCurrency(f.ppn_amount)}</td>
                        <td className="px-2.5 py-2 text-right tabular-nums font-semibold">{formatCurrency(f.grand_total)}</td>
                        <td className="px-2.5 py-2 text-center">
                          <span className={`rounded px-1.5 py-0.5 text-[11px] font-bold ${STATUS_STYLE[f.status] || ""}`}>
                            {STATUS_LABEL[f.status] || f.status}
                          </span>
                        </td>
                        <td className="px-2.5 py-2">
                          <div className="flex items-center justify-end gap-1">
                            <DocumentActionsBar docType="tax_invoice" sourceId={f.id} entityId={f.entity_id}
                              number={f.number} label="Faktur Pajak" currentUser={currentUser}
                              compact autoCheckSignature={false} />
                            <button data-testid={`fkt-print-${f.id}`} className="icon-button" title="Cetak Faktur (format lama)" onClick={() => openDoc(f.id)}>
                              <Printer size={13} />
                            </button>
                            {canSetNsfp && f.status !== "batal" && (
                              <button data-testid={`fkt-nsfp-${f.id}`} className="icon-button" title="Isi NSFP resmi" onClick={() => openModal("nsfp", f)}>
                                <Hash size={13} />
                              </button>
                            )}
                            {canReplace && isActive && (
                              <button data-testid={`fkt-replace-${f.id}`} className="icon-button" title="Terbitkan Pengganti" onClick={() => openModal("replace", f)}>
                                <Copy size={13} />
                              </button>
                            )}
                            {canCancel && f.status !== "batal" && (
                              <button data-testid={`fkt-cancel-${f.id}`} className="icon-button text-[#B23B14]" title="Batalkan" onClick={() => openModal("cancel", f)}>
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

      {modal && (
        <FormModal open onClose={closeModal} size="sm" icon={modal.type === "cancel" ? Ban : modal.type === "replace" ? Copy : Hash}
          title={modal.type === "nsfp" ? "Isi NSFP Resmi" : modal.type === "replace" ? "Terbitkan Faktur Pengganti" : "Batalkan Faktur Pajak"}
          subtitle={`${modal.fkt.number} · ${modal.fkt.order_number || "—"}`}
          testId="fkt-modal" busy={busyId === modal.fkt.id}
          footer={(
            <div className="flex justify-end gap-2">
              <button type="button" className="secondary-button" onClick={closeModal} disabled={busyId === modal.fkt.id}>Batal</button>
              <button type="button" data-testid="fkt-modal-submit"
                className={modal.type === "cancel" ? "danger-button" : "primary-button"}
                disabled={busyId === modal.fkt.id} onClick={submitModal}>
                {busyId === modal.fkt.id ? "Memproses…" : "Konfirmasi"}
              </button>
            </div>
          )}>
          <ErrorNotice message={modalErr} onDismiss={() => setModalErr("")} testId="fkt-modal-error" />
          {modal.type === "nsfp" && (
            <div className="space-y-2">
              <label className="block text-[11px] font-semibold">Nomor Seri Faktur Pajak (16 digit)</label>
              <input data-testid="fkt-nsfp-input" value={nsfpVal} onChange={(e) => setNsfpVal(e.target.value)}
                placeholder="0100123456789012"
                className="field w-full tabular-nums" />
              <label className="block text-[11px] font-semibold mt-2">Kode Transaksi</label>
              <KNSelect
                data-testid="fkt-kode-select"
                value={kodeVal}
                onValueChange={setKodeVal}
                className="field w-full"
                options={["01", "02", "03", "04", "06", "07", "08", "09"].map((k) => ({ value: k, label: k }))}
              />
            </div>
          )}

          {modal.type === "replace" && (
            <div className="space-y-2">
              <label className="block text-[11px] font-semibold">Alasan Pengganti (opsional)</label>
              <input data-testid="fkt-reason-input" value={reasonVal} onChange={(e) => setReasonVal(e.target.value)}
                placeholder="mis. Koreksi alamat / nilai"
                className="field w-full" />
              <label className="block text-[11px] font-semibold mt-2">Kode Transaksi</label>
              <KNSelect
                data-testid="fkt-kode-select"
                value={kodeVal}
                onValueChange={setKodeVal}
                className="field w-full"
                options={["01", "02", "03", "04", "06", "07", "08", "09"].map((k) => ({ value: k, label: k }))}
              />
              <p className="text-[10.5px] text-[#8A6D00]">Faktur lama ditandai diganti; faktur baru berstatus PENGGANTI.</p>
            </div>
          )}

          {modal.type === "cancel" && (
            <div className="space-y-2">
              <label className="block text-[11px] font-semibold">Alasan Pembatalan (wajib)</label>
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
