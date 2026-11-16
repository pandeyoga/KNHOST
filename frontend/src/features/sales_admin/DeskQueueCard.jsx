/**
 * DeskQueueCard — satu ANTREAN meja kerja (dipakai Meja Admin Sales & Meja Finance).
 *
 * Aturan desain yang dijaga komponen ini (US15):
 *  1. Setiap antrean membawa **JUMLAH · NILAI · UMUR TERTUA** di kepalanya.
 *  2. **Satu tindakan jelas per baris.** Bukan menu tiga titik.
 *  3. Satuannya ikut jenis nilainya (yard vs rupiah) — `value_kind`.
 *
 * UI/UX 2026-06 (keluhan pemilik):
 *  4. 5 baris per halaman + paginasi di kartu (urutan server = paling mendesak dulu).
 *  5. (16 Nov, pola UI) Kartu selalu terbuka dan setinggi tetangganya — buka/tutup dihapus atas permintaan pemilik.
 */
import { Inbox } from "lucide-react";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { formatUnitTotals } from "../../utils/qtyByUnit";
import { RevisionBadge } from "../../components/RevisionProgress";
import { ageTone, badgeClass, badgeLabel, queueMeta, fmtWhen, sinceFromAge } from "./workDeskApi";
import usePagedRows from "@/hooks/usePagedRows";
import TableFilterBar, { useTableFilter } from "../../components/TableFilter";

// Trial 22 Okt (E7) — urutan antrean: bawaan server (paling mendesak/tertua dulu), terbaru, nilai terbesar.
const QUEUE_SORTS = {
  server: { label: "Tertua dulu" },
  newest: { label: "Terbaru dulu", cmp: (a, b) => Number(a.age_days || 0) - Number(b.age_days || 0) },
  value: { label: "Nilai terbesar", cmp: (a, b) => Number(b.value || 0) - Number(a.value || 0) },
};

// Permintaan pemilik 2026-10: tiap kartu = 5 baris per halaman + paginasi DI kartu (tanpa pop-up).
const PAGE_ROWS = 5;

/**
 * Pola UI (04_POLA_UI §2.B, permintaan pemilik 16 Nov — M1, M31): kartu antrean SELALU TERBUKA (tanpa buka/tutup),
 * setinggi kartu di sebelahnya (`h-full` + daftar `flex-1`), cari + saring status + urut (dropdown) + paginasi di tiap
 * kartu, dan baris BERKOLOM (dokumen · status + keterangan + umur · nilai · aksi) sehingga tengah kartu tidak kosong.
 * `defaultOpen` diterima demi pemanggil lama, tetapi tidak berpengaruh lagi.
 */
export default function DeskQueueCard({
  queue, onAction, busyRef = "", testPrefix = "desk", rowTestPrefix, loading = false,
}) {
  const meta = queueMeta(queue?.id);
  const Icon = meta.icon;
  const isQty = queue?.value_kind === "qty";
  const rows = Array.isArray(queue?.rows) ? queue.rows : [];
  // Cek UI UAT v3 (S2) — antrean panjang urut tertua dulu: dokumen baru ada di halaman terakhir (mis. hlm 14).
  // Trial 22 Okt (E7) — cari (nomor / pelanggan / keterangan / status) + filter status + urutan di SEMUA antrean meja.
  const f = useTableFilter(rows, {
    text: (r) => `${r.number || ""} ${r.title || ""} ${r.subtitle || ""} ${badgeLabel(r.badge || "")}`,
    status: (r) => r.badge || "", statusLabel: badgeLabel, sorts: QUEUE_SORTS,
  });
  const needle = f.active;
  const shownRows = f.shown;
  const pg = usePagedRows(shownRows, { pageSize: PAGE_ROWS, testId: `${testPrefix}-pager-${queue?.id}` });
  const visible = pg.pageRows;
  const oldest = ageTone(queue?.oldest_age_days);

  // Ringkasan: qty → angka PER SATUAN (yard dan kg tidak dijumlahkan — kelas F-04); count → jumlah dokumen;
  // selain itu SELALU rupiah.
  const unitTotals = isQty
    ? rows.reduce((m, r) => { const u = r.unit || ""; m[u] = (m[u] || 0) + (Number(r.value) || 0); return m; }, {})
    : null;
  const totalText = isQty
    ? (rows.length ? formatUnitTotals(unitTotals, queue?.total_value) : `${formatQty(queue?.total_value)}`)
    : queue?.value_kind === "count"
      ? `${rows.length} dokumen`
      : formatCurrency(Number(queue?.total_value) || 0);

  return (
    <section className="section-card flex h-full flex-col" data-testid={`${testPrefix}-queue-${queue?.id}`}>
      <header className="flex items-start gap-2.5 px-3 py-2.5">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg" style={{ background: meta.bg }}>
          <Icon size={16} style={{ color: meta.tone }} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-fs-14 font-bold text-kn-text">{queue?.label}</h3>
            <span data-testid={`${testPrefix}-count-${queue?.id}`}
                  className="rounded-full px-2 py-0.5 text-fs-12 font-bold tabular-nums"
                  style={{ background: meta.bg, color: meta.tone }}>
              {queue?.count || 0}
            </span>
            {(queue?.count || 0) > 0 && (
              <span data-testid={`${testPrefix}-oldest-${queue?.id}`}
                    className={`rounded-full border px-2 py-0.5 text-fs-12 font-bold ${oldest.cls}`}
                    title="Umur baris tertua di antrean ini">
                tertua {oldest.label}
              </span>
            )}
          </div>
          {queue?.hint && (
            <p className="mt-0.5 truncate text-fs-12 text-kn-text-2" title={queue.hint}>{queue.hint}</p>
          )}
        </div>
        <div className="shrink-0 pl-2 text-right">
          <p className="text-fs-12 font-semibold uppercase tracking-wide text-kn-neutral">{queue?.value_label || "Nilai"}</p>
          <p data-testid={`${testPrefix}-total-${queue?.id}`} className="text-fs-13 font-bold tabular-nums text-kn-text">
            {totalText}
          </p>
        </div>
      </header>

      {/* Saat antrean sedang dimuat ulang, angka lama masih terpampang. Tanpa
          penanda ini pengguna menindak baris yang mungkin sudah berpindah antrean. */}
      {loading && rows.length > 0 && (
        <p data-testid={`${testPrefix}-refreshing-${queue?.id}`}
           className="border-t border-kn-divider bg-kn-neutral-soft px-3 py-1 text-fs-12 text-kn-text-2">
          Memuat ulang antrean…
        </p>
      )}

      {loading && rows.length === 0 ? (
        <p data-testid={`${testPrefix}-loading-${queue?.id}`}
           className="flex flex-1 items-center justify-center border-t border-kn-divider px-3 py-7 text-fs-12 text-kn-text-2">
          Memuat antrean…
        </p>
      ) : rows.length === 0 ? (
        <div data-testid={`${testPrefix}-empty-${queue?.id}`}
             className="flex flex-1 flex-col items-center justify-center border-t border-kn-divider px-3 py-7 text-fs-12 text-kn-text-2">
          <Inbox size={22} className="mb-1.5 text-kn-neutral" />
          Antrean ini bersih — tidak ada yang perlu ditindak.
        </div>
      ) : (<>
        <div className="border-t border-kn-divider">
          <TableFilterBar f={f} testId={`${testPrefix}-q-${queue?.id}`} searchTestId={`${testPrefix}-search-${queue?.id}`}
            onChange={() => pg.setPage(1)} placeholder="Cari nomor dokumen / pelanggan / keterangan…" />
          {needle && shownRows.length === 0 && (
            <p className="px-3 pb-1.5 text-fs-12 text-kn-text-2" data-testid={`${testPrefix}-search-empty-${queue?.id}`}>Tidak ada baris yang cocok.</p>
          )}
        </div>
        <div className="flex-1 divide-y divide-kn-divider border-t border-kn-divider">
          {visible.map((row, i) => (
            <QueueRow key={`${row.ref_type}-${row.ref_id}-${row.number || i}`}
                      row={row} queue={queue}
                      isQty={isQty} busy={busyRef === row.ref_id}
                      testPrefix={rowTestPrefix || testPrefix}
                      onAction={() => onAction?.(row, queue)} />
          ))}
        </div>
      </>)}

      {shownRows.length > PAGE_ROWS && <div className="border-t border-kn-divider px-3 py-1.5">{pg.pager}</div>}
      {/* Cek UI UAT v3 — antrean sangat panjang: server mengirim baris tertua dulu (maks. 200) */}
      {(queue?.count || 0) > rows.length && (
        <p className="border-t border-kn-divider px-3 py-1.5 text-fs-12 text-kn-warning-text" data-testid={`${testPrefix}-truncated-${queue?.id}`}>
          Menampilkan {rows.length} tertua dari {queue.count} — selesaikan yang tertua dulu, atau buka layar daftarnya untuk mencari dokumen tertentu.
        </p>
      )}
    </section>
  );
}

/** Satu baris antrean: dokumen · (status + keterangan / umur) · nilai · aksi (kolom di ≥ 640 px; bertumpuk di HP). */
function QueueRow({ row, queue, isQty, busy, onAction, testPrefix }) {
  const age = ageTone(row.age_days);
  // Kolom nilai: qty → angka + satuan; count → kosong (tidak bermakna per baris); money → rupiah.
  const value = isQty
    ? `${formatQty(row.value)} ${row.unit || ""}`.trim()
    : queue?.value_kind === "count"
      ? ""
      : formatCurrency(Number(row.value) || 0);

  const rk = row.row_key || row.ref_id;   // satu pelanggan bisa punya beberapa baris (per SO) — testid tetap unik
  return (
    <div data-testid={`${testPrefix}-row-${rk}`}
         className="grid grid-cols-1 items-center gap-x-3 gap-y-1 px-3 py-2 hover:bg-kn-neutral-soft sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)_auto_auto]">
      {/* Dokumen: nomor + judul */}
      <div className="min-w-0">
        <span data-testid={`${testPrefix}-number-${rk}`} className="block truncate text-fs-13 font-bold text-kn-action" title={row.number}>{row.number}</span>
        {/* MN-T3 — `_titleNode` (opsional): judul sebagai tautan (mis. nama pelanggan → kartu pelanggan). */}
        <p className="truncate text-fs-13 font-semibold text-kn-text">{row._titleNode || row.title}</p>
      </div>
      {/* Status + keterangan (baris 1) · umur + waktu masuk (baris 2) */}
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-1.5">
          {row.badge && (
            <span data-testid={`${testPrefix}-badge-${rk}`} title={badgeLabel(row.badge)}
                  className={`shrink-0 whitespace-nowrap rounded-full border px-1.5 text-fs-12 font-semibold ${badgeClass(row.badge)}`}>
              {badgeLabel(row.badge)}
            </span>
          )}
          {row.revision_count !== undefined && row.revision_count !== null && (
            <span className="shrink-0"><RevisionBadge count={row.revision_count} size="xs" testId={`${testPrefix}-revision-${rk}`} /></span>
          )}
          {row.subtitle && <span className="min-w-0 truncate text-fs-12 text-kn-text-2" title={row.subtitle}>{row.subtitle}</span>}
        </div>
        <p className="truncate whitespace-nowrap text-fs-12 text-kn-text-2" data-testid={`${testPrefix}-time-${rk}`}
          title="Umur baris ini">
          <span className={`rounded px-1 font-semibold ${age.cls}`}>menunggu {age.label}</span>{" · "}
          {row.at || row.created_at || row.updated_at
            ? `masuk ${fmtWhen(row.at || row.created_at || row.updated_at)}`
            : `masuk ± ${sinceFromAge(row.age_days)}`}
        </p>
      </div>
      <span data-testid={`${testPrefix}-value-${rk}`}
            className="whitespace-nowrap text-fs-13 font-semibold tabular-nums sm:text-right">
        {value}
      </span>
      <button type="button" data-testid={`${testPrefix}-action-${rk}`}
              className="btn-secondary btn-xs justify-self-start sm:justify-self-end" disabled={busy} onClick={onAction}
              title={queue?.hint || ""}>
        {busy ? "Memproses…" : (row.action || queue?.action_label || "Buka")}
      </button>
    </div>
  );
}
