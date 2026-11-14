/**
 * ReturnGeneralLimits (KF-T2) — bagian "Batas retur umum" di Penjualan › Retur › Kebijakan Retur.
 *
 * Dulu panel "Asumsi retur" menulis `PUT /api/settings` langsung ke dokumen pengaturan (tanpa riwayat, alasan, jadwal,
 * dan tanpa lapisan per PT). Kini kartu Pusat Pengaturan yang DIKUNCI ke lima kunci `returns.*` — mesin yang sama dengan
 * Pengaturan (`useSettingsBrowser` + `SettingsBrowser`, pola Komisi & Insentif), bukan form kedua. Pelaku yang tidak
 * boleh membaca kunci itu (403, atau tidak satu pun kunci terbaca) melihat satu baris hanya-baca dari
 * `GET /api/settings/effective` (kunci `returns.*` dibuka untuk semua pengguna, `sensitif_baca=False`).
 */
import { useEffect, useState } from "react";
import { Info, SlidersHorizontal } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { SettingsBrowser, SettingsNotice, useSettingsBrowser } from "../settings/config/SettingsHub";

export const RETURN_LIMIT_GROUPS = ["retur"];
export const RETURN_LIMIT_KEYS = [
  "returns.customer_window_days", "returns.supplier_window_days", "returns.supplier_reminder_days",
  "returns.bill_first", "returns.grade_price_factors",
];

/** Baris hanya-baca bagi yang tidak membuka Pusat Pengaturan. */
function ReadOnlyLimits() {
  const [r, setR] = useState(null);
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/settings/effective`)
      .then((res) => { if (alive) setR(res.data?.returns || {}); })
      .catch(() => { if (alive) setR({}); });
    return () => { alive = false; };
  }, []);
  if (!r || r.customer_window_days == null || r.supplier_window_days == null) return null;
  return (
    <p className="flex items-start gap-2 text-fs-13 text-kn-neutral" data-testid="return-limits-readonly">
      <Info size={14} className="mt-0.5 shrink-0 text-kn-action" />
      <span>
        Batas retur umum: pelanggan {r.customer_window_days} hari sejak surat jalan · pemasok {r.supplier_window_days} hari
        sejak barang diterima.
      </span>
    </p>
  );
}

export default function ReturnGeneralLimits({ selectedEntity, entities = [] }) {
  const s = useSettingsBrowser({ selectedEntity, groupIds: RETURN_LIMIT_GROUPS, includeKeys: RETURN_LIMIT_KEYS });
  const readOnly = !!s.denied || (!s.loading && !s.error && s.groups.length === 0);
  return (
    <section className="section-card mb-4" data-testid="return-general-limits">
      <div className="section-head">
        <div className="flex items-center gap-2"><SlidersHorizontal size={14} className="text-kn-action" /><h2>Batas retur umum</h2></div>
      </div>
      <div className="section-body cfg-hub cfg-group-view">
        {readOnly ? <ReadOnlyLimits /> : (
          <>
            <p className="cfg-group-intro">
              Batas pelanggan dihitung dari tanggal surat jalan, batas pemasok dari tanggal roll diterima gudang —
              keduanya terpisah. Batas dinilai pada tanggal pengajuan (pelanggan) dan tanggal klaim dikirim (pemasok).
              Hangtag hilang atau kain dipotong hanya dicatat sebagai daftar periksa dan peringatan; Finance memutus saat
              penyelesaian. Kebijakan di daftar bawah boleh menimpa batas pelanggan ini. Setiap perubahan tercatat di
              riwayat dan bisa dibuat khusus per PT.
            </p>
            <SettingsNotice s={s} />
            <SettingsBrowser s={s} entities={entities} groupNav="chips" searchPlaceholder="Cari batas retur…" />
          </>
        )}
      </div>
    </section>
  );
}
