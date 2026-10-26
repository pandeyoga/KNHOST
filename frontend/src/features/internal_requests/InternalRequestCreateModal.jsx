/**
 * InternalRequestCreateModal — FASE E-7 (E7d).
 *
 * Dipakai DUA tempat dengan satu bentuk yang sama:
 *   1. tombol “Minta dari badan usaha lain” pada **Papan Stok** (isyarat E5.1), dan
 *   2. tombol “Permintaan Baru” pada layar Permintaan Internal.
 *
 * Yang disengaja di sini:
 *  - **Sales tidak memilih badan usaha sumber.** Rincian stok PT lain bukan
 *    wewenangnya (keputusan pemilik di E5.1); yang ditampilkan hanya ANGKA gabungan
 *    “tersedia di badan usaha lain”. Admin/manajer yang memilih sumbernya nanti.
 *  - **Alasan wajib** (≥5 huruf): permintaan ini menggerakkan barang milik badan
 *    usaha lain, jadi sebabnya harus terbaca oleh yang menindak.
 *  - Nilai yang tampil ditandai **taksiran** — harga final memakai kontrak internal.
 */
import KNDatePicker from "@/components/KNDatePicker";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeftRight, Plus, Trash2, Info } from "lucide-react";
import FormModal from "../../components/FormModal";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { apiText, createInternalRequest, productAvailability } from "./internalRequestsApi";

export default function InternalRequestCreateModal({
  open, prefillProductId = "", prefillQty = "", onClose, onCreated,
}) {
  const [products, setProducts] = useState([]);
  const [lines, setLines] = useState([]);
  const [pick, setPick] = useState("");
  const [reason, setReason] = useState("");
  const [neededDate, setNeededDate] = useState("");
  const [notes, setNotes] = useState("");
  const [orders, setOrders] = useState([]);
  const [orderId, setOrderId] = useState("");
  const [avail, setAvail] = useState({});          // product_id -> ketersediaan
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const loadAvail = useCallback(async (pid) => {
    if (!pid || avail[pid]) return;
    try {
      const a = await productAvailability(pid);
      setAvail((prev) => ({ ...prev, [pid]: a }));
    } catch { /* isyarat opsional — jangan mematikan formulir */ }
  }, [avail]);

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const [p, so] = await Promise.all([
          axios.get(`${API}/products`).catch(() => ({ data: [] })),
          axios.get(`${API}/sales-orders`, { params: { limit: 50 } }).catch(() => ({ data: [] })),
        ]);
        setProducts(Array.isArray(p.data) ? p.data : (p.data?.items || []));
        const soRows = Array.isArray(so.data) ? so.data : (so.data?.items || []);
        setOrders(soRows.filter((s) => !["cancelled", "completed"].includes(s.status)));
      } catch (e) { setErr(apiText(e, "Gagal memuat data master.")); }
    })();
  }, [open]);

  // Prefill dari papan stok: produknya sudah jelas, tinggal jumlah & alasan.
  useEffect(() => {
    if (!open) return;
    if (prefillProductId) {
      setLines([{ product_id: prefillProductId, quantity: prefillQty || "", notes: "" }]);
      loadAvail(prefillProductId);
    } else {
      setLines([]);
    }
    setReason(""); setNeededDate(""); setNotes(""); setOrderId(""); setErr("");
  }, [open, prefillProductId, prefillQty]); // eslint-disable-line

  const productOptions = useMemo(() => products.map((p) => ({
    value: p.id, label: `${p.sku} — ${p.name}`,
  })), [products]);

  const orderOptions = useMemo(() => [
    { value: "", label: "— Tanpa pesanan (stok sendiri) —" },
    ...orders.map((s) => ({ value: s.id, label: `${s.number} · ${s.customer_name || ""}` })),
  ], [orders]);

  const prodOf = (pid) => products.find((p) => p.id === pid) || {};

  function addLine() {
    if (!pick) return;
    if (lines.some((l) => l.product_id === pick)) { setErr("Barang itu sudah ada di daftar."); return; }
    setLines([...lines, { product_id: pick, quantity: "", notes: "" }]);
    loadAvail(pick);
    setPick(""); setErr("");
  }

  const estTotal = lines.reduce((s, l) => {
    const p = prodOf(l.product_id);
    return s + (Number(p.harga_pokok || p.price || 0) * (Number(l.quantity) || 0));
  }, 0);

  async function submit() {
    if (lines.length === 0) { setErr("Tambahkan minimal satu barang."); return; }
    if (lines.some((l) => !(Number(l.quantity) > 0))) { setErr("Isi jumlah setiap barang (lebih dari 0)."); return; }
    if (reason.trim().length < 5) { setErr("Alasan wajib diisi minimal 5 huruf — yang menindak perlu tahu sebabnya."); return; }
    setBusy(true); setErr("");
    try {
      const doc = await createInternalRequest({
        items: lines.map((l) => ({ product_id: l.product_id, quantity: Number(l.quantity), notes: l.notes })),
        reason: reason.trim(),
        needed_date: neededDate,
        notes,
        source_order_id: orderId,
      });
      onCreated?.(doc);
    } catch (e) {
      setErr(apiText(e, "Gagal mengajukan permintaan internal."));
    } finally { setBusy(false); }
  }

  if (!open) return null;

  // Fase 3 · P3 (L-03, prasyarat D-27 P7) — `.modal-card` buatan sendiri → FormModal baku: layar penuh 1 kolom di HP,
  // Esc/latar aman (INV-UI-01/10), galat di kaki pop-up dekat tombol Ajukan. Isian & aturan tidak berubah.
  return (
    <FormModal open onClose={onClose} size="md" icon={ArrowLeftRight} testId="pin-create-modal"
      title="Minta Barang dari Badan Usaha Lain" busy={busy} error={err} onSubmit={submit}
      footer={(
        <div className="flex items-center justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy} data-testid="pin-create-cancel">Batal</button>
          <button type="submit" data-testid="pin-create-submit" className="primary-button" disabled={busy}>
            {busy ? "Mengajukan…" : "Ajukan Permintaan"}
          </button>
        </div>
      )}>
        <div className="space-y-3">
          <div className="flex items-start gap-2 rounded-lg border border-[#C9DBF7] bg-[#F2F7FF] px-3 py-2">
            <Info size={14} className="mt-0.5 shrink-0 text-[#0058CC]" />
            <p className="text-[11px] leading-relaxed text-[#1C1C1E]">
              Permintaan ini masuk <b>antrean admin/manajer</b>. Merekalah yang menentukan
              barang diambil dari badan usaha mana, lalu mengubahnya menjadi
              <b> transaksi Antar Entitas</b> — dokumen kembar di kedua badan usaha, harga
              dari kontrak internal, dan margin grup ikut dieliminasi di konsolidasi.
              Anda akan mendapat notifikasi hasilnya.
            </p>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">Tambah Barang <span className="text-red-500">*</span> <span className="font-normal text-[#8E8E93]">(min. 1 barang)</span></label>
            <div className="flex gap-2">
              <KNSelect data-testid="pin-product-pick" className="field flex-1" value={pick}
                onValueChange={(v) => { setPick(v); loadAvail(v); }}
                options={productOptions} placeholder="Pilih barang…" />
              <button type="button" data-testid="pin-add-line" className="secondary-button" onClick={addLine}>
                <Plus size={13} /> Tambah
              </button>
            </div>
          </div>

          {lines.length > 0 && (
            <div className="rounded-lg border border-[#EFF0F2] overflow-hidden" data-testid="pin-lines">
              {/* UAT 24 Okt (audit UI tahap 2) — di HP grid 4 kolom memotong nama & SKU; < 640px baris jadi dua tingkat
                  (nama penuh di atas; jumlah + satuan · catatan · hapus di bawah), kepala kolom disembunyikan. */}
              <div className="hidden grid-cols-[1.6fr_130px_1fr_36px] bg-[#FAFBFC] px-2.5 py-1.5 text-[10px] font-bold uppercase text-[#6B6B73] sm:grid">
                <span>Barang</span><span className="text-right">Jumlah *</span><span>Catatan</span><span />
              </div>
              {lines.map((l, i) => {
                const p = prodOf(l.product_id);
                const a = avail[l.product_id];
                const other = a?.other_entities_available ?? null;
                const tooMuch = other !== null && Number(l.quantity) > Number(other);
                return (
                  <div key={l.product_id} data-testid={`pin-line-${l.product_id}`}
                       className="grid grid-cols-[1fr_1fr_36px] items-center gap-1 border-t border-[#F4F5F7] px-2.5 py-2 sm:grid-cols-[1.6fr_130px_1fr_36px]">
                    <div className="col-span-3 min-w-0 sm:col-span-1">
                      <p className="text-[11.5px] font-semibold break-words sm:truncate">{p.name || l.product_id}</p>
                      <p className="text-[10px] text-[#8E8E93]">
                        {p.sku}{a ? ` · tersedia di badan usaha lain: ${formatQty(other)} ${p.base_unit || ""}` : ""}
                      </p>
                      {tooMuch && (
                        <p data-testid={`pin-line-warn-${l.product_id}`} className="text-[10px] font-semibold text-[#8A5300]">
                          Jumlah melebihi yang tersedia di badan usaha lain ({formatQty(other)}) —
                          sisanya perlu dibeli ke pemasok.
                        </p>
                      )}
                    </div>
                    <div className="relative">
                      <input data-testid={`pin-qty-${l.product_id}`} type="number" min="0" step="0.01" aria-label="Jumlah"
                        className={`field text-right ${p.base_unit ? "pr-12" : ""}`} value={l.quantity}
                        onChange={(e) => setLines(lines.map((x, ix) => ix === i ? { ...x, quantity: e.target.value } : x))} />
                      {p.base_unit && <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10.5px] font-semibold text-[#8E8E93]">{p.base_unit}</span>}
                    </div>
                    <input data-testid={`pin-note-${l.product_id}`} className="field" value={l.notes} aria-label="Catatan"
                      placeholder="Catatan"
                      onChange={(e) => setLines(lines.map((x, ix) => ix === i ? { ...x, notes: e.target.value } : x))} />
                    <button type="button" className="icon-button text-red-500" aria-label="Hapus baris"
                      data-testid={`pin-del-${l.product_id}`}
                      onClick={() => setLines(lines.filter((_, ix) => ix !== i))}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })}
              <div className="flex items-center justify-between border-t border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-2">
                <span className="text-[10.5px] text-[#6B6B73]">
                  Taksiran nilai (HPP/harga master × jumlah) — <b>bukan harga final</b>;
                  harga sebenarnya memakai kontrak internal.
                </span>
                <span data-testid="pin-est-total" className="text-[12px] font-bold tabular-nums">
                  ≈ {formatCurrency(estTotal)}
                </span>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">
                Alasan <span className="text-red-500">*</span>
              </label>
              <input data-testid="pin-reason" className="field" value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="mis. stok kosong, pesanan pelanggan menunggu…" />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">Dibutuhkan Sebelum</label>
              <KNDatePicker data-testid="pin-needed-date" value={neededDate} onChange={setNeededDate} />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">Untuk Pesanan (opsional)</label>
              <KNSelect data-testid="pin-order" className="field" value={orderId}
                onValueChange={setOrderId} options={orderOptions} placeholder="— Tanpa pesanan —" />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">Catatan</label>
              <input data-testid="pin-notes" className="field" value={notes}
                onChange={(e) => setNotes(e.target.value)} placeholder="opsional…" />
            </div>
          </div>
        </div>
    </FormModal>
  );
}
