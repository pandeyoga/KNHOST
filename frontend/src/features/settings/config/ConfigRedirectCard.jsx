/**
 * ConfigRedirectCard — FASE G-0 · penanda "pengaturan ini pindah rumah".
 *
 * LATAR BELAKANG (audit 2026-07-26):
 *   Konfigurasi dulu tersebar di 13 permukaan editor dengan 13 bentuk API. Akibatnya
 *   dua form bisa menyimpan kunci yang sama dengan cara berbeda → nilai menyimpang
 *   tanpa ada yang tahu. Pemilik memutuskan editor lama **DIHAPUS**, bukan sekadar
 *   dibuat read-only, supaya benar-benar tinggal satu sumber kebenaran.
 *
 * Kartu ini menggantikan form yang dihapus. Tugasnya cuma dua:
 *   1. Menjelaskan dengan bahasa manusia ke mana pengaturannya pindah.
 *   2. Mengantar user PERSIS ke kartu setting-nya (bukan cuma ke halamannya).
 */
import { ArrowRight, Settings2 } from "lucide-react";
import { openConfig } from "./configDeepLink";

/**
 * @param {string}   title    Judul blok yang dulu ada di sini.
 * @param {string}   note     Kalimat tambahan opsional (konteks khusus layar ini).
 * @param {string}   group    Id kelompok tujuan (opsional bila `settings` diisi).
 * @param {Array}    settings Daftar {key, label} yang dulu bisa diubah di sini.
 * @param {string}   testId   data-testid unik per pemakaian.
 * @param {boolean}  compact  Versi ringkas (untuk disisipkan di dalam panel lain).
 */
export default function ConfigRedirectCard({
  title = "Pengaturan",
  note = "",
  group = "",
  settings = [],
  testId = "config-redirect",
  compact = false,
}) {
  const primary = settings[0]?.key || "";
  const go = (key) => openConfig(key ? { key, group } : { group });

  return (
    <div className={`cfg-redirect ${compact ? "compact" : ""}`} data-testid={testId}>
      <div className="cfg-redirect-icon" aria-hidden="true">
        <Settings2 size={compact ? 15 : 18} />
      </div>

      <div className="cfg-redirect-body">
        {/* Audit UI 24 Okt (059/111) — tanpa catatan pengembang ("form lama dihapus"); cukup ke mana pengguna pergi. */}
        <h4 className="cfg-redirect-title">{title} diatur di Pusat Pengaturan</h4>
        <p className="cfg-redirect-text">
          Ubah aturan ini di Pusat Pengaturan — di sana ada penjelasan, contoh angka,
          simulasi <b>“coba dulu”</b>, jadwal berlaku, dan riwayat perubahan.
          {note ? <> {note}</> : null}
        </p>

        {settings.length > 0 ? (
          <ul className="cfg-redirect-list" data-testid={`${testId}-list`}>
            {settings.map((s) => (
              <li key={s.key}>
                <button
                  type="button"
                  className="cfg-redirect-chip"
                  onClick={() => go(s.key)}
                  data-testid={`${testId}-key-${s.key}`}
                  title={`Buka “${s.label || s.key}” di Pusat Pengaturan`}
                >
                  {s.label || s.key}
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <button
          type="button"
          className="btn-primary btn-sm cfg-redirect-cta"
          onClick={() => go(primary)}
          data-testid={`${testId}-open`}
        >
          Buka di Pusat Pengaturan <ArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}
