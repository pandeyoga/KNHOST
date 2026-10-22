/** QC retur lewat SPK (permintaan pemilik 23 Okt) — layar retur hanya MENUGASKAN & MELIHAT SPK `return_customer`;
 *  pemeriksaan per roll diisi petugas QC di menu Kualitas › SPK Inspeksi dengan form 4-point yang sama dengan QC
 *  penerimaan. SPK lahir otomatis saat retur di-ACC (satu baris per roll yang disetujui); retur lama tanpa SPK bisa
 *  diterbitkan di sini. Hasil per roll (grade, poin, kondisi, qty aktual) menjadi hasil retur saat SPK ditutup. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ClipboardCheck, ExternalLink, Loader2, UserCheck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { Panel } from "../../components/DetailParts";
import KNSelect from "../../components/KNSelect";
import { can } from "../../config/roles";
import { formatQty } from "../../utils/formatters";
import { apiText, assignInspection, getInspection, inspectionsMeta, INS_STATUS_LABEL } from "../inspections/inspectionsApi";

const COND = { ok: "Baik", minor: "Cacat ringan", damaged: "Rusak" };

export default function ReturnSpkPanel({ ret, currentUser, onOpenDocument, onChanged }) {
  const perms = currentUser?.permissions;
  const canView = can(perms, "inspection", "view");
  const canAssign = can(perms, "inspection", "assign");
  const canCreate = can(perms, "inspection", "create") || can(perms, "sales_return", "approve");
  const [spk, setSpk] = useState(null);
  const [officers, setOfficers] = useState([]);
  const [officer, setOfficer] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    if (!ret.inspection_id || !canView) { setSpk(null); return; }
    try { setSpk(await getInspection(ret.inspection_id)); } catch (e) { setErr(apiText(e, "SPK tidak bisa dimuat.")); }
  }, [ret.inspection_id, canView]);
  useEffect(() => { load(); }, [load, ret.updated_at]);
  useEffect(() => {
    if (!canAssign || !ret.inspection_id) return;
    inspectionsMeta(ret.entity_id || "").then((m) => setOfficers(m?.officers || [])).catch(() => setOfficers([]));
  }, [canAssign, ret.inspection_id, ret.entity_id]);

  // Baris per roll: hidup dari SPK (bila boleh dibaca), selesai dari hasil retur.
  const rows = useMemo(() => {
    const fromRet = (ret.items || []).flatMap((it) => Object.entries(it.inspection?.roll_results || {}).map(([rid, r]) => ({
      key: rid, roll: r.roll_no || (it.roll_nos || {})[rid] || rid, claim: (it.roll_qtys || {})[rid], unit: it.unit,
      actual: r.actual_qty, points: r.points, grade: r.grade, condition: r.condition, by: r.inspected_by })));
    if (!spk) return fromRet;
    return (spk.lines || []).map((ln) => ({
      key: ln.id, roll: ln.roll_no || ln.sku, claim: ln.quantity, unit: ln.unit, actual: ln.actual_qty,
      points: ln.points_snapshot, grade: ln.grade_after, condition: ln.condition, by: ln.qc_by || ln.inspected_by }));
  }, [spk, ret.items]);
  const done = rows.filter((r) => r.grade).length;
  const locs = ret.roll_locations || {};
  const claimed = (ret.items || []).flatMap((it) => it.roll_ids || []);
  const received = claimed.filter((rid) => (locs[rid] || {}).stage && locs[rid].stage !== "in_transit").length;

  if (!["approved", "inspecting", "inspected"].includes(ret.status) && !ret.inspection_id) return null;

  async function issue() {
    setBusy(true); setErr("");
    try { await axios.post(`${API}/sales-returns/${ret.id}/spk`); onChanged?.(); }
    catch (e) { setErr(apiText(e, "Gagal menerbitkan SPK QC.")); }
    finally { setBusy(false); }
  }
  async function assign() {
    if (!officer) { setErr("Pilih petugas QC dulu."); return; }
    setBusy(true); setErr("");
    try { await assignInspection(ret.inspection_id, officer); setOfficer(""); await load(); onChanged?.(); }
    catch (e) { setErr(apiText(e, "Gagal menugaskan petugas.")); }
    finally { setBusy(false); }
  }
  const openSpk = () => onOpenDocument?.({ view: "inspections", nav_id: "quality-hub", focus_type: "inspection",
    focus_id: ret.inspection_id, number: ret.inspection_number || spk?.number || "" });
  const status = spk?.status;

  return (
    <Panel icon={ClipboardCheck} title="QC retur · SPK inspeksi per roll" testId="return-spk-panel">
      {!ret.inspection_id ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[12px] text-[#6B6B73]">Belum ada SPK QC untuk retur ini (retur disetujui sebelum SPK otomatis berlaku).</p>
          {canCreate && (
            <button type="button" className="primary-button" onClick={issue} disabled={busy} data-testid="return-spk-issue">
              {busy ? <Loader2 size={13} className="spin" /> : <ClipboardCheck size={13} />} Terbitkan SPK QC
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
              <span className="font-mono font-semibold text-[#1C1C1E]" data-testid="return-spk-number">{ret.inspection_number || spk?.number}</span>
              {status && <span className="rounded-full bg-[#EFF4FF] px-2 py-0.5 text-[10.5px] font-semibold text-[#0058CC]" data-testid="return-spk-status">{INS_STATUS_LABEL[status] || status}</span>}
              <span className="text-[#6B6B73]">Petugas: <b className="text-[#1C1C1E]">{spk?.assigned_name || (spk ? "belum ditugaskan" : "—")}</b></span>
              <span className="tabular-nums text-[#6B6B73]" data-testid="return-spk-progress">{done}/{rows.length || claimed.length} roll diperiksa</span>
            </div>
            {onOpenDocument && canView && (
              <button type="button" className="secondary-button" onClick={openSpk} data-testid="return-spk-open">
                <ExternalLink size={13} /> Buka SPK
              </button>
            )}
          </div>
          {canAssign && ["draft", "assigned"].includes(status) && (
            <div className="flex flex-wrap items-center gap-2" data-testid="return-spk-assign">
              <div className="min-w-[240px] flex-1">
                <KNSelect className="form-select" value={officer} onValueChange={setOfficer} placeholder="Pilih petugas QC…"
                  data-testid="return-spk-officer" options={officers} />
              </div>
              <button type="button" className="primary-button" onClick={assign} disabled={busy} data-testid="return-spk-assign-btn">
                {busy ? <Loader2 size={13} className="spin" /> : <UserCheck size={13} />} {status === "assigned" ? "Ganti petugas" : "Tugaskan"}
              </button>
            </div>
          )}
          {claimed.length > 0 && ret.status !== "inspected" && (
            <p className="text-[11.5px] text-[#6B6B73]" data-testid="return-spk-gate">
              Roll diterima gudang: <b className="tabular-nums text-[#1C1C1E]">{received}/{claimed.length}</b> — QC per roll bisa diisi
              begitu roll itu discan terima; SPK ditutup sesudah semua roll diperiksa.
            </p>
          )}
          {rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="data-table" style={{ minWidth: 640 }} data-testid="return-spk-rows">
                <thead><tr><th>Roll</th><th className="text-right">Qty klaim</th><th className="text-right">Qty aktual</th>
                  <th className="text-right">Poin</th><th>Grade</th><th>Kondisi</th><th>Petugas</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.key}>
                      <td className="font-mono text-[11.5px] font-semibold">{r.roll}</td>
                      <td className="text-right tabular-nums">{r.claim != null ? `${formatQty(r.claim)} ${r.unit || ""}` : "—"}</td>
                      <td className="text-right tabular-nums">{r.actual != null ? `${formatQty(r.actual)} ${r.unit || ""}` : "—"}</td>
                      <td className="text-right tabular-nums">{r.points != null ? formatQty(r.points) : "—"}</td>
                      <td className="font-semibold">{r.grade || <span className="font-normal text-[#9A9BA3]">belum</span>}</td>
                      <td>{r.condition ? COND[r.condition] || r.condition : "—"}</td>
                      <td className="text-[11px] text-[#6B6B73]">{r.by || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {err && <p className="mt-2 text-[11.5px] font-semibold text-[#A8221A]" data-testid="return-spk-error">{err}</p>}
    </Panel>
  );
}
