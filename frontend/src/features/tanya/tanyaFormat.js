import { formatCurrency, formatQty } from "../../utils/formatters";

export const PERIOD_LABELS = {
  today: "Hari ini", this_week: "Minggu ini", mtd: "Bulan ini", last_month: "Bulan lalu",
  last_90d: "3 bulan", ytd: "Tahun ini",
};

export const WEEKDAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];

export const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }) : "—");

export const scheduleLabel = (s) => (s.frequency === "weekly" ? `Tiap ${WEEKDAYS[s.weekday || 0]}` : "Tiap hari") + ` · ${s.time} WIB`;

/** Giliran sesi tersimpan → entri percakapan di layar. */
export function turnsToThread(session) {
  const out = [];
  (session.turns || []).forEach((t) => {
    if (t.role === "user") out.push({ id: `${session.id}-${out.length}`, question: t.content, context: t.context || null });
    else if (out.length) {
      const e = out[out.length - 1];
      if (t.suggestions) Object.assign(e, { notice: t.content, suggestions: t.suggestions });
      else e.answer = { kind: "chat", question: e.question, text: t.content, verification: t.verification, resultIds: t.result_ids || [], sessionId: session.id };
    }
  });
  return out;
}

export const SALES_DEF_LABELS = {
  net_order: "Pesanan bersih tanpa PPN, menurut tanggal pesanan",
  recognized: "Pendapatan diakui (saat barang dikirim)",
};

export const ATTRIBUTION_LABELS = {
  team_split: "Dibagi sesuai % tim sales di pesanan",
  customer_owner: "Sales penanggung jawab pelanggan",
};

export function formatValue(unit, v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v !== "number") return String(v);
  if (unit === "idr") return formatCurrency(v);
  if (unit === "pct") return `${v.toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
  return formatQty(v);
}

export function shortIdr(v) {
  if (typeof v !== "number") return v;
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toLocaleString("id-ID", { maximumFractionDigits: 1 })} M`;
  if (a >= 1e6) return `${(v / 1e6).toLocaleString("id-ID", { maximumFractionDigits: 1 })} jt`;
  if (a >= 1e3) return `${(v / 1e3).toLocaleString("id-ID", { maximumFractionDigits: 0 })} rb`;
  return v.toLocaleString("id-ID");
}

export const labelOf = (result, key) => (result?.columns || []).find((c) => c.key === key)?.label || key;
export const unitOf = (result, key) => (result?.columns || []).find((c) => c.key === key)?.unit || "";

/** Pecah jawaban model menjadi teks & blok kn-chart / kn-table / kn-followups. */
export function splitAnswer(text) {
  const parts = [];
  const re = /```(kn-chart|kn-table|kn-followups|kn-action)\s*([\s\S]*?)```/g;
  let last = 0;
  let m;
  while ((m = re.exec(text || "")) !== null) {
    if (m.index > last) parts.push({ kind: "text", text: text.slice(last, m.index) });
    try { parts.push({ kind: m[1], spec: JSON.parse(m[2]) }); } catch { /* blok rusak diabaikan */ }
    last = re.lastIndex;
  }
  if (last < (text || "").length) parts.push({ kind: "text", text: text.slice(last) });
  return parts;
}

export function fmtUsd(v) {
  const n = Number(v) || 0;
  const digits = n > 0 && n < 1 ? 4 : 2;
  return `US$ ${n.toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

export const fmtInt = (v) => (Number(v) || 0).toLocaleString("id-ID");

export const COST_METRICS = { usd: { label: "Biaya (USD)", fmt: fmtUsd }, calls: { label: "Panggilan", fmt: fmtInt }, tokens: { label: "Token", fmt: fmtInt } };

export const shortDay = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString("id-ID", { day: "numeric", month: "short" });
