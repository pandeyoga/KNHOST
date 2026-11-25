/**
 * SoTrackerCard — tabel SO aktif di setiap meja: status kini, tahap berikutnya, pemilik tahap.
 * Baris dengan `can_act` mendapat tombol aksi; selebihnya hanya info siapa yang menindaklanjuti.
 * Selesai/batal otomatis hilang (difilter server). 5 baris per halaman, paginasi di kartu.
 *
 * Meja gelombang 1 (§5.1, R7, R18): SETIAP baris bisa dibuka (termasuk yang bukan wewenang meja) di `DeskRowDetail`.
 * Klik tetikus pada baris membuka rincian; baris BUKAN kontrol (tanpa role/tabIndex) — jalur papan ketik = tombol nomor SO.
 * Tombol aksi: aksi di tempat (`inPlaceActions`, dialog meja) langsung dijalankan; aksi pindah layar membuka rincian dulu.
 */
import { useCallback, useEffect, useState } from "react";
import { ClipboardList, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import usePagedRows from "@/hooks/usePagedRows";
import { formatCurrency } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { fmtWhen, ageTone } from "./workDeskApi";
import TableFilterBar, { useTableFilter } from "../../components/TableFilter";
import { HelpTip } from "../../components/ListPageParts";
import DeskRowDetail from "../desks/DeskRowDetail";

// Trial 22 Okt (E7) — Pelacak SO: cari + filter status + urutan.
const TRACKER_SORTS = {
  server: { label: "Bawaan" },
  idle: { label: "Paling lama diam", cmp: (a, b) => Number(b.idle_days || 0) - Number(a.idle_days || 0) },
  newest: { label: "Terbaru dibuat", cmp: (a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")) },
  value: { label: "Nilai terbesar", cmp: (a, b) => Number(b.grand_total || 0) - Number(a.grand_total || 0) },
};

/** Baris pelacak → baris meja umum untuk `DeskRowDetail` (aksi hanya bila meja ini berwenang). */
export function trackerRowToDeskRow(r) {
  return {
    ref_type: "sales_order", ref_id: r.id, number: r.number, title: r.customer_name,
    subtitle: `${r.next_step} · oleh ${r.owner_label}`, value: r.grand_total, age_days: r.idle_days, at: r.created_at,
    badge: r.status, entity_id: r.entity_id || "", sales_name: r.sales_name,
    action: r.can_act ? r.action : "", action_kind: "tracker", _tracker: r,
  };
}

const TRACKER_QUEUE = { id: "pelacak_so", title: "Pelacak SO", value_label: "Nilai", value_kind: "money" };

export default function SoTrackerCard({
  desk = "me", selectedEntity = "all", onOpen, onOpenFull, testPrefix = "desk", refreshKey = 0, showRefresh = true,
  inPlaceActions = [], currentUser,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState(null);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { desk };
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      setData((await axios.get(`${API}/desks/so-tracker`, { params })).data); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat pelacak SO.")); }
    finally { setLoading(false); }
  }, [desk, selectedEntity]);
  // `refreshKey` naik = meja induk baru saja mengubah SO (mis. Periksa & lepas) → muat ulang supaya status tidak basi.
  useEffect(() => { load(); }, [load, refreshKey]);
  const all = data?.rows || [];
  const f = useTableFilter(all, {
    text: (r) => `${r.number || ""} ${r.customer_name || ""} ${r.sales_name || ""} ${r.next_step || ""} ${r.status_label || ""}`,
    status: (r) => (r.can_act ? "aksi" : r.status_label || ""),
    statusLabel: (s) => (s === "aksi" ? "Aksi di meja ini" : s), sorts: TRACKER_SORTS,
  });
  const rows = f.shown;
  const pg = usePagedRows(rows, { pageSize: 5, testId: `${testPrefix}-so-tracker-pager` });
  const p = `${testPrefix}-so-tracker`;
  const inPlace = (row) => inPlaceActions.includes(row?._tracker?.action);
  // Tombol aksi sel: dialog meja langsung; aksi pindah layar → rincian dulu (aksinya di sana, bertanda pindah layar).
  const act = (r) => { if (inPlaceActions.includes(r.action)) onOpen?.(r); else setDetail(trackerRowToDeskRow(r)); };
  return (
    <section className="section-card self-start" data-testid={p}>
      <div className="section-head">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
          <ClipboardList size={15} className="text-kn-action" aria-hidden="true" />
          <h2>Pelacak SO aktif</h2>
          <HelpTip testId={`${p}-help`} label="Tentang Pelacak SO"
            text="SO baru muncul otomatis dan hilang setelah selesai/batal. Tombol aksi hanya muncul bila tahap berikutnya wewenang meja ini; baris lain tetap bisa dibuka untuk dilihat." />
          <span className="rounded-full bg-kn-action-soft px-2 py-0.5 text-fs-12 font-medium text-kn-action" data-testid={`${p}-count`}>{data?.count ?? 0}</span>
          <span className="rounded-full bg-kn-warning-soft px-2 py-0.5 text-fs-12 font-medium text-kn-warning-text" data-testid={`${p}-actionable`}>{data?.actionable ?? 0} aksi di meja ini</span>
        </div>
        {showRefresh && (
          <button className="icon-button" onClick={load} aria-label="Muat ulang pelacak SO" data-testid={`${p}-refresh`}>
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        )}
      </div>
      {error && <p className="px-3 py-2 text-fs-12 text-kn-danger-text" data-testid={`${p}-error`}>{error}</p>}
      {all.length > 1 && <TableFilterBar f={f} testId={p} onChange={() => pg.setPage?.(1)} placeholder="Cari no. SO, pelanggan, sales, tahap…" />}
      {/* UAT 24 Okt (audit UI tahap 2) — G2-25 · P-05: pesan memuat/kosong di LUAR wadah gulir (dulu di dalam tabel
          min-w-[760px] sehingga terpotong "Tida…" di HP 390). Tabel hanya dirender bila ada baris. */}
      {loading && !data && <p className="px-3 py-6 text-center text-fs-12 text-kn-text-2" data-testid={`${p}-loading`}>Memuat…</p>}
      {data && rows.length === 0 && <p className="px-3 py-6 text-center text-fs-12 text-kn-text-2" data-testid={`${p}-empty`}>{f.active ? "Tidak ada SO yang cocok dengan filter." : "Tidak ada SO aktif."}</p>}
      {pg.pageRows.length > 0 && (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-fs-12">
          <thead><tr data-testid={`${p}-head`} className="whitespace-nowrap border-b border-kn-divider text-left text-fs-12 font-semibold text-kn-text-2">
            <th className="px-3 py-2">SO</th><th className="px-2 py-2">Status</th><th className="px-2 py-2">Tahap berikutnya</th>
            <th className="px-2 py-2">Waktu</th><th className="px-2 py-2 text-right">Nilai</th><th className="col-sticky-end px-3 py-2 text-right">Tindak lanjut</th>
          </tr></thead>
          <tbody className="divide-y divide-kn-divider">
            {pg.pageRows.map((r) => <TrackerRow key={r.id} r={r} p={p} onDetail={() => setDetail(trackerRowToDeskRow(r))} onAction={() => act(r)} />)}
          </tbody>
        </table>
      </div>
      )}
      {rows.length > 5 && <div className="px-3 pb-2">{pg.pager}</div>}
      {detail && (
        <DeskRowDetail row={detail} queue={TRACKER_QUEUE} testPrefix={p} inPlace={inPlace} currentUser={currentUser}
          onAction={(row) => onOpen?.(row._tracker)}
          onOpenFull={onOpenFull ? (row) => onOpenFull(row._tracker) : undefined}
          onClose={() => setDetail(null)} />
      )}
    </section>
  );
}

function TrackerRow({ r, p, onDetail, onAction }) {
  const idle = ageTone(r.idle_days);
  // Klik tetikus di mana saja pada baris membuka rincian; klik pada tombol/tautan di dalamnya ditangani sendiri.
  const onClick = (e) => {
    const hit = e.target.closest?.("button, a, input, select, textarea");
    if (hit && hit !== e.currentTarget && e.currentTarget.contains(hit)) return;
    onDetail();
  };
  return (
    <tr data-testid={`${p}-row-${r.id}`} onClick={onClick} className="h-[52px] cursor-pointer hover:bg-kn-neutral-soft">
      <td className="px-3 py-1.5">
        {/* `.link-button` memaksa 12/700 — huruf 13/600 warna aksi dipasang di isi tombol (pola DeskQueueCard). */}
        <div className="flex min-w-0">
          <button type="button" data-testid={`${p}-number-${r.id}`} className="link-button -mx-1 -my-0.5 min-w-0 max-w-full"
            title={r.number} aria-haspopup="dialog" onClick={onDetail}>
            <span className="min-w-0 truncate text-left text-fs-13 font-semibold text-kn-action">{r.number}</span>
          </button>
        </div>
        <p className="max-w-[200px] truncate text-fs-13 text-kn-text">{r.customer_name}{r.sales_name ? ` · ${r.sales_name}` : ""}</p>
        {/* Audit UI 24 Okt (118/144, HP) — kolom Tahap/Nilai/Tindak lanjut ada di luar layar 390px;
            ringkasannya + tombol aksi ditampilkan di bawah nomor SO khusus layar sempit. */}
        <div className="mt-1 grid gap-1 sm:hidden" data-testid={`${p}-m-${r.id}`}>
          <p className="text-fs-12 text-kn-text-2">Berikutnya: <b className="font-semibold">{r.next_step}</b> · {formatCurrency(r.grand_total)}</p>
          {r.can_act
            ? <button type="button" className="secondary-button btn-sm w-fit" data-testid={`${p}-action-m-${r.id}`} onClick={(e) => { e.stopPropagation(); onAction(); }}>{r.action}</button>
            : <span className="text-fs-12 text-kn-text-2">Menunggu {r.owner_label}</span>}
        </div>
      </td>
      <td className="px-2 py-1.5"><span className="whitespace-nowrap rounded-full border border-kn-divider bg-kn-neutral-soft px-2 py-0.5 text-fs-12 font-medium text-kn-text" data-testid={`${p}-status-${r.id}`}>{r.status_label}</span></td>
      <td className="px-2 py-1.5"><p className="text-fs-13 text-kn-text">{r.next_step}</p><p className="text-fs-12 text-kn-text-2">oleh {r.owner_label}</p></td>
      <td className="px-2 py-1.5 text-fs-12 text-kn-text-2" data-testid={`${p}-time-${r.id}`}>
        <p>Dibuat {fmtWhen(r.created_at)}</p>
        <p>Diperbarui {fmtWhen(r.updated_at)} <span className={`ml-1 rounded-full border px-1.5 text-fs-12 font-medium ${idle.cls}`}>{idle.label}</span></p>
      </td>
      <td className="px-2 py-1.5 text-right text-fs-13 font-semibold tabular-nums text-kn-text">{formatCurrency(r.grand_total)}</td>
      {/* Cek layar MN-T2 (1024 px): tabel min 760 px + kolom Waktu dua baris = ±855 px di kartu ±762 px → kolom ini
          terpotong di tepi gulir; kini lekat di kanan supaya aksi selalu terlihat. */}
      <td className="col-sticky-end px-3 py-1.5 text-right">
        {r.can_act
          ? <button type="button" className="secondary-button btn-sm" data-testid={`${p}-action-${r.id}`} onClick={(e) => { e.stopPropagation(); onAction(); }}>{r.action}</button>
          : <span className="text-fs-12 text-kn-text-2" data-testid={`${p}-info-${r.id}`}>Menunggu {r.owner_label}</span>}
      </td>
    </tr>
  );
}
