/**
 * GroupRatesList — KA-9 (keputusan R15) · daftar **tarif Semua PT** tab Skema & Tarif saat kepala aplikasi di mode
 * "Semua PT".
 *
 * Rute pohon tarif (`GET /api/incentive-rates/categories|articles|…`) bekerja per satu PT dan menolak "Semua PT", jadi
 * di mode ini yang tampil hanya baris tarif tingkat grup (`entity_id = "all"`, dari `GET /api/incentive-rates?entity_id=all`;
 * tarif milik PT tertentu tidak tampil). Tiap baris bisa diubah lewat pop-up tarif yang sama (`RateFormModal`, lingkup
 * terkunci "Semua PT" → `PATCH /api/incentive-rates/{id}`; rute tingkat grup, lolos pagar tulis mode gabungan) dan dihapus
 * beralasan. Membuat tarif Semua PT baru dilakukan dari satu PT (pop-up "Berlaku untuk: Semua PT"). Izin: ubah
 * `sales_force.update`, hapus `sales_force.delete`, riwayat `audit.view`.
 * Tinjauan akhir M3 — ubah/hapus tarif Semua PT hanya untuk peran lintas PT (`bolehUbahGrup` = `caps.global_write`; server
 * menolak 403 berkalimat); M6 — konfirmasi hapus menyebut tingkat pengganti per tingkat.
 */
import { useCallback, useEffect, useState } from "react";
import { History, Pencil, Trash2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import AuditHistoryPanel from "../../components/AuditHistoryPanel";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import StatusBadge from "../../components/StatusBadge";
import { askReason } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";
import { canCurrent } from "../../config/roles";
import RateFormModal from "./RateFormModal";

const TINGKAT_LABEL = { kategori: "Kategori", artikel: "Artikel", varian: "Varian" };

/** Tingkat, nama tampil, kode, dan sebutan (varian = kodenya, seperti di pohon) satu dokumen tarif. */
export function sasaranTarif(d) {
  const tingkat = d.product_id ? "varian" : d.template_id ? "artikel" : "kategori";
  const nama = tingkat === "kategori" ? d.category : (d.target_name || d.target_code || d.category || "—");
  const kode = tingkat === "kategori" ? "" : (d.target_code || "");
  return { tingkat, nama, kode, sebutan: tingkat === "varian" ? (kode || nama) : nama };
}

export const TEKS_GRUP_TARIF_TERKUNCI = "Tarif Semua PT hanya dapat diubah peran lintas PT.";

/** M6 — akibat menghapus tarif Semua PT di satu tingkat (untuk PT yang tidak punya tarif sendiri di tingkat itu). */
export function akibatHapusGrup(tingkat) {
  return tingkat === "kategori" ? "Sesudah dihapus, PT itu tidak mendapat komisi untuk kategori ini."
    : tingkat === "artikel" ? "Sesudah dihapus, PT itu memakai tarif kategori artikel ini (tarif PT itu sendiri atau Semua PT)."
      : "Sesudah dihapus, PT itu memakai tarif artikelnya, atau tarif kategori bila artikelnya tidak bertarif.";
}

export default function GroupRatesList({ bawaanBatas, bolehUbahGrup = true, dasarHarga = "" }) {
  const boleh = bolehUbahGrup === true;                     // null = kemampuan belum termuat → tombol belum tampil
  const canUpdate = canCurrent("sales_force", "update") && boleh;
  const canDelete = canCurrent("sales_force", "delete") && boleh;
  const canAudit = canCurrent("audit", "view");
  const [rows, setRows] = useState([]);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [aksiErr, setAksiErr] = useState("");
  const [notice, setNotice] = useState("");
  const [sasaran, setSasaran] = useState(null);
  const [riwayat, setRiwayat] = useState(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/incentive-rates`, { params: { entity_id: "all" } });
      setRows((Array.isArray(r.data) ? r.data : []).filter((d) => d.entity_id === "all"));
      setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const buka = (d) => {
    const t = sasaranTarif(d);
    setSasaran({ tingkat: t.tingkat, nama: t.sebutan, category: d.category, template_id: d.template_id,
      product_id: d.product_id, adaDiTingkat: true,
      rate: { per_unit_amount: d.per_unit_amount, margin_cap_pct: d.margin_cap_pct, rate_id: d.id, asal_tingkat: t.tingkat,
        asal_lingkup: "semua_pt" } });
  };
  const hapus = async (d) => {
    const t = sasaranTarif(d);
    const reason = await askReason({ title: `Hapus tarif Semua PT ${t.sebutan}?`,
      message: `Tarif ini berlaku untuk semua PT yang tidak punya tarif sendiri di tingkat ini. ${akibatHapusGrup(t.tingkat)} `
        + "Berlaku untuk pesanan yang dibuat sesudah dihapus.",
      reasonLabel: "Alasan penghapusan", confirmLabel: "Hapus tarif", danger: true, testId: "group-rates-delete-confirm" });
    if (reason === null) return;
    try {
      await axios.delete(`${API}/incentive-rates/${d.id}`, { params: { reason } });
      setNotice(`Tarif Semua PT ${t.sebutan} dihapus.`); setAksiErr("");
      await load();
    } catch (e) { setAksiErr(apiErrorText(e) || "Tarif gagal dihapus."); }
  };

  return (
    <div className="space-y-2" data-testid="group-rates">
      {!canCurrent("sales_force", "update") ? <p className="text-fs-12 text-kn-text-2" data-testid="group-rates-why">Mengubah tarif komisi butuh akses Ubah di modul Pengawasan Tim Sales & Kredit.</p>
        : bolehUbahGrup === false && <p className="text-fs-12 text-kn-text-2" data-testid="group-rates-locked">{TEKS_GRUP_TARIF_TERKUNCI}</p>}
      {notice && <div className="notice-bar success" data-testid="group-rates-notice"><span className="text-fs-12">{notice}</span></div>}
      {aksiErr && <ErrorNotice testId="group-rates-error" message={aksiErr} onDismiss={() => setAksiErr("")} />}
      {state === "loading" ? (
        <p className="text-fs-13 text-kn-text-2" role="status" data-testid="group-rates-loading">Memuat tarif Semua PT…</p>
      ) : state === "error" ? (
        <ErrorNotice testId="group-rates-load-error" message={`Tarif Semua PT tidak bisa dimuat. ${err}`.trim()} onRetry={load} />
      ) : rows.length === 0 && state === "ready" ? (
        <p className="text-fs-13 text-kn-text-2" data-testid="group-rates-empty">Belum ada tarif Semua PT. Buat dari satu PT lewat pop-up tarif (Berlaku untuk: Semua PT).</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table head-wrap w-full" data-testid="group-rates-table">
            <thead><tr><th>Tingkat</th><th>Kategori / artikel / varian</th><th className="text-right">Tarif per satuan dasar</th>
              <th className="text-right">Batas margin</th><th className="col-sticky-end"><span className="sr-only">Aksi</span></th></tr></thead>
            <tbody>
              {rows.map((d) => {
                const t = sasaranTarif(d);
                return (
                  <tr key={d.id} data-testid={`group-rates-row-${d.id}`}>
                    <td className="whitespace-nowrap">{TINGKAT_LABEL[t.tingkat]}
                      {d.status !== "active" && <StatusBadge tone="neutral" label="Nonaktif" className="ml-1" />}</td>
                    <td className="min-w-[160px] break-words"><span className="block font-semibold">{t.nama}</span>
                      <span className="block text-fs-12 text-kn-text-2">{[t.kode, t.tingkat === "kategori" ? "" : d.category].filter(Boolean).join(" · ")}</span></td>
                    <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(d.per_unit_amount)}</td>
                    <td className="text-right tabular-nums">{Number(d.margin_cap_pct || 0) > 0 ? `${String(d.margin_cap_pct).replace(".", ",")} %` : "tidak dibatasi"}</td>
                    <td className="col-sticky-end text-right">
                      <div className="flex items-center justify-end gap-1">
                        {canUpdate && <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`group-rates-edit-${d.id}`}
                          onClick={() => buka(d)}><Pencil size={12} aria-hidden="true" />Ubah</button>}
                        {canDelete && <button type="button" className="secondary-button btn-sm whitespace-nowrap text-kn-danger-text" data-testid={`group-rates-delete-${d.id}`}
                          onClick={() => hapus(d)}><Trash2 size={12} aria-hidden="true" />Hapus tarif</button>}
                        {canAudit && <button type="button" className="icon-button" aria-label={`Riwayat tarif ${t.sebutan}`} data-testid={`group-rates-history-${d.id}`}
                          onClick={() => setRiwayat({ id: d.id, nama: t.sebutan })}><History size={13} /></button>}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <RateFormModal sasaran={sasaran} entityId="all" pt="Semua PT" bawaanBatas={bawaanBatas} semuaPtSaja dasarHarga={dasarHarga}
        onClose={() => setSasaran(null)} onSaved={async (pesan) => { setSasaran(null); setNotice(pesan); await load(); }} />
      {riwayat && (
        <FormModal open onClose={() => setRiwayat(null)} testId="group-rates-history" icon={History} size="lg" title={`Riwayat tarif ${riwayat.nama}`} subtitle="Semua PT">
          <AuditHistoryPanel entityType="incentive_rate" entityId={riwayat.id} testIdPrefix="group-rates-history-list" />
        </FormModal>
      )}
    </div>
  );
}
