/**
 * ZeroCostRollsSection (PK-27 · IV-07) — "Roll berbiaya 0" di tab rekonsiliasi persediaan.
 * Roll yang masih di gudang tanpa biaya (nilai persediaan 0) dan roll berbiaya 0 yang sudah terkirim (HPP surat jalan 0).
 * Alat menemukan data biaya yang perlu dikoreksi; layar ini hanya membaca. Roll yang sudah dihapus-buku (scrap) tidak
 * muncul karena memang bernilai 0.
 * Sumber: GET /api/gl/zero-cost-rolls?page&page_size (PT dari konteks; "Semua PT" = PT dalam cakupan pengguna).
 * Tiga keadaan dibedakan: memuat · galat (kotak merah + Coba lagi) · kosong (hanya sesudah muat berhasil).
 */
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, CircleSlash, Package, PauseCircle, Truck, XCircle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityBadge from "../../components/EntityBadge";
import ErrorNotice from "../../components/ErrorNotice";
import KNPager from "../../components/KNPager";
import { SearchBox } from "../../components/ListPageParts";
import { apiErrorText } from "../../utils/apiError";
import { docStatusLabel } from "../../utils/docStatus";
import { formatDate, formatQty } from "../../utils/formatters";

const PAGE_SIZE = 50;
export const TEKS_MEMUAT = "Memuat roll berbiaya 0…";
export const TEKS_KOSONG = "Tidak ada roll berbiaya 0.";
export const TEKS_GALAT = "Daftar roll berbiaya 0 tidak bisa dimuat.";
/** Status roll persediaan yang belum ada di peta label bersama. */
const LABEL_ROLL = { wip: "Dalam proses", blocked: "Diblokir", damaged: "Rusak",
  in_transit_transfer: "Dalam transfer gudang" };
const NADA_ROLL = {
  available: ["pill-success", CheckCircle2],
  reserved: ["pill-info", Package], committed: ["pill-info", Package], picked: ["pill-info", Package],
  packed: ["pill-info", Package], wip: ["pill-info", Package], in_transit_transfer: ["pill-info", Truck],
  quarantine: ["pill-warning", PauseCircle], hold: ["pill-warning", PauseCircle],
  blocked: ["pill-warning", PauseCircle], damaged: ["pill-danger", XCircle],
};

function RollStatus({ status }) {
  const [tone, Icon] = NADA_ROLL[status] || ["pill-muted", CircleSlash];
  return (
    <span className={`status-pill ${tone} inline-flex items-center gap-1 whitespace-nowrap`}>
      <Icon size={12} aria-hidden="true" />{docStatusLabel(status, LABEL_ROLL)}
    </span>
  );
}

const KOSONG = { in_stock: { items: [], total: 0 }, shipped: { items: [], total: 0 } };

export default function ZeroCostRollsSection({ refreshKey }) {
  const [stok, setStok] = useState(KOSONG.in_stock);
  const [kirim, setKirim] = useState(KOSONG.shipped);
  const [pageStok, setPageStok] = useState(1);
  const [pageKirim, setPageKirim] = useState(1);
  const [state, setState] = useState("loading");   // loading | error | ready
  const [err, setErr] = useState("");
  // Cek layar 15 Nov (KN_37 butir cari) — daftar bisa puluhan baris: cari nomor roll / barang / surat jalan di server.
  const [cari, setCari] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => { setQ(cari.trim()); setPageStok(1); setPageKirim(1); }, 300);
    return () => clearTimeout(t);
  }, [cari]);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const ambil = (page) => axios.get(`${API}/gl/zero-cost-rolls`, { params: { page, page_size: PAGE_SIZE, ...(q ? { q } : {}) } });
      const a = await ambil(pageStok);
      const b = pageKirim === pageStok ? a : await ambil(pageKirim);
      setStok(a.data?.in_stock || KOSONG.in_stock);
      setKirim(b.data?.shipped || KOSONG.shipped);
      setErr("");
      setState("ready");
    } catch (e) {
      setErr(apiErrorText(e) || "");
      setState("error");
    }
  }, [pageStok, pageKirim, q]);
  useEffect(() => { load(); }, [load, refreshKey]);

  const kosongSemua = state === "ready" && !stok.total && !kirim.total && !q;
  return (
    // Bagian di dalam kartu Jurnal & Buku Besar (sejajar "True-up terakhir"): garis pemisah, bukan kartu bersarang.
    <div className="mt-4 border-t border-kn-divider pt-3" data-testid="zero-cost-rolls">
      <h3 className="mb-1.5 text-fs-14 font-bold text-kn-text" data-testid="zc-title">Roll berbiaya 0</h3>
      <div className="space-y-3">
        <p className="text-fs-12 text-kn-text-2" data-testid="zc-keterangan">
          Roll tanpa biaya tidak menambah nilai persediaan dan keluar dengan HPP 0, jadi laba kotor terlihat lebih
          tinggi sampai biayanya diperbaiki. Roll yang sudah dihapus-buku (scrap) tidak ditampilkan.
        </p>
        {(q || stok.total + kirim.total > 0) && (
          <SearchBox value={cari} onChange={setCari} placeholder="Cari nomor roll, barang, atau surat jalan…" testId="zc-search" />
        )}
        {state === "loading" && (
          <p className="text-fs-13 text-kn-text-2" role="status" data-testid="zc-loading">{TEKS_MEMUAT}</p>
        )}
        {state === "error" && (
          <ErrorNotice testId="zc-error" message={`${TEKS_GALAT} ${err}`.trim()} onRetry={load} />
        )}
        {kosongSemua && (
          <p className="text-fs-13 text-kn-text-2" data-testid="zc-empty">{TEKS_KOSONG}</p>
        )}
        {state === "ready" && !kosongSemua && (
          <>
            <div data-testid="zc-stock">
              <p className="mb-1 text-fs-12 font-semibold text-kn-text" data-testid="zc-stock-title">
                Masih di gudang · {stok.total} roll</p>
              {stok.total === 0 ? (
                <p className="text-fs-12 text-kn-text-2" data-testid="zc-stock-none">Semua roll di gudang sudah berbiaya.</p>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="data-table head-wrap w-full text-fs-12" data-testid="zc-stock-table">
                      <thead>
                        <tr><th>Roll</th><th>Barang</th><th>PT</th><th className="text-right">Sisa</th><th>Status</th></tr>
                      </thead>
                      <tbody>
                        {stok.items.map((r) => (
                          <tr key={r.roll_id} data-testid={`zc-stock-row-${r.roll_id}`}>
                            <td className="font-mono whitespace-nowrap">{r.roll_no || "—"}</td>
                            <td className="max-w-[260px] break-words">{r.product_name || "—"}</td>
                            <td>{r.entity_id ? <EntityBadge entityId={r.entity_id} /> : "—"}</td>
                            <td className="whitespace-nowrap text-right tabular-nums">{formatQty(r.length_remaining)}</td>
                            <td><RollStatus status={r.status} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <KNPager page={pageStok} pageSize={PAGE_SIZE} total={stok.total} onChange={setPageStok}
                    testId="zc-stock-pager" />
                </>
              )}
            </div>
            <div data-testid="zc-shipped">
              <p className="mb-1 text-fs-12 font-semibold text-kn-text" data-testid="zc-shipped-title">
                Sudah terkirim · {kirim.total} roll</p>
              {kirim.total === 0 ? (
                <p className="text-fs-12 text-kn-text-2" data-testid="zc-shipped-none">Tidak ada surat jalan dengan roll berbiaya 0.</p>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="data-table head-wrap w-full text-fs-12" data-testid="zc-shipped-table">
                      <thead>
                        <tr><th>Surat Jalan</th><th>Pesanan</th><th>Roll</th><th className="text-right">Panjang</th>
                          <th>Tanggal</th></tr>
                      </thead>
                      <tbody>
                        {kirim.items.map((s, i) => (
                          <tr key={`${s.shipment_no}-${s.roll_no}-${i}`} data-testid={`zc-shipped-row-${i}`}>
                            <td className="font-mono whitespace-nowrap">{s.shipment_no || "—"}</td>
                            <td className="font-mono whitespace-nowrap">{s.order_number || "—"}</td>
                            <td className="font-mono whitespace-nowrap">{s.roll_no || "—"}</td>
                            <td className="whitespace-nowrap text-right tabular-nums">{formatQty(s.length)}</td>
                            <td className="whitespace-nowrap">{formatDate(s.shipped_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <KNPager page={pageKirim} pageSize={PAGE_SIZE} total={kirim.total} onChange={setPageKirim}
                    testId="zc-shipped-pager" />
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
