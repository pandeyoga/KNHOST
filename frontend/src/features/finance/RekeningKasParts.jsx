/**
 * RekeningKasParts — Kas & Bank bagian 3 (Tugas 4a): bagian kartu rekening di Rekening & Saldo untuk jenis kas, dana
 * tetap, lokasi, dan aksi kartu (rancangan §5.4: "kartu rekening menampilkan jenis, dana tetap, lokasi; aksi Isi ulang
 * di rekening kas kecil berdana tetap").
 *
 * Aksi kartu berada di KAKI kartu, di luar tombol kartu (tombol di dalam tombol = HTML tidak sah; klik aksi tidak membuka
 * buku rekening). SATU kaki per kartu untuk semua aksi (Isi ulang dari 4a + Opname dari 4b — tinjauan akhir Minor 1).
 * Izin, bukan nama peran: Isi ulang = `cash.create` (`jenisKas.bolehIsiUlang`); alasan server lain (isi ulang terbuka,
 * tidak perlu) tampil di pop-up Isi ulang yang menonaktifkan tombol kirimnya. Opname = `cash.create` + rekening tunai
 * aktif + layar Opname Kas bisa dibuka (`cashcount/OpnameKartuAksi`).
 */
import { RefreshCcw } from "lucide-react";
import StatusBadge from "../../components/StatusBadge";
import { useAppNav } from "../../context/AppNavContext";
import { formatCurrency } from "../../utils/formatters";
import OpnameKartuAksi, { tampilOpname } from "./cashcount/OpnameKartuAksi";
import { bolehIsiUlang, jenisKasRekening, labelJenisKas, pakaiDanaTetap } from "./jenisKas";

/** Lencana jenis kas: rekening tunai selalu (kas kasir / kas kecil / kas besar), rekening bank hanya bila berjenis kas
 *  kecil (data lama yang janggal — ditulis terang, seperti dulu). */
export function JenisKasPill({ a }) {
  const ct = jenisKasRekening(a);
  if (a?.account_type === "bank" && ct !== "kas_kecil") return null;
  return (
    <span className="mt-0.5 block">
      <StatusBadge tone="info" icon="tag" label={labelJenisKas(ct)} testId={`bank-cash-type-${a.id}`} />
    </span>
  );
}

/** Dana tetap (kas kecil berdana tetap) dan lokasi kerja (bila ada). */
export function RekeningKasInfo({ a }) {
  const dana = pakaiDanaTetap(a);
  const lokasi = a?.location_id ? a.location_name || "lokasi tidak dikenal" : "";
  if (!dana && !lokasi) return null;
  return (
    <>
      {dana && (
        <p className="text-fs-12 text-kn-text-2" data-testid={`bank-dana-tetap-${a.id}`}>
          Dana tetap <b className="tabular-nums">{formatCurrency(a.dana_tetap)}</b>
        </p>
      )}
      {lokasi && (
        <p className="text-fs-12 text-kn-text-2 truncate" data-testid={`bank-location-${a.id}`} title={lokasi}>
          Lokasi <b>{lokasi}</b>
        </p>
      )}
    </>
  );
}

/** Kaki kartu rekening: SEMUA aksi per rekening (Isi ulang, Opname) dalam satu kaki ber-testid unik. Tanpa aksi → tidak
 *  dirender (kartu tetap satu tombol). Opname paling kanan supaya letaknya sama di setiap kartu tunai. */
export function RekeningKartuAksi({ a, perms, onIsiUlang }) {
  const { canOpen } = useAppNav();
  const isiUlang = bolehIsiUlang(a, perms) && typeof onIsiUlang === "function";
  const opname = tampilOpname(a, perms, canOpen);
  if (!isiUlang && !opname) return null;
  return (
    <div className="flex flex-wrap items-center justify-end gap-2 border-t border-kn-divider px-3.5 py-2"
      data-testid={`bank-card-actions-${a.id}`}>
      {isiUlang && (
        <button type="button" className="secondary-button btn-sm" data-testid={`bank-refill-${a.id}`}
          onClick={() => onIsiUlang(a)}>
          <RefreshCcw size={13} aria-hidden="true" /> Isi ulang
        </button>
      )}
      {opname && <OpnameKartuAksi a={a} perms={perms} />}
    </div>
  );
}
