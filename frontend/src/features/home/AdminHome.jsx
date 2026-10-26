import { apiErrorText } from "../../utils/apiError";
import { useEffect, useState, useCallback } from "react";
import {
  Banknote, TrendingUp, ArrowUpRight, Receipt, AlertTriangle,
  Clock, PackageX, Award, RefreshCw, Trophy,
} from "lucide-react";
import axios, { API } from "../../services/apiClient";
import PeriodUnlockCard from "../../components/PeriodUnlockCard";
import OpeningCostBanner from "../../components/OpeningCostBanner";
import ErrorNotice from "../../components/ErrorNotice";
import { selectWaitingBoards } from "../../config/waitingBoards";
import SeeAllModal, { SeeAllFooter } from "../../components/SeeAllModal";
import { useAppNav } from "../../context/AppNavContext";
import HomeWaitingBoards from "./HomeWaitingBoards";
import { queueLink } from "../approvals/inboxTabs";

const fmt = new Intl.NumberFormat("id-ID");
const fmtCur = (v) => `Rp ${fmt.format(Math.round(v || 0))}`;

function KPICard({ icon: Icon, label, value, sub, color = "#007AFF", loading, onClick, testId }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag data-testid={testId || `kpi-${label.toLowerCase().replace(/\s+/g, "-")}`}
      onClick={onClick} type={onClick ? "button" : undefined}
      className={`min-w-0 rounded-xl border border-[#EFF0F2] bg-white p-3 sm:p-4 flex flex-col gap-1.5 sm:gap-2 text-left${
        onClick ? " hover:border-[#C9D6E8] hover:shadow-sm transition" : ""}`}>
      <div className="flex min-w-0 items-center gap-2">
        <div className="shrink-0 rounded-lg p-1.5" style={{ background: `${color}18` }}>
          <Icon size={16} style={{ color }} />
        </div>
        <span className="min-w-0 text-[11.5px] sm:text-[12px] font-semibold leading-tight text-[#6B6B73]">{label}</span>
      </div>
      {loading ? (
        <div className="h-7 bg-[#F5F5F7] rounded animate-pulse" />
      ) : (
        // G1-43 — di HP angka Rp dulu patah ("Rp / 4.292.925") dan menyentuh tepi. Fase 3 · P3 (L-04): 2 kolom di
        // 390 px → angka sedikit lebih kecil di HP agar tetap satu baris.
        <p className="text-[15px] min-[400px]:text-lg md:text-2xl font-bold text-[#1C1C1E] tabular-nums whitespace-nowrap">{value}</p>
      )}
      {/* L-04 — keterangan sumber tetap ada (K-01), dipotong 3 baris di HP; teks lengkap di tooltip. */}
      {sub && <p className="text-[11px] text-[#6B6B73] line-clamp-3 sm:line-clamp-none" title={typeof sub === "string" ? sub : undefined}>{sub}</p>}
    </Tag>
  );
}

export default function AdminHome({ token, selectedEntity = "all", onNavigate }) {
  const nav = useAppNav();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [showAllStock, setShowAllStock] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
      const res = await axios.get(`${API}/home/admin`, { headers, params });
      setData(res.data);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat Control Tower. Coba lagi."));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, selectedEntity]);

  useEffect(() => { load(); }, [load]);

  const sales = data?.sales || {};
  const ar = data?.ar || {};
  // K-04 (26 Okt) — KPI "Stok Rendah" = definisi tunggal (`low_stock`); papan "Stok Perlu Reorder" = saran reorder
  // (di bawah ROP, `reorder`). Respons lama tanpa `reorder` → papan memakai `low_stock` lama (isi = saran reorder).
  const lowStock = data?.low_stock || {};
  const reorderBoard = data?.reorder || (lowStock.label === undefined ? lowStock : {});
  const board = data?.leaderboard_top || [];
  const overdue = data?.top_overdue || [];
  // Papan antrean mahal (PO custom · kontrabon bersengketa · retur antar-PT).
  // Daftar & urutannya ditentukan backend (`HOME_BOARD_KEYS`); pemilihannya SATU
  // fungsi bersama dengan Dasbor Manajer (`selectWaitingBoards`) supaya keadaan
  // "tidak bisa dibaca" tidak bisa hilang di salah satu layar saja (regresi B5).
  // B5 (2026-08-25) — papan hanya boleh menyimpulkan "tidak ada yang menunggu" bila
  // datanya BENAR-BENAR terbaca. Sebelum ini `load()` yang gagal meninggalkan
  // `data === null`, jadi papan kosong dan menampilkan pesan hijau
  // "Tidak ada PO custom yang menunggu keputusan 🎉": kegagalan jaringan tampil
  // sebagai KABAR BAIK. `ErrorNotice` di atas memang muncul, tetapi pesan hijau di
  // papan tetap menyesatkan — kelas "hijau tapi hampa".
  // `error` ikut dihitung (bukan hanya `data === null`): saat pemuatan ulang GAGAL,
  // `data` masih memegang isi lama, jadi papan akan menampilkan angka BASI dengan
  // percaya diri. Lebih jujur mengatakan "tidak bisa dibaca" daripada menyajikan
  // angka yang sudah tidak diketahui benar-tidaknya.
  const boardsUnreadable = !loading && (!data || !!error);
  const boards = selectWaitingBoards(data, boardsUnreadable);
  // C2 — dalam mode gabungan pemilik tidak bisa membedakan PO custom KSC dari Kanda
  // kalau barisnya tidak menyebut badan usaha. `<EntityBadge/>` dipakai (bukan
  // `entity_id` mentah) karena INV-UI-02 melarang id teknis `ent_*` tampil ke layar.
  const showEntity = !selectedEntity || selectedEntity === "all";
  // Jenis persetujuan terbanyak → dipakai teks bantu & tujuan klik KPI.
  const approvalItems = (data?.approvals?.items || []);
  // Fase 3 · P3 (D-06) — chip jenis membuka Pusat Persetujuan di tab jenisnya (bila daftarnya ada di sana).
  const openQueue = (q) => {
    const link = queueLink(q, nav.canOpen);
    if (link.preset) nav.go(link.view, { preset: link.preset });
    else if (onNavigate && link.view) onNavigate(link.view);
  };
  const topApproval = approvalItems.slice().sort((a, b) => b.count - a.count)[0] || null;
  const approvalSub = boardsUnreadable
    // Kegagalan pemuatan tidak boleh berbunyi kabar baik ("Tidak ada yang menunggu").
    ? "Tidak bisa dibaca — coba muat ulang"
    : (data?.approvals_pending || 0) === 0
      ? "Tidak ada yang menunggu"
      : (topApproval
        ? `Terbanyak: ${topApproval.label.replace(" menunggu ACC", "")} (${topApproval.count}) · klik untuk buka`
        : "Perlu ditindak");

  // Baris stok — dipakai kartu (cuplikan 6) dan pop-up "Lihat semua".
  const renderStockRow = (it, idx) => (
    <div key={it.product_id || idx} className="grid grid-cols-[1fr_90px_90px] gap-2 text-[12px] py-1.5 border-b border-[#F5F5F7] last:border-0 items-center">
      <div className="min-w-0"><p className="font-semibold truncate">{it.product_name || it.name}</p>
        <p className="text-[10px] text-[#8E8E93]">{it.sku || ""}</p></div>
      <span className="text-right tabular-nums text-[#6B6B73]">Stok fisik {fmt.format(it.on_hand ?? it.available_qty ?? 0)}</span>
      <span className="text-right tabular-nums font-bold text-[#FF6B00]">ROP {fmt.format(it.reorder_point ?? 0)}</span>
    </div>
  );

  return (
    <section data-testid="admin-home" className="section-card">
      <div className="section-head">
        <p className="text-[12px] text-[#6B6B73] min-w-0 truncate">Pantauan penjualan, piutang & stok — real-time</p>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={load} className="secondary-button" data-testid="admin-home-refresh">
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Muat ulang
          </button>
        </div>
      </div>

      <div className="section-body">
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="admin-home-error" />

        {/* Fase 3 · P3 (L-04) — 2 kolom juga di HP 390 px (dulu 1 kolom: 8 kartu = 2+ layar gulir). */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3" data-testid="admin-home-kpis">
          <KPICard icon={Banknote} label="Penjualan Hari Ini" value={fmtCur(sales.today)} sub={`${sales.today_orders || 0} pesanan`} color="#007AFF" loading={loading} />
          <KPICard icon={TrendingUp} label="Penjualan Bulan Ini" value={fmtCur(sales.mtd)} sub="Bulan berjalan" color="#34C759" loading={loading} />
          <KPICard icon={ArrowUpRight} label="Tertagih Bulan Ini" value={fmtCur(sales.collected_mtd)} sub="Kas masuk" color="#30D158" loading={loading} />
          {/* Keputusan pemilik K-01 (26 Okt): kedua KPI piutang = SEMUA pelanggan, sumber sub-buku (dokumen belum
              lunas) — angka & definisi lewat tempo SAMA dengan layar Piutang. Dulu (G1-13) hanya pelanggan ber-sales aktif.
              Label sumber wajib tampil di kartu. */}
          <KPICard icon={Receipt} label="Belum Lunas" value={fmtCur(ar.outstanding)}
            sub={`Semua pelanggan · sub-buku (dokumen belum lunas) · buku piutang ${fmtCur(ar.ar_ledger)} · eksposur ${fmtCur(ar.exposure)}`}
            color="#5856D6" loading={loading} testId="kpi-belum-lunas" onClick={onNavigate ? () => onNavigate("ar-aging") : undefined} />
          <KPICard icon={AlertTriangle} label="Piutang Lewat Tempo" value={fmtCur(ar.overdue)}
            sub={(ar.overdue_customers || 0) > 0
              ? `Semua pelanggan · ${ar.overdue_customers} pelanggan · sama dengan layar Piutang`
              : "Semua pelanggan · sama dengan layar Piutang"}
            color="#FF3B30" loading={loading} testId="kpi-piutang-lewat-tempo" onClick={onNavigate ? () => onNavigate("ar-aging") : undefined} />
          {/* AUDIT PERAN 2026-08-15 — KPI ini dulu SELALU 0 (menghitung koleksi
              `approval_requests` yang tak pernah diisi siapa pun), padahal 16 dokumen
              memang menunggu keputusan. Sekarang angkanya = antrean nyata, `sub`
              menyebut jenis terbanyak, dan kartunya BISA DIKLIK ke tempat kerjanya —
              angka tanpa jalan ke pekerjaannya hanya membuat orang menebak. */}
          <KPICard icon={Clock} label="Persetujuan Menunggu"
            value={boardsUnreadable ? "—" : (data?.approvals_pending ?? "—")}
            sub={approvalSub}
            color="#FF9500" loading={loading}
            testId="kpi-persetujuan-menunggu"
            onClick={() => (topApproval ? openQueue(topApproval) : onNavigate && onNavigate("approval-inbox"))} />
          <KPICard icon={PackageX} label="Stok Rendah" value={lowStock.count ?? "—"}
            sub={lowStock.threshold ? `produk · tersedia < ${lowStock.threshold} (papan stok) · per badan usaha` : "Perlu reorder"}
            color="#FF6B00" loading={loading} testId="kpi-stok-rendah" onClick={onNavigate ? () => onNavigate("operations") : undefined} />
          <KPICard icon={Award} label="Insentif Sales" value={fmtCur(data?.incentive_payout)} sub="Estimasi bulan ini" color="#AF52DE" loading={loading} />
        </div>

        {/* FASE G-5 — ringkasan periode yang sedang dibuka (unlock) + sisa waktu */}
        <PeriodUnlockCard onNavigate={onNavigate} />
        <OpeningCostBanner onNavigate={onNavigate} selectedEntity={selectedEntity} />

        {/* AUDIT PERAN 2026-08-15 — RINCIAN antrean persetujuan (angka + jalan ke layarnya).
            Fase 3 · P3 (D-06) — kartu RINGKAS: total + chip per jenis yang membuka Pusat Persetujuan di tab jenisnya
            (antrean yang daftarnya bukan di inbox → layar kerjanya). Daftar "paling lama menunggu" tidak lagi
            digandakan di sini — ada di Pusat Persetujuan ("Menunggu di layar lain") dengan sumber yang sama. */}
        {!boardsUnreadable && approvalItems.length > 0 && (
          <div className="mt-4 rounded-xl border border-[#FFE2BE] bg-[#FFFBF5] p-3 sm:p-4"
            data-testid="admin-home-approval-backlog">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <Clock size={15} className="text-[#FF9500]" />
                <h3 className="text-[14px] font-bold">Antrean Persetujuan ({data?.approvals_pending || 0})</h3>
              </div>
              <button type="button" className="text-[12px] font-semibold text-[#007AFF]"
                onClick={() => onNavigate && onNavigate("approval-inbox")}
                data-testid="admin-home-goto-approval-inbox">Pusat Persetujuan →</button>
            </div>
            <div className="flex flex-wrap gap-1.5" data-testid="admin-home-approval-chips">
              {approvalItems.map((a) => (
                <button key={a.key} type="button"
                  data-testid={`admin-home-approval-${a.key}`}
                  onClick={() => openQueue(a)} title={`Buka ${a.label}`}
                  className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-[#F0E3D2] bg-white px-2.5 py-1 text-left text-[11.5px] text-[#3A3A3C] transition hover:border-[#FFB25A]">
                  <span className="truncate">{a.label.replace(" menunggu ACC", "")}</span>
                  <span className="font-bold tabular-nums text-[#B26A00]">{a.count}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* PAPAN ANTREAN MAHAL (2026-08-24 · digeneralisasi 2026-06) — dokumen yang
            salah-tundanya PALING MAHAL, masing-masing SEMUA yang menunggu + UMUR TUNGGU-nya, satu sumber dengan
            antrean di atas (`approval_backlog_service`). Fase 3 · P3 (D-07/D-28): PO Custom & Barang ditahan QC =
            papan TAUTAN (baris membuka dokumennya; keputusan hanya di layar utama). */}
        <HomeWaitingBoards boards={boards} loading={loading} unreadable={boardsUnreadable}
          onRetry={load} onActed={load} onNavigate={onNavigate}
          entityId={selectedEntity} showEntity={showEntity} className="mt-4 grid gap-3"
          ids={(b) => (b.key === "special_order"
            ? { testIdBase: "admin-home-special-orders", rowTestIdBase: "admin-home-special-order", gotoTestId: "admin-home-goto-special-orders" }
            : { testIdBase: `admin-home-board-${b.key}`, rowTestIdBase: `admin-home-board-${b.key}-row` })} />

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {/* Leaderboard */}
          <div className="rounded-xl border border-[#EFF0F2] bg-white p-4" data-testid="admin-home-leaderboard">
            <div className="flex items-center gap-2 mb-3"><Trophy size={15} className="text-[#FF9500]" /><h3 className="text-[14px] font-bold">Sales Teratas (bulan ini)</h3></div>
            {board.length > 0 ? (
              <div className="grid gap-1.5">
                {board.map((r, idx) => (
                  <div key={r.sales_id || idx} className="flex items-center gap-2 py-1.5 border-b border-[#F5F5F7] last:border-0">
                    <span className="text-[11px] font-bold text-[#8E8E93] w-5">{idx + 1}</span>
                    <div className="flex-1 min-w-0"><p className="text-[12px] font-semibold truncate">{r.sales_name}</p>
                      <p className="text-[10.5px] text-[#8E8E93]">{r.orders_count || 0} order • {Math.round((r.collection_rate || 0) * 1000) / 10}% tertagih</p></div>
                    <span className="text-[12px] font-bold text-[#007AFF] tabular-nums">{fmtCur(r.total_sales)}</span>
                  </div>
                ))}
              </div>
            ) : <div className="h-20 flex items-center justify-center text-[13px] text-[#8E8E93]">Belum ada data penjualan</div>}
          </div>

          {/* Top overdue */}
          <div className="rounded-xl border border-[#EFF0F2] bg-white p-4" data-testid="admin-home-overdue">
            <div className="flex items-center gap-2 mb-1"><AlertTriangle size={15} className="text-[#FF3B30]" /><h3 className="text-[14px] font-bold">Lewat Tempo per Sales</h3></div>
            {/* K-01 — rincian dari laporan Piutang yang sama (semua pelanggan; pelanggan tanpa sales = baris "Tanpa sales"). */}
            <p className="mb-2 text-[10.5px] text-[#8E8E93]" data-testid="admin-home-overdue-source">Semua pelanggan · sub-buku, sama dengan layar Piutang</p>
            {overdue.length > 0 && overdue.some((o) => o.overdue_amount > 0) ? (
              <div className="grid gap-1.5">
                {overdue.filter((o) => o.overdue_amount > 0).map((o, idx) => (
                  <button type="button" key={o.sales_id || `none-${idx}`} data-testid={`admin-home-overdue-row-${o.sales_id || "none"}`}
                    onClick={() => onNavigate && onNavigate("ar-aging")}
                    className="flex w-full items-center gap-2 py-1.5 border-b border-[#F5F5F7] last:border-0 text-left">
                    <div className="flex-1 min-w-0"><p className={`text-[12px] font-semibold truncate ${o.has_sales === false ? "italic text-[#6B6B73]" : ""}`}>{o.sales_name}</p>
                      <p className="text-[10.5px] text-[#8E8E93]">Belum lunas {fmtCur(o.ar_outstanding)}{o.overdue_customers ? ` · ${o.overdue_customers} pelanggan telat` : ""}</p></div>
                    <span className="text-[12px] font-bold text-red-600 tabular-nums">{fmtCur(o.overdue_amount)}</span>
                  </button>
                ))}
              </div>
            ) : <div className="h-20 flex items-center justify-center text-[13px] text-[#8E8E93]">Tidak ada tagihan lewat tempo 🎉</div>}
          </div>
        </div>

        {/* Low stock */}
        <div className="mt-4 rounded-xl border border-[#EFF0F2] bg-white p-4" data-testid="admin-home-lowstock">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><PackageX size={15} className="text-[#FF6B00]" /><h3 className="text-[14px] font-bold">Stok Perlu Reorder</h3></div>
            <button onClick={() => onNavigate && onNavigate("reorder")} className="text-[12px] font-semibold text-[#007AFF]" data-testid="admin-home-goto-reorder">Lihat semua →</button>
          </div>
          {(reorderBoard.items || []).length > 0 ? (
            <>
              {/* UI/UX 2026-06 — dulu seluruh baris digulung dalam kotak ber-scroll;
                  sekarang cuplikan 6 teratas + pop-up "Lihat semua" ber-pencarian. */}
              <div className="grid gap-1">
                {(reorderBoard.items || []).slice(0, 6).map((it, idx) => renderStockRow(it, idx))}
              </div>
              <SeeAllFooter shown={Math.min(6, (reorderBoard.items || []).length)}
                total={(reorderBoard.items || []).length} label="produk" accent="#FF6B00"
                onClick={() => setShowAllStock(true)} testId="admin-home-lowstock-see-all" />
            </>
          ) : <div className="h-20 flex items-center justify-center text-[13px] text-[#8E8E93]">Semua stok di atas titik reorder</div>}
          <SeeAllModal open={showAllStock} onClose={() => setShowAllStock(false)}
            title="Stok Perlu Reorder" subtitle="Produk di bawah titik reorder (ROP)"
            icon={PackageX} accent="#FF6B00" rows={reorderBoard.items || []}
            rowText={(it) => `${it.product_name || it.name || ""} ${it.sku || ""}`}
            renderRow={(it, idx) => renderStockRow(it, idx)}
            listClassName="px-4" searchPlaceholder="Cari produk atau SKU…"
            testId="admin-home-lowstock-modal" />
        </div>
      </div>
    </section>
  );
}
