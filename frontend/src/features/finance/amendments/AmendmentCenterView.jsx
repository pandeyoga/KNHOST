/**
 * AmendmentCenterView — FASE G-1 · PUSAT AMANDEMEN.
 *
 * Satu layar untuk seluruh siklus koreksi dokumen keuangan:
 *   · antrean yang menunggu persetujuan (dengan dampak rupiah yang sudah dihitung);
 *   · riwayat koreksi yang sudah diterapkan / ditolak beserta pengusul & pemutus;
 *   · taksonomi label alasan yang bisa diubah admin tanpa deploy.
 *
 * Angka ringkasan di atas berasal dari `GET /amendments/stats/summary` — bukan
 * hitungan ulang di browser — supaya badge dan daftar tidak pernah berbeda cerita.
 *
 * Fase 4 · R2 — L-01: navigasi 3 tingkat (bilah hub › tab-bar berisi SATU tab "Daftar Amandemen" › tab status)
 * dipangkas: tab tunggal dibuang (lencananya dulu bertabrakan dengan saringan), tautan "Label Alasan" pindah ke kepala
 * kartu, tab status → `FilterChips` (saringan, `amd-filter-*` tetap). KPI → `MetricRow` baku (nol netral).
 * Rincian: berdampingan di ≥1024 px seperti dulu; di layar lebih sempit (HP/tablet) dulu jatuh DI BAWAH daftar →
 * kini `DetailModal`.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ExternalLink, RefreshCw, Scale, Search, Tag,
} from "lucide-react";
import DetailModal from "../../../components/DetailModal";
import EntityBadge from "../../../components/EntityBadge";
import ErrorNotice from "../../../components/ErrorNotice";
import FilterChips from "../../../components/FilterChips";
import { MetricRow } from "../../../components/ListPageParts";
import useIsMobile from "../../../hooks/useIsMobile";
import { formatCurrency } from "../../../utils/formatters";
import { openConfig } from "../../settings/config/configDeepLink";
import AmendmentDetailPanel from "./AmendmentDetailPanel";
import { amendmentStats, errText, listAmendments, methodMeta, statusMeta } from "./amendmentApi";
import { can } from "../../../config/roles";

const STATUS_TABS = [
  { key: "", label: "Semua" },
  { key: "pending_approval", label: "Menunggu persetujuan" },
  { key: "applied", label: "Diterapkan" },
  { key: "auto_applied", label: "Diterapkan otomatis" },
  { key: "rejected", label: "Ditolak" },
];

function when(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("id-ID", { dateStyle: "short", timeStyle: "short" }); }
  catch { return iso; }
}

export default function AmendmentCenterView({ currentUser, selectedEntity }) {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  const canSeeReasons = can(currentUser?.permissions, "finance_amendment", "propose");
  // Di bawah 1024 px rincian tidak lagi berdampingan dengan daftar → tampil sebagai pop-up.
  const stacked = useIsMobile(1023);   // Sisir gerbang peran (2026-10-20) — GET /amendment-reasons

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const [list, st] = await Promise.all([
        listAmendments({ ...params, ...(status ? { status } : {}) }),
        amendmentStats(params).catch(() => ({})),
      ]);
      setRows(list);
      setStats(st || {});
      setError("");
    } catch (e) {
      setError(errText(e, "Gagal memuat daftar amandemen."));
    } finally {
      setLoading(false);
    }
  }, [selectedEntity, status]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return rows;
    return rows.filter((r) => [r.number, r.doc_number, r.reason_label, r.proposed_by]
      .some((v) => (v || "").toLowerCase().includes(term)));
  }, [rows, q]);

  const applied = Number(stats.applied || 0) + Number(stats.auto_applied || 0);

  return (
    <div data-testid="amendment-center-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="amd-center-error" />

      <div className="section-card mb-3">
        <div className="section-head flex-wrap gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Scale size={16} className="text-[#0058CC]" />
            <div className="min-w-0">
              <h2 data-testid="amd-center-title">Pusat Amandemen</h2>
              <p className="text-[11px] text-[#6B6B73]">
                Setiap koreksi angka pada dokumen keuangan tercatat di sini — bernomor, ber-alasan,
                ber-dampak, dan ber-penyetuju. Tidak ada edit senyap.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {canSeeReasons && (
              <a data-testid="amd-reasons-link" href="?view=amendment-reasons" className="self-center text-[11px] font-semibold text-[#0058CC] underline">
                <Tag size={12} className="mr-1 inline" /> Label Alasan (Pengaturan)
              </a>
            )}
            <button type="button" data-testid="amd-open-policy-config" className="secondary-button"
              onClick={() => openConfig({ group: "amandemen" })}>
              <ExternalLink size={13} /> Ambang & Aturan
            </button>
            <button type="button" data-testid="amd-center-refresh" className="secondary-button" onClick={load}>
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat ulang
            </button>
          </div>
        </div>
        <div className="section-body">
          <MetricRow testId="amd-center-stats" items={[
            { label: "Total amandemen", value: String(stats.total ?? 0), testId: "amd-kpi-total" },
            { label: "Menunggu persetujuan", value: String(stats.pending_approval ?? 0), tone: "#B26A00", testId: "amd-kpi-pending" },
            // Audit UI 24 Okt (005) — KPI ini menjumlah "Diterapkan" + "Diterapkan otomatis"; labelnya menyebut itu
            // supaya tidak tampak bertentangan dengan saringan "Diterapkan 0".
            { label: "Sudah diterapkan (termasuk otomatis)", value: String(applied), tone: "#1B7F4B", testId: "amd-kpi-applied" },
            { label: "Ditolak", value: String(stats.rejected ?? 0), tone: "#9B1C1C", testId: "amd-kpi-rejected" },
            { label: "Total dampak diterapkan", value: formatCurrency(stats.impact_total || 0), tone: "#0058CC", testId: "amd-kpi-impact" },
          ]} />
        </div>
      </div>

      {(

        <>
          <div className="section-card mb-3">
            <div className="section-body flex flex-wrap items-center gap-2">
              <div className="relative w-full sm:max-w-sm sm:flex-1">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
                <input data-testid="amd-search" value={q} onChange={(e) => setQ(e.target.value)}
                  className="field !pl-8" placeholder="Cari no. amandemen / dokumen / alasan / pengusul…" />
              </div>
              <FilterChips testId="amd-status-filters" ariaLabel="Saring status amandemen" className="min-w-0"
                value={status || "all"} onChange={(k) => { setStatus(k === "all" ? "" : k); setSelected(null); }}
                options={STATUS_TABS.map((f) => ({
                  key: f.key || "all", label: f.label, testId: `amd-filter-${f.key || "all"}`,
                  count: Number((f.key ? stats[f.key] : stats.total) ?? 0),
                }))} />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_360px]">
            <section className="section-card">
              <div className="section-head">
                <h3 className="text-[12.5px] font-bold">Daftar amandemen</h3>
                <span className="text-[10.5px] text-[#8E8E93]">{filtered.length} dokumen</span>
              </div>
              <div className="overflow-hidden">
                <div className="grid grid-cols-[1fr_110px_140px] gap-2 border-b border-[#EFF0F2] bg-[#FAFBFC] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">
                  <span>Amandemen</span><span className="text-right">Dampak</span><span>Status</span>
                </div>
                <div className="max-h-[620px] divide-y divide-[#EFF0F2] overflow-y-auto">
                  {loading && (
                    <p className="animate-pulse px-3 py-10 text-center text-[12px] text-[#6B6B73]">Memuat amandemen…</p>
                  )}
                  {!loading && filtered.length === 0 && (
                    <div data-testid="amd-list-empty" className="px-3 py-12 text-center text-[12px] text-[#6B6B73]">
                      <Scale className="mx-auto mb-2 text-gray-300" size={28} />
                      <p className="font-semibold text-[#3C3C43]">Tidak ada amandemen pada filter ini.</p>
                      <p>Koreksi dokumen diajukan dari panel detail Pesanan Penjualan.</p>
                    </div>
                  )}
                  {!loading && filtered.map((a) => {
                    const sm = statusMeta(a.status);
                    const mm = methodMeta(a.method);
                    const delta = Number(a.impact?.delta || 0);
                    return (
                      <div key={a.id} data-testid={`amd-row-${a.id}`} role="button" tabIndex={0}
                        onClick={() => setSelected(a.id)}
                        onKeyDown={(e) => { if (e.key === "Enter") setSelected(a.id); }}
                        className={`grid cursor-pointer grid-cols-[1fr_110px_140px] items-center gap-2 px-3 py-2.5 transition-colors hover:bg-[#FAFBFC] ${selected === a.id ? "border-l-2 border-[#007AFF] bg-[#EFF4FF]" : ""}`}>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[12px] font-bold text-[#0058CC]">{a.number}</span>
                            <EntityBadge entityId={a.entity_id} />
                            <span className="rounded px-1 py-0.5 text-[8.5px] font-bold uppercase tracking-wide"
                              style={{ background: mm.bg, color: mm.fg }}>{mm.label}</span>
                          </div>
                          <p className="truncate text-[10.5px] text-[#6B6B73]">
                            {a.doc_number} · {a.reason_label}
                          </p>
                          <p className="truncate text-[10px] text-[#9A9BA3]">
                            {a.proposed_by || "—"} · {when(a.proposed_at)}
                          </p>
                        </div>
                        <p className={`text-right text-[12px] font-bold tabular-nums ${Math.abs(delta) < 0.005 ? "text-[#6B6B73]" : delta < 0 ? "text-[#A8221A]" : "text-[#1B7A43]"}`}>
                          {Math.abs(delta) < 0.005 ? "" : delta < 0 ? "− " : "+ "}{formatCurrency(Math.abs(delta))}
                        </p>
                        <span className="justify-self-start whitespace-nowrap rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide"
                          style={{ background: sm.bg, color: sm.fg }}>{sm.label}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            {stacked ? null : selected ? (
              <AmendmentDetailPanel amdId={selected} currentUser={currentUser}
                onDecided={load} onClose={() => setSelected(null)} />
            ) : (
              <aside className="section-card flex min-h-[220px] items-center justify-center border-dashed">
                <div className="p-6 text-center">
                  <Scale size={28} className="mx-auto mb-2 text-gray-300" />
                  <p className="text-[12px] text-[#6B6B73]">Pilih amandemen untuk melihat dampak, ambang, dan memutuskan.</p>
                </div>
              </aside>
            )}
          </div>
        </>
      )}

      {stacked && selected && (
        <DetailModal open onClose={() => setSelected(null)} size="lg" label="Rincian amandemen" testId="amd-detail-modal">
          <AmendmentDetailPanel amdId={selected} currentUser={currentUser}
            onDecided={load} onClose={() => setSelected(null)} />
        </DetailModal>
      )}
    </div>
  );
}
