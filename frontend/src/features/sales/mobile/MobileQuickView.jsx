import { useEffect, useMemo, useState } from "react";
import { X, Plus, Minus, ShoppingBag, Scissors } from "lucide-react";
import { formatCurrency, formatQty } from "../../../utils/formatters";
import { convFactor } from "../../../utils/uom";
import { pickPrice } from "../../../hooks/useEffectivePrices";
import { variantLabel, mergedLineTotal, ownStockText } from "../../../utils/variants";
import VariantAxisPicker from "../../../components/VariantAxisPicker";
import { ProductGallery } from "../../../components/ProductGallery";
import RollPicker from "../../../components/RollPicker";
import RollReconcileSheet from "../../../components/RollReconcileSheet";
import { blocksOrder, lifecycleLabel, notOrderableReason } from "../../../utils/lifecycle";
import { sampleLimit, clampSampleQty, canSample } from "../../../utils/sampleOrder";
import SampleKindChooser from "../../../components/SampleKindChooser";

/** EPIC-VAR — bottom-sheet detail produk + pemilih varian (versi MOBILE).
 * SALES REVAMP V2: mode "Per yard" / "Beli per Roll"; inventory = total global saja.
 * FASE F: varian yang belum dirilis ke produksi tidak bisa ditambahkan. */
export default function MobileQuickView({ group, specialMap = {}, onAdd, onClose, entityId = "",
  rndEnforcement = "block", allowRollPick = true, customerId = "" }) {
  const variants = useMemo(() => group?.variants || [], [group]);
  const [selectedId, setSelectedId] = useState(null);
  const [qty, setQty] = useState(1);
  const [unit, setUnit] = useState("meter");
  const [mode, setMode] = useState("qty");
  const [showReconcile, setShowReconcile] = useState(false);
  const [kind, setKind] = useState("buy");   // "buy" | "sample" — sample = Pesanan Sample (SOS-) terpisah
  const [sampleKind, setSampleKind] = useState("standard");

  useEffect(() => {
    if (!group || variants.length === 0) return;
    const fa = variants.find((v) => Number(v.available_qty || 0) > 0) || variants[0];
    setSelectedId(fa.id); setQty(1); setUnit(fa.base_unit || "meter"); setMode("qty");
    setShowReconcile(false); setKind("buy"); setSampleKind("standard");
  }, [group?.key]); // eslint-disable-line react-hooks/exhaustive-deps

  const selected = useMemo(() => variants.find((v) => v.id === selectedId) || null, [variants, selectedId]);
  const axisMode = variants.length > 1;
  useEffect(() => { if (selected) setUnit(selected.base_unit || "meter"); }, [selectedId]); // eslint-disable-line

  if (!group || !variants.length) return null;
  const special = selected ? pickPrice(specialMap[selected.id], qty) : null;
  const isSpecial = !!(special && special.has_special);
  const baseUnit = selected?.base_unit || "";
  const factor = selected ? (convFactor(selected, unit) ?? 1) : 1;
  // F1b — harga dasar = harga EFEKTIF pelanggan, bukan harga umum produk.
  const effBase = special && special.price != null ? Number(special.price) : Number(selected?.price || 0);
  const unitPrice = isSpecial ? Number(special.price) : Math.round(effBase * factor * 100) / 100;
  const baseUnitPrice = effBase;
  const avail = Number(selected?.available_qty || 0);
  const rollCount = Number(selected?.roll_count || 0);
  const ownName = selected?.stock_entity_name || "";
  const lineTotal = special ? unitPrice * (Number(qty) || 0) : mergedLineTotal(selected, qty, unitPrice);
  const step = (d) => setQty((q) => (kind === "sample" && selected
    ? Math.max(0.5, Math.min(sampleLimit(selected, sampleKind).max_qty, Number(q || 0) + d * 0.5))
    : Math.max(1, Number(q || 1) + d)));
  const blocked = !selected || blocksOrder(selected, rndEnforcement);
  const chooseVariant = v => { setSelectedId(v?.id || null); setMode("qty"); setShowReconcile(false); if (kind === "sample" && v) setQty(sampleLimit(v, sampleKind).max_qty); };
  const sampleable = !!selected && canSample(selected);
  const limit = selected ? sampleLimit(selected, sampleKind) : null;
  const chooseSampleKind = (k) => { setSampleKind(k); if (selected) setQty(sampleLimit(selected, k).max_qty); };
  const isSample = kind === "sample";
  const chooseKind = (k) => { setKind(k); setMode("qty"); if (k === "sample" && selected) { setQty(sampleLimit(selected, sampleKind).max_qty); setUnit(selected.base_unit || "meter"); } else setQty(1); };

  return (
    <div className="m-sheet-wrap" data-testid="mobile-quickview">
      <div className="m-sheet-backdrop" onClick={onClose} />
      <div className="m-sheet">
        <div className="m-sheet-grip" />
        <div className="flex items-center justify-between px-4 pb-1">
          <div className="min-w-0">
            <p className="text-[9.5px] font-bold uppercase tracking-wide text-[#0058CC]">{group.category}{group.isMulti ? ` · ${variants.length} varian` : ""}</p>
            <h3 className="m-section-title truncate">{group.name}</h3>
          </div>
          <button data-testid="mobile-quickview-close" onClick={onClose} aria-label="Tutup" className="text-[#6B6B73]"><X size={18} /></button>
        </div>
        <div className="m-sheet-scroll px-4" data-testid="mobile-quickview-scroll">
          <ProductGallery product={selected} testId="mobile-quickview-gallery" compact />
          <div className="mt-2 flex items-end justify-between">
            <p data-testid="mobile-quickview-price" className="text-[20px] font-bold tabular-nums">{selected ? formatCurrency(unitPrice) : "—"}{selected && <span className="text-[11px] font-medium text-[#8E8E93]">/{unit}</span>}</p>
            {/* Trial 22 Okt (B6) — stok PT penjual dulu; angka grup (semua PT) di bawahnya. */}
            <div className="text-right">
              {ownName && (
                <p data-testid="mobile-quickview-own-stock" className="text-[12px] m-muted">{ownName}: <b className={Number(selected.entity_available_qty || 0) > 0 ? "text-[#126E2C]" : "text-[#A8221A]"}>{ownStockText(selected.entity_available_qty, selected.entity_roll_count, baseUnit)}</b></p>
              )}
              <p data-testid="mobile-quickview-stock" className={ownName ? "text-[10.5px] m-muted" : "text-[12px] m-muted"}>{ownName ? "Grup " : "Stok "}<b className={ownName ? "" : "text-[#126E2C]"}>{selected ? formatQty(avail) : "—"}</b> {baseUnit}{selected ? ` · ${rollCount} roll` : ""}</p>
            </div>
          </div>
          {ownName && avail > Number(selected.entity_available_qty || 0) && (
            <p data-testid="mobile-quickview-group-note" className="mt-1 text-[10.5px] leading-snug text-[#8C4A00]">Sebagian stok ada di PT lain di grup — tetap bisa dipesan, pemenuhannya diatur Admin Sales.</p>
          )}
          {isSpecial && <p className="mt-1 inline-block rounded-full bg-[#F3E9FA] px-2 py-0.5 text-[10.5px] font-bold text-[#6B219A]">Harga khusus · normal {formatCurrency(special.normal_price)}</p>}
          {selected?.base_fabric_name && <p data-testid="mobile-quickview-base-fabric" className="mt-1 text-[11px] m-muted">Kain dasar: <b className="text-[#1C1C1E]">{selected.base_fabric_name}</b></p>}

          {/* M0 — pemilih dua sumbu (Warna + Grade) di mobile */}
          {axisMode ? (
            <div className="mt-3">
              <VariantAxisPicker variants={variants} selectedId={selectedId} onSelect={chooseVariant} testIdPrefix="mobile-quickview" />
            </div>
          ) : group.isMulti ? (
            <>
              <p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">Pilih Varian</p>
              <div className="mt-1 flex flex-wrap gap-2" data-testid="mobile-quickview-variants">
                {variants.map((v) => {
                  const va = Number(v.available_qty || 0); const active = v.id === selected?.id;
                  return (
                    <button key={v.id} data-testid={`mobile-quickview-variant-${v.id}`} onClick={() => chooseVariant(v)}
                      className={`rounded-lg border px-2.5 py-1.5 text-left ${active ? "border-[#0058CC] bg-[#EAF2FF]" : "border-[#E5E5EA] bg-white"}`}>
                      <span className="block text-[12px] font-semibold">{variantLabel(v)}</span>
                      <span className={`block text-[10px] ${va <= 0 ? "text-[#A8221A]" : "text-[#6B6B73]"}`}>{va <= 0 ? "Habis" : `Stok ${formatQty(va)}`} · {formatCurrency(v.price)}</span>
                    </button>
                  );
                })}
              </div>
            </>
          ) : null}

          {/* FASE F — belum boleh dijual: alasan + jalan keluar (mobile) */}
          {blocked && (
            <div data-testid="mobile-quickview-not-orderable"
              className="mt-3 rounded-lg border border-[#F0D7A8] bg-[#FFF6E5] p-2.5 text-[11.5px] leading-relaxed text-[#8C4A00]">
              {selected ? <><b>{lifecycleLabel(selected)} — belum boleh dijual.</b> {notOrderableReason(selected)}</> : "Kombinasi tidak tersedia. Tidak ada SKU yang dipilih."}
            </div>
          )}

          {/* Beli biasa vs Pesanan Sample (cermin desktop ProductQuickView) */}
          {!blocked && (
            <div data-testid="mobile-quickview-kind" className={`mt-3 rounded-lg border p-2 ${isSample ? "border-[#F3D9A4] bg-[#FFF9EC]" : "border-[#EFF0F2] bg-[#FAFBFC]"}`}>
              <div className="grid grid-cols-2 gap-2">
                <button type="button" data-testid="mobile-quickview-kind-buy" onClick={() => chooseKind("buy")}
                  className={`flex items-center justify-center gap-1 rounded-md border px-2 py-2 text-[12px] font-semibold ${!isSample ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E5E5EA] bg-white text-[#3C3C43]"}`}><ShoppingBag size={13} /> Order biasa</button>
                <button type="button" data-testid="mobile-quickview-kind-sample" onClick={() => chooseKind("sample")} disabled={!sampleable}
                  className={`flex items-center justify-center gap-1 rounded-md border px-2 py-2 text-[12px] font-semibold disabled:opacity-40 ${isSample ? "border-[#9A5B00] bg-[#FFF3D6] text-[#9A5B00]" : "border-[#E5E5EA] bg-white text-[#3C3C43]"}`}><Scissors size={13} /> Order sample</button>
              </div>
              {isSample && selected && <SampleKindChooser product={selected} kind={sampleKind} onKind={chooseSampleKind} templateId={selected.template_id || ""}
                customerId={customerId} entityId={entityId} testIdPrefix="mobile-quickview" />}
              {isSample && limit && <p data-testid="mobile-quickview-sample-hint" className="mt-1.5 text-[10.5px] leading-snug text-[#9A5B00]">Pesanan Sample (SOS-) terpisah dari order biasa — maks {limit.max_qty} {limit.base_unit} ({limit.label}). Gratis/berbayar dipilih saat checkout.</p>}
            </div>
          )}

          {/* SALES REVAMP V2 — mode beli (disembunyikan bila roll_pick_sales OFF) */}
          {allowRollPick && !isSample && (
          <div data-testid="mobile-quickview-mode" className="mt-3 grid grid-cols-2 gap-2">
            <button type="button" data-testid="mobile-quickview-mode-qty" onClick={() => setMode("qty")}
              className={`rounded-lg border px-3 py-2 text-[12px] font-semibold ${mode === "qty" ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E5E5EA] bg-white text-[#3C3C43]"}`}>Per {baseUnit}</button>
            <button type="button" data-testid="mobile-quickview-mode-roll" onClick={() => setMode("roll")} disabled={rollCount <= 0 || blocked}
              className={`flex items-center justify-center gap-1 rounded-lg border px-3 py-2 text-[12px] font-semibold disabled:opacity-40 ${mode === "roll" ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]" : "border-[#E5E5EA] bg-white text-[#3C3C43]"}`}><Scissors size={13} /> Per Roll</button>
          </div>
          )}

          {mode === "qty" ? (
            <>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Qty</label>
                  <div className="flex items-center rounded-lg border border-[#E5E5EA]">
                    <button data-testid="mobile-quickview-qty-minus" className="px-3 py-2.5 text-[#6B6B73]" onClick={() => step(-1)} aria-label="Kurangi"><Minus size={15} /></button>
                    <input data-testid="mobile-quickview-qty-input" type="number" min={isSample ? "0.5" : "1"} step={isSample ? "0.5" : "1"} inputMode="decimal"
                      className="w-full border-x border-[#E5E5EA] bg-transparent py-2 text-center text-[15px] outline-none" value={qty} onChange={(e) => setQty(isSample && selected ? (clampSampleQty(selected, e.target.value, sampleKind) || 0.5) : Math.max(1, Number(e.target.value) || 1))} />
                    <button data-testid="mobile-quickview-qty-plus" className="px-3 py-2.5 text-[#6B6B73]" onClick={() => step(1)} aria-label="Tambah"><Plus size={15} /></button>
                  </div>
                </div>
                <div className="min-w-0">
                  <label className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">Satuan</label>
                  <div data-testid="mobile-quickview-unit-fixed" className="field flex items-center bg-[#F5F5F7] font-semibold text-[#3C3C43]">{baseUnit}</div>
                </div>
              </div>
            </>
          ) : selected && !blocked ? (
            <div className="mt-3">
              <RollPicker
                productId={selected.id}
                entityId={entityId}
                unitPrice={baseUnitPrice}
                baseUnit={baseUnit}
                onConfirm={(rollLines, snapshot, totalQty) => {
                  if (blocked) return;
                  onAdd(selected, totalQty, baseUnit, { purchase_mode: "roll", roll_lines: rollLines, rolls_snapshot: snapshot, rounding_choice: "exact" });
                  onClose();
                }}
              />
            </div>
          ) : null}
        </div>
        {/* Tombol aksi di kaki lembar (di luar area gulir) — selalu terlihat di Safari iOS
            walau bilah alamat ada di bawah. */}
        {mode === "qty" && (
          <div className="m-sheet-foot" data-testid="mobile-quickview-footer">
            {isSample ? (
            <button data-testid="mobile-quickview-add-sample" disabled={avail <= 0 || blocked || !sampleable || !(qty > 0)}
              className="primary-button w-full justify-center py-3 text-[14px] !bg-[#9A5B00]"
              onClick={() => { if (blocked || avail <= 0 || !sampleable) return; onAdd(selected, clampSampleQty(selected, qty, sampleKind), baseUnit, { is_sample: true, sample_kind: sampleKind }); onClose(); }}>
              <Scissors size={16} /> {avail <= 0 ? "Stok Habis" : `Tambah Sample (${qty} ${baseUnit})`}
            </button>
            ) : (
            <button data-testid="mobile-quickview-add" disabled={avail <= 0 || blocked}
              className="primary-button w-full justify-center py-3 text-[14px]"
              onClick={() => {
                if (blocked || avail <= 0) return;
                if (rollCount > 0 && allowRollPick && !(selected?.merged_members?.length > 1)) { setShowReconcile(true); }
                else { onAdd(selected, qty, unit); onClose(); }
              }}>
              <ShoppingBag size={16} /> {!selected ? "Kombinasi tidak tersedia" : blocked ? "Belum boleh dijual"
                : avail <= 0 ? "Stok Habis" : `Tambah ${qty} ${unit} · ${formatCurrency(lineTotal)}`}
            </button>
            )}
          </div>
        )}
      </div>

      {selected && !blocked && <RollReconcileSheet
        key={selected.id}
        open={showReconcile}
        productId={selected.id}
        entityId={entityId}
        targetQty={Math.round((Number(qty) || 0) * factor * 100) / 100}
        unitPrice={baseUnitPrice}
        baseUnit={baseUnit}
        onClose={() => setShowReconcile(false)}
        onConfirm={(rollLines, totalQty, snapshot, choice) => {
          if (blocked) return;
          setShowReconcile(false);
          // Cek UI UAT v3 (S7) — stok kurang: qty penuh (bukan hanya roll yang ada; 0 roll dulu = keranjang kosong).
          if (choice === "take_all") { onAdd(selected, qty, unit); onClose(); return; }
          onAdd(selected, totalQty, baseUnit, { purchase_mode: "roll", roll_lines: rollLines, rolls_snapshot: snapshot, rounding_choice: choice, target_quantity: Math.round((Number(qty) || 0) * factor * 100) / 100 });
          onClose();
        }}
      />}
    </div>
  );
}
