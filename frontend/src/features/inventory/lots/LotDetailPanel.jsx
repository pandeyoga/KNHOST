/**
 * LotDetailPanel (FASE C · D-10) — panel detail lot dengan 4 tab:
 * Ringkasan (identitas + status + aksi) · Roll · Silsilah · Recall.
 * Dipisah dari view utama agar tiap file di bawah batas guardrail (<500 baris).
 */
import { useEffect, useState } from "react";
import { AlertTriangle, GitBranch, Layers3, ListOrdered, Printer, RefreshCw, Save, Scissors,
         Merge, Repeat, ShieldCheck, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatDateTime, formatQty } from "../../../utils/formatters";
import { entityShortFromCtx } from "../../../utils/entityLabel";
import { rollStatusLabel } from "../../wms/inventory/inventoryConstants";
import { reprintRollLabel, printRollLabelsBulk } from "../../../utils/rollLabels";
import LotGenealogyTree from "./LotGenealogyTree";
import LotRecallPanel from "./LotRecallPanel";
import { LotSourcePill, LotStatusPill } from "./LotParts";
import PageTabs from "../../../components/PageTabs";
import { lotApi, shortDateTime } from "./lotApi";

// UAT 24 Okt (audit UI tahap 2) — dulu "Dokumen sumber: cycle_count_found" (kode mentah) bila lot tanpa nomor dokumen.
const SOURCE_REF_LABEL = {
  cycle_count_found: "Temuan stock opname",
  initial: "Stok awal",
  legacy_roll: "Roll lama (migrasi)",
  makloon_order: "Order makloon",
  manual: "Input manual",
  sales_return: "Retur penjualan",
  transfer: "Transfer gudang",
  wms_task: "Tugas penerimaan gudang",
  purchase_order: "Pesanan pembelian (PO)",
  grn: "Penerimaan barang (GRN)",
  production: "Produksi",
};
const sourceRefText = (ref) => {
  const r = ref || {};
  return r.number || SOURCE_REF_LABEL[r.type] || (r.type ? String(r.type).replace(/_/g, " ") : "—");
};
// Roll terikat: nomor dokumen bila ada; id teknis (so_…) hanya di tooltip.
const BOUND_TYPE = { sales_order: "Pesanan penjualan", sample_order: "Pesanan sample", transfer: "Transfer", makloon_order: "Order makloon" };
const boundText = (r) => {
  const ref = (r.reserved_ref && r.reserved_ref.id) ? r.reserved_ref : (r.earmarked_for || {});
  if (!ref.id && !ref.number) return "—";
  return ref.number || BOUND_TYPE[ref.type] || "Terikat dokumen";
};
// Peringatan server menyebut nama kolom ("Nomor lot supplier (supplier_lot) belum diisi") — buang nama kolomnya.
const cleanWarning = (w) => String(w || "").replace(/\s*\((?:supplier_lot|dye_lot|shade_ref)\)/g, "");

const TABS = [
  { id: "ringkasan", label: "Ringkasan" },
  { id: "rolls", label: "Roll" },
  { id: "silsilah", label: "Silsilah" },
  { id: "recall", label: "Recall" },
];

export default function LotDetailPanel({
  lot, loading, genealogy, genealogyLoading, recall, recallLoading,
  tab, setTab, onClose, onRefresh, onOpenLot, canEdit, labelOf, warehouses = [],
  onSaveIdentity, onSplit, onMerge, onRework, onStatus, onLabel, savingIdentity, saveMsg,
}) {
  const [draft, setDraft] = useState({ supplier_lot: "", dye_lot: "", shade_ref: "", note: "", internal_alias: "", reason: "" });
  const [queueBusy, setQueueBusy] = useState(false);
  const [queueInfo, setQueueInfo] = useState("");
  const queueLabels = async () => {
    setQueueBusy(true); setQueueInfo("");
    try {
      const { data } = await axios.post(`${API}/rfid/print-jobs`, { roll_ids: (lot?.rolls || []).map((r) => r.id), kind: "qr_label", source: `lot:${lot?.id}` });
      setQueueInfo(`Antrean ${data.job_number} · ${data.item_count} label.`);
    } catch (e) { const d = e.response?.data?.detail; setQueueInfo((d && (d.message || d)) || "Gagal mengantrekan."); }
    finally { setQueueBusy(false); }
  };

  // UAT 24 Okt (audit UI tahap 2) — gudang/bin tampil sebagai id teknis ("wh_jakarta", "bin_sim_wh_jkt_w11_l1_01").
  // Nama gudang dari daftar yang sudah dimuat; kode bin dari peta lokasi gudang (dimuat sekali per gudang lot ini).
  const [binCodes, setBinCodes] = useState({});
  const whIds = [...new Set([lot?.warehouse_id, ...(lot?.rolls || []).flatMap((r) => [r.warehouse_id, r.last_scan?.warehouse_id])]
    .filter(Boolean))].sort().join(",");
  useEffect(() => {
    if (!whIds) return undefined;
    let alive = true;
    Promise.all(whIds.split(",").map((w) => axios.get(`${API}/warehouses/${w}/locations`)
      .then((r) => r.data?.bins || []).catch(() => [])))
      .then((lists) => {
        if (!alive) return;
        const map = {};
        lists.flat().forEach((b) => { if (b?.bin_id) map[b.bin_id] = b.code || b.path || b.bin_id; });
        setBinCodes(map);
      });
    return () => { alive = false; };
  }, [whIds]);
  const whName = (id) => (id ? (warehouses.find((w) => w.id === id)?.name || id) : "—");
  const binName = (id) => (id ? (binCodes[id] || id) : "");

  useEffect(() => {
    setDraft({
      supplier_lot: lot?.supplier_lot || "", dye_lot: lot?.dye_lot || "",
      shade_ref: lot?.shade_ref || "", note: lot?.note || "", internal_alias: lot?.internal_alias || "", reason: "",
    });
  }, [lot?.id, lot?.supplier_lot, lot?.dye_lot, lot?.shade_ref, lot?.note, lot?.internal_alias]);

  if (!lot) return null;
  const rolls = lot.rolls || [];
  const warnings = lot.warnings || [];

  return (
    <div data-testid="lot-detail-panel" className="rounded-md border border-[#0058CC]/25 bg-white shadow-[0_6px_20px_rgba(20,28,45,0.08)]">
      {/* Kepala */}
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[#EFF0F2] bg-[#F7FAFF] px-2.5 py-2">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[13px] font-bold text-[#1C1C1E]">
            <Layers3 size={14} className="text-[#0058CC]" /> {lot.lot_number}
            <LotStatusPill value={lot.lot_status} label={labelOf("lot_status", lot.lot_status)}
              testId="lot-detail-status" />
            <LotSourcePill value={lot.source} label={labelOf("lot_source", lot.source)} />
          </p>
          <p className="text-[10.5px] text-[#6B6B73]">
            {lot.sku} · {lot.product_name} · {labelOf("stage", lot.stage)} ·{" "}
            {labelOf("fabric_type", lot.fabric_type)} · {lot.roll_count} roll ·{" "}
            sisa <b>{formatQty(lot.qty_remaining)} {lot.unit}</b>
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button data-testid="lot-detail-refresh" className="icon-button" onClick={onRefresh}
            aria-label="Muat ulang lot"><RefreshCw size={13} /></button>
          <button data-testid="lot-detail-close" className="icon-button" onClick={onClose}
            aria-label="Tutup detail"><X size={14} /></button>
        </div>
      </div>

      {/* Aksi */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-[#EFF0F2] px-2.5 py-1.5">
        {canEdit && (
          <>
            <button data-testid="lot-action-split" className="btn-secondary !px-2 !py-1 !text-[10.5px]"
              disabled={rolls.length < 2} onClick={onSplit}
              title={rolls.length < 2 ? "Butuh minimal 2 roll untuk split" : "Pecah sebagian roll ke lot anak"}>
              <span className="flex items-center gap-1"><Scissors size={11} /> Split</span>
            </button>
            <button data-testid="lot-action-merge" className="btn-secondary !px-2 !py-1 !text-[10.5px]"
              onClick={onMerge} title="Gabungkan dengan lot lain (produk & pemilik sama)">
              <span className="flex items-center gap-1"><Merge size={11} /> Merge</span>
            </button>
            <button data-testid="lot-action-rework" className="btn-secondary !px-2 !py-1 !text-[10.5px]"
              onClick={onRework} title="Bentuk lot anak hasil proses ulang">
              <span className="flex items-center gap-1"><Repeat size={11} /> Rework</span>
            </button>
            <button data-testid="lot-action-status" className="btn-secondary !px-2 !py-1 !text-[10.5px]"
              onClick={onStatus} title="Ubah status mutu lot">
              <span className="flex items-center gap-1"><ShieldCheck size={11} /> Status</span>
            </button>
          </>
        )}
        <button data-testid="lot-action-label" className="btn-secondary !px-2 !py-1 !text-[10.5px]"
          onClick={onLabel} title="Cetak label / QR lot">
          <span className="flex items-center gap-1"><Printer size={11} /> Label / QR</span>
        </button>
        <button data-testid="lot-action-print-roll-labels" className="btn-secondary !px-2 !py-1 !text-[10.5px]"
          disabled={rolls.length === 0} onClick={() => printRollLabelsBulk(rolls.map((r) => ({ ...r, product_name: lot.product_name, lot: lot.lot_number, supplier_lot: r.supplier_lot || lot.supplier_lot, supplier_dn_number: r.supplier_dn_number || (lot.supplier_dn_numbers || []).join(", "), dye_lot: r.dye_lot || lot.dye_lot })))}
          title="Cetak label QR semua roll di lot ini (58×40 mm per roll)">
          <span className="flex items-center gap-1"><Printer size={11} /> Label {rolls.length} roll</span>
        </button>
        <button data-testid="lot-action-queue-roll-labels" className="btn-secondary !px-2 !py-1 !text-[10.5px]"
          disabled={rolls.length === 0 || queueBusy} onClick={queueLabels}
          title="Kirim label QR semua roll ke antrean printer gudang">
          <span className="flex items-center gap-1"><ListOrdered size={11} /> {queueBusy ? "Mengantrekan…" : "Antrean printer"}</span>
        </button>
        {queueInfo && <span className="text-[10.5px] text-[#6B6B73]" data-testid="lot-action-queue-info">{queueInfo}</span>}
      </div>

      {/* Fase 4 · R3 (L-01) — tab rincian dulu pil biru bercampur tombol aksi di bilah yang sama; kini PageTabs baku di
          barisnya sendiri (garis bawah, satu baris bergulir di HP). Testid `lot-tab-<id>` tetap. */}
      <PageTabs className="px-2.5" value={tab} onChange={setTab} ariaLabel="Rincian lot" testId="lot-tabs"
        tabTestId={(k) => `lot-tab-${k}`} tabs={TABS.map((t) => ({ key: t.id, label: t.label }))} />

      <div className="px-2.5 py-2">
        {loading && <p data-testid="lot-detail-loading" className="py-4 text-center text-[11px] text-[#6B6B73]">Memuat detail lot…</p>}

        {!loading && tab === "ringkasan" && (
          <div className="space-y-2" data-testid="lot-tabpanel-ringkasan">
            {warnings.length > 0 && (
              <div data-testid="lot-detail-warnings" className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1.5">
                {warnings.map((w) => (
                  <p key={w} className="flex items-start gap-1.5 text-[10.5px] text-amber-800">
                    <AlertTriangle size={11} className="mt-[2px] shrink-0" /> {cleanWarning(w)}
                  </p>
                ))}
              </div>
            )}
            <div className="grid grid-cols-2 gap-1.5 md:grid-cols-4">
              {[["Pemilik (badan usaha)", lot.owner_entity_name || entityShortFromCtx(lot.owner_entity_id, "—")],
                ["Gudang", lot.warehouse_name || whName(lot.warehouse_id)],
                ["Supplier", lot.supplier_name || "—"],
                ["Dokumen sumber", sourceRefText(lot.source_ref)],
                ["Qty awal", `${formatQty(lot.qty_initial)} ${lot.unit}`],
                ["Sisa tersedia", `${formatQty(lot.qty_available)} ${lot.unit}`],
                ["Roll aktif", `${lot.active_roll_count ?? 0} / ${lot.roll_count ?? 0}`],
                ["Dibuat", `${shortDateTime(lot.created_at)} · ${lot.created_by_name || lot.created_by || "—"}`],
              ].map(([k, v]) => (
                <div key={k} className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-2 py-1.5">
                  <p className="text-[9px] font-bold uppercase tracking-wide text-[#8E8E93]">{k}</p>
                  <p className="truncate text-[11px] font-semibold" title={String(v)}>{v}</p>
                </div>
              ))}
            </div>

            {(lot.legacy_lot_codes || []).length > 0 && (
              <p data-testid="lot-detail-legacy" className="text-[10.5px] text-[#6B6B73]">
                Kode lot lama (jejak migrasi): <b>{(lot.legacy_lot_codes || []).join(", ")}</b>
              </p>
            )}

            <div className="rounded-md border border-[#EFF0F2]">
              <div className="border-b border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">
                Identitas lot (dipakai label, silsilah, dan recall)
              </div>
              <p className="px-2.5 pt-2 text-[10.5px] text-[#3C3C43]" data-testid="lot-canonical-number">
                Nomor lot internal (kanonik, tidak bisa diubah): <b className="font-mono">{lot.lot_number}</b>
                {lot.supplier_lot ? <> · LOT pabrik <b className="font-mono" data-testid="lot-supplier-lot-view">{lot.supplier_lot}</b></> : null}
                {lot.internal_alias ? <> · LOT KN <b data-testid="lot-alias-view">{lot.internal_alias}</b></> : null}
                {(lot.supplier_dn_numbers || []).length ? <> · SJ supplier <b className="font-mono" data-testid="lot-supplier-dn-view">{lot.supplier_dn_numbers.join(", ")}</b></> : null}
              </p>
              <div className="grid gap-2 px-2.5 py-2 md:grid-cols-2">
                {[["supplier_lot", "LOT pabrik (supplier)", "mis. 234"],
                  ["dye_lot", "Dye lot / batch warna", "mis. DL-RED-01"],
                  ["shade_ref", "Referensi shade", "mis. SHADE-A / Pantone 18-1663"],
                  ["note", "Catatan", "mis. hasil kiriman kedua supplier A"],
                  ["internal_alias", "LOT KN (diisi pengguna)", "mis. KN A"],
                  ["reason", "Alasan perubahan identitas", "wajib bila lot sudah berisi roll"]].map(([k, label, ph]) => (
                  <label key={k} className="grid gap-1">
                    <span className="text-[9.5px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</span>
                    <input data-testid={`lot-edit-${k}`} className="field" disabled={!canEdit}
                      value={draft[k]} placeholder={ph}
                      onChange={(e) => setDraft({ ...draft, [k]: e.target.value })} />
                  </label>
                ))}
              </div>
              {canEdit && (
                <div className="flex items-center gap-2 border-t border-[#EFF0F2] px-2.5 py-1.5">
                  <button data-testid="lot-edit-save" className="primary-button !px-2.5 !py-1 !text-[10.5px]"
                    disabled={savingIdentity} onClick={() => onSaveIdentity(draft)}>
                    <span className="flex items-center gap-1">
                      <Save size={11} /> {savingIdentity ? "Menyimpan…" : "Simpan Identitas Lot"}
                    </span>
                  </button>
                  {saveMsg && <span data-testid="lot-edit-msg" className="text-[10.5px] font-semibold text-emerald-600">{saveMsg}</span>}
                </div>
              )}
            </div>

            <LotIdentityHistory items={lot.identity_history || []} />

            <div className="grid gap-2 md:grid-cols-2">
              <div className="rounded-md border border-[#EFF0F2]">
                <div className="border-b border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">
                  Riwayat status mutu
                </div>
                <div className="max-h-[160px] divide-y divide-[#F5F5F7] overflow-y-auto" data-testid="lot-status-history">
                  {(lot.status_history || []).slice().reverse().map((h, i) => (
                    <div key={i} className="px-2.5 py-1.5 text-[10.5px]">
                      <span className="font-semibold">{labelOf("lot_status", h.status)}</span>
                      {h.status_before && <span className="text-[#8E8E93]"> ← {labelOf("lot_status", h.status_before)}</span>}
                      <span className="block text-[9.5px] text-[#8E8E93]">
                        {shortDateTime(h.timestamp)} · {h.user || "—"}{h.reason ? ` · ${h.reason}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-md border border-[#EFF0F2]">
                <div className="flex items-center gap-1.5 border-b border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5">
                  <GitBranch size={11} className="text-[#0058CC]" />
                  <span className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Relasi langsung</span>
                </div>
                <div className="space-y-1.5 px-2.5 py-2 text-[10.5px]" data-testid="lot-direct-relations">
                  <p><b>Induk:</b>{" "}
                    {(lot.parents || []).length === 0 ? <span className="text-[#8E8E93]">tidak ada</span>
                      : (lot.parents || []).map((p) => (
                        <button key={p.id} data-testid={`lot-parent-${p.id}`}
                          className="mr-1 rounded-full border border-[#E5E5EA] px-1.5 py-0.5 text-[10px] hover:border-[#0058CC]"
                          onClick={() => onOpenLot(p.id)}>{p.lot_number}</button>))}
                  </p>
                  <p><b>Turunan:</b>{" "}
                    {(lot.children || []).length === 0 ? <span className="text-[#8E8E93]">tidak ada</span>
                      : (lot.children || []).map((c) => (
                        <button key={c.id} data-testid={`lot-child-${c.id}`}
                          className="mr-1 rounded-full border border-[#E5E5EA] px-1.5 py-0.5 text-[10px] hover:border-[#0058CC]"
                          onClick={() => onOpenLot(c.id)}>{c.lot_number}</button>))}
                  </p>
                  {(lot.process || {}).process_type && (
                    <p><b>Proses pembentuk:</b> {labelOf("process_type", lot.process.process_type)}
                      {lot.process.partner_name ? ` · ${lot.process.partner_name}` : ""}</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {!loading && tab === "rolls" && (
          <div data-testid="lot-tabpanel-rolls" className="overflow-x-auto">
            {rolls.length === 0 ? (
              <p data-testid="lot-rolls-empty" className="py-6 text-center text-[11px] text-[#6B6B73]">
                Lot ini tidak lagi memiliki roll (mis. seluruh roll sudah pindah ke lot turunan
                setelah split/merge/rework). Lihat tab <b>Silsilah</b> untuk menelusuri.
              </p>
            ) : (
              <table className="w-full min-w-[620px] text-[11px]">
                <thead>
                  <tr className="border-b border-[#EFF0F2] bg-[#FAFBFC] text-left text-[9.5px] uppercase tracking-wide text-[#8E8E93]">
                    <th className="px-2 py-1.5 font-bold">Roll</th>
                    <th className="px-2 py-1.5 font-bold">Status</th>
                    <th className="px-2 py-1.5 font-bold">Grade</th>
                    <th className="px-2 py-1.5 text-right font-bold">Awal</th>
                    <th className="px-2 py-1.5 text-right font-bold">Sisa</th>
                    <th className="px-2 py-1.5 font-bold">Gudang / Bin</th>
                    <th className="px-2 py-1.5 font-bold">Dye lot</th>
                    <th className="px-2 py-1.5 font-bold">Terikat</th>
                    <th className="px-2 py-1.5 font-bold">Terakhir dipindai</th>
                    <th className="px-2 py-1.5 font-bold">Label</th>
                  </tr>
                </thead>
                <tbody>
                  {rolls.map((r) => (
                    <tr key={r.id} data-testid={`lot-roll-${r.id}`} className="border-b border-[#F5F5F7] last:border-0">
                      <td className="px-2 py-1.5 font-semibold">{r.roll_no}</td>
                      <td className="px-2 py-1.5"><span className="status-pill pill-muted">{rollStatusLabel(r.status)}</span></td>
                      <td className="px-2 py-1.5">{r.grade || "—"}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{formatQty(r.length_initial)}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{formatQty(r.length_remaining)} {r.unit}</td>
                      <td className="px-2 py-1.5">{whName(r.warehouse_id)}{r.bin_id ? ` / ${binName(r.bin_id)}` : ""}</td>
                      <td className="px-2 py-1.5">{r.dye_lot || "—"}</td>
                      <td className="px-2 py-1.5 text-[10px] text-[#6B6B73]" title={(r.reserved_ref || {}).id || (r.earmarked_for || {}).id || ""}>
                        {boundText(r)}
                      </td>
                      <td className="px-2 py-1.5 text-[10px] text-[#3C3C43]" data-testid={`lot-roll-last-scan-${r.id}`}>
                        {r.last_scan ? `${r.last_scan.warehouse_id ? whName(r.last_scan.warehouse_id) : ""}${r.last_scan.bin_id ? ` · bin ${binName(r.last_scan.bin_id)}` : ""} · ${formatDateTime(r.last_scan.at)}` : "—"}
                      </td>
                      <td className="px-2 py-1.5">
                        <button type="button" className="icon-button" data-testid={`lot-roll-reprint-${r.id}`}
                          aria-label={`Cetak ulang label QR ${r.roll_no}`} title="Cetak ulang label QR (rusak/hilang)"
                          onClick={() => reprintRollLabel({ ...r, lot: lot.lot_number, supplier_lot: r.supplier_lot || lot.supplier_lot, supplier_dn_number: r.supplier_dn_number || (lot.supplier_dn_numbers || []).join(", "), dye_lot: r.dye_lot || lot.dye_lot }, lot.product_name)}>
                          <Printer size={12} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {!loading && tab === "silsilah" && (
          <div data-testid="lot-tabpanel-silsilah">
            <LotGenealogyTree data={genealogy} loading={genealogyLoading}
              onOpenLot={onOpenLot} labelOf={labelOf} />
          </div>
        )}

        {!loading && tab === "recall" && (
          <div data-testid="lot-tabpanel-recall">
            <LotRecallPanel data={recall} loading={recallLoading} />
          </div>
        )}
      </div>
    </div>
  );
}

const FIELD_LABEL = { supplier_lot: "Lot supplier", dye_lot: "Dye lot", supplier_id: "Supplier", supplier_name: "Nama supplier", internal_alias: "Alias internal" };

// LN-014 — riwayat pemetaan identitas lot (sebelum → sesudah, alasan, pengubah).
function LotIdentityHistory({ items }) {
  if (!items.length) return null;
  return (
    <div className="rounded-md border border-[#EFF0F2]" data-testid="lot-identity-history">
      <div className="border-b border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Riwayat identitas lot</div>
      <div className="max-h-[160px] divide-y divide-[#F5F5F7] overflow-y-auto">
        {items.slice().reverse().map((h, i) => (
          <div key={i} className="px-2.5 py-1.5 text-[10.5px]">
            <b>{FIELD_LABEL[h.field] || h.field}</b>: {h.before || "—"} → {h.after || "—"}
            <span className="text-[#6B6B73]"> · {h.by} · {formatDateTime(h.at)}{h.reason ? ` · ${h.reason}` : ""}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
