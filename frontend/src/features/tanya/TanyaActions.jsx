import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, RefreshCw } from "lucide-react";
import DetailModal from "../../components/DetailModal";
import FilterChips from "../../components/FilterChips";
import { formatCurrency, formatDateTime } from "../../utils/formatters";
import { kpiValueParts } from "../finance/financeShared";
import { CARD_STATUS_LABEL, StatusPill, TanyaActionCard } from "./TanyaActionCard";
import { fetchActions } from "./tanyaApi";

/** Saringan tab "Tindakan" (AG-T3). "Menunggu orang lain" (AG-T5) = kartu yang menunggu persetujuan orang kedua di PT
 *  aktif: yang boleh Anda putus sebagai orang kedua, dan kartu Anda sendiri yang sedang menunggu. */
export const ACTION_BOXES = [["mine", "Menunggu saya"], ["others", "Menunggu orang lain"], ["done", "Selesai"],
  ["failed", "Gagal"]];
const PAGE_SIZE = 20;
const COLS = ["Tindakan", "PT", "Nominal", "Dibuat", "Berlaku sampai", "Status"];

/**
 * Tanya KN › Tindakan — daftar kartu tindakan milik pengguna, per saringan, berhalaman dengan jumlah total. Baris
 * dipilih → kartunya tampil di pop-up (`DetailModal`, INV-UI-08; setujui/abaikan dari sini sama dengan di percakapan).
 */
export function TanyaActions({ refreshKey, initialBox = "mine" }) {
  const [box, setBox] = useState(ACTION_BOXES.some(([k]) => k === initialBox) ? initialBox : "mine");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [sel, setSel] = useState(null);
  const load = useCallback(() => {
    setError(false);
    return fetchActions(box, page, PAGE_SIZE).then(setData).catch(() => { setData(null); setError(true); });
  }, [box, page]);
  useEffect(() => { setData(null); load(); }, [load, refreshKey]);
  const pick = (b) => { setBox(b); setPage(1); setSel(null); };
  const pages = data ? Math.max(1, Math.ceil((data.total || 0) / (data.page_size || PAGE_SIZE))) : 1;
  return (
    <div className="tanya-actions" data-testid="tanya-actions">
      <FilterChips testId="tanya-actions-box" ariaLabel="Saringan kartu tindakan" value={box} onChange={pick}
        options={ACTION_BOXES.map(([key, label]) => ({ key, label }))} />
      {!data && !error && (
        <div className="tanya-actions-state" data-testid="tanya-actions-loading"><Loader2 className="h-4 w-4 animate-spin inline" /> Memuat kartu…</div>
      )}
      {error && (
        <div className="tanya-actions-state" data-testid="tanya-actions-error" role="alert">
          Kartu tindakan tidak bisa dimuat. Coba lagi.{" "}
          <button type="button" className="secondary-button btn-sm" onClick={load} data-testid="tanya-actions-retry">
            <RefreshCw size={14} aria-hidden="true" /> Coba lagi
          </button>
        </div>
      )}
      {data && data.items.length === 0 && (
        <div className="tanya-actions-state" data-testid="tanya-actions-empty">Belum ada kartu tindakan.</div>
      )}
      {data && data.items.length > 0 && (<>
        <p className="tanya-actions-count" data-testid="tanya-actions-count">{data.total} kartu</p>
        <table className="data-table head-wrap tanya-actions-table" data-testid="tanya-actions-table">
          <thead><tr>{COLS.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {data.items.map((it) => {
              const amount = Number(it.plan?.amount) || 0;
              return (
                <tr key={it.id} className={sel === it.id ? "active" : ""} data-testid={`tanya-actions-row-${it.id}`}>
                  <td data-label={COLS[0]}>
                    <button type="button" className="link-button" onClick={() => setSel(sel === it.id ? null : it.id)}
                      aria-expanded={sel === it.id} data-testid={`tanya-actions-open-${it.id}`}>{it.title || "Kartu tindakan"}</button>
                  </td>
                  <td data-label={COLS[1]}>{it.entity_name || "—"}</td>
                  <td data-label={COLS[2]} className="tabular-nums"><span>{amount > 0 ? kpiValueParts(formatCurrency(amount)) : "—"}</span></td>
                  <td data-label={COLS[3]}>{formatDateTime(it.created_at)}</td>
                  <td data-label={COLS[4]}>{["pending", "awaiting_second"].includes(it.status) ? formatDateTime(it.expires_at) : "—"}</td>
                  <td data-label={COLS[5]}><StatusPill status={it.status} labels={CARD_STATUS_LABEL} testId={`tanya-actions-pill-${it.id}`} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {pages > 1 && (
          <div className="tanya-actions-pager" data-testid="tanya-actions-pager">
            <button type="button" className="secondary-button btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft size={14} aria-hidden="true" /> Sebelumnya
            </button>
            <span className="tanya-actions-count">Halaman {page} dari {pages}</span>
            <button type="button" className="secondary-button btn-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
              Berikutnya <ChevronRight size={14} aria-hidden="true" />
            </button>
          </div>
        )}
      </>)}
      {sel && (
        <DetailModal onClose={() => setSel(null)} size="md" framed label="Kartu tindakan" testId="tanya-actions-card-modal">
          <TanyaActionCard key={sel} proposalId={sel} onChanged={() => load()} />
        </DetailModal>
      )}
    </div>
  );
}
