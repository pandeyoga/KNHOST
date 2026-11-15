/**
 * MyIncentiveCard — KM-T5 · kartu **Capaian & Insentif Saya** (keputusan K-22, K-46).
 *
 * Sumber: `GET /api/incentive/me?period=YYYY-MM` (cukup login; PT = PT aktif, sales = pelaku — server tidak menerima
 * `sales_id`). Isi: tiga baris capaian bulan itu (omzet, uang masuk, realisasi harga — tanpa margin dan tanpa piutang),
 * baris lembar insentif yang SUDAH disahkan milik pelaku (periode bayar = bulan itu) beserta potret angka dasarnya, dan —
 * hanya di PT yang masih memakai komisi otomatis — baris "Komisi berjalan (hitungan otomatis)".
 *
 * Dipasang di Beranda Sales (`home/SalesHome.jsx`), Profil Saya (`hr/EmployeeSelfService.jsx`, `hideWhenEmpty`), dan
 * layar HP (`sales/mobile/MobileCollectionTargets.jsx` bagian Target; `MobileSalesHome.jsx` untuk PT Lembar Insentif).
 * `variant="mobile"`: kartu `m-card`, pemilih & tombol sentuh ≥ 48 px. Angka rupiah tidak pernah patah
 * (`whitespace-nowrap`, `formatCurrency` memakai spasi tak-patah — "-Rp" utuh).
 */
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronDown, ChevronUp, Info, Target, Wallet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import { formatCurrency, formatDecimal, formatPeriod, todayWib } from "../../utils/formatters";

export const TEKS_MEMUAT = "Memuat capaian…";
/** Galat: kalimat + tombol "Coba lagi" bawaan `ErrorNotice` (tampil "Capaian belum bisa dimuat. ⟳ Coba lagi"). */
export const TEKS_GALAT = "Capaian belum bisa dimuat.";
export const TEKS_KOSONG_LEMBAR = "Belum ada insentif yang disahkan untuk Anda.";
export const TEKS_CATATAN = "Nominal insentif diputuskan pimpinan dengan melihat capaian. Tidak ada rumus otomatis.";
export const TEKS_CATATAN_OTOMATIS = "Nominal di lembar insentif diputuskan pimpinan dengan melihat capaian. Komisi "
  + "berjalan dihitung otomatis sampai PT ini beralih ke Lembar Insentif.";
export const TEKS_TARGET_KOSONG = "target belum diisi";
/** Sakelar PT (`hr.payroll_commission_mode`) yang mematikan komisi otomatis. */
export const MODE_TANPA_MESIN = ["sheet", "off"];

const STATUS = {
  approved: { cls: "status-done", Icon: CheckCircle2, label: "Disahkan", teks: (b) => `Dibayar bersama gaji ${b}` },
  paid: { cls: "status-shipped", Icon: Wallet, label: "Dibayarkan", teks: (b) => `Sudah dibayar (gaji ${b})` },
};

/** Bulan berjalan WIB, `YYYY-MM`. */
export const bulanIni = () => String(todayWib()).slice(0, 7);

/** Pilihan bulan: `cur` dan 12 bulan sebelumnya (terbaru di atas), label "Oktober 2026". */
export function pilihanBulan(cur, n = 12) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(cur || bulanIni())) || /^(\d{4})-(\d{2})$/.exec(bulanIni());
  const idx0 = Number(m[1]) * 12 + Number(m[2]) - 1;
  const out = [];
  for (let k = 0; k <= n; k += 1) {
    const idx = idx0 - k;
    const v = `${Math.floor(idx / 12)}-${String((idx % 12) + 1).padStart(2, "0")}`;
    out.push({ value: v, label: formatPeriod(v) });
  }
  return out;
}

/** Persen satu desimal berkoma: 86.2 → "86,2 %"; kosong → "—". */
export const persen = (v) => (v === null || v === undefined || v === "" ? "—" : `${formatDecimal(v, 1, 1)} %`);

/** Jam stempel (ISO) di WIB: "10.00"; kosong/tak sah → "". */
export function jamWib(iso) {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" });
}

/** Ada isinya? (angka capaian bukan nol, atau ada lembar disahkan) — Profil Saya hanya menampilkan kartu berisi. */
export function adaIsi(data) {
  const a = data?.achievement || {};
  return ["target_sales", "omzet_bersih", "target_collection", "uang_masuk"].some((k) => Number(a[k] || 0) !== 0)
    || (data?.sheets || []).length > 0;
}

function Rupiah({ v, className = "", testId }) {
  return <span className={`whitespace-nowrap tabular-nums ${className}`} data-testid={testId}>{formatCurrency(v)}</span>;
}

/** "Rp 1.000.000.000 dari target Rp 800.000.000 (125,0 %)" · target 0 → "Rp … , target belum diisi". */
function BarisCapaian({ label, nilai, target, pct, testId }) {
  return (
    <div className="flex flex-col gap-0.5 py-1.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3" data-testid={testId}>
      <dt className="text-fs-13 font-semibold text-kn-text-2">{label}</dt>
      <dd className="text-fs-14 text-kn-text sm:text-right">
        <Rupiah v={nilai} className="font-bold" />
        {Number(target || 0) > 0 ? (
          <> dari target <Rupiah v={target} /> <span className="whitespace-nowrap">({persen(pct)})</span></>
        ) : <span className="text-kn-text-2">, {TEKS_TARGET_KOSONG}</span>}
      </dd>
    </div>
  );
}

function AngkaDasar({ snap, testId }) {
  const s = snap || {};
  return (
    <ul className="mt-1.5 space-y-0.5 rounded-md bg-kn-neutral-soft px-3 py-2 text-fs-13 text-kn-text" data-testid={testId}>
      <li>Omzet <Rupiah v={s.omzet_bersih} /> / target <Rupiah v={s.target_sales} /></li>
      <li>Uang masuk <Rupiah v={s.uang_masuk} /> / target <Rupiah v={s.target_collection} /></li>
      <li>Realisasi harga <span className="whitespace-nowrap">{persen(s.realisasi_harga_pct)}</span></li>
    </ul>
  );
}

function BarisLembar({ ln, mobile, testId }) {
  const [buka, setBuka] = useState(false);
  return (
    <li className="py-2" data-testid={testId}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words text-fs-14 font-semibold text-kn-text">{ln.component_name} — {ln.basis_label}</p>
          {ln.is_adjustment && (
            <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-fs-13 text-kn-text-2">
              <span className="status-pill status-draft" data-testid={`${testId}-adj`}>Penyesuaian</span>
              {ln.note ? <span className="break-words">{ln.note}</span> : null}
            </p>
          )}
        </div>
        <Rupiah v={ln.amount} className="shrink-0 text-fs-14 font-bold text-kn-text" testId={`${testId}-amount`} />
      </div>
      <button type="button" aria-expanded={buka} data-testid={`${testId}-basis`} onClick={() => setBuka((x) => !x)}
        className={`secondary-button ${mobile ? "btn-touch" : "btn-sm"} mt-1 whitespace-nowrap`}>
        {buka ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />} Angka dasar
      </button>
      {buka && <AngkaDasar snap={ln.snapshot} testId={`${testId}-snapshot`} />}
    </li>
  );
}

function Lembar({ s, mobile, testId }) {
  const st = STATUS[s.status] || STATUS.approved;
  const { Icon } = st;
  const total = (s.lines || []).reduce((t, x) => t + Number(x.amount || 0), 0);
  return (
    <div className="border-t border-kn-divider pt-2" data-testid={testId}>
      <ul className="divide-y divide-kn-divider">
        {(s.lines || []).map((ln, i) => (
          <BarisLembar key={`${s.sheet_number}-${i}`} ln={ln} mobile={mobile} testId={`${testId}-line-${i}`} />
        ))}
      </ul>
      {(s.lines || []).length > 1 && (
        <div className="flex items-center justify-between gap-3 border-t border-kn-divider py-1.5 text-fs-14 font-bold">
          <span>Jumlah</span><Rupiah v={total} testId={`${testId}-total`} />
        </div>
      )}
      <p className="mt-1 flex flex-wrap items-center gap-2 text-fs-13 text-kn-text" data-testid={`${testId}-pay`}>
        <span className={`status-pill ${st.cls}`}><Icon size={12} aria-hidden="true" />{st.label}</span>
        <span>{st.teks(formatPeriod(s.pay_period))}</span>
      </p>
    </div>
  );
}

export default function MyIncentiveCard({ variant = "page", hideWhenEmpty = false, period: periodProp,
  onPeriodChange, onLoaded, testId = "my-incentive" }) {
  const mobile = variant === "mobile";
  const [periodLokal, setPeriodLokal] = useState(bulanIni());
  const period = periodProp || periodLokal;
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [tampil, setTampil] = useState(!hideWhenEmpty);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/incentive/me`, { params: { period } });
      setData(r.data);
      setState("ready");
      if (adaIsi(r.data)) setTampil(true);
      if (onLoaded) onLoaded(r.data);
    } catch (e) {
      setState("error");
      setTampil(true);   // galat selalu terlihat (juga di Profil Saya)
    }
  }, [period]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  const gantiBulan = (v) => {
    if (!v) return;
    if (onPeriodChange) onPeriodChange(v);
    if (!periodProp) setPeriodLokal(v);
  };

  if (!tampil) return null;
  const a = data?.achievement || {};
  const sheets = data?.sheets || [];
  const otomatis = data && !MODE_TANPA_MESIN.includes(data.mode) && data.auto_commission;
  const jam = jamWib(a.facts_as_of);
  const wadah = mobile ? "m-card p-3" : "section-card";
  const bulan = pilihanBulan(bulanIni());
  if (!bulan.some((o) => o.value === period)) bulan.push({ value: period, label: formatPeriod(period) });
  return (
    <section className={wadah} data-testid={testId}>
      <div className={mobile ? "mb-2 flex items-center gap-2" : "section-head"}>
        <h2 className={`flex items-center gap-2 ${mobile ? "text-fs-16" : ""} font-bold text-kn-text`} data-testid={`${testId}-title`}>
          <Target size={16} className="shrink-0 text-kn-action" aria-hidden="true" />
          Capaian &amp; Insentif Saya — {formatPeriod(period)}
        </h2>
      </div>
      <div className={mobile ? "space-y-2" : "section-body space-y-3"}>
        <div className="flex flex-wrap items-end gap-x-3 gap-y-1">
          <div className={mobile ? "w-full" : "w-[220px]"}>
            <label className="field-label" htmlFor={`${testId}-month`}>Bulan</label>
            <KNSelect id={`${testId}-month`} data-testid={`${testId}-month`} value={period} onValueChange={gantiBulan}
              className={mobile ? "field kn-input-touch" : "field"} options={bulan} />
          </div>
          {state === "ready" && jam && (
            <span className="text-fs-12 text-kn-text-2" data-testid={`${testId}-asof`}>Data per pukul {jam} WIB</span>
          )}
        </div>

        {state === "loading" ? (
          <p className="text-fs-13 text-kn-text-2" role="status" data-testid={`${testId}-loading`}>{TEKS_MEMUAT}</p>
        ) : state === "error" ? (
          <ErrorNotice message={TEKS_GALAT} onRetry={load} testId={`${testId}-error`} />
        ) : (
          <>
            <dl className="divide-y divide-kn-divider" data-testid={`${testId}-achievement`}>
              <BarisCapaian label="Omzet" nilai={a.omzet_bersih} target={a.target_sales} pct={a.pct_omzet}
                testId={`${testId}-omzet`} />
              <BarisCapaian label="Uang masuk" nilai={a.uang_masuk} target={a.target_collection} pct={a.pct_pencairan}
                testId={`${testId}-uang`} />
              <div className="flex items-baseline justify-between gap-3 py-1.5" data-testid={`${testId}-harga`}>
                <dt className="text-fs-13 font-semibold text-kn-text-2">Realisasi harga</dt>
                <dd className="whitespace-nowrap text-fs-14 font-bold text-kn-text">{persen(a.realisasi_harga_pct)}</dd>
              </div>
              {otomatis && (
                <div className="flex items-baseline justify-between gap-3 py-1.5" data-testid={`${testId}-auto`}>
                  <dt className="text-fs-13 font-semibold text-kn-text-2">Komisi berjalan (hitungan otomatis)</dt>
                  <dd className="text-fs-14 font-bold text-kn-text"><Rupiah v={data.auto_commission.mtd} /></dd>
                </div>
              )}
            </dl>

            <div data-testid={`${testId}-sheets`}>
              <h3 className="text-fs-14 font-bold text-kn-text">Insentif yang sudah disahkan</h3>
              {sheets.length === 0 ? (
                <p className="mt-1 text-fs-13 text-kn-text-2" data-testid={`${testId}-sheets-empty`}>{TEKS_KOSONG_LEMBAR}</p>
              ) : sheets.map((s, i) => (
                <Lembar key={s.sheet_number || i} s={s} mobile={mobile} testId={`${testId}-sheet-${i}`} />
              ))}
            </div>
            <p className="flex items-start gap-1.5 text-fs-12 text-kn-text-2" data-testid={`${testId}-note`}>
              <Info size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
              {otomatis ? TEKS_CATATAN_OTOMATIS : TEKS_CATATAN}
            </p>
          </>
        )}
      </div>
    </section>
  );
}
