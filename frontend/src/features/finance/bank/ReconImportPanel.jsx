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
 * F1 — pesan sukses impor menyebut jumlah kwitansi otomatis dari mutasi berkode dan yang perlu dicek (`ringkasF1`).
 */
import { useMemo, useState } from "react";
import { Upload, RefreshCw, Eye, AlertTriangle, FileUp } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { KNSelect } from "../../../components/KNSelect";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency, formatDate, todayWib } from "../../../utils/formatters";
import { ringkasF1 } from "./bankLineReceiptApi";

// Tahun acuan baris mutasi tanpa tahun = tahun berjalan WIB (bukan zona perangkat — beda di malam tahun baru).
const yearHint = () => Number(todayWib().slice(0, 4));

// PK-42 (UX-18) — satu pemformat tanggal WIB bersama (`utils/formatters`); dulu zona perangkat / bentuk sendiri.
const fmtDate = (s) => formatDate(s);

// Rekening koran Excel (.xlsx) dibaca server dengan template yang sama seperti CSV; dikirim base64.
const XLSX_MAX_BYTES = 5 * 1024 * 1024;
const isExcel = (name) => /\.xlsx$/i.test(name || "");
function toBase64(buf) {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

export default function ReconImportPanel({ accountId, formats, onDone, onClose }) {
  const [formatId, setFormatId] = useState("");
  const [raw, setRaw] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileB64, setFileB64] = useState("");   // berkas Excel terpilih (kosong = teks/CSV)
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const ready = !!fileB64 || !!raw.trim();

  const options = useMemo(() => ([
    { value: "", label: "Kenali otomatis dari isi berkas" },
    ...(formats || []).map((f) => ({
      value: f.id, label: `${f.name} · ${(f.file_kind || "").toUpperCase()}`,
    })),
  ]), [formats]);

  async function readFile(e) {
    const f = e.target.files?.[0];
    e.target.value = "";   // memilih berkas yang sama lagi tetap memicu pembacaan
    if (!f) return;
    setPreview(null); setErr("");
    if (/\.xls$/i.test(f.name)) {
      setErr("Berkas .xls (Excel 97–2003) belum bisa dibaca — buka di Excel lalu Simpan Sebagai 'Excel Workbook (.xlsx)'.");
      return;
    }
    setFileName(f.name);
    if (isExcel(f.name)) {
      if (f.size > XLSX_MAX_BYTES) {
        setErr("Berkas Excel lebih dari 5 MB — unduh rekening koran per periode yang lebih pendek.");
        setFileName("");
        return;
      }
      setFileB64(toBase64(await f.arrayBuffer()));
      setRaw("");
      return;
    }
    setFileB64("");
    setRaw(await f.text());
  }

  // Isi yang dikirim: berkas Excel (base64) ATAU teks (berkas CSV/MT940/OFX atau tempelan).
  const body = () => (fileB64 ? { file_b64: fileB64, raw: "" } : { raw });

  async function doPreview() {
    setBusy("preview"); setErr("");
    try {
      const r = await axios.post(`${API}/bank-reconciliation/preview`,
        { ...body(), format_id: formatId || "", year_hint: yearHint() });
      setPreview(r.data);
    } catch (e) { setErr(apiErrorText(e)); setPreview(null); } finally { setBusy(""); }
  }

  async function doImport() {
    setBusy("import"); setErr("");
    try {
      const r = await axios.post(`${API}/bank-reconciliation/import-file`,
        { bank_account_id: accountId, ...body(), format_id: formatId || "",
          year_hint: yearHint(), file_name: fileName || "" });   // M38 — asal mutasi tercatat
      const d = r.data || {};
      onDone(`Impor ${d.format_name || ""}: ${d.imported} baris baru, ${d.skipped} dilewati `
        + `(sudah pernah masuk)${d.error_count ? `, ${d.error_count} baris tidak terbaca` : ""}.${ringkasF1(d)}`);
      setRaw(""); setPreview(null); setFileName(""); setFileB64("");
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
            disabled={!ready || busy === "preview"} onClick={doPreview}>
            {busy === "preview" ? <RefreshCw size={14} className="spin" /> : <Eye size={14} />}
            Pratinjau
          </button>
          <button type="button" data-testid="recon-import-submit" className="primary-button"
            disabled={!ready || !accountId || busy === "import"} onClick={doImport}>
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
            <FileUp size={14} /> {fileName || "Pilih berkas (Excel · CSV · MT940 · OFX)"}
            <input data-testid="recon-file-input" type="file" className="hidden"
              accept=".xlsx,.xls,.csv,.txt,.sta,.mt940,.ofx,.qfx" onChange={readFile} />
          </label>
        </div>
      </div>
      {fileB64 ? (
        <p className="text-[12px] text-[#1C1C1E] rounded border border-[#E5E5EA] bg-[#F7F8FA] px-3 py-2"
          data-testid="recon-file-excel">
          Berkas Excel <b>{fileName}</b> dipilih — tekan <b>Pratinjau</b> untuk melihat baris yang terbaca.{" "}
          <button type="button" className="underline text-[#0058CC]" data-testid="recon-file-clear"
            onClick={() => { setFileB64(""); setFileName(""); setPreview(null); }}>Batal pilih</button>
        </p>
      ) : (<>
      <label className="block text-[11px] font-semibold text-[#6B6B73] mb-1">
        Atau tempel isi rekening koran di sini
      </label>
      <textarea data-testid="recon-raw" className="textarea font-mono text-[11px]" rows={5}
        placeholder={"Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo\n"
          + "12/07,TRSF E-BANKING CR PT MAJU JAYA SO-0007,0000,\"12.500.000,00\",CR,..."}
        value={raw} onChange={(e) => { setRaw(e.target.value); setPreview(null); }} />
      </>)}

      {preview && (
        <div className="mt-3" data-testid="recon-preview">
          <p className="text-[12px] text-[#1C1C1E] mb-1">
            Terbaca <b>{preview.total}</b> baris memakai template <b>{preview.format?.name}</b>
            {preview.detected ? " (dikenali otomatis)" : ""}
            {preview.source?.file_kind === "xlsx" && (
              <span data-testid="recon-preview-sheet">
                {" "}· lembar <b>{preview.source.sheet}</b>
                {preview.source.header_row ? `, judul kolom di baris ${preview.source.header_row}` : ""}
              </span>
            )} · masuk{" "}
            <b className="text-[#1B7F4B]">{formatCurrency(preview.sum_in)}</b> · keluar{" "}
            <b className="text-[#C0392B]">{formatCurrency(preview.sum_out)}</b>
          </p>
          {preview.error_count > 0 && (
            // Uji variasi isian (pelatihan 18 Nov) — dulu hanya contoh baris pertama; peserta tidak tahu baris mana lagi
            // yang dilewati. Kini setiap baris yang ditolak (≤ 10) disebut nomor & alasannya.
            <div className="text-[11px] text-[#B26A00] mb-1" data-testid="recon-preview-errors">
              <p className="flex items-center gap-1">
                <AlertTriangle size={12} /> {preview.error_count} baris tidak terbaca dan TIDAK akan diimpor:
              </p>
              <ul className="ml-5 list-disc">
                {(preview.errors || []).slice(0, 10).map((e, i) => (
                  <li key={`${e.row}-${i}`} data-testid={`recon-preview-error-${i}`}>
                    {e.row ? `Baris data ke-${e.row}` : "Judul kolom"}: {e.reason}
                  </li>
                ))}
              </ul>
              {preview.error_count > 10 && <p>… dan {preview.error_count - 10} baris lagi.</p>}
            </div>
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
