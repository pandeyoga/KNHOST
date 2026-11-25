/**
 * DeskQueueCard — satu ANTREAN meja kerja (Meja Admin Sales · Meja Keuangan · Meja Gudang · Meja Sample · Meja MD ·
 * Meja Saya).
 *
 * Rancang ulang meja gelombang 1 (spek 2026-11-25 §5.2, §5.5; pemilik 25 Nov):
 *  1. Ukuran TETAP di desktop (≥ 640 px): `DESK_CARD_CLASS` sama untuk kartu berisi, < 5 baris, kosong ("bersih" di
 *     tengah), memuat (kerangka) — kartu berdampingan tidak lagi naik-turun. Di HP tinggi mengikuti isi.
 *  2. Kepala satu baris: ikon · judul · jumlah · "tertua n hari" · ? (penjelasan antrean) · nilai (bukan untuk antrean
 *     jumlah dokumen). Bilah cari/saring/urut hanya bila ada baris. Kaki satu baris: pager · catatan baris terpotong ·
 *     "Memuat ulang…".
 *  3. Baris RINGKAS (nomor · pihak | status · PT · umur | nilai · aksi) — keterangan & waktu masuk pindah ke pop-up
 *     `DeskRowDetail`. Seluruh baris bisa diklik/Enter → pop-up; tombol aksi: aksi di tempat (`inPlace`) langsung
 *     dijalankan, aksi pindah layar membuka pop-up dulu (aksinya di sana, bertanda ikon pindah layar).
 *  4. Cari / saring status / urutan / halaman per kartu tersimpan di sessionStorage (`stateKey`, lihat deskSession).
 * `defaultOpen` diterima demi pemanggil lama, tetapi tidak berpengaruh (kartu selalu terbuka, pemilik 16 Nov).
 */
import { useEffect, useRef, useState } from "react";
import { Inbox } from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { formatUnitTotals } from "../../utils/qtyByUnit";
import { HelpTip } from "../../components/ListPageParts";
import { useEntityScope } from "../../context/EntityScopeContext";
import { entityShortById } from "../../utils/entityLabel";
import usePagedRows from "@/hooks/usePagedRows";
import TableFilterBar, { useTableFilter } from "../../components/TableFilter";
import DeskBadge from "../desks/DeskBadge";
import DeskRowDetail from "../desks/DeskRowDetail";
import { cardStateKey, readDeskState, writeDeskState } from "../desks/deskSession";
import { ageText, ageTone, badgeLabel, queueMeta } from "./workDeskApi";

export { DeskBadge };

/** Baris per halaman kartu (ukuran tampilan, bukan aturan bisnis). */
export const PAGE_ROWS = 5;

/** Tinggi satu baris antrean di desktop (56 px). */
export const DESK_ROW_CLASS = "sm:h-14";

/**
 * Tinggi tetap kartu di desktop — dihitung dari tinggi NYATA bagian-bagiannya (R10), satu-satunya tempat angka ini:
 *   bingkai `section-card` (garis atas + bawah)                       1 + 1 =   2
 *   kepala `h-11`                                                             44
 *   garis + bilah saring `TableFilterBar` (`py-2` 16 + kontrol `h-8` 32)  1 + 48 =  49
 *   garis + 5 baris × `sm:h-14` 56 (garis pemisah di dalam tinggi baris)  1 + 280 = 281
 *   kaki `h-9` (garisnya di dalam tinggi kaki)                                36
 *                                                                     jumlah = 412 px
 * Tailwind memerlukan nama kelas utuh di sumber, jadi angkanya tertulis langsung — ubah bersama bila satu bagian berubah.
 */
export const DESK_CARD_CLASS = "flex flex-col sm:h-[412px]";

/** `inPlace` dari daftar jenis aksi yang dikerjakan di meja tanpa pindah layar. */
export const inPlaceOf = (kinds) => (row) => kinds.includes(row?.action_kind);

// Trial 22 Okt (E7) — urutan antrean: bawaan server (paling mendesak/tertua dulu), terbaru, nilai terbesar.
const SORT_SERVER = { label: "Tertua dulu" };
const SORT_NEWEST = { label: "Terbaru dulu", cmp: (a, b) => Number(a.age_days || 0) - Number(b.age_days || 0) };
const SORT_VALUE = { label: "Nilai terbesar", cmp: (a, b) => Number(b.value || 0) - Number(a.value || 0) };
const SORTS_MONEY = { server: SORT_SERVER, newest: SORT_NEWEST, value: SORT_VALUE };
const SORTS_COUNT = { server: SORT_SERVER, newest: SORT_NEWEST };   // jumlah dokumen: "nilai" tidak bermakna

// Pager baku (`KNPager` → `PaginationBar`) diringkas di kaki kartu: tanpa bingkai/padding, tanpa teks rentang
// ("Menampilkan 1–5 dari 12" — halaman sudah terbaca di "Hal x / y"), tidak membungkus.
// Di HP tombol halaman pertama/terakhir disembunyikan supaya pager muat selebar layar.
const FOOT_PAGER = "[&_.kn-pager-wrap]:shrink-0 [&_.kn-pager]:flex-nowrap [&_.kn-pager]:gap-1 [&_.kn-pager]:border-0 "
  + "[&_.kn-pager]:bg-transparent [&_.kn-pager]:p-0 [&_.kn-pager>span:first-child]:hidden "
  + "max-sm:[&_[data-testid$=-first]]:hidden max-sm:[&_[data-testid$=-last]]:hidden";

function rowValueText(row, kind) {
  if (kind === "count") return "";
  if (kind === "qty") return `${formatQty(row.value)} ${row.unit || ""}`.trim();
  return formatCurrency(Number(row.value) || 0);
}

/** Warna teks umur: lewat jatuh tempo / ≥ 7 hari merah, ≥ 3 hari jingga, selain itu abu. */
function ageClass(row) {
  const d = Number(row?.age_days || 0);
  if (row?.age_kind === "overdue" || d >= 7) return "text-kn-danger-text";
  if (d >= 3) return "text-kn-warning-text";
  return "text-kn-text-2";
}

/** Kolom baris ≥ 640 px: dokumen · status/PT/umur · nilai+aksi (dipasang di daftar; baris = subgrid). */
const ROW_COLS = "sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto] sm:gap-x-3";

const hasAge = (row) => (row.age_days !== undefined && row.age_days !== null && row.age_days !== "") || row.age_kind === "overdue";

/** Lima bilah kerangka setinggi baris. */
function SkeletonRows({ testId }) {
  return (
    <div data-testid={testId} aria-busy="true" className="divide-y divide-kn-divider">
      {Array.from({ length: PAGE_ROWS }, (_, i) => (
        <div key={i} className={`${DESK_ROW_CLASS} flex h-14 items-center px-3`}>
          <div className="h-4 w-full animate-pulse rounded bg-kn-neutral-soft" />
        </div>
      ))}
      <span className="sr-only">Memuat antrean…</span>
    </div>
  );
}

/** Kartu kerangka (memuat awal meja) — ukuran sama dengan kartu antrean. */
export function DeskQueueCardSkeleton({ testPrefix = "desk", index = 0 }) {
  return (
    <section data-testid={`${testPrefix}-skeleton-${index}`} aria-busy="true" className={`section-card ${DESK_CARD_CLASS}`}>
      <div className="flex h-11 shrink-0 items-center gap-2 px-3">
        <div className="h-7 w-7 shrink-0 animate-pulse rounded-lg bg-kn-neutral-soft" />
        <div className="h-4 w-2/5 animate-pulse rounded bg-kn-neutral-soft" />
      </div>
      <div className="min-h-0 flex-1 overflow-hidden border-t border-kn-divider"><SkeletonRows /></div>
      <div className="h-9 shrink-0 border-t border-kn-divider" />
    </section>
  );
}

export default function DeskQueueCard({
  queue, onAction, busyRef = "", testPrefix = "desk", rowTestPrefix, loading = false,
  stateKey = "", inPlace = () => false, onOpenFull,
}) {
  const p = testPrefix;
  const rp = rowTestPrefix || testPrefix;
  const id = queue?.id;
  const meta = queueMeta(id);
  const Icon = meta.icon;
  const kind = queue?.value_kind;
  const isCount = kind === "count";
  const rows = Array.isArray(queue?.rows) ? queue.rows : [];
  const count = Number(queue?.count ?? rows.length) || 0;
  const { selectedEntity, entities } = useEntityScope();
  const allPt = selectedEntity === "all";

  // Status tersimpan kartu ini (cari/saring/urut dipakai sebagai nilai awal; halaman dipulihkan saat baris cukup).
  const key = stateKey ? cardStateKey(stateKey) : "";
  const [saved] = useState(() => (key ? readDeskState(key) : {}));
  const f = useTableFilter(rows, {
    text: (r) => `${r.number || ""} ${r.title || ""} ${r.subtitle || ""} ${badgeLabel(r.badge || "")}`,
    status: (r) => r.badge || "", statusLabel: badgeLabel, sorts: isCount ? SORTS_COUNT : SORTS_MONEY, initial: saved,
  });
  const shownRows = f.shown;
  const pg = usePagedRows(shownRows, { pageSize: PAGE_ROWS, testId: `${p}-pager-${id}` });
  const [detail, setDetail] = useState(null);

  const waitingRows = loading && rows.length === 0;     // memuat dan belum ada baris → kerangka
  const refreshing = loading && rows.length > 0;
  // Saringan status tersimpan yang tidak ada lagi di baris → dilepas (dropdown tersembunyi bila status tinggal satu).
  const staleSt = Boolean(f.st) && rows.length > 0 && !f.statuses.some((s) => s.key === f.st);
  const noMatch = rows.length > 0 && shownRows.length === 0;
  const savedPage = Math.floor(Number(saved.page) || 0);
  const pendingPage = useRef(savedPage > 1 ? savedPage : 0);   // halaman yang menunggu baris cukup untuk dipulihkan

  // Urutan efek penting: penulisan halaman diperiksa SEBELUM pemulihan agar halaman 1 sementara tidak menimpa simpanan.
  useEffect(() => {
    if (key) writeDeskState(key, { q: f.q, st: f.st, sort: f.sort });
  }, [key, f.q, f.st, f.sort]);
  useEffect(() => {
    if (!key || pendingPage.current || waitingRows) return;   // ditahan sampai halaman tersimpan dipulihkan
    writeDeskState(key, { page: pg.page });
  }, [key, pg.page, waitingRows]);
  useEffect(() => {
    if (staleSt) f.setSt("");
  }, [staleSt]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (waitingRows) {
      // Daftar dikosongkan selama memuat: `usePagedRows` kembali ke halaman 1 — ingat halaman ini untuk dipulihkan.
      if (pg.page > 1 && !pendingPage.current) pendingPage.current = pg.page;
      return;
    }
    const want = pendingPage.current;
    if (!want || staleSt) return;
    if (shownRows.length > (want - 1) * PAGE_ROWS) {
      pendingPage.current = 0;
      pg.setPage(want);
    } else if (!loading && rows.length > 0) {
      pendingPage.current = 0;                               // baris sudah tiba tetapi tidak sampai halaman itu
      if (key) writeDeskState(key, { page: pg.page });
    }
  }, [waitingRows, staleSt, shownRows.length, rows.length, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  const onFilterChange = () => { pendingPage.current = 0; pg.setPage(1); };
  const runAction = (row) => {
    if (inPlace(row)) onAction?.(row, queue);
    else setDetail(row);                                     // aksi pindah layar dijalankan dari dalam pop-up
  };

  // Ringkasan: qty → angka PER SATUAN (yard dan kg tidak dijumlahkan — kelas F-04); selain itu rupiah. Antrean jumlah
  // dokumen tidak menulis nilai (jumlahnya sudah di lencana).
  const unitTotals = kind === "qty"
    ? rows.reduce((m, r) => { const u = r.unit || ""; m[u] = (m[u] || 0) + (Number(r.value) || 0); return m; }, {})
    : null;
  const totalText = kind === "qty"
    ? (rows.length ? formatUnitTotals(unitTotals, queue?.total_value) : `${formatQty(queue?.total_value)}`)
    : formatCurrency(Number(queue?.total_value) || 0);
  const oldest = ageTone(queue?.oldest_age_days);
  const truncated = count > rows.length;

  return (
    <section data-testid={`${p}-queue-${id}`} className={`section-card ${DESK_CARD_CLASS} !overflow-visible`}>
      {/* Desktop: satu baris setinggi tetap. HP (< 640 px): boleh turun baris supaya judul tidak terjepit habis. */}
      <header className="flex min-h-11 shrink-0 flex-wrap items-center gap-x-2 gap-y-1 px-3 py-1.5 sm:h-11 sm:flex-nowrap sm:py-0">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg" style={{ background: meta.bg }}>
          <Icon size={15} style={{ color: meta.tone }} aria-hidden="true" />
        </span>
        <h3 className="min-w-0 truncate text-fs-14 font-semibold text-kn-text" title={queue?.label}>{queue?.label}</h3>
        <span data-testid={`${p}-count-${id}`} className="shrink-0 rounded-full px-2 py-0.5 text-fs-12 font-medium tabular-nums"
          style={{ background: meta.bg, color: meta.tone }}>
          {count}
        </span>
        {count > 0 && (
          <span data-testid={`${p}-oldest-${id}`} title="Umur baris tertua di antrean ini"
            className={`shrink-0 whitespace-nowrap rounded-full border px-2 py-0.5 text-fs-12 font-medium ${oldest.cls}`}>
            tertua {oldest.label}
          </span>
        )}
        {queue?.hint && (
          <span className="shrink-0"><HelpTip text={queue.hint} testId={`${p}-hint-${id}`} label={`Tentang antrean ${queue?.label || ""}`} /></span>
        )}
        {!isCount && (
          <span data-testid={`${p}-total-${id}`} title={queue?.value_label || "Nilai"}
            className="ml-auto max-w-[45%] shrink-0 truncate text-right text-fs-13 font-semibold tabular-nums text-kn-text">
            {totalText}
          </span>
        )}
      </header>

      {rows.length > 0 && (
        <div className="shrink-0 border-t border-kn-divider">
          <TableFilterBar compact f={f} testId={`${p}-q-${id}`} searchTestId={`${p}-search-${id}`}
            onChange={onFilterChange} placeholder="Cari nomor / pihak / keterangan…" />
        </div>
      )}

      <div data-testid={`${p}-list-${id}`} className="min-h-0 flex-1 overflow-hidden border-t border-kn-divider">
        {waitingRows ? (
          <SkeletonRows testId={`${p}-loading-${id}`} />
        ) : rows.length === 0 ? (
          <div data-testid={`${p}-empty-${id}`}
            className="flex h-full flex-col items-center justify-center gap-1.5 px-3 py-7 text-center text-fs-12 text-kn-text-2">
            <Inbox size={20} className="text-kn-neutral" aria-hidden="true" />
            Antrean ini bersih — tidak ada yang perlu ditindak.
          </div>
        ) : noMatch ? (
          <p data-testid={`${p}-search-empty-${id}`}
            className="flex h-full items-center justify-center px-3 py-7 text-center text-fs-12 text-kn-text-2">
            Tidak ada baris yang cocok.
          </p>
        ) : (
          // Kolom baris sejajar antar-baris: daftar = grid 3 kolom, tiap baris memakai subgrid (lebar kolom aksi = terlebar).
          <div className={`divide-y divide-kn-divider sm:grid ${ROW_COLS}`}>
            {pg.pageRows.map((row, i) => (
              <QueueRow key={`${row.ref_type}-${row.ref_id}-${row.number || i}`} row={row} kind={kind} testPrefix={rp}
                busy={Boolean(busyRef) && busyRef === row.ref_id} label={row.action || queue?.action_label || ""}
                pt={allPt && row.entity_id ? entityShortById(entities, row.entity_id, "") : ""}
                onOpen={() => setDetail(row)} onAction={() => runAction(row)} />
            ))}
          </div>
        )}
      </div>

      <footer data-testid={`${p}-foot-${id}`}
        className={`flex min-h-9 shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-t border-kn-divider px-3 py-1 sm:h-9 sm:flex-nowrap sm:py-0 ${FOOT_PAGER}`}>
        {pg.pager}
        {/* Cek UI UAT v3 — antrean sangat panjang: server mengirim baris tertua dulu (maks. 200). */}
        {truncated && (
          <span data-testid={`${p}-truncated-${id}`} className="min-w-0 flex-1 truncate text-fs-12 text-kn-warning-text"
            title={`Kartu ini memuat ${rows.length} baris tertua dari ${count}. Selesaikan yang tertua dulu, atau buka layar daftarnya untuk mencari dokumen tertentu.`}>
            {`${rows.length} tertua dari ${count} ditampilkan`}
          </span>
        )}
        {/* Saat dimuat ulang angka lama masih terpampang — penanda ini mencegah menindak baris yang sudah berpindah. */}
        {refreshing && (
          <span data-testid={`${p}-refreshing-${id}`} role="status"
            className="ml-auto min-w-0 truncate whitespace-nowrap text-fs-12 text-kn-text-2">
            Memuat ulang…
          </span>
        )}
      </footer>

      {detail && (
        <DeskRowDetail row={detail} queue={queue} testPrefix={p} inPlace={inPlace} onAction={onAction}
          onOpenFull={onOpenFull} onClose={() => setDetail(null)} />
      )}
    </section>
  );
}

/**
 * Satu baris ringkas: nomor · pihak | status · PT · umur | nilai · aksi (kolom di ≥ 640 px; bertumpuk di HP).
 * Klik TETIKUS di mana saja pada baris membuka rincian (klik pada tombol/tautan/isian di dalamnya diabaikan). Baris
 * sendiri BUKAN kontrol (tanpa role/tabIndex — kontrol bersarang di dalam role=button melanggar ARIA, R18): jalur papan
 * ketik = tombol nomor dokumen (fokus → Enter) yang membuka rincian yang sama.
 */
function QueueRow({ row, kind, busy, label, pt, testPrefix, onOpen, onAction }) {
  const rk = row.row_key || row.ref_id;   // satu pelanggan bisa punya beberapa baris (per SO) — testid tetap unik
  const tp = testPrefix;
  const onClick = (e) => {
    // Tombol nomor & aksi, tautan judul (`_titleNode`), dan isian lain di dalam baris menangani kliknya sendiri.
    const hit = e.target.closest?.("button, a, input, select, textarea");
    if (hit && hit !== e.currentTarget && e.currentTarget.contains(hit)) return;
    onOpen();
  };
  return (
    <div data-testid={`${tp}-row-${rk}`} onClick={onClick}
      className={`${DESK_ROW_CLASS} grid cursor-pointer grid-cols-1 items-center gap-x-3 gap-y-1 px-3 py-2 hover:bg-kn-neutral-soft sm:col-span-3 sm:grid-cols-subgrid`}>
      <div className="min-w-0">
        {/* `.link-button` (padding 2/4 px, 12/700) dimuat SESUDAH utilitas: huruf 13/600 warna aksi dipasang di isi
            tombol, padding diimbangi margin negatif supaya nomor sejajar dengan nama pihak dan tinggi baris tetap. */}
        <div className="flex min-w-0">
          <button type="button" data-testid={`${tp}-number-${rk}`} className="link-button -mx-1 -my-0.5 min-w-0 max-w-full"
            title={row.number} aria-haspopup="dialog" onClick={onOpen}>
            <span className="min-w-0 truncate text-left text-fs-13 font-semibold text-kn-action">{row.number}</span>
          </button>
        </div>
        {/* MN-T3 — `_titleNode` (opsional): judul sebagai tautan (mis. nama pelanggan → kartu pelanggan). */}
        <span data-testid={`${tp}-title-${rk}`} className="block truncate text-fs-13 text-kn-text"
          title={typeof row.title === "string" ? row.title : undefined}>
          {row._titleNode || row.title}
        </span>
      </div>
      <div className="min-w-0">
        {row.badge && (
          <div className="flex min-w-0">
            <DeskBadge badge={row.badge} testId={`${tp}-badge-${rk}`} />
          </div>
        )}
        <div className="flex min-w-0 items-center gap-1.5">
          {pt && <span data-testid={`${tp}-entity-${rk}`} className="shrink-0 text-fs-12 text-kn-text-2" title="PT">{pt}</span>}
          {hasAge(row) && (
            <span data-testid={`${tp}-age-${rk}`} className={`truncate whitespace-nowrap text-fs-12 font-medium ${ageClass(row)}`}>
              {ageText(row)}
            </span>
          )}
        </div>
      </div>
      <div className="flex min-w-0 items-center justify-between gap-2 sm:justify-end">
        <span data-testid={`${tp}-value-${rk}`} className="whitespace-nowrap text-fs-13 font-semibold tabular-nums text-kn-text">
          {rowValueText(row, kind)}
        </span>
        {label && (
          <button type="button" data-testid={`${tp}-action-${rk}`} className="secondary-button btn-sm shrink-0" disabled={busy}
            onClick={(e) => { e.stopPropagation(); onAction(); }}>
            {busy ? "Memproses…" : label}
          </button>
        )}
      </div>
    </div>
  );
}
