import { useMemo, useState } from "react";
import { AlertTriangle, Building2, Calculator, CheckCircle2, FileSpreadsheet, Loader2, MinusCircle, ShieldCheck } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import { kpiValueParts } from "../finance/financeShared";

/** AG-T4 — paket tutup buku (Tanya KN › Laporan › Keuangan): kartu pemilih bulan + hasil di panel utama. */
const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];
export const PACK_SHEETS = 12;

/** 12 bulan terakhir yang SUDAH berakhir (WIB), terbaru dulu: [{value: "2026-10", label: "Oktober 2026"}, …]. */
export function endedMonths(now = new Date(), n = 12) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Jakarta", year: "numeric", month: "2-digit" })
    .formatToParts(now);
  let y = Number(parts.find((p) => p.type === "year").value);
  let m = Number(parts.find((p) => p.type === "month").value);
  const out = [];
  for (let i = 0; i < n; i += 1) {
    m -= 1;
    if (m === 0) { m = 12; y -= 1; }
    out.push({ value: `${y}-${String(m).padStart(2, "0")}`, label: `${BULAN[m - 1]} ${y}` });
  }
  return out;
}

/** Teks ringkasan: "Rp 300.000" tidak pernah terpatah di tengah angka (pola `kpiValueParts`). */
export function RupiahText({ text }) {
  const out = [];
  const re = /-?Rp\s?\d{1,3}(?:\.\d{3})*(?:,\d+)?/g;
  let last = 0;
  let m;
  while ((m = re.exec(text || "")) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(<span key={m.index}>{kpiValueParts(m[0].replace(/^(-?Rp)\s?/, "$1 "))}</span>);
    last = m.index + m[0].length;
  }
  if (last < (text || "").length) out.push(text.slice(last));
  return out;
}

function PtBanner({ combined, label, testId }) {
  return (
    <div className={`tanya-mode-scope ${combined ? "combined" : ""}`} data-testid={testId}>
      {combined ? <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" /> : <Building2 className="h-3.5 w-3.5" aria-hidden="true" />}
      <span>{combined ? "Semua PT" : `PT: ${label || "PT aktif"}`}</span>
    </div>
  );
}

/** Kartu di grup "Keuangan" tab Laporan. Mode Semua PT: tombol mati dengan alasan tertulis di sampingnya (L4). */
export function TanyaClosingPackCard({ combined, ptLabel, busy, onBuild }) {
  const months = useMemo(() => endedMonths(), []);
  const [period, setPeriod] = useState(months[0].value);
  return (
    <section className="tanya-pack-card" data-testid="tanya-pack-card">
      <div className="tanya-pack-title">
        <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />
        <span className="tanya-tpl-title">Paket tutup buku</span>
      </div>
      <span className="tanya-tpl-prompt">Satu berkas Excel per bulan: laporan utama, umur piutang dan hutang, pencocokan, posting gagal, jurnal manual.</span>
      <PtBanner combined={combined} label={ptLabel} testId="tanya-pack-scope" />
      <span className="field-label">Bulan</span>
      <KNSelect value={period} onValueChange={setPeriod} options={months} className="field" disabled={busy}
        data-testid="tanya-pack-month" />
      <div className="tanya-pack-actions">
        <button type="button" className="primary-button btn-sm" disabled={combined || busy} onClick={() => onBuild(period)}
          data-testid="tanya-pack-build">
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />} Buat paket
        </button>
        {combined && (
          <span className="text-fs-12 text-kn-text-2" data-testid="tanya-pack-combined-reason">Pilih satu PT. Paket dibuat per PT.</span>
        )}
      </div>
    </section>
  );
}

function SheetRow({ n, sec }) {
  const ok = sec.status === "ok";
  const reason = (sec.note || "").replace(/^Tidak disertakan:\s*/, "");
  return (
    <li className="tanya-pack-sheet" data-testid={`tanya-pack-sheet-${sec.key}`}>
      <span className="tanya-pack-sheet-name">{n}. {sec.title}</span>
      <span className="tanya-pack-sheet-state">
        <span className={`status-pill normal-case ${ok ? "bg-kn-success-soft text-kn-success-text"
          : sec.status === "error" ? "bg-kn-warning-soft text-kn-warning-text" : "bg-kn-neutral-soft text-kn-neutral"}`}
          data-testid={`tanya-pack-sheet-status-${sec.key}`}>
          {ok ? <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            : sec.status === "error" ? <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
              : <MinusCircle className="h-3.5 w-3.5" aria-hidden="true" />}
          {ok ? "Disertakan" : "Tidak disertakan"}
        </span>
        {!ok && reason && <span className="tanya-pack-sheet-reason" data-testid={`tanya-pack-sheet-reason-${sec.key}`}>— {reason}</span>}
      </span>
    </li>
  );
}

/** Hasil di panel utama: memuat (kemajuan per lembar) · galat · paket (lembar, ringkasan, pemeriksa angka, unduh). */
export function TanyaClosingPackResult({ state, onRetry, onDownload, downloading }) {
  if (state.status === "busy") {
    return (
      <div className="tanya-loading" data-testid="tanya-pack-busy">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
        Menyusun paket… ({Math.min(state.done || 0, PACK_SHEETS)} dari {state.total || PACK_SHEETS})
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <div className="tanya-answer section-card" data-testid="tanya-pack-error">
        <div className="tanya-pack-error">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          <span>{state.error || "Paket tidak bisa disusun. Coba lagi."}</span>
        </div>
        <div><button type="button" className="secondary-button btn-sm" onClick={onRetry} data-testid="tanya-pack-retry">Coba lagi</button></div>
      </div>
    );
  }
  const pack = state.pack;
  if (!pack) return null;
  const secs = pack.sections || [];
  const model = pack.summary_source === "model";
  return (
    <article className="tanya-answer section-card" data-testid="tanya-pack-result">
      <header className="tanya-answer-head">
        <div className="min-w-0">
          <div className="tanya-kicker">Asisten Keuangan · Paket tutup buku</div>
          <h2 className="tanya-answer-title">Paket tutup buku {pack.period_label}</h2>
        </div>
        <div className="tanya-answer-actions">
          <button type="button" className="secondary-button btn-sm" onClick={() => onDownload(pack)} disabled={downloading}
            data-testid="tanya-pack-download">
            {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <FileSpreadsheet className="h-3.5 w-3.5" aria-hidden="true" />}
            Unduh Excel
          </button>
        </div>
      </header>
      <PtBanner combined={false} label={pack.entity_label} testId="tanya-pack-result-scope" />
      <div className="tanya-narr" data-testid="tanya-pack-summary">
        {/* Baris keterangan (ikon + teks + warna), boleh turun baris di layar sempit — bukan pil `nowrap`. */}
        <div className={`tanya-pack-verify ${model ? "ok" : ""}`} data-testid="tanya-pack-verify">
          {model ? <ShieldCheck className="h-3.5 w-3.5 shrink-0" aria-hidden="true" /> : <Calculator className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />}
          <span>{model ? `Pemeriksa angka: ${pack.verification?.checked || 0} angka diperiksa, semua cocok`
            : "Ringkasan otomatis (angka dari server)"}</span>
        </div>
        <p className="tanya-pack-summary-text" data-testid="tanya-pack-summary-text"><RupiahText text={pack.summary} /></p>
      </div>
      <section>
        <div className="tanya-group-title" data-testid="tanya-pack-count">
          Lembar ({secs.filter((s) => s.status === "ok").length} dari {secs.length} disertakan)
        </div>
        <ol className="tanya-pack-sheets">
          {secs.map((s, i) => <SheetRow key={s.key} n={i + 1} sec={s} />)}
        </ol>
      </section>
    </article>
  );
}
