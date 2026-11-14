/**
 * PK-31 — bagian layar Konsolidasi Grup untuk eliminasi PER BULAN dan persen kepemilikan (K-10).
 *
 *  · `OwnershipShare` — baris **Bagian non-pengendali** dan **Bagian pemilik induk** (laba & ekuitas) di bawah
 *    matriks; tidak dirender bila semua PT 100 %.
 *  · `PeriodStaleNotice` — eliminasi bulan beku berbeda dari hitung ulang (ada jurnal mundur ke bulan tertutup).
 *  · `AutoEliminationsByMonth` — entri eliminasi otomatis antar-PT dikelompokkan per bulan; lencana **Beku** (bulan
 *    sudah ditutup di PT penjual & pembeli) dan **Bulan berjalan** (dihitung sampai tanggal laporan, tidak disimpan);
 *    kotak cari nomor transaksi/PT.
 */
import { useMemo, useState } from "react";
import { AlertTriangle, CalendarClock, ChevronDown, Lock, Users } from "lucide-react";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { SearchBox } from "../../components/ListPageParts";

/** True bila ada PT di laporan yang kepemilikannya < 100 %. */
export function hasMinority(entities) {
  return (entities || []).some((e) => Number(e.ownership_pct ?? 100) < 100);
}

export function OwnershipShare({ data, year, asOf }) {
  const k = data?.consolidated || {};
  if (!hasMinority(data?.entities)) return null;
  const rows = [
    { key: "nci", label: "Bagian non-pengendali", ni: k.nci_net_income, eq: k.nci_equity },
    { key: "parent", label: "Bagian pemilik induk", ni: k.net_income_parent, eq: k.equity_parent },
  ];
  return (
    <div className="mt-3 table-wrap" data-testid="cons-ownership-share">
      <table className="data-table">
        <thead>
          <tr>
            <th><span className="inline-flex items-center gap-1"><Users size={13} /> Pembagian kepemilikan</span></th>
            <th className="text-right">Laba bersih {year}</th>
            <th className="text-right">Ekuitas per {formatDate(asOf)}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} data-testid={`cons-share-${r.key}`}>
              <td className="font-semibold text-kn-text">{r.label}</td>
              <td className="text-right tabular-nums" data-testid={`cons-share-${r.key}-ni`}>{formatCurrency(r.ni || 0)}</td>
              <td className="text-right tabular-nums" data-testid={`cons-share-${r.key}-eq`}>{formatCurrency(r.eq || 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-fs-12 text-kn-text-2">
        Bagian non-pengendali = laba dan ekuitas buku tiap PT × (100 % − persen kepemilikan grup). Eliminasi antar-PT
        seluruhnya ditanggung pemilik induk.
      </p>
    </div>
  );
}

const bulanDari = (rows) => [...new Set((rows || []).map((s) => s.period_label || s.period_key).filter(Boolean))];

export function PeriodStaleNotice({ stale }) {
  const list = Array.isArray(stale) ? stale : [];
  if (list.length === 0) return null;
  return (
    <div className="notice-bar warning !items-start" role="alert" data-testid="cons-period-stale">
      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p className="font-semibold">
          Eliminasi bulan {bulanDari(list).join(", ")} berbeda dari hitung ulang karena ada jurnal mundur. Periksa
          sebelum memakai laporan ini.
        </p>
        <p className="text-fs-12">
          Transaksi: {list.map((s) => s.number || s.pair_id).join(", ")}. Angka bulan yang sudah ditutup tetap memakai
          entri beku.
        </p>
      </div>
    </div>
  );
}

function MonthBadges({ rows }) {
  const beku = rows.some((e) => e.frozen);
  const berjalan = rows.some((e) => e.partial);
  return (
    <>
      {beku && (
        <span className="status-pill bg-kn-neutral-soft text-kn-neutral" data-testid="cons-month-frozen">
          <Lock size={12} /> Beku
        </span>
      )}
      {berjalan && (
        <span className="status-pill bg-kn-action-soft text-kn-action" data-testid="cons-month-running">
          <CalendarClock size={12} /> Bulan berjalan
        </span>
      )}
    </>
  );
}

export function AutoEliminationsByMonth({ entries }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState({});
  const list = Array.isArray(entries) ? entries : [];
  const groups = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const hit = (e) => !needle || [e.seller_number, e.name, e.entity_from, e.entity_to]
      .some((v) => String(v || "").toLowerCase().includes(needle));
    const by = new Map();
    list.filter(hit).forEach((e) => {
      const k = e.period_key || (e.effective_date || "").slice(0, 7);
      if (!by.has(k)) by.set(k, []);
      by.get(k).push(e);
    });
    return [...by.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [list, q]);
  if (list.length === 0) return null;
  return (
    <div className="mb-4" data-testid="cons-auto-elims">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h4 className="text-fs-13 font-bold text-kn-text">Eliminasi otomatis antar-PT per bulan</h4>
        <span className="text-fs-12 text-kn-text-2">{list.length} entri · dihitung dari data bertanggal</span>
      </div>
      {list.length > 5 && (
        <SearchBox value={q} onChange={setQ} placeholder="Cari nomor transaksi antar-PT…" testId="cons-auto-elims-search" />
      )}
      {groups.length === 0 && (
        <p className="py-4 text-center text-fs-13 text-kn-text-2" data-testid="cons-auto-elims-none">
          Tidak ada eliminasi yang cocok dengan pencarian.
        </p>
      )}
      <div className="space-y-2">
        {groups.map(([pk, rows]) => {
          const label = rows[0]?.period_label || pk;
          const total = rows.reduce((s, e) => s + (Number(e.total_debit) || 0), 0);
          const isOpen = Boolean(open[pk]);
          return (
            <div key={pk} className="rounded-md border border-kn-divider" data-testid={`cons-month-${pk}`}>
              <button type="button" className="ghost-button w-full justify-between" aria-expanded={isOpen}
                onClick={() => setOpen((o) => ({ ...o, [pk]: !o[pk] }))} data-testid={`cons-month-toggle-${pk}`}>
                <span className="inline-flex flex-wrap items-center gap-2">
                  <b className="text-kn-text">{label}</b>
                  <span className="text-fs-12 text-kn-text-2">{rows.length} transaksi</span>
                  <MonthBadges rows={rows} />
                </span>
                <span className="inline-flex items-center gap-2 tabular-nums">
                  {formatCurrency(total)}
                  <ChevronDown size={13} className={isOpen ? "rotate-180" : ""} />
                </span>
              </button>
              {isOpen && (
                <div className="space-y-2 px-3 pb-3">
                  {rows.map((e) => (
                    <div key={`${e.source_g6_pair_id}-${pk}`} data-testid={`cons-auto-elim-${e.source_g6_pair_id}-${pk}`}>
                      <p className="text-fs-12 font-semibold text-kn-text">
                        {e.seller_number || e.source_g6_pair_id} · efektif {formatDate(e.effective_date)}
                        {e.partial ? " (sampai tanggal laporan)" : ""}
                      </p>
                      <div className="table-wrap">
                        <table className="data-table">
                          <thead><tr><th>Akun</th><th className="text-right">Debit</th><th className="text-right">Kredit</th></tr></thead>
                          <tbody>
                            {(e.lines || []).map((l, i) => (
                              <tr key={i}>
                                <td><span className="mr-1 font-mono text-fs-12 text-kn-text-2">{l.account_code}</span>{l.account_name}</td>
                                <td className="text-right tabular-nums">{l.debit > 0 ? formatCurrency(l.debit) : "—"}</td>
                                <td className="text-right tabular-nums">{l.credit > 0 ? formatCurrency(l.credit) : "—"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
