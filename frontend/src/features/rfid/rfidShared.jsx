/** rfidShared — komponen & util bersama untuk view RFID (Fase 5). */
import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { PageHeader } from "../../components/ListPageParts";

export const nf = new Intl.NumberFormat("id-ID");
export const q = (v) => nf.format(Math.round((v || 0) * 100) / 100);

export function fmtTime(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

// Ambil daftar gudang + state pilihan (dipakai semua view RFID).
export function useWarehouses() {
  const [warehouses, setWarehouses] = useState([]);
  const [whId, setWhId] = useState("");
  useEffect(() => {
    axios.get(`${API}/warehouses`).then((r) => setWarehouses(r.data || [])).catch(() => {});
  }, []);
  const whOpts = [{ value: "", label: "Semua Gudang" }, ...warehouses.map((w) => ({ value: w.id, label: w.name }))];
  return { warehouses, whId, setWhId, whOpts };
}

const COLORS = {
  green: "#34C759", red: "#C0341D", info: "#0058CC", blue: "#0058CC",
  orange: "#FF9500", purple: "#5856D6", gray: "#8E8E93",
};

export function Pill({ color = "gray", children, testId }) {
  const c = COLORS[color] || COLORS.gray;
  return (
    <span data-testid={testId} className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold"
      style={{ background: `${c}1A`, color: c }}>{children}</span>
  );
}

// Peta result read → warna pill.
export function resultColor(r) {
  return r === "green" ? "green" : r === "red" ? "red" : "info";
}

export function Stat({ icon: Icon, label, value, sub, color = "#0058CC", loading, testId }) {
  return (
    <div data-testid={testId} className="rounded-xl border border-[#EFF0F2] bg-white p-4 flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <div className="rounded-lg p-1.5" style={{ background: `${color}18` }}><Icon size={15} style={{ color }} /></div>
        <span className="text-[12px] font-semibold text-[#6B6B73]">{label}</span>
      </div>
      {loading ? <div className="h-6 bg-[#F5F5F7] rounded animate-pulse" />
        : <p className="text-[19px] font-bold text-[#1C1C1E] tabular-nums leading-tight">{value}</p>}
      {sub && <p className="text-[11px] text-[#6B6B73]">{sub}</p>}
    </div>
  );
}

export function EmptyBox({ icon: Icon, text }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      <div className="rounded-full bg-[#F5F5F7] p-3"><Icon size={22} className="text-[#8E8E93]" /></div>
      <p className="text-[12px] text-[#6B6B73] max-w-xs">{text}</p>
    </div>
  );
}

// Fase 4 · R3 (L-02) — kartu seksi & kepala halaman RFID memakai kelas baku (`.section-card` + `.section-head`, dan
// `PageHeader`). Dulu kartu `rounded-xl … p-4` dan judul h1 20 px berkicker "RFID & KETERTELUSURAN" buatan sendiri —
// lokasi kini dibaca dari breadcrumb menu. Tab dalam layar = `PageTabs` (TabBtn buatan sendiri dicabut).
export function SectionCard({ title, right, children, testId }) {
  return (
    <section className="section-card" data-testid={testId}>
      {(title || right) && (
        <div className="section-head flex-wrap">
          <h2>{title}</h2>
          {right}
        </div>
      )}
      <div className="section-body">{children}</div>
    </section>
  );
}

// Header standar view RFID (judul + kontrol kanan) = PageHeader baku.
export function RfidHeader({ icon, title, subtitle, children, testId }) {
  return <PageHeader icon={icon} title={title} subtitle={subtitle} testId={testId} actions={children} />;
}
