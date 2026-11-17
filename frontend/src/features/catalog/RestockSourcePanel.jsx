import { useCallback, useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import KNSelect from "../../components/KNSelect";
import StatusBadge from "../../components/StatusBadge";
import { HelpTip, ListToolbar, SearchInput } from "../../components/ListPageParts";

const MODES = [
  { value: "supplier", label: "Supplier" },
  { value: "makloon", label: "Makloon" },
  { value: "both", label: "Keduanya" },
];
// Pola UI 16 Nov (04_POLA_UI §1.2) — saringan status = dropdown (dulu deret chip "Belum diatur · Sudah diatur · Semua").
const STATUS = [
  { value: "unmapped", label: "Belum diatur" },
  { value: "mapped", label: "Sudah diatur" },
  { value: "", label: "Semua artikel" },
];
const COMPACT = "!h-auto !w-auto min-w-[150px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13";

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
        <p className="text-fs-13 font-semibold">{t.name}</p>
        <p className="text-fs-12 text-kn-text-2">{t.sku_prefix || "—"} · {t.line_code || "—"}</p>
      </div>
      {!cur && <StatusBadge tone="warning" icon="alert" label="belum diatur" testId={`restock-unmapped-${t.id}`} />}
      <KNSelect data-testid={`restock-mode-${t.id}`} disabled={!canEdit} className={COMPACT} value={mode} onValueChange={setMode}
        placeholder="— pilih —" options={MODES.map((m) => ({ value: m.value, label: m.label }))} />
      {canEdit && <input data-testid={`restock-note-${t.id}`} className="field w-44 text-fs-13" placeholder="Catatan (opsional)"
        aria-label="Catatan sumber restock" value={note} onChange={(e) => setNote(e.target.value)} />}
      {canEdit && (
        <button type="button" data-testid={`restock-save-${t.id}`} disabled={!mode || busy} onClick={save} className="primary-button btn-sm">
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} Simpan
        </button>
      )}
      {err && <p className="w-full text-fs-12 text-kn-danger-text" data-testid={`restock-error-${t.id}`}>{err}</p>}
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
    <section className="section-card section-pad" data-testid="restock-source-panel">
      <ListToolbar testId="restock-toolbar">
        <SearchInput testId="restock-search" placeholder="Cari artikel…" value={q} onChange={setQ} className="min-w-[200px] flex-1 sm:max-w-[280px]" />
        <KNSelect data-testid="restock-filter" aria-label="Status sumber restock" className={COMPACT} value={status}
          onValueChange={(v) => setStatus(v || "")} options={STATUS} />
        <span className="whitespace-nowrap text-fs-12 text-kn-text-2" data-testid="restock-counts">{data ? `${data.mapped} diatur · ${data.unmapped} belum diatur` : ""}</span>
        <HelpTip testId="restock-help" text={'Berlaku untuk barang jadi. Artikel "Keduanya" wajib alasan setiap kali PR/PO/Order Makloon dibuat.'} />
      </ListToolbar>
      {error && <p className="py-1 text-fs-12 text-kn-danger-text" data-testid="restock-load-error">{error}</p>}
      <ul className="max-h-[420px] divide-y divide-kn-divider overflow-y-auto">
        {(data?.items || []).map((t) => <SourceRow key={`${t.id}-${t.restock_source?.mode || ""}`} t={t} canEdit={canEdit} onSaved={load} />)}
        {data && !data.items.length && <li className="py-6 text-center text-fs-12 text-kn-text-2" data-testid="restock-empty">Tidak ada artikel.</li>}
      </ul>
    </section>
  );
}
