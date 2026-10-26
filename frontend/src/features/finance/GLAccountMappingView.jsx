import { apiErrorText } from "../../utils/apiError";
import { useEffect, useMemo, useState } from "react";
import { BookKey, RefreshCw, Info, AlertTriangle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import { useEntityScope } from "../../context/EntityScopeContext";
import { MappingRow } from "./glmapping/MappingRow";
import { MappingEditDialog } from "./glmapping/MappingEditDialog";
import { MappingHistory } from "./glmapping/MappingHistory";
import { can } from "../../config/roles";
import LinkCard from "../../components/LinkCard";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";

// GL-01 — Pemetaan Akun terpusat: setiap fitur → akun pembukuan, Global atau per PT.
// Fase 3 · P2 (D-02) — cakupannya pemetaan FITUR (bukan kategori LPJ); diberi tautan silang dua arah ke Kategori Beban.
export default function GLAccountMappingView({ currentUser }) {
  const { entities } = useEntityScope();
  const [scope, setScope] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [mod, setMod] = useState("all");
  const [q, setQ] = useState("");
  const [onlyUnset, setOnlyUnset] = useState(false);
  const [editing, setEditing] = useState(null);
  const [histKey, setHistKey] = useState(null);
  const canEdit = can(currentUser?.permissions, "gl_mapping", "update");   // Sisir gerbang peran (2026-10-20) — PUT /gl/account-mappings/{key}

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/gl/account-mappings`, { params: scope ? { entity_id: scope } : {} });
      setData(r.data); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat pemetaan akun.")); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [scope]); // eslint-disable-line

  const rows = useMemo(() => (data?.rows || []).filter((r) =>
    (mod === "all" || r.module === mod) && (!onlyUnset || r.status !== "ok")
    && (!q || `${r.label} ${r.key} ${r.account_code} ${r.account_name} ${r.used_by.join(" ")}`.toLowerCase().includes(q.toLowerCase()))), [data, mod, q, onlyUnset]);
  const scopeOpts = [{ value: "", label: "Global (semua PT)" }, ...(entities || []).filter((e) => e.id && e.id !== "all").map((e) => ({ value: e.id, label: e.short_name || e.legal_name || e.name || e.id }))];
  const modOpts = [{ value: "all", label: "Semua modul" }, ...(data?.modules || []).map((m) => ({ value: m.id, label: m.label }))];
  const s = data?.summary || {};

  return (
    <div data-testid="gl-mapping-view" className="grid gap-4">
      <DesktopOnlyNotice testId="settings-desktop-notice" what="Pengaturan" />
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="glmap-error" />
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <BookKey size={15} className="text-[#0058CC]" />
            <span className="kicker">Pengaturan · Keuangan</span>
            <h2 data-testid="glmap-title">Pemetaan Akun</h2>
          </div>
          <button data-testid="glmap-refresh" className="icon-button" onClick={load} aria-label="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
        </div>
        <div className="section-body grid gap-3">
          <div className="flex items-start gap-2 rounded-md bg-[#F0F6FF] border border-[#D6E6FF] px-3 py-2 text-[11.5px] text-[#004099]" data-testid="glmap-notice">
            <Info size={14} className="mt-0.5 shrink-0" />
            <span>Tentukan akun pembukuan yang dipakai setiap fitur. {data?.notice} {canEdit ? "" : "Hanya Admin/Finance yang dapat mengubah."}</span>
          </div>
          <LinkCard testId="glmap-expense-link" what="Akun beban per kategori pengeluaran kas kecil (LPJ)"
            where="Pengaturan › Keuangan & Pajak › Kategori Beban" view="expense-categories" hideWhenDenied />
          <SummaryCards s={s} onlyUnset={onlyUnset} setOnlyUnset={setOnlyUnset} />
          <div className="flex flex-wrap items-center gap-2">
            <div className="w-56"><KNSelect data-testid="glmap-scope" className="field text-xs" value={scope} options={scopeOpts} onValueChange={setScope} /></div>
            <div className="w-44"><KNSelect data-testid="glmap-module" className="field text-xs" value={mod} options={modOpts} onValueChange={setMod} /></div>
            <input data-testid="glmap-search" className="field text-xs w-64" placeholder="Cari kebutuhan / akun / fitur…" value={q} onChange={(e) => setQ(e.target.value)} />
            <span className="text-[11px] text-[#6B6B73]" data-testid="glmap-count">{rows.length} baris</span>
          </div>
          <div className="rounded-md border border-[#EFF0F2] overflow-hidden">
            <div className="hidden md:grid grid-cols-[1.7fr_1.4fr_110px_110px_150px] bg-[#FAFBFC] px-3 py-1.5 text-[10px] font-bold uppercase text-[#6B6B73]">
              <span>Kebutuhan</span><span>Akun dipakai</span><span>Sumber</span><span>Status</span><span className="text-right">Aksi</span>
            </div>
            {loading && !data ? <div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat…</div>
              : rows.length === 0 ? <div data-testid="glmap-empty" className="py-10 text-center text-[12px] text-[#6B6B73]">{onlyUnset && !q && mod === "all" ? "Semua kebutuhan sudah diatur." : "Tidak ada baris yang cocok."}</div>
              : <div className="divide-y divide-[#EFF0F2]">{rows.map((r) => (
                <MappingRow key={r.key} row={r} canEdit={canEdit} scoped={!!scope} onEdit={() => setEditing(r)} onHistory={() => setHistKey(r)} />))}</div>}
          </div>
        </div>
      </section>
      {editing && <MappingEditDialog row={editing} entityId={scope} scopeLabel={scopeOpts.find((o) => o.value === scope)?.label}
        onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
      {histKey && <MappingHistory mkey={histKey.key} label={histKey.label} entityId={scope} onClose={() => setHistKey(null)} />}
    </div>
  );
}

function SummaryCards({ s, onlyUnset, setOnlyUnset }) {
  // UAT 24 Okt (audit UI tahap 2) — G1-47: kartu "Belum diatur 0" tidak bisa diklik (dulu → "Tidak ada baris yang cocok").
  const none = !(s.unset > 0);
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
      <Card testId="glmap-kpi-total" label="Kebutuhan akun" value={s.total} />
      <button type="button" data-testid="glmap-kpi-unset" onClick={() => setOnlyUnset(!onlyUnset)} disabled={none && !onlyUnset}
        className={`text-left rounded-md border px-3 py-2 transition-colors disabled:cursor-default ${onlyUnset ? "border-[#E5484D] bg-[#FFF1F1]" : none ? "border-[#EFF0F2] bg-white" : "border-[#EFF0F2] bg-white hover:bg-[#FFF7F7]"}`}>
        <p className={`text-[10px] uppercase font-bold flex items-center gap-1 ${none ? "text-[#6B6B73]" : "text-[#B42318]"}`}><AlertTriangle size={11} /> Belum diatur</p>
        <p className="text-lg font-semibold">{s.unset ?? 0}</p>
        <p className="text-[10px] text-[#6B6B73]">{onlyUnset ? "Klik untuk tampilkan semua" : none ? "Semua kebutuhan sudah diatur" : "Klik untuk menyaring"}</p>
      </button>
      <Card testId="glmap-kpi-custom" label="Diubah dari bawaan" value={s.custom} />
      <Card testId="glmap-kpi-entity" label="Khusus PT ini" value={s.entity_override} />
    </div>
  );
}

function Card({ testId, label, value }) {
  return (
    <div data-testid={testId} className="rounded-md border border-[#EFF0F2] bg-white px-3 py-2">
      <p className="text-[10px] uppercase font-bold text-[#6B6B73]">{label}</p>
      <p className="text-lg font-semibold">{value ?? 0}</p>
    </div>
  );
}
