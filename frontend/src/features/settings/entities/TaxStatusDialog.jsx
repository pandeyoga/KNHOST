/**
 * TaxStatusDialog (KP-T1, KP-02) — pop-up baku "Ubah Status PKP" di detail PT.
 *
 * Dulu status PKP hanya bisa dipilih saat PT dibuat; mengubahnya butuh programmer, padahal PT bisa dikukuhkan atau
 * dicabut PKP-nya. Sekarang: status baru, tanggal berlaku (hari ini/mundur = langsung; maju = dijadwalkan), alasan,
 * dan panel **Dampak** dari server (`GET …/tax-status/preview`) sebelum disimpan. Tombol simpan mati selama server
 * menyatakan belum bisa diterapkan (`can_apply`) — mis. NPWP belum ada saat menjadi PKP.
 */
import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";

import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import KNDatePicker, { formatDateId } from "../../../components/KNDatePicker";
import { changeTaxStatus, errText, npwpValid, NPWP_MESSAGE, taxStatusPreview, TAX_STATUS_LABEL } from "./entityApi";

const todayWib = () => new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10);

function fmtValue(v) {
  if (typeof v === "boolean") return v ? "aktif" : "mati";
  if (typeof v === "number") return `${v.toLocaleString("id-ID")} %`;
  return v === null || v === undefined || v === "" ? "—" : String(v);
}

export default function TaxStatusDialog({ entity, onClose, onSaved }) {
  const current = entity?.default_tax_mode || "";
  const [to, setTo] = useState(current === "ppn" ? "non_ppn" : "ppn");
  const [effectiveDate, setEffectiveDate] = useState(todayWib());
  const [reason, setReason] = useState("");
  const [npwp, setNpwp] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const needNpwp = to === "ppn" && !String(entity?.npwp || "").trim();
  const npwpLocalError = needNpwp && npwp.trim() && !npwpValid(npwp) ? NPWP_MESSAGE : "";

  useEffect(() => {
    if (!entity?.id || !effectiveDate) return undefined;
    let alive = true;
    setPreviewError("");
    taxStatusPreview(entity.id, { to, effectiveDate, npwp: needNpwp ? npwp.trim() : "" })
      .then((p) => { if (alive) setPreview(p); })
      .catch((e) => { if (alive) { setPreview(null); setPreviewError(errText(e, "Gagal memuat dampak perubahan.")); } });
    return () => { alive = false; };
  }, [entity?.id, to, effectiveDate, npwp, needNpwp]);

  const count = (coll, list = preview?.open_documents) => (list || []).find((d) => d.collection === coll)?.count || 0;
  const canApply = Boolean(preview?.can_apply) && !npwpLocalError && Boolean(reason.trim()) && !busy;

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const body = { to, effective_date: effectiveDate, reason: reason.trim(), ...(needNpwp ? { npwp: npwp.trim() } : {}) };
      const saved = await changeTaxStatus(entity.id, body);
      onSaved?.(saved);
    } catch (e) {
      setError(errText(e, "Gagal mengubah status PKP."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormModal open onClose={onClose} title="Ubah Status PKP" icon={ShieldCheck} size="md"
      subtitle={`${entity?.legal_name || entity?.short_name || "PT"} · sekarang ${TAX_STATUS_LABEL[current] || "—"}`}
      testId="entity-tax-dialog" submitTestId="entity-tax-submit" submitLabel="Ubah Status PKP"
      onSubmit={submit} submitDisabled={!canApply} busy={busy} error={error}>
      <div className="grid gap-3">
        <div className="grid gap-1">
          <label className="kicker">Status baru</label>
          <KNSelect className="field" data-testid="entity-tax-to" value={to} onValueChange={setTo}
            options={[{ value: "ppn", label: TAX_STATUS_LABEL.ppn }, { value: "non_ppn", label: TAX_STATUS_LABEL.non_ppn }]} />
        </div>
        <div className="grid gap-1">
          <label className="kicker">Berlaku mulai</label>
          <KNDatePicker value={effectiveDate} onChange={setEffectiveDate} clearable={false}
            data-testid="entity-tax-date" />
          <p className="text-fs-12 text-kn-text-2">
            Hari ini atau tanggal lampau langsung berlaku; tanggal mendatang dijadwalkan dan diterapkan otomatis pada
            tanggalnya.
          </p>
        </div>
        {needNpwp && (
          <div className="grid gap-1">
            <label className="kicker">NPWP</label>
            <input className="field" data-testid="entity-tax-npwp" placeholder="00.000.000.0-000.000" value={npwp}
              onChange={(e) => setNpwp(e.target.value)} />
            {npwpLocalError && <p className="text-fs-12 text-kn-danger-text" data-testid="entity-tax-npwp-error">{npwpLocalError}</p>}
          </div>
        )}
        <div className="grid gap-1">
          <label className="kicker">Alasan</label>
          <input className="field" data-testid="entity-tax-reason" placeholder="mis. Dikukuhkan PKP oleh KPP sejak 1 Desember"
            value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>

        <div className="rounded-md border border-kn-divider bg-kn-neutral-soft p-3" data-testid="entity-tax-impact">
          <p className="kicker mb-1">Dampak</p>
          {previewError ? (
            <p className="text-fs-12 text-kn-danger-text" data-testid="entity-tax-impact-error">{previewError}</p>
          ) : !preview ? (
            <div className="h-8 animate-pulse rounded bg-kn-divider" data-testid="entity-tax-impact-loading" />
          ) : (
            <div className="grid gap-1.5 text-fs-13 text-kn-text">
              <p data-testid="entity-tax-applies">
                {preview.applies === "terjadwal"
                  ? `Dijadwalkan — status berubah otomatis pada ${formatDateId(preview.effective_date)}.`
                  : "Berlaku sekarang setelah disimpan."}
              </p>
              <p data-testid="entity-tax-open-docs">
                {count("sales_orders")} pesanan penjualan dan {count("purchase_orders")} pesanan pembelian yang masih
                berjalan tetap memakai hitungan pajak lama.
              </p>
              {(preview.documents_since || []).length > 0 && (
                <p data-testid="entity-tax-docs-since">
                  {count("sales_orders", preview.documents_since)} pesanan penjualan dan{" "}
                  {count("purchase_orders", preview.documents_since)} pesanan pembelian dibuat sejak tanggal berlaku
                  — hitungan pajaknya tidak diubah.
                </p>
              )}
              {preview.tax_invoices_issued > 0 && (
                <p>{preview.tax_invoices_issued} faktur pajak sudah terbit untuk PT ini (tidak diubah).</p>
              )}
              <ul className="grid gap-0.5" data-testid="entity-tax-settings">
                {(preview.setting_layers || []).map((s) => (
                  <li key={s.key}>{s.label}: <b>{fmtValue(s.value)}</b> — {s.effect}</li>
                ))}
              </ul>
              {(preview.blockers || []).length > 0 && (
                <ul className="grid gap-0.5 text-kn-danger-text" data-testid="entity-tax-blockers">
                  {preview.blockers.map((b) => <li key={b}>{b}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </FormModal>
  );
}
