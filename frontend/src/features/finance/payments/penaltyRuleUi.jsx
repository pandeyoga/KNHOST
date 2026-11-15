/**
 * penaltyRuleUi (CR-T4) — potongan bersama ATURAN DENDA berlapis PT → pelanggan → rencana
 * (`docs/blueprint/unit/CR-T4.md`, bagian Layar):
 *
 *  · `PenaltyRuleFields` — empat isian aturan denda (tarif % per bulan, dasar hitung, batas atas % dari dasar, hari
 *    tenggang). Kosong = ikut aturan di atasnya. Dipakai pop-up "Ajukan perubahan kredit" (aturan khusus pelanggan) dan
 *    form rencana bayar (`PaymentPlanBuilder`, aturan khusus rencana).
 *  · `ruleText` / `normRule` / `ruleFromForm` — teks manusia & bentuk baku `penalty_rule` (sama dengan server
 *    `credit_profile_service._aturan_denda`: ikut PT = null).
 *  · `sourceText` — "PT · pelanggan · rencana" dari `policy_snapshot.sources` nota denda (L6: siapa yang menentukan).
 * Teks untuk manusia saja (L1): kode `installment`/`outstanding`/`pelanggan` tidak pernah tampil.
 */
import DecimalInput from "../../../components/DecimalInput";
import KNSelect from "../../../components/KNSelect";
import { parseDecimal } from "../../../utils/decimalInput";
import { formatDate } from "../../../utils/formatters";

export const RULE_MODE_OPTIONS = [
  { value: "ikut_pt", label: "Ikut PT" },
  { value: "khusus", label: "Khusus" },
  { value: "bebas", label: "Bebas denda" },
];
export const BASE_LABEL = { installment: "Sisa tagihan yang telat", outstanding: "Seluruh sisa pesanan" };
export const BASE_OPTIONS = [
  { value: "", label: "Ikut aturan di atasnya" },
  { value: "installment", label: BASE_LABEL.installment },
  { value: "outstanding", label: BASE_LABEL.outstanding },
];
/** Batas angka = registry (`ar.denda_rate_pct_per_month`, `payment.penalty_cap_pct` 0–100; `ar.grace_days` 0–180). */
export const RULE_LIMITS = { pct: [0, 100], grace: [0, 180] };
const SOURCE_WORD = { global: "PT", pt: "PT", pelanggan: "pelanggan", rencana: "rencana" };
const NUM_FIELDS = ["rate_pct_per_month", "cap_pct", "grace_days"];

const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
const pctText = (v) => `${String(v).replace(".", ",")} %`;

/** `penalty_rule` tersimpan → bentuk baku pembanding (null = ikut PT). */
export function normRule(rule) {
  const mode = rule?.mode || "ikut_pt";
  if (mode === "bebas") return { mode, reason: String(rule.reason || ""), valid_until: String(rule.valid_until || "").slice(0, 10) };
  if (mode !== "khusus") return null;
  return { mode, rate_pct_per_month: num(rule.rate_pct_per_month), cap_pct: num(rule.cap_pct),
    grace_days: num(rule.grace_days), base: rule.base || "" };
}

/** Isian form (teks) → nilai form awal dari aturan tersimpan. */
export function formFromRule(rule) {
  const r = normRule(rule) || { mode: "ikut_pt" };
  const t = (v) => (v === null || v === undefined ? "" : String(v).replace(".", ","));
  return { mode: r.mode, rate_pct_per_month: t(r.rate_pct_per_month), cap_pct: t(r.cap_pct), grace_days: t(r.grace_days),
    base: r.base || "", reason: r.reason || "", valid_until: r.valid_until || "" };
}

/** Isian empat angka (teks) → angka atau null; `bad` = daftar isian yang tidak sah (untuk "Lengkapi: …"). */
export function numbersFromForm(f) {
  const out = {};
  const bad = [];
  NUM_FIELDS.forEach((k) => {
    const raw = String(f?.[k] ?? "").trim();
    if (raw === "") { out[k] = null; return; }
    const n = parseDecimal(raw);
    const [lo, hi] = k === "grace_days" ? RULE_LIMITS.grace : RULE_LIMITS.pct;
    if (!Number.isFinite(n) || n < lo || n > hi || (k === "grace_days" && !Number.isInteger(n))) bad.push(k);
    out[k] = n;
  });
  return { values: { ...out, base: f?.base || "" }, bad };
}

/** Form aturan pelanggan → `penalty_rule` yang dikirim (null = ikut PT). */
export function ruleFromForm(f) {
  if (f.mode === "bebas") return { mode: "bebas", reason: String(f.reason || "").trim(), valid_until: f.valid_until || "" };
  if (f.mode !== "khusus") return null;
  return { mode: "khusus", ...numbersFromForm(f).values };
}

export const FIELD_WORD = { rate_pct_per_month: "tarif denda", cap_pct: "batas atas denda", grace_days: "hari tenggang" };

/** Aturan denda satu pelanggan sebagai teks pendek (riwayat & konfirmasi pengajuan). */
export function ruleText(rule) {
  const r = normRule(rule);
  if (!r) return "Ikut PT";
  if (r.mode === "bebas") return `Bebas denda s.d. ${r.valid_until ? formatDate(r.valid_until) : "—"}`;
  const parts = [];
  if (r.rate_pct_per_month !== null) parts.push(`tarif ${pctText(r.rate_pct_per_month)} per bulan`);
  if (r.base) parts.push(`dasar ${(BASE_LABEL[r.base] || "").toLowerCase()}`);
  if (r.cap_pct !== null) parts.push(`batas atas ${pctText(r.cap_pct)}`);
  if (r.grace_days !== null) parts.push(`tenggang ${r.grace_days} hari`);
  return parts.length ? `Khusus: ${parts.join(", ")}` : "Khusus (semua ikut PT)";
}

/** "PT · pelanggan · rencana" — asal unsur aturan nota denda (`policy_snapshot.sources`), urut umum → khusus. */
export function sourceText(sources) {
  if (!sources) return "";
  const kata = new Set(Object.values(sources).map((s) => SOURCE_WORD[s]).filter(Boolean));
  return ["PT", "pelanggan", "rencana"].filter((k) => kata.has(k)).join(" · ");
}

/**
 * Empat isian aturan denda. `value` = objek teks {rate_pct_per_month, base, cap_pct, grace_days}; `onChange(k, v)`;
 * `bad` = daftar isian tidak sah (garis merah); `hint` = keterangan arti kosong.
 */
export function PenaltyRuleFields({ value, onChange, bad = [], testPrefix, hint }) {
  const v = value || {};
  const field = (k, label, suffix, placeholder) => (
    <div>
      <label className="field-label" htmlFor={`${testPrefix}-${k}`}>{label}</label>
      <DecimalInput id={`${testPrefix}-${k}`} data-testid={`${testPrefix}-${k}`} value={v[k] ?? ""} suffix={suffix}
        placeholder={placeholder} invalid={bad.includes(k)} onChange={(t) => onChange(k, t)} className="field" />
    </div>
  );
  return (
    <div className="grid gap-2">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {field("rate_pct_per_month", "Tarif denda (% per bulan)", "%", "ikut")}
        <div>
          <label className="field-label" htmlFor={`${testPrefix}-base`}>Dasar hitung</label>
          <KNSelect id={`${testPrefix}-base`} value={v.base || ""} onValueChange={(x) => onChange("base", x)} className="field"
            data-testid={`${testPrefix}-base`} options={BASE_OPTIONS} />
        </div>
        {field("cap_pct", "Batas atas (% dari dasar)", "%", "ikut")}
        {field("grace_days", "Hari tenggang", "hari", "ikut")}
      </div>
      {hint && <p className="text-fs-12 text-kn-text-2" data-testid={`${testPrefix}-hint`}>{hint}</p>}
    </div>
  );
}
