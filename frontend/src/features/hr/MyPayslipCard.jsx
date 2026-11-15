import { useEffect, useRef, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Wallet, FileText, ChevronDown, ChevronUp, CheckCircle2, Clock3 } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";
import { rp, openPayslipPdf, runTypeLabel, slipGroups } from "./payrollUtils";
import { formatDate, formatPeriod } from "../../utils/formatters";

// PY-T5 — kartu "Slip Gaji Saya" di Profil Saya (menggantikan "Slip Gaji Terakhir"). Server hanya mengirim slip yang
// sudah TERBIT bagi pemiliknya (`hr.slip_swalayan_sejak` PT: bawaan setelah gaji dibayar) — layar tidak menyaring lagi.
// Isi: ringkasan slip terakhir + riwayat per tahun (pemilih tahun dari `years`), tiap baris bisa dibuka menjadi rincian
// komponen Pendapatan · Potongan · Gaji bersih, dan PDF per baris. Kartu berbentuk daftar (bukan tabel lebar) supaya
// utuh di HP 390 px: dua kolom per baris di HP, lima kolom berjudul mulai 640 px; ringkasan di atas riwayat, dan di
// samping kirinya mulai 1280 px (di 1024 px riwayat tetap selebar kartu supaya lima kolomnya tidak berdesakan).
export const TEKS_GALAT = "Slip belum bisa dimuat.";
export const TEKS_KOSONG = "Belum ada slip gaji yang terbit.";
export const ketKosong = (since) => (since === "disahkan"
  ? "Slip muncul setelah penggajian disahkan." : "Slip muncul setelah gaji dibayar.");

const GRUP_SLIP = ["pendapatan", "potongan"];
const BARIS = "grid-cols-2 gap-x-3 gap-y-1 items-center "
  + "sm:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)_minmax(0,1.1fr)_minmax(0,1fr)_auto]";

function StatusBayar({ slip, testId }) {
  if (slip.paid_date || slip.status === "paid") {
    return (
      <span className="status-pill status-paid" data-testid={testId}>
        <CheckCircle2 size={12} aria-hidden="true" />
        <span className="sm:hidden">Dibayar</span> {slip.paid_date ? formatDate(slip.paid_date) : ""}
      </span>
    );
  }
  return (
    <span className="status-pill status-pending" data-testid={testId}>
      <Clock3 size={12} aria-hidden="true" /> Belum dibayar
    </span>
  );
}

/** Rincian komponen satu slip: Pendapatan · Potongan, lalu Gaji bersih. */
export function SlipRincian({ slip, testId }) {
  const groups = slipGroups(slip).filter((g) => GRUP_SLIP.includes(g.key));
  return (
    <div className="mt-2 rounded-lg bg-kn-neutral-soft p-3" data-testid={testId}>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {groups.map((g) => (
          <div key={g.key} data-testid={`${testId}-${g.key}`}>
            <p className="text-fs-12 font-bold uppercase text-kn-text-2 mb-1">{g.label}</p>
            {g.rows.length === 0 ? (
              <p className="text-fs-13 text-kn-text-2">—</p>
            ) : g.rows.map((c, i) => (
              <div key={`${c.code}-${i}`} className="flex items-start justify-between gap-3 text-fs-13 py-0.5">
                <span className="min-w-0 break-words">{c.label || c.name || c.code}</span>
                <span className="tabular-nums whitespace-nowrap">{rp(c.amount)}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="mt-2 pt-2 border-t border-kn-divider flex items-center justify-between gap-3 text-fs-14 font-bold">
        <span>Gaji bersih</span>
        <span className="tabular-nums" data-testid={`${testId}-net`}>{rp(slip.net)}</span>
      </div>
    </div>
  );
}

export function MyPayslipCard() {
  const [data, setData] = useState(null);
  const [latest, setLatest] = useState(null);
  const [year, setYear] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState({});
  const [busy, setBusy] = useState("");
  const [pdfErr, setPdfErr] = useState("");
  const first = useRef(true);

  useEffect(() => { load(null); }, []); // eslint-disable-line
  async function load(y) {
    setLoading(true); setError(false);
    try {
      const r = await axios.get(`${API}/hr/payslips/me`, { params: y ? { year: y } : {} });
      const d = r.data || {};
      const years = d.years || [];
      // Tahun berjalan belum punya slip (mis. awal Januari) → buka tahun terbaru yang punya slip.
      if (first.current && !y && (d.payslips || []).length === 0 && years.length > 0 && !years.includes(d.year)) {
        first.current = false;
        await load(years[0]);
        return;
      }
      if (first.current || (years.length > 0 && Number(d.year) === years[0])) setLatest((d.payslips || [])[0] || null);
      first.current = false;
      setData(d); setYear(d.year ?? y); setOpen({});
    } catch (_) {
      setError(true);
    } finally {
      setLoading(false);
    }
  }
  async function openPdf(id) {
    setBusy(id); setPdfErr("");
    try { await openPayslipPdf(id); } catch (_) { setPdfErr("Slip PDF belum bisa dibuka. Coba lagi."); } finally { setBusy(""); }
  }

  const slips = data?.payslips || [];
  const years = data?.years || [];
  const kosong = !error && data && years.length === 0 && slips.length === 0;
  return (
    <div className="section-card" data-testid="ess-payslip-card">
      <div className="section-head">
        <h2 className="flex items-center gap-2"><Wallet size={15} className="text-kn-action" aria-hidden="true" /> Slip Gaji Saya</h2>
      </div>
      <div className="section-body">
        {loading && !data ? (
          <p className="text-fs-13 text-kn-text-2 py-3" data-testid="ess-payslip-loading">Memuat slip…</p>
        ) : error ? (
          <ErrorNotice message={TEKS_GALAT} onRetry={() => load(year)} testId="ess-payslip-error" />
        ) : kosong ? (
          <div className="py-3" data-testid="ess-payslip-empty">
            <p className="text-fs-14 font-semibold">{TEKS_KOSONG}</p>
            <p className="text-fs-13 text-kn-text-2 mt-0.5" data-testid="ess-payslip-empty-hint">{ketKosong(data?.visible_since)}</p>
          </div>
        ) : (
          <>
          <ErrorNotice message={pdfErr} onDismiss={() => setPdfErr("")} testId="ess-payslip-pdf-error" />
          <div className={`grid grid-cols-1 gap-4 ${latest ? "xl:grid-cols-[minmax(0,260px)_minmax(0,1fr)]" : ""}`}>
            {latest && (
              <div className="rounded-lg bg-kn-action-soft p-3 self-start sm:flex sm:items-end sm:justify-between sm:gap-4 xl:block"
                data-testid="ess-payslip-latest">
                <div className="min-w-0">
                <p className="text-fs-13 text-kn-text-2">
                  Periode {formatPeriod(latest.period)}{latest.run_type && latest.run_type !== "regular" ? ` · ${runTypeLabel(latest.run_type)}` : ""}
                </p>
                <p className="text-fs-12 text-kn-text-2 mt-1">Gaji bersih diterima</p>
                <p className="text-fs-24 font-bold tabular-nums text-kn-action" data-testid="ess-payslip-latest-net">{rp(latest.net)}</p>
                <p className="text-fs-13 text-kn-text-2 mt-0.5" data-testid="ess-payslip-latest-paid">
                  {latest.paid_date ? `Dibayar ${formatDate(latest.paid_date)}` : "Belum dibayar"}
                </p>
                </div>
                <button type="button" data-testid="ess-payslip-pdf" disabled={!!busy} onClick={() => openPdf(latest.id)}
                  className="primary-button w-full sm:w-auto xl:w-full justify-center mt-2 sm:mt-0 xl:mt-2 whitespace-nowrap">
                  <FileText size={14} aria-hidden="true" /> {busy === latest.id ? "Membuka…" : "Lihat slip (PDF)"}
                </button>
              </div>
            )}
            <div className="min-w-0" data-testid="ess-payslip-history">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <h3 className="text-fs-14 font-bold">Riwayat slip</h3>
                <FilterChips testId="ess-payslip-years" ariaLabel="Pilih tahun slip" value={year}
                  onChange={(y) => y && y !== year && load(y)}
                  options={years.map((y) => ({ key: y, label: String(y) }))} />
              </div>
              <div className={`hidden sm:grid ${BARIS} text-fs-12 font-bold uppercase text-kn-text-2 pb-1 border-b border-kn-divider`}>
                <span>Periode</span><span>Jenis</span><span>Dibayar</span><span className="text-right">Gaji bersih</span><span className="sr-only">Aksi</span>
              </div>
              {loading ? (
                <p className="text-fs-13 text-kn-text-2 py-3">Memuat slip…</p>
              ) : slips.length === 0 ? (
                <p className="text-fs-13 text-kn-text-2 py-3" data-testid="ess-payslip-year-empty">Tidak ada slip yang terbit di tahun {year}.</p>
              ) : (
                <ul className="divide-y divide-kn-divider">
                  {slips.map((s) => {
                    const buka = !!open[s.id];
                    return (
                      <li key={s.id} className="py-2" data-testid={`ess-payslip-row-${s.id}`}>
                        <div className={`grid ${BARIS}`}>
                          <span className="text-fs-13 font-semibold">{formatPeriod(s.period)}</span>
                          <span className="text-fs-13 text-right sm:text-left" data-testid={`ess-payslip-type-${s.id}`}>{runTypeLabel(s.run_type)}</span>
                          <span><StatusBayar slip={s} testId={`ess-payslip-paid-${s.id}`} /></span>
                          <span className="text-fs-13 font-bold tabular-nums text-right" data-testid={`ess-payslip-net-${s.id}`}>{rp(s.net)}</span>
                          <span className="col-span-2 sm:col-span-1 flex justify-end gap-2">
                            <button type="button" className="ghost-button btn-sm whitespace-nowrap" aria-expanded={buka}
                              aria-controls={`ess-payslip-detail-${s.id}`} data-testid={`ess-payslip-toggle-${s.id}`}
                              onClick={() => setOpen((o) => ({ ...o, [s.id]: !o[s.id] }))}>
                              {buka ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />} Rincian
                            </button>
                            <button type="button" className="secondary-button btn-sm whitespace-nowrap" disabled={!!busy}
                              data-testid={`ess-payslip-rowpdf-${s.id}`} onClick={() => openPdf(s.id)}>
                              <FileText size={13} aria-hidden="true" /> {busy === s.id ? "Membuka…" : "PDF"}
                            </button>
                          </span>
                        </div>
                        {buka && <div id={`ess-payslip-detail-${s.id}`}><SlipRincian slip={s} testId={`ess-payslip-detail-${s.id}`} /></div>}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
          </>
        )}
      </div>
    </div>
  );
}
