import { useEffect, useState } from "react";
import { CalendarClock, Info } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import KNSelect from "../../../components/KNSelect";
import { formatCurrency, formatDate } from "../../../utils/formatters";

// 23 Okt — formatter baku (dulu toLocaleString tanpa batas desimal → "Rp 20.998,967").
const rp = (v) => formatCurrency(v);
const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;
const BASIS = [{ value: "", label: "Belum diatur" }, { value: "receipt", label: "Tanggal barang diterima" },
  { value: "invoice", label: "Tanggal invoice" }, { value: "document", label: "Tanggal dokumen" }];

// LN-024 KLX-03 — cutoff, tanggal bayar & acuan periode dapat dikonfigurasi (semua PT atau per PT pembayar).
function CutoffForm({ cfg, onSaved }) {
  const [f, setF] = useState({ cutoff_day: cfg.cutoff_day ?? "", payment_day: cfg.payment_day ?? "", basis: cfg.basis ?? "",
    reminder_days: cfg.reminder_days ?? 3 });
  const [scope, setScope] = useState("global");
  const [ents, setEnts] = useState([]);
  useEffect(() => { axios.get(`${API}/entities`).then((r) => setEnts(Array.isArray(r.data) ? r.data : r.data?.items || [])).catch(() => setEnts([])); }, []);
  useEffect(() => {
    if (scope === "global") return;
    axios.get(`${API}/settings/effective`, { params: { entity_id: scope } }).then((r) => {
      const c = r.data.interco_payment || {};
      setF({ cutoff_day: c.cutoff_day ?? "", payment_day: c.payment_day ?? "", basis: c.basis ?? "", reminder_days: c.reminder_days ?? 3 });
    }).catch(() => {});
  }, [scope]);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const save = async () => {
    setErr(""); setOk("");
    const num = (v) => (v === "" || v === null ? null : Math.min(31, Math.max(1, parseInt(v, 10) || 1)));
    try {
      await axios.put(`${API}/settings`, { scope, interco_payment: {
        allow_netting: false, require_full_payment: true, cutoff_day: num(f.cutoff_day), payment_day: num(f.payment_day), basis: f.basis || null,
        reminder_days: Math.max(0, Math.min(30, parseInt(f.reminder_days, 10) || 0)) } });
      setOk("Tersimpan."); onSaved();
    } catch (e) { setErr(errText(e)); }
  };
  return (
    <div data-testid="interco-cutoff-form" className="flex flex-wrap items-end gap-2 text-[12px]">
      <div className="w-56 flex flex-col gap-1">Berlaku untuk (PT pembayar)
        <KNSelect data-testid="interco-cutoff-scope" value={scope} searchable={false} onValueChange={setScope}
                  options={[{ value: "global", label: "Semua PT" }, ...ents.map((e) => ({ value: e.id, label: e.short_name || e.name || e.id }))]} /></div>
      <label className="flex flex-col gap-1">Tanggal cutoff
        <input data-testid="interco-cutoff-day" type="number" min={1} max={31} value={f.cutoff_day} placeholder="—"
               onChange={(e) => setF({ ...f, cutoff_day: e.target.value })} className="field w-24" /></label>
      <label className="flex flex-col gap-1">Tanggal bayar
        <input data-testid="interco-payment-day" type="number" min={1} max={31} value={f.payment_day} placeholder="akhir bulan"
               onChange={(e) => setF({ ...f, payment_day: e.target.value })} className="field w-28" /></label>
      <label className="flex flex-col gap-1">Ingatkan (hari sebelum)
        <input data-testid="interco-reminder-days" type="number" min={0} max={30} value={f.reminder_days}
               onChange={(e) => setF({ ...f, reminder_days: e.target.value })} className="field w-24" /></label>
      <div className="w-56 flex flex-col gap-1">Basis tanggal
        <KNSelect data-testid="interco-cutoff-basis" value={f.basis} options={BASIS} searchable={false} onValueChange={(v) => setF({ ...f, basis: v })} /></div>
      <button type="button" data-testid="interco-cutoff-save" onClick={save}
              className="rounded-lg bg-[#0F172A] text-white px-4 py-2 font-semibold">Simpan pengaturan</button>
      {err && <span className="text-[#C62828]" data-testid="interco-cutoff-error">{err}</span>}
      {ok && <span className="text-[#1B7F4B]" data-testid="interco-cutoff-saved">{ok}</span>}
    </div>
  );
}

export default function IntercoPaymentSchedule({ canConfigure }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const load = () => axios.get(`${API}/interco/payment-schedule`).then((r) => setData(r.data)).catch((e) => setErr(errText(e)));
  useEffect(() => { load(); }, []);
  if (err) return <p className="text-sm text-[#C62828]" data-testid="interco-schedule-error">{err}</p>;
  if (!data) return <div className="h-24 rounded-xl bg-[#F5F5F7] animate-pulse" />;
  const pending = data.cutoff_status !== "configured";
  return (
    <div data-testid="interco-schedule-panel" className="space-y-4">
      <div className={`rounded-xl border p-3 text-[12.5px] flex gap-2 ${pending ? "border-[#F5E0C3] bg-[#FDF6EC] text-[#8A4B08]" : "border-[#BFE3CC] bg-[#F2FBF5] text-[#1B7F4B]"}`}
           data-testid="interco-cutoff-status">
        <Info size={15} className="shrink-0 mt-0.5" />
        <div>
          {pending ? data.note : <>Cutoff tanggal <b>{data.config.cutoff_day}</b> · bayar tanggal <b>{data.config.payment_day || "akhir bulan"}</b> · acuan periode <b>{data.basis_label}</b> (dapat diubah, KLX-03).</>}
          <p className="mt-1">Pembayaran penuh per transaksi, netting antar tagihan <b>dinonaktifkan</b>. Saldo setiap PT dihitung sendiri-sendiri.</p>
        </div>
      </div>
      {canConfigure && <CutoffForm cfg={data.config} onSaved={load} />}
      <div className="flex flex-wrap gap-2">
        {data.pairs.map((p) => (
          <div key={`${p.payer_entity_id}>${p.payee_entity_id}`} className="rounded-lg border border-[#E5E5EA] bg-white px-3 py-2 text-[12px]"
               data-testid={`interco-pair-${p.payer_entity_id}-${p.payee_entity_id}`}>
            <b>{p.payer_entity_name}</b> → {p.payee_entity_name}: {p.count} transaksi · {rp(p.remaining)}
          </div>
        ))}
      </div>
      <div className="overflow-x-auto rounded-xl border border-[#E5E5EA] bg-white">
        <table className="min-w-full text-[12.5px]">
          <thead className="bg-[#F7F7F9] text-left text-[#3A3A3C]">
            <tr>{["No.", "Pembayar → Penerima", "Status", "Diterima", "Invoice", "Sisa (bayar penuh)", "Umur", "Periode bayar"].map((h) => <th key={h} className="px-3 py-2 font-semibold whitespace-nowrap">{h}</th>)}</tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.interco_id} className="border-t border-[#F0F0F3]" data-testid={`interco-schedule-row-${r.interco_id}`}>
                <td className="px-3 py-2 font-mono">{r.number}</td>
                <td className="px-3 py-2">{r.payer_entity_name} → {r.payee_entity_name}</td>
                <td className="px-3 py-2">{r.status}</td>
                <td className="px-3 py-2">{formatDate(r.received_at) || "—"}</td>
                <td className="px-3 py-2">{formatDate(r.invoiced_at) || "—"}</td>
                <td className="px-3 py-2 text-right tabular-nums">{rp(r.remaining)}</td>
                <td className="px-3 py-2 tabular-nums">{r.age_days ?? "—"} hari</td>
                <td className="px-3 py-2" data-testid={`interco-schedule-period-${r.interco_id}`}>
                  {r.period ? <span className="inline-flex items-center gap-1"><CalendarClock size={12} /> {r.pay_date}</span>
                            : <span className="text-[#B45309]">Menunggu KLX-03</span>}
                </td>
              </tr>
            ))}
            {!data.rows.length && <tr><td colSpan={8} className="px-3 py-6 text-center text-[#8E8E93]">Tidak ada utang antar-PT terbuka.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
