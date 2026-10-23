import { useCallback, useEffect, useState } from "react";
import { Check, Factory, Loader2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import KNSelect from "../../components/KNSelect";

const MODES = [
  { value: "supplier", label: "Supplier" },
  { value: "makloon", label: "Makloon" },
  { value: "both", label: "Keduanya" },
];

/** P05 IMP-19 / DEC-07 — sumber restock per artikel. Tanpa default: "belum diatur" diisi MD. */
function SourceRow({ t, canEdit, onSaved }) {
  const cur = t.restock_source?.mode || "";
  const [mode, setMode] = useState(cur);
  const [note, setNote] = useState(t.restock_source?.note || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const save = async () => {
    setBusy(true); setErr("");
    try { await axios.put(`${API}/product-templates/${t.id}/restock-source`, { mode, note }); onSaved?.(); }
    catch (e) { setErr(apiErrorText(e, "Gagal menyimpan.")); }
    finally { setBusy(false); }
  };
  return (
    <li className="flex flex-wrap items-center gap-2 px-3 py-2" data-testid={`restock-row-${t.id}`}>
      <div className="min-w-[160px] flex-1">
        <p className="text-[12px] font-semibold">{t.name}</p>
        <p className="text-[10.5px] text-[#8E8E93]">{t.sku_prefix || "—"} · {t.line_code || "—"}</p>
      </div>
      {!cur && <span className="rounded-full bg-[#FFF3E0] px-2 py-0.5 text-[10px] font-bold text-[#9A5B00]" data-testid={`restock-unmapped-${t.id}`}>belum diatur</span>}
      <KNSelect data-testid={`restock-mode-${t.id}`} disabled={!canEdit} className="input !w-auto text-[12px]" value={mode} onValueChange={setMode}
        placeholder="— pilih —" options={MODES.map((m) => ({ value: m.value, label: m.label }))} />
      {canEdit && <input data-testid={`restock-note-${t.id}`} className="input !w-44 text-[12px]" placeholder="Catatan (opsional)" value={note} onChange={(e) => setNote(e.target.value)} />}
      {canEdit && (
        <button type="button" data-testid={`restock-save-${t.id}`} disabled={!mode || busy} onClick={save} className="primary-button px-2.5 py-1 text-[11.5px] disabled:opacity-40">
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} Simpan
        </button>
      )}
      {err && <p className="w-full text-[11px] text-[#C0392B]" data-testid={`restock-error-${t.id}`}>{err}</p>}
    </li>
  );
}

export default function RestockSourcePanel({ canEdit = false }) {
  const [status, setStatus] = useState("unmapped");
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try { setData((await axios.get(`${API}/restock-sources`, { params: { status, q, limit: 60 } })).data); setError(""); }
    catch (e) { setError(apiErrorText(e, "Gagal memuat sumber restock.")); }
  }, [status, q]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  return (
    <section className="rounded-lg border border-[#EFF0F2] bg-white" data-testid="restock-source-panel">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#EFF0F2] px-3 py-2">
        <Factory size={15} className="text-[#0058CC]" />
        <h2 className="text-[13px] font-bold">Sumber Restock Artikel</h2>
        <span className="text-[11px] text-[#6B6B73]" data-testid="restock-counts">{data ? `${data.mapped} diatur · ${data.unmapped} belum diatur` : ""}</span>
        <div className="ml-auto flex gap-1">
          {[["unmapped", "Belum diatur"], ["mapped", "Sudah diatur"], ["", "Semua"]].map(([v, l]) => (
            <button key={v || "all"} type="button" data-testid={`restock-filter-${v || "all"}`} onClick={() => setStatus(v)}
              className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${status === v ? "bg-[#0058CC] text-white" : "bg-[#F2F3F5] text-[#3C3C43]"}`}>{l}</button>
          ))}
        </div>
        <input data-testid="restock-search" className="input !w-48 text-[12px]" placeholder="Cari artikel…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <p className="px-3 pt-2 text-[10.5px] text-[#6B6B73]">Berlaku untuk barang jadi. Artikel "Keduanya" wajib alasan setiap kali PR/PO/Order Makloon dibuat.</p>
      {error && <p className="px-3 py-1 text-[11px] text-[#C0392B]" data-testid="restock-load-error">{error}</p>}
      <ul className="max-h-[420px] divide-y divide-[#F2F3F5] overflow-y-auto">
        {(data?.items || []).map((t) => <SourceRow key={`${t.id}-${t.restock_source?.mode || ""}`} t={t} canEdit={canEdit} onSaved={load} />)}
        {data && !data.items.length && <li className="py-6 text-center text-[12px] text-[#8E8E93]" data-testid="restock-empty">Tidak ada artikel.</li>}
      </ul>
    </section>
  );
}
