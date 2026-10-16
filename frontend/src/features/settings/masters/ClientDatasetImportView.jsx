import { useCallback, useEffect, useState } from "react";
import { Download, FileUp, Loader2, RotateCcw, CheckCircle2 } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import AddFabricTypeInline from "./AddFabricTypeInline";
import { invalidateDomainEnums } from "../../../hooks/useDomainEnums";

const ST = { ok: "Akan diubah", same: "Sudah sama", error: "Ditolak" };
const ST_DONE = { ok: "Diubah", same: "Sudah sama", error: "Ditolak" };
const BST = { dry_run: "Draf (belum diterapkan)", committed: "Diterapkan", rolled_back: "Dibatalkan", committing: "Diproses", rolling_back: "Membatalkan" };

/** L01 LN-011 — impor dataset client: artikel · tahap · jenis kain · supplier/warna (dry-run → terapkan → batalkan). */
export default function ClientDatasetImportView() {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [cur, setCur] = useState(null);
  const [batches, setBatches] = useState([]);
  const [filter, setFilter] = useState("all");

  const loadBatches = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/client-dataset/batches`); setBatches(data || []); } catch { setBatches([]); }
  }, []);
  useEffect(() => { loadBatches(); }, [loadBatches]);

  const download = async () => {
    const { data } = await axios.get(`${API}/client-dataset/template`, { responseType: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(data); a.download = "template_dataset_client.csv"; a.click();
  };
  const upload = async () => {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      const fd = new FormData(); fd.append("file", file);
      const { data } = await axios.post(`${API}/client-dataset/upload`, fd);
      setCur(data); loadBatches();
    } catch (e) { setErr(e.response?.data?.detail || "Gagal membaca file."); }
    finally { setBusy(false); }
  };
  const act = async (id, kind) => {
    if (kind === "rollback" && !window.confirm("Batalkan impor ini? Nilai sebelum impor dipulihkan.")) return;
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/client-dataset/batches/${id}/${kind}`);
      if (cur?.id === id) setCur({ ...cur, status: kind === "commit" ? "committed" : "rolled_back" });
      loadBatches();
    } catch (e) { setErr(e.response?.data?.detail || "Gagal memproses batch."); }
    finally { setBusy(false); }
  };

  const rep = cur?.report;
  const rows = (rep?.rows || []).filter((r) => filter === "all" || r.status === filter);
  const unk = rep?.unknown_values || {};
  return (
    <section className="space-y-3" data-testid="client-dataset-import">
      <div className="rounded-xl border border-[#E5E5EA] bg-white p-4">
        <h2 className="text-[15px] font-bold">Impor Dataset Client — artikel, tahap, jenis kain, supplier/warna</h2>
        <p className="mt-1 text-[12px] text-[#6B6B73]">
          Hanya memperbarui master yang sudah ada (artikel lewat kode/nama, SKU lewat kode SKU atau artikel + warna internal) dan peta warna supplier.
          Artikel, SKU, supplier, tahap, atau jenis kain yang belum ada <b>tidak dibuat otomatis</b>; semuanya dilaporkan untuk diputuskan. Selalu dicek dulu (dry-run) dan bisa dibatalkan.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button className="secondary-button !py-1.5 text-[12px]" onClick={download} data-testid="cds-template"><Download size={13} /> Unduh template CSV</button>
          <input type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="cds-file" className="text-[12px]" />
          <button className="primary-button !py-1.5 text-[12px]" disabled={!file || busy} onClick={upload} data-testid="cds-upload">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <FileUp size={13} />} Cek file (dry-run)
          </button>
        </div>
        {err && <p className="mt-2 text-[12px] text-[#C0392B]" data-testid="cds-error">{err}</p>}
      </div>

      {rep && (
        <div className="rounded-xl border border-[#E5E5EA] bg-white p-4" data-testid="cds-report">
          <div className="flex flex-wrap items-center gap-2 text-[12px]">
            <b>{cur.filename}</b> · {BST[cur.status] || cur.status}
            <span data-testid="cds-summary">· {rep.summary.rows} baris: {rep.summary.ok} diubah, {rep.summary.same} sama, {rep.summary.error} ditolak ·
              artikel {rep.summary.templates}, SKU {rep.summary.products}, peta supplier {rep.summary.supplier_items}</span>
            {cur.status === "dry_run" && (
              <button className="primary-button ml-auto !py-1.5 text-[12px]" disabled={busy || !rep.summary.ok} onClick={() => act(cur.id, "commit")} data-testid="cds-commit">
                <CheckCircle2 size={13} /> Terapkan {rep.summary.ok} baris
              </button>
            )}
          </div>
          {Object.entries(unk).some(([, v]) => Object.keys(v).length) && (
            <div className="mt-2 rounded-lg bg-[#FFF5E5] p-2 text-[11.5px] text-[#8C4A00]" data-testid="cds-unknown">
              <b>Nilai belum ada di master (perlu keputusan):</b>{" "}
              {Object.entries(unk).filter(([, v]) => Object.keys(v).length).map(([k, v]) => (
                <span key={k} className="mr-2">{k}: {Object.entries(v).map(([n, c]) => (
                  <span key={n} className="mr-1">{n} ({c}){k === "jenis_kain" && cur.status === "dry_run" && (
                    <AddFabricTypeInline value={n} onError={setErr} onAdded={async () => { invalidateDomainEnums(); const { data } = await axios.get(`${API}/client-dataset/batches/${cur.id}`); setCur(data); loadBatches(); }} />
                  )}</span>
                ))}</span>
              ))}
            </div>
          )}
          <div className="mt-2 flex gap-1.5 text-[11px]">
            {["all", "ok", "same", "error"].map((f) => (
              <button key={f} className={`rounded-full px-2.5 py-1 ${filter === f ? "bg-[#1C1C1E] text-white" : "bg-[#F2F2F7]"}`} onClick={() => setFilter(f)} data-testid={`cds-filter-${f}`}>
                {f === "all" ? "Semua" : ST[f]}
              </button>
            ))}
          </div>
          <div className="mt-2 max-h-[420px] overflow-auto">
            <table className="w-full text-[11.5px]" data-testid="cds-rows">
              <thead className="sticky top-0 bg-[#F7F7F9] text-left text-[10.5px] uppercase text-[#8E8E93]">
                <tr><th className="px-2 py-1.5">Baris</th><th className="px-2 py-1.5">Artikel / SKU</th><th className="px-2 py-1.5">Status</th><th className="px-2 py-1.5">Perubahan / alasan</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.line} className="border-t border-[#F0F0F3] align-top" data-testid={`cds-row-${r.line}`}>
                    <td className="px-2 py-1.5 tabular-nums">{r.line}</td>
                    <td className="px-2 py-1.5">{r.input.sku || r.input.kode_artikel || r.input.nama_artikel} {r.input.warna_internal && `· ${r.input.warna_internal}`}</td>
                    <td className={`px-2 py-1.5 font-semibold ${r.status === "error" ? "text-[#C0392B]" : r.status === "ok" ? "text-[#0A7A3B]" : "text-[#8E8E93]"}`}>{(cur.status === "committed" ? ST_DONE : ST)[r.status]}</td>
                    <td className="px-2 py-1.5">
                      {[...r.errors, ...r.changes, ...r.warnings].map((t, i) => <div key={i}>{t}</div>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-[#E5E5EA] bg-white p-4">
        <h3 className="text-[13px] font-bold">Riwayat impor</h3>
        <table className="mt-2 w-full text-[11.5px]" data-testid="cds-batches">
          <tbody>
            {batches.map((b) => (
              <tr key={b.id} className="border-t border-[#F0F0F3]" data-testid={`cds-batch-${b.id}`}>
                <td className="px-2 py-1.5">{(b.created_at || "").slice(0, 16).replace("T", " ")}</td>
                <td className="px-2 py-1.5">{b.filename}</td>
                <td className="px-2 py-1.5">{BST[b.status] || b.status}</td>
                <td className="px-2 py-1.5">{b.summary?.ok ?? 0} diubah · {b.summary?.error ?? 0} ditolak</td>
                <td className="px-2 py-1.5 text-right">
                  {b.status === "dry_run" && <button className="secondary-button !py-1 text-[11px]" onClick={async () => { const { data } = await axios.get(`${API}/client-dataset/batches/${b.id}`); setCur(data); }} data-testid={`cds-open-${b.id}`}>Buka</button>}
                  {b.status === "committed" && <button className="secondary-button !py-1 text-[11px]" disabled={busy} onClick={() => act(b.id, "rollback")} data-testid={`cds-rollback-${b.id}`}><RotateCcw size={12} /> Batalkan</button>}
                </td>
              </tr>
            ))}
            {!batches.length && <tr><td className="px-2 py-3 text-[#8E8E93]">Belum ada impor.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
