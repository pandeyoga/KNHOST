import { useCallback, useEffect, useMemo, useState } from "react";
import { PackageCheck, Printer, RefreshCw, Scissors, Search } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { KNSelect } from "../../components/KNSelect";
import { apiErrorText } from "../../utils/apiError";
import { formatQty } from "../../utils/formatters";
import { printSampleLabel, printSampleLabels } from "../../utils/rollLabels";
import SampleCutPanel from "./SampleCutPanel";
import PendingCutsPanel from "./PendingCutsPanel";
import useViewPreset from "../../hooks/useViewPreset";

/**
 * Operasi Gudang › **Cutting** — Trial 22 Okt 2026 (F1/A2, permintaan pemilik): operasi potong DIPISAH dari Barang
 * Keluar (order biasa). Dulu potong sample bercampur di daftar Barang Keluar, dan potong roll untuk SO tersembunyi
 * di Lokasi Rak. Pesanan sample/catalogue tampil sebagai SATU paket per pesanan × gudang (bukan 9 tugas terpisah):
 * "Potong semua" memotong semua baris dengan roll saran FIFO sekaligus; baris yang perlu roll lain dipotong manual.
 * Sesudah dipotong → serahkan ke Admin Cutting (Meja Cutting) → paket muncul di Barang Keluar untuk dikirim.
 */
const STAGES = [
  { id: "cut", label: "Belum dipotong" },
  { id: "handoff", label: "Menunggu Admin Cutting" },
  { id: "ready", label: "Siap kirim" },
  { id: "all", label: "Semua" },
];

const lineStage = (t) => (Number(t.picked_qty || 0) <= 0 ? "cut" : t.cutting_handoff?.received_at ? "ready" : "handoff");

export default function CuttingOpsView() {
  const [tasks, setTasks] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [wh, setWh] = useState("");
  const [cutWh, setCutWh] = useState("");
  const [q, setQ] = useState("");
  const [stage, setStage] = useState("cut");
  // Fase 3 · P5 — D-24 (a): Operasi Gudang › Cutting = layar utama "menunggu dipotong". Tautan dari Meja Cutting
  // (Pesanan Sample, P3) membawa preset `{ stage, q }` → tahap dan pencarian langsung terpasang.
  useViewPreset("wms-cutting", (p) => {
    if (p.stage && STAGES.some((s) => s.id === p.stage)) setStage(p.stage);
    if (p.q !== undefined) setQ(p.q || "");
  });
  const [open, setOpen] = useState({});
  const [manual, setManual] = useState(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [t, w] = await Promise.all([axios.get(`${API}/outbound/tasks`), axios.get(`${API}/warehouses`)]);
      const rows = Array.isArray(t.data) ? t.data : t.data?.items || [];
      setTasks(rows.filter((x) => x.task_subtype === "sample_cut" && !["dispatched", "cancelled"].includes(x.status)));
      const ws = Array.isArray(w.data) ? w.data : w.data?.items || [];
      setWarehouses(ws);
      setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat tugas potong.")); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const packages = useMemo(() => {
    const term = q.toLowerCase().trim();
    const map = {};
    tasks.forEach((t) => {
      const key = `${t.order_id}|${t.warehouse_id}`;
      (map[key] = map[key] || { key, order_id: t.order_id, order_number: t.order_number, customer_name: t.customer_name,
        warehouse_id: t.warehouse_id, warehouse_name: t.warehouse_name, lines: [] }).lines.push(t);
    });
    return Object.values(map).filter((p) => {
      if (wh && p.warehouse_id !== wh) return false;
      if (stage !== "all" && !p.lines.some((l) => lineStage(l) === stage)) return false;
      if (!term) return true;
      return [p.order_number, p.customer_name, ...p.lines.flatMap((l) => [l.product_name, l.sku, l.suggested_roll_no])]
        .filter(Boolean).join(" ").toLowerCase().includes(term);
    });
  }, [tasks, q, wh, stage]);

  const cutAll = async (p) => {
    setBusy(p.key); setMsg(""); setError("");
    try {
      const { data } = await axios.post(`${API}/outbound/so/${p.order_id}/cut-samples`, { warehouse_id: p.warehouse_id });
      printSampleLabels(data.cut);
      setMsg(`${p.order_number}: ${data.cut.length} baris dipotong (label dicetak). Serahkan potongan ke Admin Cutting — Meja Cutting › Terima semua.`
        + (data.failed.length ? ` Gagal ${data.failed.length}: ${data.failed.map((f) => `${f.product_name} — ${f.error}`).join("; ")} (potong manual).` : ""));
      await load();
    } catch (e) { setError(apiErrorText(e, "Gagal memotong paket.")); } finally { setBusy(""); }
  };

  const whOptions = [{ value: "", label: "Semua gudang" }, ...warehouses.map((w) => ({ value: w.id, label: w.name }))];
  return (
    <div className="section-card" data-testid="wms-cutting-view">
      <div className="section-head">
        <div className="flex items-center gap-2 min-w-0"><span className="kicker">Cutting</span><h2>Potong Sample & Potong Roll</h2></div>
        <button className="icon-button" onClick={load} aria-label="Muat ulang" data-testid="cutting-ops-refresh"><RefreshCw size={14} /></button>
      </div>
      <div className="section-body grid gap-3">
        <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="cutting-ops-error" />
        {msg && <p data-testid="cutting-ops-msg" className="rounded-lg bg-[#EAF7EE] px-3 py-2 text-[11.5px] text-[#1B7E3B]">{msg}</p>}

        <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_220px]">
          <div className="flex items-center gap-2 rounded-lg border border-[#E5E5EA] bg-white px-3 py-1.5">
            <Search size={14} className="text-[#8E8E93]" />
            <input data-testid="cutting-ops-search" value={q} onChange={(e) => setQ(e.target.value)} className="w-full bg-transparent text-[12.5px] outline-none"
              placeholder="Cari no. pesanan, pelanggan, produk, SKU, roll…" />
          </div>
          <KNSelect data-testid="cutting-ops-wh" value={wh} onValueChange={setWh} options={whOptions} searchable={false} />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {STAGES.map((s) => (
            <button key={s.id} data-testid={`cutting-ops-stage-${s.id}`} onClick={() => setStage(s.id)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${stage === s.id ? "bg-[#FF9500] text-white" : "border border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>{s.label}</button>
          ))}
        </div>

        <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Paket potong sample / catalogue ({packages.length})</p>
        {packages.length === 0 && <p className="rounded-lg border border-dashed border-[#E5E5EA] p-4 text-center text-[12px] text-[#8E8E93]" data-testid="cutting-ops-empty">Tidak ada paket potong pada filter ini.</p>}
        {packages.map((p) => {
          const n = p.lines.length;
          const cut = p.lines.filter((l) => lineStage(l) !== "cut").length;
          const recv = p.lines.filter((l) => lineStage(l) === "ready").length;
          const uncut = p.lines.filter((l) => lineStage(l) === "cut");
          const isOpen = open[p.key] ?? n <= 3;
          return (
            <div key={p.key} data-testid={`cutting-pkg-${p.order_id}`} className="rounded-xl border border-[#F3D9A4] bg-[#FFFCF5]">
              <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-[12.5px] font-bold text-[#9A5B00]">{p.order_number} · {p.customer_name}</p>
                  <p className="text-[11px] text-[#6B6B73]">{p.warehouse_name} · {n} baris · dipotong {cut}/{n} · diterima Admin Cutting {recv}/{n}</p>
                </div>
                <div className="flex items-center gap-2">
                  {uncut.length > 0 && (
                    <button data-testid={`cutting-pkg-cut-all-${p.order_id}`} disabled={busy === p.key} onClick={() => cutAll(p)}
                      className="inline-flex items-center gap-1 rounded-lg bg-[#FF9500] px-3 py-1.5 text-[12px] font-semibold text-white disabled:opacity-50">
                      <Scissors size={13} /> {busy === p.key ? "Memotong…" : `Potong semua (${uncut.length}) · roll saran`}
                    </button>
                  )}
                  {uncut.length === 0 && recv < n && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-[#FFF3D6] px-2 py-0.5 text-[10.5px] font-semibold text-[#9A5B00]"><PackageCheck size={12} /> Serahkan ke Admin Cutting</span>
                  )}
                  {recv === n && <span className="rounded-full bg-[#EAF7EE] px-2 py-0.5 text-[10.5px] font-semibold text-[#1B7E3B]">Siap kirim — lihat Barang Keluar</span>}
                  <button className="text-[11px] font-semibold text-[#0058CC]" onClick={() => setOpen((o) => ({ ...o, [p.key]: !isOpen }))}>{isOpen ? "Tutup" : "Rincian"}</button>
                </div>
              </div>
              {isOpen && (
                <ul className="divide-y divide-[#F6ECD5] border-t border-[#F6ECD5] text-[11.5px]">
                  {p.lines.map((l) => (
                    <li key={l.id} data-testid={`cutting-line-${l.id}`} className="px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="min-w-0"><b>{l.product_name}</b> · {formatQty(l.quantity)} {l.unit} · saran {l.suggested_roll_no || "—"}</span>
                        <span className="flex items-center gap-2">
                          {lineStage(l) === "cut" ? (
                            <button data-testid={`cutting-line-manual-${l.id}`} className="text-[11px] font-semibold text-[#CC7700]" onClick={() => setManual(manual === l.id ? null : l.id)}>Potong manual</button>
                          ) : (
                            <>
                              <span className="text-[#126E2C]">{l.parent_roll_no} → <b>{l.child_roll_no}</b>{lineStage(l) === "ready" ? " · diterima" : " · menunggu Admin Cutting"}</span>
                              <button aria-label="Cetak label" className="text-[#6B6B73]" onClick={() => printSampleLabel({ ...l, cut_roll_no: l.parent_roll_no, length: l.picked_qty, sales_order_number: l.order_number })}><Printer size={12} /></button>
                            </>
                          )}
                        </span>
                      </div>
                      {manual === l.id && <div className="mt-2"><SampleCutPanel task={l} onCut={() => { setManual(null); load(); }} /></div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}

        <div className="mt-2 border-t border-[#EFF0F2] pt-3" data-testid="cutting-ops-so-cuts">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Potong roll untuk pesanan (SO) — reservasi panjang yang belum dipotong</p>
            {/* Audit UI 054 — dulu dua filter gudang di satu layar punya nilai awal berbeda ("Semua gudang" vs gudang
                pertama). Kini sama-sama mulai dari "Semua gudang". */}
            <div className="w-[220px]"><KNSelect data-testid="cutting-ops-cut-wh" aria-label="Gudang potong SO" value={cutWh} onValueChange={setCutWh} options={whOptions} searchable={false} /></div>
          </div>
          <PendingCutsPanel whId={cutWh} />
        </div>
      </div>
    </div>
  );
}
