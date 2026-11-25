/**
 * useIssuePenalty — satu-satunya jalur "Terbitkan denda" (Meja gelombang 2, Task 7).
 * Dipakai Meja Keuangan, antrean Denda Meja Kredit, dan PenaltyPanel: konfirmasi → `POST /penalties/{id}/issue`
 * dengan kunci intent `pnl-terbit`. Teks konfirmasi = teks Meja Kredit (menyebut pelanggan & PT).
 *
 * `issue(row)` — row: { id, number, amount, customer_name, entity_id }.
 * Hasil: `true` terbit · `false` dibatalkan di konfirmasi. Galat server dilempar ke pemanggil (tampil di layarnya).
 */
import { useState } from "react";
import { askConfirm } from "../../../services/confirmService";
import useIntentKey from "../../../hooks/useIntentKey";
import { useEntityScope } from "../../../context/EntityScopeContext";
import { entityShort } from "../../../utils/entityLabel";
import { formatCurrency } from "../../../utils/formatters";
import { issuePenalty } from "./paymentApi";

export default function useIssuePenalty() {
  const { entities } = useEntityScope() || {};
  const intent = useIntentKey("pnl-terbit");
  const [busy, setBusy] = useState(false);

  const ptName = (id) => entityShort((entities || []).find((e) => e && e.id === id), "PT");

  const issue = async (row) => {
    const ok = await askConfirm({
      title: `Terbitkan denda ${row.number}?`,
      message: `Denda ${formatCurrency(row.amount)} untuk ${row.customer_name} di ${ptName(row.entity_id)} diterbitkan dan dijurnal ke piutang denda.`,
      confirmLabel: "Terbitkan",
    });
    if (!ok) return false;
    setBusy(true);
    try {
      await intent.send({ id: row.id, aksi: "issue" }, (key) => issuePenalty(row.id, key));
      return true;
    } finally { setBusy(false); }
  };

  return { issue, busy };
}
