/**
 * PostingFailuresView — Panel Posting Gagal (P03 lanjutan · PK-18).
 * Semua dokumen yang jurnalnya gagal tercatat (jenisnya dari registri server `services/posting_registry.py`) + ulang.
 * Sumber: GET /api/finance/posting-failures?kind&page&page_size&q · POST /api/finance/posting-failures/{kind}/{id}/retry
 *
 * PK-18 (UX-04) — tiga keadaan dibedakan: memuat · galat (kotak merah + Coba lagi, TANPA teks kosong) · kosong (hanya
 * sesudah muat berhasil). Halaman & hitungan dari server (`02` D4/L4); nomor dokumen = tautan ke dokumennya (`02` L8).
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityBadge from "../../components/EntityBadge";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";
import KNPager from "../../components/KNPager";
import { SearchBox } from "../../components/ListPageParts";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";
import { useAppNav } from "../../context/AppNavContext";
import { canCurrent } from "../../config/roles";

const PAGE_SIZE = 50;
export const KETERANGAN = "Dokumen yang jurnalnya gagal tercatat. Perbaiki penyebabnya lalu tekan “Ulang Posting”.";
export const TEKS_KOSONG = "Tidak ada dokumen dengan jurnal gagal. Semua posting tercatat.";
export const TEKS_GALAT = "Daftar posting gagal tidak bisa dimuat.";
const ALASAN_TANPA_IZIN = "Ulang posting butuh akses kelola Akuntansi.";

export default function PostingFailuresView() {
  const { openDocument } = useAppNav();
  const [data, setData] = useState({ items: [], counts: {}, labels: {}, total: 0 });
  const [state, setState] = useState("loading");   // loading | error | ready
  const [loadErr, setLoadErr] = useState("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [kind, setKind] = useState("");
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const canRetry = canCurrent("accounting", "manage");

  useEffect(() => {
    const t = setTimeout(() => setQDebounced(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/finance/posting-failures`,
        { params: { kind: kind || undefined, page, page_size: PAGE_SIZE, q: qDebounced || undefined } });
      setData(r.data || {});
      setLoadErr("");
      setState("ready");
    } catch (e) {
      setLoadErr(apiErrorText(e) || "");
      setState("error");
    }
  }, [kind, page, qDebounced]);
  useEffect(() => { load(); }, [load]);

  const pilihJenis = (k) => { setKind(k === "all" ? "" : k); setPage(1); };

  const retry = async (it) => {
    // G1-16 — Ulang Posting menerbitkan jurnal nyata → konfirmasi yang menyebut dokumen & nilai.
    if (!(await askConfirm({
      title: `Ulang posting ${it.number}?`,
      message: `${it.kind_label || "Dokumen"} senilai ${formatCurrency(Number(it.amount) || 0)} akan dicoba diposting ulang ke buku besar. `
        + "Pastikan penyebab galatnya sudah diperbaiki.",
      confirmLabel: "Ulang Posting",
    }))) return;
    setBusy(it.id);
    try {
      const r = await axios.post(`${API}/finance/posting-failures/${it.kind}/${encodeURIComponent(it.id)}/retry`);
      const st = r.data?.gl_status;
      setMsg(`${it.number}: ${st === "posted" ? "jurnal terbit." : st === "not_required" ? "tidak memerlukan jurnal." : "status jurnal diperbarui."}`);
      await load();
      window.dispatchEvent(new CustomEvent("kn-posting-failures-changed"));
    } catch (e) { setMsg(`${it.number}: ${apiErrorText(e) || "ulang posting gagal"}`); } finally { setBusy(""); }
  };

  const counts = data.counts || {};
  const labels = data.labels || {};
  const totalSemua = Object.values(counts).reduce((a, b) => a + (Number(b) || 0), 0);
  const chips = [{ key: "all", label: "Semua", count: totalSemua },
    ...Object.entries(labels).map(([k, label]) => ({ key: k, label, count: counts[k] || 0,
      hidden: !(counts[k] > 0) && kind !== k }))];
  const rows = data.items || [];

  return (
    <div className="space-y-4" data-testid="posting-failures-view">
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-kn-danger-text" aria-hidden="true" />
            <h2 data-testid="pf-title">Posting Jurnal Gagal</h2>
          </div>
          <button type="button" data-testid="pf-refresh" onClick={load} className="secondary-button btn-sm ml-auto whitespace-nowrap">
            <RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-[12px] text-kn-text-2" data-testid="pf-keterangan">{KETERANGAN}</p>
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Cari nomor dokumen…" testId="pf-search">
            <FilterChips testId="pf-filter" value={kind || "all"} onChange={(k) => pilihJenis(k || "all")}
              options={chips} ariaLabel="Jenis dokumen" />
          </SearchBox>
          {!canRetry && <p className="text-[12px] text-kn-text-2" data-testid="pf-no-manage">{ALASAN_TANPA_IZIN}</p>}
        </div>
      </div>

      {msg && <div data-testid="pf-msg" className="notice-bar warning"><span className="text-[12px]">{msg}</span></div>}

      {state === "loading" && (
        <div data-testid="pf-loading" className="section-card section-pad text-[13px] text-kn-text-2" role="status">
          Memuat daftar posting gagal…</div>
      )}
      {state === "error" && (
        <ErrorNotice testId="pf-error" message={`${TEKS_GALAT} ${loadErr}`.trim()} onRetry={load} />
      )}
      {state === "ready" && rows.length === 0 && (
        <div data-testid="pf-empty" className="section-card section-pad text-center text-[13px] text-kn-text-2">
          {qDebounced ? `Tidak ada dokumen bernomor “${qDebounced}” dengan jurnal gagal.` : TEKS_KOSONG}</div>
      )}
      {state === "ready" && rows.length > 0 && (
        <div className="section-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full text-[12px]" data-testid="pf-table">
              <thead>
                <tr><th>Jenis</th><th>Nomor</th><th>PT</th><th className="text-right">Nilai</th><th>Galat</th>
                  <th className="col-sticky-end text-right">Aksi</th></tr>
              </thead>
              <tbody>
                {rows.map((it) => (
                  <tr key={`${it.kind}-${it.id}`} data-testid={`pf-row-${it.id}`}>
                    <td className="font-semibold">
                      <span className="status-pill status-rejected inline-flex items-center gap-1 whitespace-nowrap">
                        <AlertTriangle size={12} aria-hidden="true" />{it.kind_label}</span>
                    </td>
                    <td className="font-mono">
                      {it.link?.view ? (
                        <button type="button" className="link-button" data-testid={`pf-open-${it.id}`}
                          onClick={() => openDocument({ ...it.link, number: it.number })}>{it.number}</button>
                      ) : it.number}
                    </td>
                    <td>{it.entity_id ? <EntityBadge entityId={it.entity_id} /> : "—"}</td>
                    <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(Number(it.amount) || 0)}</td>
                    <td className="max-w-[320px] break-words text-kn-danger-text" title={it.error}>{it.error || "—"}</td>
                    <td className="col-sticky-end text-right">
                      <button type="button" data-testid={`pf-retry-${it.id}`} disabled={busy === it.id || !canRetry}
                        onClick={() => retry(it)} title={canRetry ? "" : ALASAN_TANPA_IZIN}
                        className="secondary-button btn-sm whitespace-nowrap">
                        {busy === it.id ? "Memproses…" : "Ulang Posting"}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-[12px] text-kn-text-2">
            <span data-testid="pf-total">{data.total || 0} dokumen dengan jurnal gagal</span>
            <KNPager page={page} pageSize={PAGE_SIZE} total={data.total || 0} onChange={setPage} testId="pf-pager" />
          </div>
        </div>
      )}
    </div>
  );
}
