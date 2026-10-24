import { useState } from "react";
import { Barcode } from "lucide-react";
import { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";

// Audit UI 24 Okt (091): deskripsi template dulu memuat kunci mentah ("invoice • sku, name, qty…").
const DOC_TYPE_LABEL = {
  invoice: "Faktur", surat_jalan: "Surat Jalan", delivery_note: "Surat Jalan", purchase_order: "Pesanan Pembelian",
  sales_order: "Pesanan Penjualan", quotation: "Penawaran", receipt: "Kwitansi", packing_list: "Daftar Kemas",
};
const COLUMN_LABEL = {
  sku: "SKU", name: "Nama barang", product_name: "Nama barang", qty: "Jumlah", quantity: "Jumlah", unit: "Satuan",
  uom: "Satuan", price: "Harga", unit_price: "Harga", subtotal: "Subtotal", total: "Total", discount: "Diskon",
  batch: "Batch", lot: "Lot", roll: "Roll", roll_no: "No. roll", color: "Warna", grade: "Grade", notes: "Catatan",
  length: "Panjang", weight: "Berat",
};
const humanKey = (k) => { const t = String(k || "").replace(/_/g, " "); return t.charAt(0).toUpperCase() + t.slice(1); };

export default function DocumentsView({ templates, loading = false, lastDocument, lastLabel, onGenerateLabel, products }) {
  const [selectedProductId, setSelectedProductId] = useState("");

  const selectedProduct = products.find(p => p.id === selectedProductId);
  const generateCode = selectedProduct ? `ROLL-${selectedProduct.sku}` : "ROLL-BTK-001";

  return (
    <div data-testid="documents-view">
      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-3 min-w-0">
            <span className="kicker">Pusat Cetak</span>
            <h2>Template dokumen & barcode label</h2>
          </div>
        </div>
        <p className="px-4 py-2 text-[12px] text-[#6B6B73]">Header, footer, kolom, area tanda tangan, dan ukuran label dapat dikonfigurasi.</p>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <section className="section-card">
          <div className="section-head"><h2>Template aktif</h2></div>
          <div className="section-body grid gap-2">
            {loading && (
              <div className="animate-pulse py-2 text-[12px] text-[#6B6B73]">Memuat template…</div>
            )}
            {!loading && (templates || []).length === 0 && (
              <div data-testid="templates-empty" className="py-2 text-[12px] text-[#6B6B73]">Belum ada template aktif.</div>
            )}
            {!loading && (templates || []).map((template) => (
              <div data-testid={`template-card-${template.id}`} key={template.id} className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-3">
                <p data-testid={`template-name-${template.id}`} className="text-[13px] font-semibold">{template.name}</p>
                <p data-testid={`template-type-${template.id}`} className="text-[11.5px] text-[#3C3C43]">{DOC_TYPE_LABEL[template.document_type] || humanKey(template.document_type)} • kolom: {(template.columns || []).map((c) => COLUMN_LABEL[c] || humanKey(c)).join(", ")}</p>
              </div>
            ))}
          </div>
        </section>
        <section className="section-card">
          <div className="section-head"><h2>Buat label cepat</h2></div>
          <div className="section-body grid gap-2">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73] block mb-1.5">Pilih Produk</label>
              <KNSelect
                data-testid="label-product-selector"
                className="field w-full"
                value={selectedProductId || ""}
                onValueChange={setSelectedProductId}
                placeholder="-- Pilih produk untuk label --"
                options={[
                  { value: "", label: "-- Pilih produk untuk label --" },
                  ...products.map((p) => ({ value: p.id, label: `${p.sku} - ${p.name}` })),
                ]}
              />
            </div>
            <button
              data-testid="generate-demo-barcode-button"
              className="primary-button"
              disabled={!selectedProductId}
              onClick={() => onGenerateLabel("roll", generateCode)}
            >
              <Barcode size={14} /> Buat Label Roll
            </button>
            {!selectedProductId && <p className="text-[11px] text-[#6B6B73]" data-testid="label-hint">Pilih produk dulu untuk membuat label roll.</p>}
            {lastLabel && (
              <div data-testid="last-barcode-label" className="mt-4 inline-block rounded-md border border-[#EFF0F2] bg-white p-3">
                <p data-testid="last-barcode-code" className="mb-2 text-[11px] font-bold tracking-wider">{lastLabel.code}</p>
                <div className="grid w-[130px] grid-cols-[repeat(13,10px)] gap-0">
                  {lastLabel.qr_matrix.flatMap((row, i) => row.map((cell, j) => <span data-testid={`qr-cell-${i}-${j}`} key={`${i}-${j}`} className={`qr-cell ${cell ? "on" : "off"} h-2.5 w-2.5`} />))}
                </div>
                <p className="mt-2 text-[11px] font-semibold">Ukuran: {lastLabel.label_size}</p>
              </div>
            )}
            {lastDocument && (
              <div data-testid="last-generated-document" className="mt-4 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-3">
                <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Dokumen terakhir</p>
                <p data-testid="last-generated-document-number" className="text-[13px] font-semibold">{lastDocument.number}</p>
                <a data-testid="open-last-document-link" className="mt-2 inline-flex text-[12px] font-semibold text-[#0058CC] underline" href={`${API}/documents/${lastDocument.id}/print`} target="_blank" rel="noreferrer">Buka tampilan cetak</a>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
