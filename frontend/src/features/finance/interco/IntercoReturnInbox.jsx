import { useCallback, useEffect, useState } from "react";
import { Inbox, Check, Truck } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { formatCurrency } from "../../../utils/formatters";
import { DispositionRow, DispositionActionBar } from "../../sales/ReturnDispositionPanel";
import LoadingLine from "../../../components/LoadingLine";
import ErrorNotice from "../../../components/ErrorNotice";

const errText = (e) => e.response?.data?.detail?.message || e.response?.data?.detail || e.message;
const ST = { draft: "Menunggu diterima", approved: "Diterima · tunggu barang" };

function IncomingList({ rows, canAct, onDone }) {
  const [msg, setMsg] = useState("");
  const act = async (r, path) => {
    setMsg("");
    try { await axios.post(`${API}/interco/returns/${r.id}/${path}`, { note: "" }); onDone(); }
    catch (e) { setMsg(errText(e)); }
  };
  if (!rows.length) return <p className="text-xs text-[#8E8E93]" data-testid="ic-inbox-incoming-empty">Tidak ada retur internal yang menunggu diterima.</p>;
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.id} className="rounded-lg border border-[#E5E5EA] bg-white p-3 text-xs" data-testid={`ic-inbox-incoming-${r.id}`}>
          <div className="flex flex-wrap items-center gap-2">
            <b className="font-mono">{r.number}</b>
            <span className="text-[#6E6E73]">dari {r.buyer_entity_name} · kembar {r.counterpart_number} · {r.doc_date}</span>
            <span className="rounded-full bg-[#FFF3DC] px-2 py-0.5 font-semibold text-[#9A6700]">{ST[r.status] || r.status}</span>
            <span className="rounded-full bg-[#EAF2FF] px-2 py-0.5 text-[#0058CC]">Wajib diterima</span>
            <b className="ml-auto">{formatCurrency(r.grand_total || 0)}</b>
          </div>
          <p className="mt-1 text-[#3C3C43]">{(r.items || []).map((i) => `${i.product_name || i.sku} ${i.quantity} ${i.unit}`).join(" · ")}</p>
          <p className="text-[#6E6E73]">Alasan: {r.reason}{r.source_sales_return_number ? ` · kasus ${r.source_sales_return_number}` : ""}
            {r.warehouse_transfer_code ? ` · tugas gudang ${r.warehouse_transfer_code} (${r.warehouse_transfer_status})` : ""}</p>
          {canAct && (
            <div className="mt-2 flex flex-wrap gap-2">
              {r.status === "draft" && <button type="button" data-testid={`ic-inbox-accept-${r.id}`} onClick={() => act(r, "approve")}
                className="primary-button !px-3 !py-1 text-xs"><Check size={12} /> Terima retur</button>}
              {r.status === "approved" && !r.warehouse_transfer_code && <button type="button" data-testid={`ic-inbox-task-${r.id}`} onClick={() => act(r, "warehouse-task")}
                className="secondary-button !px-3 !py-1 text-xs"><Truck size={12} /> Terbitkan tugas gudang</button>}
            </div>
          )}
        </div>
      ))}
      {msg && <p className="text-xs text-[#C62828]" data-testid="ic-inbox-msg">{msg}</p>}
    </div>
  );
}

function CaseCard({ c, canAct, onDone }) {
  const [sel, setSel] = useState([]);
  const [photos, setPhotos] = useState(c.photos || []);
  const imgs = photos.filter((a) => (a.content_type || "").startsWith("image/"));
  const toggle = (id) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  return (
    <div className="rounded-lg border border-[#E5E5EA] bg-white p-3" data-testid={`ic-inbox-case-${c.return_id}`}>
      <p className="mb-1 text-xs font-semibold">Kasus {c.return_number} · batas retur supplier {c.supplier_window_days} hari dari terima</p>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px]"><tbody className="divide-y divide-[#F2F2F5]">
          {c.rows.map((r) => <DispositionRow key={r.roll_id} r={r} checked={sel.includes(r.roll_id)} onToggle={() => toggle(r.roll_id)} />)}
        </tbody></table>
      </div>
      {canAct && sel.length > 0 && (
        <DispositionActionBar returnId={c.return_id} imgs={imgs} stage="supplier_pending" sel={sel} rows={c.rows}
          onDone={() => { setSel([]); onDone(); }} onPhoto={() => axios.get(`${API}/return-dispositions/inbox`)
            .then((x) => setPhotos((x.data.cases.find((k) => k.return_id === c.return_id) || {}).photos || photos))} />
      )}
    </div>
  );
}

// LN-093 — meja PT pemasok (CST): terima retur internal wajib + putuskan nasib roll tanpa akses ke PT pengembali.
export default function IntercoReturnInbox({ entityId, canAct }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  // 23 Okt — dulu kosong total selama memuat, dan galat muat DITELAN jadi daftar kosong ("tidak ada retur")
  // sehingga PT pemasok mengira tak ada yang perlu diputus.
  const load = useCallback(() => {
    setErr("");
    axios.get(`${API}/return-dispositions/inbox`, { params: entityId ? { entity_id: entityId } : {} })
      .then((r) => setData(r.data)).catch((e) => { setErr(e); setData((d) => d || { incoming: [], cases: [], counts: {} }); });
  }, [entityId]);
  useEffect(() => { load(); }, [load]);
  if (!data) return <LoadingLine text="Memuat retur internal…" testId="ic-inbox-loading" />;
  return (
    // G1-32 — tab Retur Masuk dibungkus kartu seperti tab lain (dulu teks lepas di latar halaman).
    <div className="section-card"><div className="section-body space-y-4" data-testid="ic-return-inbox">
      {err && <ErrorNotice message={err} onRetry={load} testId="ic-inbox-error" />}
      <div>
        <h3 className="mb-2 inline-flex items-center gap-1.5 text-sm font-semibold"><Inbox size={15} /> Retur internal masuk ({data.counts.incoming || 0})</h3>
        <IncomingList rows={data.incoming} canAct={canAct} onDone={load} />
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold">Roll menunggu keputusan ({data.counts.rolls || 0})</h3>
        {!data.cases.length && <p className="text-xs text-[#8E8E93]" data-testid="ic-inbox-cases-empty">Tidak ada roll yang menunggu keputusan simpan / retur supplier / buang BS.</p>}
        <div className="space-y-3">{data.cases.map((c) => <CaseCard key={c.return_id} c={c} canAct={canAct} onDone={load} />)}</div>
      </div>
    </div></div>
  );
}
