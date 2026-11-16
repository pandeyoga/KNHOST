// MP-T1 — tab "Rute" di rincian induk Master Produk (docs/blueprint/unit/MP-T1.md).
// Rute = jalan beli/buat barang di PT aktif: beli dari pemasok, makloon per tahap, atau produksi sendiri. Pilihan di
// pop-up tersaring: tahap hanya yang boleh sesudah tahap sebelumnya (Master Tahapan Proses), mitra hanya yang
// mengerjakan prosesnya, kontrak hanya milik mitra itu, bahan/hasil hanya produk bertahap sesuai. Aturan yang sama
// diperiksa server (`services/product_route_service.validate`); pesan server ditampilkan apa adanya.
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, GitBranch, Plus, Sparkles, Trash2 } from "lucide-react";
import StatusBadge from "../../components/StatusBadge";
import FormModal from "../../components/FormModal";
import ProductSelect from "../../components/ProductSelect";
import { askConfirm } from "../../services/confirmService";
import { can } from "../../config/roles";
import { catalogApi, catalogError } from "./catalogApi";

const KIND_LABEL = { purchase: "Beli dari pemasok", makloon: "Makloon", inhouse: "Produksi sendiri" };
const ORIGIN_LABEL = { rnd: "Dari R&D", rute_awal: "Rute awal (data lama)", manual: "" };
const emptyStep = (kind) => ({ kind, stage_code: "", partner_id: "", contract_id: "", input_product_id: "", input_product_label: "",
  output_product_id: "", output_product_label: "", bom_id: "", note: "" });

function stageText(labels, v) { return (labels || {})[v] || v || "—"; }

function RouteChain({ route, labels }) {
  const steps = route.steps || [];
  const start = steps[0]?.kind === "purchase" ? null : steps[0]?.from_stage;
  return <div className="flex flex-wrap items-center gap-1.5 text-xs" data-testid={`route-chain-${route.id}`}>
    {start && <span className="rounded bg-kn-neutral-soft px-2 py-0.5 font-semibold">{stageText(labels, start)}</span>}
    {steps.map((s) => <span key={s.seq} className="contents">
      {start || s.seq > 1 ? <ArrowRight size={12} className="text-kn-text-2" /> : null}
      <span className="rounded border border-kn-divider px-2 py-0.5">
        {s.kind === "makloon" ? s.stage_label || s.stage_code : KIND_LABEL[s.kind]}
        {s.kind !== "inhouse" && <> @ {s.partner_name || <em className="text-kn-warning-text">{s.kind === "purchase" ? "pemasok" : "mitra"} belum diisi</em>}</>}
        {s.contract_number ? <span className="text-kn-text-2"> · {s.contract_number}</span> : null}
      </span>
      <ArrowRight size={12} className="text-kn-text-2" />
      <span className="rounded bg-kn-neutral-soft px-2 py-0.5 font-semibold">{stageText(labels, s.to_stage)}</span>
    </span>)}
  </div>;
}

function StepEditor({ step, index, prevTo, opts, onChange, onRemove }) {
  const labels = opts?.stage_labels || {};
  const stages = useMemo(() => (opts?.stages || []).filter((o) => !prevTo || o.from_stage === prevTo), [opts, prevTo]);
  const stage = (opts?.stages || []).find((o) => o.stage_code === step.stage_code);
  const partners = step.kind === "makloon" ? (stage?.partners || []) : (opts?.suppliers || []);
  const contracts = (opts?.contracts || []).filter((k) => k.contract_type === (step.kind === "purchase" ? "purchase" : "makloon")
    && (!step.partner_id || k.partner_id === step.partner_id)
    && (step.kind !== "makloon" || !k.process_type || k.process_type === stage?.process_type));
  const set = (patch) => onChange({ ...step, ...patch });
  const tid = `route-step-${index + 1}`;
  return <div className="rounded-lg border border-kn-divider p-3" data-testid={tid}>
    <div className="mb-2 flex items-center justify-between gap-2">
      <strong className="text-sm">Langkah {index + 1}</strong>
      <button type="button" className="secondary-button" data-testid={`${tid}-remove`} onClick={onRemove}><Trash2 size={13} />Hapus langkah</button>
    </div>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="text-xs font-semibold">Jenis langkah
        <select className="field mt-1" data-testid={`${tid}-kind`} value={step.kind} onChange={(e) => onChange(emptyStep(e.target.value))}>
          {index === 0 && <option value="purchase">{KIND_LABEL.purchase}</option>}
          <option value="makloon">{KIND_LABEL.makloon}</option>
          <option value="inhouse">{KIND_LABEL.inhouse}</option>
        </select>
      </label>
      {step.kind === "makloon" && <label className="text-xs font-semibold">Tahap
        <select className="field mt-1" data-testid={`${tid}-stage`} value={step.stage_code} onChange={(e) => set({ stage_code: e.target.value, partner_id: "", contract_id: "", input_product_id: "", input_product_label: "", output_product_id: "", output_product_label: "" })}>
          <option value="">Pilih tahap…</option>
          {stages.map((o) => <option key={o.stage_code} value={o.stage_code}>{o.label} ({stageText(labels, o.from_stage)} → {stageText(labels, o.to_stage)})</option>)}
        </select>
        {prevTo && !stages.length && <span className="mt-1 block font-normal text-kn-warning-text">Tidak ada tahap makloon yang menerima bahan {stageText(labels, prevTo)}.</span>}
      </label>}
      {step.kind === "inhouse" && <label className="text-xs font-semibold">BOM produksi
        <select className="field mt-1" data-testid={`${tid}-bom`} value={step.bom_id} onChange={(e) => set({ bom_id: e.target.value })}>
          <option value="">Pilih BOM…</option>
          {(opts?.boms || []).map((b) => <option key={b.id} value={b.id}>{b.code || b.name || "BOM tanpa nama"}</option>)}
        </select>
      </label>}
      {step.kind !== "inhouse" && <label className="text-xs font-semibold">{step.kind === "purchase" ? "Pemasok" : "Mitra makloon"} (boleh menyusul)
        <select className="field mt-1" data-testid={`${tid}-partner`} value={step.partner_id} disabled={step.kind === "makloon" && !step.stage_code}
          onChange={(e) => set({ partner_id: e.target.value, contract_id: "" })}>
          <option value="">{step.kind === "makloon" && !step.stage_code ? "Pilih tahap dulu" : "Belum diisi"}</option>
          {partners.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
      </label>}
      {step.kind !== "inhouse" && <label className="text-xs font-semibold">Kontrak (boleh menyusul)
        <select className="field mt-1" data-testid={`${tid}-contract`} value={step.contract_id} onChange={(e) => set({ contract_id: e.target.value })}>
          <option value="">Belum ada kontrak</option>
          {contracts.map((k) => <option key={k.id} value={k.id}>{k.contract_number}{k.title ? ` — ${k.title}` : ""}</option>)}
        </select>
      </label>}
      {step.kind === "makloon" && step.stage_code && <div className="text-xs font-semibold">Bahan masuk ({stageText(labels, stage?.from_stage)}, boleh kosong)
        <div className="mt-1"><ProductSelect stage={stage?.from_stage || ""} value={step.input_product_id} valueName={step.input_product_label}
          triggerTestId={`${tid}-input`} label="Pilih bahan…" onSelect={(p) => set({ input_product_id: p.id, input_product_label: `${p.sku} · ${p.name}` })} /></div>
      </div>}
      {step.kind === "purchase" && <div className="text-xs font-semibold">Barang yang dibeli (boleh kosong)
        <div className="mt-1"><ProductSelect value={step.output_product_id} valueName={step.output_product_label} triggerTestId={`${tid}-output`}
          label="Pilih barang…" onSelect={(p) => set({ output_product_id: p.id, output_product_label: `${p.sku} · ${p.name}` })} /></div>
      </div>}
    </div>
  </div>;
}

function RouteForm({ family, route, initial, opts, onClose, onSaved }) {
  const [name, setName] = useState(route?.name || initial?.name || "");
  const [productId, setProductId] = useState(route?.product_id || "");
  const [steps, setSteps] = useState(() => (route?.steps || initial?.steps || [emptyStep("makloon")]).map((s) => ({ ...emptyStep(s.kind), ...s })));
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const labels = opts?.stage_labels || {};
  const toOf = (i) => {
    const s = steps[i]; if (!s) return "";
    if (s.kind === "makloon") return (opts?.stages || []).find((o) => o.stage_code === s.stage_code)?.to_stage || "";
    return "";
  };
  const submit = async () => {
    setBusy(true); setError("");
    const body = { name, steps: steps.map(({ input_product_label, output_product_label, ...s }) => s) };
    try {
      const saved = route ? await catalogApi.routeUpdate(route.id, body) : await catalogApi.routeCreate(family.id, { ...body, product_id: productId, origin_ref: initial?.origin_ref });
      onSaved(saved);
    } catch (e) { setError(catalogError(e)); } finally { setBusy(false); }
  };
  return <FormModal open onClose={onClose} title={route ? "Ubah rute" : "Buat rute"} subtitle={`${family.name} · tahap akhir ${stageText(labels, family.stage || "finished")}`}
    icon={GitBranch} size="lg" testId="route-form" onSubmit={submit} submitLabel={route ? "Simpan rute" : "Buat rute"} busy={busy} error={error}>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="text-xs font-semibold">Nama rute
        <input className="field mt-1" data-testid="route-name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} placeholder="mis. Printing di mitra langganan" />
      </label>
      <label className="text-xs font-semibold">Berlaku untuk
        <select className="field mt-1" data-testid="route-scope" value={productId} disabled={!!route} onChange={(e) => setProductId(e.target.value)}>
          <option value="">Semua varian artikel ini</option>
          {(family.variants || []).map((v) => <option key={v.id} value={v.id}>Khusus {v.sku}</option>)}
        </select>
      </label>
    </div>
    <div className="mt-3 grid gap-3">
      {steps.map((s, i) => <StepEditor key={i} step={s} index={i} prevTo={i ? toOf(i - 1) : ""} opts={opts}
        onChange={(n) => setSteps(steps.map((x, j) => (j === i ? n : x)))} onRemove={() => setSteps(steps.filter((_, j) => j !== i))} />)}
      <button type="button" className="secondary-button justify-self-start" data-testid="route-add-step" onClick={() => setSteps([...steps, emptyStep("makloon")])}><Plus size={14} />Tambah langkah</button>
    </div>
  </FormModal>;
}

export default function FamilyRoutesTab({ family, currentUser, selectedEntity }) {
  const canEdit = can(currentUser?.permissions, "product_route", "update");
  const [data, setData] = useState(null); const [opts, setOpts] = useState(null);
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [form, setForm] = useState(null);
  const allPt = selectedEntity === "all";
  const load = useCallback(async () => {
    setError("");
    try { const [d, o] = await Promise.all([catalogApi.routes(family.id), catalogApi.routeOptions("")]); setData(d); setOpts(o); }
    catch (e) { setError(catalogError(e)); setData({ items: [] }); }
  }, [family.id]);
  useEffect(() => { load(); }, [load, selectedEntity]);
  const labels = opts?.stage_labels || {};
  const variantSku = (pid) => (family.variants || []).find((v) => v.id === pid)?.sku || "(varian tidak ditemukan)";
  const suggest = async () => {
    setError(""); setNotice("");
    try {
      const r = await catalogApi.routeSuggest(family.id);
      if (!r.items?.length) { setNotice("Tidak ada data lama (resep proses, BOM, sumber restock) yang bisa diusulkan untuk artikel ini."); return; }
      setForm({ initial: r.items[0] });
      if (r.items.length > 1) setNotice(`Ada ${r.items.length} usulan; yang pertama dibuka: ${r.items.map((x) => x.name).join(", ")}.`);
    } catch (e) { setError(catalogError(e)); }
  };
  const act = async (fn, msg) => { setError(""); try { await fn(); setNotice(msg); await load(); } catch (e) { setError(catalogError(e)); } };
  const items = data?.items || [];
  return <section className="mt-3" data-testid="catalog-routes">
    <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
      <div><h2 className="text-base font-semibold">Rute di PT ini</h2>
        <p className="text-xs text-kn-text-2">Jalan beli atau buat barang ini. Rute utama dipakai pembelian dan SPK makloon; produk hasil R&D baru bisa dirilis bila punya rute utama.</p></div>
      {canEdit && <div className="flex flex-wrap gap-2">
        <button className="secondary-button" data-testid="route-suggest" disabled={allPt} onClick={suggest}><Sparkles size={14} />Usulkan dari data lama</button>
        <button className="primary-button" data-testid="route-create" disabled={allPt} onClick={() => setForm({})}><Plus size={14} />Buat rute</button>
      </div>}
    </div>
    {allPt && canEdit && <p className="mb-2 text-xs text-kn-warning-text">Pilih satu PT untuk membuat atau mengubah rute.</p>}
    {error && <p className="mb-2 rounded bg-kn-danger-soft px-3 py-2 text-sm text-kn-danger-text" data-testid="route-error">{error}</p>}
    {notice && <p className="mb-2 rounded bg-kn-action-soft px-3 py-2 text-sm text-kn-action" data-testid="route-notice">{notice}</p>}
    {!data ? <p className="text-sm text-kn-text-2" data-testid="route-loading">Memuat rute…</p>
      : !items.length ? <div className="rounded-lg border border-dashed border-kn-divider p-4 text-sm text-kn-text-2" data-testid="route-empty">Artikel ini belum punya rute di PT ini.</div>
        : <div className="grid gap-2">{items.map((r) => <div key={r.id} className="rounded-lg border border-kn-divider p-3" data-testid={`route-card-${r.id}`}>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <strong className="text-sm">{r.name}</strong>
            {r.is_primary && <StatusBadge tone="success" label="Utama" testId={`route-primary-${r.id}`} />}
            {r.product_id && <StatusBadge tone="warning" label={`Khusus varian ${variantSku(r.product_id)}`} />}
            {ORIGIN_LABEL[r.origin] && <span className="text-xs text-kn-text-2">{ORIGIN_LABEL[r.origin]}</span>}
          </div>
          <RouteChain route={r} labels={labels} />
          {canEdit && !allPt && <div className="mt-2 flex flex-wrap gap-2">
            <button className="secondary-button" data-testid={`route-edit-${r.id}`} onClick={() => setForm({ route: r })}>Ubah</button>
            {!r.is_primary && <button className="secondary-button" data-testid={`route-make-primary-${r.id}`} onClick={() => act(() => catalogApi.routePrimary(r.id), `“${r.name}” kini rute utama.`)}>Jadikan utama</button>}
            <button className="secondary-button" data-testid={`route-deactivate-${r.id}`} onClick={async () => {
              if (!await askConfirm({ title: "Nonaktifkan rute ini?", message: `${r.name}${r.is_primary ? " — ini rute utama; pilih rute utama lain sesudahnya." : ""}`, confirmLabel: "Nonaktifkan", danger: true })) return;
              act(() => catalogApi.routeUpdate(r.id, { status: "inactive" }), `“${r.name}” dinonaktifkan.`);
            }}>Nonaktifkan</button>
          </div>}
        </div>)}</div>}
    {form && <RouteForm family={family} route={form.route} initial={form.initial} opts={opts} onClose={() => setForm(null)}
      onSaved={async (saved) => { setForm(null); setNotice(`Rute “${saved.name}” tersimpan.`); await load(); }} />}
  </section>;
}
