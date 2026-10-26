import { useEffect, useMemo, useRef, useState } from "react";
import KNSelect from "../../components/KNSelect";
import axios, { API } from "../../services/apiClient";
import { openRnd } from "../rnd/rndDeepLink";
import { catalogApi, catalogError } from "./catalogApi";

const emptySelection = (invalid = "") => ({ template_id: "", target_product_id: "", variant_attrs: {}, variant_options: {}, color_target: null, invalid, new_axis_values: {} });
// Varian yang sudah "dipakai" — dirilis (produksi), tanpa siklus (data lama), atau sudah punya spesifikasi R&D.
const taken = (v) => !!v && (v.spec_id || v.lifecycle === "produksi" || !v.lifecycle);

/** UAT 24 Okt (P5.1) — kode opsi baru 4 huruf (gaya kode sumbu yang ada, mis. NAVY / ABUX), unik di sumbu itu. */
export function newOptionCode(label, used) {
  const base = (String(label || "").toUpperCase().replace(/[^A-Z0-9]/g, "") || "NEW").slice(0, 4).padEnd(4, "X");
  if (!used.has(base)) return base;
  for (let i = 1; i < 100; i += 1) {
    const c = `${base.slice(0, i < 10 ? 3 : 2)}${i}`;
    if (!used.has(c)) return c;
  }
  return `${base}${Date.now() % 1000}`;
}

/**
 * SpecVariantFields — pemilih induk produk + kombinasi varian untuk spesifikasi R&D.
 * Props: `initial` · `onChange(selection)` · `onInherit(patch)` · `mode` ("create" bawaan | "edit").
 *
 * Fase 3 · P3 (permintaan P6, D-24c) — `mode="edit"`: form "Ubah spesifikasi" memuat pilihan TERSIMPAN
 *   `initial = { templateId, variantOptions, newAxisValues, specId, productId? }` (dari dokumen spesifikasi:
 *   `template_id`, `variant_options`, `new_axis_values`, `id`, `target_product_id` bila SKU tujuan dikunci).
 *   Saat memuat induk tersimpan, judul/gramasi/lebar/kategori/satuan TIDAK ditimpa (`onInherit` tidak dipanggil);
 *   `onInherit` (lebar/grade) baru dipanggil bila pengguna MENGUBAH pilihan sumbu atau mengganti induk. Varian yang
 *   sudah ditautkan ke spesifikasi INI (`spec_id === specId`) tidak dianggap "sudah dipakai".
 */
export const SpecVariantFields = ({ initial, onChange, onInherit, mode = "create" }) => {
  const editing = mode === "edit";
  // Varian "dipakai" — kecuali varian milik spesifikasi yang sedang diubah sendiri.
  const isTaken = (v) => taken(v) && !(editing && initial?.specId && v.spec_id === initial.specId);
  const [families, setFamilies] = useState([]);
  const [family, setFamily] = useState(null);
  const [tid, setTid] = useState(initial?.templateId || "");
  const [choices, setChoices] = useState({});
  const [newValues, setNewValues] = useState({});
  const [labdipColors, setLabdipColors] = useState(null);
  const [showLabdip, setShowLabdip] = useState(false);
  const [loading, setLoading] = useState(!!initial?.templateId);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const callbacks = useRef({ onChange, onInherit });
  callbacks.current = { onChange, onInherit };

  useEffect(() => {
    let live = true;
    setListLoading(true);
    catalogApi.list().then(rows => { if (live) { setFamilies(rows.filter(t => t.status === "active")); setError(""); } })
      .catch(e => { if (live) setError(catalogError(e)); })
      .finally(() => { if (live) setListLoading(false); });
    return () => { live = false; };
  }, [retry]);

  // P5.1 — sumbu efektif = opsi induk + nilai BARU yang dipilih (lahir di induk saat spesifikasi di-ACC).
  const axesOf = (tpl, nv) => (tpl?.axes || []).map(a => (nv[a.key] && !a.options.some(o => o.code === nv[a.key].code)
    ? { ...a, options: [...a.options, { ...nv[a.key], isNew: true }] } : a));

  const resolve = (tpl, options, nv = newValues, { inherit = true } = {}) => {
    const axes = axesOf(tpl, nv);
    const variants = tpl.variants || [];
    const attrs = Object.fromEntries(axes.flatMap(a => {
      const o = a.options.find(o => o.code === options[a.key]);
      return o ? [[a.key, o.label]] : [];
    }));
    const existing = variants.find(v => axes.length && axes.every(a => v.variant_options?.[a.key] === options[a.key]));
    const target = initial?.productId ? variants.find(v => v.id === initial.productId) : existing;
    const invalid = initial?.productId && !target ? "SKU tujuan tidak ditemukan dalam induk ini."
      : axes.some(a => !a.options.some(o => o.code === options[a.key])) ? "Pilih seluruh atribut varian."
      : !initial?.productId && isTaken(target)
        ? `Kombinasi ini sudah menjadi SKU ${target.sku} — pilih nilai lain, ambil warna baru dari labdip, atau uji ulang SKU itu.` : "";
    const option = key => axes.find(a => a.key === key)?.options.find(o => o.code === options[key]);
    const color = option("color"), width = option("lebar"), grade = option("grade");
    const usedNew = Object.fromEntries(Object.entries(nv).filter(([k, v]) => options[k] === v.code));
    callbacks.current.onChange({ template_id: tpl.id, target_product_id: target && !isTaken(target) ? target.id : (initial?.productId ? target?.id || "" : ""),
      variant_attrs: attrs, variant_options: options, invalid, taken_product: isTaken(target) ? target : null,
      color_target: color ? (color.isNew && color.color_id ? { color_id: color.color_id } : { code: color.value || color.code }) : null,
      new_axis_values: Object.fromEntries(Object.entries(usedNew).map(([k, v]) => [k, { code: v.code, label: v.label, value: v.value, hex: v.hex || "" }])) });
    if (!inherit) return;
    callbacks.current.onInherit({
      ...(width ? { lebar: String(Number(width.value) * 100) } : {}),
      ...(grade ? { grade: grade.value || grade.code } : {}),
    });
  };

  useEffect(() => {
    let live = true;
    setFamily(null); setChoices({}); setNewValues({}); setError("");
    if (!tid) { setLoading(false); callbacks.current.onChange(emptySelection()); return; }
    setLoading(true);
    callbacks.current.onChange(emptySelection("Memuat kombinasi induk…"));
    catalogApi.detail(tid).then(tpl => {
      if (!live) return;
      const target = (tpl.variants || []).find(v => v.id === initial?.productId);
      // Mode ubah di induk TERSIMPAN: pakai pilihan sumbu & nilai baru yang tersimpan, jangan timpa isian form.
      const stored = editing && tid === initial?.templateId;
      const opts = stored && initial?.variantOptions ? initial.variantOptions : (target?.variant_options || {});
      const nv0 = stored ? (initial?.newAxisValues || {}) : {};
      setFamily(tpl); setChoices(opts); setNewValues(nv0);
      if (!stored) {
        callbacks.current.onInherit({ stage: tpl.stage, fabric_type: tpl.fabric_type, gramasi: target?.gramasi ?? tpl.gramasi ?? "",
          lebar: String(Number(target?.lebar ?? tpl.lebar ?? 0) * 100), base_unit: tpl.base_unit, category: tpl.category,
          title: target?.name || tpl.name, sku_hint: target?.sku || "", line_code: tpl.line_code || "", grade: target?.grade || "" });
      }
      resolve(tpl, opts, nv0, { inherit: !stored });
    }).catch(e => {
      if (live) { setError(catalogError(e)); callbacks.current.onChange(emptySelection("Induk belum berhasil dimuat.")); }
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [tid, initial?.productId, retry]); // eslint-disable-line react-hooks/exhaustive-deps

  // P5.1 — warna ACC dari labdip (Pustaka yang lahir dari labdip) sebagai calon nilai sumbu warna baru.
  useEffect(() => {
    if (!showLabdip || labdipColors) return;
    axios.get(`${API}/rnd/samples`, { params: { sample_type: "labdip", status: "decided", limit: 200 } })
      .then(r => {
        const seen = new Set();
        setLabdipColors((r.data?.items || []).map(s => ({ ...(s.color_target || {}), sample_number: s.number }))
          .filter(c => c.color_id && !seen.has(c.color_id) && seen.add(c.color_id)));
      }).catch(() => setLabdipColors([]));
  }, [showLabdip, labdipColors]);

  const chooseFamily = value => {
    callbacks.current.onChange(emptySelection(value ? "Memuat kombinasi induk…" : ""));
    setFamily(null); setChoices({}); setNewValues({}); setTid(value);
  };
  const pick = (key, v, nv = newValues) => { const next = { ...choices, [key]: v }; setChoices(next); resolve(family, next, nv); };
  const pickLabdipColor = (c) => {
    const axis = (family?.axes || []).find(a => a.key === "color");
    if (!axis) return;
    const existingOpt = axis.options.find(o => (o.value || "").toUpperCase() === (c.code || "").toUpperCase());
    if (existingOpt) { setShowLabdip(false); pick("color", existingOpt.code); return; }
    const code = newOptionCode(c.name, new Set(axis.options.map(o => o.code)));
    const nv = { ...newValues, color: { code, label: c.name, value: c.code, hex: c.hex || "", color_id: c.color_id } };
    setNewValues(nv); setShowLabdip(false); pick("color", code, nv);
  };

  const axes = useMemo(() => axesOf(family, newValues), [family, newValues]);
  // P5.1 — opsi yang (bersama pilihan sumbu lain) sudah jadi SKU ditandai & tidak bisa dipilih.
  const optionList = (a) => a.options.map(o => {
    const combo = { ...choices, [a.key]: o.code };
    const hit = (family?.variants || []).find(v => axes.every(x => v.variant_options?.[x.key] === combo[x.key]));
    const done = !initial?.productId && axes.every(x => combo[x.key]) && isTaken(hit);
    return { value: o.code, label: `${o.label}${o.isNew ? " · BARU (dari labdip)" : ""}${done ? ` · sudah ada (SKU ${hit.sku})` : ""}`, disabled: done };
  });
  const allTaken = family && axes.length && (family.variants || []).filter(isTaken).length >= axes.reduce((n, a) => n * Math.max(a.options.length, 1), 1);
  const takenTarget = family && (family.variants || []).find(v => axes.length && axes.every(a => v.variant_options?.[a.key] === choices[a.key]));

  return <section data-testid="spec-variant-link" aria-busy={loading} className="space-y-3 rounded-md border border-blue-100 bg-blue-50/40 p-3">
    <div className="text-xs font-semibold"><span data-testid="spec-family-label">Induk produk</span>
      <KNSelect data-testid="spec-family-select" aria-label="Induk produk" className="field mt-1" searchable
        value={tid} onValueChange={chooseFamily} disabled={!!initial?.productId || listLoading}
        options={[{ value: "", label: "Induk baru saat persetujuan (produk konsep mandiri)" }, ...families.map(t => ({ value: t.id, label: t.name }))]} />
    </div>
    {loading && <p data-testid="spec-family-loading" role="status" className="text-xs text-blue-700">Memuat kombinasi induk…</p>}
    {error && <div role="alert"><p data-testid="spec-family-error" className="text-sm text-red-700">{error}</p>
      <button type="button" data-testid="spec-family-retry" className="secondary-button mt-2" onClick={() => setRetry(n => n + 1)}>Coba lagi</button></div>}
    {family && <div className="grid gap-2 sm:grid-cols-2">{axes.map(a => <div key={a.key} className="text-xs font-semibold">
      <span data-testid={`spec-axis-label-${a.key}`}>{a.label}</span>
      <KNSelect data-testid={`spec-axis-${a.key}`} aria-label={a.label} className="field mt-1" value={choices[a.key] || ""}
        disabled={!!initial?.productId} options={optionList(a)} onValueChange={v => pick(a.key, v)} />
      {a.key === "color" && !initial?.productId && (
        <button type="button" className="mt-1 text-[11px] font-bold text-[#0058CC]" data-testid="spec-axis-color-from-labdip"
          onClick={() => setShowLabdip(s => !s)}>{showLabdip ? "Tutup" : "+ Warna baru dari labdip ACC"}</button>
      )}
    </div>)}</div>}
    {showLabdip && (
      <div className="rounded border border-[#CBDFFF] bg-white p-2 text-[11px]" data-testid="spec-labdip-colors">
        {labdipColors === null ? "Memuat warna labdip ACC…" : !labdipColors.length ? "Belum ada warna dari labdip yang ACC." : (
          <div className="grid gap-1">
            {labdipColors.map(c => (
              <button key={c.color_id} type="button" data-testid={`spec-labdip-color-${c.color_id}`} onClick={() => pickLabdipColor(c)}
                className="flex items-center gap-2 rounded px-1.5 py-1 text-left hover:bg-[#F2F7FF]">
                <span className="inline-block h-3 w-3 rounded-full border border-[#D9D9DE]" style={{ background: c.hex || "#fff" }} />
                <span className="font-mono">{c.code}</span> {c.name}{c.pantone_code ? ` · ${c.pantone_code}` : ""} <span className="text-[#8E8E93]">({c.sample_number})</span>
              </button>
            ))}
          </div>
        )}
      </div>
    )}
    {family && !initial?.productId && (takenTarget && isTaken(takenTarget) || allTaken) && (
      <div className="rounded border border-[#F0D9A8] bg-[#FFF9EC] p-2 text-[11px] text-[#5C3B00]" data-testid="spec-variant-exits">
        {allTaken ? "Semua kombinasi induk ini sudah menjadi SKU." : `Kombinasi ini sudah menjadi SKU ${takenTarget.sku}.`} Jalan keluar:
        <div className="mt-1 flex flex-wrap gap-2">
          {takenTarget && isTaken(takenTarget) && (
            <button type="button" className="secondary-button !h-7 !text-[11px]" data-testid="spec-exit-revalidate"
              onClick={() => openRnd({ view: "rnd-revalidation", productId: takenTarget.id, product: takenTarget, productLabel: `${takenTarget.sku} — ${takenTarget.name}` })}>
              Uji ulang SKU {takenTarget.sku}
            </button>
          )}
          {(axes.some(a => a.key === "color")) && (
            <button type="button" className="secondary-button !h-7 !text-[11px]" data-testid="spec-exit-new-color" onClick={() => setShowLabdip(true)}>
              Warna baru dari labdip
            </button>
          )}
          <span className="self-center text-[10.5px]">atau tambah nilai sumbu di Produk &amp; Harga → Master Katalog (Ubah induk).</span>
        </div>
      </div>
    )}
  </section>;
};
