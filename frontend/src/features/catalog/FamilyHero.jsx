import { mediaUrl } from "../../components/ProductGallery";
import { formatCurrency, formatQty } from "../../utils/formatters";

import { axisLabel } from "./catalogLabels";   // G4-19 — nama sumbu varian dari registri

/**
 * Ringkasan induk produk (pola UI 16 Nov · M22, templat C): foto kecil + SATU baris spesifikasi + deskripsi + atribut.
 * Dulu enam kartu angka berikon selalu tampil walau kosong ("Gramasi —", "Lebar —", "Tersedia 0 roll", "Foto 0
 * disetujui"), lencana tahap teknis di atas foto, dan teks pengisi "Belum ada deskripsi" / "belum ada atribut". Kini
 * hanya nilai yang ADA yang tampil; nama tahap & jenis kain pindah ke kepala rincian (label ringkas); keadaan kosong
 * tetap terbaca lengkap di tab Informasi. `children` = baris tambahan (mis. baris desain) di bawah ringkasan.
 */
export const FamilyHero = ({ family, summary, children }) => {
  const variants = family.variants || [];
  const cover = variants.find(v => v.cover_media_id && (v.media || []).some(m => m.id === v.cover_media_id && m.status === "approved"));
  const coverMedia = cover ? cover.media.find(m => m.id === cover.cover_media_id) : null;
  const src = coverMedia ? mediaUrl(coverMedia.url) : (variants.find(v => v.image)?.image || family.image);
  const prices = variants.map(v => Number(v.price || 0)).filter(Boolean);
  const min = prices.length ? Math.min(...prices) : Number(family.base_price || 0);
  const max = prices.length ? Math.max(...prices) : min;
  const totalMedia = variants.reduce((s, v) => s + (v.media || []).filter(m => m.status === "approved").length, 0);
  const available = (summary?.variants || []).reduce((s, v) => s + Number(v.available || 0), 0);
  const rolls = (summary?.variants || []).reduce((s, v) => s + Number(v.rolls || 0), 0);
  const facts = [
    { label: "Varian", value: `${family.variant_count || 0} SKU`, testId: "hero-fact-sku" },
    { label: "Harga jual", value: min > 0 ? (max > min ? `${formatCurrency(min)} – ${formatCurrency(max)}` : formatCurrency(min)) : "", testId: "hero-fact-price" },
    { label: "Gramasi", value: family.gramasi ? `${family.gramasi} gsm` : "", testId: "hero-fact-gsm" },
    { label: "Lebar", value: family.lebar ? `${family.lebar} m` : "", testId: "hero-fact-width" },
    // FIX-2 (B3a STK-1) — angkanya memang Tersedia (K-04), PT aktif. Nol tidak dipajang (stok per SKU tetap di panel SKU).
    { label: "Tersedia (PT aktif)", value: rolls || available ? `${rolls} roll · ${formatQty(available)} ${family.base_unit}` : "", testId: "hero-fact-stock" },
    { label: "Foto disetujui", value: totalMedia ? String(totalMedia) : "", testId: "hero-fact-media" },
  ].filter(f => f.value);
  const axes = (family.axes || []).map(a => ({ a, opts: (a.options || []).filter(o => o.code !== "XX" && (o.label || "").toLowerCase() !== "tidak ada") }))
    .filter(x => x.opts.length);
  return <section className={`catalog-hero${src ? "" : " no-media"}`} data-testid="catalog-family-hero">
    {src && <div className="catalog-hero-media"><img src={src} alt={family.name} data-testid="catalog-hero-image" /></div>}
    <div className="catalog-hero-body">
      <dl className="catalog-hero-specs" data-testid="catalog-hero-specs">
        {facts.map(f => <div key={f.testId} data-testid={f.testId}><dt>{f.label}</dt><dd>{f.value}</dd></div>)}
      </dl>
      {family.description && <p className="catalog-hero-desc" data-testid="catalog-hero-description">{family.description}</p>}
      {axes.length > 0 && <div className="catalog-hero-swatches" data-testid="catalog-hero-swatches">
        {axes.map(({ a, opts }) => (
          <span key={a.key} className="inline-flex flex-wrap items-center gap-1" data-testid={`catalog-hero-axis-${a.key}`}>
            <small className="catalog-hero-axis">{axisLabel(a)}</small>
            {opts.map(o => <span key={`${a.key}-${o.code}`} className="catalog-swatch" title={`${axisLabel(a)}: ${o.label}`}>{o.hex && <i style={{ background: o.hex }} />}{o.label}</span>)}
          </span>
        ))}
      </div>}
      {children}
    </div>
  </section>;
};
