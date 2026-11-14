/**
 * ProfileSettingDialog (KP-T1, KP-01) — ubah tahun buku / mata uang pembukuan PT dari detail PT.
 *
 * Tahun buku dan mata uang punya SATU sumber: kunci Pusat Pengaturan `finance.fiscal_year_end_month` dan
 * `finance.base_currency`, lapisan PT. Pop-up ini memakai editor baku Pusat Pengaturan (`SettingEditor`) dan jalur
 * simpan baku (`PUT /api/config/values`, lapisan PT) — bukan isian master PT kedua. Alasan wajib bila registry
 * menandai kunci berisiko tinggi (tahun buku).
 */
import { useState } from "react";
import { SlidersHorizontal } from "lucide-react";

import FormModal from "../../../components/FormModal";
import SettingEditor from "../config/SettingEditor";
import { BULAN_ID, errText, saveProfileSetting } from "./entityApi";

export default function ProfileSettingDialog({ entityId, entityName, item, onClose, onSaved }) {
  const [value, setValue] = useState(item?.value);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!item) return null;
  const isMonth = item.key === "finance.fiscal_year_end_month";
  // Bulan ditampilkan sebagai nama bulan (bukan angka 1–12) — pilihan enum untuk editor baku.
  const entry = isMonth
    ? { ...item, type: "enum", options: BULAN_ID.map((b, i) => ({ value: String(i + 1), label: b })) }
    : item;
  const dirty = JSON.stringify(value) !== JSON.stringify(item.value);
  const needReason = Boolean(item.requires_reason);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await saveProfileSetting(entityId, item.key, isMonth ? Number(value) : value, reason.trim());
      onSaved?.();
    } catch (e) {
      setError(errText(e, "Gagal menyimpan pengaturan."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormModal open onClose={onClose} title={isMonth ? "Ubah Tahun Buku" : "Ubah Mata Uang Pembukuan"}
      subtitle={`${entityName || "PT ini"} · hanya PT ini yang berubah`} icon={SlidersHorizontal} size="sm"
      testId="entity-profile-dialog" onSubmit={submit} busy={busy} error={error}
      submitDisabled={!dirty || (needReason && !reason.trim())}>
      <div className="grid gap-3">
        <div className="grid gap-1">
          <label className="kicker">{isMonth ? "Tahun buku berakhir pada bulan" : "Mata uang pembukuan"}</label>
          <SettingEditor entry={entry} value={isMonth ? String(value ?? "") : value}
            onChange={(v) => setValue(isMonth ? Number(v) : v)} disabled={busy} testId="entity-profile-input" />
          <p className="text-fs-12 text-kn-text-2">{item.impact}</p>
        </div>
        <div className="grid gap-1">
          <label className="kicker">Alasan {needReason ? "(wajib)" : "(opsional)"}</label>
          <input className="field" data-testid="entity-profile-reason" value={reason}
            onChange={(e) => setReason(e.target.value)} />
        </div>
      </div>
    </FormModal>
  );
}
