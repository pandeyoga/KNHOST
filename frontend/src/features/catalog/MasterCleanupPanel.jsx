/**
 * PREP-A (K-OPN-06) — Perbaikan master produk lewat lembar kerja.
 * Alur: unduh lembar (semua produk yang terlihat + stok lama + dokumen terbuka + saran duplikat) → MD/klien
 * mengisi kolom tindakan → unggah = PRATINJAU (tidak menulis apa pun; galat per baris) → Terapkan = satu batch
 * berjejak → Batalkan (alasan wajib). SKU tidak pernah diubah; stok tidak dipindah (didaftarkan ulang dari fisik).
 * Izin: unduh `product.export`; pratinjau/terapkan/batalkan `product.update` (server tetap menegakkan).
 */
import { useCallback, useEffect, useState } from "react";
import { Download, FileUp, Loader2, RotateCcw, CheckCircle2 } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";
import { formatDateTime } from "../../utils/formatters";
import { askConfirm, askReason, REASON_MIN_LENGTH } from "../../services/confirmService";
import { masterCleanupApi as api, blobErrorText, saveBlob, BATCH_STATUS, ROLLBACKABLE } from "./masterCleanupApi";
import MasterCleanupPreview from "./MasterCleanupPreview";

export default function MasterCleanupPanel({ canExport = false, canUpdate = false }) {
  const [file, setFile] = useState(null);
  const [pv, setPv] = useState(null);
  const [note, setNote] = useState("");
  const [batches, setBatches] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadBatches = useCallback(async () => {
    if (!canUpdate) return;
    try { setBatches(await api.batches()); } catch (e) { setError(apiErrorText(e, "Gagal memuat riwayat batch.")); }
  }, [canUpdate]);
  useEffect(() => { loadBatches(); }, [loadBatches]);

  const run = async (kind, fn) => {
    setBusy(kind); setError(""); setNotice("");
    try { await fn(); } catch (e) { setError(kind === "download" ? await blobErrorText(e, "Gagal mengunduh lembar.") : apiErrorText(e, "Gagal memproses.")); }
    finally { setBusy(""); }
  };
  const download = () => run("download", async () => {
    const res = await api.sheet("xlsx");
    setNotice(`Lembar diunduh: ${saveBlob(res, "perbaikan_master_produk.xlsx")}. Isi kolom kuning lalu unggah kembali.`);
  });
  const preview = () => run("preview", async () => { setPv(await api.preview(file)); });
  const apply = async () => {
    const s = pv.summary;
    const ok = await askConfirm({
      title: `Terapkan ${s.changes} perubahan master?`, danger: true, confirmLabel: "Terapkan", testId: "mc-apply-confirm",
      message: `Ganti nama ${s.GANTI_NAMA} · ganti kode ${s.GANTI_KODE} · gabung ${s.GABUNG_KE} · nonaktifkan ${s.NONAKTIFKAN}. `
        + "SKU lama tidak diubah dan stok tidak dipindah. Batch bisa dibatalkan dari riwayat.",
    });
    if (!ok) return;
    run("apply", async () => {
      const b = await api.apply({ actions: pv.actions, preview_signature: pv.preview_signature, note: note.trim(), source_filename: pv.source_filename });
      setNotice(`Batch ${b.id}: ${BATCH_STATUS[b.status] || b.status} — ${b.changed} perubahan${b.failed?.length ? `, ${b.failed.length} baris gagal` : ""}.`);
      setPv(null); setFile(null); setNote("");
      await loadBatches();
    });
  };
  const rollback = async (b) => {
    const reason = await askReason({ title: `Batalkan batch ${b.id}?`, confirmLabel: "Batalkan batch", danger: true,
      message: "Nama, status & penanda 'digantikan oleh' dikembalikan. Produk berkode baru dihapus bila belum dipakai, dinonaktifkan bila sudah.",
      reasonLabel: "Alasan pembatalan", reasonRequired: true, reasonMinLength: REASON_MIN_LENGTH, testId: "mc-rollback-dialog" });
    if (!reason || reason.trim().length < REASON_MIN_LENGTH) return;
    run("rollback", async () => {
      const r = await api.rollback(b.id, reason.trim());
      setNotice(`Batch ${b.id} dibatalkan: ${(r.rollback_done || []).length} dipulihkan, ${(r.rollback_skipped || []).length} dilewati.`);
      await loadBatches();
    });
  };

  return (
    <section data-testid="master-cleanup-panel" className="section-card space-y-3 p-3 text-[12px]">
      <h3 className="text-[13px] font-bold">Perbaikan master produk (lembar kerja)</h3>
      <p className="text-[#6B6B73]">
        1) Unduh lembar · 2) isi kolom kuning <b>tindakan</b> (PERTAHANKAN, GANTI_NAMA, GANTI_KODE, GABUNG_KE, NONAKTIFKAN) ·
        3) unggah untuk pratinjau (belum mengubah data) · 4) Terapkan sebagai satu batch yang bisa dibatalkan.
        SKU lama <b>tidak pernah diubah</b>: kode salah → produk baru berkode benar, kode lama ditandai “digantikan oleh”.
        Stok lama tidak dipindah — didaftarkan ulang dari fisik saat opname awal.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {canExport && (
          <button data-testid="mc-download" className="secondary-button !py-1.5" disabled={!!busy} onClick={download}>
            {busy === "download" ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />} Unduh lembar (XLSX)
          </button>
        )}
        {canUpdate && <>
          <label className="secondary-button !py-1.5 cursor-pointer" data-testid="mc-file-label">
            <FileUp size={13} /> {file ? "Ganti berkas" : "Pilih berkas (.xlsx / .csv)"}
            <input type="file" accept=".xlsx,.csv" className="sr-only" data-testid="mc-file"
              onChange={(e) => { setFile(e.target.files?.[0] || null); setPv(null); }} />
          </label>
          <span data-testid="mc-file-name" className="max-w-[240px] truncate text-[#6B6B73]">{file ? file.name : "Belum ada berkas"}</span>
          <button data-testid="mc-preview-btn" className="primary-button !py-1.5" disabled={!file || !!busy} onClick={preview}>
            {busy === "preview" ? <Loader2 size={13} className="animate-spin" /> : <FileUp size={13} />} Unggah & pratinjau
          </button>
        </>}
        {!canExport && !canUpdate && <span data-testid="mc-no-access" className="text-[#8E8E93]">Butuh izin ekspor/ubah produk.</span>}
      </div>
      {error && <ErrorNotice message={error} onDismiss={() => setError("")} testId="mc-error" />}
      {notice && <div data-testid="mc-notice" role="status" className="rounded-lg bg-[#EAF7EE] px-2 py-1.5 text-[#0A7A3B]">{notice}</div>}
      {pv && (
        <div data-testid="mc-preview" className="space-y-2">
          <MasterCleanupPreview pv={pv} />
          {canUpdate && (
            <div className="flex flex-wrap items-center gap-2">
              <input data-testid="mc-note" className="field min-w-[240px] flex-1" value={note} onChange={(e) => setNote(e.target.value)}
                placeholder="Catatan batch (wajib, min. 5 huruf) — mis. Perapian master sebelum opname Gedung A" />
              <button data-testid="mc-apply" className="primary-button !py-1.5" disabled={!!busy || !pv.can_apply || note.trim().length < REASON_MIN_LENGTH} onClick={apply}>
                {busy === "apply" ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />} Terapkan {pv.summary.changes} perubahan
              </button>
            </div>
          )}
          {!pv.can_apply && <p data-testid="mc-cannot-apply" className="text-[#8C4A00]">{pv.summary.errors ? `Perbaiki ${pv.summary.errors} galat di lembar lalu unggah ulang.` : "Tidak ada perubahan untuk diterapkan."}</p>}
        </div>
      )}
      {canUpdate && batches.length > 0 && (
        <div data-testid="mc-batches" className="space-y-1">
          <h4 className="font-semibold">Riwayat batch perbaikan</h4>
          {batches.map((b) => (
            <div key={b.id} data-testid={`mc-batch-${b.id}`} className="flex flex-wrap items-center gap-2 border-t border-[#F0F0F3] pt-1">
              <span className="font-mono">{b.id}</span>
              <span data-testid={`mc-batch-status-${b.id}`} className="font-semibold">{BATCH_STATUS[b.status] || b.status}</span>
              <span>· {b.changed ?? b.n_changes ?? 0} perubahan{(b.failed || []).length ? ` · ${b.failed.length} gagal` : ""} · {b.applied_by} · {formatDateTime(b.applied_at || b.created_at)}</span>
              {b.note && <span className="text-[#6B6B73]">— {b.note}</span>}
              {b.rollback_reason && <span className="text-[#8E8E93]">(dibatalkan: {b.rollback_reason})</span>}
              {ROLLBACKABLE.includes(b.status) && (
                <button data-testid={`mc-rollback-${b.id}`} className="secondary-button !py-0.5" disabled={!!busy} onClick={() => rollback(b)}>
                  <RotateCcw size={12} /> Batalkan
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
