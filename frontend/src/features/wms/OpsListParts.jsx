/**
 * Pola UI gelombang Gudang (pemilik 16 Nov — M26; `docs/blueprint/04_POLA_UI.md` §2.A): SATU pola untuk tab Operasi
 * Gudang Barang Masuk · Barang Keluar · Cutting. Dulu tiap tab punya bentuknya sendiri (Barang Masuk: cari + chip status
 * + ruang kosong; Barang Keluar: chip status + cari + chip jenis + dropdown gudang + daftar kiri/panel kosong kanan;
 * Cutting: kotak cari buatan + chip tahap + kartu buka-tutup + dropdown gudang kedua).
 *
 * Kini sama di ketiganya:
 *   bilah daftar (`ListToolbar`)  Cari → Status ▾ → Jenis ▾ (bila ada) → Gudang ▾ → jumlah · [aksi di kanan]
 *   daftar (`OpsList` + `OpsRow`) kartu berbaris selebar layar: nomor · keterangan · kemajuan · status
 *   rincian (`OpsSplit`)         panel kanan; daftar menyempit jadi kolom kiri HANYA saat ada baris yang dibuka
 *   keadaan daftar               `EmptyState` (memuat · kosong · saringan · galat · tanpa akses) di dalam kartu daftar
 */
import { ChevronRight } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import "./opsList.css";

/** Kelas dropdown bilah daftar — sama dengan pilot Retur (`SalesReturns.jsx`). */
export const OPS_SELECT_CLASS = "!h-auto !w-auto rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13";

/** Dropdown saringan (Status ▾ · Jenis ▾ · Gudang ▾). Daftar pendek = pilihan biasa; gudang banyak = bisa dicari. */
export function OpsSelect({ testId, label, value, onChange, options, width = "min-w-[150px]", searchable = false }) {
  return (
    <KNSelect data-testid={testId} aria-label={label} value={value} onValueChange={(v) => onChange(v ?? "")}
      className={`${OPS_SELECT_CLASS} ${width}`} options={options} searchable={searchable} />
  );
}

/** Pilihan "Gudang ▾" dari baris yang termuat (id → nama), urut nama. Nilai terpilih yang hilang dari daftar tetap
 *  ditawarkan supaya dropdown tidak menampilkan "(tidak ada di daftar)" sesudah saringan lain berubah. */
export function warehouseOptions(rows, selected = "") {
  const names = new Map();
  (rows || []).forEach((r) => {
    if (r.warehouse_id && !names.has(r.warehouse_id)) names.set(r.warehouse_id, r.warehouse_name || "Gudang tanpa nama");
  });
  if (selected && !names.has(selected)) names.set(selected, "Gudang terpilih (tidak ada di daftar ini)");
  const list = [...names].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label, "id"));
  return [{ value: "", label: "Semua gudang" }, ...list];
}

/** Jumlah hasil di bilah daftar (testid lama tiap layar dipertahankan). */
export function OpsCount({ testId, children }) {
  return <span className="whitespace-nowrap text-fs-12 text-kn-text-2" data-testid={testId}>{children}</span>;
}

/** Daftar + panel rincian. `open` = ada baris yang dibuka → daftar jadi kolom kiri (≥ 1024 px), panel di kanan. */
export function OpsSplit({ open = false, testId, children }) {
  return <div className={`kn-ops-split${open ? " is-open" : ""}`} data-testid={testId}>{children}</div>;
}

/** Kartu daftar berbaris; `footer` = catatan batas muat ("Muat berikutnya"). */
export function OpsList({ testId, footer, children }) {
  return (
    <div className="kn-ops-list" data-testid={testId}>
      <div className="kn-ops-rows">{children}</div>
      {footer}
    </div>
  );
}

/**
 * Satu baris daftar: `title` (nomor + lencana) · `lines` (keterangan, baris pertama paling penting) · `aside`
 * (kemajuan/waktu) · `status` (StatusBadge). Seluruh baris = satu tombol pembuka rincian (`testId`); `action` = tombol
 * aksi baris di luar area klik (mis. "Potong semua"); `wrapperTestId` = penanda seluruh baris.
 */
export function OpsRow({ testId, wrapperTestId, selected = false, onOpen, title, status, lines = [], aside, action }) {
  return (
    <div className={`kn-ops-row${selected ? " is-selected" : ""}`} data-testid={wrapperTestId}>
      <button type="button" className="kn-ops-row-main" data-testid={testId} onClick={onOpen}
        aria-current={selected ? "true" : undefined}>
        <span className="kn-ops-row-head">
          <span className="kn-ops-row-title">{title}</span>
          <span className="kn-ops-row-status">{status}<ChevronRight size={14} aria-hidden="true" /></span>
        </span>
        <span className="kn-ops-row-lines">
          {lines.filter(Boolean).map((l, i) => <span key={i}>{l}</span>)}
        </span>
        {aside ? <span className="kn-ops-row-aside">{aside}</span> : null}
      </button>
      {action ? <span className="kn-ops-row-action">{action}</span> : null}
    </div>
  );
}
