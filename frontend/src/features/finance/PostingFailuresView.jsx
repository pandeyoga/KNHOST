/**
 * PostingFailuresView — Panel Posting Gagal (P03 lanjutan).
 * Semua dokumen yang jurnalnya gagal (kas, kwitansi, retur beli, GR, surat jalan) + ulang posting.
 * Sumber: GET /api/finance/posting-failures · POST /api/finance/posting-failures/{kind}/{id}/retry
 */
import { useEffect, useState } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityBadge from "../../components/EntityBadge";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";

const rp = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });   // 23 Okt — rupiah tanpa desimal liar

import PagedRows from "@/components/PagedRows";

export default function PostingFailuresView() {
  const [data, setData] = useState({ items: [], counts: {}, labels: {} });
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [filter, setFilter] = useState("");

  const load = async () => {
    try {
      const r = await axios.get(`${API}/finance/posting-failures`);
      setData(r.data);
    } catch (e) { setMsg(apiErrorText(e) || "Gagal memuat daftar"); }
  };
  useEffect(() => { load(); }, []);

  const retry = async (it) => {
    // G1-16 — Ulang Posting menerbitkan jurnal nyata → konfirmasi yang menyebut dokumen & nilai.
    if (!(await askConfirm({
      title: `Ulang posting ${it.number}?`,
      message: `${it.kind_label || "Dokumen"} senilai Rp ${rp.format(Number(it.amount) || 0)} akan dicoba diposting ulang ke buku besar. `
        + "Pastikan penyebab galatnya sudah diperbaiki.",
      confirmLabel: "Ulang Posting",
    }))) return;
    setBusy(it.id);
    try {
      const r = await axios.post(`${API}/finance/posting-failures/${it.kind}/${it.id}/retry`);
      setMsg(`${it.number}: status jurnal sekarang ${r.data.gl_status}`);
      await load();
      window.dispatchEvent(new CustomEvent("kn-posting-failures-changed"));
    } catch (e) { setMsg(`${it.number}: ${apiErrorText(e) || "ulang posting gagal"}`); } finally { setBusy(""); }
  };

  const rows = data.items.filter((i) => !filter || i.kind === filter);
  return (
    <div className="space-y-4" data-testid="posting-failures-view">
      {/* Audit UI 24 Okt (135): judul + kartu standar, tab garis bawah (dulu pil hitam), muat ulang = tombol. */}
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-[#C0392B]" />
            <h2 data-testid="pf-title">Posting Jurnal Gagal</h2>
          </div>
          <button data-testid="pf-refresh" onClick={load} className="secondary-button ml-auto">
            <RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body">
          <p className="mb-2 text-[11.5px] text-[#6B6B73]">Dokumen yang jurnalnya gagal tercatat (kas, kwitansi piutang, retur beli, penerimaan barang, surat jalan). Perbaiki penyebabnya lalu tekan “Ulang Posting”.</p>
          <div className="tab-bar !mb-0">
            <button data-testid="pf-filter-all" onClick={() => setFilter("")}
              className={`tab-button ${!filter ? "active" : ""}`}>
              Semua <span className="tab-badge">{data.total || 0}</span></button>
            {Object.entries(data.labels || {}).map(([k, label]) => (
              <button key={k} data-testid={`pf-filter-${k}`} onClick={() => setFilter(k)}
                className={`tab-button ${filter === k ? "active" : ""}`}>
                {label} <span className="tab-badge">{(data.counts || {})[k] || 0}</span></button>
            ))}
          </div>
        </div>
      </div>
      {msg && <div data-testid="pf-msg" className="rounded-lg bg-[#FFF8E6] px-3 py-2 text-[12px] font-semibold text-[#8C4A00]">{msg}</div>}
      {rows.length === 0 ? (
        <div data-testid="pf-empty" className="rounded-xl border border-dashed border-[#DCE6F5] p-8 text-center text-[13px] text-[#6B7280]">
          Tidak ada dokumen dengan jurnal gagal. Semua posting tercatat.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-[#E5E5EA]">
          <table className="w-full min-w-[720px] text-[12px]" data-testid="pf-table">
            <thead className="whitespace-nowrap bg-[#F7F7FA] text-left text-[11px] uppercase text-[#6B7280]">
              <tr><th className="p-2">Jenis</th><th className="p-2">Nomor</th><th className="p-2">Entitas</th>
                <th className="p-2 text-right">Nilai</th><th className="p-2">Galat</th><th className="p-2" /></tr>
            </thead>
            <tbody>
              <PagedRows rows={rows} testId="posting-failures-pager">{(it) => (
                <tr key={`${it.kind}-${it.id}`} className="border-t border-[#F2F2F7]" data-testid={`pf-row-${it.id}`}>
                  <td className="p-2 font-semibold"><span className="inline-flex items-center gap-1"><AlertTriangle size={12} className="text-[#C2410C]" />{it.kind_label}</span></td>
                  <td className="p-2 font-mono">{it.number}</td>
                  <td className="p-2">{it.entity_id ? <EntityBadge entityId={it.entity_id} /> : "—"}</td>
                  <td className="whitespace-nowrap p-2 text-right tabular-nums">Rp {rp.format(Number(it.amount) || 0)}</td>
                  <td className="max-w-[360px] truncate p-2 text-[#B42318]" title={it.error}>{it.error || "—"}</td>
                  <td className="p-2 text-right">
                    <button data-testid={`pf-retry-${it.id}`} disabled={busy === it.id} onClick={() => retry(it)}
                      className="rounded-lg bg-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                      {busy === it.id ? "Memproses…" : "Ulang Posting"}</button>
                  </td>
                </tr>
              )}</PagedRows>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
