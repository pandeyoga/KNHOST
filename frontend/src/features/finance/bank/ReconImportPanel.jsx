/**
 * FASE G-8 — ReconImportPanel: pilih template bank, tempel/unggah berkas,
 * PRATINJAU hasil baca, lalu impor.
 *
 * Kenapa ada pratinjau: sebelum fase ini impor hanya menerima CSV 4 kolom baku yang
 * harus diketik ulang manusia, dan kesalahan baca baru terlihat SETELAH data masuk.
 *
 * Fase 4 · R2 (L-03) — dulu panel yang DISELIPKAN di tengah halaman (tombol "Impor mutasi bank" ⇄ "Tutup panel
 * impor"), galatnya ke bilah halaman. Kini `FormModal` baku: Pratinjau & Impor di kaki yang menempel, galat
 * pratinjau/impor tampil di DALAM pop-up (`recon-import-error`). Isian & testid tetap (`recon-import-panel` = kartu
 * pop-up, `recon-format-select`, `recon-file-input`, `recon-raw`, `recon-preview-btn`, `recon-import-submit`).
 */
import { useMemo, useState } from "react";
import { Upload, RefreshCw, Eye, AlertTriangle, FileUp } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { KNSelect } from "../../../components/KNSelect";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency } from "../../../utils/formatters";

const fmtDate = (s) => {
  if (!s) return "—";
  try {
    return new Date(String(s).length <= 10 ? `${s}T00:00:00` : s)
      .toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" });
  } catch { return s; }
};

export default function ReconImportPanel({ accountId, formats, onDone, onClose }) {
  const [formatId, setFormatId] = useState("");
  const [raw, setRaw] = useState("");
  const [fileName, setFileName] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const options = useMemo(() => ([
    { value: "", label: "Kenali otomatis dari isi berkas" },
    ...(formats || []).map((f) => ({
      value: f.id, label: `${f.name} · ${(f.file_kind || "").toUpperCase()}`,
    })),
  ]), [formats]);

  async function readFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFileName(f.name);
    const text = await f.text();
    setRaw(text);
    setPreview(null);
  }

  async function doPreview() {
    setBusy("preview"); setErr("");
    try {
      const r = await axios.post(`${API}/bank-reconciliation/preview`,
        { raw, format_id: formatId || "", year_hint: new Date().getFullYear() });
      setPreview(r.data);
    } catch (e) { setErr(apiErrorText(e)); setPreview(null); } finally { setBusy(""); }
  }

  async function doImport() {
    setBusy("import"); setErr("");
    try {
      const r = await axios.post(`${API}/bank-reconciliation/import-file`,
        { bank_account_id: accountId, raw, format_id: formatId || "",
          year_hint: new Date().getFullYear() });
      const d = r.data || {};
      onDone(`Impor ${d.format_name || ""}: ${d.imported} baris baru, ${d.skipped} dilewati `
        + `(sudah pernah masuk)${d.error_count ? `, ${d.error_count} baris tidak terbaca` : ""}.`);
      setRaw(""); setPreview(null); setFileName("");
    } catch (e) { setErr(apiErrorText(e)); } finally { setBusy(""); }
  }

  return (
    <FormModal open onClose={onClose} size="lg" icon={Upload} title="Impor mutasi bank"
      subtitle="Pilih template bank, unggah atau tempel rekening koran, pratinjau hasil baca, lalu impor."
      testId="recon-import-panel" busy={busy === "import"}
      footer={(
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy === "import"}>Batal</button>
          <button type="button" data-testid="recon-preview-btn" className="secondary-button"
            disabled={!raw.trim() || busy === "preview"} onClick={doPreview}>
            {busy === "preview" ? <RefreshCw size={14} className="spin" /> : <Eye size={14} />}
            Pratinjau
          </button>
          <button type="button" data-testid="recon-import-submit" className="primary-button"
            disabled={!raw.trim() || !accountId || busy === "import"} onClick={doImport}>
            {busy === "import" ? <RefreshCw size={14} className="spin" /> : <Upload size={14} />}
            Impor
          </button>
        </div>
      )}>
      <ErrorNotice message={err} onDismiss={() => setErr("")} testId="recon-import-error" />
      <div className="flex flex-wrap items-end gap-3 mb-2">
        <div className="w-full sm:w-auto sm:min-w-[260px]">
          <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">
            Template bank
          </label>
          <KNSelect data-testid="recon-format-select" value={formatId}
            onValueChange={setFormatId} options={options} />
        </div>
        <div>
          <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">
            Unggah berkas
          </label>
          <label className="secondary-button cursor-pointer" data-testid="recon-file-label">
            <FileUp size={14} /> {fileName || "Pilih berkas (CSV · MT940 · OFX)"}
            <input data-testid="recon-file-input" type="file" className="hidden"
              accept=".csv,.txt,.sta,.mt940,.ofx,.qfx" onChange={readFile} />
          </label>
        </div>
      </div>
      <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">
        Atau tempel isi rekening koran di sini
      </label>
      <textarea data-testid="recon-raw" className="textarea font-mono text-[11px]" rows={5}
        placeholder={"Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo\n"
          + "12/07,TRSF E-BANKING CR PT MAJU JAYA SO-0007,0000,\"12.500.000,00\",CR,..."}
        value={raw} onChange={(e) => { setRaw(e.target.value); setPreview(null); }} />

      {preview && (
        <div className="mt-3" data-testid="recon-preview">
          <p className="text-[12px] text-[#1C1C1E] mb-1">
            Terbaca <b>{preview.total}</b> baris memakai template <b>{preview.format?.name}</b>
            {preview.detected ? " (dikenali otomatis)" : ""} · masuk{" "}
            <b className="text-[#1B7F4B]">{formatCurrency(preview.sum_in)}</b> · keluar{" "}
            <b className="text-[#C0392B]">{formatCurrency(preview.sum_out)}</b>
          </p>
          {preview.error_count > 0 && (
            <p className="text-[11px] text-[#B26A00] flex items-center gap-1 mb-1"
              data-testid="recon-preview-errors">
              <AlertTriangle size={12} /> {preview.error_count} baris tidak terbaca dan TIDAK akan
              diimpor — contoh: {preview.errors?.[0]?.reason} (baris {preview.errors?.[0]?.row})
            </p>
          )}
          <div className="overflow-x-auto rounded border border-[#E5E5EA] sm:max-h-[260px] sm:overflow-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#F7F8FA]">
                  <th className="px-2 py-1.5">Tanggal</th>
                  <th className="px-2 py-1.5">Keterangan</th>
                  <th className="px-2 py-1.5">Referensi</th>
                  <th className="px-2 py-1.5 text-right">Nominal</th>
                  <th className="px-2 py-1.5">Arah</th>
                </tr>
              </thead>
              <tbody>
                {(preview.rows || []).map((r, i) => (
                  <tr key={`${r.row}-${i}`} className="border-t border-[#F5F5F7]">
                    <td className="px-2 py-1.5 whitespace-nowrap">{fmtDate(r.stmt_date)}</td>
                    <td className="px-2 py-1.5 max-w-[320px] truncate" title={r.description}>
                      {r.description || "—"}
                    </td>
                    <td className="px-2 py-1.5 text-[#6B6B73]">{r.ref || "—"}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      {formatCurrency(r.amount)}
                    </td>
                    <td className={`px-2 py-1.5 font-semibold ${
                      r.direction === "in" ? "text-[#1B7F4B]" : "text-[#C0392B]"}`}>
                      {r.direction === "in" ? "Masuk" : "Keluar"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </FormModal>
  );
}
