/**
 * DomainRegistryParts — komponen pendukung layar Registry Domain (Fase A).
 * Dipisah agar `DomainRegistryView.jsx` tetap di bawah batas 500 baris.
 */
import { stripInternalCodes } from "../../../utils/cleanText";
import { ArrowRight, Check, Minus } from "lucide-react";

export function Kpi({ label, value, hint, icon: Icon, tone = "#0058CC", testId }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body flex items-center gap-3 py-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg"
          style={{ background: `${tone}14` }}>
          {Icon ? <Icon size={17} style={{ color: tone }} /> : null}
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className="text-[16px] font-bold tabular-nums leading-tight">{value}</p>
          {hint && <p className="truncate text-[10.5px] text-[#8E8E93]">{hint}</p>}
        </div>
      </div>
    </div>
  );
}

/** Rantai stage visual: yarn → grey → pfd|pfp → finished (+ sisa/hasil samping). */
// Audit UI 105 — layar ini untuk pemilik, bukan pengembang: kode enum/API diganti label.
const PROC_LABEL = {
  weaving: "tenun", knitting: "rajut", pre_treatment: "pra-proses", dyeing: "celup", printing: "printing",
  finishing: "finishing", screen: "screen", other: "lainnya", lainnya: "lainnya",
};
const USE_LABEL = { dye: "untuk celup", print: "untuk printing" };
const DEV_TERMS = [
  [/target_use\s*=\s*dye/g, "tujuan celup"], [/target_use\s*=\s*print/g, "tujuan printing"],
  [/`?fabric_type`?/g, "jenis kain"], [/`?pre_treatment`?/g, "pra-proses"], [/`?process_type`?/g, "jenis proses"],
  [/`?target_use`?/g, "tujuan pra-proses"], [/`?tariff_basis`?/g, "basis tarif"], [/`([^`]+)`/g, "$1"],
];
export function cleanDevText(text) {
  const plain = DEV_TERMS.reduce((t, [re, to]) => t.replace(re, to), String(text || ""));
  return stripInternalCodes(plain
    .replace(/[;,]?\s*(?:lihat\s+)?(?:GET|POST)\s+\/api\/[\w/.-]+/gi, "")
    .replace(/\s*\(HTTP\s*\d{3}\)/g, ""));
}

export function StageChain({ stages, transitions }) {
  const label = (v) => (stages.find((s) => s.value === v)?.label || v);
  const procFor = (from, to) => transitions
    .filter((t) => t.from_stage === from && t.to_stage === to)
    .map((t) => (t.process_label || PROC_LABEL[t.process_type] || t.process_type)
      + (t.target_use ? ` ${USE_LABEL[t.target_use] || t.target_use}` : ""))
    .join(" / ");
  const steps = [
    { from: "yarn", to: "grey" },
    { from: "grey", to: "pfd" },
    { from: "pfd", to: "finished" },
  ];
  const alt = [{ from: "grey", to: "pfp" }, { from: "pfp", to: "finished" }];

  const Node = ({ v }) => (
    <span data-testid={`stage-node-${v}`}
      className="rounded-md border border-[#DCE7FA] bg-[#F6F9FF] px-2.5 py-1.5 text-[11.5px] font-semibold text-[#0058CC]">
      {label(v)}
    </span>
  );
  const Arrow = ({ from, to }) => (
    <span className="flex flex-col items-center px-1">
      <span className="text-[9.5px] font-semibold uppercase tracking-wide text-[#6B219A]">
        {procFor(from, to) || "—"}
      </span>
      <ArrowRight size={14} className="text-[#8E8E93]" />
    </span>
  );

  return (
    <div className="grid gap-2" data-testid="domain-stage-chain">
      <div className="flex flex-wrap items-center gap-1.5">
        <Node v="yarn" />
        {steps.map((s) => (
          <span key={`${s.from}-${s.to}`} className="flex items-center gap-1.5">
            <Arrow from={s.from} to={s.to} /><Node v={s.to} />
          </span>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-1.5 pl-6">
        <span className="text-[10.5px] text-[#8E8E93]">jalur printing:</span>
        <Node v="grey" />
        {alt.map((s) => (
          <span key={`${s.from}-${s.to}`} className="flex items-center gap-1.5">
            <Arrow from={s.from} to={s.to} /><Node v={s.to} />
          </span>
        ))}
      </div>
      <p className="text-[10.5px] text-[#6B6B73]">
        Aturan: satu proses <b>pra-proses</b> (scouring/bleaching) menghasilkan <b>PFD</b>
        (tujuan celup) atau <b>PFP</b> (tujuan printing). Perpindahan tahap lain ditolak sistem.
      </p>
    </div>
  );
}

/** Matriks transisi: baris = stage asal, kolom = proses. */
// UAT 24 Okt (audit UI tahap 2) — G4-21: sel memakai label registri (sama dengan kepala baris), bukan kode
// tahap mentah ("Grey · Woven", "Pfd · Dye"). `labelOf` = useDomainEnums().labelOf.
export function TransitionMatrix({ matrix, loading = false, labelOf = (_n, v) => v }) {
  if (loading) {
    return (
      <p data-testid="domain-matrix-loading" className="animate-pulse text-[11.5px] text-[#6B6B73]">
        Memuat matriks transisi…
      </p>
    );
  }
  if (!matrix.length) {
    return (
      <p data-testid="domain-matrix-empty" className="text-[11.5px] text-[#6B6B73]">
        Belum ada transisi terdaftar di registry.
      </p>
    );
  }
  const procs = matrix[0].cells.map((c) => ({ value: c.process_type, label: c.process_label }));
  return (
    <div className="overflow-x-auto" data-testid="domain-transition-matrix">
      <table className="w-full min-w-[720px] border-collapse text-[11.5px]">
        <thead>
          <tr className="bg-[#FAFBFC] text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">
            <th className="border-b border-[#EFF0F2] px-2 py-1.5 text-left">Tahap asal</th>
            {procs.map((p) => (
              <th key={p.value} className="border-b border-[#EFF0F2] px-2 py-1.5 text-left">{p.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row) => (
            <tr key={row.from_stage} data-testid={`matrix-row-${row.from_stage}`}>
              <td className="border-b border-[#EFF0F2] px-2 py-1.5 font-semibold">{row.from_label}</td>
              {row.cells.map((cell) => (
                <td key={cell.process_type} className="border-b border-[#EFF0F2] px-2 py-1.5"
                  data-testid={`matrix-cell-${row.from_stage}-${cell.process_type}`}>
                  {cell.allowed ? (
                    <span className="flex flex-wrap items-center gap-1">
                      <Check size={11} className="text-[#1E7B34]" />
                      {cell.targets.map((t, i) => (
                        <span key={i} className="status-pill pill-success">
                          {labelOf("stage", t.to_stage)}{t.target_use ? ` · ${labelOf("target_use", t.target_use)}` : ""}
                          {t.fabric_type ? ` · ${labelOf("fabric_type", t.fabric_type)}` : ""}
                        </span>
                      ))}
                    </span>
                  ) : (
                    <Minus size={11} className="text-[#C7C7CC]" />
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Tabel aturan kelengkapan field per stage (woven vs knit — D-22). */
export function FieldRuleTable({ stages, fieldRules, fieldLabels, loading = false }) {
  const lbl = (f) => fieldLabels[f] || f;
  if (loading) {
    return (
      <p data-testid="domain-field-rules-loading" className="animate-pulse text-[11.5px] text-[#6B6B73]">
        Memuat aturan kelengkapan field…
      </p>
    );
  }
  if (!stages.length) {
    return (
      <p data-testid="domain-field-rules-empty" className="text-[11.5px] text-[#6B6B73]">
        Belum ada stage terdaftar.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto" data-testid="domain-field-rules">
      <table className="w-full min-w-[620px] border-collapse text-[11.5px]">
        <thead>
          <tr className="bg-[#FAFBFC] text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">
            <th className="border-b border-[#EFF0F2] px-2 py-1.5 text-left">Stage</th>
            <th className="border-b border-[#EFF0F2] px-2 py-1.5 text-left">Woven — wajib</th>
            <th className="border-b border-[#EFF0F2] px-2 py-1.5 text-left">Knit — wajib</th>
            <th className="border-b border-[#EFF0F2] px-2 py-1.5 text-left">Disarankan (knit)</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((s) => {
            const w = fieldRules(s.value, "woven");
            const k = fieldRules(s.value, "knit");
            return (
              <tr key={s.value} data-testid={`field-rule-row-${s.value}`}>
                <td className="border-b border-[#EFF0F2] px-2 py-1.5 font-semibold">{s.label}</td>
                <td className="border-b border-[#EFF0F2] px-2 py-1.5">
                  {w.required.length ? w.required.map(lbl).join(", ") : "—"}
                </td>
                <td className="border-b border-[#EFF0F2] px-2 py-1.5">
                  {k.required.length ? k.required.map(lbl).join(", ") : "—"}
                </td>
                <td className="border-b border-[#EFF0F2] px-2 py-1.5 text-[#8C4A00]">
                  {k.recommended.length ? k.recommended.map(lbl).join(", ") : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Kartu satu enum + nilainya. */
export function EnumCard({ name, meta }) {
  const values = Array.isArray(meta?.values) ? meta.values : [];
  return (
    <div className="rounded-md border border-[#EFF0F2] bg-white p-2.5" data-testid={`enum-card-${name}`}>
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[12.5px] font-semibold" title={name}>{meta.label}</p>
        <span className={`status-pill ${meta.in_use ? "pill-success" : "pill-muted"}`}>
          {meta.in_use ? "dipakai" : "disiapkan"}
        </span>
        {/* Kode internal (meta.ps / meta.decision) sengaja tidak ditampilkan ke pengguna. 23 Okt — dulu ditulis
            `{false && …}` sehingga lint seluruh proyek merah (no-constant-binary-expression). */}
      </div>
      {meta.note && <p className="mt-1 text-[11px] text-[#6B6B73]">{cleanDevText(meta.note)}</p>}
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {values.map((v) => (
          <span key={v.value} data-testid={`enum-value-${name}-${v.value}`}
            title={stripInternalCodes(v.description || v.label)}
            className="rounded-full border border-[#E5E5EA] bg-[#FAFBFC] px-2 py-0.5 text-[11px]">
            {v.rank ? <span className="mr-1 text-[#6B219A]">urutan {v.rank}</span> : null}
            <span className="text-[#3A3A3C]">{stripInternalCodes(v.label)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
