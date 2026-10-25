/**
 * ResponsiveTable — tabel dari DEFINISI KOLOM: `.data-table` di layar lebar, KARTU di HP (fase 3 · P1, L-04/L-07).
 *
 * KENAPA ADA: crawl HP 390 px (audit UI tahap 2) — tabel `min-w-[…]` memaksa seluruh halaman bergulir ke
 * samping, kolom aksi hilang di luar layar, dan pesan kosong/pager ikut bergulir. Layar kelas B (bisa dibuka
 * dari aplikasi HP) wajib layak 390 px. Satu definisi kolom → dua rupa, supaya tiap layar tidak membangun
 * kartu HP sendiri-sendiri.
 *
 *   <ResponsiveTable testId="rfq-table" rows={rows} rowKey="id" onRowClick={openDetail}
 *     columns={[
 *       { key: "number", header: "Nomor", mobile: "title", render: (r) => <b>{r.number}</b> },
 *       { key: "status", header: "Status", mobile: "badge", render: (r) => <StatusBadge s={r.status} /> },
 *       { key: "supplier", header: "Pemasok", mobile: "subtitle" },
 *       { key: "total", header: "Total", align: "right", priority: 1, render: (r) => formatCurrency(r.total) },
 *       { key: "created_at", header: "Dibuat", priority: 2, render: (r) => formatDate(r.created_at) },
 *       { key: "note", header: "Catatan", mobile: "hidden" },
 *     ]}
 *     actions={(r) => <button className="secondary-button" onClick={() => edit(r)}>Ubah</button>}
 *     empty="Belum ada RFQ." footer={<KNPager … />} />
 *
 * Kolom: `{ key, header, render?(row, i), value?(row), align?: "left"|"right"|"center", className?,
 *   headerClassName?, mobile?: "title"|"subtitle"|"badge"|"field"|"hidden", mobileLabel?, priority? }`.
 *   Bawaan `mobile`: kolom pertama "title", sisanya "field". Kartu menampilkan `cardFields` isian (bawaan 4)
 *   dengan `priority` terkecil lebih dulu; sisanya di balik tombol "+N lainnya" — tidak ada kolom yang hilang.
 * Props lain: `rows` · `rowKey` (nama field atau fungsi; bawaan "id") · `onRowClick(row)` · `actions(row)`
 *   (kolom terakhir di desktop, kaki kartu di HP; `actionsHeader` bawaan "Aksi"; `stickyActions` = kolom aksi
 *   menempel kanan saat tabel bergulir) · `loading` · `empty` · `footer` (pager — di LUAR wadah gulir, P-05)
 *   · `testId` (baris: `${testId}-row-${key}`) · `rowTestId(row)` · `rowClassName(row)` · `breakpoint` (bawaan
 *   640) · `mode` ("auto" | "table" | "cards") · `cardFields`.
 */
import { useState } from "react";
import useIsMobile from "../hooks/useIsMobile";

const EMPTY_CELL = "—";
const alignCls = (a) => (a === "right" ? "text-right" : a === "center" ? "text-center" : "");

function cellOf(col, row, i) {
  const v = col.render ? col.render(row, i) : (col.value ? col.value(row) : row?.[col.key]);
  return v === null || v === undefined || v === "" ? EMPTY_CELL : v;
}

function keyOf(rowKey, row, i) {
  if (typeof rowKey === "function") return rowKey(row, i);
  const k = row?.[rowKey];
  return k === undefined || k === null || k === "" ? `row-${i}` : k;
}

/** Peran tiap kolom di kartu HP. */
function mobileRoles(columns) {
  return columns.map((c, i) => c.mobile || (i === 0 ? "title" : "field"));
}

function Card({ row, i, columns, roles, actions, onRowClick, tid, cls, cardFields }) {
  const [more, setMore] = useState(false);
  const pick = (role) => columns.filter((_, k) => roles[k] === role);
  const title = pick("title");
  const subtitle = pick("subtitle");
  const badges = pick("badge");
  const fields = columns
    .map((c, k) => ({ c, k }))
    .filter(({ k }) => roles[k] === "field")
    .sort((a, b) => (a.c.priority ?? 99) - (b.c.priority ?? 99) || a.k - b.k)
    .map(({ c }) => c);
  const shown = more ? fields : fields.slice(0, cardFields);
  const rest = fields.length - shown.length;
  const clickable = typeof onRowClick === "function";
  const open = () => clickable && onRowClick(row);
  return (
    <div className={`rt-card ${clickable ? "rt-clickable" : ""} ${cls || ""}`.trim()} data-testid={tid}
      role={clickable ? "button" : undefined} tabIndex={clickable ? 0 : undefined} onClick={open}
      onKeyDown={(e) => { if (clickable && (e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) { e.preventDefault(); open(); } }}>
      {(title.length > 0 || badges.length > 0) && (
        <div className="rt-card-head">
          <div className="rt-card-title">{title.map((c) => <span key={c.key}>{cellOf(c, row, i)}</span>)}</div>
          {badges.length > 0 && <div className="rt-card-badges">{badges.map((c) => <span key={c.key}>{cellOf(c, row, i)}</span>)}</div>}
        </div>
      )}
      {subtitle.length > 0 && (
        <div className="rt-card-sub">{subtitle.map((c) => <span key={c.key}>{cellOf(c, row, i)}</span>)}</div>
      )}
      {shown.length > 0 && (
        <dl className="rt-card-fields">
          {shown.map((c) => (
            <div key={c.key} className="rt-card-field">
              <dt>{c.mobileLabel || c.header}</dt>
              <dd className={alignCls(c.align)}>{cellOf(c, row, i)}</dd>
            </div>
          ))}
        </dl>
      )}
      {(rest > 0 || more) && fields.length > cardFields && (
        <button type="button" className="rt-card-more" data-testid={tid ? `${tid}-more` : undefined}
          onClick={(e) => { e.stopPropagation(); setMore((m) => !m); }}>
          {more ? "Ringkas" : `+${rest} lainnya`}
        </button>
      )}
      {actions && (
        // Klik tombol aksi tidak ikut membuka rincian baris.
        <div className="rt-card-actions" onClick={(e) => e.stopPropagation()}>{actions(row)}</div>
      )}
    </div>
  );
}

export default function ResponsiveTable({
  columns = [], rows = [], rowKey = "id", onRowClick, actions, actionsHeader = "Aksi", stickyActions = false,
  loading = false, empty = "Tidak ada data.", footer = null, testId, rowTestId, rowClassName,
  breakpoint = 640, mode = "auto", cardFields = 4, className = "",
}) {
  const narrow = useIsMobile(breakpoint);
  const cards = mode === "cards" || (mode === "auto" && narrow);
  const cols = (columns || []).filter(Boolean);
  const list = Array.isArray(rows) ? rows : [];
  const tidOf = (row, i) => (rowTestId ? rowTestId(row, i) : (testId ? `${testId}-row-${keyOf(rowKey, row, i)}` : undefined));
  const clickable = typeof onRowClick === "function";

  let body;
  if (loading && list.length === 0) {
    body = <div className="rt-state" data-testid={testId ? `${testId}-loading` : undefined}>Memuat…</div>;
  } else if (list.length === 0) {
    // Pesan kosong di LUAR wadah gulir (P-05): tidak ikut tergeser ke samping di HP.
    body = <div className="rt-state" data-testid={testId ? `${testId}-empty` : undefined}>{empty}</div>;
  } else if (cards) {
    const roles = mobileRoles(cols);
    body = (
      <div className="rt-cards">
        {list.map((row, i) => (
          <Card key={keyOf(rowKey, row, i)} row={row} i={i} columns={cols} roles={roles} actions={actions}
            onRowClick={onRowClick} tid={tidOf(row, i)} cls={rowClassName?.(row, i)} cardFields={cardFields} />
        ))}
      </div>
    );
  } else {
    body = (
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              {cols.map((c) => <th key={c.key} className={`${alignCls(c.align)} ${c.headerClassName || ""}`.trim() || undefined}>{c.header}</th>)}
              {actions && <th className={`rt-actions ${stickyActions ? "rt-sticky" : ""}`.trim()}>{actionsHeader}</th>}
            </tr>
          </thead>
          <tbody>
            {list.map((row, i) => (
              <tr key={keyOf(rowKey, row, i)} data-testid={tidOf(row, i)}
                className={`${clickable ? "rt-clickable" : ""} ${rowClassName?.(row, i) || ""}`.trim() || undefined}
                tabIndex={clickable ? 0 : undefined}
                onClick={clickable ? () => onRowClick(row) : undefined}
                onKeyDown={clickable ? (e) => { if (e.key === "Enter" && e.target === e.currentTarget) onRowClick(row); } : undefined}>
                {cols.map((c) => <td key={c.key} className={`${alignCls(c.align)} ${c.className || ""}`.trim() || undefined}>{cellOf(c, row, i)}</td>)}
                {actions && (
                  <td className={`rt-actions ${stickyActions ? "rt-sticky" : ""}`.trim()} onClick={(e) => e.stopPropagation()}>{actions(row)}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className={`rt ${cards ? "rt-mode-cards" : "rt-mode-table"} ${className}`.trim()} data-testid={testId}>
      {body}
      {footer}
    </div>
  );
}
