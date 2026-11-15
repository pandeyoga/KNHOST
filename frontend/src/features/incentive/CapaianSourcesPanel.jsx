/**
 * CapaianSourcesPanel — KM-T2 · panel "telusur" di layar Capaian (pop-up rincian): dokumen di balik SATU angka (Omzet, Retur,
 * atau Uang masuk) satu baris, dengan jumlah total yang sama dengan angka sel yang dibuka (`02_STANDAR.md` §5 D4).
 *
 * Sumber: GET /api/incentive/achievement/sources (parameter periode & saringan sama dengan tabel + `metric`, `sales_id`
 * atau `key`, `page`, `page_size`). Nomor dokumen membuka surat jalan (lewat pesanannya), nota kredit, kwitansi, atau
 * pesanan (L8) memakai tautan tunggal server (`doc_refs_service.link_of`).
 *
 * Pop-up rincian baku `DetailModal` (INV-UI-08/INV-UI-11: berkas baru tidak merakit lapisan sendiri; Esc, klik latar,
 * dan kunci gulir halaman diurus di sana). Kotak centang per baris + bilah "{n} dokumen dipilih · jumlah Rp … · rata-rata
 * Rp …" (dihitung di layar).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import DetailModal from "../../components/DetailModal";
import ErrorNotice from "../../components/ErrorNotice";
import KNPager from "../../components/KNPager";
import { useAppNav } from "../../context/AppNavContext";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate } from "../../utils/formatters";

export const UKURAN_HALAMAN = 50;

/** Judul panel: "{kolom} — {sales} — {periode}". */
export const judulPanel = ({ metricLabel, name, periodLabel }) => `${metricLabel} — ${name} — ${periodLabel}`;

/** Ringkasan pilihan dokumen: "{n} dokumen dipilih · jumlah Rp … · rata-rata Rp …" ("" bila tidak ada pilihan). */
export function teksPilihanDokumen(items, selected) {
  const pilih = (items || []).filter((it) => selected.has(kunciDokumen(it)));
  if (!pilih.length) return "";
  const jumlah = pilih.reduce((s, it) => s + Number(it.amount || 0), 0);
  return `${pilih.length} dokumen dipilih · jumlah ${formatCurrency(jumlah)} · rata-rata ${formatCurrency(Math.round(jumlah / pilih.length))}`;
}

export const kunciDokumen = (it) => `${it.doc_type}:${it.doc_id}:${it.so_id}:${it.source_kind}`;

export default function CapaianSourcesPanel({ request, onClose }) {
  const nav = useAppNav();
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState(() => new Set());

  const load = useCallback(async () => {
    if (!request) return;
    setState("loading");
    try {
      const r = await axios.get(`${API}/incentive/achievement/sources`, {
        params: { ...request.params, metric: request.metric, page, page_size: UKURAN_HALAMAN } });
      setData(r.data); setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [request, page]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); setSelected(new Set()); }, [request]);

  const items = useMemo(() => data?.items || [], [data]);
  const pilihan = teksPilihanDokumen(items, selected);
  const togel = (k) => setSelected((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const semua = items.length > 0 && items.every((it) => selected.has(kunciDokumen(it)));
  const togelSemua = () => setSelected((s) => {
    const n = new Set(s);
    items.forEach((it) => (semua ? n.delete(kunciDokumen(it)) : n.add(kunciDokumen(it))));
    return n;
  });
  const buka = (it) => {
    if (!it.link?.view) return;
    onClose?.();
    nav.openDocument({ ...it.link, number: it.doc_number });
  };
  if (!request) return null;
  const judul = judulPanel(request);

  return (
    <DetailModal open onClose={onClose} size="lg" label={judul} testId="cap-src-modal" showClose={false}>
      <div className="section-card flex max-h-[calc(100dvh-2rem)] flex-col" data-testid="cap-src-panel">
        <div className="section-head">
          <h2 className="min-w-0 break-words" data-testid="cap-src-title">{judul}</h2>
          <button type="button" className="icon-button" aria-label="Tutup" title="Tutup (Esc)" data-testid="cap-src-close" onClick={onClose}>
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {state === "loading" ? (
            <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="cap-src-loading">Memuat dokumen…</div>
          ) : state === "error" ? (
            <div className="section-pad"><ErrorNotice testId="cap-src-error" message={`Dokumen gagal dimuat. ${err}`.trim()} onRetry={load} /></div>
          ) : items.length === 0 ? (
            <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="cap-src-empty">Tidak ada dokumen untuk angka ini.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full" data-testid="cap-src-table">
                <thead><tr>
                  <th className="w-8"><input type="checkbox" aria-label="Pilih semua dokumen di halaman ini" checked={semua} onChange={togelSemua} data-testid="cap-src-all" /></th>
                  <th>Tanggal</th><th>Dokumen</th><th>Pelanggan</th><th>Pesanan</th><th>Jenis</th><th className="text-right">Nilai</th>
                </tr></thead>
                <tbody>
                  {items.map((it) => {
                    const k = kunciDokumen(it);
                    return (
                      <tr key={k} data-testid={`cap-src-row-${it.doc_id}`}>
                        <td><input type="checkbox" aria-label={`Pilih ${it.doc_number || "dokumen"}`} checked={selected.has(k)} onChange={() => togel(k)} data-testid={`cap-src-check-${it.doc_id}`} /></td>
                        <td className="whitespace-nowrap">{formatDate(it.date_wib)}</td>
                        <td className="min-w-[120px] break-words">
                          {it.link?.view ? (
                            <button type="button" className="link-button font-mono text-left" data-testid={`cap-src-open-${it.doc_id}`} onClick={() => buka(it)}>{it.doc_number || "Buka dokumen"}</button>
                          ) : <span className="font-mono">{it.doc_number || "—"}</span>}
                        </td>
                        <td className="min-w-[120px] break-words">{it.customer_name || "—"}</td>
                        <td className="font-mono whitespace-nowrap">{it.so_number || "—"}</td>
                        <td className="min-w-[96px]">{it.source_label}{Number(it.split) < 0.999 ? <span className="block text-fs-12 text-kn-text-2">porsi {Math.round(Number(it.split) * 1000) / 10} %</span> : null}</td>
                        <td className="text-right tabular-nums">{formatCurrency(it.amount)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {state === "ready" && data && (
          <div className="border-t border-kn-divider">
            {pilihan && <div className="notice-bar info mx-3 mt-2" data-testid="cap-src-selection"><span className="text-fs-12">{pilihan}</span></div>}
            <p className="px-3 pt-2 text-fs-13 font-semibold text-kn-text" data-testid="cap-src-sum">
              Jumlah {formatCurrency(data.sum)} dari {data.total} dokumen</p>
            <KNPager page={page} pageSize={UKURAN_HALAMAN} total={data.total} onChange={setPage} testId="cap-src-pager" />
          </div>
        )}
      </div>
    </DetailModal>
  );
}
