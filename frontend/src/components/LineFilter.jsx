/**
 * LineFilter (FASE L) — PENYARING **LINI PRODUK** (dropdown sejak pola UI 16 Nov) untuk 12 layar.
 *
 * KENAPA SATU KOMPONEN
 * Lini (woven · knit · printing · lini baru berikutnya) muncul di Pesanan,
 * Pesanan Pembelian, PR, Roll, Transfer, Retur ×2, Makloon, Sample, Spesifikasi,
 * Desain, dan Master Produk. Kalau tiap layar membuat bilah filternya sendiri,
 * lini ke-4 yang ditambah pemilik akan muncul di sebagian layar saja — persis
 * kelas "dua daftar untuk satu fakta" yang paling mahal di repo ini.
 *
 * TIGA KEPUTUSAN YANG DISENGAJA
 * 1. **Nilai chip datang dari MASTER**, bukan hardcode: `useDomainEnums()` →
 *    `product_line` yang isinya di-overlay `services/master_registry.py` dari
 *    koleksi `product_lines`. Menambah lini di Pengaturan → Master → Lini Produk
 *    langsung terasa di sini tanpa satu baris kode pun berubah (POC L1).
 * 2. **Pilihan diingat per pengguna & per layar** (`localStorage`), karena orang
 *    yang bekerja di satu lini membuka layar yang sama puluhan kali sehari; memaksa
 *    dia memilih ulang tiap kali adalah pajak yang tidak perlu.
 * 3. **Akun berpagar lini hanya melihat lininya.** Menampilkan chip "Woven"
 *    kepada staf printing berarti menawarkan tombol yang PASTI menghasilkan daftar
 *    kosong — server memang menolaknya (pagar `line_scope`), jadi menyembunyikan
 *    chipnya bukan menyembunyikan kebenaran, melainkan tidak memasang jebakan.
 *
 * Gaya visual MENIRU bilah filter yang sudah ada (`features/orders/OrdersView.jsx`
 * & `AccountList.jsx`): kotak putih, border #E5E5EA, chip rounded-md. Tidak ada
 * bahasa visual baru (kontrak UI/UX §4 RENCANA_EKSEKUSI_MD_ERP.md).
 *
 * Pemakaian:
 *   const [line, setLine] = useState("");            // "" = semua
 *   <LineFilter value={line} onChange={setLine} storageKey="orders"
 *               allowed={currentUser?.allowed_line_codes} />
 *   …lalu kirim `line` sebagai parameter `?line=` ke endpoint daftarnya.
 */
import { useCallback, useEffect, useMemo } from "react";
import KNSelect from "./KNSelect";

import useDomainEnums from "../hooks/useDomainEnums";

const STORAGE_PREFIX = "kn.lineFilter.";

/** Baca pilihan tersimpan (aman bila localStorage diblokir peramban). */
function readSaved(storageKey) {
  if (!storageKey) return "";
  try {
    return window.localStorage.getItem(STORAGE_PREFIX + storageKey) || "";
  } catch {
    return "";
  }
}

function writeSaved(storageKey, value) {
  if (!storageKey) return;
  try {
    window.localStorage.setItem(STORAGE_PREFIX + storageKey, value || "");
  } catch {
    /* mode privat / storage penuh — penyaring tetap bekerja, hanya tidak diingat */
  }
}

export default function LineFilter({
  value = "",
  onChange,
  storageKey = "",
  allowed = [],
  label = "Lini",
  className = "",
  testId = "line-filter",
}) {
  const { options, loading } = useDomainEnums();

  const allOptions = useMemo(() => options("product_line"), [options]);
  const allowedSet = useMemo(
    () => new Set((allowed || []).map((c) => String(c || "").trim().toLowerCase())),
    [allowed]
  );
  const lines = useMemo(
    () => (allowedSet.size ? allOptions.filter((o) => allowedSet.has(o.value)) : allOptions),
    [allOptions, allowedSet]
  );

  const selected = useMemo(
    () => String(value || "").split(",").map((s) => s.trim()).filter(Boolean),
    [value]
  );

  // Pulihkan pilihan terakhir sekali saat layar dibuka (hanya bila belum dipilih).
  useEffect(() => {
    if (!storageKey || value) return;
    const saved = readSaved(storageKey);
    if (!saved) return;
    // Buang lini yang sudah tidak ada / tidak boleh diakses akun ini, supaya
    // pilihan lama tidak membuat layar kosong tanpa sebab setelah hak berubah.
    const known = new Set(lines.map((o) => o.value));
    const keep = saved.split(",").filter((c) => known.has(c));
    if (keep.length) onChange?.(keep.join(","));
    else if (saved) writeSaved(storageKey, "");
  }, [storageKey, lines]); // eslint-disable-line react-hooks/exhaustive-deps

  const setValue = useCallback((next) => {
    writeSaved(storageKey, next);
    onChange?.(next);
  }, [onChange, storageKey]);

  // Satu lini (atau nol) → tidak ada yang bisa disaring; sembunyikan kontrolnya
  // daripada memasang kontrol yang tidak mengubah apa pun.
  if (loading || lines.length < 2) return null;

  // Pola UI (04_POLA_UI §1.2, pemilik 16 Nov — M24) — lini dipilih lewat DROPDOWN, sebaris dengan cari & saringan lain.
  // Dulu deret chip "LINI Semua · Woven · Knit · Printing" yang memakan ruang dan beda dari saringan lain. Nilai lama
  // berisi beberapa lini (koma) tetap dihormati sampai pengguna memilih ulang.
  const multi = selected.length > 1;
  return (
    <span data-testid={testId} className={`inline-flex items-center gap-1.5 ${className}`}>
      <KNSelect data-testid={`${testId}-select`} aria-label={label} value={multi ? "__multi" : (selected[0] || "")}
        onValueChange={(v) => v !== "__multi" && setValue(v || "")}
        className="!h-auto !w-auto min-w-[140px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13"
        options={[{ value: "", label: `Semua ${label.toLowerCase()}` },
          ...(multi ? [{ value: "__multi", label: `${selected.length} ${label.toLowerCase()} dipilih` }] : []),
          ...lines.map((o) => ({ value: o.value, label: `${label}: ${o.label}` }))]} />
      {allowedSet.size > 0 && (
        <span
          data-testid={`${testId}-restricted`}
          className="whitespace-nowrap text-fs-12 text-kn-warning-text"
          title="Akses akun Anda dibatasi pada lini ini oleh admin (Pengaturan › Pengguna & Hak Akses › Akun)."
        >
          akses lini terbatas
        </span>
      )}
    </span>
  );
}
