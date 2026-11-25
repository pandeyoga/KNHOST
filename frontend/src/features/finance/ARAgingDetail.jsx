/**
 * ARAgingDetail — rincian piutang SATU pelanggan (pop-up dari layar Piutang `ar-aging`).
 *
 * Fase 3 · P4 — diekstrak dari ARAgingView.jsx (batas 500 baris) dan:
 *  · kepala panel di HP 390 px: dulu satu baris kaku (judul + ringkasan + lencana kredit + "Buat Nota Denda" + ×)
 *    sehingga tombol × berada di x≈403 (di luar layar) dan panel bisa digeser ke samping. Kini baris 1 = judul + ×
 *    (selalu terlihat), baris 2 = ringkasan + aksi, keduanya membungkus;
 *  · L-07: tabel mentah → `.table-wrap` + `.data-table` baku (bergulir di dalam wadahnya sendiri).
 * PK-43 (UX-15) — **Terima pembayaran** (MN-T3; dulu "Catat Pembayaran") (`ar-aging-pay`, bilah aksi kepala panel) dan **Bayar** per pesanan
 * (`ar-aging-pay-{id}`, kolom aksi menempel kanan) membuka form kwitansi baku (`onPay`). Tampil hanya bagi pemegang
 * `ar_receipt.create`; di "Semua PT" mati dengan alasan tertulis di bilah sendiri.
 * PK-41 (K-16) — tiap pesanan bisa dibuka menjadi baris per surat jalan (Tagihan, Tanggal, Jatuh Tempo, Nilai,
 * Terbayar, Sisa, Hari Lewat) + satu baris "Belum dikirim"; status umur = ikon + teks + warna (`status-pill`).
 * CR-T2 — bagian **Jadwal Tagihan**: baris jadwal tersimpan seluruh pesanan pelanggan (surat jalan, uang muka, baris
 * rencana cicilan, nota debit) dengan kolom Pesanan, Tagihan, Jatuh tempo, Nilai, Dibayar, Sisa, Telat (hari); pesanan dan
 * jurnalnya terbuka lewat Jejak Dokumen (L8). Memuat / galat / kosong ("Tidak ada tagihan terbuka.") dibedakan.
 * S5 (pelatihan 18 Nov, permintaan pemilik "piutang per pelanggan … aksinya lengkap") — dari satu tempat: **Rekening koran**
 * (kepala panel; tab yang sama dengan kartu pelanggan `CustomerStatementTab`: tampil, Cetak PDF, Salin pengingat — izin
 * `ar_receipt.view`/`credit_profile.view`, server `GET /customers/{id}/statement`) dan **Janji bayar** per pesanan (form
 * tindak lanjut penagihan yang sama dengan Penagihan & Penerimaan `WorklistFollowup`, izin `order.update` =
 * `POST /customers/{id}/followups`). Terima pembayaran (beberapa pesanan, titipan) tetap form `ReceivePaymentModal`.
 */
import { useState } from "react";
import {
  FileText, Loader2, Receipt, X, BadgeDollarSign, Wallet, ChevronDown, ChevronRight, AlertTriangle, CheckCircle2, Truck,
  BookOpen, PhoneCall, Route,
} from "lucide-react";
import { formatCurrency, formatDate } from "../../utils/formatters";
import StoreCreditBadge from "../../components/StoreCreditBadge";
import PenaltyPanel from "./payments/PenaltyPanel";
import { openTrace } from "../documents/trace/traceDeepLink";
import DocLink from "../documents/preview/DocLink";   // Meja gelombang 2 — nomor pesanan membuka rincian barang
import { penaltyMeta } from "./payments/paymentApi";
// INV-ROLE-01 — wewenang dibaca dari IZIN, bukan dari daftar nama peran.
import { can } from "../../config/roles";
import { AskKnButton } from "../../components/AskKnButton";
import EntityGatedButton, { EntityGateNote } from "../../components/EntityGatedButton";   // PK-42 (UX-05)
import CustomerStatementTab from "../crm/CustomerStatementTab";   // S5 — rekening koran dari rincian piutang
import { WorklistFollowup } from "../crm/CollectionWorklist";   // S5 — janji bayar per pesanan

// UAT 24 Okt (audit UI tahap 2) — G1-15: tanggal tampilan satu format ("25 Okt 2026", WIB) via formatDate.
const fmtDate = (iso) => formatDate(iso);

const PAY_WHAT = "mencatat pembayaran";

export default function ARAgingDetail({ detail, customerId, loading, currentUser, accruing, onAccrue, onRefresh, onClose,
  selectedEntity, onPay, notice = "", error = "", accrueNotice = null }) {
  // INV-ROLE-01 — sama seperti di layar induk: izin, bukan nama peran.
  const canAccrue = can(currentUser?.permissions || {}, "penalty", "issue");
  const canPay = Boolean(onPay) && can(currentUser?.permissions || {}, "ar_receipt", "create");   // PK-43
  const [open, setOpen] = useState({});   // PK-41 — pesanan yang rincian surat jalannya dibuka
  const toggle = (oid) => setOpen((o) => ({ ...o, [oid]: !o[oid] }));
  // S5 — rekening koran (izin baca sama dengan server `IZIN_RK`) & janji bayar (izin `order.update`).
  const perms = currentUser?.permissions || {};
  const canStatement = can(perms, "ar_receipt", "view") || can(perms, "credit_profile", "view");
  const canPromise = can(perms, "order", "update");
  const [showStatement, setShowStatement] = useState(false);
  const [followFor, setFollowFor] = useState(null);   // baris pesanan yang dicatat janji bayarnya
  const [followMsg, setFollowMsg] = useState("");
  const stmtCustomer = { id: customerId, name: detail?.customer_name || "",
    entity_id: selectedEntity && selectedEntity !== "all" ? selectedEntity : "" };
  const t = detail?.totals || {};
  // M34 — tombol nota denda nonaktif + alasan bila tidak ada estimasi denda yang belum jadi nota.
  const accrueReason = !detail ? "" : (t.denda_undocumented || 0) > 0.01 ? ""
    : "Tidak ada denda baru: semua denda sudah jadi nota atau belum ada tagihan lewat tenggang.";
  return (
    <div className="section-card mt-3" data-testid="ar-aging-detail">
      <div className="section-head flex-wrap items-start gap-x-2 gap-y-1.5">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          <FileText size={15} className="flex-shrink-0 text-[#0058CC]" />
          <h2 className="min-w-0 normal-case break-words" data-testid="ar-aging-detail-customer">{detail?.customer_name || "Rincian Piutang"}</h2>
          <StoreCreditBadge customerId={customerId} testId="ar-aging-store-credit" />
        </div>
        <button data-testid="ar-aging-detail-close" className="icon-button flex-shrink-0" onClick={onClose} aria-label="Tutup"><X size={14} /></button>
        {(detail || canAccrue || canPay) && (
          <div className="flex basis-full flex-wrap items-center gap-x-3 gap-y-1.5">
            {detail && (
              <span className="min-w-0 text-[11px] text-[#6B6B73]" data-testid="ar-aging-detail-summary">
                Belum lunas <b className="tabular-nums">{formatCurrency(t.total)}</b>{" "}
                (tercatat <b className="tabular-nums" data-testid="ar-detail-ledger-total">{formatCurrency(t.ar_ledger || 0)}</b>
                {" "}· belum dikirim <b className="tabular-nums" data-testid="ar-detail-exposure-total">{formatCurrency(t.exposure || 0)}</b>)
              </span>
            )}
            <div className="ml-auto flex flex-wrap items-center gap-2">
              {/* AG-T3 — "Tanya soal layar ini" (Asisten Keuangan; tampil menurut izin, bukan nama peran). */}
              <AskKnButton type="ar_receipt" id={customerId} label={detail?.customer_name || ""}
                buttonLabel="Tanya soal layar ini" className="secondary-button btn-sm" />
              {canStatement && (
                <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="ar-aging-statement"
                  aria-pressed={showStatement} onClick={() => setShowStatement((v) => !v)}>
                  <BookOpen size={13} aria-hidden="true" /> {showStatement ? "Tutup rekening koran" : "Rekening koran"}
                </button>
              )}
              {canAccrue && (
                <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="ar-aging-accrue"
                  disabled={accruing || Boolean(accrueReason)} title={accrueReason || undefined}
                  aria-describedby={accrueReason ? "ar-aging-accrue-reason" : undefined} onClick={onAccrue}>
                  {accruing ? <Loader2 size={13} className="animate-spin" /> : <Receipt size={13} />}
                  Buat Nota Denda
                </button>
              )}
              {canPay && (
                <EntityGatedButton selectedEntity={selectedEntity} what={PAY_WHAT} hint={false}
                  aria-describedby="ar-aging-pay-scope-note" data-testid="ar-aging-pay"
                  className="primary-button btn-sm whitespace-nowrap" disabled={loading}
                  onClick={() => onPay()}>
                  <Wallet size={13} aria-hidden="true" /> Terima pembayaran
                </EntityGatedButton>
              )}
            </div>
          </div>
        )}
      </div>
      <div className="section-body space-y-3">
        {/* PK-43 — alasan tombol bayar yang mati di "Semua PT" di bilah sendiri (kepala panel sudah berisi aksi). */}
        {canPay && <EntityGateNote selectedEntity={selectedEntity} what={PAY_WHAT} testId="ar-aging-pay-scope-note" className="!mb-0" />}
        {notice && <div className="notice-bar success" role="status" data-testid="ar-aging-detail-notice">{notice}</div>}
        {accrueNotice?.text && (
          <div className={`notice-bar ${accrueNotice.tone}`} role={accrueNotice.tone === "danger" ? "alert" : "status"}
            data-testid="ar-aging-accrue-notice">{accrueNotice.text}</div>
        )}
        {followMsg && <div className="notice-bar success" role="status" data-testid="ar-aging-followup-notice">{followMsg}</div>}
        {canStatement && showStatement && (
          <div className="rounded-lg border border-kn-divider p-2" data-testid="ar-aging-statement-panel">
            <h3 className="mb-1.5 flex items-center gap-1.5 text-fs-13 font-bold text-kn-text"><BookOpen size={14} aria-hidden="true" />Rekening koran</h3>
            <CustomerStatementTab customer={stmtCustomer} currentUser={currentUser} selectedEntity={selectedEntity} />
          </div>
        )}
        {canAccrue && accrueReason && (
          <p id="ar-aging-accrue-reason" className="text-fs-12 text-kn-neutral" data-testid="ar-aging-accrue-reason">
            {accrueReason}
          </p>
        )}
        {loading ? (
          <div className="grid gap-2" data-testid="ar-aging-detail-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
        ) : error ? (
          <div className="notice-bar danger flex flex-wrap items-center gap-2" role="alert" data-testid="ar-aging-detail-error">
            <AlertTriangle size={14} aria-hidden="true" />
            <span className="min-w-0 flex-1">{error}</span>
            {onRefresh && <button type="button" className="secondary-button btn-sm whitespace-nowrap" onClick={onRefresh}>Coba lagi</button>}
          </div>
        ) : !detail || (detail.items || []).length === 0 ? (
          <div className="py-8 text-center text-[12px] text-[#8E8E93]" data-testid="ar-aging-detail-empty">Tidak ada pesanan terbuka.</div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table head-wrap" data-testid="ar-aging-detail-table">
                <thead>
                  <tr>
                    <th>Pesanan</th>
                    <th>Jatuh Tempo</th>
                    <th className="text-center">Umur</th>
                    <th className="text-right">Total</th>
                    <th className="text-right">Terbayar</th>
                    <th className="text-right">Belum Lunas</th>
                    <th className="text-right" title="Piutang tercatat (barang sudah dikirim) · nilai pesanan yang belum dikirim">Tercatat · Belum dikirim</th>
                    <th className="text-right">Est. Denda</th>
                    <th>Nota Denda</th>
                    {(canPay || canPromise) && <th className="col-sticky-end"><span className="sr-only">Aksi</span></th>}
                  </tr>
                </thead>
                <tbody>
                  {detail.items.map((it) => (
                    <OrderRows key={it.order_id} it={it} open={!!open[it.order_id]} cols={canPay || canPromise ? 10 : 9}>
                    <tr data-testid={`ar-detail-row-${it.order_id}`}>
                      <td className="px-3 py-2 font-semibold whitespace-nowrap">
                        <button type="button" className="icon-button mr-1 align-middle" onClick={() => toggle(it.order_id)}
                          aria-expanded={!!open[it.order_id]} data-testid={`ar-detail-toggle-${it.order_id}`}
                          aria-label={`${open[it.order_id] ? "Tutup" : "Buka"} rincian surat jalan ${it.order_number}`}>
                          {open[it.order_id] ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                        </button>
                        <DocLink docType="sales_order" docId={it.order_id} number={it.order_number} entityId={it.entity_id}
                          perms={perms} testId={`ar-aging-order-${it.order_id}`} />
                        {it.has_plan && (
                          <span className="ml-1 rounded bg-[#EFF4FF] px-1 text-[9px] font-bold text-[#0058CC]"
                            title={`Rencana pembayaran ${it.plan_number}`}>RPB</span>
                        )}
                      </td>
                      {/* PK-41 — jatuh tempo surat jalan tertua yang masih bersisa (per surat jalan + termin) */}
                      <td className="px-3 py-2 text-[#3C3C43]" data-testid={`ar-detail-due-${it.order_id}`}>
                        {it.due_date ? fmtDate(it.due_date) : <span className="text-[#8E8E93]">belum dikirim</span>}
                      </td>
                      <td className="px-3 py-2 text-center"><AgeStatus it={it} /></td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(it.grand_total)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#1B7F4B]">{formatCurrency(it.paid_total)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-bold">{formatCurrency(it.outstanding)}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-[11px]" data-testid={`ar-detail-split-${it.order_id}`}>
                        <span className="text-[#0058CC]">{formatCurrency(it.ar_ledger || 0)}</span>
                        <span className="text-[#9A9BA3]"> · {formatCurrency(it.exposure || 0)}</span>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#B45309]">{it.denda_estimate > 0 ? formatCurrency(it.denda_estimate) : "—"}</td>
                      <td className="px-3 py-2" data-testid={`ar-detail-penalties-${it.order_id}`}>
                        {(it.penalties || []).length === 0 ? (
                          it.denda_estimate > 0
                            ? <span className="text-[10.5px] font-semibold text-[#9A9BA3]">belum jadi nota</span>
                            : <span className="text-[#C7C7CC]">—</span>
                        ) : (
                          <div className="flex flex-wrap items-center gap-1">
                            {(it.penalties || []).map((p) => {
                              const pm = penaltyMeta(p.status);
                              return (
                                <button key={p.id} type="button"
                                  data-testid={`ar-detail-penalty-${p.id}`}
                                  title={`${p.line_label || ""} · ${formatCurrency(p.amount)}${p.je_number ? ` · jurnal ${p.je_number}` : ""}`}
                                  onClick={() => openTrace({ docType: "penalty", docId: p.id, number: p.number })}
                                  className="rounded px-1.5 py-0.5 text-[9.5px] font-bold hover:underline"
                                  style={{ background: pm.bg, color: pm.fg }}>
                                  {p.number} · {formatCurrency(p.amount)}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </td>
                      {(canPay || canPromise) && (
                        <td className="col-sticky-end text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {canPromise && Number(it.outstanding || 0) > 0.005 && (
                              <button type="button" className="secondary-button btn-sm whitespace-nowrap"
                                data-testid={`ar-aging-promise-${it.order_id}`} title="Catat janji bayar / tindak lanjut penagihan"
                                onClick={() => { setFollowMsg(""); setFollowFor(it); }}>
                                <PhoneCall size={12} aria-hidden="true" /> Janji bayar
                              </button>
                            )}
                            {canPay && Number(it.outstanding || 0) > 0.005 && (
                              <EntityGatedButton selectedEntity={selectedEntity} what={PAY_WHAT} hint={false}
                                aria-describedby="ar-aging-pay-scope-note" data-testid={`ar-aging-pay-${it.order_id}`}
                                className="secondary-button btn-sm whitespace-nowrap" onClick={() => onPay(it.order_id)}>
                                Bayar
                              </EntityGatedButton>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                    </OrderRows>
                  ))}
                </tbody>
              </table>
            </div>

            <BillingSchedule items={detail.items || []} perms={perms} />

            {/* Nota denda nyata + keputusannya (terbitkan / ubah / bebaskan / catat bayar) */}
            <div>
              <div className="mb-1.5 flex flex-wrap items-center gap-2">
                <BadgeDollarSign size={14} className="text-[#B45309]" />
                <h3 className="text-[12px] font-bold text-[#1C1C1E]">Nota Denda Pelanggan Ini</h3>
                <span className="text-[10.5px] text-[#6B6B73]">
                  usulan {formatCurrency(t.penalty_draft)} · terbit belum dibayar{" "}
                  {formatCurrency(t.penalty_issued)} · dibebaskan {formatCurrency(t.penalty_waived)}
                </span>
                {(t.denda_undocumented || 0) > 0.01 && (
                  <span className="rounded bg-[#FFF3CD] px-1.5 py-0.5 text-[9.5px] font-bold text-[#8A6D00]"
                    data-testid="ar-aging-undocumented">
                    est. {formatCurrency(t.denda_undocumented)} belum jadi nota
                  </span>
                )}
              </div>
              <PenaltyPanel rows={detail.penalties || []} currentUser={currentUser}
                entityId={detail.entity_id || ""} onChanged={onRefresh} />
            </div>
          </>
        )}
      </div>
      {followFor && (
        <WorklistFollowup row={{ customer_id: customerId, customer_name: detail?.customer_name || "", order_id: followFor.order_id,
          order_number: followFor.order_number, outstanding: followFor.outstanding, overdue: followFor.overdue,
          days_late: followFor.days_late }}
          onClose={() => setFollowFor(null)}
          onDone={(m) => { setFollowFor(null); setFollowMsg(m || "Tindak lanjut dicatat."); onRefresh?.(); }} />
      )}
    </div>
  );
}

/** PK-41 — status umur pesanan: ikon + teks + warna (bukan warna saja). */
function AgeStatus({ it }) {
  if (!it.due_date) {
    return (
      <span className="status-pill pill-muted inline-flex items-center gap-1 whitespace-nowrap" data-testid={`ar-detail-age-${it.order_id}`}>
        <Truck size={12} aria-hidden="true" />Belum dikirim
      </span>
    );
  }
  return it.overdue ? (
    <span className="status-pill pill-danger inline-flex items-center gap-1 whitespace-nowrap" data-testid={`ar-detail-age-${it.order_id}`}>
      <AlertTriangle size={12} aria-hidden="true" />Telat {it.days_late} hari
    </span>
  ) : (
    <span className="status-pill pill-success inline-flex items-center gap-1 whitespace-nowrap" data-testid={`ar-detail-age-${it.order_id}`}>
      <CheckCircle2 size={12} aria-hidden="true" />Belum jatuh tempo
    </span>
  );
}

const SUMBER_LABEL = { surat_jalan: "", pesanan: "Pesanan (jurnal lama)", belum_dikirim: "Belum dikirim", uang_muka: "Uang muka" };
/** Judul baris: nomor surat jalan; tagihan tambahan nota debit (PK-32) "Nota debit {nomor}"; CR-T2 — "Uang muka" dan
 *  baris rencana cicilan (labelnya sendiri, mis. "Cicilan 1"). */
const lineTitle = (ln) => {
  if (ln.sumber === "nota_debit") return `Nota debit ${ln.ref_number}`;
  if (ln.sumber === "rencana") return ln.label || "Cicilan";
  if (ln.sumber === "uang_muka") return ln.label || "Uang muka";
  return SUMBER_LABEL[ln.sumber] || ln.ref_number;
};
/** CR-T2 — label kolom "Tagihan" bagian Jadwal Tagihan. */
const tagihanLabel = (ln) => (ln.sumber === "surat_jalan" ? `Surat jalan ${ln.ref_number}` : lineTitle(ln));

function hariLewat(ln) {
  if (ln.sumber === "belum_dikirim") return "—";
  if (ln.hari_lewat > 0) return `${ln.hari_lewat} hari`;
  if (ln.hari_lewat === 0) return "0 hari";
  return `${-ln.hari_lewat} hari lagi`;
}

/** Baris pesanan + (bila dibuka) tabel baris per surat jalan dan baris "Belum dikirim". */
function OrderRows({ it, open, cols = 9, children }) {
  return (
    <>
      {children}
      {open && (
        <tr data-testid={`ar-detail-lines-${it.order_id}`}>
          <td colSpan={cols} className="bg-kn-neutral-soft px-3 py-2">
            <table className="data-table" data-testid={`ar-detail-lines-table-${it.order_id}`}>
              <thead>
                <tr>
                  <th>Tagihan</th>
                  <th>Tanggal</th>
                  <th>Jatuh Tempo</th>
                  <th className="text-right">Nilai</th>
                  <th className="text-right">Terbayar</th>
                  <th className="text-right">Sisa</th>
                  <th className="text-right">Hari Lewat</th>
                </tr>
              </thead>
              <tbody>
                {(it.lines || []).map((ln) => (
                  <tr key={`${ln.sumber}:${ln.ref_id}:${ln.jurnal_id || ""}`} data-testid={`ar-line-${it.order_id}-${ln.sumber}`}>
                    <td className="font-medium">{lineTitle(ln)}</td>
                    <td>{ln.tanggal ? formatDate(ln.tanggal) : "—"}</td>
                    <td>{ln.jatuh_tempo ? formatDate(ln.jatuh_tempo) : "—"}</td>
                    <td className="text-right tabular-nums">{formatCurrency(ln.nilai)}</td>
                    <td className="text-right tabular-nums">{formatCurrency(ln.terbayar)}</td>
                    <td className="text-right tabular-nums font-semibold">{formatCurrency(ln.sisa)}</td>
                    <td className={`text-right tabular-nums ${ln.hari_lewat > 0 ? "text-kn-danger-text font-semibold" : "text-kn-text-2"}`}>
                      {hariLewat(ln)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(it.lines || []).some((ln) => ln.sumber === "belum_dikirim" && ln.uang_muka > 0) && (
              <p className="mt-1 text-fs-12 text-kn-text-2">
                Uang muka <b className="whitespace-nowrap tabular-nums">{formatCurrency((it.lines || []).find((ln) => ln.sumber === "belum_dikirim").uang_muka)}</b> sudah
                dikurangkan dari nilai yang belum dikirim.
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

/** CR-T2 — status telat satu baris jadwal: ikon + teks + warna (bukan warna saja). */
function LateCell({ ln }) {
  if (ln.hari_lewat > 0) {
    return (
      <span className="status-pill pill-danger inline-flex items-center gap-1 whitespace-nowrap">
        <AlertTriangle size={12} aria-hidden="true" />{ln.hari_lewat}
      </span>
    );
  }
  return <span className="text-kn-text-2 whitespace-nowrap">{ln.hari_lewat === 0 ? "0" : `${-ln.hari_lewat} lagi`}</span>;
}

/** Banyak baris jadwal sebelum kotak cari & saringan "hanya lewat jatuh tempo" ditampilkan. */
const SCHEDULE_FILTER_FROM = 8;

/** CR-T2 — Jadwal Tagihan pelanggan: baris jadwal tersimpan (tanpa bagian belum dikirim), jatuh tempo tertua dulu. */
function BillingSchedule({ items, perms }) {
  const [cari, setCari] = useState("");
  const [hanyaTelat, setHanyaTelat] = useState(false);
  const semua = items
    .flatMap((it) => (it.lines || []).filter((ln) => ln.sumber !== "belum_dikirim")
      .map((ln) => ({ ...ln, order_id: it.order_id, order_number: it.order_number, entity_id: it.entity_id })))
    .sort((a, b) => String(a.jatuh_tempo || "9999").localeCompare(String(b.jatuh_tempo || "9999")));
  const kata = cari.trim().toLowerCase();
  const rows = semua.filter((ln) => (!hanyaTelat || ln.hari_lewat > 0)
    && (!kata || `${ln.order_number} ${tagihanLabel(ln)}`.toLowerCase().includes(kata)));
  return (
    <div data-testid="ar-billing-schedule">
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <Receipt size={14} className="text-kn-text-2" aria-hidden="true" />
        <h3 className="text-[12px] font-bold text-[#1C1C1E]">Jadwal Tagihan</h3>
        {semua.length > 0 && <span className="text-fs-12 text-kn-text-2">{semua.length} tagihan terbuka</span>}
      </div>
      {semua.length > SCHEDULE_FILTER_FROM && (
        <div className="mb-1.5 flex flex-wrap items-center gap-2" data-testid="ar-billing-schedule-filters">
          <input className="field" type="search" placeholder="Cari pesanan / tagihan…" value={cari}
            aria-label="Cari jadwal tagihan" data-testid="ar-billing-schedule-search" onChange={(e) => setCari(e.target.value)} />
          <button type="button" className="filter-chip" aria-pressed={hanyaTelat} data-testid="ar-billing-schedule-overdue"
            onClick={() => setHanyaTelat((v) => !v)}>
            Hanya lewat jatuh tempo
          </button>
        </div>
      )}
      {semua.length === 0 ? (
        <div className="py-4 text-center text-[12px] text-[#8E8E93]" data-testid="ar-billing-schedule-empty">Tidak ada tagihan terbuka.</div>
      ) : rows.length === 0 ? (
        <div className="py-4 text-center text-[12px] text-[#8E8E93]" data-testid="ar-billing-schedule-nomatch">Tidak ada tagihan yang cocok dengan saringan.</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table head-wrap" data-testid="ar-billing-schedule-table">
            <thead>
              <tr>
                <th>Pesanan</th>
                <th>Tagihan</th>
                <th>Jatuh tempo</th>
                <th className="text-right">Nilai</th>
                <th className="text-right">Dibayar</th>
                <th className="text-right">Sisa</th>
                <th className="text-right">Telat (hari)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((ln) => (
                <tr key={`${ln.order_id}:${ln.line_id || ln.ref_id}:${ln.jurnal_id || ""}`} data-testid={`ar-schedule-${ln.order_id}-${ln.sumber}`}>
                  <td className="whitespace-nowrap">
                    <DocLink docType="sales_order" docId={ln.order_id} number={ln.order_number} entityId={ln.entity_id}
                      perms={perms} className="font-semibold" testId={`ar-schedule-doc-${ln.order_id}-${ln.sumber}`} />
                    <button type="button" className="icon-button ml-1 align-middle" title="Jejak Dokumen"
                      aria-label={`Jejak dokumen ${ln.order_number}`} data-testid={`ar-schedule-trace-${ln.order_id}-${ln.sumber}`}
                      onClick={() => openTrace({ docType: "sales_order", docId: ln.order_id, number: ln.order_number })}>
                      <Route size={13} aria-hidden="true" />
                    </button>
                  </td>
                  <td>
                    <span className="font-medium">{tagihanLabel(ln)}</span>
                    {ln.jurnal_id && " "}
                    {ln.jurnal_id && (
                      <button type="button" className="link-button whitespace-nowrap"
                        data-testid={`ar-schedule-journal-${ln.jurnal_id}`}
                        onClick={() => openTrace({ docType: "journal_entry", docId: ln.jurnal_id, number: ln.jurnal_number })}>
                        Jurnal {ln.jurnal_number}
                      </button>
                    )}
                  </td>
                  <td className="whitespace-nowrap">{ln.jatuh_tempo ? formatDate(ln.jatuh_tempo) : "—"}</td>
                  <td className="text-right tabular-nums">{formatCurrency(ln.nilai)}</td>
                  <td className="text-right tabular-nums">{formatCurrency(ln.terbayar)}</td>
                  <td className="text-right tabular-nums font-semibold">{formatCurrency(ln.sisa)}</td>
                  <td className="text-right"><LateCell ln={ln} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="ar-billing-schedule-note">
        Umur dihitung per tagihan: surat jalan, uang muka, atau baris rencana.
      </p>
    </div>
  );
}
