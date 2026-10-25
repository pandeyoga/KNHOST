/**
 * WaitingQueueBoard — papan "yang menunggu keputusan" beserta UMUR TUNGGU-nya.
 *
 * Lahir sebagai Papan PO Custom di Control Tower pemilik (2026-08-24), lalu dipakai
 * ULANG (2026-06) untuk antrean lain yang sama mahalnya bila menunggu: kontrabon
 * bersengketa & retur antar-PT — dan sekarang juga muncul di Dasbor Manajer, orang
 * yang tanda tangannya justru ditunggu.
 *
 * Semua angka datang dari SATU sumber (`approval_backlog_service.queue_detail`):
 * `count` (yang menunggu), `shown`/`hidden`/`truncated` (kejujuran saat daftar
 * dipotong), dan `days_waiting` per baris. Layar tidak menghitung ulang apa pun,
 * jadi mustahil berselisih dengan antrean di layar yang sama (INV-HOME-01).
 */
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import SeeAllModal, { SeeAllFooter } from "./SeeAllModal";
import axios, { API } from "../services/apiClient";
import { askConfirm, askReason } from "../services/confirmService";
import { notifySuccess } from "../utils/feedback";
import { apiErrorText } from "../utils/apiError";
import EntityBadge from "./EntityBadge";
import { roleLabel } from "../config/roles";

const fmt = new Intl.NumberFormat("id-ID");
const fmtCur = (v) => `Rp ${fmt.format(Math.round(v || 0))}`;
const hasTitle = (r) => { const t = String(r?.title ?? "").trim(); return !!t && t !== "—" && t !== "-"; };

/** Umur tunggu diberi warna: "12 hari" dan "hari ini" bukan pekerjaan yang sama mendesaknya. */
function AgeBadge({ days, testId }) {
  const cls = days >= 7
    ? "bg-[#FFE5E5] text-[#C62828]"
    : days >= 3 ? "bg-[#FFF1DB] text-[#B26A00]" : "bg-[#EFF3FB] text-[#33538B]";
  return (
    <span data-testid={testId}
      className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold tabular-nums ${cls}`}>
      {days === 0 ? "< 1 hari" : `${days} hari`}
    </span>
  );
}

export default function WaitingQueueBoard({
  board = {}, loading = false, unreadable = false, onRetry, onNavigate,
  showEntity = false, icon: Icon, accent = "#6C3FD1", title,
  testIdBase, rowTestIdBase, gotoLabel = "Buka layarnya →", emptyText, gotoTestId,
  onActed, entityId = "all",
}) {
  const rows = board.rows || [];
  const go = () => { if (board.view && onNavigate) onNavigate(board.view); };
  const judul = title || (board.label || "Menunggu keputusan");
  const [busyId, setBusyId] = useState("");
  const [actError, setActError] = useState("");
  // UI/UX 2026-06 — papan hanya menampilkan CUPLIKAN 5 teratas (paling lama dulu);
  // selebihnya lewat pop-up "Lihat semua" supaya papan tidak memanjang ke bawah.
  const [showAll, setShowAll] = useState(false);
  const visible = rows.slice(0, 5);
  /**
   * MUAT SISA BARIS (2026-06) — papan hanya membawa cuplikan dari server
   * (`truncated`). Saat pop-up dibuka, sisa dokumen diambil sendiri dari
   * `GET /approvals/queue-board/{key}` (definisi antrean yang SAMA, INV-HOME-01)
   * supaya "Lihat semua" benar-benar berarti semuanya — lengkap dengan tombol
   * keputusan per baris sesuai izin peran.
   */
  const [fullRows, setFullRows] = useState(null);
  const [fullLoading, setFullLoading] = useState(false);
  const [fullError, setFullError] = useState("");
  useEffect(() => { setFullRows(null); }, [board]);

  async function fetchAllRows() {
    setFullLoading(true); setFullError("");
    try {
      const params = { limit: 300 };
      if (entityId && entityId !== "all") params.entity_id = entityId;
      const res = await axios.get(`${API}/approvals/queue-board/${board.key}`, { params });
      setFullRows(res.data?.rows || []);
    } catch (e) {
      setFullError("Gagal memuat baris lainnya — menampilkan yang sudah dimuat.");
    } finally { setFullLoading(false); }
  }

  function openSeeAll() {
    setShowAll(true);
    if (board.truncated && board.key && !fullRows && !fullLoading) fetchAllRows();
  }

  /**
   * PAPAN BISA DITINDAK (2026-06) — keputusan selesai TANPA pindah layar.
   *
   * Sebelum ini setiap baris hanya bisa "dibuka": orang yang tanda tangannya ditunggu
   * melihat dokumennya di papan, lalu harus berpindah layar, mencari barisnya lagi,
   * baru bisa menekan Setujui. Yang paling sering terjadi bukan salah klik, melainkan
   * TIDAK diklik sama sekali.
   *
   * Yang TIDAK dipindahkan ke sini: aturannya. Path & wewenangnya datang dari server
   * (`approval_backlog_service.ACTION_META`) dan endpoint tujuannya tetap endpoint
   * persetujuan yang sudah ada — lengkap dengan pemisahan tugas, ambang nilai, dan
   * pemeriksaan status. Papan tidak boleh punya jalur tulis sendiri.
   */
  async function act(row) {
    const a = row.action;
    if (!a) return;
    // T5: server bisa menyatakan keputusan ini PASTI ditolak untuk dokumen ini
    // (pemisahan tugas / ambang Direksi). Tombolnya tampil mati beserta alasannya.
    if (a.blocked_reason) { setActError(a.blocked_reason); return; }
    const title = `${a.label} ${row.number}?`;
    const message = `${row.title || ""}${row.amount > 0 ? ` · ${fmtCur(row.amount)}` : ""}`;
    let note = "";
    if (a.note_field) {
      // T3 DIBAYAR: isian catatan hanya diminta bila endpointnya PUNYA tempat
      // menyimpannya (`note_field`).
      const res = await askReason({
        title, message, confirmLabel: a.label,
        reasonLabel: "Catatan (opsional)",
        reasonRequired: false,
        reasonPlaceholder: "Boleh dikosongkan",
        testId: `${rowTestIdBase}-confirm`,
      });
      if (res === null) return;                   // dibatalkan
      note = res;
    } else {
      // T2 DIBAYAR: dulu dialognya SELALU meminta catatan padahal endpoint tujuannya
      // tidak punya field catatan — apa yang diketik orang dibuang diam-diam.
      const ok = await askConfirm({
        title, message, confirmLabel: a.label,
        testId: `${rowTestIdBase}-confirm`,
      });
      if (!ok) return;
    }
    setBusyId(row.id); setActError("");
    try {
      const body = { ...(a.body || {}) };
      // T3 DIBAYAR: catatan KOSONG jangan dikirim — nilai "" menimpa default server
      // yang berarti (mis. alasan bawaan persetujuan stock opname) sehingga
      // penyesuaian stok tercatat tanpa alasan apa pun.
      if (a.note_field && note) body[a.note_field] = note;
      await axios.post(`${API}${a.path}`, body);
      notifySuccess(`${a.label}: ${row.number}`, "Papan diperbarui.");
      if (fullRows) fetchAllRows();          // pop-up "Lihat semua" ikut segar
      if (onActed) await onActed();
      else if (onRetry) await onRetry();
    } catch (e) {
      // G0-03: penolakan izin/teks server lewat apiErrorText (bukan detail mentah "Permission ditolak: …").
      setActError(e?.response?.data?.detail
        ? apiErrorText(e) : `Gagal ${a.label.toLowerCase()} ${row.number}.`);
    } finally { setBusyId(""); }
  }

  // Satu penggambar baris untuk kartu DAN pop-up "Lihat semua" (testid dibedakan
  // lewat `base` supaya tidak ganda saat pop-up terbuka).
  // UAT 24 Okt (audit UI tahap 2) — G0-01: di HP (< 640px) nomor dokumen dulu terpotong ("SORD-26(") karena
  // satu baris berbagi tempat dengan nominal, umur & tombol. Kini nomor utuh di baris sendiri, judul maks 2 baris,
  // dan nominal/umur/tombol turun ke baris berikutnya; di desktop susunannya tetap satu baris.
  const renderRow = (r, base) => (
    <div key={r.id || r.number}
      className="flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-lg border border-[#EDEFF3] bg-white px-3 py-2 transition hover:border-[#C9D6E8] sm:flex-nowrap">
      <button type="button" data-testid={`${base}-${r.id}`}
        onClick={go}
        className="min-w-0 basis-full text-left sm:basis-auto sm:flex-1">
        <p className="flex flex-col text-[12px] font-semibold text-[#1C1C1E] sm:flex-row sm:items-center sm:gap-1.5">
          <span className="flex shrink-0 items-center gap-1.5 whitespace-nowrap">
            {r.number}
            {hasTitle(r) && <span className="hidden sm:inline">·</span>}
          </span>
          {/* Audit UI tahap 2 (G3-31) — judul kosong/"—" tidak lagi dirakit menjadi "· —". */}
          {hasTitle(r) && <span className="min-w-0 line-clamp-2 sm:line-clamp-1">{r.title}</span>}
          {showEntity && r.entity_id ? <span className="shrink-0"><EntityBadge entityId={r.entity_id} /></span> : null}
        </p>
        <p className="line-clamp-2 text-[10.5px] text-[#8E8E93] sm:line-clamp-1">
          {/* Label peran dari registry (`Manajer`), bukan kode mentah (C1). */}
          {r.note || judul}{r.role ? ` · perlu ${roleLabel(r.role)}` : ""}
        </p>
      </button>
      {r.amount > 0 && (
        <span className="shrink-0 text-[12px] font-bold tabular-nums text-[#1C1C1E]">{fmtCur(r.amount)}</span>
      )}
      <AgeBadge days={r.days_waiting} testId={`${base}-age-${r.id}`} />
      {/* Tombol keputusan hanya ada bila SERVER memberi `action`: itu berarti
          pintunya nyata DAN peran ini memang berwenang. G0-01: tombol biru baku (.primary-button) di semua papan —
          warna aksen papan hanya untuk ikon & bingkai. */}
      {r.action && (
        <button type="button"
          data-testid={`${base}-act-${r.id}`}
          disabled={busyId === r.id || !!r.action.blocked_reason}
          onClick={() => act(r)}
          className="primary-button ml-auto shrink-0 !rounded-full !px-2.5 !py-1 !text-[11px] !shadow-none sm:ml-0"
          title={r.action.blocked_reason
            || `${r.action.label} langsung dari papan ini`}>
          {busyId === r.id ? "…" : r.action.label}
        </button>
      )}
    </div>
  );

  return (
    <div className="rounded-xl border p-4"
      style={{ borderColor: `${accent}33`, background: `${accent}0A` }}
      data-testid={testIdBase}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {Icon ? <Icon size={15} style={{ color: accent }} /> : null}
          <h3 className="line-clamp-2 text-[14px] font-bold sm:line-clamp-1">
            {judul} {unreadable ? "(—)" : `(${board.count ?? 0})`}
          </h3>
        </div>
        <button type="button"
          className="shrink-0 text-[12px] font-semibold disabled:cursor-not-allowed disabled:opacity-40"
          style={{ color: accent }}
          onClick={go} disabled={!board.view}
          title={board.view ? "" : "Layar tujuan belum dikirim server"}
          data-testid={gotoTestId || `${testIdBase}-goto`}>{gotoLabel}</button>
      </div>

      {loading ? (
        <div className="h-16 animate-pulse rounded-lg bg-white/70" />
      ) : unreadable ? (
        /* Kegagalan pemuatan TIDAK boleh tampil sebagai kabar baik (B5). */
        <div className="flex flex-col items-center justify-center gap-2 py-4 text-center"
          data-testid={`${testIdBase}-unreadable`}>
          <p className="text-[13px] font-semibold text-[#C62828]">
            {judul} tidak bisa dibaca
          </p>
          <p className="text-[11.5px] text-[#6B6B73]">
            Data gagal dimuat — ini BUKAN berarti tidak ada yang menunggu keputusan.
          </p>
          {onRetry && (
            <button type="button" onClick={onRetry} className="secondary-button"
              data-testid={`${testIdBase}-retry`}>
              <RefreshCw size={13} /> Coba lagi
            </button>
          )}
        </div>
      ) : rows.length === 0 ? (
        <div className="flex h-16 items-center justify-center text-[13px] text-[#8E8E93]"
          data-testid={`${testIdBase}-empty`}>
          {emptyText || "Tidak ada dokumen yang menunggu keputusan"}
        </div>
      ) : (
        <div className="grid gap-1.5" data-testid={`${testIdBase}-list`}>
          {actError && (
            <div className="notice-bar danger" data-testid={`${testIdBase}-act-error`}>
              <span>{actError}</span>
              <button onClick={() => setActError("")}>×</button>
            </div>
          )}
          {visible.map((r) => renderRow(r, rowTestIdBase))}
          {/* Angka di judul tidak boleh lebih besar dari daftar di layar yang sama
              TANPA satu pun tanda (B2): kartu = cuplikan 5 teratas, pop-up = semuanya. */}
          <SeeAllFooter shown={visible.length} total={board.count ?? rows.length}
            label="dokumen" onClick={openSeeAll}
            testId={`${testIdBase}-see-all`}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed bg-white/60 px-3 py-2 text-[11.5px] font-semibold transition-colors hover:bg-white"
            style={{ color: accent, borderColor: `${accent}55` }} />
        </div>
      )}

      <SeeAllModal open={showAll} onClose={() => setShowAll(false)}
        title={judul} icon={Icon} accent={accent} rows={fullRows ?? rows}
        subtitle="Terurut dari yang paling lama menunggu"
        rowText={(r) => `${r.number || ""} ${r.title || ""} ${r.note || ""}`}
        renderRow={(r) => renderRow(r, `${rowTestIdBase}-modal`)}
        listClassName="grid gap-1.5 p-3"
        testId={`${testIdBase}-see-all-modal`}
        footerNote={fullLoading ? (
          <p className="mb-1.5 flex items-center justify-center gap-1.5 text-[11px] text-[#6B6B73]"
            data-testid={`${testIdBase}-fetching-all`}>
            <RefreshCw size={11} className="animate-spin" />
            Memuat {board.hidden ?? ""} dokumen lainnya…
          </p>
        ) : (board.truncated && !fullRows) ? (
          /* Pengambilan penuh gagal / belum jalan — kejujuran pemotongan SERVER tetap
             tampil beserta jalan keluarnya (layar penuh). */
          <button type="button" data-testid={`${testIdBase}-truncated`}
            onClick={go} disabled={!board.view}
            className="mb-2 w-full rounded-lg border border-dashed bg-white px-3 py-1.5 text-[11px] font-semibold disabled:opacity-40"
            style={{ borderColor: `${accent}55`, color: accent }}>
            {fullError ? `${fullError} · ` : ""}Server memuat {board.shown ?? rows.length} dari {board.count} —
            {" "}{board.hidden ?? (board.count - rows.length)} lainnya belum tampil ·
            {" "}{gotoLabel}
          </button>
        ) : null} />
    </div>
  );
}
