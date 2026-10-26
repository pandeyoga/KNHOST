/**
 * FASE G-9 — FinanceCasesView: **Pusat Kasus Keuangan** (Finance Exception Desk).
 *
 * Satu layar untuk uang yang "nyangkut": antrean kasus + ringkasan + wizard playbook.
 * Prinsip layar ini:
 *   · MENUNTUN — urutan antrean & kalimat playbook datang dari backend, bukan tebakan UI;
 *   · JUJUR — setiap penyelesaian menampilkan dokumen turunan yang benar-benar lahir;
 *   · TIDAK MEMAKSA — kasus tanpa alasan/bukti/persetujuan ditolak berikut arahannya.
 *
 * Akses: izin `finance_case` (admin/manager penuh; sales hanya melapor & memantau).
 *
 * Fase 4 · R2 — layar ini dibuka juga dari aplikasi HP (Lainnya › Kasus Keuangan) → layak 390 px:
 *  · L-02: kepala halaman (h2 + 3 tombol rata kiri) → `PageHeader` (aksi di kanan); saringan & daftar dalam
 *    `.section-card`;
 *  · L-01: pil jenis buatan sendiri & tab status (tingkat ke-3) → `FilterChips` (`case-chip-*`,
 *    `case-filter-status-*` tetap); hitungan status baru tampil setelah ringkasan termuat (dulu "0" saat memuat);
 *  · rincian kasus: berdampingan di ≥1280 px seperti dulu; di layar lebih sempit (HP/tablet) dulu jatuh DI BAWAH
 *    daftar (di luar pandangan) → kini `DetailModal` (layar penuh di HP).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw, Briefcase, Plus, ScanSearch, AlertTriangle, CheckCircle2, FilterX, Clock,
} from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import { KNSelect } from "../../../components/KNSelect";
import DetailModal from "../../../components/DetailModal";
import FilterChips from "../../../components/FilterChips";
import { PageHeader } from "../../../components/ListPageParts";
import useIsMobile from "../../../hooks/useIsMobile";
import { formatCurrency } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { askConfirm } from "../../../services/confirmService";
import CaseInboxTable from "./CaseInboxTable";
import CaseDetailPanel from "./CaseDetailPanel";
import CasePlaybookWizard from "./CasePlaybookWizard";
import CaseCreateModal from "./CaseCreateModal";
import { STATUS_FILTERS, humanAge } from "./caseApi";
import { caseNumberFromText } from "./caseDeepLink";
import { can } from "../../../config/roles";

export default function FinanceCasesView({ currentUser, selectedEntity, entities = [],
  focusCase = null, onFocusCaseConsumed }) {
  const [cases, setCases] = useState([]);
  const [stats, setStats] = useState(null);
  const [playbooks, setPlaybooks] = useState([]);
  const [reasons, setReasons] = useState([]);
  const [policy, setPolicy] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [active, setActive] = useState(null);
  const [wizard, setWizard] = useState(null);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [msgKind, setMsgKind] = useState("success");
  const [fStatus, setFStatus] = useState("");
  const [fType, setFType] = useState("");
  const [fOverdue, setFOverdue] = useState(false);
  const canResolve = can(currentUser?.permissions, "finance_case", "resolve");
  // Di bawah 1280 px rincian tidak lagi berdampingan dengan daftar → tampil sebagai pop-up (lihat kepala berkas).
  const stacked = useIsMobile(1279);   // Sisir lanjutan gerbang peran (2026-10-21) — POST /finance-cases/{id}/resolve

  const notify = (m, kind = "success") => {
    setMsg(m); setMsgKind(kind);
    setTimeout(() => setMsg(""), kind === "warning" ? 12000 : 6000);
  };
  /**
   * KN-G9-ERR-SILENT \u2014 penolakan backend WAJIB terbaca pengguna.
   * Semua error dinormalkan ke KALIMAT di sini, supaya tidak ada lagi objek axios
   * mentah yang masuk ke `<ErrorNotice message>` (lihat utils/apiError.js).
   */
  const fail = useCallback((e) => setErr(apiErrorText(e)), []);

  const loadRefs = useCallback(async () => {
    try {
      const [pb, rs, pol, cust, acc] = await Promise.all([
        axios.get(`${API}/finance-cases/playbooks`),
        axios.get(`${API}/finance-cases/reasons`),
        axios.get(`${API}/finance-cases/policy`),
        axios.get(`${API}/customers`),
        axios.get(`${API}/bank-accounts`),
      ]);
      setPlaybooks(Array.isArray(pb.data) ? pb.data : []);
      setReasons(Array.isArray(rs.data) ? rs.data : []);
      setPolicy(pol.data || null);
      const list = (d) => (Array.isArray(d) ? d : (d?.items || []));
      setCustomers(list(cust.data));
      setAccounts(list(acc.data));
    } catch (e) { fail(e); }
    /**
     * AUDIT PERAN (2026-08-15) — SATU daftar opsional tidak boleh mematikan layar.
     * Daftar supplier hanya dipakai pemilih lawan-transaksi untuk kasus bertipe
     * supplier. Dulu ia ikut di dalam `Promise.all` di atas, sehingga SATU 403
     * (peran `finance` belum punya `supplier.view` waktu itu) menggagalkan seluruh
     * blok: playbook, alasan, kebijakan, pelanggan, DAN rekening ikut kosong, lalu
     * layar utama Kasus Keuangan — menu resmi peran ini — disambut bilah merah.
     * Izinnya sekarang sudah diberikan (permissions_config.py), dan pemisahan ini
     * memastikan kelas cacat itu tak bisa lahir lagi dari daftar opsional lain.
     */
    try {
      const sup = await axios.get(`${API}/suppliers`);
      setSuppliers(Array.isArray(sup.data) ? sup.data : (sup.data?.items || []));
    } catch { setSuppliers([]); }
  }, [fail]);

  const loadData = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const [ls, st] = await Promise.all([
        axios.get(`${API}/finance-cases`, {
          params: {
            ...(fStatus ? { status: fStatus } : {}),
            ...(fType ? { case_type: fType } : {}),
            ...(fOverdue ? { overdue_only: true } : {}),
          },
        }),
        axios.get(`${API}/finance-cases/stats`),
      ]);
      const rows = Array.isArray(ls.data) ? ls.data : [];
      setCases(rows);
      setStats(st.data || null);
      setActive((cur) => (cur ? rows.find((r) => r.id === cur.id) || cur : null));
    } catch (e) { fail(e); } finally { setLoading(false); }
  }, [fStatus, fType, fOverdue, fail]);

  useEffect(() => { loadRefs(); }, [loadRefs, selectedEntity]);
  useEffect(() => { loadData(); }, [loadData, selectedEntity]);

  /**
   * US8 — deep-link dari **Rekonsiliasi Bank → Dana Titipan**. Petugas menekan
   * "Buka kasus" di layar titipan, lalu MENDARAT langsung pada kasusnya di sini
   * (tidak disuruh mencari menunya sendiri).
   *
   * KENAPA MENGAMBIL ULANG DARI SERVER, bukan mencari di `cases` yang sedang tampil:
   * daftar bisa (a) belum selesai dimuat saat deep-link tiba — dulu ini membuat layar
   * salah berkata "kasus tidak ada di daftar ini" padahal barisnya terpampang; atau
   * (b) tersaring/terpotong halaman. Mengambil `GET /finance-cases/{id}` (atau
   * mencocokkan nomor lewat daftar tanpa filter) membuat hasilnya PASTI, bukan lomba
   * waktu antar-render.
   */
  useEffect(() => {
    if (!focusCase?.nonce) return;
    const { caseId, number, note, noteKind } = focusCase;
    if (!caseId && !number) { onFocusCaseConsumed?.(); return; }
    let alive = true;
    (async () => {
      try {
        let hit = null;
        if (caseId) {
          const r = await axios.get(`${API}/finance-cases/${caseId}`);
          hit = r.data || null;
        } else {
          const r = await axios.get(`${API}/finance-cases`);
          hit = (Array.isArray(r.data) ? r.data : []).find((c) => c.number === number) || null;
        }
        if (!alive) return;
        if (hit) {
          // Filter dibersihkan supaya kasus tujuan tidak tersaring keluar dari tabel.
          setFStatus(""); setFType(""); setFOverdue(false);
          setActive(hit);
          setErr("");
          notify(note || `Kasus ${hit.number} dibuka — lanjutkan dari panel di kanan.`,
            noteKind || "success");
        } else {
          setErr(`Kasus ${number || "yang diminta"} tidak bisa dibuka — mungkin milik PT `
            + `lain atau sudah dihapus.`);
        }
      } catch (e) {
        if (alive) fail(e);
      } finally {
        if (alive) onFocusCaseConsumed?.();
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusCase?.nonce]);

  async function runScan() {
    // G1-16 — pemindaian membuat kasus baru & menaikkan kasus lama ke atasan → konfirmasi dulu.
    if (!(await askConfirm({
      title: "Pindai temuan sekarang?",
      message: "Sistem membuat kasus baru dari titipan dana & dugaan bayar dobel, dan menaikkan kasus yang "
        + "melewati batas ke atasan. Kasus yang sudah ada tidak digandakan.",
      confirmLabel: "Pindai",
    }))) return;
    setBusy("scan"); setErr("");
    try {
      const r = await axios.post(`${API}/finance-cases/scan`, {});
      const d = r.data || {};
      notify(d.enabled === false
        ? d.note
        : `Pemindaian selesai: ${d.holding_cases} kasus dari titipan dana, `
          + `${d.duplicate_cases} kasus dugaan bayar dobel, ${d.escalated} dinaikkan ke atasan `
          + `(${d.skipped} dilewati karena sudah ada kasusnya).`);
      await loadData();
    } catch (e) { fail(e); } finally { setBusy(""); }
  }

  const typeOptions = useMemo(() => [
    { value: "", label: "Semua jenis kasus" },
    ...playbooks.map((p) => ({ value: p.code, label: p.label })),
  ], [playbooks]);
  const filterOn = !!(fStatus || fType || fOverdue);
  const detailProps = active ? {
    caseData: active, reasons, canResolve,
    onClose: () => setActive(null),
    onChanged: async (updated) => { setActive(updated); await loadData(); },
    onOpenWizard: (c) => setWizard(c),
    onError: fail, onNotify: notify,
  } : null;

  return (
    <div className="view-container" data-testid="finance-cases-view">
      <PageHeader icon={Briefcase} title="Pusat Kasus Keuangan" testId="case-head"
        subtitle={"Antrean uang yang nyangkut — salah transfer, bayar dobel, giro ditolak, dana tak dikenal — "
          + "diselesaikan lewat langkah baku yang selalu melahirkan dokumen, bukan perubahan senyap."}
        actions={(
          <>
            <button type="button" className="secondary-button" data-testid="case-refresh" onClick={loadData}>
              <RefreshCw size={14} className={loading ? "spin" : ""} /> Muat ulang
            </button>
            <button type="button" className="secondary-button" data-testid="case-scan"
              disabled={busy === "scan"} onClick={runScan}>
              <ScanSearch size={14} className={busy === "scan" ? "spin" : ""} /> Pindai temuan
            </button>
            <button type="button" className="primary-button" data-testid="case-new" onClick={() => setCreating(true)}>
              <Plus size={14} /> Kasus baru
            </button>
          </>
        )} />

      {err && <ErrorNotice message={err} onRetry={loadData} onDismiss={() => setErr("")}
        onAction={caseNumberFromText(err)
          ? () => {
            const n = caseNumberFromText(err);
            const hit = cases.find((c) => c.number === n);
            setErr("");
            if (hit) { setActive(hit); } else { setFStatus(""); setFType(""); setFOverdue(false); }
          }
          : undefined}
        actionLabel={caseNumberFromText(err) ? `Buka ${caseNumberFromText(err)}` : ""}
        testId="case-error" />}
      {msg && (
        <div className={`notice-bar ${msgKind} !mb-0`} data-testid="case-notice">
          {msgKind === "warning" ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
          {" "}{msg}
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5" data-testid="case-stats">
          <div className="stat-card">
            <p className="stat-label">Kasus terbuka</p>
            <p className="stat-value" data-testid="case-stat-open">{stats.open}</p>
            <p className="text-[11px] text-[#8E8E93]">{stats.in_progress} sedang ditangani</p>
          </div>
          <div className={`stat-card ${stats.overdue ? "ring-1 ring-[#F3C9C7]" : ""}`}>
            <p className="stat-label">Lewat batas waktu</p>
            <p className={`stat-value ${stats.overdue ? "text-[#C0392B]" : "text-[#1B7F4B]"}`}
              data-testid="case-stat-overdue">{stats.overdue}</p>
            <p className="text-[11px] text-[#8E8E93]">
              {stats.overdue ? "perlu tindakan hari ini" : "semua masih dalam batas waktu"}
            </p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Nilai uang terdampak</p>
            <p className="stat-value text-[#0058CC]" data-testid="case-stat-money">
              {formatCurrency(stats.money_at_stake)}
            </p>
            <p className="text-[11px] text-[#8E8E93]">pada kasus yang belum selesai</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Kasus tertua</p>
            {/* Audit UI 24 Okt (131): dulu "baru saja" walau tidak ada kasus terbuka. */}
            <p className={`stat-value flex items-center gap-1 ${(stats.open || 0) + (stats.in_progress || 0) > 0 ? "text-[#B26A00]" : "text-[#8E8E93]"}`}>
              <Clock size={14} /> {(stats.open || 0) + (stats.in_progress || 0) > 0 ? humanAge(stats.oldest_age_hours) : "—"}
            </p>
            {(stats.open || 0) + (stats.in_progress || 0) === 0 && <p className="text-[11px] text-[#8E8E93]">tidak ada kasus terbuka</p>}
          </div>
          <div className="stat-card">
            <p className="stat-label">Sudah selesai</p>
            <p className="stat-value text-[#1B7F4B]" data-testid="case-stat-resolved">
              {stats.resolved}
            </p>
            <p className="text-[11px] text-[#8E8E93]">{stats.rejected} ditutup tanpa tindakan</p>
          </div>
        </div>
      )}

      <div className="section-card">
        <div className="section-body space-y-3">
          {!!stats?.by_type?.length && (
            <FilterChips testId="case-type-chips" ariaLabel="Saring jenis kasus" clearable
              value={fType || null} onChange={(k) => setFType(k || "")}
              options={stats.by_type.map((t) => ({
                key: t.case_type, testId: `case-chip-${t.case_type}`,
                label: <>{t.label} <b>{t.open}</b>/{t.total}</>,
              }))} />
          )}

          <div className="grid grid-cols-1 gap-2 rounded-lg border border-[#E5E5EA] bg-[#FAFBFC] px-3 py-2"
            data-testid="case-filter-bar">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold text-[#6B6B73]">Status</span>
              <FilterChips ariaLabel="Saring status kasus" className="min-w-0" testId="case-filter-status"
                value={fStatus || "all"} onChange={(k) => setFStatus(k === "all" ? "" : k)}
                options={STATUS_FILTERS.map((o) => ({
                  key: o.value || "all", label: o.label,
                  count: stats ? (o.value ? stats.by_status?.[o.value] ?? 0 : stats.total ?? cases.length) : undefined,
                }))} />
            </div>
            <div className="flex flex-wrap items-end gap-3">
              {/* G1-35 — lebar tetap supaya memilih jenis tidak menggeser isi bilah. */}
              <div className="w-full shrink-0 sm:w-[230px]">
                <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Jenis kasus</label>
                <KNSelect data-testid="case-filter-type" value={fType}
                  onValueChange={setFType} options={typeOptions} />
              </div>
              <label className="flex items-center gap-1.5 text-[12px] text-[#1C1C1E]">
                <input type="checkbox" data-testid="case-filter-overdue" checked={fOverdue}
                  onChange={(e) => setFOverdue(e.target.checked)} />
                Hanya yang terlambat
              </label>
              {filterOn && (
                <button type="button" className="secondary-button" data-testid="case-filter-clear"
                  onClick={() => { setFStatus(""); setFType(""); setFOverdue(false); }}>
                  <FilterX size={14} /> Bersihkan filter
                </button>
              )}
              <span className="ml-auto self-center text-[11px] text-[#6B6B73]" data-testid="case-filter-count">
                {loading ? "Memuat…" : `${cases.length} kasus ditampilkan`}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[3fr_2fr]">
            <CaseInboxTable cases={cases} loading={loading} activeId={active?.id}
              onOpen={setActive} />
            {!stacked && (active
              ? <CaseDetailPanel {...detailProps} />
              : (
                <div className="rounded-lg border border-dashed border-[#E5E5EA] bg-white px-4 py-10 text-center"
                  data-testid="case-detail-empty">
                  <p className="text-[13px] font-semibold text-[#1C1C1E]">
                    Pilih satu kasus untuk melihat detailnya.
                  </p>
                  <p className="mt-1 text-[12px] text-[#6B6B73]">
                    Panel ini menampilkan sumber uang, langkah playbook, bukti, dokumen turunan,
                    dan jejak waktu siapa melakukan apa.
                  </p>
                </div>
              ))}
          </div>
        </div>
      </div>

      {stacked && active && (
        <DetailModal open onClose={() => setActive(null)} size="lg" label={`Kasus ${active.number || ""}`}
          testId="case-detail-modal">
          <CaseDetailPanel {...detailProps} />
        </DetailModal>
      )}

      <p className="flex items-start gap-1 text-[11px] text-[#9A9BA3]">
        <AlertTriangle size={11} className="mt-[2px] shrink-0" />
        Kasus yang sudah melahirkan dokumen tidak bisa dibuka ulang — tindak lanjutnya kasus
        baru (buku besar bersifat tambah-saja). Batas waktu, ambang persetujuan, dan jendela
        deteksi dobel diatur di Pengaturan → Pusat Kasus Keuangan.
      </p>

      {wizard && policy && (
        <CasePlaybookWizard caseData={wizard} reasons={reasons} entities={entities}
          customers={customers} suppliers={suppliers} accounts={accounts} policy={policy}
          onClose={() => setWizard(null)}
          onDone={async (updated) => {
            setWizard(null);
            setActive(updated);
            notify(`${updated.number} — ${updated.status === "resolved"
              ? "kasus selesai" : "langkah dijalankan"}: `
              + `${(updated.documents || []).length} dokumen turunan lahir.`);
            await loadData();
          }}
          onError={fail} />
      )}

      {creating && (
        <CaseCreateModal playbooks={playbooks} customers={customers} suppliers={suppliers}
          onClose={() => setCreating(false)}
          onCreated={async (c) => {
            setCreating(false);
            setActive(c);
            notify(`Kasus ${c.number} dibuat. Batas waktu ${c.sla_hours} jam.`);
            await loadData();
          }}
          onError={fail} />
      )}
    </div>
  );
}
