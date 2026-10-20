/** P03 IMP-27 — penerimaan AKTUAL per roll: pilih/scan roll yang tiba, rusak, staging/bin, exception. */
import { useCallback, useEffect, useState } from "react";
import { roleIs } from "../../../config/roles";
import { PackageCheck, ScanLine, AlertTriangle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { notifySuccess } from "../../../utils/feedback";
import ErrorNotice from "../../../components/ErrorNotice";
import KNSelect from "../../../components/KNSelect";
import { ReceiptRollTable, ReceiptResults } from "./ReceiptRollTable";
import ReceiptExceptions from "./ReceiptExceptions";
import { STATE_TXT } from "./transferConstants";

const SUPERVISOR = ["warehouse_admin", "manager", "admin"];

export default function TransferReceiptPanel({ transfer, user, onChanged }) {
  const [data, setData] = useState(null);
  const [picked, setPicked] = useState({});
  const [scan, setScan] = useState("");
  const [binId, setBinId] = useState("");
  const [ruleReason, setRuleReason] = useState("");
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // FE-11 — status MUAT dipisah dari error AKSI: gagal GET pertama tampil sebagai error + Coba lagi,
  // bukan "Memuat…" selamanya dan bukan pula "tidak ada roll".
  const [loadErr, setLoadErr] = useState("");
  const [loadingReceipt, setLoadingReceipt] = useState(true);
  const open = ["dispatched", "partially_received"].includes(transfer.status);
  const isSup = roleIs(user?.role, SUPERVISOR);   // FE-04 — sama dengan supervisor di server (kenal peran acuan)

  const load = useCallback(async () => {
    setLoadingReceipt(true); setLoadErr("");
    try {
      const r = await axios.get(`${API}/transfers/${transfer.id}/receipt`);
      setData(r.data);
    } catch (e) { setLoadErr(apiErrorText(e, "Gagal memuat penerimaan.")); }
    finally { setLoadingReceipt(false); }
  }, [transfer.id]);
  useEffect(() => { load(); }, [load]);

  const submit = async (lines) => {
    if (!lines.length) { setErr("Pilih atau scan minimal satu roll yang tiba."); return; }
    const bad = lines.find((l) => l.outcome === "damaged" && (l.note || "").trim().length < 5);
    if (bad) { setErr("Roll rusak wajib diberi keterangan kerusakan (min. 5 huruf)."); return; }
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/transfers/${transfer.id}/receive`, {
        lines, bin_id: binId, rule_exception_reason: ruleReason, note: "" });
      setResults(r.data.results || []);
      setData(r.data.summary);
      setPicked({}); setScan("");
      const ok = (r.data.results || []).filter((x) => ["received", "damaged", "hold"].includes(x.result)).length;
      notifySuccess("Penerimaan dicatat", `${ok} roll masuk gudang tujuan.`);
      onChanged?.(r.data.transfer_status);
    } catch (e) { setErr(apiErrorText(e, "Gagal mencatat penerimaan.")); } finally { setBusy(false); }
  };

  const fromPicked = () => Object.entries(picked).filter(([, v]) => v.on)
    .map(([roll_id, v]) => ({ roll_id, outcome: v.outcome || "received", note: v.note || "" }));

  if (!data && loadErr && !loadingReceipt) {
    return (
      <div data-testid="transfer-receipt-load-failed" className="rounded-xl border border-[#F3D6D3] bg-[#FFF8F7] p-3">
        <p className="mb-1 text-[11px] text-[#3C3C43]">Penerimaan transfer <b>{transfer.code || transfer.number || transfer.id}</b> belum bisa dimuat.</p>
        <ErrorNotice message={loadErr} onRetry={load} testId="transfer-receipt-load-error" />
      </div>
    );
  }
  if (!data) return <div data-testid="transfer-receipt-loading" className="text-xs text-[#8E8E93]">Memuat penerimaan…</div>;
  const blocked = results.some((x) => x.result === "blocked_rules");
  return (
    <div data-testid="transfer-receipt-panel" className="rounded-xl border border-[#D7E3F7] bg-[#F7FAFF] p-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <PackageCheck size={15} className="text-[#0058CC]" />
        <h4 className="text-sm font-semibold">Penerimaan per roll</h4>
        <span data-testid="transfer-receipt-counts" className="ml-auto text-[11px] text-[#3C3C43]">
          {Object.entries(data.counts || {}).map(([k, v]) => `${STATE_TXT[k] || k}: ${v}`).join(" · ")}
        </span>
      </div>
      {data.legacy_note && <p data-testid="transfer-receipt-legacy" className="rounded-md bg-[#FFF7E6] px-2 py-1 text-[11px] text-[#8A5A00]">{data.legacy_note}</p>}
      {data.sales_order_number && (
        <p data-testid="transfer-receipt-so" className="text-[11px] text-[#3C3C43]">
          Untuk <b>{data.sales_order_number}</b> — roll berkomitmen tetap terkunci untuk SO ini. Tiba di gudang ≠ terkirim ke pelanggan (SJ pelanggan dibuat terpisah).
        </p>
      )}
      <ReceiptRollTable rows={data.rolls} picked={picked} setPicked={setPicked} editable={open} />
      {open && (
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="flex gap-1">
            <input data-testid="transfer-receipt-scan" value={scan} onChange={(e) => setScan(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && scan.trim()) submit([{ code: scan.trim() }]); }}
              placeholder="Scan / ketik nomor roll lalu Enter" className="flex-1 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-xs" />
            <button data-testid="transfer-receipt-scan-btn" disabled={busy || !scan.trim()} onClick={() => submit([{ code: scan.trim() }])}
              className="rounded-lg border border-[#0058CC] px-2 text-xs text-[#0058CC] disabled:opacity-40"><ScanLine size={14} /></button>
          </div>
          <KNSelect data-testid="transfer-receipt-bin" value={binId} onValueChange={setBinId} searchable
            options={[{ value: "", label: "Simpan nanti (masuk antrean putaway)" },
              ...(data.dest_bins || []).map((b) => ({ value: b.id, label: `${b.function === "staging" ? "[Staging] " : ""}${b.code} · ${b.path}` }))]}
            placeholder="Bin / staging tujuan" />
          {(blocked || ruleReason) && isSup && (
            <input data-testid="transfer-receipt-rule-reason" value={ruleReason} onChange={(e) => setRuleReason(e.target.value)}
              placeholder="Alasan pengecualian aturan gudang (roll masuk sebagai DITAHAN)" className="sm:col-span-2 rounded-lg border border-[#E5B34A] bg-white px-2 py-1.5 text-xs" />
          )}
          <button data-testid="transfer-receipt-submit" disabled={busy} onClick={() => submit(fromPicked())}
            className="sm:col-span-2 rounded-full bg-[#34C759] px-4 py-2 text-sm font-medium text-white hover:bg-[#28A745] disabled:opacity-50">
            {busy ? "Menyimpan…" : `Terima roll terpilih (${fromPicked().length})`}
          </button>
        </div>
      )}
      {blocked && !isSup && (
        <p data-testid="transfer-receipt-blocked-note" className="flex items-center gap-1 text-[11px] text-[#B4231F]">
          <AlertTriangle size={12} /> Ada roll ditolak aturan gudang tujuan — minta Admin Gudang/Manajer memutuskan.
        </p>
      )}
      <ErrorNotice message={err} onDismiss={() => setErr("")} testId="transfer-receipt-error" />
      <ErrorNotice message={loadErr} onRetry={load} onDismiss={() => setLoadErr("")} testId="transfer-receipt-load-error" />
      <ReceiptResults results={results} />
      <ReceiptExceptions transfer={transfer} data={data} open={open} isSup={isSup}
        rolls={data.rolls} onDone={(s) => { setData(s); onChanged?.(); }} />
    </div>
  );
}
