/**
 * PricelistModals — pop-up "Set harga" & "Riwayat harga" layar Harga per Badan Usaha (`PricelistView`).
 * Fase 3 · P3: diekstrak dari `PricelistView.jsx` (berkas layar < 500 baris) dan dipindah ke cangkang baku
 * `FormModal` (L-03: Esc/latar aman INV-UI-01/10, layar penuh 1 kolom di HP). Isian & perilaku tidak berubah.
 */
import { useCallback, useEffect, useState } from "react";
import KNDatePicker from "@/components/KNDatePicker";
import MoneyInput from "@/components/MoneyInput";
import usePagedRows from "@/hooks/usePagedRows";
import { Tag, History, Save, AlertTriangle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EntityBadge from "../../components/EntityBadge";
import FormModal from "../../components/FormModal";
import { formatCurrency, todayWib } from "../../utils/formatters";

const STATUS_META = {
  current: { label: "Berlaku", tone: "bg-[#E6F6EC] text-[#1B7F4B]" },
  scheduled: { label: "Terjadwal", tone: "bg-[#E7F0FF] text-[#0058CC]" },
  expired: { label: "Kadaluarsa", tone: "bg-[#F5F5F7] text-[#8E8E93]" },
  inactive: { label: "Nonaktif", tone: "bg-[#FDEDE7] text-[#C0392B]" },
};

export function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" }); }
  catch { return "—"; }
}

const Label = ({ children }) => <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">{children}</label>;
const Opt = () => <span className="font-normal text-[#9A9BA3]">(opsional)</span>;

export function SetPriceModal({ row, entityId, entityName, onClose, onSaved, onError }) {
  const today = todayWib();
  const [price, setPrice] = useState(row.entity_price != null ? String(row.entity_price) : "");
  const [validFrom, setValidFrom] = useState(today);
  const [validUntil, setValidUntil] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [localError, setLocalError] = useState("");

  const numeric = parseFloat(price);
  const diff = Number.isFinite(numeric) ? numeric - Number(row.global_price || 0) : 0;

  const save = async () => {
    setLocalError("");
    const p = parseFloat(price);
    if (!p || p <= 0) { setLocalError("Harga jual harus lebih dari 0."); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/pricelist`, {
        product_id: row.product_id, sell_price: p, entity_id: entityId,
        valid_from: validFrom, valid_until: validUntil, note,
      });
      onSaved();
    } catch (e) {
      const msg = e.response?.data?.detail || "Gagal menyimpan harga.";
      setLocalError(msg); onError?.(msg);
      setSaving(false);
    }
  };

  return (
    <FormModal open onClose={onClose} size="sm" icon={Tag} title={`Harga ${entityName}`}
      subtitle={row.product_name} testId="pl-setprice-modal" busy={saving} error={localError}
      onSubmit={save}
      footer={(
        <div className="flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Batal</button>
          <button type="submit" data-testid="pl-setprice-save" className="primary-button" disabled={saving}>
            <Save size={14} /> {saving ? "Menyimpan…" : "Simpan harga"}
          </button>
        </div>
      )}>
      <div className="space-y-3 text-[12px]">
        <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2">
          <p className="font-semibold text-[#1C1C1E]">{row.product_name}</p>
          <p className="text-[11px] text-[#9A9BA3]">
            {row.sku} · harga global {formatCurrency(row.global_price)} / {row.base_unit}
            {row.hpp_ref > 0 ? ` · HPP ${formatCurrency(row.hpp_ref)}` : ""}
          </p>
        </div>
        <div>
          <Label>Harga jual {entityName} (per {row.base_unit})</Label>
          <MoneyInput testId="pl-input-price" className="field py-2 text-[13px]"
            placeholder="Mis. 195000" value={price} onChange={(v) => setPrice(v)} autoFocus />
          {Number.isFinite(numeric) && numeric > 0 && (
            <p data-testid="pl-price-diff" className="mt-1 text-[10.5px] text-[#6B6B73]">
              {diff === 0 ? "Sama dengan harga global."
                : `${diff > 0 ? "Lebih tinggi" : "Lebih rendah"} ${formatCurrency(Math.abs(diff))} dari harga global.`}
              {row.hpp_ref > 0 && numeric < row.hpp_ref && (
                <span className="ml-1 font-bold text-[#C0392B]">
                  <AlertTriangle size={10} className="inline" /> di bawah HPP
                </span>
              )}
            </p>
          )}
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <Label>Berlaku mulai</Label>
            <KNDatePicker data-testid="pl-input-from" value={validFrom} onChange={setValidFrom} />
          </div>
          <div>
            <Label>Berlaku sampai <Opt /></Label>
            <KNDatePicker data-testid="pl-input-until" value={validUntil} onChange={setValidUntil} />
          </div>
        </div>
        <div>
          <Label>Catatan <Opt /></Label>
          <input data-testid="pl-input-note" className="field py-2 text-[13px]"
            placeholder="Mis. penyesuaian harga triwulan 3" value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        <p className="text-[10.5px] text-[#8E8E93]">
          Harga lama tidak hilang: ia ditutup pada tanggal mulai harga baru dan tetap
          terlihat di riwayat.
        </p>
      </div>
    </FormModal>
  );
}

// ─── Riwayat Harga Modal ─────────────────────────────────────────────────────
export function HistoryModal({ row, entityId, entities, canManage, onClose, onChanged }) {
  const [records, setRecords] = useState([]);
  const pgRec = usePagedRows(records, { pageSize: 25, testId: "pricelist-records-pager" });
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const res = await axios.get(`${API}/pricelist/records`,
        { params: { product_id: row.product_id, entity_id: entityId } });
      setRecords(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setErr(e.response?.data?.detail || "Gagal memuat riwayat.");
    } finally {
      setLoading(false);
    }
  }, [row.product_id, entityId]);

  useEffect(() => { load(); }, [load]);

  const deactivate = async (id) => {
    try {
      await axios.delete(`${API}/pricelist/${id}`);
      load(); onChanged();
    } catch (e) {
      setErr(e.response?.data?.detail || "Gagal menonaktifkan harga.");
    }
  };

  return (
    <FormModal open onClose={onClose} size="md" icon={History} title={`Riwayat harga · ${row.product_name}`}
      subtitle={<EntityBadge entityId={entityId} entities={entities} />} testId="pl-history-modal"
      footer={(
        <div className="flex justify-end">
          <button type="button" className="primary-button" onClick={onClose}>Tutup</button>
        </div>
      )}>
      <ErrorNotice message={err} onRetry={load} onDismiss={() => setErr("")} testId="pl-history-error" />
      {loading ? (
        <div className="grid gap-2">{[0, 1, 2].map((i) => <div key={i} className="h-9 animate-pulse rounded bg-[#F5F5F7]" />)}</div>
      ) : records.length === 0 ? (
        <div data-testid="pl-history-empty" className="py-8 text-center text-[12px] text-[#8E8E93]">
          Belum ada harga khusus badan usaha untuk produk ini — memakai harga global {formatCurrency(row.global_price)}.
        </div>
      ) : (
        <div className="overflow-auto rounded-md border border-[#EFF0F2]">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-[#EFF0F2] bg-[#FAFBFC] text-left text-[10px] font-bold uppercase text-[#8E8E93]">
                <th className="px-3 py-2 text-right">Harga</th>
                <th className="px-3 py-2">Mulai</th>
                <th className="px-3 py-2">Sampai</th>
                <th className="px-3 py-2 text-center">Status</th>
                <th className="px-3 py-2">Catatan</th>
                {canManage && <th className="px-3 py-2"></th>}
              </tr>
            </thead>
            <caption className="caption-bottom px-3 py-2">{records.length > 25 && pgRec.pager}</caption>
            <tbody>
              {pgRec.pageRows.map((r) => {
                const sm = STATUS_META[r.effective_status] || STATUS_META.inactive;
                return (
                  <tr key={r.id} data-testid={`pl-hist-row-${r.id}`} className="border-b border-[#F5F5F7] last:border-0">
                    <td className="px-3 py-2 text-right font-semibold tabular-nums text-[#6B219A]">{formatCurrency(r.sell_price)}</td>
                    <td className="px-3 py-2">{fmtDate(r.valid_from)}</td>
                    <td className="px-3 py-2">{r.valid_until ? fmtDate(r.valid_until) : "∞"}</td>
                    <td className="px-3 py-2 text-center">
                      <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${sm.tone}`}>{sm.label}</span>
                    </td>
                    <td className="max-w-[160px] truncate px-3 py-2 text-[#6B6B73]" title={r.note}>{r.note || "—"}</td>
                    {canManage && (
                      <td className="px-3 py-2 text-right">
                        {r.status !== "inactive" && (
                          <button data-testid={`pl-deactivate-${r.id}`} className="text-[11px] text-[#C0392B] hover:underline"
                            onClick={() => deactivate(r.id)}>Nonaktifkan</button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </FormModal>
  );
}
