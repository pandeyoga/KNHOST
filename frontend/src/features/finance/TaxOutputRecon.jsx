import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, Scale, Wand2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, todayWib } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import KNMonthPicker from "../../components/KNMonthPicker";
import { MetricRow } from "../../components/ListPageParts";
import { useEntityScope } from "../../context/EntityScopeContext";
import { useAppNav } from "../../context/AppNavContext";
import { ROW_TARGET } from "../sales_admin/workDeskApi";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";

/**
 * TX-T2 (TX-05) — Pencocokan PPN keluaran per PT per masa: PPN di faktur, di dokumen retur, di buku besar (akun PPN
 * keluaran pemetaan PT), selisih, lalu daftar penyebabnya. Sumber: `GET /api/tax/output-reconciliation` (rumus satu
 * tempat dengan penjaga INV-TAX-OUT-01). "Semua PT" hanya baca → panel meminta satu PT (02 §3.4 N3).
 * Baris sumber bisa dibuka (L8): pesanan → detail pesanan, surat jalan → Logistik.
 */
const SEBAB = [
  { key: "surat_jalan_tanpa_faktur", label: "Surat jalan tanpa faktur",
    hint: "PPN sudah dijurnal saat barang keluar, faktur terbit untuk sumber ini di masa ini belum ada atau kurang." },
  { key: "faktur_tanpa_jurnal", label: "Faktur tanpa jurnal",
    hint: "Faktur (atau dokumen retur) masa ini lebih besar dari jurnal PPN sumbernya di masa ini." },
  { key: "retur_tanpa_dokumen", label: "Retur tanpa dokumen pajak",
    hint: "PPN dibalik nota kredit, dokumen pajak returnya belum terbit." },
];
const JENIS = { pesanan: "Pesanan", surat_jalan: "Surat jalan", retur: "Nota kredit", antar_pt: "Antar-PT",
  retur_antar_pt: "Retur antar-PT" };

function sumberTeks(r) {
  if (r.jenis === "retur") return `${r.credit_note_number || "Nota kredit"}${r.order_number ? ` · ${r.order_number}` : ""}`;
  if (r.jenis === "surat_jalan") return `${r.order_number || "Pesanan"} · ${r.shipment_no || ""}`;
  if (r.jenis === "pesanan") return r.order_number || "Pesanan";
  return r.label || JENIS[r.jenis] || "—";
}

export default function TaxOutputRecon({ canRebuild = false }) {
  const { selectedEntity } = useEntityScope();
  const nav = useAppNav();
  const satuPt = !!selectedEntity && selectedEntity !== "all";
  const [period, setPeriod] = useState(() => todayWib().slice(0, 7));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [cari, setCari] = useState("");   // saring baris sebab menurut nomor pesanan / surat jalan / nota
  const rebuildIntent = useIntentKey("fktb");

  const load = useCallback(async () => {
    if (!satuPt || !period) { setData(null); return; }
    setLoading(true);
    setError("");
    try {
      const r = await axios.get(`${API}/tax/output-reconciliation`, { params: { period, entity_id: selectedEntity } });
      setData(r.data || null);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat pencocokan PPN keluaran."));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [period, selectedEntity, satuPt]);
  useEffect(() => { load(); }, [load]);

  const rebuild = async () => {
    if (busy) return;
    setNote("");
    setBusy(true);
    try {
      const body = { period };
      const r = await rebuildIntent.send({ aksi: "rebuild", ...body },
        (k) => moneyPost(`${API}/tax-invoices/drafts/rebuild`, body, k));
      const j = r?.data || r || {};
      setNote(j.created ? `${j.created} draf baru dibuat.` : "Tidak ada draf baru: semua sumber sudah punya dokumen.");
      await load();
    } catch (e) {
      setError(apiErrorText(e, "Gagal membangun ulang draf."));
    } finally {
      setBusy(false);
    }
  };

  // L8 — sumber dibuka di detail pesanan (surat jalan & nota kreditnya tampil di sana); jurnal di Buku Besar.
  const buka = (r) => {
    if (r.order_id && nav?.openDocument) nav.openDocument({ ...ROW_TARGET.sales_order, focus_id: r.order_id,
      number: r.order_number });
  };
  const bukaJurnal = (j) => nav?.openDocument && nav.openDocument({ view: "general-ledger",
    focus_type: "journal_entry", focus_id: j.id, number: j.number });

  const belum = Number(data?.unexplained || 0);
  return (
    <div className="section-card" data-testid="fkt-recon">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <Scale size={16} className="shrink-0 text-kn-action" aria-hidden="true" />
          <h2 className="text-fs-14 font-bold">Pencocokan PPN keluaran</h2>
        </div>
        <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="fkt-recon-refresh"
          onClick={load} disabled={loading || !satuPt}>
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} aria-hidden="true" /> Muat ulang
        </button>
      </div>
      <div className="section-body space-y-3">
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1 text-fs-12 text-kn-text-2">
            Masa pajak
            <KNMonthPicker data-testid="fkt-recon-period" value={period} onChange={(v) => setPeriod(v || "")}
              placeholder="Pilih masa" />
          </div>
          {data && (
            <label className="flex flex-col gap-1 text-fs-12 text-kn-text-2">
              Cari sumber
              <input type="search" data-testid="fkt-recon-search" className="field" value={cari}
                placeholder="Nomor pesanan, surat jalan, nota" onChange={(e) => setCari(e.target.value)} />
            </label>
          )}
          {canRebuild && satuPt && (
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="fkt-recon-rebuild"
                onClick={rebuild} disabled={busy}>
                <Wand2 size={13} aria-hidden="true" /> Bangun ulang draf masa ini
              </button>
              <span className="text-fs-12 text-kn-text-2">Draf yang dibuang tidak dibuat ulang.</span>
            </div>
          )}
        </div>
        {!satuPt && (
          <p className="text-fs-12 text-kn-text-2" data-testid="fkt-recon-pilih-pt">
            Pilih satu PT di bilah atas untuk melihat pencocokan PPN keluaran (mode Semua PT hanya untuk melihat daftar).
          </p>
        )}
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="fkt-recon-error" />
        {note && <p className="text-fs-12 text-kn-text-2" data-testid="fkt-recon-note">{note}</p>}
        {satuPt && loading && !data && <p className="text-fs-12 text-kn-text-2">Memuat…</p>}
        {data && (
          <>
            <MetricRow testId="fkt-recon-angka" items={[
              { label: "PPN di faktur", value: formatCurrency(data.faktur_ppn) },
              { label: "PPN di dokumen retur", value: formatCurrency(data.retur_ppn) },
              { label: "PPN di buku besar", value: formatCurrency(data.gl_ppn),
                hint: `Akun ${(data.accounts || []).join(", ")}` },
              { label: "Selisih", value: formatCurrency(data.difference),
                hint: "Buku besar − (faktur − dokumen retur)" },
            ]} />
            {SEBAB.map((s) => {
              const semua = data.causes?.[s.key] || [];
              const kata = cari.trim().toLowerCase();
              const rows = kata ? semua.filter((r) => sumberTeks(r).toLowerCase().includes(kata)) : semua;
              if (!semua.length) return null;
              return (
                <section key={s.key} data-testid={`fkt-recon-${s.key}`}>
                  <h3 className="text-fs-13 font-semibold">
                    {s.label} ({kata ? `${rows.length} dari ${semua.length}` : semua.length})
                  </h3>
                  <p className="text-fs-12 text-kn-text-2">{s.hint}</p>
                  <div className="mt-1 overflow-x-auto rounded-md border border-kn-divider">
                    <table className="data-table head-wrap">
                      <thead>
                        <tr>
                          <th>Sumber</th>
                          <th className="text-right">PPN di jurnal</th>
                          <th className="text-right">PPN di dokumen</th>
                          <th className="text-right">Selisih</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.length === 0 && (
                          <tr><td colSpan={4} className="py-3 text-center text-kn-text-2">Tidak ada sumber yang cocok dengan pencarian.</td></tr>
                        )}
                        {rows.map((r, i) => (
                          <tr key={`${s.key}-${i}`}>
                            <td>
                              <span className="block text-fs-12 text-kn-text-2">{JENIS[r.jenis] || "Sumber"}</span>
                              {r.order_id ? (
                                <button type="button" className="link-button whitespace-nowrap" onClick={() => buka(r)}>
                                  {sumberTeks(r)}
                                </button>
                              ) : <span>{sumberTeks(r)}</span>}
                            </td>
                            <td className="text-right tabular-nums">{formatCurrency(r.gl_ppn)}</td>
                            <td className="text-right tabular-nums">{formatCurrency(r.doc_ppn)}</td>
                            <td className="text-right tabular-nums font-semibold">{formatCurrency(r.amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              );
            })}
            {SEBAB.every((s) => !(data.causes?.[s.key] || []).length) && belum === 0 && (
              <p className="flex items-center gap-1 text-fs-12 text-kn-success-text" data-testid="fkt-recon-cocok">
                <CheckCircle2 size={13} aria-hidden="true" /> Faktur, dokumen retur, dan buku besar cocok untuk masa ini.
              </p>
            )}
            <div data-testid="fkt-recon-belum"
              className={`rounded-md px-3 py-2 text-fs-13 ${belum !== 0 ? "bg-kn-warning-soft text-kn-warning-text" : "bg-kn-neutral-soft text-kn-text-2"}`}>
              <span className="flex flex-wrap items-center gap-1">
                {belum !== 0 && <AlertTriangle size={13} aria-hidden="true" />}
                Belum terjelaskan: <b className="whitespace-nowrap tabular-nums">{formatCurrency(belum)}</b>
              </span>
              {(data.unexplained_journals || []).length > 0 && (
                <ul className="mt-1 list-disc pl-5 text-fs-12">
                  {data.unexplained_journals.map((j) => (
                    <li key={j.id}>
                      <button type="button" className="link-button" onClick={() => bukaJurnal(j)}>{j.number}</button>
                      {" "}{j.description || ""} · <span className="whitespace-nowrap">{formatCurrency(j.amount)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

