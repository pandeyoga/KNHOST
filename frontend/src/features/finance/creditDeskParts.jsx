/**
 * creditDeskParts (CR-T5) — tabel enam antrean daftar kerja "Kredit & Plafon" (`CreditDeskView.jsx`).
 *
 * Satu tabel baku per antrean (`table-wrap` + `data-table head-wrap`, judul kolom boleh dua baris). Lebar dihitung
 * terhadap kartu 1280 px (±1018) dan 1024 px (±760): tiap antrean ≤ 760 px; kolom aksi `col-sticky-end` dengan tombol
 * `btn-sm` yang boleh turun baris di dalam selnya (tombol tidak pernah terpotong). "Buka kartu pelanggan" = tautan di
 * sel pelanggan (semua antrean). Status = ikon + teks + warna (`status-pill` berkelas yang ada). Nominal rata kanan,
 * `tabular-nums`, `whitespace-nowrap` (saldo negatif tidak patah).
 */
import { AlertTriangle, BadgeDollarSign, Ban, CheckCircle2, ChevronDown, ChevronRight, Clock3, Copy, FileWarning,
  HandCoins, RefreshCw, Send, ShieldCheck, ShieldQuestion, Truck, XCircle } from "lucide-react";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { PromiseStatusPill } from "../crm/promiseUi";

export const QUEUES = [
  { key: "menunggu_keputusan", label: "Menunggu keputusan" },
  { key: "ditahan", label: "Ditahan" },
  { key: "jatuh_tempo", label: "Jatuh tempo" },
  { key: "janji_bayar", label: "Janji bayar" },
  { key: "kaji_ulang", label: "Kaji ulang" },
  { key: "denda", label: "Denda" },
];

const KIND = {
  izin_kredit: { label: "Izin kredit", cls: "status-pending", Icon: ShieldCheck },
  ubah_profil: { label: "Ubah profil", cls: "status-shipped", Icon: ShieldQuestion },
  pesanan_ditahan: { label: "Ditahan", cls: "status-pending", Icon: Truck },
  pesanan_ditolak: { label: "Ditolak", cls: "status-rejected", Icon: XCircle },
  plafon: { label: "Plafon", cls: "status-shipped", Icon: ShieldCheck },
  bebas_denda: { label: "Bebas denda", cls: "status-draft", Icon: BadgeDollarSign },
};
const STATE = {
  lewat: { label: "Lewat", cls: "status-rejected", Icon: AlertTriangle },
  mendekati: { label: "Mendekati", cls: "status-pending", Icon: Clock3 },
};

function Pill({ meta, testId }) {
  if (!meta) return null;
  const { Icon } = meta;
  return (
    <span className={`status-pill ${meta.cls} inline-flex items-center gap-1`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{meta.label}
    </span>
  );
}

const Money = ({ v, strong = false }) => (
  <span className={`whitespace-nowrap tabular-nums ${strong ? "font-semibold" : ""}`}>{formatCurrency(v)}</span>
);

function CustomerCell({ row, ctx }) {
  return (
    <div className="min-w-0">
      <p className="font-semibold text-kn-text break-words">{row.customer_name || "—"}</p>
      {ctx.combined && <p className="text-fs-12 text-kn-text-2">{ctx.ptName(row.entity_id)}</p>}
      <button type="button" className="link-button text-fs-12" data-testid={`credit-desk-open-${row.id}`}
        onClick={() => ctx.openCustomer(row)}>Buka kartu pelanggan</button>
    </div>
  );
}

/** Telat (positif) atau "jatuh tempo N hari lagi" (negatif) — ikon + teks + warna. */
function LatePill({ days }) {
  if (days > 0) {
    return (
      <span className="status-pill status-rejected inline-flex items-center gap-1">
        <AlertTriangle size={12} aria-hidden="true" />Telat {days} hari
      </span>
    );
  }
  return (
    <span className="status-pill status-pending inline-flex items-center gap-1">
      <Clock3 size={12} aria-hidden="true" />{days === 0 ? "Jatuh tempo hari ini" : `${-days} hari lagi`}
    </span>
  );
}

/** Alasan tombol mati, ditulis di samping tombol (bukan hanya tooltip). */
const Why = ({ text, testId }) => (text ? <p className="text-fs-12 text-kn-text-2" data-testid={testId}>{text}</p> : null);

function DecisionCell({ row, ctx }) {
  const can = row.kind === "izin_kredit" ? ctx.canApproveOverride : ctx.canApproveProfile;
  if (!can) return <span className="text-fs-12 text-kn-text-2">Dipantau</span>;
  const off = ctx.combined || Boolean(row.blocked_reason) || ctx.busy === row.id;
  return (
    <div className="grid gap-1">
      <div className="flex flex-wrap gap-1">
        <button type="button" className="primary-button btn-sm" disabled={off} data-testid={`credit-desk-approve-${row.id}`}
          onClick={() => ctx.onDecide(row, "approve")}><CheckCircle2 size={13} aria-hidden="true" />Setujui</button>
        <button type="button" className="danger-button btn-sm" disabled={off} data-testid={`credit-desk-reject-${row.id}`}
          onClick={() => ctx.onDecide(row, "reject")}><XCircle size={13} aria-hidden="true" />Tolak</button>
      </div>
      <Why text={row.blocked_reason} testId={`credit-desk-blocked-${row.id}`} />
    </div>
  );
}

function Head({ cols, action = true }) {
  return (
    <thead>
      <tr>
        {cols.map(([label, cls]) => <th key={label} className={cls || ""}>{label}</th>)}
        {action && <th className="col-sticky-end">Aksi</th>}
      </tr>
    </thead>
  );
}

function MenungguTable({ rows, ctx }) {
  const showAction = ctx.canApproveOverride || ctx.canApproveProfile;
  return (
    <table className="data-table head-wrap" data-testid="credit-desk-table-menunggu_keputusan">
      <Head cols={[["Jenis"], ["Pelanggan"], ["Nominal", "text-right"], ["Pengaju & umur"], ["Ringkasan"]]}
        action={showAction} />
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} data-testid={`credit-desk-row-${r.id}`}>
            <td><Pill meta={KIND[r.kind]} testId={`credit-desk-kind-${r.id}`} /></td>
            <td className="min-w-[150px]"><CustomerCell row={r} ctx={ctx} /></td>
            <td className="text-right">{r.amount > 0 ? <Money v={r.amount} strong /> : <span className="text-kn-text-2">—</span>}</td>
            <td className="min-w-[110px]"><p>{r.requested_by || "—"}</p>
              <p className="text-fs-12 text-kn-text-2">{r.age_days ? `${r.age_days} hari` : "hari ini"}</p></td>
            <td className="min-w-[110px]"><p className="line-clamp-2 break-words">{r.summary}</p></td>
            {showAction && <td className="col-sticky-end min-w-[150px]"><DecisionCell row={r} ctx={ctx} /></td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DitahanTable({ rows, ctx }) {
  return (
    <table className="data-table head-wrap" data-testid="credit-desk-table-ditahan">
      <Head cols={[["Jenis"], ["Pelanggan"], ["Pesanan"], ["Nilai", "text-right"], ["Alasan"]]} />
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} data-testid={`credit-desk-row-${r.id}`}>
            <td><Pill meta={KIND[r.kind]} /></td>
            <td className="min-w-[160px]"><CustomerCell row={r} ctx={ctx} /></td>
            <td className="whitespace-nowrap">{r.order_number || "—"}</td>
            <td className="text-right"><Money v={r.amount} strong /></td>
            <td className="min-w-[110px]"><p className="break-words" data-testid={`credit-desk-reason-${r.id}`}>{r.message}</p>
              {r.since && <p className="text-fs-12 text-kn-text-2">sejak {formatDate(r.since)}</p>}</td>
            <td className="col-sticky-end min-w-[150px]">
              {r.kind === "pesanan_ditahan" ? (
                <div className="grid gap-1">
                  <button type="button" className="secondary-button btn-sm" data-testid={`credit-desk-recheck-${r.id}`}
                    disabled={ctx.combined || !r.recheck_available || ctx.busy === r.id} onClick={() => ctx.onRecheck(r)}>
                    <RefreshCw size={13} aria-hidden="true" />Periksa ulang kredit
                  </button>
                  {!r.recheck_available && <Why text="Pesanan dilepas lewat keputusan izin kredit." />}
                </div>
              ) : <span className="text-fs-12 text-kn-text-2">Ajukan izin kredit dari kartu pelanggan</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function JatuhTempoTable({ rows, ctx }) {
  return (
    <table className="data-table head-wrap" data-testid="credit-desk-table-jatuh_tempo">
      <Head cols={[["Pelanggan"], ["Tagihan"], ["Total sisa", "text-right"], ["Telat terlama"]]} />
      <tbody>
        {rows.map((r) => {
          const open = Boolean(ctx.expanded[r.id]);
          return [
            <tr key={r.id} data-testid={`credit-desk-row-${r.id}`}>
              <td className="min-w-[170px]"><CustomerCell row={r} ctx={ctx} /></td>
              <td className="min-w-[140px]">
                <button type="button" className="link-button inline-flex items-center gap-1" aria-expanded={open}
                  data-testid={`credit-desk-lines-${r.id}`} onClick={() => ctx.toggle(r.id)}>
                  {open ? <ChevronDown size={13} aria-hidden="true" /> : <ChevronRight size={13} aria-hidden="true" />}
                  {r.line_count} tagihan
                </button>
                {r.next_due_date && <p className="text-fs-12 text-kn-text-2">terdekat {formatDate(r.next_due_date)}</p>}
              </td>
              <td className="text-right"><Money v={r.total_outstanding} strong /></td>
              <td><LatePill days={r.max_days_late} /></td>
              <td className="col-sticky-end min-w-[160px]">
                <div className="flex flex-wrap gap-1">
                  <button type="button" className="secondary-button btn-sm" data-testid={`credit-desk-copy-${r.id}`}
                    disabled={ctx.busy === r.id} onClick={() => ctx.onCopyReminder(r)}>
                    <Copy size={13} aria-hidden="true" />Salin pengingat
                  </button>
                  <button type="button" className="secondary-button btn-sm" data-testid={`credit-desk-promise-${r.id}`}
                    disabled={ctx.combined || !ctx.canPromise} onClick={() => ctx.onPromise(r)}>
                    <HandCoins size={13} aria-hidden="true" />Catat janji bayar
                  </button>
                </div>
                {!ctx.canPromise && <Why text="Mencatat janji butuh akses ubah pesanan." />}
              </td>
            </tr>,
            open && (
              <tr key={`${r.id}-lines`} data-testid={`credit-desk-lines-table-${r.id}`}>
                <td colSpan={5} className="bg-kn-neutral-soft">
                  <ul className="grid gap-1 text-fs-12">
                    {r.lines.map((ln) => (
                      <li key={`${ln.order_id}:${ln.line_id}`} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="font-semibold">{ln.order_number}</span>
                        <span>{ln.label || "Tagihan"}</span>
                        <span>jatuh tempo {formatDate(ln.due_date)}</span>
                        <Money v={ln.outstanding} />
                        <LatePill days={ln.days_late} />
                      </li>
                    ))}
                  </ul>
                </td>
              </tr>
            ),
          ];
        })}
      </tbody>
    </table>
  );
}

function JanjiTable({ rows, ctx }) {
  return (
    <table className="data-table head-wrap" data-testid="credit-desk-table-janji_bayar">
      <Head cols={[["Pelanggan"], ["Tanggal janji"], ["Nominal janji", "text-right"], ["Sudah dibayar", "text-right"],
        ["Status"], ["Pencatat"]]} action={false} />
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} data-testid={`credit-desk-row-${r.id}`}>
            <td className="min-w-[160px]"><CustomerCell row={r} ctx={ctx} /></td>
            <td className="whitespace-nowrap">{formatDate(r.promise_date)}</td>
            <td className="text-right"><Money v={r.promise_amount} strong /></td>
            <td className="text-right"><Money v={r.paid_amount} /></td>
            <td><PromiseStatusPill status={r.status} testId={`credit-desk-promise-status-${r.id}`} /></td>
            <td className="min-w-[100px]"><p>{r.created_by || "—"}</p>
              <p className="text-fs-12 text-kn-text-2">{formatDate(r.created_at)}</p></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function KajiTable({ rows, ctx }) {
  return (
    <table className="data-table head-wrap" data-testid="credit-desk-table-kaji_ulang">
      <Head cols={[["Pelanggan"], ["Jenis"], ["Berakhir"], ["Keadaan"], ["Penolakan 90 hari", "text-right"]]}
        action={false} />
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} data-testid={`credit-desk-row-${r.id}`}>
            <td className="min-w-[160px]"><CustomerCell row={r} ctx={ctx} /></td>
            <td><Pill meta={KIND[r.kind]} />
              {r.kind === "plafon" && r.credit_limit > 0 && <p className="text-fs-12 text-kn-text-2"><Money v={r.credit_limit} /></p>}</td>
            <td className="whitespace-nowrap">{formatDate(r.valid_until)}</td>
            <td><Pill meta={STATE[r.state]} testId={`credit-desk-state-${r.id}`} /></td>
            <td className="text-right tabular-nums">{r.rejections_90d}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DendaTable({ rows, ctx }) {
  return (
    <table className="data-table head-wrap" data-testid="credit-desk-table-denda">
      <Head cols={[["Nota"], ["Pelanggan"], ["Nominal", "text-right"], ["Telat", "text-right"], ["Catatan"]]} />
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} data-testid={`credit-desk-row-${r.id}`}>
            <td className="whitespace-nowrap"><p className="font-semibold">{r.number}</p>
              <p className="text-fs-12 text-kn-text-2">{r.doc_number}</p></td>
            <td className="min-w-[160px]"><CustomerCell row={r} ctx={ctx} /></td>
            <td className="text-right"><Money v={r.amount} strong /></td>
            <td className="text-right tabular-nums whitespace-nowrap">{r.days_late ? `${r.days_late} hari` : "—"}</td>
            <td className="min-w-[140px]">
              {r.plan_void ? (
                <span className="inline-flex items-start gap-1 text-fs-12 text-kn-warning-text" data-testid={`credit-desk-planvoid-${r.id}`}>
                  <FileWarning size={13} aria-hidden="true" className="mt-0.5 shrink-0" />
                  Jadwal tagihannya sudah diganti rencana baru — periksa agar hari telat tidak tertagih dua kali.
                </span>
              ) : <span className="text-fs-12 text-kn-text-2">{r.line_label || "—"}</span>}
            </td>
            <td className="col-sticky-end min-w-[150px]">
              <div className="flex flex-wrap gap-1">
                {ctx.canIssue && (
                  <button type="button" className="primary-button btn-sm" data-testid={`credit-desk-issue-${r.id}`}
                    disabled={ctx.combined || ctx.busy === r.id} onClick={() => ctx.onIssue(r)}>
                    <Send size={13} aria-hidden="true" />Terbitkan
                  </button>
                )}
                {ctx.canWaive && (
                  <button type="button" className="secondary-button btn-sm" data-testid={`credit-desk-waive-${r.id}`}
                    disabled={ctx.combined || ctx.busy === r.id} onClick={() => ctx.onWaive(r)}>
                    <Ban size={13} aria-hidden="true" />Bebaskan
                  </button>
                )}
                {!ctx.canIssue && !ctx.canWaive && <span className="text-fs-12 text-kn-text-2">Dipantau</span>}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const TABLES = { menunggu_keputusan: MenungguTable, ditahan: DitahanTable, jatuh_tempo: JatuhTempoTable,
  janji_bayar: JanjiTable, kaji_ulang: KajiTable, denda: DendaTable };

export function QueueTable({ queue, rows, ctx }) {
  const T = TABLES[queue];
  return T ? <div className="table-wrap"><T rows={rows} ctx={ctx} /></div> : null;
}

const C = (key, header, type, get) => ({ key, header, ...(type ? { type } : {}), ...(get ? { get } : {}) });
const KIND_TEXT = (r) => KIND[r.kind]?.label || "";
/** Kolom CSV per antrean (= kolom tabel; antrean hasil hitung, bukan satu koleksi — Excel Pusat Export tidak tersedia). */
export const CSV_COLUMNS = {
  menunggu_keputusan: [C("kind", "Jenis", "", KIND_TEXT), C("customer_name", "Pelanggan"), C("amount", "Nominal", "num"),
    C("requested_by", "Pengaju"), C("age_days", "Umur (hari)", "int"), C("summary", "Ringkasan")],
  ditahan: [C("kind", "Jenis", "", KIND_TEXT), C("customer_name", "Pelanggan"), C("order_number", "Pesanan"),
    C("amount", "Nilai", "num"), C("message", "Alasan"), C("since", "Sejak", "date")],
  jatuh_tempo: [C("customer_name", "Pelanggan"), C("line_count", "Jumlah tagihan", "int"),
    C("total_outstanding", "Total sisa", "num"), C("max_days_late", "Telat terlama (hari)", "int"),
    C("next_due_date", "Jatuh tempo terdekat", "date")],
  janji_bayar: [C("customer_name", "Pelanggan"), C("promise_date", "Tanggal janji", "date"),
    C("promise_amount", "Nominal janji", "num"), C("paid_amount", "Sudah dibayar", "num"),
    C("status", "Status", "", (r) => ({ menunggu: "Menunggu", ditepati: "Ditepati", ingkar: "Ingkar" }[r.status] || "")),
    C("created_by", "Pencatat")],
  kaji_ulang: [C("customer_name", "Pelanggan"), C("kind", "Jenis", "", KIND_TEXT), C("valid_until", "Berakhir", "date"),
    C("state", "Keadaan", "", (r) => STATE[r.state]?.label || ""), C("rejections_90d", "Penolakan 90 hari", "int")],
  denda: [C("number", "Nota"), C("customer_name", "Pelanggan"), C("doc_number", "Pesanan"), C("amount", "Nominal", "num"),
    C("days_late", "Telat (hari)", "int")],
};

/** Salin teks ke papan klip (cadangan `execCommand` untuk peramban lama). */
export async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return true; }
  } catch { /* cara lama di bawah */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
