import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, FileEdit, Search } from "lucide-react";
import { formatCurrency } from "../../../utils/formatters";
import { listAmendments, statusMeta } from "../../finance/amendments/amendmentApi";
import MobileAmendSheet from "./MobileAmendSheet";

const CLOSED = ["cancelled", "expired"];
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short" }) : "-");

function HistoryCard({ a }) {
  const [open, setOpen] = useState(false);
  const meta = statusMeta(a.status);
  const d = Number(a.impact?.delta || 0);
  return (
    <div className="m-card overflow-hidden" data-testid={`m-amd-history-${a.id}`}>
      <button className="m-press flex w-full items-center gap-2 p-3 text-left" onClick={() => setOpen(!open)}>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <b className="text-[12.5px] text-[#0058CC]">{a.number}</b>
            <span className="rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase" style={{ background: meta.bg, color: meta.fg }}>{meta.label}</span>
          </div>
          <p className="truncate text-[11.5px]">{a.doc_number} · {a.reason_label}</p>
          <p className="text-[10.5px] m-muted">{fmtDate(a.created_at)} · {a.proposed_by_name || a.proposed_by || ""}</p>
        </div>
        <span className={`text-[12.5px] font-bold tabular-nums ${d < 0 ? "text-[#C0392B]" : "text-[#1A7A3A]"}`}>{d > 0 ? "+" : ""}{formatCurrency(d)}</span>
        <ChevronDown size={15} className={`text-[#8E8E93] transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="space-y-1 border-t border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2 text-[11.5px]" data-testid={`m-amd-history-detail-${a.id}`}>
          {(a.changes || []).map((c, i) => (
            <p key={i}><b>{c.product_name}</b> · {c.label}: {c.field === "price" ? `${formatCurrency(c.from)} → ${formatCurrency(c.to)}` : `${c.from} → ${c.to}`}</p>
          ))}
          {a.method_label && <p className="m-muted">{a.method_label}</p>}
          {a.note && <p className="m-muted">Catatan: {a.note}</p>}
          {a.decision_note && <p className="m-muted">Putusan: {a.decision_note}</p>}
        </div>
      )}
    </div>
  );
}

/** Koreksi & Amandemen versi HP: pilih pesanan → koreksi; riwayat usulan beserta statusnya. */
export default function MobileAmendments({ orders = [], onRefresh }) {
  const [tab, setTab] = useState("new");
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(null);
  const load = () => listAmendments({ doc_type: "sales_order", limit: 100 }).then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  const eligible = useMemo(() => orders.filter((o) => !CLOSED.includes(o.status) && (o.items || []).length
    && (!q || `${o.number} ${o.customer_name}`.toLowerCase().includes(q.toLowerCase()))), [orders, q]);
  const count = (s) => (rows || []).filter((a) => s.includes(a.status)).length;
  const close = (done) => { setSel(null); if (done) { load(); onRefresh?.(); setTab("history"); } };

  return (
    <div className="space-y-3" data-testid="m-amendments">
      <div className="grid grid-cols-3 gap-2">
        {[["pending", "Menunggu", ["pending_approval"]], ["applied", "Diterapkan", ["applied", "auto_applied", "approved"]], ["rejected", "Ditolak", ["rejected"]]].map(([k, label, s]) => (
          <div key={k} className="m-card p-2.5 text-center" data-testid={`m-amd-stat-${k}`}>
            <p className="text-[18px] font-bold tabular-nums">{rows ? count(s) : "–"}</p>
            <p className="text-[10.5px] m-muted">{label}</p>
          </div>
        ))}
      </div>
      <div className="flex rounded-xl bg-[#E9E9EE] p-1">
        {[["new", "Ajukan koreksi"], ["history", "Riwayat"]].map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`m-amd-tab-${k}`}
            className={`flex-1 rounded-lg py-2 text-[12.5px] font-semibold ${tab === k ? "bg-white shadow-sm" : "text-[#6B6B73]"}`}>{label}</button>
        ))}
      </div>
      {tab === "new" && (<>
        <div className="m-card flex items-center gap-2 px-3 py-2"><Search size={15} className="m-muted" />
          <input className="w-full bg-transparent text-sm outline-none" placeholder="Cari nomor / pelanggan" value={q} onChange={(e) => setQ(e.target.value)} data-testid="m-amd-search" /></div>
        <p className="px-1 text-[11px] m-muted">Ketuk pesanan → ubah angka → Ajukan. Alasan dipilih otomatis.</p>
        {eligible.length === 0 && <p className="py-8 text-center text-[12px] m-muted" data-testid="m-amd-empty">Tidak ada pesanan yang bisa dikoreksi.</p>}
        {eligible.map((o) => (
          <button key={o.id} className="m-card m-press flex w-full items-center gap-2 p-3 text-left" onClick={() => setSel(o)} data-testid={`m-amd-order-${o.id}`}>
            <FileEdit size={16} className="text-[#0058CC]" />
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] font-bold">{o.number}</p>
              <p className="truncate text-[11px] m-muted">{o.customer_name} · {(o.items || []).length} item</p>
            </div>
            <span className="text-[12.5px] font-bold tabular-nums">{formatCurrency(o.grand_total ?? o.total_amount)}</span>
            <ChevronRight size={15} className="text-[#C7C7CC]" />
          </button>
        ))}
      </>)}
      {tab === "history" && (
        rows === null ? <p className="text-center text-[12px] m-muted">Memuat…</p>
          : rows.length === 0 ? <p className="py-8 text-center text-[12px] m-muted" data-testid="m-amd-history-empty">Belum ada koreksi.</p>
            : rows.map((a) => <HistoryCard key={a.id} a={a} />)
      )}
      {sel && <MobileAmendSheet order={sel} onClose={close} />}
    </div>
  );
}
