import { useCallback, useEffect, useMemo, useState } from "react";
import { Printer, RefreshCw, Scissors, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import EmptyState, { listStateKind } from "../../components/EmptyState";
import StatusBadge from "../../components/StatusBadge";
import { ListToolbar, PageHeader, SearchInput } from "../../components/ListPageParts";   // pola UI 16 Nov
import { apiErrorText } from "../../utils/apiError";
import { formatQty } from "../../utils/formatters";
import { printSampleLabel, printSampleLabels } from "../../utils/rollLabels";
import SampleCutPanel from "./SampleCutPanel";
import PendingCutsPanel from "./PendingCutsPanel";
import useViewPreset from "../../hooks/useViewPreset";
import ExportMenu from "../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)
import ListLimitNote, { metaFromHeaders } from "./ListLimitNote";   // FIX-7 (B3b LST-01)
import { OpsCount, OpsList, OpsRow, OpsSelect, OpsSplit } from "./OpsListParts";   // pola UI M26

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
  { id: "all", label: "Semua tahap" },
];

// FIX-7 (B3b LST-01) — tugas potong disaring di SERVER (`task_subtype` + `exclude_status`); dulu disaring dari 200
// tugas keluar TERBARU apa pun jenisnya, sehingga paket potong lama hilang begitu ada > 200 tugas SO.
const CUT_PARAMS = { task_subtype: "sample_cut", exclude_status: "dispatched,cancelled", limit: 500 };

const lineStage = (t) => (Number(t.picked_qty || 0) <= 0 ? "cut" : t.cutting_handoff?.received_at ? "ready" : "handoff");

export default function CuttingOpsView() {
  const [tasks, setTasks] = useState([]);
  const [listMeta, setListMeta] = useState(null);
  const [moreBusy, setMoreBusy] = useState(false);
  const [warehouses, setWarehouses] = useState([]);
  const [wh, setWh] = useState("");
  const [kind, setKind] = useState("all");   // M26 — Jenis ▾: paket sample/catalogue · potong roll SO · keduanya
  const [q, setQ] = useState("");
  const [stage, setStage] = useState("cut");
  // Fase 3 · P5 — D-24 (a): Operasi Gudang › Cutting = layar utama "menunggu dipotong". Tautan dari Meja Cutting
  // (Pesanan Sample, P3) membawa preset `{ stage, q }` → tahap dan pencarian langsung terpasang.
  useViewPreset("wms-cutting", (p) => {
    if (p.stage && STAGES.some((s) => s.id === p.stage)) setStage(p.stage);
    if (p.q !== undefined) setQ(p.q || "");
  });
  const [selKey, setSelKey] = useState("");   // paket yang dibuka di panel kanan (dulu kartu buka-tutup)
  const [loaded, setLoaded] = useState(false);
  const [loadErr, setLoadErr] = useState(null);   // galat muat daftar (403 ≠ "tidak ada paket")
  const [manual, setManual] = useState(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [t, w] = await Promise.all([axios.get(`${API}/outbound/tasks`, { params: CUT_PARAMS }), axios.get(`${API}/warehouses`)]);
      const rows = Array.isArray(t.data) ? t.data : t.data?.items || [];
      setTasks(rows.filter((x) => x.task_subtype === "sample_cut" && !["dispatched", "cancelled"].includes(x.status)));
      setListMeta(metaFromHeaders(t, rows.length));
      const ws = Array.isArray(w.data) ? w.data : w.data?.items || [];
      setWarehouses(ws);
      setError("");
      setLoadErr(null);
    } catch (e) { setError(apiErrorText(e, "Gagal memuat tugas potong.")); setLoadErr(e); } finally { setLoaded(true); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const loadMore = async () => {
    setMoreBusy(true);
    try {
      const t = await axios.get(`${API}/outbound/tasks`, { params: { ...CUT_PARAMS, skip: tasks.length } });
      const seen = new Set(tasks.map((x) => x.id));
      const next = [...tasks, ...(Array.isArray(t.data) ? t.data : []).filter((x) => !seen.has(x.id))];
      setTasks(next);
      const m = metaFromHeaders(t, next.length);
      setListMeta(m ? { ...m, shown: next.length, skip: 0 } : null);
    } catch (e) { setError(apiErrorText(e, "Gagal memuat tugas potong berikutnya.")); } finally { setMoreBusy(false); }
  };

  // Semua paket (panel rincian tetap menampilkan paket terbuka walau tahapnya berpindah sesudah dipotong).
  const allPackages = useMemo(() => {
    const map = {};
    tasks.forEach((t) => {
      const key = `${t.order_id}|${t.warehouse_id}`;
      (map[key] = map[key] || { key, order_id: t.order_id, order_number: t.order_number, customer_name: t.customer_name,
        warehouse_id: t.warehouse_id, warehouse_name: t.warehouse_name, lines: [] }).lines.push(t);
    });
    return Object.values(map);
  }, [tasks]);
  const packages = useMemo(() => {
    const term = q.toLowerCase().trim();
    return allPackages.filter((p) => {
      if (wh && p.warehouse_id !== wh) return false;
      if (stage !== "all" && !p.lines.some((l) => lineStage(l) === stage)) return false;
      if (!term) return true;
      return [p.order_number, p.customer_name, ...p.lines.flatMap((l) => [l.product_name, l.sku, l.suggested_roll_no])]
        .filter(Boolean).join(" ").toLowerCase().includes(term);
    });
  }, [allPackages, q, wh, stage]);

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

  const whOptions = [{ value: "", label: "Semua gudang" },
    ...warehouses.map((w) => ({ value: w.id, label: w.name || w.code || "Gudang tanpa nama" }))];
  const selPkg = selKey ? allPackages.find((p) => p.key === selKey) || null : null;
  const listKind = listStateKind({ loading: !loaded, error: loadErr, count: packages.length,
    filtered: stage !== "all" || Boolean(wh) || Boolean(q.trim()) });
  return (
    <div className="space-y-3" data-testid="wms-cutting-view">
      {/* Pola UI gelombang Gudang (M26, pemilik 16 Nov) — kepala satu baris + ?; SATU bilah daftar seperti Barang Masuk &
          Barang Keluar (Cari → Tahap ▾ → Jenis ▾ → Gudang ▾ → jumlah · Muat ulang/Unduh). Dulu: kotak cari buatan, chip
          tahap, kartu paket buka-tutup, dan dropdown gudang KEDUA untuk potong roll SO. Kini satu Gudang ▾ untuk kedua
          daftar; Jenis ▾ memilih daftar mana yang tampil; paket dibuka di panel kanan. */}
      <PageHeader icon={Scissors} title="Cutting" testId="cutting-header"
        help="Potong sample/catalogue: satu paket per pesanan × gudang. “Potong semua” memotong semua baris dengan roll saran FIFO sekaligus (label tercetak); baris yang perlu roll lain dipotong manual di panel paket. Sesudah dipotong → serahkan ke Admin Cutting (Meja Cutting › Terima semua) → paket muncul di Barang Keluar untuk dikirim. Potong roll pesanan (SO) = reservasi panjang di roll induk yang belum dipotong fisik." />
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="cutting-ops-error" />
      {msg && (
        <div className="notice-bar success !mb-0" data-testid="cutting-ops-msg">
          {msg}
          <button type="button" aria-label="Tutup pesan" onClick={() => setMsg("")}><X size={12} /></button>
        </div>
      )}

      <ListToolbar testId="cutting-ops-toolbar" actions={(
        <>
          <button type="button" className="icon-button" onClick={load} aria-label="Muat ulang" title="Muat ulang"
            data-testid="cutting-ops-refresh"><RefreshCw size={14} /></button>
          {kind !== "so" && (
            <ExportMenu dataset="wms_tasks" label="tugas-potong-sample" scope="work" testId="cutting-ops-export" search={q}
              filters={[["task_subtype", "eq", "sample_cut"], ["status", "ne", "dispatched"], ["status", "ne", "cancelled"],
                wh && ["warehouse_id", "eq", wh]]} sort={[{ key: "created_at", dir: "desc" }]}
              unsupported={stage !== "all" ? "Tahap paket dihitung di layar — pilih tahap “Semua tahap” untuk mengunduh." : ""} />
          )}
        </>
      )}>
        {kind !== "so" && (
          <SearchInput testId="cutting-ops-search" value={q} onChange={setQ} placeholder="Cari no. pesanan, pelanggan, produk, SKU, roll…"
            className="min-w-[220px] flex-1 sm:max-w-[320px]" />
        )}
        {kind !== "so" && (
          <OpsSelect testId="cutting-ops-stage" label="Tahap paket" value={stage} onChange={(v) => setStage(v || "all")}
            width="min-w-[190px]" options={STAGES.map((s) => ({ value: s.id, label: s.label }))} />
        )}
        <OpsSelect testId="cutting-ops-kind" label="Jenis potong" value={kind} onChange={(v) => setKind(v || "all")}
          width="min-w-[190px]" options={KINDS} />
        <OpsSelect testId="cutting-ops-wh" label="Gudang" value={wh} onChange={setWh} width="min-w-[170px]"
          searchable={whOptions.length > 9} options={whOptions} />
        {kind !== "so" && <OpsCount testId="cutting-ops-count">{loaded ? `${packages.length} paket` : "Memuat…"}</OpsCount>}
      </ListToolbar>

      {kind !== "so" && (
        <OpsSplit open={Boolean(selPkg)} testId="cutting-ops-split">
          <OpsList testId="cutting-ops-list" footer={(
            <ListLimitNote meta={listMeta} noun="tugas potong" onMore={loadMore} loading={moreBusy}
              hint="paket & saringan di layar hanya atas tugas yang sudah dimuat." testId="cutting-ops-limit" />
          )}>
            {listKind ? (
              <EmptyState compact what="paket potong" icon={Scissors} error={loadErr} onRetry={load} kind={listKind}
                testId="cutting-ops-empty" onReset={() => { setStage("all"); setWh(""); setQ(""); }} />
            ) : packages.map((p) => {
              const st = pkgState(p);
              return (
                <OpsRow key={p.key} wrapperTestId={`cutting-pkg-${p.order_id}`} testId={`cutting-open-${p.order_id}`}
                  selected={selKey === p.key} onOpen={() => { setSelKey(p.key); setManual(null); }}
                  title={p.order_number}
                  status={<PkgBadge st={st} />}
                  lines={[p.customer_name, `${p.warehouse_name || "Gudang tanpa nama"} · ${st.n} baris · dipotong ${st.cut}/${st.n} · diterima Admin Cutting ${st.recv}/${st.n}`]}
                  action={st.uncut.length > 0 && (
                    <button type="button" data-testid={`cutting-pkg-cut-all-${p.order_id}`} disabled={busy === p.key}
                      onClick={() => cutAll(p)} className="primary-button btn-sm">
                      <Scissors size={14} /> {busy === p.key ? "Memotong…" : `Potong semua (${st.uncut.length}) · roll saran`}
                    </button>
                  )} />
              );
            })}
          </OpsList>

          {selPkg && (
            <PackagePanel p={selPkg} st={pkgState(selPkg)} busy={busy} manual={manual} setManual={setManual}
              onCutAll={() => cutAll(selPkg)} onCut={() => { setManual(null); load(); }}
              onClose={() => { setSelKey(""); setManual(null); }} />
          )}
        </OpsSplit>
      )}

      {kind !== "sample" && (
        <div data-testid="cutting-ops-so-cuts">
          <PendingCutsPanel whId={wh} />
        </div>
      )}
    </div>
  );
}

const KINDS = [
  { value: "all", label: "Semua jenis potong" },
  { value: "sample", label: "Sample / catalogue (paket)" },
  { value: "so", label: "Potong roll pesanan (SO)" },
];

function pkgState(p) {
  const n = p.lines.length;
  const cut = p.lines.filter((l) => lineStage(l) !== "cut").length;
  const recv = p.lines.filter((l) => lineStage(l) === "ready").length;
  const uncut = p.lines.filter((l) => lineStage(l) === "cut");
  return { n, cut, recv, uncut };
}

/** Tahap paket = lencana baku (dulu pil oranye/hijau buatan sendiri). */
function PkgBadge({ st }) {
  if (st.uncut.length > 0) return <StatusBadge tone="warning" icon="alert">Belum dipotong</StatusBadge>;
  if (st.recv < st.n) return <StatusBadge tone="info" icon="clock">Serahkan ke Admin Cutting</StatusBadge>;
  return <StatusBadge tone="success" icon="check">Siap kirim — lihat Barang Keluar</StatusBadge>;
}

/** Panel rincian paket (kanan): aksi paket + baris potong (dulu kartu yang dibuka-tutup "Rincian/Tutup"). */
function PackagePanel({ p, st, busy, manual, setManual, onCutAll, onCut, onClose }) {
  return (
    <div className="kn-ops-panel" data-testid={`cutting-detail-${p.order_id}`}>
      <div className="kn-ops-panel-head">
        <div className="min-w-0">
          <p className="text-fs-13 font-bold text-kn-text">{p.order_number} · {p.customer_name}</p>
          <p className="text-fs-12 text-kn-text-2">{p.warehouse_name || "Gudang tanpa nama"} · {st.n} baris · dipotong {st.cut}/{st.n} · diterima Admin Cutting {st.recv}/{st.n}</p>
        </div>
        <div className="flex items-center gap-2">
          {st.uncut.length > 0 ? (
            <button type="button" data-testid={`cutting-detail-cut-all-${p.order_id}`} disabled={busy === p.key} onClick={onCutAll}
              className="primary-button btn-sm">
              <Scissors size={14} /> {busy === p.key ? "Memotong…" : `Potong semua (${st.uncut.length}) · roll saran`}
            </button>
          ) : <PkgBadge st={st} />}
          <button type="button" className="icon-button" aria-label="Tutup panel paket" data-testid="cutting-detail-close" onClick={onClose}>
            <X size={14} />
          </button>
        </div>
      </div>
      <ul className="divide-y divide-kn-divider text-fs-12">
        {p.lines.map((l) => (
          <li key={l.id} data-testid={`cutting-line-${l.id}`} className="px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0"><b>{l.product_name}</b> · {formatQty(l.quantity)} {l.unit} · saran {l.suggested_roll_no || "—"}</span>
              <span className="flex items-center gap-2">
                {lineStage(l) === "cut" ? (
                  <button type="button" data-testid={`cutting-line-manual-${l.id}`} className="secondary-button btn-sm"
                    onClick={() => setManual(manual === l.id ? null : l.id)}>Potong manual</button>
                ) : (
                  <>
                    <span className="text-kn-success-text">{l.parent_roll_no} → <b>{l.child_roll_no}</b>{lineStage(l) === "ready" ? " · diterima" : " · menunggu Admin Cutting"}</span>
                    <button type="button" aria-label="Cetak label" title="Cetak label" className="icon-button"
                      onClick={() => printSampleLabel({ ...l, cut_roll_no: l.parent_roll_no, length: l.picked_qty, sales_order_number: l.order_number })}>
                      <Printer size={14} />
                    </button>
                  </>
                )}
              </span>
            </div>
            {manual === l.id && <div className="mt-2"><SampleCutPanel task={l} onCut={onCut} /></div>}
          </li>
        ))}
      </ul>
    </div>
  );
}
