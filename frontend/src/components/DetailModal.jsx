import { useEffect } from "react";
import { X } from "lucide-react";
import { overlayDismiss } from "@/utils/overlayDismiss";
import { useEscapeClose } from "@/utils/escapeLayers";

/**
 * DetailModal — **standar pop-up untuk PANEL RINCIAN** (klik baris → detail), FASE P7.
 *
 * MASALAH YANG DISELESAIKAN (keluhan pemilik, berulang)
 * =====================================================
 * FASE P4 sudah mewajibkan tombol **"Buat/Ubah"** memakai pop-up (`FormModal`), dengan
 * alasan yang ditulis di berkas itu: form yang diselipkan di tengah halaman mendorong
 * daftar data ke bawah lipatan, pengguna tak sadar formnya terbuka, lalu menyimpulkan
 * "tombolnya tidak berfungsi".
 *
 * Persoalan yang SAMA masih ada untuk **panel rincian**, dan tidak pernah tercakup:
 * pada 9 layar, mengklik satu baris tabel merender panel detail sebagai **saudara di
 * bawah tabelnya**. Diukur pada `ar-aging` (layar yang dilaporkan pemilik): tabel
 * "Piutang per Pelanggan" + tabel ringkasan + catatan kaki berada di antara baris yang
 * diklik dan panel yang muncul — jadi setelah mengklik, **tidak ada perubahan apa pun
 * yang terlihat di layar**; rinciannya ada, tetapi di luar pandangan. Semakin panjang
 * tabelnya, semakin jauh. Pengguna menyimpulkan kliknya tidak berfungsi, lalu mengklik
 * baris lain — dan panel di bawah diam-diam berganti isi.
 *
 * KENAPA SHELL INI TIDAK PUNYA KEPALA SENDIRI (beda dari `FormModal`)
 * ------------------------------------------------------------------
 * Kesembilan panel itu SUDAH punya `section-head` sendiri: judul, ringkasan nominal,
 * lencana, tombol aksi kontekstual (mis. "Buat Nota Denda"), dan tombol tutup. Bila
 * shell ini menambahkan kepala lagi, hasilnya dua baris judul dan dua tombol tutup.
 * Jadi ia sengaja hanya menyediakan **lapisan + posisi + perilaku**, dan membiarkan
 * panelnya tetap menjadi kartu yang sudah ada. Akibatnya konversi tiap layar = satu
 * pembungkus, tanpa menyentuh isi panelnya — perubahan kecil, risiko kecil.
 *
 * Yang dibereskan di satu tempat (sama seperti `FormModal`, supaya perilaku pop-up di
 * aplikasi ini hanya ada SATU macam):
 *  · **Esc menutup**;
 *  · **backdrop pakai `overlayDismiss()`** — INV-UI-01: memilih opsi pada dropdown
 *    ber-portal Radix di dalam panel TIDAK boleh menutup pop-upnya;
 *  · **scroll halaman di belakang dikunci**, isi panjang di-scroll di dalam lapisan;
 *  · `role="dialog"` + `aria-modal` + nama yang terbacakan.
 *
 * Dijaga `scripts/guardrails/verify_detail_modal.py` (INV-UI-08).
 *
 * Fase 3 · P1 (L-03/L-04) — di layar ≤640 px pop-up ini LAYAR PENUH (100dvh, sudut lurus). `framed`: kartu
 * sendiri yang bergulir sehingga tombol × tetap terlihat di pojok; tanpa `framed`: panel anak yang bergulir.
 * API tidak berubah; gaya di `styles/components.css` (`.kn-detail-*`).
 */
const SIZES = {
  md: "max-w-2xl",
  lg: "max-w-4xl",
  xl: "max-w-6xl",
  full: "max-w-[1400px]",
};

export default function DetailModal({
  open = true,
  onClose,
  size = "xl",
  label = "Rincian",
  testId = "detail-modal",
  // Sesi #087 — `framed`: panel yang TIDAK punya kartu sendiri (root `grid gap-3`) dibungkus
  // kartu putih di sini; tanpa itu isinya melayang transparan di atas halaman (laporan pemilik).
  framed = false,
  // UAT 24 Okt (audit UI tahap 2) — G0-07 · P-08: pop-up `framed` dulu tanpa tombol × — penutupan hanya lewat Esc,
  // klik latar, atau tombol "Tutup" di dasar setelah gulir ±2.600 px di HP. Kini × melayang di pojok kartu
  // (di luar area gulir, jadi selalu terlihat). `showClose={false}` bila panel sudah punya × sendiri.
  showClose = true,
  children,
}) {
  // Esc menutup lewat tumpukan lapisan (INV-UI-10): pemilih/dropdown di dalam panel
  // rincian menutup dirinya saja, panelnya tetap terbuka.
  useEscapeClose(open, onClose);

  useEffect(() => {
    if (!open) return undefined;
    const sebelumnya = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = sebelumnya; };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="modal-overlay kn-modal-overlay fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:items-center"
      data-testid={`${testId}-overlay`}
      {...overlayDismiss(onClose)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={label}
        data-testid={testId}
        className={`kn-detail-modal ${framed ? "kn-detail-framed relative" : ""} w-full ${SIZES[size] || SIZES.xl} my-auto`}
        onClick={(e) => e.stopPropagation()}
      >
        {framed ? (
          <>
            {showClose && typeof onClose === "function" && (
              <button type="button" aria-label="Tutup" title="Tutup (Esc)" data-testid={`${testId}-close-x`}
                onClick={onClose}
                className="kn-detail-close absolute -right-2.5 -top-2.5 z-10 grid h-8 w-8 place-items-center rounded-full border border-[#E5E5EA] bg-white text-[#3C3C43] shadow-md transition hover:bg-[#F2F2F7]">
                <X size={16} />
              </button>
            )}
            <div className="kn-detail-frame rounded-2xl bg-white p-4 shadow-2xl max-h-[calc(100dvh-2rem)] overflow-y-auto">
              {children}
            </div>
          </>
        ) : children}
      </div>
    </div>
  );
}
