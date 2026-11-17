import { useState } from "react";
import { formatCurrency } from "../utils/formatters";
import { heldMoney, isMoneyDraft, moneyText } from "../utils/parseMoney";

/**
 * MoneyInput — isian rupiah seragam: awalan "Rp", keypad desimal, dan pratinjau
 * terformat ("Rp 1.250.000") di bawah kotak supaya nol-nya tidak salah hitung.
 *
 * PK-42 — awalan & pratinjau mengikuti Standar UI (KN_37 §2: huruf ≥ 12 px, warna teks minimum `kn-text-2`); dulu
 * 10–11 px berwarna #8E8E93 (gagal kontras AA).
 *
 * Pola UI 16 Nov (M43) — `showPreview={false}` untuk baris daftar padat (mis. Kontrol dua orang): tanpa baris gema
 * "Rp 0" di bawah kotak; nilai terformat tetap ada di tooltip kotak. Bawaan tetap menampilkan pratinjau.
 *
 * Pelatihan Keuangan 18 Nov (uji variasi isian) — kotak menerima cara orang Indonesia menulis uang: "3.374.123",
 * "3.374.122,50", "3,374,123", "Rp 3.374.123", "3 374 123", "3.374.123,-" (aturan: `utils/parseMoney`). Yang DIKETIK
 * tetap tampil apa adanya, tetapi `onChange` menerima teks KANONIK ("3374122.5"; "" bila kosong/belum angka) sehingga
 * pemanggil yang membaca `Number(v)` maupun `parseDecimal(v)` mendapat nominal yang sama dengan pratinjau. Dulu
 * "3.374.123" yang diketik menjadi "3.374123" (Rp 3), tempelan bertitik ditolak diam-diam, dan "3374122,5" terbaca 0.
 * Bila pemanggil mengubah nilainya sendiri (dibatasi maksimum, diisi ulang), kotak menampilkan nilai pemanggil.
 */
export default function MoneyInput({ value, onChange, className = "field", testId, hint, showPreview = true,
  invalid = false, allowNegative = false, min: _min, suffix: _suffix, ...rest }) {
  const held = value === null || value === undefined ? "" : String(value);
  // `src` = nilai kanonik yang terakhir dikirim untuk `draft`. Selama pemanggil memegang nilai itu, teks ketikan
  // ditampilkan; begitu pemanggil memegang nilai lain, nilai pemanggil yang tampil.
  const [st, setSt] = useState({ draft: held, src: held });
  const text = st.src === held ? st.draft : held;
  const n = heldMoney(held);
  // Pelatihan 18 Nov — pratinjau menampilkan sen bila ada (Rp 40.864,50), dulu dibulatkan (Rp 40.865) sehingga berbeda
  // dari nilai yang tersimpan.
  const preview = held !== "" && !Number.isNaN(n)
    ? (Number.isInteger(n) ? formatCurrency(n) : new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR",
      minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n))
    : "";
  // `allowNegative` — nominal penyesuaian (mis. masukan gaji minus) sah: tanpa bingkai merah.
  const bad = invalid || (!allowNegative && !Number.isNaN(n) && n < 0);
  return (
    <div className="grid gap-0.5">
      <div className="relative">
        <input title={showPreview ? undefined : preview || undefined} {...rest} type="text" inputMode="decimal"
          autoComplete="off" data-testid={testId} value={text} style={{ paddingLeft: 34 }}
          className={`${className} tabular-nums ${bad ? "!border-[#D14343]" : ""}`}
          onChange={(e) => {
            // Awalan "Rp"/"IDR" yang ikut ditempel dibuang (kotak sudah berlabel "Rp"); nol di depan dirapikan.
            const next = e.target.value.replace(/^\s*(?:rp|idr)\.?\s*/i, "").replace(/^0+(?=\d)/, "");
            if (!isMoneyDraft(next)) return;          // huruf/simbol lain: diabaikan seperti dulu
            const canon = moneyText(next);
            setSt({ draft: next, src: canon });
            onChange?.(canon);
          }} />
        <span className="pointer-events-none absolute left-2.5 top-1/2 z-10 -translate-y-1/2 text-fs-12 font-semibold text-kn-text-2">Rp</span>
      </div>
      {showPreview && (preview || hint) && (
        <p className="text-fs-12 tabular-nums text-kn-text-2" data-testid={testId ? `${testId}-preview` : undefined}>
          {preview}{preview && hint ? " · " : ""}{hint || ""}
        </p>
      )}
    </div>
  );
}
