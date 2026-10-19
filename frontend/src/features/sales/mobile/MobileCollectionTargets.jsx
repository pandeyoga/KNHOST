import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BellRing, CheckCircle2, PhoneCall, Trophy, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";
import { formatCurrency } from "../../../utils/formatters";

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" }) : "-");
const thisMonth = () => new Date().toISOString().slice(0, 7);
const errOf = (e, fb) => { const d = e?.response?.data?.detail; return (typeof d === "string" ? d : d?.message) || fb; };
const OUTCOMES = [{ value: "contacted", label: "Dihubungi" }, { value: "promised", label: "Dijanjikan bayar" },
  { value: "paid", label: "Sudah bayar" }, { value: "no_response", label: "Tak respon" }, { value: "escalated", label: "Eskalasi" }];

/** Penagihan & Target versi HP: pengingat tagih (tandai/follow-up) + target, komisi, riwayat, peringkat saya. */
export default function MobileCollectionTargets({ selectedEntity, initialTab = "collection" }) {
  const [tab, setTab] = useState(initialTab);
  return (
    <div className="space-y-2 p-3" data-testid="m-collect-targets">
      <div className="grid grid-cols-2 gap-1 rounded-xl bg-[#F2F3F5] p-1">
        {[["collection", "Penagihan"], ["targets", "Target & Komisi"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`m-ct-tab-${k}`}
            className={`rounded-lg py-2 text-[12.5px] font-semibold ${tab === k ? "bg-white text-[#0058CC] shadow-sm" : "text-[#6B6B73]"}`}>{l}</button>
        ))}
      </div>
      {tab === "collection" ? <Collection selectedEntity={selectedEntity} /> : <Targets selectedEntity={selectedEntity} />}
    </div>
  );
}

function Kpi({ label, value, tone = "", testId }) {
  return (
    <div className="m-card p-2.5" data-testid={testId}>
      <p className="text-[9.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">{label}</p>
      <p className={`text-[13px] font-bold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

function Collection({ selectedEntity }) {
  const [rows, setRows] = useState(null);
  const [mode, setMode] = useState("all");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState("");
  const [fu, setFu] = useState(null);
  const load = () => {
    const params = { days_ahead: 60 };
    if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
    axios.get(`${API}/collection-reminders`, { params }).then((r) => setRows(Array.isArray(r.data) ? r.data : []))
      .catch((e) => { setRows([]); setMsg({ ok: false, text: errOf(e, "Gagal memuat pengingat tagih.") }); });
  };
  useEffect(load, [selectedEntity]); // eslint-disable-line react-hooks/exhaustive-deps
  const list = useMemo(() => (mode === "overdue" ? (rows || []).filter((r) => r.overdue) : rows || []), [rows, mode]);
  const t = useMemo(() => ({
    ar: (rows || []).reduce((s, r) => s + Number(r.outstanding || 0), 0),
    overdue: (rows || []).filter((r) => r.overdue).reduce((s, r) => s + Number(r.outstanding || 0), 0),
    need: (rows || []).filter((r) => (r.overdue || r.due_soon) && !r.reminded).length,
  }), [rows]);
  const mark = async (r) => {
    setBusy(r.order_id); setMsg(null);
    try {
      await axios.post(`${API}/collection-reminders/mark`, { customer_id: r.customer_id, order_id: r.order_id, note: `Pengingat penagihan ${r.order_number}` });
      setMsg({ ok: true, text: `${r.customer_name} ditandai sudah diingatkan.` }); load();
    } catch (e) { setMsg({ ok: false, text: errOf(e, "Gagal menandai.") }); } finally { setBusy(""); }
  };
  return (
    <div className="space-y-2" data-testid="m-collection">
      <div className="grid grid-cols-3 gap-1.5">
        <Kpi label="Tagihan" value={formatCurrency(t.ar)} testId="m-collection-total" />
        <Kpi label="Lewat tempo" value={formatCurrency(t.overdue)} tone="text-[#C0392B]" testId="m-collection-overdue" />
        <Kpi label="Perlu diingatkan" value={t.need} tone={t.need ? "text-[#B45309]" : ""} testId="m-collection-need" />
      </div>
      <div className="flex gap-1.5">
        {[["all", "Semua aktif"], ["overdue", "Lewat tempo"]].map(([k, l]) => (
          <button key={k} onClick={() => setMode(k)} data-testid={`m-collection-mode-${k}`}
            className={`rounded-full border px-3 py-1.5 text-[11.5px] font-semibold ${mode === k ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white"}`}>{l}</button>
        ))}
      </div>
      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"} text-xs`} data-testid="m-collection-msg">{msg.text}</div>}
      {rows === null && <p className="p-6 text-center text-sm m-muted">Memuat…</p>}
      {rows && !list.length && <p className="p-6 text-center text-sm m-muted" data-testid="m-collection-empty">Tidak ada tagihan {mode === "overdue" ? "lewat tempo" : "aktif"}.</p>}
      {list.map((r) => (
        <div key={r.order_id} className="m-card p-3" data-testid={`m-collection-row-${r.order_id}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-[13px] font-bold">{r.customer_name}</p>
              <p className="text-[11px] m-muted">{r.order_number} · jatuh tempo {fmtDate(r.due_date)}</p>
            </div>
            <div className="text-right">
              <p className="text-[13px] font-bold tabular-nums">{formatCurrency(r.outstanding)}</p>
              {r.overdue
                ? <span className="inline-flex items-center gap-1 text-[10.5px] font-semibold text-[#C0392B]"><AlertTriangle size={10} /> telat {r.days_late} hari</span>
                : <span className="text-[10.5px] m-muted">{Math.abs(r.days_late)} hari lagi</span>}
            </div>
          </div>
          <div className="mt-2 flex gap-2">
            {r.reminded
              ? <span className="flex flex-1 items-center justify-center gap-1 rounded-lg bg-[#E6F6EC] py-2 text-[11.5px] font-semibold text-[#1B7F4B]" data-testid={`m-collection-reminded-${r.order_id}`}><CheckCircle2 size={13} /> Sudah diingatkan</span>
              : <button className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-[#B45309] py-2 text-[11.5px] font-semibold text-[#B45309]" disabled={busy === r.order_id} onClick={() => mark(r)} data-testid={`m-collection-mark-${r.order_id}`}><BellRing size={13} /> {busy === r.order_id ? "…" : "Tandai diingatkan"}</button>}
            <button className="flex flex-1 items-center justify-center gap-1 rounded-lg border border-[#0058CC] py-2 text-[11.5px] font-semibold text-[#0058CC]" onClick={() => setFu(r)} data-testid={`m-collection-followup-${r.order_id}`}><PhoneCall size={13} /> Catat hasil</button>
          </div>
        </div>
      ))}
      {fu && <FollowupSheet row={fu} onClose={() => setFu(null)} onDone={(m) => { setFu(null); setMsg({ ok: true, text: m }); load(); }} />}
    </div>
  );
}

function FollowupSheet({ row, onClose, onDone }) {
  const [note, setNote] = useState("");
  const [outcome, setOutcome] = useState("contacted");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/customers/${row.customer_id}/followups`, { customer_id: row.customer_id, order_id: row.order_id, note, outcome });
      onDone(`Follow-up untuk ${row.customer_name} dicatat.`);
    } catch (e) { setErr(errOf(e, "Gagal menyimpan.")); setBusy(false); }
  };
  return (
    <div className="m-sheet-wrap" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }} data-testid="m-collection-fu-sheet">
      <div className="m-sheet">
        <div className="m-sheet-grip" />
        <div className="flex items-center justify-between px-4 pb-2">
          <p className="text-[14px] font-bold">Hasil follow-up · {row.customer_name}</p>
          <button onClick={onClose} aria-label="Tutup"><X size={18} /></button>
        </div>
        <div className="m-sheet-scroll space-y-2 px-4">
          <p className="text-[11px] m-muted">{row.order_number} · {formatCurrency(row.outstanding)}{row.overdue ? ` · telat ${row.days_late} hari` : ""}</p>
          <KNSelect value={outcome} onValueChange={setOutcome} options={OUTCOMES} data-testid="m-collection-fu-outcome" />
          <textarea className="w-full rounded-xl border border-[#E5E5EA] p-2.5 text-sm" rows={3} placeholder="Hasil kontak penagihan…" value={note} onChange={(e) => setNote(e.target.value)} data-testid="m-collection-fu-note" />
          {err && <p className="text-[11px] text-[#C62828]" data-testid="m-collection-fu-error">{err}</p>}
          <button className="primary-button w-full justify-center py-3" disabled={busy || !note.trim()} onClick={go} data-testid="m-collection-fu-submit">{busy ? "Menyimpan…" : "Simpan"}</button>
        </div>
      </div>
    </div>
  );
}

function Targets({ selectedEntity }) {
  const [period, setPeriod] = useState(thisMonth());
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    setData(null); setErr("");
    const entity_id = selectedEntity && selectedEntity !== "all" ? selectedEntity : undefined;
    Promise.all([
      axios.get(`${API}/sales/commission`, { params: { period, entity_id } }),
      axios.get(`${API}/sales/commission-history`, { params: { period_type: "month", anchor: period, count: 6, entity_id } }),
      axios.get(`${API}/sales/my-rank`, { params: { period, entity_id } }).catch(() => ({ data: null })),
    ]).then(([c, h, rk]) => setData({ c: c.data, h: Array.isArray(h.data) ? h.data : [], rk: rk.data }))
      .catch((e) => setErr(errOf(e, "Gagal memuat target & komisi.")));
  }, [period, selectedEntity]);
  const c = data?.c || {};
  const k = c.kpi || {};
  const pct = Math.max(0, Math.min(100, Number(c.achievement_pct || 0)));
  const maxH = Math.max(1, ...(data?.h || []).map((x) => Number(x.base_amount ?? x.total_sales ?? 0)));
  return (
    <div className="space-y-2" data-testid="m-targets">
      <input type="month" className="w-full rounded-lg border border-[#E5E5EA] p-2.5 text-sm" value={period} onChange={(e) => setPeriod(e.target.value || thisMonth())} data-testid="m-targets-period" />
      {err && <div className="notice-bar danger text-xs" data-testid="m-targets-error">{err}</div>}
      {!data && !err && <p className="p-6 text-center text-sm m-muted">Memuat…</p>}
      {data && (<>
        <div className="m-card p-3" data-testid="m-targets-progress">
          <div className="flex items-end justify-between">
            <div><p className="text-[10px] font-semibold uppercase text-[#6B6B73]">Pencapaian target</p>
              <p className="text-[20px] font-bold tabular-nums" data-testid="m-targets-pct">{Number(c.achievement_pct || 0).toFixed(1)}%</p></div>
            <p className="text-right text-[11px] m-muted">{formatCurrency(c.base_amount || 0)}<br />dari {formatCurrency(c.target_amount || 0)}</p>
          </div>
          <div className="mt-2 h-2 rounded-full bg-[#EFF0F2]"><div className="h-2 rounded-full bg-[#0058CC]" style={{ width: `${pct}%` }} /></div>
          {!c.target_amount && <p className="mt-1 text-[10.5px] text-[#A05000]">Target periode ini belum diatur manajer.</p>}
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          <Kpi label="Insentif (perkiraan)" value={formatCurrency(c.total_incentive || 0)} tone="text-[#1B7F4B]" testId="m-targets-incentive" />
          <Kpi label="Proyeksi akhir bulan" value={formatCurrency(c.projection_full || 0)} testId="m-targets-projection" />
          <Kpi label="Penjualan" value={formatCurrency(k.total_sales || 0)} testId="m-targets-sales" />
          <Kpi label="Tertagih" value={`${formatCurrency(k.total_collected || 0)} · ${Number(k.collection_rate || 0).toFixed(0)}%`} testId="m-targets-collected" />
          <Kpi label="Piutang" value={formatCurrency(k.ar_outstanding || 0)} testId="m-targets-ar" />
          <Kpi label="Lewat tempo" value={formatCurrency(k.overdue_amount || 0)} tone="text-[#C0392B]" testId="m-targets-overdue" />
        </div>
        <div className="m-card flex items-center gap-3 p-3" data-testid="m-targets-rank">
          <Trophy size={22} className="text-[#B7791F]" />
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase text-[#6B6B73]">Peringkat saya</p>
            <p className="text-[14px] font-bold" data-testid="m-targets-rank-value">
              {data.rk && data.rk.rank && Number(data.rk.total_sales) > 0 ? `#${data.rk.rank} dari ${data.rk.total} sales` : "Belum ada penjualan periode ini"}</p>
          </div>
        </div>
        {(c.breakdown || []).length > 0 && (
          <div className="m-card p-3" data-testid="m-targets-breakdown">
            <p className="mb-1 text-[10px] font-semibold uppercase text-[#6B6B73]">Rincian komisi</p>
            {c.breakdown.slice(0, 8).map((b, i) => (
              <p key={i} className="flex justify-between text-[11.5px]"><span className="truncate">{b.name || b.category || b.sku || "-"}</span>
                <span className="shrink-0 tabular-nums">{formatCurrency(b.commission ?? b.amount ?? 0)}</span></p>
            ))}
          </div>
        )}
        {data.h.length > 0 && (
          <div className="m-card p-3" data-testid="m-targets-history">
            <p className="mb-2 text-[10px] font-semibold uppercase text-[#6B6B73]">6 bulan terakhir</p>
            <div className="flex h-24 items-end gap-1.5">
              {data.h.map((x, i) => {
                const v = Number(x.base_amount ?? x.total_sales ?? 0);
                return (
                  <div key={i} className="flex flex-1 flex-col items-center gap-1">
                    <div className="w-full rounded-t bg-[#0058CC]" style={{ height: `${Math.max(3, (v / maxH) * 80)}px`, opacity: i === data.h.length - 1 ? 1 : 0.45 }} title={formatCurrency(v)} />
                    <span className="text-[9px] m-muted">{String(x.period || x.label || "").slice(5) || i + 1}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </>)}
    </div>
  );
}
