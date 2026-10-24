/**
 * UomConversionParts (FASE B) — bagian tampilan layar “Konversi Satuan”.
 * Dipisah dari view utama agar tiap file di bawah batas guardrail (<500 baris).
 */
import { stripInternalCodes } from "../../../utils/cleanText";
import { ArrowRight, Pencil, Power } from "lucide-react";
import { SOURCE_LABEL } from "../../../hooks/useUomConversions";

export const KIND_TONE = { fixed: "pill-info", pack: "pill-warning", formula: "pill-success" };

// Label tampilan dari katalog server ("Faktor tetap (fisika/standar)" → "Faktor tetap").
// Kode mentah (fixed / gsm_width / length…) TIDAK boleh tampil ke pengguna.
const shortLabel = (list, value) => {
  const hit = (list || []).find((x) => x.value === value);
  return hit ? String(hit.label).split(" (")[0] : "";
};
const fmtNum = (v, digits = 6) => Number(v).toLocaleString("id-ID", { maximumFractionDigits: digits });
// Catatan otomatis "1 cm = 0.01 meter" hanya mengulang kolom Faktor → tidak ditampilkan lagi.
const isAutoNote = (text) => /^1\s+\S+\s*=\s*[\d.,]+\s+\S+$/.test(String(text || "").trim());

export function StatCards({ rules, settings }) {
  const active = rules.filter((r) => r.status === "active").length;
  const byKind = (k) => rules.filter((r) => r.kind === k && r.status === "active").length;
  const cards = [
    { k: "Aturan aktif", v: active, s: `${rules.length} total terdaftar` },
    { k: "Faktor tetap", v: byKind("fixed"), s: "standar fisika/industri" },
    { k: "Ukuran kemasan", v: byKind("pack"), s: "roll · bal · cone · box" },
    {
      k: "Toleransi selisih",
      v: `${Number(settings?.warn_pct ?? 0)}% / ${Number(settings?.block_pct ?? 0)}%`,
      s: "peringatan / blokir",
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
      {cards.map((c) => (
        <div key={c.k} data-testid={`uom-stat-${c.k}`}
          className="rounded-md border border-[#EFF0F2] bg-white px-2.5 py-2">
          <p className="text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">{c.k}</p>
          <p className="text-[16px] font-bold tabular-nums text-[#1C1C1E]">{c.v}</p>
          <p className="text-[11px] text-[#8E8E93]">{c.s}</p>
        </div>
      ))}
    </div>
  );
}


export function RuleTable({ rules, onEdit, onToggle, canEdit, busyId, loading = false,
  kinds = [], dimensions = [], formulas = [] }) {
  if (loading) {
    return (
      <p data-testid="uom-rules-loading" className="px-2.5 py-3 text-[11px] text-[#6B6B73]">
        Memuat aturan konversi…
      </p>
    );
  }
  if (!rules.length) {
    return (
      <p data-testid="uom-rules-empty" className="px-2.5 py-3 text-[11px] text-[#6B6B73]">
        Belum ada aturan pada filter ini.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-[11.5px]">
        <thead>
          <tr className="whitespace-nowrap bg-[#FAFBFC] text-[11px] uppercase tracking-wide text-[#6B6B73]">
            <th className="px-2 py-1.5 text-left">Konversi</th>
            <th className="px-2 py-1.5 text-left">Jenis</th>
            <th className="px-2 py-1.5 text-right">Faktor</th>
            <th className="px-2 py-1.5 text-left">Dimensi</th>
            <th className="px-2 py-1.5 text-left">Catatan</th>
            <th className="px-2 py-1.5 text-left">Status</th>
            <th className="px-2 py-1.5 text-right">Aksi</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id} data-testid={`uom-rule-row-${r.from_unit}-${r.to_unit}`}
              className="border-t border-[#F2F3F5]">
              <td className="whitespace-nowrap px-2 py-1.5 font-semibold text-[#1C1C1E]">
                <span className="inline-flex items-center gap-1">
                  {r.from_unit} <ArrowRight size={10} className="text-[#8E8E93]" /> {r.to_unit}
                </span>
              </td>
              <td className="px-2 py-1.5">
                <span className={`status-pill whitespace-nowrap ${KIND_TONE[r.kind] || "pill-muted"}`}>
                  {shortLabel(kinds, r.kind) || "Lainnya"}
                </span>
              </td>
              <td className="whitespace-nowrap px-2 py-1.5 text-right tabular-nums">
                {r.kind === "formula" ? (shortLabel(formulas, r.formula) || "Formula produk")
                  : `1 ${r.from_unit} = ${fmtNum(r.factor, 8)} ${r.to_unit}`}
              </td>
              <td className="whitespace-nowrap px-2 py-1.5 text-[#6B6B73]">{shortLabel(dimensions, r.dimension) || "—"}</td>
              <td className="px-2 py-1.5 text-[#6B6B73]">
                {isAutoNote(r.note || r.label) ? "" : stripInternalCodes(r.note || r.label)}
                {r.source === "standard" && (
                  <span className="ml-1 text-[11px] font-semibold text-[#0058CC]">standar</span>
                )}
              </td>
              <td className="px-2 py-1.5">
                <span className={`status-pill ${r.status === "active" ? "pill-success" : "pill-muted"}`}>
                  {r.status === "active" ? "Aktif" : "Nonaktif"}
                </span>
              </td>
              <td className="whitespace-nowrap px-2 py-1.5 text-right">
                {canEdit && (
                  <span className="inline-flex gap-1">
                    <button data-testid={`uom-rule-edit-${r.id}`} className="icon-button"
                      title="Ubah faktor" aria-label="Ubah aturan" onClick={() => onEdit(r)}><Pencil size={12} /></button>
                    <button data-testid={`uom-rule-toggle-${r.id}`} className="icon-button"
                      title={r.status === "active" ? "Nonaktifkan" : "Aktifkan"}
                      aria-label={r.status === "active" ? "Nonaktifkan aturan" : "Aktifkan aturan"}
                      disabled={busyId === r.id}
                      onClick={() => onToggle(r)}><Power size={12} /></button>
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function UsageTable({ usage, loading = false }) {
  if (loading) {
    return (
      <p data-testid="uom-usage-loading" className="px-2.5 py-3 text-[11px] text-[#6B6B73]">
        Memuat jejak konversi…
      </p>
    );
  }
  if (!usage.length) {
    return (
      <p data-testid="uom-usage-empty" className="px-2.5 py-3 text-[11px] text-[#6B6B73]">
        Belum ada jejak konversi. Jejak muncul otomatis saat PR/PO/penerimaan memakai satuan
        selain satuan dasar produk.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-[11.5px]">
        <thead>
          <tr className="whitespace-nowrap bg-[#FAFBFC] text-[11px] uppercase tracking-wide text-[#6B6B73]">
            <th className="px-2 py-1.5 text-left">Dokumen</th>
            <th className="px-2 py-1.5 text-left">SKU</th>
            <th className="px-2 py-1.5 text-left">Konversi</th>
            <th className="px-2 py-1.5 text-right">Faktor</th>
            <th className="px-2 py-1.5 text-left">Sumber</th>
            <th className="px-2 py-1.5 text-left">Selisih</th>
            <th className="px-2 py-1.5 text-left">Waktu</th>
          </tr>
        </thead>
        <tbody>
          {usage.map((u, i) => (
            <tr key={i} data-testid={`uom-usage-row-${i}`} className="border-t border-[#F2F3F5]">
              <td className="px-2 py-1.5">
                <span className="font-semibold">{u.number || "—"}</span>
                <span className="ml-1 text-[11px] text-[#8E8E93]">{u.doc_type}</span>
              </td>
              <td className="px-2 py-1.5 text-[#6B6B73]">{u.sku || "—"}</td>
              <td className="px-2 py-1.5 tabular-nums">
                {u.doc_qty} {u.doc_uom} → <b>{u.base_qty} {u.base_uom}</b>
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums">
                {u.factor == null ? "—"
                  : Number(u.factor).toLocaleString("id-ID", { maximumFractionDigits: 6 })}
              </td>
              <td className="px-2 py-1.5 text-[#6B6B73]">
                {SOURCE_LABEL[u.source] || u.source}
                {u.source_migrated && (
                  <span className="ml-1 text-[11px] text-[#8C4A00]">migrasi</span>
                )}
              </td>
              <td className="px-2 py-1.5">
                {u.variance?.level && u.variance.level !== "ok" ? (
                  <span className={`status-pill ${u.variance.level === "block" ? "pill-danger" : "pill-warning"}`}>
                    {Number(u.variance.variance_pct).toFixed(2)}%
                    {u.variance.overridden ? " · ditimpa" : ""}
                  </span>
                ) : (
                  <span className="text-[#8E8E93]">—</span>
                )}
              </td>
              <td className="whitespace-nowrap px-2 py-1.5 text-[11px] text-[#8E8E93]">
                {u.converted_at ? new Date(u.converted_at).toLocaleString("id-ID") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
