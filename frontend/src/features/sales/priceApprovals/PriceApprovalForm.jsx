import KNDatePicker from "@/components/KNDatePicker";
import { useMemo } from "react";
import MoneyInput from "@/components/MoneyInput";
import { X, Send } from "lucide-react";
import { formatCurrency } from "../../../utils/formatters";
import KNSelect from "../../../components/KNSelect";
import { customerOptionLabel } from "./priceApprovalText";

/**
 * Form ajukan / edit pengajuan harga khusus.
 * Named export (komponen). State diangkat ke parent (PriceApprovals.jsx).
 */
export function PriceApprovalForm({
  editId,
  form,
  setForm,
  formErr,
  busyId,
  customers,
  products,
  onClose,
  onSubmit,
  variant = "card",
}) {
  // FASE P5 — `variant="modal"`: kartu & judulnya sendiri dilepas (FormModal yang
  // menyediakannya). Tombolnya tetap di sini karena ada DUA aksi berbeda
  // ("Simpan sebagai Draft" vs "Ajukan untuk Persetujuan") yang bukan satu tombol simpan.
  const isModal = variant === "modal";
  const selectedProduct = useMemo(
    () => products.find((p) => p.id === form.product_id),
    [products, form.product_id],
  );

  return (
    <section data-testid="price-approvals-form" className={isModal ? "" : "section-card p-4"}>
      {!isModal && (
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[13px] font-bold text-[#1C1C1E]">{editId ? "Edit Pengajuan Harga" : "Ajukan Harga Khusus"}</h3>
          <button className="icon-button" onClick={onClose} aria-label="Tutup"><X size={14} /></button>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-[11px] font-semibold text-[#6B6B73]">
          Pelanggan *
          <KNSelect
            data-testid="price-approvals-customer"
            className="field"
            disabled={!!editId}
            value={form.customer_id}
            onValueChange={(v) => setForm({ ...form, customer_id: v })}
            placeholder="— Pilih Pelanggan —"
            options={[
              { value: "", label: "— Pilih Pelanggan —" },
              ...customers.map((c) => ({ value: c.id, label: customerOptionLabel(c) })),
            ]}
          />
        </label>
        <label className="grid gap-1 text-[11px] font-semibold text-[#6B6B73]">
          Produk *
          <KNSelect
            data-testid="price-approvals-product"
            className="field"
            disabled={!!editId}
            value={form.product_id}
            onValueChange={(v) => setForm({ ...form, product_id: v })}
            placeholder="— Pilih Produk —"
            options={[
              { value: "", label: "— Pilih Produk —" },
              ...products.map((p) => ({ value: p.id, label: `${p.name} (${p.sku})` })),
            ]}
          />
        </label>
        <label className="grid gap-1 text-[11px] font-semibold text-[#6B6B73]">
          Harga Khusus / unit *
          {selectedProduct && (
            <span className="text-[10px] font-normal text-[#8E8E93]">Harga normal: {formatCurrency(selectedProduct.price)}</span>
          )}
          <MoneyInput
            testId="price-approvals-price"
            className="field tabular-nums"
            placeholder="cth: 150000"
            value={form.requested_price}
            onChange={(v) => setForm({ ...form, requested_price: v })}
          />
        </label>
        <label className="grid gap-1 text-[11px] font-semibold text-[#6B6B73]">
          Qty Minimum
          <input
            data-testid="price-approvals-minqty"
            type="number" min="0" className="field tabular-nums"
            placeholder="0"
            value={form.min_quantity}
            onChange={(e) => setForm({ ...form, min_quantity: e.target.value })}
          />
        </label>
        <label className="grid gap-1 text-[11px] font-semibold text-[#6B6B73]">
          Berlaku Sampai (opsional)
          <KNDatePicker
            data-testid="price-approvals-validuntil"
            value={form.valid_until}
            onChange={(v) => setForm({ ...form, valid_until: v })}
          />
        </label>
        <label className="grid gap-1 text-[11px] font-semibold text-[#6B6B73] sm:col-span-2">
          Alasan / Catatan
          <textarea
            data-testid="price-approvals-reason"
            className="field min-h-[56px] text-[12px]"
            placeholder="Konteks negosiasi harga…"
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
          />
        </label>
      </div>
      {formErr && <p data-testid="price-approvals-form-error" className="mt-2 text-[11px] font-semibold text-[#A8221A]">{formErr}</p>}
      {/* Audit UI 24 Okt (002) — kaki standar modal: Batal kiri, aksi kanan; tombol utama biru (dulu ungu). */}
      <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
        <button type="button" data-testid="price-approvals-cancel" className="secondary-button"
          disabled={busyId === "form"} onClick={onClose}>
          Batal
        </button>
        <button
          type="button"
          data-testid="price-approvals-save"
          disabled={busyId === "form"}
          onClick={() => onSubmit(false)}
          className={editId ? "primary-button" : "secondary-button"}
        >
          {editId ? "Simpan Perubahan" : "Simpan sebagai Draf"}
        </button>
        {!editId && (
          <button
            type="button"
            data-testid="price-approvals-save-submit"
            disabled={busyId === "form"}
            onClick={() => onSubmit(true)}
            className="primary-button"
          >
            <Send size={13} /> Ajukan untuk Persetujuan
          </button>
        )}
      </div>
    </section>
  );
}
