/** Item & roll yang diretur (permintaan pemilik 23 Okt) — detail PER ROLL: qty, kondisi, alasan, checklist (hangtag
 *  hilang / sudah dipotong) & foto; keputusan Terima/Tolak per roll sebelum ACC oleh pemegang izin `decide_rolls`
 *  modul retur itu (dapat diatur di matriks akses). Roll ditolak keluar dari retur (scan, QC, nilai uang).
 *  Satu panel untuk retur pelanggan, retur ke supplier & retur antar-PT: pemanggil memetakan barisnya ke bentuk
 *  retur pelanggan (`quantity_returned`, `unit_price_est`, `line_total_est`, `roll_nos`) dan memberi URL-nya. */
import AttachmentGallery from "../../components/AttachmentThumb";
import { useMemo, useState } from "react";
import { Check, Loader2, Package, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { Panel } from "../../components/DetailParts";
import QtyDual from "../../components/QtyDual";
import { formatCurrency, formatQty } from "../../utils/formatters";
import { lengthAlt } from "../../utils/uom";   // 23 Okt — padanan yard↔meter

const Badge = ({ tone, children, testId }) => {
  const cls = { ok: "bg-[#E7F6EC] text-[#126E2C]", warn: "bg-[#FFF4E5] text-[#8C4A00]", bad: "bg-[#FDECEC] text-[#A8221A]",
    muted: "bg-[#F2F3F5] text-[#6B6B73]" }[tone] || "bg-[#F2F3F5] text-[#6B6B73]";
  return <span data-testid={testId} className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${cls}`}>{children}</span>;
};

/** Kolom Kondisi · Alasan · Checklist · Foto satu roll — sama untuk roll aktif maupun yang ditolak. */
function RollInfoCells({ d, cond, reason, photos, href }) {
  return (
    <>
      <td><Badge tone={cond === "damaged" ? "warn" : "ok"}>{cond === "damaged" ? "Rusak" : "Baik"}</Badge></td>
      <td className="text-[11.5px] text-[#3C3C43]">{reason || "—"}</td>
      <td className="space-x-1 whitespace-nowrap">
        {d.hangtag_missing && <Badge tone="warn">Hangtag hilang</Badge>}
        {d.cut_by_customer && <Badge tone="bad">Sudah dipotong</Badge>}
        {!d.hangtag_missing && !d.cut_by_customer && <span className="text-[11px] text-[#9A9BA3]">—</span>}
      </td>
      <td className="text-[11px]">
        {/* UAT 24 Okt (P17) — thumbnail + lightbox di halaman yang sama (dulu tautan "Foto 1" → unduhan). */}
        <AttachmentGallery items={photos.map((a) => ({ url: href(a), filename: a.filename, content_type: a.content_type }))}
          size={32} testId={`roll-photo-${d.roll_id || "x"}`} emptyText="—" />
      </td>
    </>
  );
}

export default function ReturnRollsPanel({ ret, items, fullView, canDecide, estimatedValue, onChanged,
  decideUrl, attachmentHref, canReject = true, title = "Item & roll yang diretur", hint, testId = "return-items-panel",
  valueLabel = "Estimasi nilai retur (harga transaksi SO per satuan dasar; angka resmi = Nota Kredit)" }) {
  const href = attachmentHref || ((a) => `${API}/sales-returns/${ret.id}/attachments/${a.id}/download`);
  const [draft, setDraft] = useState({});   // { roll_id: { decision, reason } }
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const photos = useMemo(() => {
    const m = {};
    (ret.attachments || []).filter((a) => !a.is_deleted && a.roll_id).forEach((a) => { (m[a.roll_id] = m[a.roll_id] || []).push(a); });
    return m;
  }, [ret.attachments]);
  const pending = Object.entries(draft).filter(([, d]) => d.decision);

  async function save() {
    const bad = pending.filter(([, d]) => d.decision === "reject" && (d.reason || "").trim().length < 5);
    if (bad.length) { setErr("Isi alasan tolak (min. 5 huruf) untuk setiap roll yang ditolak."); return; }
    setBusy(true); setErr("");
    try {
      await axios.post(decideUrl || `${API}/sales-returns/${ret.id}/roll-decisions`,
        { decisions: pending.map(([roll_id, d]) => ({ roll_id, decision: d.decision, reason: (d.reason || "").trim() })) });
      setDraft({});
      onChanged?.();
    } catch (e) {
      setErr(e.response?.data?.detail || "Gagal menyimpan keputusan roll.");
    } finally { setBusy(false); }
  }

  return (
    <Panel icon={Package} title={`${title} · ${items.length} produk`} testId={testId}>
      <div className="space-y-3">
        {items.map((item, i) => {
          const rolls = item.roll_ids || [];
          const det = item.roll_details || {};
          const nos = item.roll_nos || {};
          return (
            <div key={`${item.product_id}-${i}`} className="overflow-hidden rounded-lg border border-[#EFF0F2]" data-testid={`return-item-${i}`}>
              <div className="flex flex-wrap items-start justify-between gap-2 bg-[#FAFBFC] px-3 py-2">
                <div className="min-w-0">
                  <p className="truncate text-[12.5px] font-semibold text-[#1C1C1E]">{item.product_name || item.product_id}</p>
                  <p className="font-mono text-[10.5px] text-[#6B6B73]">{item.sku || "—"}</p>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] tabular-nums">
                  <span>Diklaim <b><QtyDual rolls={item.qty_rolls} measure={item.quantity_returned} unit={item.unit} compact /></b>
                    {lengthAlt(item.quantity_returned, item.unit) && <span className="text-[#6B6B73]"> {lengthAlt(item.quantity_returned, item.unit)}</span>}</span>
                  {fullView && item.unit_price_est != null && (
                    <span className="text-[#6B6B73]" data-testid={`return-item-value-${i}`}>{formatCurrency(item.unit_price_est)}/{item.unit} · <b className="text-[#1C1C1E]">{formatCurrency(item.line_total_est)}</b></span>
                  )}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="data-table" style={{ minWidth: 760 }}>
                  <thead>
                    <tr><th>Roll</th><th className="text-right">Qty</th><th>Kondisi</th><th>Alasan</th><th>Checklist</th><th>Foto</th><th>Keputusan</th></tr>
                  </thead>
                  <tbody>
                    {rolls.length === 0 && (
                      <tr><td colSpan={7} className="text-[11.5px] text-[#6B6B73]">Baris tanpa roll · {item.condition === "ok" ? "Baik" : "Rusak"} · {item.reason || "—"}</td></tr>
                    )}
                    {rolls.map((rid) => {
                      const d = det[rid] || {};
                      const cond = d.condition || item.condition;
                      const dr = draft[rid] || {};
                      const decided = d.decision === "accept" ? <Badge tone="ok" testId={`roll-decision-${rid}`}>Diterima</Badge> : null;
                      return (
                        <tr key={rid} data-testid={`return-roll-${rid}`}>
                          <td className="font-mono text-[11.5px] font-semibold">{nos[rid] || rid}</td>
                          <td className="text-right tabular-nums">{formatQty((item.roll_qtys || {})[rid])} {item.unit}</td>
                          <RollInfoCells d={d} cond={cond} reason={d.reason || item.reason} photos={photos[rid] || []} href={href} />
                          <td className="min-w-[220px]">
                            {canDecide ? (
                              <div className="space-y-1">
                                <div className="inline-flex overflow-hidden rounded-md border border-[#E5E5EA] text-[11px] font-semibold">
                                  <button type="button" data-testid={`roll-accept-${rid}`}
                                    className={`inline-flex items-center gap-1 px-2 py-1 ${(dr.decision || d.decision) === "accept" ? "bg-[#E7F6EC] text-[#126E2C]" : "bg-white text-[#3C3C43]"}`}
                                    onClick={() => setDraft((x) => ({ ...x, [rid]: { decision: "accept", reason: "" } }))}><Check size={11} /> Terima</button>
                                  {canReject && <button type="button" data-testid={`roll-reject-${rid}`}
                                    className={`inline-flex items-center gap-1 border-l border-[#E5E5EA] px-2 py-1 ${dr.decision === "reject" ? "bg-[#FDECEC] text-[#A8221A]" : "bg-white text-[#3C3C43]"}`}
                                    onClick={() => setDraft((x) => ({ ...x, [rid]: { decision: "reject", reason: x[rid]?.reason || "" } }))}><X size={11} /> Tolak</button>}
                                </div>
                                {dr.decision === "reject" && (
                                  <input className="form-input !py-1 text-[11.5px]" placeholder="Alasan tolak (mis. kain sudah dipotong)"
                                    data-testid={`roll-reject-reason-${rid}`} value={dr.reason || ""}
                                    onChange={(e) => setDraft((x) => ({ ...x, [rid]: { ...x[rid], reason: e.target.value } }))} />
                                )}
                              </div>
                            ) : (decided || <span className="text-[11px] text-[#9A9BA3]">—</span>)}
                          </td>
                        </tr>
                      );
                    })}
                    {(item.rejected_rolls || []).map((r) => {
                      const d = det[r.roll_id] || {};
                      return (
                        <tr key={`rej-${r.roll_id}`} className="bg-[#FFF8F8]" data-testid={`return-roll-rejected-${r.roll_id}`}>
                          <td className="font-mono text-[11.5px] font-semibold text-[#6B6B73] line-through">{r.roll_no}</td>
                          <td className="text-right tabular-nums text-[#6B6B73] line-through">{formatQty(r.qty)} {r.unit}</td>
                          <RollInfoCells d={d} cond={d.condition || item.condition} reason={d.reason} photos={photos[r.roll_id] || []} href={href} />
                          <td className="text-[11px]"><Badge tone="bad">{r.by_supplier ? "Ditolak supplier" : "Ditolak"}</Badge>
                            <span className="block text-[#6B6B73]">{r.reason} · {r.by}</span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>
      {fullView && estimatedValue != null && (
        <div className="mt-2 flex items-center justify-between rounded-md bg-[#FAFBFC] px-3 py-2 text-[12px]" data-testid="return-estimated-value">
          <span className="text-[#6B6B73]">{valueLabel}</span>
          <b className="tabular-nums">{formatCurrency(estimatedValue)}</b>
        </div>
      )}
      {canDecide && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-[#EFF0F2] pt-2">
          <p className="text-[11.5px] text-[#6B6B73]">{hint || "Roll yang ditolak keluar dari retur (tetap di pelanggan). Roll tanpa keputusan ikut disetujui saat ACC."}</p>
          {err && <p className="w-full text-[11.5px] font-semibold text-[#A8221A]" data-testid="roll-decisions-error">{err}</p>}
          <button type="button" className="primary-button" disabled={busy || !pending.length} onClick={save} data-testid="roll-decisions-save">
            {busy ? <Loader2 size={13} className="spin" /> : <Check size={13} />} Simpan keputusan roll ({pending.length})
          </button>
        </div>
      )}
    </Panel>
  );
}
