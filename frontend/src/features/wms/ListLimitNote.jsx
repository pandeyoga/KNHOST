import { formatQty } from "../../utils/formatters";

/**
 * FIX-5 (B3b LST-01, B1b "batas senyap") — daftar berbatas server TIDAK lagi memotong diam-diam: tampilkan
 * "Menampilkan a–b dari N" + tombol muat berikutnya bila masih ada sisa. Sumber angka = server (`total`/`truncated`
 * di badan respons, atau header `X-Total-Count`/`X-Truncated`) — lihat `metaFromHeaders`.
 */
export function metaFromHeaders(res, shown, skip = 0) {
  const h = res?.headers || {};
  const raw = h["x-total-count"];
  if (raw === undefined || raw === null || raw === "") return null;
  const total = Number(raw) || 0;
  return { total, truncated: String(h["x-truncated"] || "0") === "1", shown, skip };
}

export default function ListLimitNote({ meta, noun = "baris", onMore, loading = false, hint = "", testId = "list-limit-note" }) {
  if (!meta || !meta.truncated) return null;
  const start = (meta.skip || 0) + 1;
  const end = (meta.skip || 0) + (meta.shown || 0);
  return (
    <div data-testid={testId} role="status"
      className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-[#F5D9A8] bg-[#FFF8EB] px-3 py-2 text-[12px] text-[#7A4A00]">
      <span>
        Menampilkan {noun} {formatQty(start)}–{formatQty(end)} dari <b>{formatQty(meta.total)}</b>
        {hint ? ` — ${hint}` : " — persempit saringan atau muat berikutnya."}
      </span>
      {onMore && (
        <button type="button" className="secondary-button ml-auto" disabled={loading} onClick={onMore}
          data-testid={`${testId}-more`}>
          {loading ? "Memuat…" : "Muat berikutnya"}
        </button>
      )}
    </div>
  );
}
