/**
 * PutawayDraftsPanel (PREP-C · K-GDG-10, keputusan pemilik 8 Nov 2026) — DRAF Putaway Order yang disiapkan sistem
 * sesudah QC lulus / GRN tanpa QC / SPK QC 4-point ditutup. Admin gudang mengecek isi & tujuan (boleh ubah), lalu
 * MENERBITKAN. Draf tidak mengunci stok; roll yang tag/labelnya belum terverifikasi ditandai "belum siap" — terbitkan
 * yang siap saja, sisanya tetap draf. Roll yang diminta inspeksi diarahkan ke gedung inspeksi.
 */
import { useState } from "react";
import { FileClock, Send, Trash2, Wand2, Microscope, ChevronDown, ChevronUp } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import axios, { API } from "../../services/apiClient";
import { askReason, askConfirm } from "../../services/confirmService";
import { draftReadiness, purposeLabel } from "./putawayUtils";
import ExportMenu from "../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)

export default function PutawayDraftsPanel({ drafts = [], whId, onChanged }) {
  const [openId, setOpenId] = useState("");
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState("");

  const run = async (fn, ok) => {
    setBusy(true); setError(null);
    try { const r = await fn(); if (ok) setMsg(ok(r)); await onChanged?.(); return r; }
    catch (e) { setError(e); return null; } finally { setBusy(false); }
  };
  const loadDetail = async (id) => {
    const r = await run(() => axios.get(`${API}/putaway-orders/${id}`).then((x) => x.data));
    if (r) setDetail(r);
  };
  const toggle = async (id) => {
    if (openId === id) { setOpenId(""); setDetail(null); return; }
    setOpenId(id); setDetail(null); await loadDetail(id);
  };
  const prepare = () => run(() => axios.post(`${API}/putaway-orders/auto-draft`, { from_warehouse_id: whId }).then((x) => x.data),
    (r) => (r.drafts.length ? `${r.drafts.length} draf disiapkan.` : "Tidak ada roll baru untuk dibuatkan draf.")
      + ((r.unrouted || []).length ? ` ${r.unrouted.length} roll tanpa tujuan yang cocok.` : ""));
  const patch = async (id, body) => {
    const r = await run(() => axios.patch(`${API}/putaway-orders/${id}/draft`, body).then((x) => x.data), () => "Draf diperbarui.");
    if (r) setDetail(r);
  };
  const publish = async (d, split) => {
    const r = await run(() => axios.post(`${API}/putaway-orders/${d.id}/publish`, { split_unready: split }).then((x) => x.data),
      (o) => `${o.pa_number} diterbitkan (${o.item_count} roll) — siap dikirim.`);
    if (r) { setOpenId(""); setDetail(null); }
  };
  const cancel = async (d) => {
    const why = await askReason({ title: `Batalkan draf ${d.pa_number}?`, message: "Roll tetap di gudang asal & bisa dibuatkan PA lagi.",
      confirmLabel: "Batalkan draf", reasonMinLength: 5, testId: "pa-draft-cancel-dialog" });
    if (!why) return;
    await run(() => axios.post(`${API}/putaway-orders/${d.id}/cancel-draft`, { reason: why.trim() }), () => "Draf dibatalkan.");
    setOpenId(""); setDetail(null);
  };
  const removeRoll = async (d, it) => {
    if (await askConfirm({ title: `Keluarkan ${it.roll_no} dari draf?`, confirmLabel: "Keluarkan", testId: "pa-draft-remove-dialog" })) {
      await patch(d.id, { remove_roll_ids: [it.roll_id] });
    }
  };

  const notReadyErr = error?.response?.status === 409 && error?.response?.data?.detail?.code === "PA_DRAFT_NOT_READY";
  return (
    <section className="section-card" data-testid="pa-drafts">
      <div className="section-head flex flex-wrap items-center gap-2">
        <h2 className="flex flex-1 items-center gap-1.5 text-[13px] font-bold"><FileClock size={15} className="text-[#6B219A]" /> Draf Putaway otomatis ({drafts.length})</h2>
        <ExportMenu dataset="putaway_orders" label="draf-putaway" scope="work" testId="pa-drafts-export"
          filters={[["status", "eq", "draft"], whId && ["from_warehouse_id", "eq", whId]]} sort={[{ key: "created_at", dir: "desc" }]} />
        {whId && (
          <button type="button" data-testid="pa-drafts-prepare" disabled={busy} onClick={prepare}
            className="flex items-center gap-1 rounded-lg border border-[#6B219A] px-3 py-1.5 text-[11.5px] font-semibold text-[#6B219A] disabled:opacity-40">
            <Wand2 size={12} /> Siapkan draf
          </button>
        )}
      </div>
      <div className="section-body space-y-2">
        {error && !notReadyErr && <ErrorNotice message={error} onDismiss={() => setError(null)} testId="pa-drafts-error" />}
        {notReadyErr && (
          <div data-testid="pa-drafts-not-ready" className="rounded-lg bg-[#FFF4E5] px-3 py-2 text-[11.5px] text-[#8C4A00]">
            <p className="font-bold">{error.response.data.detail.message}</p>
            <p>{(error.response.data.detail.rolls || []).slice(0, 6).map((x) => `${x.roll_no}: ${x.reason}`).join(" · ")}</p>
          </div>
        )}
        {msg && <p data-testid="pa-drafts-msg" className="rounded-lg bg-[#E7F7EC] px-3 py-2 text-[12px] font-semibold text-[#1B7E3B]">{msg}</p>}
        {drafts.length === 0 && (
          <p className="py-4 text-center text-[12px] text-[#8E8E93]" data-testid="pa-drafts-empty">
            Belum ada draf. Draf lahir otomatis sesudah QC lulus / GRN tanpa QC (bisa dimatikan di Pengaturan: "Siapkan draf Putaway Order otomatis").
          </p>
        )}
        {drafts.map((d) => {
          const open = openId === d.id;
          const rd = open && detail ? draftReadiness(detail) : null;
          return (
            <div key={d.id} data-testid={`pa-draft-${d.id}`} className="rounded-lg border border-[#E9DDF3] p-2.5">
              <button type="button" className="flex w-full items-center gap-2 text-left" onClick={() => toggle(d.id)} data-testid={`pa-draft-toggle-${d.id}`}>
                <div className="min-w-0 flex-1">
                  <p className="text-[12.5px] font-bold">{d.pa_number}
                    {d.purpose === "inspection" && <span className="ml-1.5 rounded bg-[#EAF2FF] px-1.5 py-0.5 text-[10px] font-bold text-[#0058CC]"><Microscope size={10} className="mr-0.5 inline" />Inspeksi</span>}
                  </p>
                  <p className="text-[11px] text-[#6B6B73]">{d.from_warehouse_name} → <b>{d.to_warehouse_name}</b> · {d.item_count} roll · {purposeLabel(d.purpose)}
                    {d.auto?.trigger?.number ? ` · dari ${d.auto.trigger.number}` : ""}</p>
                </div>
                {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {open && detail && (
                <div className="mt-2 space-y-2" data-testid={`pa-draft-detail-${d.id}`}>
                  <p className="text-[11.5px]" data-testid={`pa-draft-readiness-${d.id}`}>
                    <b className="text-[#1B7F4B]">{rd.ready} siap</b> · <b className="text-[#8C4A00]">{rd.notReady} belum siap</b>
                    {rd.inspection ? ` · ${rd.inspection} diminta inspeksi` : ""}
                  </p>
                  {detail.inspection_warning && <p className="rounded bg-[#EAF2FF] px-2 py-1 text-[11px] text-[#0058CC]">{detail.inspection_warning}</p>}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[11px] text-[#6B6B73]">Tujuan</span>
                    <KNSelect data-testid={`pa-draft-dest-${d.id}`} value={detail.to_warehouse_id}
                      options={(detail.destination_options || []).map((o) => ({ value: o.warehouse_id, label: o.warehouse_name }))}
                      onValueChange={(v) => v && v !== detail.to_warehouse_id && patch(d.id, { to_warehouse_id: v })}
                      className="field !py-1 !px-2 w-auto text-[12px]" />
                  </div>
                  <div className="max-h-56 space-y-1 overflow-y-auto">
                    {(detail.items || []).map((it) => (
                      <div key={it.roll_id} className="flex flex-wrap items-center gap-2 rounded bg-[#FAFAFB] px-2 py-1 text-[11.5px]" data-testid={`pa-draft-item-${it.roll_id}`}>
                        <span className={`h-2 w-2 rounded-full ${it.ready ? "bg-[#1B7F4B]" : "bg-[#FF9500]"}`} />
                        <span className="flex-1">{it.roll_no} · {it.sku} · {it.qty} {it.unit}
                          {it.inspection_requested && <span className="ml-1 text-[10px] font-bold text-[#0058CC]">minta inspeksi</span>}
                          {!it.ready && it.block_reason && <span className="block text-[10.5px] text-[#8C4A00]">{it.block_reason}</span>}
                        </span>
                        <button type="button" aria-label={`Keluarkan ${it.roll_no}`} data-testid={`pa-draft-remove-${it.roll_id}`} disabled={busy}
                          onClick={() => removeRoll(d, it)} className="rounded p-1 text-[#C0341D] hover:bg-[#FBE9E7] disabled:opacity-40"><Trash2 size={12} /></button>
                      </div>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <button type="button" data-testid={`pa-draft-publish-${d.id}`} disabled={busy || rd.ready === 0 || rd.notReady > 0}
                      onClick={() => publish(d, false)}
                      className="flex items-center gap-1 rounded-lg bg-[#0058CC] px-3 py-1.5 text-[11.5px] font-semibold text-white disabled:opacity-40">
                      <Send size={12} /> Terbitkan
                    </button>
                    {rd.notReady > 0 && (
                      <button type="button" data-testid={`pa-draft-publish-ready-${d.id}`} disabled={busy || rd.ready === 0}
                        onClick={() => publish(d, true)}
                        className="rounded-lg border border-[#0058CC] px-3 py-1.5 text-[11.5px] font-semibold text-[#0058CC] disabled:opacity-40">
                        Terbitkan {rd.ready} yang siap (sisa tetap draf)
                      </button>
                    )}
                    <button type="button" data-testid={`pa-draft-cancel-${d.id}`} disabled={busy} onClick={() => cancel(d)}
                      className="rounded-lg border border-[#C0341D] px-3 py-1.5 text-[11.5px] font-semibold text-[#C0341D] disabled:opacity-40">
                      Batalkan draf
                    </button>
                  </div>
                </div>
              )}
              {open && !detail && !error && <p className="mt-2 text-[11px] text-[#8E8E93]">Memuat…</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
