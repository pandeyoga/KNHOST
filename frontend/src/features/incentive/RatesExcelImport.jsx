/**
 * RatesExcelImport — KA-9 · pop-up "Unggah Excel" tarif komisi tab Skema & Tarif (rancangan komisi per artikel §6.6).
 *
 * Alur: pilih berkas `.xlsx` hasil "Unduh Excel" → `POST /api/incentive-rates/import/preview` (multipart `file` +
 * `entity_id`; tidak menulis apa pun) → pratinjau per baris berstatus Baru · Diubah · Sama · Galat (nomor baris Excel,
 * tarif lama → baru, batas margin, pesan server) → "Terapkan n perubahan" meminta alasan (`askReason`) →
 * `POST /api/incentive-rates/import/apply` dengan baris Baru/Diubah saja, masing-masing membawa `baris` (nomor baris
 * Excel) supaya pesan galat server menyebut baris yang sama. Ada baris Galat → Terapkan mati dengan alasan tertulis.
 */
import { useMemo, useState } from "react";
import { FileSpreadsheet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import StatusBadge from "../../components/StatusBadge";
import { askReason } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";

export const TEKS_ADA_GALAT = "Perbaiki baris bergalat di Excel lalu unggah ulang.";
const STATUS = {
  baru: { label: "Baru", tone: "info", icon: "dot" },
  ubah: { label: "Diubah", tone: "warning", icon: "check" },
  sama: { label: "Sama", tone: "neutral", icon: "circle" },
  galat: { label: "Galat", tone: "danger", icon: "alert" },
};
const TAMPIL = [
  { value: "berubah", label: "Yang berubah & galat" },
  { value: "semua", label: "Semua baris" },
  { value: "galat", label: "Galat saja" },
];

/** Hitungan per status: { baru, ubah, sama, galat }. */
export function hitungStatus(rows) {
  const n = { baru: 0, ubah: 0, sama: 0, galat: 0 };
  (rows || []).forEach((r) => { n[r.status] = (n[r.status] || 0) + 1; });
  return n;
}

/** Baris untuk `import/apply`: hanya Baru/Diubah, sasaran (artikel ATAU varian) + nomor baris Excel. */
export function barisTerap(rows) {
  return (rows || []).filter((r) => r.status === "baru" || r.status === "ubah").map((r) => ({
    baris: r.baris, ...(r.product_id ? { product_id: r.product_id } : { template_id: r.template_id }),
    per_unit_amount: r.baru, margin_cap_pct: r.baru_batas ?? null,
  }));
}

const rp = (v) => (v === null || v === undefined ? "—" : formatCurrency(v));
const pct = (v) => (v === null || v === undefined ? "" : `${String(v).replace(".", ",")} %`);

export default function RatesExcelImport({ entityId, pt, onClose, onApplied }) {
  const [rows, setRows] = useState(null);
  const [nama, setNama] = useState("");
  const [tampil, setTampil] = useState("berubah");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const n = hitungStatus(rows);
  const terap = useMemo(() => barisTerap(rows), [rows]);
  const lihat = (rows || []).filter((r) => tampil === "semua" || (tampil === "galat" ? r.status === "galat" : r.status !== "sama"));

  const pilih = async (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    setNama(f.name); setRows(null); setErr(""); setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("entity_id", entityId);
      const r = await axios.post(`${API}/incentive-rates/import/preview`, fd);
      setRows(r.data?.rows || []);
    } catch (ex) { setErr(apiErrorText(ex) || "Berkas tidak bisa dibaca."); } finally { setBusy(false); }
  };

  const terapkan = async () => {
    const reason = await askReason({
      title: `Terapkan ${terap.length} perubahan tarif?`,
      message: `${n.baru} tarif baru dan ${n.ubah} tarif diubah untuk ${pt}. Tarif berlaku untuk pesanan yang dibuat sesudah disimpan.`,
      reasonLabel: "Alasan perubahan", confirmLabel: "Terapkan", testId: "rates-import-confirm",
    });
    if (reason === null) return;
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/incentive-rates/import/apply`, { entity_id: entityId, rows: terap, reason });
      await onApplied(r.data || {});
    } catch (ex) { setErr(apiErrorText(ex) || "Perubahan gagal diterapkan."); } finally { setBusy(false); }
  };

  const alasanMati = !rows ? "Pilih berkas Excel hasil Unduh Excel." : n.galat ? TEKS_ADA_GALAT
    : terap.length === 0 ? "Tidak ada tarif yang berubah." : "";
  const footer = (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {alasanMati && <span className="mr-auto text-fs-12 text-kn-text-2" data-testid="rates-import-why">{alasanMati}</span>}
      <button type="button" className="secondary-button" data-testid="rates-import-cancel" disabled={busy} onClick={onClose}>Batal</button>
      <button type="button" className="primary-button" data-testid="rates-import-apply" disabled={!!alasanMati || busy}
        onClick={terapkan}>{`Terapkan ${terap.length} perubahan`}</button>
    </div>
  );

  return (
    <FormModal open onClose={onClose} testId="rates-import" icon={FileSpreadsheet} size="lg" title="Unggah Excel tarif komisi"
      subtitle={pt} footer={footer} busy={busy} error={err}>
      <div className="space-y-3">
        <div>
          <label className="field-label" htmlFor="rates-import-file">Berkas Excel (.xlsx) hasil Unduh Excel</label>
          <input id="rates-import-file" type="file" accept=".xlsx" className="field" data-testid="rates-import-file" onChange={pilih} disabled={busy} />
          <p className="mt-1 text-fs-12 text-kn-text-2">Ubah kolom tarif atau batas margin; jangan ubah kolom ID artikel dan ID varian. Sel tarif kosong = baris tidak diubah.</p>
        </div>
        {busy && !rows && <p className="text-fs-13 text-kn-text-2" role="status" data-testid="rates-import-loading">Membaca {nama}…</p>}
        {rows && (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-fs-13 font-semibold text-kn-text" data-testid="rates-import-summary">
                {`${n.baru} baru · ${n.ubah} diubah · ${n.sama} sama · ${n.galat} galat`}</span>
              <div className="ml-auto w-[200px]"><KNSelect data-testid="rates-import-filter" className="field" value={tampil}
                options={TAMPIL} onValueChange={(v) => v && setTampil(v)} /></div>
            </div>
            {!busy && lihat.length === 0 ? (
              <p className="text-fs-13 text-kn-text-2" data-testid="rates-import-empty">Tidak ada baris untuk tampilan ini.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table head-wrap w-full" data-testid="rates-import-table">
                  <thead><tr><th>Baris</th><th>Artikel / varian</th><th className="text-right">Tarif lama</th>
                    <th className="text-right">Tarif baru</th><th>Status</th><th>Keterangan</th></tr></thead>
                  <tbody>
                    {lihat.map((r) => {
                      const st = STATUS[r.status] || STATUS.galat;
                      return (
                        <tr key={r.baris} data-testid={`rates-import-row-${r.baris}`}>
                          <td className="tabular-nums">{r.baris}</td>
                          <td className="min-w-[160px] break-words"><span className="block">{r.nama || "—"}</span>
                            <span className="block font-mono text-fs-12 text-kn-text-2">{r.kode_varian || r.kode_artikel}</span></td>
                          <td className="whitespace-nowrap text-right tabular-nums">{rp(r.lama)}
                            {r.lama_batas !== null && r.lama_batas !== undefined && <span className="block text-fs-12 text-kn-text-2">batas {pct(r.lama_batas)}</span>}</td>
                          <td className="whitespace-nowrap text-right tabular-nums">{rp(r.baru)}
                            {r.baru_batas !== null && r.baru_batas !== undefined && <span className="block text-fs-12 text-kn-text-2">batas {pct(r.baru_batas)}</span>}</td>
                          <td><StatusBadge tone={st.tone} icon={st.icon} label={st.label} testId={`rates-import-status-${r.baris}`} /></td>
                          <td className="min-w-[160px] break-words text-fs-12 text-kn-text-2">{r.pesan}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </FormModal>
  );
}
