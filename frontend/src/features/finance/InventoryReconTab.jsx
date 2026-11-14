/**
 * InventoryReconTab (Gelombang 1 F-3) — rekonsiliasi buku besar persediaan vs nilai
 * fisik roll (subledger) per PT + posting saldo awal / true-up.
 * Diekstrak dari GeneralLedger.jsx (jaga batas ukuran file). Sumber: /api/gl/*.
 *
 * PK-29 (IV-05, IV-09, K-06) — status "sinkron" dari server (`reconciled` per baris dan tingkat atas = SEMUA PT
 * sinkron; banner menyebut PT yang belum sinkron dan total selisih mutlak); kolom Akun = akun persediaan yang dibaca
 * per PT (hasil pemetaan); lencana Sinkron / Tidak sinkron (ikon + teks + warna). Posting Saldo Awal hanya untuk PT
 * aktif yang tidak sinkron dan boleh di-true-up (`trueup_allowed`); bila tidak boleh, alasannya tertulis di samping
 * tombol. Dialog menyebut satu PT dan nominalnya.
 */
import { apiErrorText } from "../../utils/apiError";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { askReason } from "@/services/confirmService";
import { originLabel, sourceLabel, ROLL_STATUS_LABELS } from "./glSourceLabels";
import { docStatusLabel } from "../../utils/docStatus";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import ZeroCostRollsSection from "./ZeroCostRollsSection";
import { isAllEntities } from "../../components/EntityGatedButton";

export const TEKS_PILIH_PT = "Pilih satu PT untuk memposting saldo awal.";
export const TEKS_SUDAH_SINKRON = "Persediaan PT ini sudah sinkron — tidak ada yang perlu disamakan.";
export const TEKS_PT_TIDAK_ADA = "PT aktif tidak ada di daftar rekonsiliasi.";

/** Tombol Posting Saldo Awal: aktif hanya bila PT aktif dipilih, barisnya tidak sinkron, dan `trueup_allowed`. */
export function trueupButtonState(selectedEntity, rows = []) {
  if (!selectedEntity || isAllEntities(selectedEntity)) return { enabled: false, reason: TEKS_PILIH_PT };
  const row = rows.find((r) => r.entity_id === selectedEntity);
  if (!row) return { enabled: false, reason: TEKS_PT_TIDAK_ADA };
  if (row.reconciled) return { enabled: false, reason: TEKS_SUDAH_SINKRON };
  if (!row.trueup_allowed) return { enabled: false, reason: row.trueup_blocked_reason || "" };
  return { enabled: true, reason: "" };
}

/** Teks banner dari angka server (`reconciled`, `rows_out_of_sync`, `total_abs_difference`). */
export function bannerText(data) {
  const rows = data?.rows || [];
  const tol = data?.rounding_tolerance ?? 1;
  if (data?.reconciled === false) {
    const nama = rows.filter((r) => r.reconciled === false).map((r) => r.entity_name).join(", ");
    return `${data.rows_out_of_sync} PT belum sinkron: ${nama}. Total selisih mutlak ${formatCurrency(data.total_abs_difference)}.`;
  }
  if ((data?.total_abs_difference || 0) > 0) {
    return `GL Persediaan sinkron dengan subledger roll — sisa ${formatCurrency(data.total_abs_difference)} hanya `
      + `pembulatan sen (di bawah ambang ${formatCurrency(tol)}).`;
  }
  return "GL Persediaan sinkron dengan subledger roll.";
}

/** `02` §3.4 N5 — dialog true-up menyebut satu PT dan nominalnya. */
export function trueupConfirmText(row) {
  return `GL Persediaan ${row.entity_name} akan disamakan dengan nilai fisik roll (${formatCurrency(row.difference)}), `
    + "dengan lawan akun Ekuitas Saldo Awal. Jurnalnya nyata dan masuk buku besar.";
}

/** Lencana per baris — ikon + teks + warna (`status-pill`). */
function SyncStatus({ row }) {
  return row.reconciled ? (
    <span className="status-pill pill-success inline-flex items-center gap-1 whitespace-nowrap" data-testid={`recon-sync-${row.entity_id}`}>
      <CheckCircle2 size={12} aria-hidden="true" />Sinkron
    </span>
  ) : (
    <span className="status-pill pill-warning inline-flex items-center gap-1 whitespace-nowrap" data-testid={`recon-sync-${row.entity_id}`}>
      <AlertTriangle size={12} aria-hidden="true" />Tidak sinkron
    </span>
  );
}

export default function InventoryReconTab({ refreshKey, onError, onNotice, onChanged,
                                           selectedEntity = "all", entities = [] }) {
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  // PK-12 — posting saldo awal / true-up memakai kunci idempotensi (kirim ulang tidak memposting dua kali).
  const openingIntent = useIntentKey("invob");
  const [explain, setExplain] = useState(null);
  const [explaining, setExplaining] = useState("");
  // "Tuduhan bisa diklik" (2026-06) — bukti dokumen dibuka DI LAYAR INI. Sebelum ini
  // dugaan penyebab hanya kalimat: ia menyebut "Roll RTN-00001 Rp 900.000" lalu
  // berhenti, dan orangnya masih harus mencari roll itu sendiri di layar lain.
  const [evidence, setEvidence] = useState(null);   // {key, kind, loading, error, data}

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/gl/inventory-reconciliation`);
      setData(res.data);
      // Riwayat true-up: yang menjelaskan SIAPA menyamakan apa & atas dasar apa.
      // Tanpa ini layar hanya bisa menjawab "sekarang selisih berapa" — pertanyaan
      // saat tutup buku justru "selisih tempo hari itu diapakan, dan kenapa".
      // DIFILTER PER BADAN USAHA (2026-06): riwayat dua buku yang tercampur di satu
      // daftar membuat orang mengira buku ini pernah di-true-up padahal itu buku lain.
      const params = { source: "inventory_opening" };
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const hist = await axios.get(`${API}/gl/journal`, { params });
      setHistory((hist.data || []).slice(0, 5));
    } catch (e) {
      onError(apiErrorText(e, "Gagal memuat rekonsiliasi persediaan."));
    } finally {
      setLoading(false);
    }
  }, [onError, selectedEntity]);

  const entityName = (id) => (entities.find((e) => e.id === id) || {}).name || id;

  /** Penjelas selisih — "di mana", bukan cuma "berapa". Tidak menerbitkan jurnal. */
  const loadExplain = async (entityId) => {
    if (explain?.entity_id === entityId) { setExplain(null); return; }
    setExplaining(entityId);
    try {
      const res = await axios.get(`${API}/gl/inventory-drift-explain`,
        { params: { entity_id: entityId } });
      setExplain(res.data);
    } catch (e) {
      onError(apiErrorText(e, "Gagal membaca penjelasan selisih."));
    } finally {
      setExplaining("");
    }
  };

  useEffect(() => { load(); }, [load, refreshKey]);

  /** Buka BUKTI satu tuduhan: roll, jurnal, atau buku besar akun 1-1300. */
  const openEvidence = async (suspect, idx) => {
    const ref = suspect?.ref || {};
    const key = `${suspect.kind}-${idx}`;
    if (!ref.kind) return;
    if (evidence?.key === key) { setEvidence(null); return; }
    setEvidence({ key, kind: ref.kind, loading: true, error: "", data: null, ref });
    try {
      let data = null;
      if (ref.kind === "roll") {
        const res = await axios.get(`${API}/inventory/rolls`,
          { params: { page: 1, page_size: 1, q: ref.q || ref.number } });
        data = (res.data?.items || [])[0] || null;
        // Riwayat NILAI roll ikut ditempelkan sebagai bukti (2026-06): tuduhan
        // "roll ini bernilai Rp 900.000" jauh lebih berguna bila disertai siapa yang
        // menaikkan nilainya dan atas dasar apa.
        if (data?.id) {
          // T1 DIBAYAR (2026-06c): galatnya dulu DITELAN, jadi blok riwayat tidak
          // pernah muncul tanpa satu pun pesan — kegagalan tampil sebagai kabar
          // baik (kelas regresi B5). Sekarang sebabnya ikut dilaporkan.
          try {
            const h = await axios.get(`${API}/inventory/rolls/${data.id}/cost-history`);
            data = { ...data, cost_history: (h.data?.history || []).slice(0, 3),
              cost_history_error: "" };
          } catch (e) {
            data = { ...data, cost_history: [],
              cost_history_error: apiErrorText(e, "Riwayat nilai (HPP) tidak bisa dibaca dengan izin Anda.") };
          }
        }
      } else if (ref.kind === "journal" && ref.id) {
        data = (await axios.get(`${API}/gl/journal/${ref.id}`)).data;
      } else if (ref.kind === "account") {
        const params = {};
        if (explain?.entity_id) params.entity_id = explain.entity_id;
        data = (await axios.get(`${API}/gl/accounts/${ref.id}/ledger`, { params })).data;
      }
      setEvidence({ key, kind: ref.kind, loading: false, error: data ? "" : "Dokumennya tidak bisa dibuka dari layar ini.", data, ref });
    } catch (e) {
      setEvidence({ key, kind: ref.kind, loading: false, data: null, ref,
        error: apiErrorText(e, "Gagal membuka dokumen buktinya.") });
    }
  };

  const postOpening = async (includeRounding = false) => {
    // Berdampak UANG + STOK: menerbitkan jurnal true-up terhadap ekuitas saldo awal — HANYA untuk PT aktif (PK-29).
    // `02` §3.4 N5 — dialog menyebut SATU PT dan nominalnya.
    if (!activeRow) return;
    const nama = activeRow.entity_name;
    const reason = await askReason({
      title: includeRounding
        ? `Rapikan sisa pembulatan ${nama}?`
        : `Posting saldo awal persediaan ${nama}?`,
      message: includeRounding
        ? `Sisa pembulatan ${formatCurrency(activeRow.difference)} pada ${nama} akan dinolkan dengan jurnal kecil `
          + "terhadap Ekuitas Saldo Awal. Jurnalnya nyata dan masuk buku besar."
        : trueupConfirmText(activeRow),
      reasonLabel: "Alasan / dasar penyesuaian",
      reasonPlaceholder: includeRounding
        ? "Contoh: merapikan sisa pembulatan sen warisan jurnal lama"
        : "Contoh: impor stok awal gudang utama 1 November",
      confirmLabel: includeRounding ? "Rapikan Sisa" : "Posting True-Up",
      testId: "recon-post-confirm",
    });
    if (reason === null) return;
    setPosting(true);
    try {
      const params = includeRounding ? { reason, include_rounding: true } : { reason };
      const res = await openingIntent.send({ aksi: "inventory-opening-balance", pt: activeRow.entity_id, ...params },
        (k) => moneyPost(`${API}/gl/inventory-opening-balance`, null, k, { params }));
      const n = res.data?.count || 0;
      onNotice(n > 0 ? `Saldo awal diposting: ${n} jurnal (${(res.data.posted || []).map((p) => p.journal_number).join(", ")}).` : "Tidak ada selisih — GL sudah sinkron dengan subledger.");
      await load();
      onChanged();
    } catch (e) {
      onError(apiErrorText(e, "Gagal posting saldo awal persediaan."));
    } finally {
      setPosting(false);
    }
  };

  // Ambang "sinkron" datang dari SERVER (2026-06c, gap iterasi 256) — satu definisi untuk layar & penjelas selisih.
  const tol = data?.rounding_tolerance ?? 1;
  const rows = data?.rows || [];
  const activeRow = isAllEntities(selectedEntity) ? null : rows.find((r) => r.entity_id === selectedEntity) || null;
  const tombol = trueupButtonState(selectedEntity, rows);
  const bisaRapikan = Boolean(activeRow && activeRow.reconciled && activeRow.rounding_only && activeRow.trueup_allowed);
  if (loading) return <p className="text-fs-12 text-kn-text-2 py-6 text-center" data-testid="recon-loading">Memuat rekonsiliasi…</p>;

  return (
    <div data-testid="inventory-recon-tab">
      <div role="status" data-testid="recon-status-banner"
        className={`mb-2 flex items-start gap-2 rounded-md border px-3 py-2 text-fs-13 ${data?.reconciled === false
          ? "border-kn-divider bg-kn-warning-soft text-kn-warning-text" : "border-kn-divider bg-kn-success-soft text-kn-success-text"}`}>
        {data?.reconciled === false ? <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
          : <CheckCircle2 size={14} className="mt-0.5 shrink-0" aria-hidden="true" />}
        <span>{bannerText(data)}</span>
      </div>
      {/* Bilah aksi sendiri (bukan di dalam banner): tombol + alasan mati yang TERTULIS di sampingnya. */}
      <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="recon-actions">
        <button type="button" data-testid="recon-post-opening" className="primary-button btn-sm whitespace-nowrap"
          onClick={() => postOpening(false)} disabled={posting || !tombol.enabled}
          aria-describedby={tombol.enabled ? undefined : "recon-post-reason"}>
          {posting ? "Memposting…" : "Posting Saldo Awal"}
        </button>
        {bisaRapikan && (
          <button type="button" data-testid="recon-fix-rounding" className="secondary-button btn-sm whitespace-nowrap"
            onClick={() => postOpening(true)} disabled={posting}>
            Rapikan sisa pembulatan
          </button>
        )}
        {!tombol.enabled && (
          <span id="recon-post-reason" data-testid="recon-post-reason"
            className="inline-flex min-w-0 items-start gap-1 text-fs-12 text-kn-text-2">
            <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>{tombol.reason}</span>
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="data-table head-wrap w-full" data-testid="recon-table">
          <thead>
            <tr>
              <th>PT</th>
              <th>Akun</th>
              <th className="text-right">Nilai fisik (roll × HPP)</th>
              <th className="text-right">Saldo buku besar</th>
              <th className="text-right">Selisih</th>
              <th>Status</th>
              <th className="col-sticky-end text-right">Penjelasan</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.entity_id} data-testid={`recon-row-${r.entity_id}`}>
                <td className="max-w-[220px] break-words font-semibold">{r.entity_name}</td>
                <td data-testid={`recon-accounts-${r.entity_id}`}>
                  {(r.inventory_accounts || []).map((c, i) => (
                    <span key={c} className="whitespace-nowrap font-mono">{c}{i < r.inventory_accounts.length - 1 ? ", " : ""}</span>
                  ))}
                </td>
                <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(r.subledger_value)}</td>
                <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(r.gl_balance)}</td>
                <td className={`whitespace-nowrap text-right tabular-nums font-bold ${r.reconciled ? "text-kn-success-text" : "text-kn-danger-text"}`}
                  data-testid={`recon-diff-${r.entity_id}`}>
                  {formatCurrency(r.difference)}
                  {r.rounding_only ? <span className="ml-1 text-fs-12 font-semibold text-kn-text-2" data-testid={`recon-rounding-${r.entity_id}`}>pembulatan</span> : null}
                </td>
                <td><SyncStatus row={r} /></td>
                <td className="col-sticky-end text-right">
                  {/* G1-46 — tombol penjelas hanya untuk baris yang benar-benar berselisih. */}
                  {r.reconciled && explain?.entity_id !== r.entity_id
                    ? <span className="text-fs-12 text-kn-text-2" data-testid={`recon-explain-none-${r.entity_id}`}>—</span>
                    : <button type="button" className="secondary-button btn-sm whitespace-nowrap"
                      onClick={() => loadExplain(r.entity_id)}
                      disabled={explaining === r.entity_id}
                      data-testid={`recon-explain-${r.entity_id}`}>
                      {explaining === r.entity_id ? "Membaca…"
                        : explain?.entity_id === r.entity_id ? "Tutup" : "Jelaskan selisih"}
                    </button>}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} className="py-6 text-center text-kn-text-2" data-testid="recon-empty">Belum ada PT untuk direkonsiliasi.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {/* PENJELAS SELISIH (lanjutan INV-GL-DRIFT 2026-06) — memecah KEDUA sisi dari
          koleksi aslinya (roll `acquired.via` vs baris jurnal akun 1-1300), supaya
          true-up bukan lagi satu-satunya jawaban atas pertanyaan "kenapa". */}
      {explain && (
        <div className="mt-3 rounded-xl border border-[#E7EAF0] bg-[#FAFBFC] p-3"
          data-testid={`recon-explain-panel-${explain.entity_id}`}>
          <p className="mb-2 text-[12px] font-bold text-[#1C1C1E]">
            {explain.entity_name} — fisik {formatCurrency(explain.subledger_value)} vs GL{" "}
            {formatCurrency(explain.gl_balance)} · selisih{" "}
            <span className={Math.abs(explain.difference) > tol ? "text-[#C0392B]" : "text-[#1B7F4B]"}>
              {formatCurrency(explain.difference)}
            </span>
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <p className="mb-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">
                Nilai fisik menurut ASAL barang
              </p>
              <div className="grid gap-1" data-testid="recon-explain-physical">
                {(explain.physical_by_origin || []).map((o) => (
                  <div key={o.origin} className="flex items-center gap-2 text-[11.5px]"
                    data-testid={`recon-explain-origin-${o.origin}`}>
                    <span className="min-w-0 flex-1 truncate text-[#3C3C43]" title={o.origin}>{o.origin_label || originLabel(o.origin)}</span>
                    <span className="text-[#8E8E93]">{o.rolls} roll</span>
                    <span className="tabular-nums font-semibold">{formatCurrency(o.value)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">
                Mutasi akun persediaan ({(explain.inventory_accounts || []).join(", ")}) menurut SUMBER jurnal
              </p>
              <div className="grid gap-1" data-testid="recon-explain-gl">
                {(explain.gl_by_source || []).map((s) => (
                  <div key={s.source} className="flex items-center gap-2 text-[11.5px]"
                    data-testid={`recon-explain-source-${s.source}`}>
                    <span className="min-w-0 flex-1 truncate text-[#3C3C43]" title={s.source}>{s.source_label || sourceLabel(s.source)}</span>
                    <span className={`tabular-nums font-semibold ${s.net < 0 ? "text-[#C0392B]" : ""}`}>
                      {formatCurrency(s.net)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-3 border-t border-[#EDEFF3] pt-2">
            <p className="mb-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">
              Dugaan penyebab (fakta dari dokumennya, bukan tebakan)
            </p>
            {(explain.suspects || []).length === 0 ? (
              <p className="text-[11.5px] text-[#1B7F4B]" data-testid="recon-explain-suspects-empty">
                Tidak ada kejanggalan yang bisa ditunjuk — kedua sisi cocok per kategori.
              </p>
            ) : (
              <ul className="grid gap-1" data-testid="recon-explain-suspects">
                {(explain.suspects || []).map((s, i) => {
                  const key = `${s.kind}-${i}`;
                  const clickable = Boolean(s.ref?.kind);
                  const open = evidence?.key === key;
                  return (
                    <li key={key} className="text-[11.5px]"
                      data-testid={`recon-explain-suspect-${s.kind}`}>
                      {clickable ? (
                        <button type="button"
                          className="text-left"
                          onClick={() => openEvidence(s, i)}
                          data-testid={`recon-suspect-open-${s.kind}`}
                          title="Buka dokumen yang dituduh">
                          <span className="font-semibold text-[#0058CC] underline decoration-dotted">
                            {s.label}
                          </span>
                          <span className="text-[#6B6B73]"> — {s.hint}</span>
                          <span className="ml-1 text-[10.5px] font-semibold text-[#0058CC]">
                            {open ? "· tutup bukti" : `· buka ${s.ref.number || s.ref.kind} →`}
                          </span>
                        </button>
                      ) : (
                        <>
                          <span className="font-semibold text-[#1C1C1E]">{s.label}</span>
                          <span className="text-[#6B6B73]"> — {s.hint}</span>
                        </>
                      )}
                      {open && (
                        <div className="mt-1 rounded-lg border border-[#DCE6F7] bg-white p-2"
                          data-testid={`recon-suspect-evidence-${s.kind}`}>
                          {evidence.loading ? (
                            <span className="text-[11px] text-[#8E8E93]">Membuka dokumennya…</span>
                          ) : evidence.error ? (
                            <span className="text-[11px] text-[#C0392B]"
                              data-testid="recon-suspect-evidence-error">{evidence.error}</span>
                          ) : evidence.kind === "roll" ? (
                            <div className="grid gap-0.5 text-[11px]">
                              <p className="font-bold text-[#1C1C1E]">
                                Roll {evidence.data.roll_no || evidence.data.id}
                                {evidence.data.lot ? ` · lot ${evidence.data.lot}` : ""}
                              </p>
                              <p className="text-[#3C3C43]">
                                {evidence.data.product_name || evidence.data.sku || "—"} ·{" "}
                                {evidence.data.warehouse_name || "gudang tak tercatat"} ·{" "}
                                sisa {evidence.data.length_remaining} {evidence.data.unit || ""}
                              </p>
                              <p className="text-[#3C3C43]">
                                HPP/unit {formatCurrency(evidence.data.unit_cost)} · nilai{" "}
                                <b>{formatCurrency((evidence.data.length_remaining || 0)
                                  * (evidence.data.unit_cost || evidence.data.base_unit_cost || 0))}</b>
                              </p>
                              <p className="text-[#6B6B73]">
                                Masuk lewat {(evidence.data.acquired || {}).via ? originLabel(evidence.data.acquired.via) : "—"} ·
                                dokumen {(evidence.data.acquired || {}).ref_id || "—"} ·
                                status {docStatusLabel(evidence.data.status)}
                              </p>
                              {evidence.data.cost_history_error ? (
                                <p className="mt-1 border-t border-[#EDEFF3] pt-1 text-[10.5px] font-semibold text-[#C62828]"
                                  data-testid="recon-suspect-cost-history-error">
                                  Riwayat nilai (HPP) tidak bisa dibaca:{" "}
                                  {evidence.data.cost_history_error}
                                </p>
                              ) : null}
                              {(evidence.data.cost_history || []).length > 0 && (
                                <div className="mt-1 border-t border-[#EDEFF3] pt-1"
                                  data-testid="recon-suspect-cost-history">
                                  <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">
                                    Riwayat nilai (HPP)
                                  </p>
                                  {evidence.data.cost_history.map((h, hi) => (
                                    <p key={hi} className="text-[10.5px] text-[#3C3C43]">
                                      {formatCurrency(h.old_unit_cost)} →{" "}
                                      {formatCurrency(h.new_unit_cost)} ·{" "}
                                      {h.reason_label || h.reason} · oleh {h.actor}
                                      {h.ref_number ? ` (${h.ref_number})` : ""}
                                    </p>
                                  ))}
                                </div>
                              )}
                            </div>
                          ) : evidence.kind === "journal" ? (
                            <div className="grid gap-0.5 text-[11px]">
                              <p className="font-bold text-[#1C1C1E]">
                                Jurnal {evidence.data.number} · {formatDate(evidence.data.date)}
                              </p>
                              <p className="text-[#6B6B73]">{evidence.data.description}</p>
                              {(evidence.data.lines || []).map((l, li) => (
                                <p key={li} className="tabular-nums text-[#3C3C43]">
                                  {l.account_code} · D {formatCurrency(l.debit)} / K {formatCurrency(l.credit)}
                                </p>
                              ))}
                            </div>
                          ) : (
                            <div className="grid gap-0.5 text-[11px]">
                              <p className="font-bold text-[#1C1C1E]">
                                Buku Besar {(evidence.data.account || {}).code} — saldo{" "}
                                {formatCurrency(evidence.data.balance)}
                              </p>
                              {(evidence.data.lines || []).slice(0, 5).map((m, mi) => (
                                <p key={mi} className="tabular-nums text-[#3C3C43]">
                                  {formatDate(m.date)} · {m.number || m.source_type || ""} ·
                                  D {formatCurrency(m.debit)} / K {formatCurrency(m.credit)}
                                </p>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
      <p className="mt-2 text-fs-12 text-kn-text-2" data-testid="recon-footnote">Nilai fisik = Σ (sisa panjang roll × HPP/unit) untuk roll berstatus {(data?.roll_statuses || Object.keys(ROLL_STATUS_LABELS)).map((s) => ROLL_STATUS_LABELS[s] || docStatusLabel(s)).join(", ")}. Saldo buku besar = jumlah akun persediaan PT itu (kolom Akun). Posting Saldo Awal menyamakan keduanya lewat Ekuitas Saldo Awal dan dipakai untuk pengisian saldo awal; selisih PT yang sudah bertransaksi ditelusuri lewat Jelaskan selisih lalu dikoreksi di dokumennya.</p>

      {/* Riwayat true-up (lanjutan INV-GL-DRIFT 2026-06) — alasan yang diketik di
          pop-up sekarang tersimpan di jurnalnya, jadi bisa dibaca di sini. */}
      <div className="mt-4 border-t border-[#F0F1F3] pt-3" data-testid="recon-history">
        <p className="mb-1.5 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">
          True-up terakhir ({history.length} jurnal)
          {selectedEntity && selectedEntity !== "all"
            ? ` · ${entityName(selectedEntity)}` : " · semua PT"}
        </p>
        {history.length === 0 ? (
          <p className="text-[11.5px] text-[#8E8E93]" data-testid="recon-history-empty">
            Belum ada true-up persediaan pada buku ini.
          </p>
        ) : (
          <div className="grid gap-1">
            {history.map((j) => (
              <div key={j.id} data-testid={`recon-history-${j.id}`}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-[#F4F5F7] bg-[#FAFBFC] px-2 py-1.5 text-[11.5px]">
                <span className="font-semibold text-[#1C1C1E]">{j.number}</span>
                <span className="text-[#8E8E93]">{formatDate(j.date)}</span>
                {(!selectedEntity || selectedEntity === "all") && j.entity_id && (
                  <span className="rounded bg-[#EFF3FB] px-1.5 py-0.5 text-[10.5px] font-semibold text-[#33538B]"
                    data-testid={`recon-history-entity-${j.id}`}>
                    {entityName(j.entity_id)}
                  </span>
                )}
                <span className="tabular-nums font-bold text-[#0058CC]">
                  {formatCurrency(j.total_debit)}
                </span>
                <span className="text-[#6B6B73]">oleh {j.created_by || "—"}</span>
                <span className={`min-w-0 flex-1 truncate ${j.reason ? "text-[#6B6B73]" : "text-[#C0392B]"}`}
                  data-testid={`recon-history-reason-${j.id}`}>
                  {j.reason ? `dasar: ${j.reason}` : "tanpa dasar tercatat"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* PK-27 (IV-07) — roll berbiaya 0 (di gudang & sudah terkirim), di bawah riwayat true-up. */}
      <ZeroCostRollsSection refreshKey={refreshKey} />
    </div>
  );
}
