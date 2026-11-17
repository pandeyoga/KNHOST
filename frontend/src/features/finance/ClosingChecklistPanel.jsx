/**
 * ClosingChecklistPanel — PK-43 (UX-16) · **Daftar Periksa Sebelum Tutup Buku** di layar Tutup Buku.
 *
 * Sumber: `GET /api/finance/closing/checklist` (`services/closing_checklist.py`) — angka diambil dari sistem untuk satu
 * PT + satu periode. Dimuat bersama tombol **Pratinjau** (dan sebelum konfirmasi Tutup Buku bila belum dimuat).
 * Tiap butir (`closing-check-{key}`): status ikon + teks + warna (`status-pill`), label, keterangan, nilai, dan tombol
 * **Buka** ke layar sumbernya (`go(link.view, { preset })`; layar tujuan menampilkan "← Kembali ke Tutup Buku").
 * MN-T2 — tautan ke layar ini sendiri (`link.view === "closing"` + `preset.seksi`: akun sementara, persediaan) membuka
 * seksi lipatnya lewat `onOpenSection(seksi)` tanpa navigasi; Posting Gagal dan Buka Periode = tab hub yang sama.
 * Memuat / galat / kosong dibedakan. Galat tidak menghalangi tutup buku — aturan server yang menentukan.
 *
 *   const ceklis = useClosingChecklist(entityId, periodType, periodKey);
 *   ceklis.load();                      // → data | null
 *   <ClosingChecklistPanel {...ceklis} />
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, ClipboardCheck, ExternalLink, HelpCircle, XCircle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { useAppNav } from "../../context/AppNavContext";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";

export const CHECK_STATUS = {
  ok: { label: "Beres", cls: "status-done", Icon: CheckCircle2 },
  warning: { label: "Perlu dilihat", cls: "status-pending", Icon: AlertTriangle },
  blocking: { label: "Harus diselesaikan", cls: "status-rejected", Icon: XCircle },
  unknown: { label: "Tidak terbaca", cls: "status-draft", Icon: HelpCircle },
};
export const CHECKLIST_ERROR = "Daftar periksa gagal dimuat.";

// Satuan nilai hitungan per butir; butir rupiah ditulis rupiah. Nilai 0 pada butir yang beres tidak ditonjolkan.
const UNIT = { posting_gagal: "dokumen", bank_cocok: "mutasi", buka_periode_aktif: "izin", penyusutan: "aset",
  gaji: "penggajian" };
const RUPIAH = new Set(["suspense_nol", "neraca_saldo", "stok_cocok"]);

/** "Piutang: buku {a} · dokumen {b} · selisih {c} — Utang: buku {d} · dokumen {e} · selisih {f}" (butir antar-PT). */
export function intercoValueText(v) {
  if (!v || typeof v !== "object") return "";
  const n = (x) => Number(x) || 0;
  return `Piutang: buku ${formatCurrency(n(v.gl_receivable))} · dokumen ${formatCurrency(n(v.doc_receivable))} · selisih `
    + `${formatCurrency(n(v.gl_receivable) - n(v.doc_receivable))} — Utang: buku ${formatCurrency(n(v.gl_payable))} · `
    + `dokumen ${formatCurrency(n(v.doc_payable))} · selisih ${formatCurrency(n(v.gl_payable) - n(v.doc_payable))}`;
}

export function checkValueText(item) {
  const v = item?.value;
  if (item?.key === "antar_pt_cocok") return intercoValueText(v);
  if (v === null || v === undefined || v === "") return "";
  if (typeof v !== "number") return String(v);
  if (item.status === "ok" && Math.abs(v) < 0.005) return "";
  if (RUPIAH.has(item.key)) return formatCurrency(v);
  return UNIT[item.key] ? `${v.toLocaleString("id-ID")} ${UNIT[item.key]}` : v.toLocaleString("id-ID");
}

/** "{n} beres · {m} perlu dilihat · {k} harus diselesaikan" (+ tidak terbaca bila ada). */
export function checklistSummary(items = []) {
  const c = (s) => items.filter((it) => it.status === s).length;
  const parts = [`${c("ok")} beres`, `${c("warning")} perlu dilihat`, `${c("blocking")} harus diselesaikan`];
  if (c("unknown")) parts.push(`${c("unknown")} tidak terbaca`);
  return parts.join(" · ");
}

/** Butir `warning` sebagai baris peringatan dialog konfirmasi tutup buku. Rincian server sudah berupa kalimat masalah
 *  ("Penggajian belum diposting: …"); nama butir berupa pernyataan yang belum terpenuhi ("… sudah diposting") sehingga
 *  hanya dipakai bila rincian kosong — digabung keduanya terbaca bertentangan. */
export const checklistWarnings = (data) => (data?.items || []).filter((it) => it.status === "warning")
  .map((it) => it.detail || `${it.label}: ${checkValueText(it)}`);

export function useClosingChecklist(entityId, periodType, periodKey) {
  const [state, setState] = useState("idle");   // idle | loading | ok | error
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const seq = useRef(0);
  useEffect(() => { seq.current += 1; setState("idle"); setData(null); setError(""); }, [entityId, periodType, periodKey]);
  const load = useCallback(async () => {
    if (!entityId) return null;
    const my = ++seq.current;
    setState("loading"); setError("");
    try {
      const r = await axios.get(`${API}/finance/closing/checklist`,
        { params: { period_type: periodType, period_key: periodKey, entity_id: entityId } });
      if (my !== seq.current) return null;
      setData(r.data || null); setState("ok");
      return r.data || null;
    } catch (e) {
      if (my !== seq.current) return null;
      setData(null); setState("error");
      setError(apiErrorText(e, ""));
      return null;
    }
  }, [entityId, periodType, periodKey]);
  return { state, data, error, load };
}

/** Butir yang tautannya membuka seksi di layar Tutup Buku sendiri (MN-T2) → kunci seksinya; selain itu "". */
export const seksiOf = (link) => (link?.view === "closing" && link?.preset?.seksi ? link.preset.seksi : "");

export default function ClosingChecklistPanel({ state, data, error, load, onOpenSection }) {
  const { go, canOpen } = useAppNav();
  if (state === "idle") return null;
  const items = data?.items || [];
  return (
    <section className="mt-3 border-t border-kn-divider pt-3" data-testid="closing-checklist" aria-busy={state === "loading"}>
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <ClipboardCheck size={15} aria-hidden="true" className="text-kn-text-2" />
        <h4 className="text-fs-13 font-bold text-kn-text">Daftar Periksa Sebelum Tutup Buku</h4>
        {state === "ok" && items.length > 0 && (
          <span className="text-fs-12 text-kn-text-2" data-testid="closing-checklist-summary">{checklistSummary(items)}</span>
        )}
      </div>
      {state === "loading" && (
        <div className="grid gap-2" data-testid="closing-checklist-loading">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-10 animate-pulse rounded bg-kn-neutral-soft" />)}
        </div>
      )}
      {state === "error" && (
        <ErrorNotice testId="closing-checklist-error" onRetry={load}
          message={`${CHECKLIST_ERROR}${error ? ` ${error}` : ""} Tutup buku tetap bisa dilanjutkan menurut aturan server.`} />
      )}
      {state === "ok" && items.length === 0 && (
        <p className="py-4 text-center text-fs-12 text-kn-text-2" data-testid="closing-checklist-empty">
          Tidak ada butir daftar periksa untuk periode ini.</p>
      )}
      {state === "ok" && items.length > 0 && (
        <ul className="divide-y divide-kn-divider rounded-md border border-kn-divider" data-testid="closing-checklist-items">
          {items.map((it) => {
            const st = CHECK_STATUS[it.status] || CHECK_STATUS.unknown;
            const { Icon } = st;
            const nilai = checkValueText(it);
            const seksi = seksiOf(it.link);
            const bisaBuka = seksi ? typeof onOpenSection === "function" : Boolean(it.link?.view) && canOpen(it.link.view);
            return (
              <li key={it.key} className="flex flex-wrap items-start gap-x-3 gap-y-1 px-3 py-2" data-testid={`closing-check-${it.key}`}
                data-status={it.status}>
                <span className={`status-pill ${st.cls} mt-0.5 shrink-0`} data-testid={`closing-check-${it.key}-status`}>
                  <Icon size={12} aria-hidden="true" /> {st.label}
                </span>
                <div className="min-w-[200px] flex-1">
                  <p className="text-fs-13 font-semibold text-kn-text">{it.label}</p>
                  {it.detail && it.key !== "antar_pt_cocok" && <p className="text-fs-12 text-kn-text-2">{it.detail}</p>}
                  {nilai && <p className="text-fs-12 tabular-nums text-kn-text" data-testid={`closing-check-${it.key}-value`}>{nilai}</p>}
                  {it.key === "antar_pt_cocok" && nilai && (
                    <p className="text-fs-12 text-kn-text-2">Buku besar per {formatDate(data.end_date)}; sisa dokumen = keadaan hari ini.</p>
                  )}
                </div>
                {bisaBuka && (
                  <button type="button" className="secondary-button btn-sm shrink-0 whitespace-nowrap"
                    data-testid={`closing-check-${it.key}-open`}
                    onClick={() => (seksi ? onOpenSection(seksi)
                      : go(it.link.view, { preset: { ...(it.link.preset || {}), from: { view: "closing" } } }))}>
                    <ExternalLink size={13} aria-hidden="true" /> Buka
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
