import { useEffect, useState } from "react";
import { Inbox, ArrowRight, Clock, RefreshCw, CheckSquare, FileEdit } from "lucide-react";
import { formatCurrency, formatPeriod } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import { SearchBox } from "../../components/ListControls";
// Tujuan navigasi yang SAH untuk peran ini (sumber sama dengan Ctrl+K & deep-link) —
// dipakai ringkasan antrean agar tidak pernah menawarkan tautan yang buntu.
import { resolveDeepLinkTarget } from "../../config/navigationConfig";
import PaginationBar from "../../components/PaginationBar";
import SeeAllModal, { SeeAllFooter } from "../../components/SeeAllModal";
import PageTabs from "../../components/PageTabs";
import LinkCard from "../../components/LinkCard";
import useViewPreset from "../../hooks/useViewPreset";
import ApprovalDecisionModal from "./ApprovalDecisionModal";
import MyApprovalsPanel from "./MyApprovalsPanel";
import { KIND_META, loadInbox } from "./approvalInboxData";
import { INBOX_TABS, LISTED_IN_INBOX, canSeeMatrix } from "./inboxTabs";
import { notifySuccess } from "../../utils/feedback";
import { actorLabel } from "../../utils/actorLabel";
import { roleLabel } from "../../config/roles";

/**
 * ApprovalInbox — "Pusat Persetujuan" (FASE 5 — terpadu).
 * Hub lintas-modul: menampilkan SEMUA persetujuan yang menunggu keputusan dalam satu tempat:
 *  - Sales Order (SSOT `pending_approvals`: nilai / kredit / harga khusus) → deep-link ke DETAIL SO.
 *  - PO pembelian, retur jual/beli, cycle count, kredit pelanggan → keputusan di tempat (pop-up) / layar modul.
 *
 * Fase 3 · P3 (D-06, keputusan pemilik) — SATU antrean persetujuan:
 *  · tab **Matriks divisi** = panel "Persetujuan Saya" (ACC desain, PO custom 2 tingkat, PR, klaim makloon + jejak),
 *    hanya untuk peran yang dulu membuka `my-approvals` (`canSeeMatrix`); alias `my-approvals` → {tab:"matrix"} (P8).
 *  · tab **Amandemen** = kartu tautan berhitungan ke Pusat Amandemen — keputusan amandemen HANYA di sana, jadi
 *    amandemen tidak lagi didaftar/diputus di sini dan dihitung "ditangani di layar lain".
 *  · preset `{ tab }` (chip Control Tower / Dasbor Manajer, alias) membuka tab yang dituju.
 */

// INV-UI-07 — daftar berhalaman wajib bisa diunduh (kolom = yang dilihat di baris).
const INBOX_CSV_COLUMNS = [
  { header: "Jenis", get: (it) => KIND_META[it.kind]?.label || it.kind || "" },
  { key: "title", header: "Dokumen" },
  { key: "subtitle", header: "Keterangan" },
  { key: "meta", header: "Info" },
  { key: "amount", header: "Nilai", type: "num" },
  { header: "Diajukan oleh", get: (it) => actorLabel(it.requester, "") },
  { header: "Butuh peran", get: (it) => roleLabel(it.role || "manager") },
  { key: "at", header: "Diajukan pada", type: "date" },
];

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))} mnt lalu`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} jam lalu`;
  return `${Math.floor(diff / 86400)} hari lalu`;
}

// UI/UX 2026-06 — daftar utama berhalaman (bukan satu gulungan panjang ke bawah).
const PAGE_SIZE = 15;

export default function ApprovalInbox({ currentUser, onNavigate, onOpenDocument }) {
  const [items, setItems] = useState([]);
  const [amendments, setAmendments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const showMatrix = canSeeMatrix(currentUser?.role);
  const validTab = (t) => INBOX_TABS.some((x) => x.key === t) && (t !== "matrix" || showMatrix);
  const [tab, setTab] = useState("all");
  const [page, setPage] = useState(1);
  // Preset navigasi (alias `my-approvals` → matrix, chip beranda → jenis) — juga saat layar sudah terbuka.
  useViewPreset("approval-inbox", (p) => { if (validTab(p.tab)) { setTab(p.tab); setPage(1); } });
  const [showAllOthers, setShowAllOthers] = useState(false);
  // KEPUTUSAN DI TEMPAT (2026-06) — baris dibuka sebagai pop-up detail + Setujui/Tolak.
  const [reviewItem, setReviewItem] = useState(null);
  /**
   * RINGKASAN SELURUH ANTREAN (F-3, 2026-08-15) — dari `GET /approvals/backlog`, sumber yang SAMA dengan KPI
   * beranda. Antrean yang TIDAK didaftar layar ini tetap disebut di sini beserta jalannya, supaya "Pusat
   * Persetujuan" berhenti mengaku kosong untuk pekerjaan yang sebenarnya menumpuk di tab sebelah.
   */
  const [backlog, setBacklog] = useState(null);
  // AUDIT SALES vs ADMIN SALES (2026-08-15) — kategori yang GAGAL dimuat disebut, bukan "tidak ada yang menunggu"
  // (Admin Sales membuka layar ini read-only; kategori di luar wilayahnya wajar tak terbaca, tapi tidak disembunyikan).
  const [unavailable, setUnavailable] = useState([]);
  const [inboxQ, setInboxQ] = useState("");

  useEffect(() => { load(); }, []); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const res = await loadInbox();
      setItems(res.items);
      setAmendments(res.amendments);
      setBacklog(res.backlog);
      setUnavailable(res.unavailable);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat antrian persetujuan.");
    } finally {
      setLoading(false);
    }
  }

  const groupOf = (it) => KIND_META[it.kind]?.group;
  const counts = INBOX_TABS.reduce((acc, t) => {
    acc[t.key] = t.key === "all" ? items.length
      : t.key === "amendment" ? amendments.length
        : t.key === "matrix" ? undefined : items.filter((i) => groupOf(i) === t.key).length;
    return acc;
  }, {});
  const filtered = items.filter((i) => (tab === "all" || groupOf(i) === tab)
    && (!inboxQ.trim() || Object.values(i).filter((v) => typeof v === "string" || typeof v === "number").join(" ").toLowerCase().includes(inboxQ.trim().toLowerCase())));
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const curPage = Math.min(page, totalPages);
  const pageRows = filtered.slice((curPage - 1) * PAGE_SIZE, curPage * PAGE_SIZE);
  /**
   * Berapa dari total antrean yang TIDAK diurus daftar layar ini (transfer gudang, kontrabon, permintaan
   * internal & retur antar-PT, tagihan supplier, biaya masuk, uang muka, klaim makloon, buka periode, cuti,
   * lembur, PR, spesifikasi/sample, pesanan khusus, antar-PT, dan — sejak D-06 — amandemen). FASE F-6 menambahkan
   * DAFTAR dokumennya (bukan cuma angka).
   */
  const elsewhere = (backlog?.all_items || [])
    .filter((q) => !LISTED_IN_INBOX.includes(q.key))
    .reduce((s, q) => s + (q.count || 0), 0);
  //: dokumen NYATA dari antrean-antrean itu (paling lama menunggu lebih dulu).
  const othersOldest = (backlog?.oldest || []).filter((o) => !LISTED_IN_INBOX.includes(o.key));

  // UAT 24 Okt (audit UI tahap 2, G5-21) — label antrean server berbahasa campur ("Payroll menunggu pengesahan") dan
  // periode mentah ("2026-08") di judul. Teks server tidak diubah di sini (berkas backend grup lain).
  const queueText = (label) => String(label || "").replace(" menunggu ACC", "").replace(/^Payroll\b/, "Penggajian");
  const periodText = (t) => String(t || "").replace(/\b(\d{4}-\d{2})\b(?!-)/g, (m) => formatPeriod(m)).replace(/\bPayroll\b/g, "Penggajian");

  // Satu penggambar baris "menunggu di layar lain" untuk kartu (cuplikan 5) DAN pop-up "Lihat semua".
  const renderOther = (o, base = "approval-inbox-other") => {
    const target = resolveDeepLinkTarget(o.view, currentUser?.role);
    return (
      <div key={`${o.key}-${o.id}`} data-testid={`${base}-${o.id}`}
        className="flex items-center gap-3 px-3 py-2.5 hover:bg-[#FAFBFC]">
        <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[#FEF3C7] text-[#B45309]">
          <Clock size={14} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="text-[12px] font-bold text-[#1C1C1E] [overflow-wrap:anywhere]">{o.number}</span>
            <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-[#F2F2F7] text-[#6B6B73]">
              {queueText(o.queue_label)}
            </span>
          </div>
          <p className="text-[11px] text-[#6B6B73] truncate">{periodText(o.title) || "—"}</p>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-[11px] font-semibold tabular-nums text-[#B45309]">
            {o.days_waiting === 0 ? "menunggu < 1 hari" : `menunggu ${o.days_waiting} hari`}
          </p>
          <button data-testid={`${base}-open-${o.id}`}
            disabled={!target}
            title={target ? `Buka ${o.queue_label}` : "Antrean ini bukan wilayah peran Anda"}
            onClick={() => target && onNavigate?.(target.navId, target.view, target.tab)}
            className={`mt-1 inline-flex items-center gap-1 text-[11px] font-bold ${
              target ? "text-[#0058CC] hover:underline" : "text-[#8E8E93] cursor-not-allowed"}`}>
            Buka layarnya <ArrowRight size={12} />
          </button>
        </div>
      </div>
    );
  };

  const handleReview = (it) => {
    if (it.isSO && onOpenDocument) {
      onOpenDocument({ nav_id: "orders", view: "orders", focus_type: "sales_order", focus_id: it.orderId });
      return;
    }
    onNavigate?.(it.target, it.targetView, it.targetTab);
  };
  const listTab = tab !== "matrix" && tab !== "amendment";

  return (
    <div data-testid="approval-inbox-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="approval-inbox-error" />

      {unavailable.length > 0 && (
        <div className="notice-bar warning !py-1.5 mb-2" data-testid="approval-inbox-partial">
          <span className="text-[11.5px]">
            Daftar ini <strong>belum lengkap</strong>: {unavailable.length} kategori tidak
            bisa ditampilkan untuk peran Anda ({unavailable.join(", ")}). Angka di tab
            terkait karena itu bukan nol sungguhan.
          </span>
        </div>
      )}

      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2 min-w-0">
            <Inbox size={16} className="text-[#0058CC]" />
            <div className="min-w-0">
              <h2 data-testid="approval-inbox-title">Pusat Persetujuan</h2>
              <p className="text-[11px] text-[#6B6B73]">Semua persetujuan yang menunggu keputusan — daftar rinci untuk Pesanan Penjualan (nilai/kredit/harga), PO, retur, stock opname &amp; kredit pelanggan{showMatrix ? "; matriks divisi (ACC desain, PO custom, PR, klaim makloon) di tab Matriks divisi" : ""}; antrean lain (amandemen, transfer gudang, kontrabon, cuti, uang muka, …) tampil beserta nomor dokumen &amp; umur tunggunya.</p>
            </div>
          </div>
          <button data-testid="approval-inbox-refresh" onClick={load} className="secondary-button shrink-0 whitespace-nowrap">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat Ulang
          </button>
        </div>
        <div className="section-body">
          {/* RINGKASAN SELURUH ANTREAN — angka yang sama dengan KPI beranda (INV-HOME-01). */}
          {backlog && (
            <div className="mb-3 rounded-lg border border-[#E4E9F2] bg-[#F8FAFD] p-3"
              data-testid="approval-inbox-backlog">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <p className="text-[12px] font-semibold text-[#3A3A3C]">
                  Menunggu keputusan (semua jenis):{" "}
                  <span className="tabular-nums text-[#0058CC]"
                    data-testid="approval-inbox-backlog-total">{backlog.total}</span>
                </p>
                {elsewhere > 0 && (
                  // Audit UI 24 Okt (000) / G5-21 — rincian: berapa di daftar bawah & berapa di layar lain.
                  <span className="text-[11px] text-[#6B6B73]"
                    data-testid="approval-inbox-backlog-elsewhere">
                    {items.length} di daftar bawah · {elsewhere} ditangani di layar lain
                  </span>
                )}
              </div>
              {(backlog.items || []).length === 0 ? (
                <p className="text-[11.5px] text-[#6B6B73]" data-testid="approval-inbox-backlog-empty">
                  Tidak ada satu pun dokumen yang menunggu keputusan.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {(backlog.items || []).map((q) => {
                    const target = resolveDeepLinkTarget(q.view, currentUser?.role);
                    return (
                      <button key={q.key} type="button"
                        data-testid={`approval-inbox-backlog-${q.key}`}
                        disabled={!target}
                        title={target ? `Buka ${q.label}` : "Antrean ini bukan wilayah peran Anda"}
                        onClick={() => target && onNavigate?.(target.navId, target.view, target.tab)}
                        className={`flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11.5px] ${
                          target
                            ? "border-[#CFDBEC] bg-white text-[#1C1C1E] hover:border-[#0058CC] hover:text-[#0058CC]"
                            : "border-[#E5E5EA] bg-[#F2F2F7] text-[#8E8E93] cursor-not-allowed"}`}>
                        <span className="truncate max-w-[15rem]">{queueText(q.label)}</span>
                        <span className="font-bold tabular-nums">{q.count}</span>
                        {target && <ArrowRight size={11} />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
          <PageTabs testId="approval-inbox-tabs" value={tab} ariaLabel="Jenis persetujuan"
            tabTestId={(k) => `approval-inbox-tab-${k}`}
            onChange={(k) => { setTab(k); setPage(1); }}
            tabs={INBOX_TABS.map((t) => ({ key: t.key, label: t.label, count: counts[t.key], showZero: t.key !== "matrix",
              hidden: t.key === "matrix" && !showMatrix }))} />
        </div>
      </div>

      {/* ── FASE F-6 — ANTREAN LAIN SEBAGAI DOKUMEN, BUKAN CUMA ANGKA ── (sumber sama dengan KPI beranda) */}
      {listTab && othersOldest.length > 0 && (
        <div className="section-card mb-3" data-testid="approval-inbox-others">
          <div className="section-head">
            <div className="flex items-center gap-2 min-w-0">
              <Clock size={15} className="text-[#B45309]" />
              <div className="min-w-0">
                <h2>Menunggu di layar lain — paling lama dulu</h2>
                <p className="text-[11px] text-[#6B6B73]">
                  Keputusan yang tempat kerjanya bukan daftar di bawah: amandemen, transfer gudang,
                  kontrabon, permintaan internal &amp; retur antar-PT, tagihan supplier,
                  uang muka, klaim makloon, buka periode, cuti &amp; lembur.
                </p>
              </div>
            </div>
          </div>
          <div className="divide-y divide-[#EFF0F2]">
            {othersOldest.slice(0, 5).map((o) => renderOther(o))}
          </div>
          <SeeAllFooter shown={Math.min(5, othersOldest.length)} total={othersOldest.length}
            label="dokumen" accent="#B45309" onClick={() => setShowAllOthers(true)}
            testId="approval-inbox-others-see-all" />
          <SeeAllModal open={showAllOthers} onClose={() => setShowAllOthers(false)}
            title="Menunggu di layar lain"
            subtitle="Paling lama menunggu lebih dulu — klik untuk melompat ke layar keputusannya"
            icon={Clock} accent="#B45309" rows={othersOldest}
            rowText={(o) => `${o.number || ""} ${o.title || ""} ${o.queue_label || ""}`}
            renderRow={(o) => renderOther(o, "approval-inbox-other-modal")}
            testId="approval-inbox-others-modal" />
        </div>
      )}

      {tab === "matrix" && showMatrix && <MyApprovalsPanel currentUser={currentUser} embedded />}

      {tab === "amendment" && (
        <div className="section-card" data-testid="approval-inbox-amendments">
          <div className="section-body">
            {/* D-06 — keputusan amandemen HANYA di Pusat Amandemen (dulu juga diputus di pop-up inbox). */}
            <LinkCard testId="approval-inbox-amendments-link" icon={FileEdit}
              what="Keputusan amandemen dokumen" where="Penjualan › Pesanan › Koreksi & Amandemen" view="amendments"
              count={amendments.length} label="Buka Pusat Amandemen"
              summary={amendments.length ? `${amendments.length} usulan menunggu keputusan` : "tidak ada usulan yang menunggu"} />
          </div>
        </div>
      )}

      {listTab && (
      <div className="section-card">
        <div className="px-3 py-2"><SearchBox value={inboxQ} onChange={setInboxQ} placeholder="Cari nomor / judul / pengaju…" testId="approval-inbox-search" /></div>
        {loading ? (
          <div className="py-12 text-center text-[12px] text-[#6B6B73]">Memuat antrian persetujuan...</div>
        ) : filtered.length === 0 ? (
          <div className="py-14 text-center text-[12px] text-[#6B6B73]" data-testid="approval-inbox-empty">
            <CheckSquare className="mx-auto mb-2 text-gray-300" size={30} />
            {/* G5-21 — bila ada kategori yang tak terbaca (403), jangan menyatakan "semua beres". */}
            {unavailable.length > 0 ? (<>
              <p className="font-semibold text-[#3C3C43]">Tidak ada yang menunggu di kategori yang bisa Anda lihat.</p>
              <p>Sebagian kategori tidak bisa ditampilkan untuk peran Anda ({unavailable.join(", ")}).</p>
            </>) : inboxQ.trim() || tab !== "all" ? (
              <p className="font-semibold text-[#3C3C43]">Tidak ada persetujuan yang cocok dengan saringan ini.</p>
            ) : (<>
              <p className="font-semibold text-[#3C3C43]">Tidak ada yang menunggu persetujuan.</p>
              <p>Semua keputusan sudah ditindaklanjuti.</p>
            </>)}
          </div>
        ) : (
          <div className="divide-y divide-[#EFF0F2]">
            {pageRows.map((it) => {
              const m = KIND_META[it.kind] || KIND_META.po;
              const Icon = m.icon;
              return (
                <div key={`${it.kind}-${it.id}`} data-testid={`approval-inbox-item-${it.id}`}
                  className="flex items-center gap-3 px-3 py-2.5 hover:bg-[#FAFBFC]">
                  <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full"
                    style={{ background: m.bg, color: m.fg }}>
                    <Icon size={15} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                      <span className="text-[12px] font-bold text-[#1C1C1E] [overflow-wrap:anywhere]">{it.title}</span>
                      <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded"
                        style={{ background: m.bg, color: m.fg }}>
                        {m.label}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#6B6B73] truncate">{it.subtitle}{it.meta ? ` · ${it.meta}` : ""}</p>
                    {/* Audit UI 24 Okt (000) — akun teknis ("system-seed") tidak ditampilkan mentah; peran berlabel Indonesia. */}
                    <p className="text-[11px] text-[#8E8E93] flex flex-wrap items-center gap-x-1 mt-0.5">
                      <Clock size={10} /> {timeAgo(it.at)} · diajukan {actorLabel(it.requester)} · butuh <b>{roleLabel(it.role || "manager")}</b>
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    {it.amount != null && (
                      <p className="text-[13px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(it.amount)}</p>
                    )}
                    <button data-testid={`approval-inbox-review-${it.id}`}
                      onClick={() => setReviewItem(it)}
                      className="mt-1 inline-flex items-center gap-1 text-[11px] font-bold text-[#0058CC] hover:underline">
                      Tinjau & Putuskan <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {!loading && filtered.length > PAGE_SIZE && (
          <div className="border-t border-[#EFF0F2] p-2.5">
            <PaginationBar page={curPage} pageSize={PAGE_SIZE} total={filtered.length}
              hasMore={curPage < totalPages}
              onPrev={() => setPage((p) => Math.max(1, p - 1))}
              onNext={() => setPage((p) => Math.min(totalPages, p + 1))}
              testId="approval-inbox-pager" label="persetujuan"
              exportConfig={{ columns: INBOX_CSV_COLUMNS, rows: pageRows,
                fetchAll: async () => filtered, filename: "antrean-persetujuan" }} />
          </div>
        )}
      </div>
      )}

      {reviewItem && (
        <ApprovalDecisionModal item={reviewItem} currentUser={currentUser}
          meta={KIND_META[reviewItem.kind]}
          queuePos={(() => {
            const i = filtered.findIndex((x) => x.kind === reviewItem.kind && x.id === reviewItem.id);
            return i >= 0 ? i + 1 : null;
          })()}
          queueTotal={filtered.length}
          onClose={() => setReviewItem(null)}
          onOpenFull={() => { const it = reviewItem; setReviewItem(null); handleReview(it); }}
          onDecided={(msg) => {
            /* KEPUTUSAN BERUNTUN (2026-06) — dokumen berikutnya dalam saringan yang
               sama langsung dibuka, supaya antrean habis tanpa klik ekstra. */
            const cur = reviewItem;
            const idx = filtered.findIndex((x) => x.kind === cur.kind && x.id === cur.id);
            const next = filtered.slice(idx + 1).find((x) => !(x.kind === cur.kind && x.id === cur.id))
              || filtered.slice(0, Math.max(idx, 0)).find((x) => !(x.kind === cur.kind && x.id === cur.id))
              || null;
            setReviewItem(next);
            notifySuccess(msg, next
              ? `Lanjut ke ${next.title} — dokumen berikutnya di antrean.`
              : "Antrean saringan ini habis. Kerja bagus!");
            load();
          }} />
      )}
    </div>
  );
}
