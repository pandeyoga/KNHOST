/**
 * DocumentsView — Pusat Dokumen › Cetak PDF & Label.
 *
 * Fase 3 · P2 (D-01, keputusan pemilik 26 Okt) — kartu "Template aktif" (daftar template ketiga, baca-saja) diganti
 * SATU baris ringkas: tautan ke Pengaturan › Dokumen & Cetak › Template Dokumen bagi peran yang boleh membukanya,
 * "dikelola Admin" bagi peran lain. Daftar & form template hanya di layar utama itu.
 */
import { useState } from "react";
import { Barcode, FileText } from "lucide-react";
import { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import LinkCard from "../../components/LinkCard";

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
        <div className="px-4 py-2">
          <LinkCard testId="documents-templates-link" icon={FileText} what="Template dokumen (kop, kolom, tanda tangan)"
            where="Pengaturan › Dokumen & Cetak › Template Dokumen" view="pdf-templates" preset={{ tab: "dasar" }}
            summary={loading ? "memuat…" : `${(templates || []).length} template aktif`}
            readOnlyText="Template dokumen (kop, kolom, tanda tangan) dikelola Admin di Pengaturan." />
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
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
