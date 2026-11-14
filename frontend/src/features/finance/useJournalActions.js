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

  return { voidEntry, reverseEntry };
}
