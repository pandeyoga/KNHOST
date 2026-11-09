/** rfidShared — komponen & util bersama untuk view RFID (Fase 5). */
import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { PageHeader } from "../../components/ListPageParts";
import StatusBadge from "../../components/StatusBadge";
import EmptyState, { isForbidden } from "../../components/EmptyState";
import { formatDateTime } from "../../utils/formatters";
import { LEGACY_TONE } from "../../utils/statusVocab";

export const nf = new Intl.NumberFormat("id-ID");
export const q = (v) => nf.format(Math.round((v || 0) * 100) / 100);

// FIX-8 (B3b INP-15 · G-OUT-01) — dulu `toLocaleString` tanpa zona & tanpa tahun (zona perangkat; 14 pemakaian RFID +
// antrean periksa D2). Kini formatter tunggal WIB: "10 Nov 2026 14.05 WIB".
export const fmtTime = (iso) => formatDateTime(iso);

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

// FIX-8 (B4 §3.9 · KN_37 §8) — `Pill` kini pembungkus lencana baku `StatusBadge`: ikon + teks + warna token AA.
// Dulu 10 px dengan warna hex lepas (`#34C759`/`#FF9500` di latar 10 % gagal kontras) dan tanpa ikon (warna saja).
// Nama warna lama dipetakan ke nada baku (green→berhasil, orange→perhatian, red→bahaya, purple→khusus, …).
export function Pill({ color = "gray", children, testId, status, icon }) {
  return <StatusBadge status={status} tone={LEGACY_TONE[color] || "neutral"} icon={icon} testId={testId}>{children}</StatusBadge>;
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

// FIX-8 (B4 §3.10 · B1b UI-49/UI-50) — keadaan kosong RFID = `EmptyState` baku. `loading` → "Memuat …" (bukan
// "Belum ada …" selama data belum datang); `error` (403 → "tanpa akses", lainnya → galat + Coba lagi).
export function EmptyBox({ icon, text, loading = false, error = null, onRetry, what = "data", testId }) {
  const kind = error ? undefined : loading ? "loading" : "empty";
  if (error) {
    return <EmptyState kind={isForbidden(error) ? "forbidden" : "error"} error={error} onRetry={onRetry} what={what} testId={testId} />;
  }
  return <EmptyState kind={kind} icon={icon} title={kind === "empty" ? text : undefined} what={what} testId={testId} />;
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
