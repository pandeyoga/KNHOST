/**
 * MyApprovalsPanel (PS-20 / D-14) — antrean **matriks persetujuan divisi** yang bisa langsung ditindak.
 *
 * Fase 3 · P3 (D-06, keputusan pemilik): layar "Persetujuan Saya" (`my-approvals`) digabung ke **Pusat
 * Persetujuan** sebagai tab "Matriks divisi" (digerbang `canSeeMatrix` = peran yang dulu membuka `my-approvals`).
 * `MyApprovalsView` tetap ada sebagai pembungkus tipis (rute cadangan alias, P8).
 *
 * Menjawab keputusan pemilik: matriks persetujuan divisi MENGIKAT, dan approver butuh SATU antrean:
 *   • tahap: ACC Desain · ACC Sample · PO Custom (2 tingkat) · Permintaan Pembelian · Klaim selisih makloon.
 *   • Setiap baris jujur: bila tidak boleh diputuskan, alasannya ditulis (peran salah, pemisahan tugas, atau sample
 *     belum punya round ACC) — tombol tidak disembunyikan.
 *   • Jejak persetujuan (siapa memutus apa, termasuk percobaan yang ditolak sistem).
 * ACC Sample sengaja TIDAK diputuskan dari sini (butuh pemenang supplier + harga → layar Permintaan Sample).
 * PO Custom diputus lewat dialog BERSAMA `services/approvalDecisions.js` (D-07) — sama dengan Pesanan Khusus & HP.
 *
 * Props: `currentUser` · `selectedEntity` (bawaan PT header) · `onNavigate(view)` (bawaan `useAppNav().go`)
 *   · `embedded` (di dalam tab inbox: judul "Matriks divisi").
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, Check, RefreshCw, ShieldCheck, X } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import useListSearch from "@/hooks/useListSearch";
import { formatCurrency } from "../../utils/formatters";
import { actorLabel } from "../../utils/actorLabel";
import { can } from "../../config/roles";
import axios, { API } from "../../services/apiClient";
import { useAppNav } from "../../context/AppNavContext";
import { useEntityScope } from "../../context/EntityScopeContext";
import { approveSpecialOrder, rejectSpecialOrder, decisionErrorText } from "../../services/approvalDecisions";
import { apiErr, approvalMatrixLog, myApprovalQueue } from "./approvalsMatrixApi";
import { STAGE_META, StageCard, ChainPills, EnforcementPills, ApprovalLogSection, fmtDate } from "./myApprovalsParts";
import MyApprovalDecisionModal from "./MyApprovalDecisionModal";

/** Baris PO Custom matriks → bentuk pesanan yang dipakai dialog bersama. */
const asOrder = (it) => ({ id: it.id, number: it.number, customer_name: it.customer_name,
  total_amount: it.amount, custom_item: { description: it.title } });

export default function MyApprovalsPanel({ currentUser, selectedEntity: entityProp, onNavigate, embedded = false }) {
  const nav = useAppNav();
  const scope = useEntityScope();
  const selectedEntity = entityProp ?? scope.selectedEntity;
  const openView = (view) => { if (!view) return; if (onNavigate) onNavigate(view); else nav.go(view); };
  const [data, setData] = useState(null);
  const [logRows, setLogRows] = useState([]);
  const [onlyViolations, setOnlyViolations] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stage, setStage] = useState("");
  const [msg, setMsg] = useState(null);
  const [modal, setModal] = useState(null);   // {item, action:'approve'|'reject'}
  const [busyId, setBusyId] = useState("");

  const params = useMemo(() => {
    const p = {};
    if (selectedEntity && selectedEntity !== "all") p.entity_id = selectedEntity;
    return p;
  }, [selectedEntity]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [q, lg] = await Promise.all([
        myApprovalQueue(params),
        approvalMatrixLog({ ...params, limit: 40, only_violations: onlyViolations }),
      ]);
      setData(q || null);
      setLogRows((lg && lg.items) || []);
      setError("");
    } catch (e) {
      setError(apiErr(e, "Gagal memuat antrean persetujuan."));
    } finally {
      setLoading(false);
    }
  }, [params, onlyViolations]);

  useEffect(() => { load(); }, [load]);

  // G5-22 — pengaju dulu tampil sebagai email mentah ("admin@kainnusantara.id"); kini nama (email di tooltip).
  const [userNames, setUserNames] = useState({});
  useEffect(() => {
    if (!can(currentUser?.permissions, "user", "view")) return;
    axios.get(`${API}/users`).then((r) => {
      const m = {};
      (Array.isArray(r.data) ? r.data : r.data?.items || []).forEach((u) => { if (u.email) m[String(u.email).toLowerCase()] = u.name; });
      setUserNames(m);
    }).catch(() => {});
  }, [currentUser]);
  const personText = (v) => {
    const s = String(v || "");
    if (!s.includes("@")) return actorLabel(s);
    if (currentUser?.email && s.toLowerCase() === String(currentUser.email).toLowerCase()) return currentUser.name || s;
    return userNames[s.toLowerCase()] || s.split("@")[0].replace(/[._-]+/g, " ").replace(/(^|\s)\S/g, (c) => c.toUpperCase());
  };

  const items = (data?.items || []).filter((it) => !stage || it.stage === stage);
  const srch = useListSearch(items, (it) => [it.number, it.title, it.doc_number, it.label, it.summary, it.requester_name, it.stage_label],
    { testId: "my-approvals", placeholder: "Cari nomor / judul / pengaju…" });
  const counts = data?.counts || {};

  async function decide(item, action) {
    setMsg(null);
    if (item.stage !== "po_custom") { setModal({ item, action }); return; }
    // D-07 — PO Custom: dialog bersama (catatan opsional / alasan ≥5 huruf, pesan hasil berantai).
    setBusyId(item.id);
    try {
      const res = await (action === "approve" ? approveSpecialOrder : rejectSpecialOrder)(asOrder(item));
      if (res === null) return;
      setMsg({ ok: true, text: `${item.number} — ${res.message}` });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: decisionErrorText(e) });
    } finally { setBusyId(""); }
  }

  const renderActions = (it, sfx = "") => {
    const isSample = it.stage === "sample_acc";
    return (
      <>
        <div className="flex flex-wrap items-center gap-1.5">
          {!isSample && (
            <>
              <button className="primary-button !h-7 !px-2 !text-[11px]"
                disabled={!it.can_decide || busyId === it.id}
                data-testid={`my-approvals-approve-${sfx}${it.id}`}
                onClick={() => decide(it, "approve")}>
                <Check size={12} /> Setujui
              </button>
              <button className="danger-button !h-7 !px-2 !text-[11px]"
                disabled={!it.can_decide || busyId === it.id}
                data-testid={`my-approvals-reject-${sfx}${it.id}`}
                onClick={() => decide(it, "reject")}>
                <X size={12} /> Tolak
              </button>
            </>
          )}
          <button className="secondary-button !h-7 !px-2 !text-[11px]"
            data-testid={`my-approvals-open-${sfx}${it.id}`}
            onClick={() => openView(it.view)}>
            Buka <ArrowRight size={12} />
          </button>
        </div>
        {isSample && (
          <p className="mt-1 max-w-[240px] text-[11px] text-[#8E8E93]">
            Keputusan sample memilih pemenang + harga — dilakukan di layar Permintaan Sample.
          </p>
        )}
        {!it.can_decide && (it.block_reasons || []).length > 0 && (
          <p className="mt-1 max-w-[260px] text-[11px] font-medium text-[#C0392B]"
            data-testid={`my-approvals-blocked-${sfx}${it.id}`}>
            <AlertTriangle size={10} className="mr-1 inline" />
            {it.block_reasons[0]}
          </p>
        )}
      </>
    );
  };

  return (
    <div className="grid gap-3" data-testid="my-approvals-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")}
        testId="my-approvals-error" />

      {/* ── Kepala + status penegakan ──────────────────────────────── */}
      <section className="section-card">
        <div className="section-head">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-[#1B7F4B]" />
            <h2 data-testid="my-approvals-title">{embedded ? "Matriks divisi" : "Persetujuan Saya"}</h2>
          </div>
          <button className="secondary-button shrink-0 whitespace-nowrap" onClick={load} data-testid="my-approvals-refresh">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat ulang
          </button>
        </div>
        <div className="section-body">
          <p className="text-[11.5px] text-[#6B6B73]">
            Dokumen yang menunggu keputusan Anda menurut <strong>matriks persetujuan
            divisi</strong> — ACC desain, ACC sample, PO custom, permintaan pembelian, dan klaim
            selisih makloon. Keputusan tercatat di jejak persetujuan.
          </p>
          <EnforcementPills cfg={data?.config || {}} actorRole={data?.actor?.role_label || currentUser?.role} />
          {msg && (
            <p data-testid="my-approvals-msg"
              className={`mt-2 rounded-md px-2.5 py-1.5 text-[11.5px] font-medium ${
                msg.ok ? "bg-[#E9F7EF] text-[#1B7F4B]" : "bg-[#FDECEA] text-[#C0392B]"}`}>
              {msg.text}
            </p>
          )}
        </div>
      </section>

      {/* ── Kartu per tahap (saringan) ─────────────────────────────── */}
      <section className="section-card">
        <div className="section-head">
          <h2>Antrean per Tahap</h2>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-[#6B6B73]" data-testid="my-approvals-summary">
              {data?.total || 0} menunggu · {data?.actionable || 0} bisa Anda putuskan
            </span>
            {stage && (
              <button className="secondary-button" data-testid="my-approvals-clear-filter"
                onClick={() => setStage("")}>Tampilkan semua</button>
            )}
          </div>
        </div>
        <div className="section-body">
          <div className="grid gap-2.5 grid-cols-2 lg:grid-cols-5">
            {(data?.stages || []).map((s) => (
              <StageCard key={s.stage} stage={s.stage} count={counts[s.stage] || 0}
                active={stage === s.stage}
                onClick={() => setStage(stage === s.stage ? "" : s.stage)} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Daftar antrean ─────────────────────────────────────── */}
      <section className="section-card">
        <div className="section-head"><h2>Dokumen Menunggu ({items.length})</h2></div>
        <div className="section-body">
          {srch.toolbar}
          {loading && !data ? (
            <p className="py-8 text-center text-[12px] text-[#6B6B73]">Memuat antrean…</p>
          ) : srch.shown.length === 0 ? (
            <p className="py-8 text-center text-[12px] text-[#9A9BA3]"
              data-testid="my-approvals-empty">
              Tidak ada dokumen yang menunggu keputusan pada saringan ini. 🎉
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[12px] sm:min-w-[980px]"
                data-testid="my-approvals-list">
                <thead>
                  <tr className="text-[10px] uppercase text-[#8E8E93]">
                    <th className="py-1.5 pr-3 font-bold">Tahap</th>
                    <th className="py-1.5 pr-3 font-bold">Dokumen</th>
                    <th className="py-1.5 pr-3 font-bold">Pengaju</th>
                    <th className="py-1.5 pr-3 text-right font-bold">Nilai</th>
                    <th className="py-1.5 pr-3 font-bold">Menunggu</th>
                    <th className="py-1.5 pr-3 font-bold">Tingkat</th>
                    <th className="hidden py-1.5 font-bold sm:table-cell">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#F4F5F7]">
                  {srch.pageRows.map((it) => {
                    const meta = STAGE_META[it.stage] || {};
                    const Icon = meta.icon || ShieldCheck;
                    return (
                      <tr key={`${it.stage}-${it.id}-${it.step_seq || 0}`} data-testid={`my-approvals-row-${it.id}`}
                        className="align-top">
                        <td className="py-2 pr-3">
                          <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-bold"
                            style={{ background: meta.bg, color: meta.fg }}>
                            <Icon size={11} /> {meta.label || it.stage}
                          </span>
                        </td>
                        <td className="py-2 pr-3">
                          <div className="font-semibold text-[#1C1C1E]">{it.number}{it.step_seq ? <span className="ml-1 text-[10px] font-normal text-[#8E8E93]">langkah {it.step_seq}</span> : null}</div>
                          <div className="text-[11px] text-[#6B6B73]">{it.title}</div>
                          {it.customer_name && (
                            <div className="text-[11px] text-[#8E8E93]">{it.customer_name}</div>
                          )}
                          {/* Audit UI 24 Okt (001, HP) — di HP aksi tampil di bawah dokumen; kolom Aksi hanya ≥ sm. */}
                          <div className="mt-1.5 sm:hidden" data-testid={`my-approvals-actions-m-${it.id}`}>{renderActions(it, "m-")}</div>
                        </td>
                        <td className="py-2 pr-3 text-[11.5px] text-[#4A4B52]">
                          <span title={String(it.requester || "").includes("@") ? it.requester : undefined}>{personText(it.requester)}</span>
                          <div className="text-[11px] text-[#9A9BA3]">{fmtDate(it.created_at)}</div>
                        </td>
                        <td className="py-2 pr-3 text-right font-semibold text-[#1C1C1E]">
                          {it.amount ? formatCurrency(it.amount) : "—"}
                        </td>
                        <td className="py-2 pr-3">
                          <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-bold ${
                            it.days_waiting >= 3 ? "bg-[#FDECEA] text-[#C0392B]"
                              : "bg-[#EEF1F5] text-[#4A4B52]"}`}>
                            {it.days_waiting > 0 ? `${it.days_waiting} hari` : "< 1 hari"}
                          </span>
                        </td>
                        <td className="py-2 pr-3">
                          <ChainPills chain={it.approval_chain} level={it.level}
                            total={it.levels_total} label={it.level_label} />
                          <div className="mt-1 text-[10px] text-[#8E8E93]">
                            perlu: {it.required_roles_label}
                          </div>
                        </td>
                        <td className="hidden py-2 sm:table-cell">{renderActions(it)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <ApprovalLogSection rows={logRows} onlyViolations={onlyViolations} onToggleViolations={setOnlyViolations} />

      <MyApprovalDecisionModal modal={modal} requesterText={personText}
        onClose={() => setModal(null)}
        onDone={async (text) => { setModal(null); setMsg({ ok: true, text }); await load(); }} />
    </div>
  );
}
