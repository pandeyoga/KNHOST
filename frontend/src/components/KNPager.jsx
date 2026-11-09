/**
 * KNPager — pager sisi-klien (T-03 Lapis 4: tabel SDM, `usePagedRows`/`PagedRows`, `ResponsiveTable` footer).
 *
 * FIX-8 (Standar UI Gudang v1 tahap 2 · B4 §3.13 · B1b "pager 3 gaya berbeda"): KNPager kini HANYA pembungkus
 * `PaginationBar` — satu-satunya pager aplikasi. Dulu tiga bentuk (PaginationBar · KNPager 12 px hex lepas dengan
 * tombol `btn-xs` · baris pager PagedRows) dengan teks, ukuran tombol, dan warna berbeda. API lama dipertahankan
 * (`page`, `pageSize`, `total`, `onChange`, `testId`; `${testId}-prev` / `${testId}-next` tetap ada). Tidak tampil
 * bila hanya satu halaman (perilaku lama).
 */
import PaginationBar from "./PaginationBar";

export default function KNPager({ page, pageSize, total, onChange, testId = "pager", label = "baris", loading = false }) {
  const pages = Math.max(1, Math.ceil((total || 0) / pageSize));
  if (pages <= 1) return null;
  return (
    <div data-testid={testId} className="kn-pager-wrap">
      <PaginationBar page={page} pageSize={pageSize} total={total || 0} hasMore={page < pages} loading={loading}
        onPrev={() => onChange(Math.max(1, page - 1))} onNext={() => onChange(Math.min(pages, page + 1))}
        onFirst={pages > 2 ? () => onChange(1) : undefined} onLast={pages > 2 ? () => onChange(pages) : undefined}
        testId={testId} label={label} />
    </div>
  );
}
