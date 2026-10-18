import { useEffect, useState } from "react";
import { AlertOctagon, AlertTriangle, Loader2, MessageCircleQuestion, RefreshCw } from "lucide-react";
import { toast } from "../../hooks/use-toast";
import { fetchInsights, scanInsights } from "./tanyaApi";

const KIND = { sales_drop: "Penjualan", ar_overdue: "Piutang", stock_out: "Stok", po_late: "Pembelian" };

/** Tab Peringatan: anomali harian (dihitung server tiap pagi) + tombol lanjut bertanya. */
export function TanyaInsights({ canScan, onAsk, refreshKey }) {
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => fetchInsights().then(setItems).catch(() => setItems([]));
  useEffect(() => { load(); }, [refreshKey]);
  const scan = async () => {
    setBusy(true);
    try { const r = await scanInsights(); toast({ title: `Pindai selesai · ${r.insights} peringatan` }); await load(); }
    catch (e) { toast({ title: "Pindai gagal", description: e?.response?.data?.detail || "", variant: "destructive" }); }
    finally { setBusy(false); }
  };
  return (
    <div className="tanya-insights" data-testid="tanya-insights">
      <div className="tanya-insights-head">
        <span className="tanya-kicker">Dipindai otomatis tiap pagi 07.00 WIB</span>
        {canScan && (
          <button type="button" className="tanya-chip" onClick={scan} disabled={busy} data-testid="tanya-insights-scan">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin inline" /> : <RefreshCw className="h-3.5 w-3.5 inline" />} Pindai sekarang
          </button>
        )}
      </div>
      {items === null && <div className="tanya-loading"><Loader2 className="h-4 w-4 animate-spin" /> Memuat…</div>}
      {items?.length === 0 && <div className="tanya-empty" data-testid="tanya-insights-empty">Tidak ada anomali 7 hari terakhir.</div>}
      {(items || []).map((it) => (
        <article key={it.key} className={`tanya-insight ${it.severity}`} data-testid={`tanya-insight-${it.kind}`}>
          <div className="tanya-insight-top">
            {it.severity === "critical" ? <AlertOctagon className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
            <span className="tanya-insight-kind">{KIND[it.kind] || it.kind} · {it.date}</span>
          </div>
          <h4 className="tanya-insight-title">{it.title}</h4>
          <p className="tanya-insight-body">{it.body}</p>
          <button type="button" className="tanya-chip" onClick={() => onAsk(it.question)} data-testid={`tanya-insight-ask-${it.kind}`}>
            <MessageCircleQuestion className="h-3.5 w-3.5 inline" /> Tanyakan ke asisten
          </button>
        </article>
      ))}
    </div>
  );
}
