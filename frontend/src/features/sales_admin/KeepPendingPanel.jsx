import { useCallback, useEffect, useState } from "react";
import { Hourglass, PackageSearch, Truck, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { soTrackerLink } from "./workDeskApi";
import PendingProductRow from "./PendingProductRow";

const TABS = [
  { id: "keep", label: "Keep", icon: Hourglass },
  { id: "pending", label: "Pending", icon: PackageSearch },
  { id: "in_transit", label: "Dalam Perjalanan", icon: Truck },
];

/** P04 IMP-02/03 — Keep (belum diverifikasi) & Pending (kebutuhan barang) dipisah; total SO unik tidak ganda. */
export default function KeepPendingPanel({ selectedEntity = "all", onOpenDocument, testPrefix = "kp" }) {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("keep");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {};
      setData((await axios.get(`${API}/sales/keep-pending`, { params })).data);
      setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat Keep & Pending.")); }
    finally { setLoading(false); }
  }, [selectedEntity]);
  useEffect(() => { load(); }, [load]);

  const c = data?.counts || {};
  const open = (id, number) => onOpenDocument?.(soTrackerLink({ id, number }));
  const count = { keep: c.keep, pending: c.pending_orders, in_transit: c.in_transit_orders };

  return (
    <section className="section-card" data-testid={`${testPrefix}-panel`}>
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <PackageSearch size={15} className="text-[#0058CC]" />
          <h2>Keep &amp; Pending</h2>
          <span className="text-[11px] text-[#6B6B73]" data-testid={`${testPrefix}-unique`}>
            {c.unique_orders ?? 0} SO unik · {c.both ?? 0} keduanya
          </span>
        </div>
        <button className="icon-button" onClick={load} data-testid={`${testPrefix}-refresh`} aria-label="Muat ulang">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5 px-3 pt-2">
        {TABS.map((t) => (
          <button key={t.id} type="button" data-testid={`${testPrefix}-tab-${t.id}`} onClick={() => setTab(t.id)}
            className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11.5px] font-semibold transition-colors ${tab === t.id ? "bg-[#0058CC] text-white" : "bg-[#F2F3F5] text-[#3C3C43] hover:bg-[#E5E7EB]"}`}>
            <t.icon size={12} /> {t.label} <span className="tabular-nums" data-testid={`${testPrefix}-count-${t.id}`}>{count[t.id] ?? 0}</span>
          </button>
        ))}
      </div>
      {error && <p className="mx-3 mt-2 rounded-md bg-[#FDECEA] px-2 py-1.5 text-[11px] text-[#C0392B]" data-testid={`${testPrefix}-error`}>{error}</p>}
      <div className="p-3">
        {tab === "keep" && <KeepList rows={data?.keep || []} limit={data?.keep_limit_days || 0} overdue={c.keep_overdue || 0} onOpen={open} tp={testPrefix} />}
        {tab === "pending" && (
          (data?.pending || []).length === 0 ? <Empty tp={testPrefix} text="Tidak ada kebutuhan barang yang menunggu pemenuhan." />
            : <ul className="grid gap-2">{data.pending.map((p) => <PendingProductRow key={`${p.product_id}-${p.unit}`} p={p} onOpen={open} tp={testPrefix} />)}</ul>
        )}
        {tab === "in_transit" && <TransitList rows={data?.in_transit || []} onOpen={open} tp={testPrefix} />}
      </div>
    </section>
  );
}

function Empty({ text, tp }) {
  return <p className="py-6 text-center text-[12px] text-[#8E8E93]" data-testid={`${tp}-empty`}>{text}</p>;
}

function KeepList({ rows, limit, overdue, onOpen, tp }) {
  return (
    <>
      <p className="mb-2 text-[11px] text-[#6B6B73]" data-testid={`${tp}-keep-limit`}>
        Keep = SO belum diverifikasi Admin Sales (bukan berarti stok dicadangkan).{" "}
        {limit > 0 ? <>Batas umur <b>{limit} hari</b> · <b className="text-[#C0392B]">{overdue}</b> lewat batas (tanda saja, tidak dibatalkan).</>
          : "Batas umur belum diatur (Pusat Pengaturan › sales.keep_max_age_days)."}
      </p>
      {rows.length === 0 ? <Empty tp={tp} text="Semua SO sudah diverifikasi." /> : (
        <ul className="divide-y divide-[#F2F3F5] rounded-lg border border-[#EFF0F2]">
          {rows.map((r) => (
            <li key={r.order_id} data-testid={`${tp}-keep-row-${r.order_id}`}>
              <button type="button" onClick={() => onOpen(r.order_id, r.number)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-[#FAFBFC]">
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-semibold">{r.number} <span className="font-normal text-[#6B6B73]">· {r.customer_name}</span></p>
                  <p className="text-[10.5px] text-[#8E8E93]">{r.items_count} baris · {r.sales_name || "—"} · status {r.status}</p>
                </div>
                {r.also_pending && <span className="rounded-full bg-[#FFF3E0] px-2 py-0.5 text-[9.5px] font-bold text-[#9A5B00]" data-testid={`${tp}-keep-also-pending-${r.order_id}`}>juga Pending</span>}
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold tabular-nums ${r.overdue ? "bg-[#FDECEA] text-[#C0392B]" : "bg-[#F2F3F5] text-[#3C3C43]"}`} data-testid={`${tp}-keep-age-${r.order_id}`}>
                  {r.age_days} hari{r.overdue ? " · lewat batas" : ""}
                </span>
                <span className="w-28 text-right text-[11.5px] font-bold tabular-nums">{formatCurrency(r.grand_total)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function TransitList({ rows, onOpen, tp }) {
  if (!rows.length) return <Empty tp={tp} text="Tidak ada roll berkomitmen SO yang sedang di jalan." />;
  return (
    <ul className="grid gap-2">
      {rows.map((r) => (
        <li key={r.order_id} className="rounded-lg border border-[#EFF0F2] p-2.5" data-testid={`${tp}-transit-row-${r.order_id}`}>
          <button type="button" className="text-[12px] font-semibold text-[#0058CC] hover:underline" onClick={() => onOpen(r.order_id, r.number)}>{r.number}</button>
          <span className="text-[11px] text-[#6B6B73]"> · {r.customer_name} — sudah dikunci untuk SO, bukan Pending</span>
          {r.lines.map((ln) => (
            <p key={ln.product_id + ln.unit} className="mt-1 text-[11px] text-[#3C3C43]">
              {ln.product_name || ln.sku}: <b className="tabular-nums">{formatQty(ln.qty)} {ln.unit}</b> ({ln.rolls} roll) · {ln.transfers.map((t) => t.code).join(", ")}
            </p>
          ))}
        </li>
      ))}
    </ul>
  );
}
