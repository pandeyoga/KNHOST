/**
 * useJournalActions — anulir & balik jurnal dari pop-up rincian jurnal (dipakai tab Jurnal dan tab Buku Besar).
 *
 * PK-43 (UX-13) — diekstrak dari `JournalTab` (GeneralLedger.jsx) supaya rincian jurnal yang dibuka dari baris buku
 * besar punya aksi yang sama. PK-12 — satu kunci idempotensi per niat (anulir / balik); tombolnya dimatikan
 * `JournalDetailModal` selama menunggu. Galat DILEMPAR ke pop-up rincian (bukan ke bilah galat halaman).
 *
 *   const { voidEntry, reverseEntry } = useJournalActions(() => { setDetail(null); onChanged(); });
 */
import { API } from "../../services/apiClient";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { can } from "../../config/roles";

/**
 * Pelatihan 18 Nov (F16) — izin akuntansi akun yang sedang masuk (dari sesi tersimpan `kn_user`). Finance = `view` saja
 * (K-09): tombol Jurnal Baru (`create`), Sinkronkan (`manage`), Anulir/Balik (`void`) dulu tampil lalu ditolak 403.
 * Data izin belum ada (uji komponen / sesi lama) → `true` (perilaku lama); server tetap menegakkan.
 */
export function izinAkuntansi(aksi) {
  let u = null;
  try { u = JSON.parse(localStorage.getItem("kn_user") || "null"); } catch { u = null; }
  if (!u || !u.permissions) return true;   // izin Admin bawaan memuat semua aksi `accounting` — tanpa cek nama peran
  return can(u.permissions, "accounting", aksi);
}

export default function useJournalActions(onDone) {
  const voidIntent = useIntentKey("jev");
  const reverseIntent = useIntentKey("jer");

  const voidEntry = async (je) => {
    await voidIntent.send({ id: je.id, aksi: "void" },
      (k) => moneyPost(`${API}/gl/journal/${je.id}/void`, undefined, k));
    onDone?.();
  };

  const reverseEntry = async (je, date, reason) => {
    const body = { date, reason };
    await reverseIntent.send({ id: je.id, ...body },
      (k) => moneyPost(`${API}/gl/journal/${je.id}/reverse`, body, k));
    onDone?.();
  };

  // `bolehBatal` — anulir & balik jurnal ber-izin `accounting.void`; pemanggil tidak mengirim aksinya bila tidak boleh.
  return { voidEntry, reverseEntry, bolehBatal: izinAkuntansi("void") };
}
