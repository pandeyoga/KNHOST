/**
 * UAT 24 Okt (P4.3/P4.4/P3.5) — warna target LABDIP: banyak warna sekaligus (tiap warna = satu sampel berkelompok).
 * Warna BARU diisi bebas (nama + hex + Pantone wajib) — Pustaka Warna LAHIR dari warna yang di-ACC. Warna yang sudah
 * ada di Pustaka tetap bisa dipakai (mis. warna pelanggan) lewat "Ambil dari Pustaka".
 */
import { Plus, Trash2 } from "lucide-react";
import KNSelect from "../../components/KNSelect";

export const PANTONE_RE = /^(\d{2}-\d{4}\s?(TCX|TPX|TPG|TN)|[A-Z0-9][A-Z0-9 .-]{0,24}\s(C|U|CP|UP))$/i;
export const emptyColor = () => ({ color_id: "", name: "", hex: "#1F3A93", pantone_code: "" });

/** Masalah satu baris warna (kosong = lengkap). */
export function colorProblem(c) {
  if (c.color_id) return "";
  if (!c.name?.trim()) return "nama warna";
  if (!/^#?[0-9A-Fa-f]{6}$/.test(c.hex || "")) return "hex";
  if (!PANTONE_RE.test((c.pantone_code || "").trim())) return "kode Pantone";
  return "";
}

export default function ColorTargetsEditor({ value = [], onChange, colors = [], max = 10, testId = "labdip-colors" }) {
  const rows = value.length ? value : [emptyColor()];
  const upd = (i, patch) => onChange(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const lib = Object.fromEntries(colors.map((c) => [c.id, c]));
  return (
    <div className="grid gap-2" data-testid={testId}>
      {rows.map((r, i) => {
        const fromLib = Boolean(r.color_id);
        const prob = colorProblem(r);
        return (
          <div key={i} className="grid items-end gap-2 rounded-lg border border-[#EFF0F2] p-2 sm:grid-cols-[1.4fr_0.8fr_1fr_1.2fr_auto]" data-testid={`${testId}-row-${i}`}>
            <label className="block">
              <span className="mb-1 block text-[10px] font-semibold text-[#6B6B73]">Warna {i + 1} — nama *</span>
              <input className="field" data-testid={`${testId}-name-${i}`} disabled={fromLib} value={fromLib ? lib[r.color_id]?.name || r.name : r.name}
                onChange={(e) => upd(i, { name: e.target.value })} placeholder="mis. Navy Blazer" />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-semibold text-[#6B6B73]">Hex *</span>
              <span className="flex items-center gap-1">
                <input type="color" className="h-8 w-9 shrink-0 cursor-pointer rounded border border-[#E5E5EA]" disabled={fromLib}
                  data-testid={`${testId}-hex-picker-${i}`} value={(fromLib ? lib[r.color_id]?.hex : r.hex) || "#000000"}
                  onChange={(e) => upd(i, { hex: e.target.value.toUpperCase() })} />
                <input className="field font-mono" data-testid={`${testId}-hex-${i}`} disabled={fromLib}
                  value={fromLib ? lib[r.color_id]?.hex || "" : r.hex} onChange={(e) => upd(i, { hex: e.target.value })} />
              </span>
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-semibold text-[#6B6B73]">Kode Pantone *</span>
              <input className="field font-mono" data-testid={`${testId}-pantone-${i}`} disabled={fromLib && !!lib[r.color_id]?.pantone_code}
                value={fromLib ? (lib[r.color_id]?.pantone_code || r.pantone_code || "") : r.pantone_code}
                onChange={(e) => upd(i, { pantone_code: e.target.value.toUpperCase() })} placeholder="19-4052 TCX" />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-semibold text-[#6B6B73]">atau ambil dari Pustaka</span>
              <KNSelect data-testid={`${testId}-lib-${i}`} className="field" value={r.color_id} searchable
                options={[{ value: "", label: "— warna baru —" }, ...colors.map((c) => ({ value: c.id, label: `${c.code} · ${c.name}${c.pantone_code ? ` · ${c.pantone_code}` : ""}` }))]}
                onValueChange={(v) => upd(i, v ? { color_id: v, name: lib[v]?.name || "", hex: lib[v]?.hex || "", pantone_code: lib[v]?.pantone_code || "" } : emptyColor())} />
            </label>
            <button type="button" className="mb-1 rounded p-1.5 text-[#A8221A] disabled:opacity-30" disabled={rows.length <= 1}
              data-testid={`${testId}-remove-${i}`} onClick={() => onChange(rows.filter((_, j) => j !== i))} aria-label={`Hapus warna ${i + 1}`}><Trash2 size={14} /></button>
            {prob && (r.name || r.pantone_code) && <p className="text-[10.5px] text-[#A8221A] sm:col-span-5" data-testid={`${testId}-problem-${i}`}>Lengkapi {prob}.</p>}
          </div>
        );
      })}
      <div className="flex flex-wrap items-center justify-between gap-2 text-[10.5px] text-[#6B6B73]">
        <span>{rows.length > 1 ? `${rows.length} warna → ${rows.length} sampel berkelompok (ronde, ACC & pemenang per warna).` : "Tambah warna untuk menguji beberapa warna sekaligus."}
          {" "}Warna yang di-ACC otomatis masuk Pustaka Warna.</span>
        <button type="button" className="inline-flex items-center gap-1 font-bold text-[#0058CC] disabled:opacity-40" disabled={rows.length >= max}
          data-testid={`${testId}-add`} onClick={() => onChange([...rows, emptyColor()])}><Plus size={12} /> Tambah warna ({rows.length}/{max})</button>
      </div>
    </div>
  );
}
