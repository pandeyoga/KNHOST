/**
 * KNSelect — Select universal (wrapper shadcn).
 * UX W2: Semua select harus pakai komponen ini.
 *
 * API (tidak berubah — backward compatible):
 *   <KNSelect value={v} onValueChange={setV} options={[{value, label}]}
 *             className="field" placeholder="..." disabled searchable data-testid="..." />
 *
 * Dua mode render (otomatis, transparan ke pemanggil):
 *  1) Radix Select (default) untuk daftar pendek.
 *  2) Combobox (Popover + cmdk Command) dengan pencarian inline untuk daftar panjang
 *     (>= SEARCH_THRESHOLD opsi) atau saat prop `searchable` di-set true.
 *
 * Empty-value handling: Radix <Select.Item> melarang value="" — komponen ini
 * memetakan "" <-> sentinel "__empty__" untuk jalur Select, DAN menyisipkan satu
 * item sentinel berlabel `placeholder` bila daftar opsi belum punya opsi bernilai
 * kosong. Tanpa item itu, Radix menampilkan kotak KOSONG tanpa petunjuk saat value
 * masih "". Jalur combobox tidak butuh sentinel (kontrol penuh), tapi tetap
 * mengirim "" ke parent seperti biasa.
 *
 * UAT 24 Okt (audit UI tahap 2) — P-03 (G0-04/05/06), berlaku ke semua pemakaian:
 *  · Opsi bernilai "" (placeholder / "Semua …") tidak lagi tampil sebagai pilihan TERCENTANG: selama nilai
 *    masih kosong ia disembunyikan dari daftar (pemicu tetap menampilkan labelnya); setelah nilai terisi ia
 *    tampil abu tanpa ✓ sebagai jalan untuk mengosongkan kembali.
 *  · Sorotan keyboard/kursor netral (abu), BUKAN hijau seperti "terpilih"; nilai terpilih = ✓ + teks tebal biru.
 *    Combobox dibuka dengan sorotan & gulir di nilai aktif (dulu selalu butir pertama).
 *  · Menu selebar isinya (minimal selebar pemicu, maksimal 26rem / lebar layar) — dulu dipaksa selebar pemicu
 *    sehingga nama gudang patah 3–4 baris.
 *  · Nilai tersimpan yang tidak ada di daftar opsi (dan daftar sudah termuat) tampil "<nilai> (tidak ada di daftar)"
 *    bergaya peringatan, bukan kotak kosong — prop opsional `unknownLabel(value)` untuk teks lain.
 *  · Daftar tanpa opsi nyata menampilkan `emptyText` (bawaan "Belum ada pilihan").
 */
import React, { useEffect, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

// Aktifkan pencarian otomatis bila opsi >= ambang ini.
const SEARCH_THRESHOLD = 6;
// Sentinel internal untuk menggantikan empty string yang dilarang Radix Select.
const EMPTY_SENTINEL = "__empty__";

const toSafe = (v) =>
  v === "" || v === null || v === undefined ? EMPTY_SENTINEL : String(v);
const isBlank = (v) => v === "" || v === null || v === undefined;
// G0-05 — lebar menu: minimal selebar pemicu, mengikuti isi, dibatasi layar.
const MENU_WIDTH = "min-w-[var(--radix-popover-trigger-width)] w-max max-w-[min(26rem,calc(100vw-1.5rem))]";

/** G0-06 — nilai tersimpan non-kosong yang tidak ada di daftar opsi. Hanya bila daftar sudah berisi: saat opsi
 *  masih dimuat (kosong) perilaku lama dipertahankan. Dev: console.warn sekali per nilai. */
function useUnknownValue(value, options, unknownLabel, testId) {
  const unknown = !isBlank(value) && options.length > 0
    && !options.some((o) => String(o.value ?? "") === String(value));
  const text = unknown
    ? (typeof unknownLabel === "function" ? unknownLabel(value) : `${value} (tidak ada di daftar)`)
    : "";
  useEffect(() => {
    if (unknown && process.env.NODE_ENV === "development") {
      console.warn(`KNSelect${testId ? ` [${testId}]` : ""}: nilai "${value}" tidak ada di daftar opsi.`);
    }
  }, [unknown, value, testId]);
  return { unknown, text };
}

/** Combobox dengan pencarian inline. Kontrak prop sama dengan KNSelect. */
function KNCombobox({ value, onValueChange, options, className, placeholder, disabled, testId, ariaLabel, emptyText, unknown, unknownText }) {
  const [open, setOpen] = useState(false);
  const valueStr = String(value ?? "");
  const selected = options.find((o) => String(o.value ?? "") === valueStr);
  const itemValue = (opt) => `${opt.label} ${String(opt.value)}`.trim();
  // G0-04 — opsi bernilai "" hanya tampil (abu, tanpa ✓) bila nilai sudah terisi: jalan untuk mengosongkan.
  const listed = options.filter((o) => !isBlank(o.value) || valueStr !== "");
  const realCount = options.filter((o) => !isBlank(o.value)).length;

  const handleSelect = (val) => {
    if (typeof onValueChange === "function") onValueChange(val);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={className}
          data-testid={testId}
          aria-label={ariaLabel}
          data-kn-unknown={unknown ? "true" : undefined}
          title={unknown ? unknownText : undefined}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 8,
            textAlign: "left",
            cursor: disabled ? "not-allowed" : "pointer",
          }}
        >
          <span data-testid={testId ? `${testId}-value` : undefined}
            style={{
              // `minWidth: 0` WAJIB, bukan hiasan: tanpa dia sebuah flex item
              // memakai lebar min-content teks-nya, jadi `textOverflow: ellipsis`
              // di bawah TIDAK PERNAH berlaku dan tombolnya justru MELEBAR sampai
              // menembus tepi pop-up induknya. Terukur 2026-08-23 di pop-up "Buat
              // SPK Inspeksi": label pilihan yang panjang ("SRET-00001 · Toko Kain
              // Sejahtera · Warna tidak sesuai · sudah ada SPK KSC/INS-00002")
              // membuat isi modal terpotong di sisi kanan.
              minWidth: 0,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              color: unknown ? "#B26A00" : selected ? "inherit" : "#9A9BA3",
            }}
          >
            {selected ? (selected.render || selected.label) : unknown ? unknownText : placeholder}
          </span>
          {/* UAT 24 Okt (audit UI) — ikon sama dengan jalur Radix: pengguna dulu melihat dua gaya dropdown yang
              berbeda hanya karena jumlah opsinya ≥ / < SEARCH_THRESHOLD. */}
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className={`p-0 ${MENU_WIDTH}`}
        data-testid={testId ? `${testId}-popover` : undefined}
      >
        {/* G0-04 — sorotan awal di nilai aktif (cmdk menggulirnya ke tampilan saat dibuka), bukan butir pertama. */}
        <Command defaultValue={selected && !isBlank(selected.value) ? itemValue(selected) : undefined}>
          <CommandInput placeholder="Cari..." data-testid={testId ? `${testId}-search` : undefined} />
          <CommandList data-testid={testId ? `${testId}-listbox` : undefined}>
            <CommandEmpty data-testid={testId ? `${testId}-empty-state` : undefined}>
              {realCount === 0 ? (emptyText || "Belum ada pilihan") : "Tidak ada hasil."}
            </CommandEmpty>
            <CommandGroup>
              {listed.map((opt) => {
                const blank = isBlank(opt.value);
                const chosen = !blank && String(opt.value) === valueStr;
                return (
                  <CommandItem
                    key={String(opt.value)}
                    value={itemValue(opt)}
                    keywords={Array.isArray(opt.keywords) ? opt.keywords.filter(Boolean) : undefined}
                    disabled={opt.disabled}
                    data-option-value={String(opt.value ?? "")}
                    data-kn-chosen={chosen ? "true" : undefined}
                    className={chosen ? "font-semibold text-[#0058CC]" : blank ? "text-[#8E8E93]" : undefined}
                    onSelect={() => handleSelect(opt.value)}
                    data-testid={testId ? `${testId}-option-${String(opt.value) || "empty"}` : undefined}
                  >
                    <Check className={`mr-2 h-4 w-4 ${chosen ? "opacity-100" : "opacity-0"}`} />
                    {opt.render || opt.label}
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

/**
 * KNSelect — komponen Select reusable.
 * @param {string|number} value - nilai terpilih ("" untuk kosong)
 * @param {(val: string) => void} onValueChange - callback ("" untuk kosong)
 * @param {Array<{value: string|number, label: string}>} options
 * @param {string} [className]
 * @param {string} [placeholder]
 * @param {boolean} [disabled]
 * @param {boolean} [searchable] - paksa aktif/nonaktif pencarian (override ambang)
 * @param {string} [aria-label] - nama yang terbacakan pembaca layar. WAJIB diteruskan:
 *   `<select>` bawaan bisa diberi `aria-label` langsung, jadi tanpa pass-through ini
 *   setiap konversi native → KNSelect akan **menghapus** nama kontrolnya secara senyap
 *   (terukur pada `NotificationCenter`, filter "Filter jenis notifikasi").
 * @param {string} [emptyText] - teks saat tidak ada opsi nyata (bawaan "Belum ada pilihan").
 * @param {(value) => string} [unknownLabel] - teks untuk nilai tersimpan yang tak ada di daftar
 *   (bawaan "<nilai> (tidak ada di daftar)").
 */
export function KNSelect({
  value,
  onValueChange,
  options = [],
  className = "field",
  placeholder = "Pilih...",
  disabled = false,
  searchable,
  "data-testid": testId,
  "aria-label": ariaLabel,
  onChange,
  emptyText = "Belum ada pilihan",
  unknownLabel,
}) {
  // FE-02 — kontraknya `onValueChange`; `onChange` dulu dibuang diam-diam sehingga pilihan tidak tersimpan.
  if (process.env.NODE_ENV !== "production" && typeof onChange === "function" && typeof onValueChange !== "function") {
    // eslint-disable-next-line no-console
    console.error(`KNSelect${testId ? ` [${testId}]` : ""}: gunakan prop onValueChange, bukan onChange — pilihan tidak akan tersimpan.`);
  }
  // Hook dipanggil SEBELUM percabangan jalur (jumlah opsi bisa melewati ambang antar-render).
  const { unknown, text: unknownText } = useUnknownValue(value, options, unknownLabel, testId);
  const useSearch =
    searchable === true || (searchable !== false && options.length >= SEARCH_THRESHOLD);

  if (useSearch) {
    return (
      <KNCombobox
        value={value}
        onValueChange={onValueChange}
        options={options}
        className={className}
        placeholder={placeholder}
        disabled={disabled}
        testId={testId}
        ariaLabel={ariaLabel}
        emptyText={emptyText}
        unknown={unknown}
        unknownText={unknownText}
      />
    );
  }

  // ── Jalur Radix Select (daftar pendek) ──
  // CATATAN PENTING: Radix hanya menampilkan `placeholder` bila value-nya `undefined`,
  // sedangkan komponen ini SELALU controlled (memakai "" untuk kondisi kosong). Bila
  // "" dipetakan ke sentinel tanpa item pendamping, Radix menganggap "sudah ada nilai"
  // tetapi tidak menemukan item yang cocok → kotak tampil BENAR-BENAR KOSONG tanpa
  // petunjuk apa pun (mis. "Gudang Tujuan *" terlihat kosong).
  // Solusi: sediakan satu item sentinel berlabel placeholder — kotak selalu punya
  // petunjuk, pengguna juga bisa mengosongkan kembali pilihannya, dan komponen tetap
  // controlled (tanpa peringatan uncontrolled→controlled dari React).
  const safeValue = toSafe(value);
  const handleValueChange = (val) => {
    // Item Radix tak pernah bernilai "" (kosong = sentinel). "" mentah datang dari <select> bayangan Radix di dalam
    // <form> saat nilai diisi program sebelum item terdaftar — mis. SO bawaan "Ajukan retur" di HP ter-reset kosong.
    if (val === "") return;
    if (typeof onValueChange === "function") {
      onValueChange(val === EMPTY_SENTINEL ? "" : val);
    }
  };
  const mapped = options.map((opt) => ({ ...opt, safeValue: toSafe(opt.value) }));
  const hasEmptyOption = mapped.some((opt) => opt.safeValue === EMPTY_SENTINEL);
  const isEmpty = safeValue === EMPTY_SENTINEL;
  // Sentinel HANYA disisipkan selama nilainya masih kosong: cukup untuk memunculkan
  // teks petunjuk di trigger, tanpa menambah kemampuan baru "mengosongkan kembali"
  // pada field wajib setelah pengguna memilih (perilaku lama tetap terjaga).
  // G0-04 — sentinel & opsi bernilai "" yang sedang aktif tetap TERDAFTAR (pemicu menampilkan labelnya) tetapi
  // disembunyikan dari daftar: dulu tampil sebagai pilihan tercentang ✓ hijau. Opsi "" saat nilai terisi = abu.
  // G0-06 — nilai tak dikenal didaftarkan sebagai item tersembunyi agar pemicu menampilkan "<nilai> (tidak ada…)".
  const safeOptions = [
    ...(hasEmptyOption || !isEmpty ? [] : [{ value: "", label: placeholder, safeValue: EMPTY_SENTINEL, kn_hidden: true }]),
    ...mapped.map((opt) => (opt.safeValue === EMPTY_SENTINEL
      ? { ...opt, kn_hidden: isEmpty, kn_blank: true } : opt)),
    ...(unknown ? [{ value: String(value), label: unknownText, safeValue: String(value), kn_hidden: true }] : []),
  ];
  const realCount = mapped.filter((opt) => opt.safeValue !== EMPTY_SENTINEL).length;

  return (
    <Select value={safeValue} onValueChange={handleValueChange} disabled={disabled}>
      <SelectTrigger className={className} data-testid={testId} aria-label={ariaLabel}
        data-kn-empty={isEmpty ? "true" : undefined} data-kn-unknown={unknown ? "true" : undefined}
        title={unknown ? unknownText : undefined}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent data-testid={testId ? `${testId}-listbox` : undefined}>
        {realCount === 0 && (
          <div className="px-2 py-1.5 text-sm text-[#8E8E93]" data-testid={testId ? `${testId}-empty-state` : undefined}>
            {emptyText}
          </div>
        )}
        {safeOptions.map((opt) => (
          <SelectItem key={opt.safeValue} value={opt.safeValue} disabled={opt.disabled || opt.kn_hidden}
            className={opt.kn_hidden ? "hidden" : opt.kn_blank ? "text-[#8E8E93]" : undefined}
            aria-hidden={opt.kn_hidden ? "true" : undefined}
            data-option-value={String(opt.value ?? "")}
            data-testid={testId ? `${testId}-option-${String(opt.value) || "empty"}` : undefined}>
            {opt.render || opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export default KNSelect;
