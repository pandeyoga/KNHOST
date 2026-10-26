import { useEffect, useMemo, useState } from "react";
import KNDatePicker from "@/components/KNDatePicker";
import MoneyInput from "@/components/MoneyInput";
import axios, { API } from "../../services/apiClient";
import { Plus, Trash2, FileStack } from "lucide-react";
import FormModal from "../../components/FormModal";
import { formatCurrency } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import useUomConversions from "../../hooks/useUomConversions";
import { GroupEntityNotice, isGroupEntityPartner, supplierOptionLabel }
  from "../../components/GroupEntityBadge";

/**
 * BlanketPOCreateModal (P2) — buat kontrak Blanket/Contract PO.
 * 1.c — komitmen = kuantitas per item (contract_qty) + plafon nilai (contract_value_cap).
 * Plafon 0 → backend default = Σ qty × harga.
 */
export default function BlanketPOCreateModal({ open, selectedEntity, onClose, onCreated, onError }) {
  const [supplierId, setSupplierId] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [supplierContact, setSupplierContact] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [validFrom, setValidFrom] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [valueCap, setValueCap] = useState("");
  const [notes, setNotes] = useState("");
  // PB-01 — syarat komersial kontrak → turun ke tiap call-off.
  const [paymentTermCode, setPaymentTermCode] = useState("");
  const [taxMode, setTaxMode] = useState("");
  const [priceIncl, setPriceIncl] = useState("");   // "" ikut config | "yes" | "no"
  const [paymentTerms, setPaymentTerms] = useState([]);
  const [rows, setRows] = useState([{ product_id: "", contract_qty: "", contract_price: "", unit: "" }]);
  const [products, setProducts] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [busy, setBusy] = useState(false);
  // Fase 3 · P5 (L-03) — galat validasi/simpan tampil DI pop-up (dulu ke bilah halaman di belakang lapisan).
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) { reset(); return; }
    (async () => {
      try {
        const [p, s, w, t] = await Promise.all([
          axios.get(`${API}/products`),
          axios.get(`${API}/suppliers`),
          axios.get(`${API}/warehouses`),
          axios.get(`${API}/payment-terms`).catch(() => ({ data: [] })),
        ]);
        setProducts(Array.isArray(p.data) ? p.data : []);
        setSuppliers(Array.isArray(s.data) ? s.data : []);
        setWarehouses(Array.isArray(w.data) ? w.data : []);
        setPaymentTerms(Array.isArray(t.data) ? t.data.filter((x) => x.active !== false) : []);
      } catch (e) { setErr("Gagal memuat data master."); onError?.("Gagal memuat data master."); }
    })();
  }, [open]); // eslint-disable-line

  function reset() {
    setSupplierId(""); setSupplierName(""); setSupplierContact(""); setWarehouseId("");
    setValidFrom(""); setValidUntil(""); setValueCap(""); setNotes("");
    setPaymentTermCode(""); setTaxMode(""); setPriceIncl("");
    setRows([{ product_id: "", contract_qty: "", contract_price: "", unit: "" }]);
  }

  const activeSuppliers = useMemo(() => suppliers.filter((s) => s.status !== "inactive"), [suppliers]);
  const supplierOptions = useMemo(() => [
    { value: "", label: "— Isi manual / tanpa master —" },
    // FASE E-7 (E7.2) — badan usaha grup ditandai sejak di daftar pilihan.
    ...activeSuppliers.map((s) => ({
      value: s.id, label: supplierOptionLabel(s, `${s.code || ""} ${s.name}`.trim()),
    })),
  ], [activeSuppliers]);
  const selectedSupplier = useMemo(
    () => suppliers.find((s) => s.id === supplierId) || null, [suppliers, supplierId]);
  const supplierIsGroupEntity = isGroupEntityPartner(selectedSupplier);
  const warehouseOptions = useMemo(
    () => warehouses.map((w) => ({ value: w.id, label: `${w.name}${w.code ? ` (${w.code})` : ""}` })), [warehouses]);
  const productOptions = useMemo(
    () => [{ value: "", label: "Pilih produk..." }, ...products.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` }))], [products]);

  // Satuan dari MASTER (katalog UOM server) — bukan ketikan bebas, supaya konversi
  // & drawdown kontrak selalu punya faktor yang dikenal mesin satuan.
  const { unitOptions: uomUnitOptions } = useUomConversions();
  const uomCatalogUnits = uomUnitOptions();
  function unitOptionsFor(r) {
    const prod = products.find((p) => p.id === r.product_id);
    const baseUnit = prod?.base_unit || "meter";
    const opts = [{ value: baseUnit, label: `${baseUnit} (satuan dasar)` }];
    (uomCatalogUnits || []).forEach((u) => { if (u.value !== baseUnit) opts.push(u); });
    if (r.unit && !opts.some((o) => o.value === r.unit)) opts.push({ value: r.unit, label: r.unit });
    return opts;
  }

  function handleSupplier(v) {
    setSupplierId(v);
    if (v) {
      const s = suppliers.find((x) => x.id === v);
      setSupplierName(s?.name || "");
      setSupplierContact([s?.pic_name, s?.phone].filter(Boolean).join(" · "));
    }
  }

  function setRow(i, patch) {
    setRows((rs) => rs.map((r, idx) => {
      if (idx !== i) return r;
      const next = { ...r, ...patch };
      if (patch.product_id !== undefined) {
        const prod = products.find((p) => p.id === patch.product_id);
        if (prod) {
          next.unit = prod.base_unit || "meter";
          if (!next.contract_price) next.contract_price = prod.price || "";
        }
      }
      return next;
    }));
  }
  function addRow() { setRows((rs) => [...rs, { product_id: "", contract_qty: "", contract_price: "", unit: "" }]); }
  function delRow(i) { setRows((rs) => (rs.length === 1 ? rs : rs.filter((_, idx) => idx !== i))); }

  const computedTotal = useMemo(
    () => rows.reduce((sum, r) => sum + (Number(r.contract_qty) || 0) * (Number(r.contract_price) || 0), 0), [rows]);
  const effectiveCap = Number(valueCap) > 0 ? Number(valueCap) : computedTotal;

  async function submit() {
    if (!warehouseId) { setErr("Pilih gudang default."); return; }
    if (!supplierId && !supplierName.trim()) { setErr("Pilih supplier master atau isi nama supplier."); return; }
    const items = rows
      .filter((r) => r.product_id && Number(r.contract_qty) > 0)
      .map((r) => ({
        product_id: r.product_id,
        contract_qty: Number(r.contract_qty),
        contract_price: Number(r.contract_price) || 0,
        unit: r.unit || "",
      }));
    if (items.length === 0) { setErr("Tambah minimal 1 item kontrak (produk + qty > 0)."); return; }
    if (validFrom && validUntil && validUntil < validFrom) {
      setErr("Masa berlaku akhir tidak boleh sebelum mulai."); return;
    }
    setBusy(true); setErr("");
    try {
      const body = {
        supplier_id: supplierId, supplier_name: supplierName, supplier_contact: supplierContact,
        warehouse_id: warehouseId, items,
        contract_value_cap: Number(valueCap) || 0,
        valid_from: validFrom, valid_until: validUntil, notes,
        payment_term_code: paymentTermCode, tax_mode: taxMode,
        price_includes_ppn: priceIncl === "" ? null : priceIncl === "yes",
        entity_id: (selectedEntity && selectedEntity !== "all") ? selectedEntity : "",
      };
      const r = await axios.post(`${API}/purchase-orders/blanket`, body);
      onCreated?.(r.data);
    } catch (e) {
      setErr(e.response?.data?.detail || "Gagal membuat kontrak.");
    } finally { setBusy(false); }
  }

  if (!open) return null;

  // Fase 3 · P5 (L-03) — dulu `modal-overlay`/`modal-card` buatan sendiri; kini FormModal baku (layar penuh di HP,
  // tombol Buat Kontrak selalu terlihat, galat di dalam pop-up). Isian sama.
  return (
    <FormModal open={open} onClose={onClose} title="Buat Kontrak Blanket PO" icon={FileStack} size="lg"
      subtitle="Kontrak payung dengan supplier — barang ditarik bertahap lewat call-off"
      testId="blanket-create-modal" onSubmit={submit} submitTestId="blanket-submit" cancelTestId="blanket-create-close"
      submitLabel={supplierIsGroupEntity ? "Pakai menu Antar Entitas" : busy ? "Menyimpan..." : "Buat Kontrak"}
      submitDisabled={supplierIsGroupEntity} busy={busy} error={err}>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Supplier (Master)">
              <KNSelect value={supplierId} onValueChange={handleSupplier} options={supplierOptions}
                className="field" placeholder="Pilih dari master / manual" data-testid="blanket-supplier-select" />
            </Field>
            <Field label="Nama Supplier" req={!supplierId}>
              <input data-testid="blanket-supplier-name" value={supplierName} disabled={!!supplierId}
                onChange={(e) => setSupplierName(e.target.value)}
                className="field disabled:bg-gray-100 disabled:text-gray-500" placeholder="mis. PT Sinar Tekstil" />
            </Field>
            <Field label="Kontak Supplier">
              <input data-testid="blanket-supplier-contact" value={supplierContact}
                onChange={(e) => setSupplierContact(e.target.value)} className="field" placeholder="PIC · telepon" />
            </Field>
            {/* FASE E-7 (E7.2) — komitmen harga ke badan usaha grup adalah KONTRAK
                INTERNAL, bukan Blanket PO: call-off-nya akan melahirkan PO biasa dan
                margin antar-PT tidak pernah dieliminasi di konsolidasi. */}
            {supplierIsGroupEntity && (
              <div className="sm:col-span-2">
                <GroupEntityNotice partner={selectedSupplier} docLabel="Kontrak Blanket PO" />
              </div>
            )}
            <Field label="Gudang Default" req>
              <KNSelect value={warehouseId} onValueChange={setWarehouseId} options={warehouseOptions}
                className="field" placeholder="Pilih gudang" data-testid="blanket-warehouse-select" />
            </Field>
            <Field label="Berlaku Mulai">
              <KNDatePicker data-testid="blanket-valid-from" value={validFrom} onChange={setValidFrom} />
            </Field>
            <Field label="Berlaku Sampai">
              <KNDatePicker data-testid="blanket-valid-until" value={validUntil} onChange={setValidUntil} />
              <p className="text-[11px] text-[#9A9BA3] mt-0.5">Kosongkan bila tanpa batas waktu</p>
            </Field>
          </div>

          {/* Items kontrak */}
          <div>
            <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">Item Kontrak <span className="text-red-500">*</span></label>
            {/* UAT 24 Okt (audit UI tahap 2) — G4-09: kepala kolom bergaya label biasa (dulu MAJUSCULE 10px),
                "Harga per satuan" (dulu "Harga Sepakat", bentrok dengan isian PPN di bawah). */}
            <div className="grid grid-cols-[1fr_80px_100px_130px_32px] gap-2 px-1 mb-1 text-[11px] font-semibold text-[#4A4B53]">
              <span>Produk</span><span>Qty kontrak</span><span>Harga per satuan</span><span>Satuan</span><span></span>
            </div>
            <div className="space-y-2">
              {rows.map((r, i) => (
                <div key={i} className="grid grid-cols-[1fr_80px_100px_130px_32px] gap-2" data-testid={`blanket-item-row-${i}`}>
                  <KNSelect value={r.product_id} onValueChange={(v) => setRow(i, { product_id: v })}
                    options={productOptions} className="field" placeholder="Pilih produk" data-testid={`blanket-item-product-${i}`} />
                  <input type="number" value={r.contract_qty} onChange={(e) => setRow(i, { contract_qty: e.target.value })}
                    className="field" placeholder="0" aria-label={`Qty kontrak item ${i + 1}`} data-testid={`blanket-item-qty-${i}`} />
                  <MoneyInput value={r.contract_price} onChange={(v) => setRow(i, { contract_price: v })}
                    className="field" placeholder="0" testId={`blanket-item-price-${i}`} />
                  <KNSelect value={r.unit} onValueChange={(v) => setRow(i, { unit: v })}
                    options={unitOptionsFor(r)} className="field" placeholder="Satuan"
                    disabled={!r.product_id} data-testid={`blanket-item-unit-${i}`} />
                  <button type="button" onClick={() => delRow(i)} disabled={rows.length === 1} aria-label={`Hapus item ${i + 1}`}
                    className="icon-button text-red-500 disabled:opacity-30"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>
            <button type="button" data-testid="blanket-add-item" onClick={addRow} className="secondary-button mt-2 text-[11px]">
              <Plus size={12} /> Tambah Item
            </button>
          </div>

          {/* Plafon nilai + ringkasan */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Plafon Nilai Kontrak (Rp)">
              <MoneyInput testId="blanket-value-cap" value={valueCap}
                onChange={(v) => setValueCap(v)} className="field" placeholder="0" />
              <p className="text-[11px] text-[#9A9BA3] mt-0.5">0 = otomatis (jumlah qty × harga)</p>
            </Field>
            <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5 text-[11.5px]" data-testid="blanket-summary">
              <div className="flex justify-between"><span className="text-[#6B6B73]">Jumlah qty × harga</span><span className="tabular-nums">{formatCurrency(computedTotal)}</span></div>
              <div className="flex justify-between font-bold mt-1 pt-1 border-t border-[#EFF0F2]">
                <span>Plafon Efektif</span>
                <span data-testid="blanket-effective-cap" className="tabular-nums text-[#007AFF]">{formatCurrency(effectiveCap)}</span>
              </div>
            </div>
          </div>

          <Field label="Catatan">
            <textarea data-testid="blanket-notes" value={notes} onChange={(e) => setNotes(e.target.value)}
              className="field" rows="2" placeholder="Catatan kontrak (syarat lain, dll)…" />
          </Field>

          {/* PB-01 — syarat komersial: turun otomatis ke tiap call-off (PO anak) */}
          <div className="rounded-md border border-[#DCE7F7] bg-[#F7FAFF] p-2.5" data-testid="blanket-terms-block">
            <p className="mb-2 text-[12px] font-semibold text-[#1C1C1E]">Termin & PPN kontrak <span className="font-normal text-[#6B6B73]">— turun otomatis ke tiap penarikan (call-off)</span></p>
            {/* G4-09 — dua kolom supaya teks pilihan PPN tidak terpotong chevron. */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2"><Field label="Termin pembayaran">
                <KNSelect value={paymentTermCode} onValueChange={setPaymentTermCode} className="field"
                  placeholder="— ikut termin supplier —" data-testid="blanket-payment-term"
                  options={[{ value: "", label: `— ikut supplier${selectedSupplier?.payment_term_code ? ` (${selectedSupplier.payment_term_code})` : ""} —` },
                    ...paymentTerms.map((t) => ({ value: t.code, label: `${t.code} · ${t.name}${t.net_days ? ` · ${t.net_days} hari` : ""}${t.dp_percent ? ` · DP ${t.dp_percent}%` : ""}` }))]} />
              </Field></div>
              <Field label="PPN">
                <KNSelect value={taxMode} onValueChange={setTaxMode} className="field" data-testid="blanket-tax-mode"
                  options={[{ value: "", label: "Ikut pengaturan badan usaha" }, { value: "ppn", label: "Kena PPN (Faktur Pajak Masukan)" }, { value: "non_ppn", label: "Non-PPN (supplier non-PKP)" }]} />
              </Field>
              <Field label="Kebijakan harga">
                <KNSelect value={priceIncl} onValueChange={setPriceIncl} className="field" data-testid="blanket-price-incl"
                  options={[{ value: "", label: "Ikut pengaturan badan usaha" }, { value: "no", label: "Harga belum termasuk PPN" }, { value: "yes", label: "Harga sudah termasuk PPN" }]} />
              </Field>
            </div>
          </div>
        </div>
    </FormModal>
  );
}

function Field({ label, req, children }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">{label}{req && <span className="text-red-500"> *</span>}</label>
      {children}
    </div>
  );
}
