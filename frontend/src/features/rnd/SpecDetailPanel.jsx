/**
 * SpecDetailPanel (FASE F · PS-12) — detail spesifikasi + aksi alur:
 * ajukan → ACC (produk lahir) → rilis ke produksi (barang boleh dijual) — atau tolak.
 * Menampilkan permintaan sample turunannya supaya rantai R&D terlihat utuh.
 */
import { useCallback, useEffect, useState } from "react";
import MoneyInput from "@/components/MoneyInput";
import { CheckCircle2, FlaskConical, Rocket, Send, X, XCircle } from "lucide-react";
import { REASON_MIN_LENGTH } from "../../services/confirmService";
import { formatCurrency, formatQty, formatDateTime } from "../../utils/formatters";
import { approveSpec, getSpec, rejectSpec, releaseProduct, submitSpec } from "./rndApi";
import { specOverride } from "./requiredTests";
import { errMsg, fabricLabel, lifecycleMeta, SAMPLE_STATUS_META, SPEC_STATUS_META } from "./rndMeta";
import { sampleTypesOf, typeLabel } from "./sampleTypeMeta";
import { useEntityScope } from "../../context/EntityScopeContext";
import useDomainEnums from "../../hooks/useDomainEnums";

export default function SpecDetailPanel({ specId, currentUser, types = [], onClose,
                                         onChanged }) {
  const [spec, setSpec] = useState(null);
  const [err, setErr] = useState("");
  const { labelOf } = useDomainEnums();
  const [busy, setBusy] = useState(false);
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [reason, setReason] = useState("");

  const { canWrite, writeBlockHint } = useEntityScope();
  const canSubmit = (currentUser?.permissions?.rnd || []).includes('create');
  const canApprove = (currentUser?.permissions?.rnd || []).includes('assess');
  const canRelease = (currentUser?.permissions?.rnd || []).includes('decide');

  const load = useCallback(async () => {
    try {
      const d = await getSpec(specId);
      setSpec(d);
      setSku(d.sku_hint || "");
      setName(d.title || "");
      setPrice(String(d.target_price || ""));
      setErr("");
    } catch (e) { setErr(errMsg(e, "Gagal memuat spesifikasi.")); }
  }, [specId]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn, okMsg) => {
    if (!canWrite) { setErr(writeBlockHint); return; }
    setBusy(true); setErr("");
    try {
      await fn();
      await load();
      onChanged?.();
      if (okMsg) setErr("");
    } catch (e) { setErr(errMsg(e, "Aksi gagal dijalankan.")); } finally { setBusy(false); }
  };

  const meta = SPEC_STATUS_META[spec?.status] || SPEC_STATUS_META.draft;
  const life = lifecycleMeta(spec?.lifecycle);

  return (
    // Fase 3 · P6 (L-03) — dulu panel ini memasang lapisan gelapnya sendiri DI DALAM `DetailModal` (dua lapisan,
    // dua jalur tutup). Kini hanya kartu; lapisan, Esc & klik latar milik `DetailModal` (RndSpecsView).
    <div data-testid="spec-detail-panel"
      className="mx-auto flex max-h-[94vh] w-full max-w-[880px] flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[#EFF0F2] px-4 py-3">
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-[15px] font-bold">
              <FlaskConical size={16} className="text-[#0058CC]" />
              <span data-testid="spec-detail-number">{spec?.number || "…"}</span>
              <span className={`status-pill ${meta.cls}`}
                data-testid="spec-detail-status">{meta.label}</span>
            </h2>
            <p className="truncate text-[11.5px] text-[#6B6B73]">{spec?.title}</p>
          </div>
          <button className="icon-button" onClick={onClose} data-testid="spec-detail-close">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {err && (
            <div className="rounded-lg bg-[#FDEDE7] px-3 py-2 text-[11.5px] text-[#C0392B]"
              data-testid="spec-detail-error">{err}</div>
          )}

          <div className="grid gap-2 md:grid-cols-4">
            <Box label="Tahap produk" value={life.label} tone={life.tone}
              testId="spec-detail-lifecycle" />
            {/* UAT 24 Okt (audit UI tahap 2) — G5-49: tahap bahan berlabel registri (dulu "finished" mentah); nilai
                kosong "—" (dulu "0 gsm · 0 cm" & "Rp 0"). */}
            <Box label="Jenis kain / tahap bahan"
              value={`${fabricLabel(spec?.target?.fabric_type) || "—"} · ${spec?.target?.stage ? labelOf("stage", spec.target.stage) : "—"}`} />
            <Box label="Gramasi / lebar"
              value={!(Number(spec?.target?.gramasi) > 0) && !(Number(spec?.target?.lebar) > 0) ? "—"
                : `${Number(spec?.target?.gramasi) > 0 ? `${formatQty(spec.target.gramasi)} gsm` : "gramasi —"} · ${Number(spec?.target?.lebar) > 0 ? `${formatQty(spec.target.lebar)} cm` : "lebar —"}`} />
            <Box label="Target harga" value={Number(spec?.target_price) > 0 ? formatCurrency(spec.target_price) : "—"} />
          </div>

          <div className="grid gap-2 md:grid-cols-4">
            <Box label="Warna target"
              value={`${spec?.color_target?.name || "—"}${spec?.color_target?.code ? ` (${spec.color_target.code})` : ""}`}
              swatch={spec?.color_target?.hex} />
            <Box label="Desain / pattern"
              value={spec?.design_code ? `${spec.design_code} v${spec.design_version || 1}` : "—"} />
            <Box label="Rencana sample"
              value={spec?.sample_type_hint ? typeLabel(spec.sample_type_hint, types) : "—"} />
            <Box label="Kain dasar (master data)" testId="spec-detail-base-fabric"
              value={spec?.base_fabric_name || "Tidak ada"} />
          </div>

          {spec?.product && (
            <div className="rounded-lg border border-[#EFF0F2] p-3" data-testid="spec-detail-product">
              <p className="mb-1 text-[10.5px] font-bold uppercase text-[#8E8E93]">
                Produk hasil persetujuan
              </p>
              <p className="text-[12.5px] font-semibold">
                {spec.product.sku} — {spec.product.name}
              </p>
              <p className="text-[11px]" style={{ color: lifecycleMeta(spec.product.lifecycle).tone }}>
                Tahap: <b>{lifecycleMeta(spec.product.lifecycle).label}</b>
                {lifecycleMeta(spec.product.lifecycle).sellable
                  ? " — sudah boleh dipesan & dijual"
                  : " — BELUM boleh dipesan/dijual"}
              </p>
              {spec.template_id && <button data-testid="spec-open-catalog" className="secondary-button mt-3" onClick={() => { window.dispatchEvent(new CustomEvent('kn-open-catalog', { detail: { templateId: spec.template_id, productId: spec.product.id } })); onClose(); }}>Buka induk, varian & foto</button>}
            </div>
          )}

          {(spec?.samples || []).length > 0 && (
            <div className="rounded-lg border border-[#EFF0F2]" data-testid="spec-detail-samples">
              <p className="border-b border-[#EFF0F2] px-3 py-1.5 text-[10.5px] font-bold uppercase text-[#8E8E93]">
                Permintaan sample dari spesifikasi ini
              </p>
              <div className="divide-y divide-[#F4F5F7]">
                {spec.samples.map((s) => {
                  const sm = SAMPLE_STATUS_META[s.status] || SAMPLE_STATUS_META.draft;
                  return (
                    <div key={s.id} className="flex items-center justify-between px-3 py-2">
                      <span className="text-[11.5px] font-semibold">{s.number}</span>
                      <span className="text-[11px] text-[#6B6B73]">
                        {/* FASE S — satu permintaan bisa menempuh beberapa jenis;
                            namanya dibaca dari master, bukan peta di layar. */}
                        {sampleTypesOf(s).map((c) => typeLabel(c, types)).join(" + ")
                          || "—"} ·
                        {" "}{(s.participants || []).length} supplier ·
                        {" "}{(s.rounds || []).length} round
                      </span>
                      <span className={`status-pill ${sm.cls}`}>{sm.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {spec?.status === "review" && canApprove && canWrite && (
            <div className="rounded-lg border border-[#D9E8FF] bg-[#F7FBFF] p-3"
              data-testid="spec-approve-form">
              <p className="mb-2 text-[11.5px] font-semibold text-[#004099]">
                Setujui spesifikasi → produk baru akan lahir (belum boleh dijual)
              </p>
              <div className="grid gap-2 md:grid-cols-3">
                <label className="block">
                  <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Kode SKU</span>
                  <input className="field" data-testid="spec-approve-sku" value={sku}
                    onChange={(e) => setSku(e.target.value)} />
                </label>
                <label className="block">
                  <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Nama produk</span>
                  <input className="field" data-testid="spec-approve-name" value={name}
                    onChange={(e) => setName(e.target.value)} />
                </label>
                <label className="block">
                  <span className="mb-1 block text-[10.5px] font-semibold text-[#6B6B73]">Harga jual (Rp)</span>
                  <MoneyInput className="field" testId="spec-approve-price" value={price}
                    onChange={(v) => setPrice(v)} />
                </label>
              </div>
            </div>
          )}

          {(spec?.timeline || []).length > 0 && (
            <div className="rounded-lg border border-[#EFF0F2] p-3" data-testid="spec-detail-timeline">
              <p className="mb-1.5 text-[10.5px] font-bold uppercase text-[#8E8E93]">Riwayat</p>
              <ul className="space-y-1">
                {spec.timeline.slice().reverse().map((t, i) => (
                  <li key={i} className="text-[11px] text-[#3C3C43]">
                    <b>{t.label}</b>
                    {t.actor ? ` · ${t.actor}` : ""}
                    {t.note ? ` — ${t.note}` : ""}
                    <span className="text-[#9A9BA3]"> · {formatDateTime(t.at)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
          {spec?.status === "draft" && canSubmit && (
            <button className="primary-button" disabled={busy || !canWrite} title={writeBlockHint || undefined} data-testid="spec-submit-button"
              onClick={() => act(() => submitSpec(spec.id))}>
              <Send size={13} /> Ajukan untuk ACC
            </button>
          )}
          {spec?.status === "review" && canApprove && (
            <>
              <input className="field max-w-[220px]" placeholder="Alasan penolakan…" disabled={!canWrite || busy}
                data-testid="spec-reject-reason" value={reason}
                onChange={(e) => setReason(e.target.value)} />
              <button className="secondary-button" disabled={busy || !canWrite || reason.trim().length < REASON_MIN_LENGTH}
                title={writeBlockHint || (reason.trim().length < REASON_MIN_LENGTH ? `Alasan penolakan minimal ${REASON_MIN_LENGTH} huruf` : undefined)}
                data-testid="spec-reject-button"
                onClick={() => act(() => rejectSpec(spec.id, reason))}>
                <XCircle size={13} /> Tolak
              </button>
              <button className="primary-button" disabled={busy || !canWrite} title={writeBlockHint || undefined} data-testid="spec-approve-button"
                onClick={async () => {
                  const ov = await specOverride(spec.id, "ACC spesifikasi");
                  if (ov !== null) act(() => approveSpec(spec.id, { sku, name, price: price || 0, note: "", override_reason: ov }));
                }}>
                <CheckCircle2 size={13} /> Setujui & buat produk
              </button>
            </>
          )}
          {spec?.status === "approved" && spec?.lifecycle !== "produksi" && canRelease && (
            <button className="primary-button" disabled={busy || !canWrite} title={writeBlockHint || undefined} data-testid="spec-release-button"
              onClick={async () => {
                const ov = await specOverride(spec.id, "Rilis produk");
                if (ov !== null) act(() => releaseProduct(spec.id, "Sample sudah ACC & kontrak harga siap", "", ov));
              }}>
              <Rocket size={13} /> Rilis ke produksi (boleh dijual)
            </button>
          )}
          <button className="secondary-button" data-testid="spec-detail-dismiss" onClick={onClose}>Tutup</button>
        </div>
      </div>
    </div>
  );
}

function Box({ label, value, tone = "#1C1C1E", swatch, testId }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2" data-testid={testId}>
      <p className="text-[9.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="flex items-center gap-1.5 text-[12px] font-bold leading-tight"
        style={{ color: tone }}>
        {swatch && (
          <span className="inline-block h-3.5 w-3.5 rounded-full border border-[#E5E5EA]"
            style={{ background: swatch }} />
        )}
        {value}
      </p>
    </div>
  );
}
