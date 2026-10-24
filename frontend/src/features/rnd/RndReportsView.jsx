/**
 * RndReportsView (FASE F · PS-18) — **Laporan R&D**: pertanyaan pemilik dijawab dari
 * data NYATA (bukan angka hias):
 *   1. Round mana yang TERLAMBAT sekarang? (papan SLA)
 *   2. Berapa produk yang masih BELUM boleh dijual, dan di tahap apa? (papan lifecycle)
 *
 * CATATAN IA (PS-18): tabel kinerja pelaksana yang dulu ada di sini DIPINDAH ke menu
 * **Desainer › KPI Desainer** (lebih kaya: tepat waktu, pengulangan, nilai komposit,
 * filter periode). Di layar ini tinggal ringkasan 3 teratas + pintu masuknya, supaya
 * tidak ada dua tempat yang mengaku sumber kebenaran kinerja desainer.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, BarChart3, Palette, RefreshCw, Settings2 } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import { formatCurrency } from "../../utils/formatters";
import { openConfig } from "../settings/config/configDeepLink";
import { designerKpi } from "../designer/designerApi";
import { gradeMeta, num } from "../designer/designerMeta";
import { lifecycleBoard, listSamples, performerReport, sampleTypes } from "./rndApi";
import { openRnd } from "./rndDeepLink";
import { errMsg, lifecycleMeta } from "./rndMeta";
import { roundTypeOf, typeLabel } from "./sampleTypeMeta";
import { roleIs } from "../../config/roles";
import { actorLabel, isTechActor } from "../../utils/actorLabel";

/** Audit UI 24 Okt (042) — "Desainer Teratas": akun teknis (system-seed) bukan orang, dan desainer tanpa
 *  bukti kerja (0 ronde & 0 versi desain) tidak ikut diperingkat. Urutan tetap urutan nilai komposit server
 *  (sama dengan KPI Desainer); nomor peringkat dihitung ulang setelah penyaringan. */
function topDesigners(items, n = 3) {
  return (items || [])
    .filter((p) => !isTechActor(p.designer) && p.grade_score != null
      && (Number(p.rounds || 0) > 0 || Number(p.design_versions || 0) > 0))
    .slice(0, n)
    .map((p, i) => ({ ...p, rank: i + 1 }));
}

export default function RndReportsView({ currentUser, selectedEntity }) {
  const [perf, setPerf] = useState([]);
  const [stats, setStats] = useState({});
  const [board, setBoard] = useState({});
  const [samples, setSamples] = useState([]);
  const [types, setTypes] = useState([]);   // FASE S — kosakata jenis dari MASTER
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // md HP — designer-kpi bisa 403 untuk peran tertentu; dulu ditelan jadi "belum ada round" (galat tersamar).
  const [kpiDenied, setKpiDenied] = useState(false);

  const canManage = roleIs(currentUser?.role, ["admin", "manager"]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const [rep, kpi, brd, smp, typ] = await Promise.all([
        performerReport(params),
        designerKpi({ ...params, period: "30d" })
          .catch((e) => ({ items: [], denied: [401, 403].includes(e?.response?.status) })),
        lifecycleBoard(params).catch(() => ({})),
        listSamples({ ...params, limit: 300 }).catch(() => ({ items: [] })),
        // FASE S — kosakata jenis dari MASTER: jenis yang ditambah pemilik muncul
        // di papan SLA dengan NAMANYA, bukan sebagai kode teknis (`sanforize`).
        sampleTypes(params).catch(() => []),
      ]);
      setStats(rep?.stats || {});
      setKpiDenied(Boolean(kpi?.denied));
      setPerf(topDesigners(kpi?.items));
      setBoard(brd || {});
      setSamples(smp?.items || []);
      setTypes(Array.isArray(typ) ? typ : []);
      setError("");
    } catch (e) {
      setError(errMsg(e, "Gagal memuat laporan R&D."));
    } finally { setLoading(false); }
  }, [selectedEntity]);
  useEffect(() => { load(); }, [load]);

  /** Papan SLA — round yang masih berjalan; yang terlambat naik ke atas. */
  const slaRows = useMemo(() => {
    const out = [];
    samples.forEach((s) => {
      (s.rounds || []).forEach((r) => {
        if (r.status === "open" || r.status === "submitted") {
          out.push({
            key: r.id, number: s.number, title: s.title,
            // FASE S — jenis ROUND: satu permintaan bisa menempuh labdip & handfeel,
            // dan yang menunggu hasil hanya salah satunya.
            type: roundTypeOf(r, s), supplier: r.supplier_name,
            round_no: r.round_no, due: r.due_date || "—",
            state: r.status === "open" ? "menunggu hasil supplier" : "menunggu penilaian",
            overdue: Boolean(r.overdue) || isPast(r.due_date),
          });
        }
      });
    });
    out.sort((a, b) => (Number(b.overdue) - Number(a.overdue))
      || String(a.due).localeCompare(String(b.due)));
    return out;
  }, [samples]);

  const lifeCounts = board?.counts || {};
  const notOrderable = board?.not_orderable || [];

  return (
    <div data-testid="rnd-reports-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")}
        testId="rnd-reports-error" />

      <div className="section-card mb-3">
        <div className="section-head flex-wrap">
          <div className="flex items-center gap-2">
            <BarChart3 size={16} className="text-[#0058CC]" />
            <h2 data-testid="rnd-reports-title">Laporan R&D</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="secondary-button" onClick={load} data-testid="rnd-reports-refresh">
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat ulang
            </button>
            {canManage && (
              <button className="secondary-button" data-testid="rnd-reports-policy-button"
                onClick={() => openConfig({ group: "rnd", key: "rnd.round_sla_days" })}>
                <Settings2 size={13} /> Target SLA
              </button>
            )}
          </div>
        </div>
        <div className="section-body">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5" data-testid="rnd-reports-kpi">
            <Kpi label="Total permintaan" value={String(stats.total ?? 0)} />
            <Kpi label="Ronde berjalan" value={String(stats.open_rounds ?? 0)} tone="#0058CC" />
            <Kpi label="Ronde terlambat" value={String(stats.overdue_rounds ?? 0)} tone="#C0392B" />
            <Kpi label="Sudah diputus" value={String(stats.decided ?? 0)} tone="#1B7F4B" />
            <Kpi label="Total biaya sample" value={formatCurrency(stats.cost_total || 0)} />
          </div>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {/* Ringkasan kinerja desainer — sumber lengkapnya di menu Desainer */}
        <div className="section-card">
          <div className="section-head flex-wrap">
            <div className="flex items-center gap-2">
              <Palette size={16} className="text-[#6B219A]" />
              <h2>Desainer Teratas (30 hari)</h2>
            </div>
            {!kpiDenied && (
              <button className="secondary-button" data-testid="rnd-reports-open-designer"
                onClick={() => openRnd({ view: "designer-kpi" })}>
                Buka KPI Desainer <ArrowRight size={13} />
              </button>
            )}
          </div>
          <div className="section-body">
            <p className="mb-2 text-[11px] leading-relaxed text-[#6B6B73]"
              data-testid="rnd-reports-designer-note">
              Penilaian kinerja desainer kini punya menunya sendiri (<b>Desainer › KPI
              Desainer</b>) dengan ketepatan waktu, pengulangan kerja, nilai komposit,
              filter periode, dan papan eskalasi SLA. Di sini hanya 3 teratas menurut nilai
              komposit — hanya desainer yang menyetor ronde sample atau versi desain dalam
              30 hari terakhir.
            </p>
            {kpiDenied ? (
              <p className="rounded-lg border border-[#F5E0C3] bg-[#FDF6EC] px-3 py-3 text-[11.5px] text-[#8A4B08]"
                data-testid="rnd-perf-denied">
                Anda tidak punya akses ke data KPI Desainer, jadi ringkasan desainer tidak ditampilkan.
                Minta Manajer/Admin bila Anda perlu melihatnya.
              </p>
            ) : perf.length === 0 ? (
              <p className="py-8 text-center text-[11.5px] text-[#6B6B73]"
                data-testid="rnd-perf-empty">
                Belum ada ronde atau versi desain yang dinilai dalam 30 hari terakhir. Angka
                terbentuk sendiri begitu desainer menyetor hasil — tidak diisi manual.
              </p>
            ) : (
              <div className="divide-y divide-[#F4F5F7]">
                {perf.map((p) => {
                  const g = gradeMeta(p.grade_letter);
                  return (
                    <div key={p.designer} data-testid={`rnd-perf-row-${p.designer}`}
                      className="flex flex-wrap items-center gap-x-2 gap-y-0.5 py-1.5 text-[11.5px]">
                      <span className="w-5 text-[10.5px] font-bold text-[#8E8E93]">
                        #{p.rank}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-semibold">
                        {actorLabel(p.designer)}
                      </span>
                      <span className="tabular-nums text-[#6B6B73]" data-testid={`rnd-perf-basis-${p.designer}`}>
                        {Number(p.rounds || 0)} ronde
                        {Number(p.design_versions || 0) > 0 ? ` · ${p.design_versions} versi desain` : ""}
                      </span>
                      {Number(p.rounds || 0) > 0 && (
                        <span className="tabular-nums font-semibold text-[#1B7F4B]">
                          {num(p.on_time_pct, "%")} tepat
                        </span>
                      )}
                      {p.late_total > 0 && (
                        <span className="tabular-nums font-semibold text-[#C0392B]">
                          {p.late_total} telat
                        </span>
                      )}
                      <span className={`status-pill ${g.cls}`}>
                        {g.label} · {num(p.grade_score)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Papan lifecycle produk */}
        <div className="section-card">
          <div className="section-head">
            <h2>Tahap Produk (boleh dijual atau belum)</h2>
          </div>
          <div className="section-body space-y-2">
            <p className="text-[11px] text-[#6B6B73]" data-testid="rnd-board-enforcement">
              Ketegasan sekarang:{" "}
              <b>{board.enforcement === "block" ? "tolak pesanan"
                : board.enforcement === "warn" ? "beri peringatan" : "abaikan"}</b>
              {" "}bila produk yang belum sah dipesan. Total produk: <b>{board.total ?? 0}</b>.
            </p>
            <div className="grid grid-cols-2 gap-1.5 md:grid-cols-3" data-testid="rnd-board-counts">
              {Object.keys(lifeCounts).length === 0 && (
                <p className="text-[11.5px] text-[#6B6B73]">Belum ada data produk.</p>
              )}
              {Object.entries(lifeCounts).map(([k, v]) => {
                const m = lifecycleMeta(k);
                return (
                  <div key={k} data-testid={`rnd-board-count-${k}`}
                    className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2">
                    <p className="text-[10.5px] font-bold uppercase" style={{ color: m.tone }}>
                      {m.label}
                    </p>
                    <p className="text-[14px] font-bold tabular-nums leading-tight">{v}</p>
                  </div>
                );
              })}
            </div>
            {notOrderable.length > 0 && (
              <div className="rounded-lg border border-[#FFE0B2] bg-[#FFFAF2] p-2"
                data-testid="rnd-board-not-orderable">
                <p className="mb-1 flex items-center gap-1 text-[10.5px] font-bold text-[#8C4A00]">
                  <AlertTriangle size={11} /> {notOrderable.length} produk BELUM boleh dijual
                </p>
                <div className="max-h-[180px] space-y-0.5 overflow-y-auto">
                  {notOrderable.map((p) => (
                    <p key={p.id} className="text-[11px] text-[#3C3C43]"
                      data-testid={`rnd-board-blocked-${p.id}`}>
                      <b>{p.sku}</b> {p.name}
                      <span className="text-[#8C4A00]">
                        {" · "}{lifecycleMeta(p.lifecycle).label}
                      </span>
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Papan SLA round */}
      <div className="section-card mt-3">
        <div className="section-head"><h2>Papan SLA Ronde (yang masih berjalan)</h2></div>
        {/* Audit UI 24 Okt (md HP) — tabel grid dulu bertumpuk di 390px ("JUDRONDE"); kini tabel standar yang
            digeser horizontal dengan kepala satu baris. */}
        <div className="section-body">
          {slaRows.length === 0 ? (
            <p className="py-8 text-center text-[11.5px] text-[#6B6B73]" data-testid="rnd-sla-empty">
              Tidak ada ronde yang sedang berjalan. Semua permintaan sudah dinilai atau diputus.
            </p>
          ) : (
            <div className="table-container max-h-[360px] overflow-y-auto">
              <table className="data-table" style={{ minWidth: 760 }}>
                <thead>
                  <tr className="whitespace-nowrap">
                    <th>No. Permintaan</th><th>Judul</th><th>Supplier</th><th>Ronde</th><th>Tenggat</th><th>Keadaan</th>
                  </tr>
                </thead>
                <tbody>
                  {slaRows.map((r) => (
                    <tr key={r.key} data-testid={`rnd-sla-row-${r.key}`}>
                      <td className="whitespace-nowrap font-bold text-[#0058CC]">{r.number}</td>
                      <td>
                        {r.title}
                        <span className="text-[#8E8E93]">
                          {" · "}{typeLabel(r.type, types)}
                        </span>
                      </td>
                      <td>{r.supplier}</td>
                      <td className="whitespace-nowrap tabular-nums">ronde {r.round_no}</td>
                      <td className={`whitespace-nowrap tabular-nums ${r.overdue ? "font-bold text-[#C0392B]" : ""}`}>
                        {r.due}
                      </td>
                      <td className={r.overdue ? "font-semibold text-[#C0392B]" : "text-[#6B6B73]"}>
                        {r.state}{r.overdue ? " · TERLAMBAT" : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Tenggat sudah lewat hari ini? (dipakai sebagai penanda terlambat di papan SLA). */
function isPast(due) {
  if (!due) return false;
  try { return new Date(`${String(due).slice(0, 10)}T23:59:59`) < new Date(); }
  catch { return false; }
}

function Kpi({ label, value, tone = "#1C1C1E" }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2">
      <p className="text-[10.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="text-[13px] font-bold tabular-nums leading-tight" style={{ color: tone }}>{value}</p>
    </div>
  );
}
