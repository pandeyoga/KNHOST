/**
 * ChartOfAccounts (EPIC7-C) — Bagan Akun / Chart of Accounts.
 * Akses admin/manager (permission "accounting"). Sumber: /api/gl/accounts.
 *
 * Fase 3 · P4 (L-03) — form Tambah Akun (dulu inline di atas tabel), Ubah Akun & Detail Akun kini pop-up baku
 * (FormModal/DetailModal) di `ChartOfAccountsParts.jsx`; banner "paling nyaman di desktop" di HP (L-04 kelas C).
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Plus, BookOpen, Pencil, Trash2, X, Layers, Globe, Building2,
  ToggleLeft, ToggleRight, CheckCircle2, History,
} from "lucide-react";
import { can } from "../../config/roles";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import DesktopOnlyNotice from "../../components/DesktopOnlyNotice";
import { SearchBox } from "../../components/ListControls";
import {
  TYPE_META, TYPE_ORDER, TYPE_OPTIONS, AddAccountModal, EditAccountModal, AccountDetailModal, Kpi,
} from "./ChartOfAccountsParts";

export default function ChartOfAccounts({ entities = [], currentUser }) {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterType, setFilterType] = useState("");
  const [q, setQ] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editAcc, setEditAcc] = useState(null);
  const [detailAcc, setDetailAcc] = useState(null);
  const canAudit = can(currentUser?.permissions, "audit", "view");
  // M-3 — Scope tab: "" (template global) | "<entity_id>" (per-PT effective view)
  const [scopeEntityId, setScopeEntityId] = useState("");
  // FASE E-4 (E4.4) — pemakaian akun per badan usaha
  const [togglingCode, setTogglingCode] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = scopeEntityId ? { entity_id: scopeEntityId } : {};
      const res = await axios.get(`${API}/gl/accounts`, { params });
      setAccounts(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat bagan akun."));
    } finally {
      setLoading(false);
    }
  }, [scopeEntityId]);

  useEffect(() => { load(); }, [load]);

  const scopeLabel = useMemo(() => {
    if (!scopeEntityId) return "Template Global";
    const ent = entities.find((e) => e.id === scopeEntityId);
    return ent ? (ent.short_name || ent.code || ent.legal_name || scopeEntityId) : scopeEntityId;
  }, [scopeEntityId, entities]);

  const parentOptions = useMemo(
    () => [{ value: "", label: "— Tanpa induk (root) —" },
      ...accounts.map((a) => ({ value: a.code, label: `${a.code} — ${a.name}` }))],
    [accounts]);

  const stats = useMemo(() => {
    const byType = {};
    TYPE_ORDER.forEach((t) => { byType[t] = 0; });
    accounts.forEach((a) => { byType[a.type] = (byType[a.type] || 0) + 1; });
    const overrideCount = scopeEntityId
      ? accounts.filter((a) => a.entity_id === scopeEntityId).length
      : 0;
    return {
      total: accounts.length,
      postable: accounts.filter((a) => a.is_postable).length,
      overrideCount,
      byType,
    };
  }, [accounts, scopeEntityId]);

  const grouped = useMemo(() => {
    const t = q.trim().toLowerCase();
    const rows = accounts.filter((a) => (!filterType || a.type === filterType)
      && (!t || `${a.code} ${a.name}`.toLowerCase().includes(t)));
    const g = {};
    TYPE_ORDER.forEach((t) => { g[t] = []; });
    rows.forEach((a) => { (g[a.type] = g[a.type] || []).push(a); });
    TYPE_ORDER.forEach((t) => g[t].sort((x, y) => (x.code > y.code ? 1 : -1)));
    return g;
  }, [accounts, filterType, q]);

  const removeAccount = async (acc) => {
    setError("");
    try {
      // Kalau kita di scope PT dan akun yg dihapus punya entity_id = scope → hapus override.
      // Kalau template global (entity_id null) → hapus dari template global.
      const params = acc.entity_id ? { entity_id: acc.entity_id } : {};
      await axios.delete(`${API}/gl/accounts/${acc.code}`, { params });
      await load();
    } catch (err) {
      setError(apiErrorText(err, "Gagal menghapus akun."));
    }
  };

  // FASE E-4 (E4.4) — nyalakan/matikan akun HANYA untuk badan usaha yang sedang dibuka.
  // Sebelumnya pengguna harus membuka modal dan menebak bahwa mencentang "aktif" akan
  // melahirkan override; sekarang satu tombol dengan akibat yang tertulis jelas.
  const toggleEntityActive = async (acc) => {
    if (!scopeEntityId) return;
    setError(""); setTogglingCode(acc.code);
    try {
      const next = acc.is_active === false;
      await axios.patch(`${API}/gl/accounts/${acc.code}`,
        { name: acc.name, is_active: next },
        { params: { entity_id: scopeEntityId } });
      setNotice(next
        ? `Akun ${acc.code} sekarang dipakai ${scopeLabel}.`
        : `Akun ${acc.code} tidak dipakai ${scopeLabel} lagi (badan usaha lain tidak terpengaruh).`);
      setTimeout(() => setNotice(""), 4000);
      await load();
    } catch (err) {
      setError(apiErrorText(err, "Gagal mengubah pemakaian akun di badan usaha ini."));
    } finally { setTogglingCode(""); }
  };

  const scopeTabs = useMemo(() => {
    const tabs = [{ id: "", label: "Template Global", icon: Globe }];
    entities.forEach((e) => {
      if (e.status && e.status !== "active") return;
      tabs.push({
        id: e.id,
        label: e.short_name || e.code || e.legal_name || e.id,
        icon: Building2,
      });
    });
    return tabs;
  }, [entities]);

  return (
    <div data-testid="coa-view">
      <DesktopOnlyNotice testId="coa-desktop-notice" what="Bagan Akun" />
      {notice && (
        <div data-testid="coa-notice"
          className="mb-3 flex items-center gap-2 rounded-md border border-[#BDE5CC] bg-[#E6F6EC] px-3 py-2 text-[12px] text-[#1B7F4B]">
          <CheckCircle2 size={14} /><span>{notice}</span>
          <button className="ml-auto" onClick={() => setNotice("")} aria-label="Tutup"><X size={13} /></button>
        </div>
      )}
      {/* M-3 — Scope tabs */}
      {entities.length > 0 && (
        <div className="section-card mb-3" data-testid="coa-scope-tabs">
          <div className="section-body py-2 flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93] mr-2">
              Lingkup:
            </span>
            {scopeTabs.map((t) => {
              const Icon = t.icon;
              const active = t.id === scopeEntityId;
              return (
                <button
                  key={t.id || "global"}
                  data-testid={`coa-scope-${t.id || "global"}`}
                  onClick={() => setScopeEntityId(t.id)}
                  className={`inline-flex items-center gap-1.5 text-[12px] font-semibold rounded-full px-3 py-1 border transition
                    ${active
                      ? "bg-[#6B219A] text-white border-[#6B219A]"
                      : "bg-white text-[#3C3C43] border-[#EFF0F2] hover:border-[#6B219A]"}`}
                >
                  <Icon size={13} /> {t.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
        <Kpi testId="coa-kpi-total" label="Total Akun" value={stats.total} icon={BookOpen} />
        <Kpi testId="coa-kpi-postable" label="Akun Detail (Postable)" value={stats.postable} icon={Layers} tone="text-[#0058CC]" />
        {scopeEntityId ? (
          <Kpi testId="coa-kpi-override" label={`Override / Khusus ${scopeLabel}`} value={stats.overrideCount} icon={Building2} tone="text-[#6B219A]" />
        ) : (
          <Kpi testId="coa-kpi-asset" label="Aset / Beban" value={`${stats.byType.asset} / ${stats.byType.expense}`} icon={Layers} tone="text-[#1B7F4B]" />
        )}
        <Kpi testId="coa-kpi-liab" label="Kewajiban / Ekuitas" value={`${stats.byType.liability} / ${stats.byType.equity}`} icon={Layers} tone="text-[#6B219A]" />
      </div>

      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <BookOpen size={16} className="text-[#6B219A]" />
            <h2 data-testid="coa-title">
              Bagan Akun · <span className="text-[#6B219A]">{scopeLabel}</span>
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2 ml-auto">
            <SearchBox value={q} onChange={setQ} placeholder="Cari kode / nama akun…" testId="coa-search" />
            <div className="w-[170px]">
              <KNSelect data-testid="coa-filter-type" className="field py-1 text-[12px]" value={filterType} onValueChange={setFilterType}
                placeholder="Semua tipe" options={[{ value: "", label: "Semua tipe" }, ...TYPE_OPTIONS]} />
            </div>
            <button data-testid="coa-add-toggle" className="primary-button whitespace-nowrap" onClick={() => setShowForm(true)}>
              <Plus size={14} /> Tambah Akun
            </button>
            <button data-testid="coa-refresh" className="icon-button" onClick={load} aria-label="Muat ulang" title="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="coa-error" />

          {scopeEntityId && (
            <div className="mb-3 rounded-md border border-[#E6E0F2] bg-[#FAF8FE] px-3 py-2 text-[11px] text-[#6B219A]" data-testid="coa-scope-note">
              <b>Mode {scopeLabel}:</b> akun berlencana <b>global</b> adalah warisan template
              grup (dipakai apa adanya); akun berlencana <b>override</b> khusus badan usaha ini.
              Kolom <b>Dipakai {scopeLabel}</b> menyalakan/mematikan akun <i>hanya</i> untuk badan
              usaha ini — badan usaha lain tidak terpengaruh, dan kode akun tetap bersama
              sehingga jurnal lama tetap sah.
            </div>
          )}

          {loading ? (
            <div className="grid gap-2" data-testid="coa-loading">{[0, 1, 2, 3].map((i) => <div key={i} className="h-9 bg-[#F5F5F7] rounded animate-pulse" />)}</div>
          ) : accounts.length === 0 ? (
            <div data-testid="coa-empty" className="py-12 text-center text-[12px] text-[#8E8E93]">
              <BookOpen size={26} className="mx-auto mb-2 text-gray-300" />Belum ada akun.
            </div>
          ) : (
            <div className="space-y-4" data-testid="coa-groups">
              {TYPE_ORDER.filter((t) => grouped[t] && grouped[t].length > 0).map((t) => (
                <div key={t} data-testid={`coa-group-${t}`}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`text-[11px] font-bold uppercase tracking-wide rounded px-2 py-0.5 ${TYPE_META[t].tone}`}>{TYPE_META[t].label}</span>
                    <span className="text-[11px] text-[#9A9BA3]">{grouped[t].length} akun</span>
                  </div>
                  {/* Audit UI 24 Okt (070 HP): tabel digulir di dalam kotak; kode akun tidak patah. */}
                  <div className="overflow-x-auto rounded-md border border-[#EFF0F2]">
                    <table className="w-full min-w-[560px] text-[12px]">
                      <thead>
                        <tr className="whitespace-nowrap border-b border-[#EFF0F2] bg-[#FAFBFC] text-left text-[11px] font-bold uppercase tracking-wide text-[#8E8E93]">
                          <th className="w-[110px] px-3 py-1.5">Kode</th>
                          <th className="px-3 py-1.5">Nama Akun</th>
                          {scopeEntityId && <th className="w-[190px] px-3 py-1.5">Dipakai Entitas</th>}
                          <th className="px-3 py-1.5 text-right">Jenis · Saldo Normal</th>
                          <th className="w-[104px] px-3 py-1.5"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {grouped[t].map((a) => {
                          const isOverride = scopeEntityId && a.entity_id === scopeEntityId;
                          const usedHere = a.is_active !== false;
                          return (
                          <tr key={a.code + "|" + (a.entity_id || "g")} data-testid={`coa-row-${a.code}`} className={`border-b border-[#F5F5F7] last:border-0 ${a.is_postable ? "" : "bg-[#FAFBFC]"} ${scopeEntityId && !usedHere ? "opacity-60" : ""}`}>
                            <td className="px-3 py-2 w-[110px]"><span className="whitespace-nowrap font-mono font-semibold text-[#3C3C43] tabular-nums">{a.code}</span></td>
                            <td className="px-3 py-2">
                              <span className={a.is_postable ? "text-[#1C1C1E]" : "font-bold text-[#3C3C43] uppercase text-[11px] tracking-wide"}>{a.name}</span>
                              {a.is_active === false && !scopeEntityId && <span className="ml-2 text-[10px] text-[#C0392B]">nonaktif</span>}
                              {isOverride && (
                                <span data-testid={`coa-badge-override-${a.code}`} className="ml-2 text-[9px] font-bold uppercase tracking-wide rounded px-1.5 py-0.5 bg-[#6B219A] text-white">
                                  override
                                </span>
                              )}
                              {scopeEntityId && !isOverride && (
                                <span data-testid={`coa-badge-global-${a.code}`} className="ml-2 rounded bg-[#F5F5F7] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[#6B6B73]">
                                  global
                                </span>
                              )}
                            </td>
                            {/* FASE E-4 (E4.4) — kolom "dipakai badan usaha ini" */}
                            {scopeEntityId && (
                              <td className="px-3 py-2 w-[190px]">
                                <button type="button" data-testid={`coa-toggle-entity-active-${a.code}`}
                                  disabled={togglingCode === a.code}
                                  onClick={() => toggleEntityActive(a)}
                                  title={usedHere
                                    ? `Berhenti memakai akun ini di ${scopeLabel} (badan usaha lain tidak terpengaruh)`
                                    : `Pakai akun ini di ${scopeLabel}`}
                                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold transition-colors ${
                                    usedHere
                                      ? "border-[#BDE5CC] bg-[#E6F6EC] text-[#1B7F4B] hover:border-[#1B7F4B]"
                                      : "border-[#E5E5EA] bg-[#FAFBFC] text-[#8E8E93] hover:border-[#0058CC]"}`}>
                                  {usedHere ? <ToggleRight size={13} /> : <ToggleLeft size={13} />}
                                  {usedHere ? `Dipakai ${scopeLabel}` : `Tidak dipakai ${scopeLabel}`}
                                </button>
                              </td>
                            )}
                            <td className="whitespace-nowrap px-3 py-2 text-right text-[11px] text-[#6B6B73]">{a.is_postable ? "Detail" : "Kelompok"} · {a.normal_balance === "debit" ? "Debit" : "Kredit"}</td>
                            <td className="px-3 py-2 w-[104px] text-right">
                              <div className="inline-flex items-center gap-1">
                                <button data-testid={`coa-detail-${a.code}`} className="icon-button" onClick={() => setDetailAcc(a)} aria-label="Detail akun" title="Detail & riwayat perubahan"><History size={13} /></button>
                                <button data-testid={`coa-edit-${a.code}`} className="icon-button" onClick={() => setEditAcc(a)} aria-label="Ubah"><Pencil size={13} /></button>
                                {(!a.system || scopeEntityId) && (
                                  <button data-testid={`coa-delete-${a.code}`} className="icon-button text-[#C0392B]" onClick={() => removeAccount(a)} aria-label="Hapus"><Trash2 size={13} /></button>
                                )}
                              </div>
                            </td>
                          </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AddAccountModal open={showForm} scopeEntityId={scopeEntityId} scopeLabel={scopeLabel}
        parentOptions={parentOptions} onClose={() => setShowForm(false)}
        onSaved={async () => { setShowForm(false); await load(); }} />
      {editAcc && (
        <EditAccountModal acc={editAcc} scopeEntityId={scopeEntityId} scopeLabel={scopeLabel}
          onClose={() => setEditAcc(null)}
          onSaved={async () => { setEditAcc(null); await load(); }} />
      )}
      {detailAcc && (
        <AccountDetailModal acc={detailAcc} canAudit={canAudit} scopeLabel={scopeLabel} entities={entities} onClose={() => setDetailAcc(null)} />
      )}
    </div>
  );
}
