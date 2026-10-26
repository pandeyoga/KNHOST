/**
 * TaxCenterView (EPIC 7) — Pusat Pajak: PPN (SPT Masa) + PPh (configurable).
 * Akses admin/manager (permission `accounting`). ENTITY-AWARE:
 *  - PKP/non-PKP mengikuti konfigurasi entitas (business_entities.default_tax_mode).
 *    Entitas non-PKP → PPN TIDAK berlaku (rekap ditandai jelas).
 *  - PPh butir CONFIGURABLE — FASE G-0: form konfigurasinya DIHAPUS dari sini dan
 *    pindah ke Pusat Pengaturan (satu sumber kebenaran). Tab "Konfigurasi" kini
 *    hanya mengantar ke kartu setting yang tepat.
 * Sumber: GET /api/tax/summary · POST/DELETE /api/tax/pph-records.
 *
 * Fase 3 · P4 (D-20) — layar UTAMA rekap/posisi PPN. "Rincian Pajak Masukan per Pemasok" (tabel yang sama dengan
 * Faktur Masukan) → kartu tautan ke `input-tax` dengan masa pajak yang sama; angka PPN Masukan per faktur hanya di
 * satu tabel. Preset `{ tab, period }` dibaca dari tautan (mis. baris "Posisi PPN" di Faktur Masukan).
 * L-03: pop-up Rekam DPP PPh (`fixed inset-0`) → FormModal.
 */
import { apiErrorText } from "../../utils/apiError";
import MoneyInput from "../../components/MoneyInput";
import { useCallback, useEffect, useState } from "react";
import {
  Receipt, ShieldCheck, Wallet, TrendingUp, TrendingDown, RefreshCw, Plus,
  Trash2, Settings, Building2, AlertTriangle, Landmark, ScrollText, Info, FileText,
} from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import ConfigRedirectCard from "../settings/config/ConfigRedirectCard";
import { can } from "../../config/roles";
import FormModal from "../../components/FormModal";
import LinkCard from "../../components/LinkCard";
import useViewPreset from "../../hooks/useViewPreset";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
function fmtPeriod(p) {
  if (!p || p.length !== 7) return p || "—";
  const [y, m] = p.split("-");
  return `${MONTHS[(parseInt(m, 10) || 1) - 1]} ${y}`;
}
const BASIS_LABEL = { payroll: "Otomatis · Payroll", omzet: "Otomatis · Omzet", manual: "Manual" };

const TABS = [
  { key: "ppn", label: "PPN (SPT Masa)", icon: Receipt },
  { key: "pph", label: "PPh", icon: ScrollText },
];

export default function TaxCenterView({ currentUser, selectedEntity }) {
  const preset = useViewPreset("cs-pajak", (p) => {
    if (TABS.some((t) => t.key === p.tab)) setTab(p.tab);
    if (p.period) setPeriod(p.period);
  });
  const [tab, setTab] = useState(() => (TABS.some((t) => t.key === preset?.tab) ? preset.tab : "ppn"));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState(() => preset?.period || "");
  const [recordFor, setRecordFor] = useState(null); // pph item cfg → open modal

  const canManage = can(currentUser?.permissions, "accounting", "manage");   // Sisir gerbang peran (2026-10-20) — POST/DELETE /tax/pph-records
  const entSpecific = selectedEntity && selectedEntity !== "all";

  const load = useCallback(async (p) => {
    setLoading(true);
    const ent = entSpecific ? selectedEntity : "all";
    try {
      const r = await axios.get(`${API}/tax/summary`, { params: { entity_id: ent, ...(p ? { period: p } : {}) } });
      setData(r.data || null);
      if (!p && r.data?.period) setPeriod(r.data.period);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data pajak."));
    } finally {
      setLoading(false);
    }
  }, [selectedEntity, entSpecific]);

  useEffect(() => { load(period); }, [period, selectedEntity]); // eslint-disable-line react-hooks/exhaustive-deps

  const ent = data?.entity || {};
  const cfg = data?.config || {};
  const isPkp = !!cfg.is_pkp;
  const ppn = data?.ppn || {};
  const pph = data?.pph || {};
  const periodOpts = (data?.periods || []).map((p) => ({ value: p, label: fmtPeriod(p) }));
  // Masa dari tautan yang belum ada di daftar server tetap bisa dipilih (tidak tampil kosong).
  if (period && !periodOpts.some((o) => o.value === period)) periodOpts.unshift({ value: period, label: fmtPeriod(period) });

  return (
    <div data-testid="tax-center-view">
      {/* Header */}
      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2">
            <Landmark size={16} className="text-[#0058CC]" />
            {/* UAT 24 Okt (audit UI tahap 2) — G1-40: judul kartu sama dengan judul kepala (G0-17) & isi (PPN + PPh). */}
            <h2 data-testid="tax-center-title">Pajak (PPN & PPh)</h2>
            <EntityBadge entity={ent} isPkp={isPkp} />
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <KNSelect data-testid="tax-center-period" value={period} onValueChange={setPeriod}
              options={periodOpts} className="field !py-1 !px-2 text-[12px] w-auto" placeholder="Periode" />
            <button data-testid="tax-center-refresh" className="icon-button" onClick={() => load(period)} aria-label="Muat ulang">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
        <div className="section-body py-0">
          {/* Tabs — Audit UI 24 Okt (068): tab standar biru (dulu garis bawah ungu buatan sendiri). */}
          <div className="tab-bar !mb-0">
            {TABS.map((t) => {
              const Icon = t.icon;
              const active = tab === t.key;
              return (
                <button key={t.key} data-testid={`tax-tab-${t.key}`} onClick={() => setTab(t.key)}
                  className={`tab-button inline-flex items-center gap-1.5 ${active ? "active" : ""}`}>
                  <Icon size={14} /> {t.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <ErrorNotice message={error} onRetry={() => load(period)} onDismiss={() => setError("")} testId="tax-center-error" />

      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="tax-center-loading">
          {[0, 1, 2, 3].map((i) => <div key={i} className="section-card"><div className="section-body h-16 animate-pulse bg-[#F5F5F7] rounded" /></div>)}
        </div>
      ) : (
        <>
          {tab === "ppn" && <PpnTab ppn={ppn} isPkp={isPkp} entity={ent} period={period} />}
          {tab === "pph" && (
            <PphTab pph={pph} entSpecific={entSpecific} canManage={canManage}
              onRecord={(item) => setRecordFor(item)} onReload={() => load(period)}
              entityId={selectedEntity} period={period} />
          )}
          {canManage && (
            <div className="mt-3"><ConfigRedirectCard
              title="Konfigurasi Pajak"
              note="Perubahan tarif PPN berisiko tinggi, jadi di sana Anda juga bisa mencoba dampaknya dulu sebelum menyimpan."
              group="pajak"
              testId="tax-config-redirect"
              settings={[
                { key: "tax.ppn_rate", label: "Tarif PPN" },
                { key: "tax.ppn_mode", label: "Mode PPN (included/excluded)" },
                { key: "tax.dpp_nilai_lain", label: "DPP Nilai Lain 11/12" },
                { key: "tax.efaktur_enabled", label: "Terbitkan e-Faktur" },
                { key: "tax.pph_items", label: "Daftar butir PPh" },
              ]}
            /></div>
          )}
        </>
      )}

      {recordFor && (
        <PphRecordModal item={recordFor} entityId={selectedEntity} period={period}
          onClose={() => setRecordFor(null)} onSaved={() => { setRecordFor(null); load(period); }} />
      )}
    </div>
  );
}

function EntityBadge({ entity, isPkp }) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-[#6B6B73] ml-1" data-testid="tax-entity-badge">
      <Building2 size={13} className="text-[#8E8E93]" />
      <span className="font-semibold text-[#3C3C43]">{entity?.name || "Semua Entitas"}</span>
      <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${isPkp ? "bg-[#E6F6EC] text-[#1B7F4B]" : "bg-[#F2F2F7] text-[#8E8E93]"}`}
        data-testid="tax-pkp-badge">{isPkp ? "PKP" : "Non-PKP"}</span>
      {entity?.npwp ? <span className="text-[10px] text-[#9A9BA3] tabular-nums">NPWP {entity.npwp}</span> : null}
    </span>
  );
}

/* ─────────────────────────── PPN Tab ─────────────────────────── */
function PpnTab({ ppn, isPkp, entity, period }) {
  const keluaran = ppn?.keluaran || {};
  const masukan = ppn?.masukan || {};
  const net = ppn?.net_ppn || 0;
  const position = ppn?.position || "nihil";
  const posTone = position === "kurang_bayar" ? "#C0392B" : position === "lebih_bayar" ? "#1B7F4B" : "#6B6B73";
  const bySupplier = ppn?.masukan_by_supplier || [];

  if (!isPkp) {
    return (
      <div className="section-card" data-testid="tax-ppn-nonpkp">
        <div className="section-body py-10 text-center">
          <ShieldCheck size={30} className="mx-auto mb-3 text-[#C7C7CC]" />
          <p className="text-[13px] font-bold text-[#3C3C43]">Entitas Non-PKP</p>
          <p className="text-[12px] text-[#8E8E93] mt-1 max-w-md mx-auto">
            <b>{entity?.name || "Entitas ini"}</b> tidak dikukuhkan sebagai PKP, sehingga <b>tidak memungut PPN</b> dan tidak menerbitkan Faktur Pajak. Status ini mengikuti konfigurasi entitas (mode pajak = non-PPN).
          </p>
          <p className="text-[11px] text-[#9A9BA3] mt-2">Ubah status di master entitas bila perusahaan telah dikukuhkan PKP.</p>
        </div>
      </div>
    );
  }

  return (
    <div data-testid="tax-ppn-tab">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <Kpi testId="tax-kpi-keluaran" label="Pajak Keluaran" value={formatCurrency(keluaran.ppn)} icon={TrendingUp}
          sub={`${keluaran.count || 0} faktur · DPP ${formatCurrency(keluaran.dpp)}`} color="#0058CC" />
        <Kpi testId="tax-kpi-masukan" label="Pajak Masukan" value={formatCurrency(masukan.ppn)} icon={TrendingDown}
          sub={`${masukan.count || 0} faktur · DPP ${formatCurrency(masukan.dpp)}`} color="#B45309" />
        {/* Audit UI 24 Okt (068): label posisi ("PPN Nihil" dst.) sudah tampil di kartu posisi
            di bawah — KPI ini cukup "Selisih PPN" agar tidak tertulis dua kali. */}
        <Kpi testId="tax-kpi-net" label="Selisih PPN" value={formatCurrency(Math.abs(net))}
          sub="Keluaran − Masukan" icon={Wallet} color={posTone} tone={posTone} />
      </div>

      <div className="section-card" data-testid="tax-ppn-position">
        <div className="section-body py-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${posTone}18` }}>
            <Receipt size={17} style={{ color: posTone }} />
          </div>
          <div>
            <p className="text-[12px] font-bold" style={{ color: posTone }}>{ppn?.position_label || "PPN Nihil"}</p>
            <p className="text-[11px] text-[#6B6B73]">SPT Masa PPN {fmtPeriod(period)} · Keluaran − Masukan = <b className="tabular-nums">{formatCurrency(net)}</b></p>
          </div>
        </div>
      </div>

      {/* D-20 — rincian per pemasok/faktur hanya di Faktur Masukan (masa pajak sama). */}
      <div className="mt-3">
        <LinkCard testId="tax-masukan-link" icon={FileText} view="input-tax" preset={{ period }}
          what={`Rincian Pajak Masukan ${fmtPeriod(period)}`} where="Pajak › Faktur Masukan" label="Lihat faktur"
          count={bySupplier.length ? `${bySupplier.length} pemasok` : undefined}
          summary={bySupplier.length
            ? `${masukan.count || 0} faktur · PPN Masukan di kartu atas`
            : "Belum ada Faktur Pajak Masukan pada periode ini"} />
      </div>
    </div>
  );
}

/* ─────────────────────────── PPh Tab ─────────────────────────── */
function PphTab({ pph, entSpecific, canManage, onRecord, entityId, period, onReload }) {
  const items = pph?.items || [];
  return (
    <div data-testid="tax-pph-tab">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
        <Kpi testId="tax-kpi-pph-total" label="Total PPh Periode" value={formatCurrency(pph?.total)} icon={ScrollText} color="#6B219A" />
        <div className="section-card" data-testid="tax-pph-note">
          <div className="section-body py-3 flex items-start gap-2">
            <Info size={15} className="text-[#0058CC] mt-0.5 shrink-0" />
            <p className="text-[11px] text-[#6B6B73] leading-relaxed">
              <b>PPh 21</b> ditarik otomatis dari payroll (TER). Butir lain mengikuti <b>Konfigurasi</b> — basis <i>manual</i> perlu direkam DPP-nya, basis <i>omzet</i> dihitung dari peredaran bruto.
            </p>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-head"><div className="flex items-center gap-2"><ScrollText size={15} className="text-[#6B219A]" /><h3 className="text-[12px] font-bold">Butir PPh</h3></div></div>
        <div className="section-body">
          {items.length === 0 ? (
            <div className="py-8 text-center text-[12px] text-[#8E8E93]" data-testid="tax-pph-empty">Belum ada butir PPh aktif. Aktifkan di tab Konfigurasi.</div>
          ) : (
            <div className="overflow-auto rounded-md border border-[#EFF0F2]">
              <table className="w-full text-[12px]" data-testid="tax-pph-table">
                <thead><tr className="text-left text-[10px] font-bold uppercase text-[#8E8E93] bg-[#FAFBFC] border-b border-[#EFF0F2]">
                  <th className="px-3 py-2">Butir</th><th className="px-3 py-2">Basis</th>
                  <th className="px-3 py-2 text-right">Tarif</th><th className="px-3 py-2 text-right">DPP</th>
                  <th className="px-3 py-2 text-right">PPh Terutang</th><th className="px-3 py-2 text-center">Aksi</th>
                </tr></thead>
                <tbody>
                  {items.map((it) => (
                    <tr key={it.code} data-testid={`tax-pph-row-${it.code}`} className="border-b border-[#F5F5F7] last:border-0">
                      <td className="px-3 py-2">
                        <p className="font-semibold text-[#1C1C1E]">{it.name}</p>
                        <p className="text-[10px] text-[#9A9BA3]">{String(it.source || "").replace(/(\d+) payroll run \(PPh21 aktual\/TER\)/, "$1 penggajian terposting (PPh 21 tarif efektif/TER)")}</p>
                      </td>
                      <td className="px-3 py-2"><span className="chip text-[10px]">{BASIS_LABEL[it.basis] || it.basis}</span></td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#6B6B73]">{it.basis === "payroll" ? "TER" : `${it.rate}%`}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(it.dpp)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-bold text-[#1C1C1E]">{formatCurrency(it.amount)}</td>
                      <td className="px-3 py-2 text-center">
                        {it.editable && canManage ? (
                          <button data-testid={`tax-pph-record-${it.code}`} className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#0058CC] hover:underline disabled:opacity-40 disabled:no-underline"
                            disabled={!entSpecific} onClick={() => onRecord(it)}
                            title={entSpecific ? "Rekam DPP" : "Pilih entitas spesifik di header"}>
                            <Plus size={12} /> Rekam DPP
                          </button>
                        ) : <span className="text-[10px] text-[#C7C7CC]">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot><tr className="bg-[#FAFBFC] border-t border-[#EFF0F2] text-[11px] font-bold">
                  <td className="px-3 py-2 uppercase text-[10px] text-[#6B6B73]" colSpan={4}>Total PPh</td>
                  <td className="px-3 py-2 text-right tabular-nums text-[#1C1C1E]" data-testid="tax-pph-total">{formatCurrency(pph?.total)}</td>
                  <td />
                </tr></tfoot>
              </table>
            </div>
          )}
          {!entSpecific && (
            <p className="text-[10.5px] text-[#B45309] mt-2 flex items-center gap-1" data-testid="tax-pph-allhint">
              <AlertTriangle size={12} /> Mode "Semua Entitas": rekam DPP manual dinonaktifkan. Pilih satu entitas di header untuk merekam.
            </p>
          )}
          <ManualRecordsList entityId={entityId} period={period} canManage={canManage} entSpecific={entSpecific} onReload={onReload} />
        </div>
      </div>
    </div>
  );
}

function ManualRecordsList({ entityId, period, canManage, entSpecific, onReload }) {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const entSpec = entSpecific;
  const fetchRows = useCallback(async () => {
    if (!entSpec || !period) { setRows([]); return; }
    try {
      const r = await axios.get(`${API}/tax/pph-records`, { params: { entity_id: entityId, period } });
      setRows(r.data || []);
    } catch { setRows([]); }
  }, [entityId, period, entSpec]);
  useEffect(() => { fetchRows(); }, [fetchRows]);

  const del = async (id) => {
    setBusy(true);
    try { await axios.delete(`${API}/tax/pph-records/${id}`); await fetchRows(); onReload && onReload(); }
    catch { /* noop */ } finally { setBusy(false); }
  };

  if (!entSpec || rows.length === 0) return null;
  return (
    <div className="mt-3" data-testid="tax-pph-records">
      <p className="text-[10px] font-bold uppercase text-[#8E8E93] mb-1.5">Rekaman DPP Manual · {fmtPeriod(period)}</p>
      <div className="grid gap-1.5">
        {rows.map((r) => (
          <div key={r.id} data-testid={`tax-pph-rec-${r.id}`} className="flex items-center gap-2 rounded-md border border-[#EFF0F2] bg-white px-3 py-2 text-[11.5px]">
            <span className="font-semibold text-[#3C3C43]">{r.name}</span>
            <span className="text-[#9A9BA3]">DPP {formatCurrency(r.dpp)} · {r.rate}% → <b className="text-[#1C1C1E] tabular-nums">{formatCurrency(r.amount)}</b></span>
            {r.note ? <span className="text-[#9A9BA3] truncate">· {r.note}</span> : null}
            {canManage && (
              <button data-testid={`tax-pph-rec-del-${r.id}`} className="ml-auto icon-button !w-6 !h-6" disabled={busy} onClick={() => del(r.id)} aria-label="Hapus">
                <Trash2 size={12} className="text-[#C0392B]" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PphRecordModal({ item, entityId, period, onClose, onSaved }) {
  const [dpp, setDpp] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const amount = (parseFloat(dpp) || 0) * (item.rate || 0) / 100;

  const save = async () => {
    setSaving(true); setErr("");
    try {
      await axios.post(`${API}/tax/pph-records`, {
        entity_id: entityId, period, code: item.code, name: item.name,
        rate: item.rate, dpp: parseFloat(dpp) || 0, note,
      });
      onSaved();
    } catch (e) {
      setErr(apiErrorText(e, "Gagal menyimpan rekaman."));
    } finally { setSaving(false); }
  };

  // Fase 3 · P4 (L-03) — `div fixed inset-0` buatan sendiri → FormModal baku (Esc/klik latar lewat cangkang).
  return (
    <FormModal open onClose={onClose} size="sm" icon={Plus} testId="tax-pph-modal"
      title={`Rekam DPP · ${item.name}`} subtitle={`Periode ${fmtPeriod(period)} · Tarif ${item.rate}% · PPh = DPP × tarif`}
      onSubmit={save} submitLabel={saving ? "Menyimpan…" : "Simpan"} submitTestId="tax-pph-modal-save"
      busy={saving} submitDisabled={!(parseFloat(dpp) > 0)} error={err}>
      <div className="grid gap-3">
        <label className="grid gap-1">
          <span className="text-[11px] font-semibold text-[#3C3C43]">Dasar Pengenaan Pajak (DPP)</span>
          <MoneyInput testId="tax-pph-modal-dpp" className="field" value={dpp} placeholder="mis. 10000000" onChange={(v) => setDpp(v)} />
        </label>
        <label className="grid gap-1">
          <span className="text-[11px] font-semibold text-[#3C3C43]">Keterangan (opsional)</span>
          <input data-testid="tax-pph-modal-note" className="field" placeholder="mis. Sewa gudang" value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <div className="rounded-md bg-[#EFF4FF] px-3 py-2 text-[12px] flex items-center justify-between">
          <span className="text-[#6B6B73]">PPh Terutang</span>
          <b className="text-[#0058CC] tabular-nums" data-testid="tax-pph-modal-amount">{formatCurrency(amount)}</b>
        </div>
      </div>
    </FormModal>
  );
}

function Kpi({ label, value, icon: Icon, sub, color = "#0058CC", tone = "", testId }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body flex items-center gap-3 py-3">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${color}18` }}>
          <Icon size={17} style={{ color }} />
        </div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className="text-[18px] font-bold tabular-nums truncate" style={tone ? { color: tone } : { color: "#1C1C1E" }} data-testid={`${testId}-value`}>{value}</p>
          {sub && <p className="text-[10px] text-[#9A9BA3] truncate">{sub}</p>}
        </div>
      </div>
    </div>
  );
}
