/**
 * CustomerStatementTab (CR-T5, RP-05) — tab **Rekening Koran** kartu pelanggan: saldo dari baris jurnal akun piutang
 * pelanggan di SATU PT, per tanggal berapa pun sama dengan buku besar (`GET /api/customers/{id}/statement`).
 *
 *  · Isian "Dari" / "Sampai" (`KNDatePicker`; bawaan tanggal 1 bulan ini – hari ini WIB), tombol "Tampilkan",
 *    "Cetak PDF" (`document.print`, `statement.pdf`, berkop PT), "Salin pengingat" (`order.view`).
 *  · Kolom: Tanggal · Dokumen · Keterangan · Tagihan · Pembayaran / Kredit · Saldo; baris pertama "Saldo awal", terakhir
 *    "Saldo akhir". Nomor dokumen membuka dokumennya, "Jurnal …" membuka jurnalnya (Jejak Dokumen, L8). Bagian kedua
 *    "Denda" (akun piutang denda, tidak menambah saldo utama).
 *  · Lebar tabel ±650 px (Tanggal 84 · Dokumen 130 · Keterangan 132 · Tagihan 96 · Pembayaran 104 · Saldo 104) — muat di
 *    kolom kanan kartu 1280 px; di 1024 px kartu ditumpuk (lebar penuh ±728). Kolom Saldo menempel kanan.
 *  · Mode "Semua PT": rekening koran memakai PT pemilik data pelanggan (server menolak gabungan).
 */
import { useCallback, useEffect, useState } from "react";
import { Copy, FileDown, Search } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNDatePicker from "../../components/KNDatePicker";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate, todayWib } from "../../utils/formatters";
import { can } from "../../config/roles";
import { openTrace } from "../documents/trace/traceDeepLink";
import { copyText } from "../finance/creditDeskParts";

const awalBulan = (tgl) => `${tgl.slice(0, 8)}01`;
/** S5 (pelatihan 18 Nov) — nama berkas PDF hanya huruf/angka/tanda hubung. Dulu nama pelanggan dipakai apa adanya
 *  ("rekening-koran-latihan-91-·-toko-…pdf"): peramban menolak nama ber-"·" dan menyimpan berkas sebagai "download" tanpa
 *  ".pdf" (terjadi saat kartu/rincian piutang tidak membawa kode pelanggan). */
export const namaBerkas = (s) => String(s || "").normalize("NFKD").replace(/[^\w-]+/g, "-").replace(/-+/g, "-")
  .replace(/^-|-$/g, "").toLowerCase() || "pelanggan";
const Money = ({ v }) => <span className="whitespace-nowrap tabular-nums">{formatCurrency(v)}</span>;

function StatementTable({ part, from, to, testId }) {
  return (
    <div className="table-wrap">
      <table className="data-table head-wrap" data-testid={testId}>
        <thead>
          <tr>
            <th>Tanggal</th><th>Dokumen</th><th>Keterangan</th>
            <th className="text-right">Tagihan</th><th className="text-right">Pembayaran / Kredit</th>
            <th className="text-right col-sticky-end">Saldo</th>
          </tr>
        </thead>
        <tbody>
          <tr data-testid={`${testId}-opening`}>
            <td className="whitespace-nowrap">{formatDate(from)}</td><td /><td className="font-semibold">Saldo awal</td>
            <td /><td /><td className="text-right font-semibold col-sticky-end"><Money v={part.opening_balance} /></td>
          </tr>
          {part.rows.map((r) => (
            <tr key={`${r.je_id}:${r.doc_id}`} data-testid={`${testId}-row-${r.je_id}`}>
              <td className="whitespace-nowrap">{formatDate(r.date)}</td>
              <td className="min-w-[120px]">
                <span className="block text-fs-12 text-kn-text-2">{r.doc_label}</span>
                <button type="button" className="link-button font-semibold" data-testid={`${testId}-doc-${r.je_id}`}
                  onClick={() => openTrace({ docType: r.trace_type, docId: r.doc_id, number: r.doc_number })}>
                  {r.doc_number || "—"}
                </button>
                {r.je_number && (
                  <button type="button" className="link-button block text-fs-12" data-testid={`${testId}-je-${r.je_id}`}
                    onClick={() => openTrace({ docType: "journal_entry", docId: r.je_id, number: r.je_number })}>
                    Jurnal {r.je_number}
                  </button>
                )}
              </td>
              <td className="min-w-[120px]"><p className="line-clamp-2 break-words">{r.description}</p></td>
              <td className="text-right">{r.debit ? <Money v={r.debit} /> : ""}</td>
              <td className="text-right">{r.credit ? <Money v={r.credit} /> : ""}</td>
              <td className="text-right col-sticky-end"><Money v={r.balance} /></td>
            </tr>
          ))}
          <tr data-testid={`${testId}-closing`}>
            <td className="whitespace-nowrap">{formatDate(to)}</td><td /><td className="font-semibold">Saldo akhir</td>
            <td /><td /><td className="text-right font-bold col-sticky-end"><Money v={part.closing_balance} /></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export default function CustomerStatementTab({ customer, currentUser, selectedEntity }) {
  const perms = currentUser?.permissions;
  const entityId = selectedEntity && selectedEntity !== "all" ? selectedEntity : (customer?.entity_id || "");
  const hari = todayWib();
  const [from, setFrom] = useState(awalBulan(hari));
  const [to, setTo] = useState(hari);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const params = { entity_id: entityId || undefined, from, to };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/customers/${customer.id}/statement`, { params });
      setData(r.data); setError("");
    } catch (e) {
      setError(apiErrorText(e, "Rekening koran belum bisa dimuat."));
    } finally { setLoading(false); }
  }, [customer?.id, entityId, from, to]);   // eslint-disable-line react-hooks/exhaustive-deps
  // Memuat sendiri saat dibuka / pelanggan atau PT berganti; tanggal baru dimuat lewat "Tampilkan".
  useEffect(() => { load(); }, [customer?.id, entityId]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function cetak() {
    setBusy("pdf"); setNotice("");
    try {
      const r = await axios.get(`${API}/customers/${customer.id}/statement.pdf`, { params, responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `rekening-koran-${namaBerkas(customer.code || customer.name)}-${from}-${to}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      setNotice("PDF rekening koran sudah diunduh.");
    } catch (e) {
      setError(apiErrorText(e, "PDF rekening koran belum bisa dibuat."));
    } finally { setBusy(""); }
  }

  async function salin() {
    setBusy("copy"); setNotice("");
    try {
      const r = await axios.get(`${API}/customers/${customer.id}/reminder-text`, { params: { entity_id: entityId || undefined } });
      if (!r.data?.text) { setNotice(r.data?.note || "Tidak ada tagihan untuk diingatkan."); return; }
      setNotice((await copyText(r.data.text)) ? "Naskah pengingat disalin — tempel di pesan ke pelanggan."
        : "Naskah belum bisa disalin otomatis; salin dari kotak di bawah.");
      setData((d) => ({ ...(d || {}), reminder: r.data.text }));
    } catch (e) {
      setError(apiErrorText(e, "Naskah pengingat belum bisa disusun."));
    } finally { setBusy(""); }
  }

  const pen = data?.penalties;
  return (
    <div data-testid="customer-statement-tab">
      <div className="mb-2 flex flex-wrap items-end gap-2" data-testid="customer-statement-bar">
        <div>
          <label className="field-label">Dari</label>
          <KNDatePicker value={from} onChange={setFrom} max={to} clearable={false} data-testid="customer-statement-from" />
        </div>
        <div>
          <label className="field-label">Sampai</label>
          <KNDatePicker value={to} onChange={setTo} min={from} clearable={false} data-testid="customer-statement-to" />
        </div>
        <button type="button" className="primary-button btn-sm" onClick={load} disabled={loading}
          data-testid="customer-statement-show"><Search size={13} aria-hidden="true" />Tampilkan</button>
        {can(perms, "document", "print") && (
          <button type="button" className="secondary-button btn-sm" onClick={cetak} disabled={busy === "pdf" || !data}
            data-testid="customer-statement-pdf"><FileDown size={13} aria-hidden="true" />Cetak PDF</button>
        )}
        {can(perms, "order", "view") && (
          <button type="button" className="secondary-button btn-sm" onClick={salin} disabled={busy === "copy"}
            data-testid="customer-statement-copy"><Copy size={13} aria-hidden="true" />Salin pengingat</button>
        )}
      </div>
      {notice && <p className="mb-2 text-fs-12 text-kn-success-text" role="status" data-testid="customer-statement-notice">{notice}</p>}
      {data?.entity && (
        <p className="mb-2 text-fs-12 text-kn-text-2" data-testid="customer-statement-pt">
          Rekening koran di <b>{data.entity.legal_name || data.entity.short_name}</b> · {formatDate(data.from)} – {formatDate(data.to)}
        </p>
      )}
      {error ? <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="customer-statement-error" />
        : loading && !data ? <p className="py-6 text-center text-fs-13 text-kn-text-2" data-testid="customer-statement-loading">Memuat rekening koran…</p>
          : data && (
            <>
              <StatementTable part={data} from={data.from} to={data.to} testId="customer-statement-table" />
              {data.rows.length === 0 && (
                <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="customer-statement-empty">Tidak ada mutasi piutang pada periode ini.</p>
              )}
              <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="customer-statement-note">{data.note}</p>
              <h4 className="mb-1 mt-3 text-fs-13 font-bold text-kn-text">Denda</h4>
              {pen && (pen.rows.length > 0 || pen.opening_balance || pen.closing_balance)
                ? <StatementTable part={pen} from={data.from} to={data.to} testId="customer-statement-penalty" />
                : <p className="text-fs-12 text-kn-text-2" data-testid="customer-statement-penalty-empty">Tidak ada denda pada periode ini.</p>}
              {data.reminder && (
                <pre className="mt-3 whitespace-pre-wrap rounded-lg border border-kn-divider bg-kn-neutral-soft p-2 text-fs-12"
                  data-testid="customer-statement-reminder">{data.reminder}</pre>
              )}
            </>
          )}
    </div>
  );
}
