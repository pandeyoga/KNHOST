/**
 * Harga final Pesanan Khusus.
 * UAT 24 Okt (P2, arahan pemilik SO-12):
 *  · Dasar harga per item: item ber-induk → harga Grade A induk; tanpa induk → harga diisi PIC Special Order
 *    (`od_pricing.set_price`); kontrak + margin hanya pembanding laba untuk pemegang `od_pricing.view_cost`.
 *  · Kunci harga oleh Admin Sales/Manajer/Admin (`od_pricing.lock`) → SO langsung lahir, pengadaan menyusul.
 *  · Sales melihat harga final & mengajukan "harga nego" lewat mekanisme harga khusus SO (diputus Manajer);
 *    selama nego belum beres, realisasi pengadaan ditahan.
 */
import { useEffect, useState } from "react";
import { Lock, Unlock, Loader2, Percent, Handshake, Save } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { askReason } from "@/services/confirmService";
import { fmtNum, fmtDate, fmtDay, docStatus } from "./SpecialOrderShared";
import { can, roleIs } from "../../config/roles";
import { notifySuccess } from "../../utils/feedback";
import { formatCurrency } from "../../utils/formatters";
import SiteSelect from "../../components/SiteSelect";

const NEGO_STATUS = { pending: "Menunggu Manajer", approved: "Disetujui", rejected: "Ditolak", superseded: "Diganti pengajuan baru", cancelled: "Lanjut harga normal" };
const BASIS_TONE = { parent_grade_a: "bg-[#EAF2FF] text-[#0058CC]", pic: "bg-[#F3E8FF] text-[#6B21A8]", cost_margin: "bg-[#FFF4E5] text-[#B45309]", negotiated: "bg-[#E9F7EF] text-[#1B7F4B]" };

const numMap = (m) => Object.fromEntries(Object.entries(m).filter(([, v]) => v !== "" && v != null && !Number.isNaN(Number(v))).map(([k, v]) => [k, Number(v)]));

export default function SpecialOrderPricingPanel({ order, currentUser, onUpdated }) {
  const saved = (order.chain || {}).pricing || {};
  const locked = !!saved.locked;
  const accd = order.customer_decision === "acc";
  const perms = currentUser?.permissions;
  const canLock = can(perms, "od_pricing", "lock") && can(perms, "order", "update") && accd && !locked && order.status !== "cancelled";
  const canSetPrice = can(perms, "od_pricing", "set_price");
  const canSeeCost = can(perms, "od_pricing", "view_cost");
  const canProcure = can(perms, "purchase_requisition", "create") && can(perms, "od_fulfillment", "realize");
  const canNego = can(perms, "order", "update");
  const [margin, setMargin] = useState(saved.margin_pct ?? 30);
  const [itemMargins, setItemMargins] = useState({});
  const [itemPrices, setItemPrices] = useState({});   // harga PIC per satuan item (item tanpa induk)
  const [unitPrice, setUnitPrice] = useState("");      // OD satu item tanpa induk
  const [pv, setPv] = useState(saved);
  const multi = pv.mode === "items" && Array.isArray(pv.items);
  const [note, setNote] = useState("");
  const [siteId, setSiteId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => { setPv(saved); if (saved.margin_pct != null) setMargin(saved.margin_pct); }, [saved.locked, saved.margin_pct, saved.cost_price]); // eslint-disable-line

  const key = JSON.stringify([itemMargins, itemPrices, unitPrice]);
  useEffect(() => {
    if (!accd && !locked) return undefined;
    let stale = false;   // hanya respons untuk input terakhir yang dipakai
    const t = setTimeout(async () => {
      try {
        const params = locked ? {} : { margin_pct: margin, item_margins: JSON.stringify(numMap(itemMargins)), item_prices: JSON.stringify(numMap(itemPrices)) };
        if (!locked && unitPrice !== "" && !Number.isNaN(Number(unitPrice))) params.unit_price = Number(unitPrice);
        const r = await axios.get(`${API}/special-orders/${order.id}/pricing`, { params });
        if (!stale) setPv(r.data);
      } catch { /* biarkan */ }
    }, 250);
    return () => { stale = true; clearTimeout(t); };
  }, [margin, key, order.id, locked, accd, reload]); // eslint-disable-line

  const refresh = async () => {
    const r = await axios.get(`${API}/special-orders/${order.id}`);
    onUpdated?.(r.data);
    setReload((n) => n + 1);
  };
  const lock = async () => {
    setBusy(true); setErr("");
    try {
      const body = { margin_pct: Number(margin), item_margins: numMap(itemMargins), note, site_id: siteId };
      if (canSetPrice) { body.item_prices = numMap(itemPrices); if (unitPrice !== "") body.unit_price = Number(unitPrice); }
      const r = await axios.post(`${API}/special-orders/${order.id}/lock-price`, body);
      onUpdated?.(r.data.special_order);
      const od = r.data.special_order || {};
      notifySuccess("Harga dikunci", `${order.number} · total ${formatCurrency(r.data.pricing?.total || od.total_amount)}.`
        + (od.linked_sales_order_number ? ` SO ${od.linked_sales_order_number} terbit — sales bisa mengajukan harga nego sebelum PO.` : od.shipping_error ? ` ${od.shipping_error}` : ""));
    }
    catch (e) { setErr(e.response?.data?.detail || "Gagal mengunci harga."); } finally { setBusy(false); }
  };
  const savePic = async () => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/special-orders/${order.id}/pic-prices`, { item_prices: numMap(itemPrices), unit_price: unitPrice === "" ? null : Number(unitPrice) });
      notifySuccess("Harga PIC disimpan", "Pengunci harga memakai harga ini untuk item tanpa induk.");
      setReload((n) => n + 1);
    } catch (e) { setErr(e.response?.data?.detail || "Gagal menyimpan harga PIC."); } finally { setBusy(false); }
  };
  const unlock = async () => {
    const reason = await askReason({ title: `Buka kunci harga ${order.number}?`, danger: true, testId: "od-price-unlock-confirm" });
    if (!reason) return;
    setBusy(true); setErr("");
    try { const r = await axios.post(`${API}/special-orders/${order.id}/unlock-price`, { reason }); onUpdated?.(r.data); }
    catch (e) { setErr(e.response?.data?.detail || "Gagal membuka kunci."); } finally { setBusy(false); }
  };
  const procure = async () => {
    setBusy(true); setErr("");
    try { const r = await axios.post(`${API}/special-orders/${order.id}/procure`, { warehouse_id: order.procurement_warehouse_id || "" }); onUpdated?.(r.data.special_order); setReload((n) => n + 1); }
    catch (e) { setErr(e.response?.data?.detail || "Gagal membuat PR/PO."); } finally { setBusy(false); }
  };
  const pos = (order.chain || {}).po || [];
  const po = pos.find((p) => p.status !== "cancelled") || pos[0];
  const nego = pv.nego || {};
  const priceInput = (it) => !locked && canSetPrice && it && ["cost_margin", "pic"].includes(it.basis);

  if (!accd && !locked) {
    return (
      <section className="section-card !p-3" data-testid="od-pricing">
        <p className="mb-1 text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">Harga final &amp; confirmed</p>
        <p className="rounded-lg border border-dashed border-[#D9D9DE] px-3 py-3 text-[11px] text-[#9A9BA3]" data-testid="od-pricing-waiting">
          Menunggu ACC pelanggan. Harga final{multi ? ` per item (${pv.items.length} item)` : ""}: item dari induk produk memakai harga Grade A induk;
          item tanpa induk diisi PIC Special Order.
        </p>
      </section>
    );
  }
  return (
    <section className="section-card !p-3" data-testid="od-pricing">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">Harga final &amp; confirmed</p>
        {locked ? <span className="inline-flex items-center gap-1 rounded-full bg-[#E9F7EF] px-2 py-0.5 text-[10.5px] font-bold text-[#1B7F4B]" data-testid="od-price-locked"><Lock size={10} /> Dikunci {saved.locked_by} · {fmtDate(saved.locked_at)}</span>
          : <span className="rounded-full bg-[#FFF4E5] px-2 py-0.5 text-[10.5px] font-bold text-[#B45309]" data-testid="od-price-open">Belum dikunci</span>}
      </div>
      {!locked && canSeeCost && (pv.needs_pic || (!multi && pv.basis === "cost_margin")) && (
        <p className="mb-1.5 inline-flex flex-wrap items-center gap-1 text-[11px]">
          Margin usulan untuk item tanpa induk
          <input type="number" min="0" max="500" step="0.5" className="input !w-20 !py-0.5 text-right" value={margin}
            onChange={(e) => setMargin(e.target.value)} disabled={!canLock && !canSetPrice} data-testid="od-price-margin" /><Percent size={12} />
          <span className="text-[10px] text-[#6B6B73]">hanya usulan — harga final item tanpa induk diputus PIC</span>
        </p>
      )}
      {multi ? (
        <ItemPricingTable pv={pv} locked={locked} canSeeCost={canSeeCost} priceInput={priceInput} margin={margin}
          itemMargins={itemMargins} onItemMargin={(id, v) => setItemMargins((m) => ({ ...m, [id]: v }))}
          itemPrices={itemPrices} onItemPrice={(id, v) => setItemPrices((m) => ({ ...m, [id]: v }))} />
      ) : (
        <div className="grid gap-2 text-[11.5px] sm:grid-cols-4">
          <Cell label="Dasar harga" testId="od-price-basis"><BasisChip it={pv} /><span className="block text-[10px] text-[#6B6B73]">{pv.ref_sku ? <>acuan <span className="font-mono">{pv.ref_sku}</span> · </> : null}{pv.basis_note}</span></Cell>
          {canSeeCost && <Cell label="Harga kontrak supplier" testId="od-price-cost"><b>Rp {fmtNum(pv.cost_price)}</b>/{pv.base_unit || pv.unit}<span className="block text-[10px] text-[#6B6B73]">{pv.supplier_name || "—"}{pv.contract_number ? ` · ${pv.contract_number}` : ""} · pembanding Rp {fmtNum(pv.comparator_unit_price)}</span></Cell>}
          <Cell label="Harga final / satuan" testId="od-price-final">
            {priceInput(pv) ? (
              <span className="inline-flex items-center gap-1">Rp <input type="number" min="0" className="input !w-28 !py-0.5 text-right" placeholder={String(Math.round((pv.final_unit_price || 0) * (pv.unit_factor || 1)))}
                value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} data-testid="od-price-pic-unit" />/{pv.unit}</span>
            ) : <><b className="text-[13px] text-[#0058CC]">Rp {fmtNum(pv.price_per_unit || pv.final_unit_price)}</b>/{pv.unit}</>}
            {canSeeCost && pv.loss && <span className="block text-[10px] font-semibold text-[#C0392B]" data-testid="od-price-loss">di bawah biaya kontrak — Manajer diberi peringatan</span>}
          </Cell>
          <Cell label={`Total (${fmtNum(pv.quantity)} ${pv.unit})`} testId="od-price-total"><b className="text-[13px]">Rp {fmtNum(pv.total)}</b></Cell>
        </div>
      )}
      {!multi && pv.product_sku && <p className="mt-1.5 text-[10.5px] text-[#6B6B73]">SKU eksklusif <b className="font-mono">{pv.product_sku}</b> → harga jual master produk ikut harga final saat dikunci / nego disetujui.</p>}
      {err && <p className="mt-1 text-[11px] text-[#C0392B]" data-testid="od-price-error">{err}</p>}
      {canLock && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="w-64"><SiteSelect testId="od-price-site" value={siteId} onChange={setSiteId} required={false}
            entityId={order.entity_id || ""} label="Lokasi kirim pengadaan (kosong = lokasi bawaan PT)" /></div>
          <input className="input !w-64 !py-1 text-[11px]" placeholder="catatan (opsional)" value={note} onChange={(e) => setNote(e.target.value)} data-testid="od-price-note" />
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {!locked && canSetPrice && (multi ? pv.items?.some(priceInput) : priceInput(pv)) && (
          <button type="button" className="secondary-button !py-1 text-[11px]" disabled={busy} onClick={savePic} data-testid="od-price-pic-save"><Save size={12} /> Simpan harga PIC</button>
        )}
        {canLock && (
          <button type="button" className="primary-button !py-1 text-[11px]" disabled={busy || (multi ? !pv.ready : !pv.cost_price)} onClick={lock} data-testid="od-price-lock-button">{busy ? <Loader2 size={12} className="spin" /> : <Lock size={12} />} Kunci harga &amp; buat SO</button>
        )}
        {!locked && accd && !canLock && <span className="text-[10.5px] text-[#6B6B73]" data-testid="od-price-lock-hint">Harga dikunci Admin Sales / Manajer.</span>}
        {locked && roleIs(currentUser?.role, ["admin"]) && can(perms, "order", "update") && !order.linked_pr_id && !order.linked_sales_order_id && !order.linked_po_id && !order.linked_mko_id && (
          <button type="button" className="secondary-button !py-1 text-[11px]" disabled={busy} onClick={unlock} data-testid="od-price-unlock-button"><Unlock size={12} /> Buka kunci (admin)</button>
        )}
        {saved.unlocked_at && !locked && <span className="text-[10.5px] text-[#B45309]">dibuka {saved.unlocked_by} · {saved.unlock_reason}</span>}
      </div>
      {locked && <NegoBox orderId={order.id} nego={nego} canNego={canNego} onChanged={refresh} />}
      {locked && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]" data-testid="od-procurement">
          {po && <span className="rounded-full bg-[#E9F7EF] px-2 py-0.5 font-bold text-[#1B7F4B]" data-testid="od-po-chip">{pos.filter((p) => p.status !== "cancelled").length > 1 ? `${pos.filter((p) => p.status !== "cancelled").length} PO — rincian di panel Pemenuhan produksi` : <>PO <span className="font-mono">{po.po_number}</span>{po.supplier_name ? ` · ${po.supplier_name}` : ""} · {docStatus(po.status)}{po.expected_delivery_date ? ` · tiba ${fmtDay(po.expected_delivery_date)}` : ""}</>}</span>}
          {order.linked_mko_id && <span className="rounded-full bg-[#E9F7EF] px-2 py-0.5 font-bold text-[#1B7F4B]" data-testid="od-mko-chip">MKO <span className="font-mono">{order.linked_mko_number}</span> · makloon</span>}
          {!po && !order.linked_mko_id && <span className="text-[#B45309]" data-testid="od-po-missing">{nego.block || `Pengadaan belum direalisasi${order.procurement_note ? ` — ${order.procurement_note}` : order.procurement_error ? ` — ${order.procurement_error}` : ""}`}</span>}
          {!po && !order.linked_mko_id && canProcure && (!order.procurement_note || roleIs(currentUser?.role, ["manager", "admin"])) && (
            <button type="button" className="secondary-button !py-1 text-[11px]" disabled={busy || !!nego.block} title={nego.block || ""} onClick={procure} data-testid="od-procure-button">{busy ? <Loader2 size={12} className="spin" /> : null} Realisasi pengadaan</button>
          )}
        </div>
      )}
    </section>
  );
}

function BasisChip({ it }) {
  if (!it?.basis) return <span className="text-[#9A9BA3]">—</span>;
  return <span className={`inline-block rounded-full px-1.5 py-0.5 text-[10px] font-bold ${BASIS_TONE[it.basis] || ""}`} data-testid="od-price-basis-chip">{it.basis_label}</span>;
}

/** Rincian harga per item OD: dasar harga (Grade A induk / PIC / usulan), harga final, total; biaya hanya untuk view_cost. */
function ItemPricingTable({ pv, locked, canSeeCost, priceInput, margin, itemMargins, onItemMargin, itemPrices, onItemPrice }) {
  return (
    <div className="text-[11.5px]" data-testid="od-price-items">
      <div className="overflow-x-auto rounded-lg border border-[#EFF0F2]">
        <table className="w-full min-w-[720px] bg-white">
          <thead className="bg-[#F7F8FA] text-left text-[10px] uppercase tracking-wide text-[#8E8E93]">
            <tr><th className="px-2 py-1">#</th><th className="px-2 py-1">Item &amp; produk hasil</th><th className="px-2 py-1 text-right">Qty</th>
              <th className="px-2 py-1">Dasar harga</th>
              {canSeeCost && <th className="px-2 py-1 text-right">Kontrak · pembanding</th>}
              {canSeeCost && !locked && <th className="px-2 py-1 text-right">Margin usulan</th>}
              <th className="px-2 py-1 text-right">Harga final</th><th className="px-2 py-1 text-right">Total</th><th className="px-2 py-1">Status</th></tr>
          </thead>
          <tbody>
            {pv.items.map((it) => (
              <tr key={it.item_id || it.key} className="border-t border-[#EFF0F2] align-top" data-testid={`od-price-item-row-${it.line_no}`}>
                <td className="px-2 py-1.5 tabular-nums">{it.line_no}</td>
                <td className="px-2 py-1.5">{it.description}
                  <span className="block text-[10px] text-[#6B6B73]">{it.product_sku ? <span className="font-mono">{it.product_sku}</span> : "produk hasil belum ada"}{canSeeCost && it.supplier_name ? ` · ${it.supplier_name}` : ""}{it.sample_number ? ` · ${it.sample_number}` : ""}</span></td>
                <td className="px-2 py-1.5 text-right tabular-nums">{fmtNum(it.quantity)} {it.unit}</td>
                <td className="px-2 py-1.5"><BasisChip it={it} />
                  <span className="block text-[10px] text-[#6B6B73]">{it.ref_sku ? <>acuan <span className="font-mono">{it.ref_sku}</span></> : it.basis_note}</span></td>
                {canSeeCost && <td className="px-2 py-1.5 text-right tabular-nums">{it.cost_price ? <>Rp {fmtNum(it.cost_price)}<span className="text-[10px] text-[#6B6B73]">/{it.base_unit || it.unit}</span><span className="block text-[10px] text-[#6B6B73]">+margin Rp {fmtNum(it.comparator_unit_price)}</span></> : "—"}</td>}
                {canSeeCost && !locked && (
                  <td className="px-2 py-1.5 text-right">{it.basis === "cost_margin" ? (
                    <input type="number" min="0" max="500" step="0.5" className="input !w-16 !py-0.5 text-right" placeholder={String(margin)}
                      value={itemMargins[it.item_id] ?? ""} onChange={(e) => onItemMargin(it.item_id, e.target.value)} data-testid={`od-price-item-margin-${it.line_no}`} />
                  ) : <span className="text-[10px] text-[#9A9BA3]">—</span>}</td>
                )}
                <td className="px-2 py-1.5 text-right tabular-nums" data-testid={`od-price-item-unit-${it.line_no}`}>
                  {priceInput(it) ? (
                    <input type="number" min="0" className="input !w-24 !py-0.5 text-right" placeholder={String(Math.round(it.price_per_unit || 0))}
                      value={itemPrices[it.item_id] ?? ""} onChange={(e) => onItemPrice(it.item_id, e.target.value)} data-testid={`od-price-item-pic-${it.line_no}`} />
                  ) : it.price_per_unit ? <b>Rp {fmtNum(it.price_per_unit)}</b> : "—"}<span className="text-[10px] text-[#6B6B73]">/{it.unit}</span>
                  {canSeeCost && it.loss && <span className="block text-[10px] font-semibold text-[#C0392B]">di bawah kontrak</span>}
                  {it.negotiated && <span className="block text-[10px] text-[#1B7F4B]">nego dari Rp {fmtNum(it.negotiated.previous_price_per_unit)}</span>}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums" data-testid={`od-price-item-total-${it.line_no}`}><b>Rp {fmtNum(it.total)}</b></td>
                <td className="px-2 py-1.5">
                  {locked ? <span className="rounded-full bg-[#E9F7EF] px-2 py-0.5 text-[10px] font-bold text-[#1B7F4B]">Terkunci</span>
                    : it.ready ? <span className="rounded-full bg-[#E9F7EF] px-2 py-0.5 text-[10px] font-bold text-[#1B7F4B]">Siap</span>
                    : <span className="text-[10.5px] text-[#C0392B]" data-testid={`od-price-item-blocker-${it.line_no}`}>{(it.blockers || []).join(" · ")}</span>}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-[#D9D9DE] bg-[#F7F8FA]">
              <td className="px-2 py-1.5" colSpan={4 + (canSeeCost ? 1 : 0) + (canSeeCost && !locked ? 1 : 0) + 1}><b>Total {pv.items.length} item</b>{pv.target_total ? <span className="ml-2 text-[10px] text-[#6B6B73]">target pelanggan Rp {fmtNum(pv.target_total)}</span> : null}</td>
              <td className="px-2 py-1.5 text-right tabular-nums" data-testid="od-price-items-total"><b className="text-[13px] text-[#0058CC]">Rp {fmtNum(pv.total)}</b></td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      {!locked && !pv.ready && (
        <p className="mt-1.5 text-[11px] text-[#B45309]" data-testid="od-price-items-not-ready">
          Harga belum bisa dikunci: semua item harus punya produk hasil &amp; harga kontrak — item tidak akan dihilangkan dari SO.
        </p>
      )}
    </div>
  );
}

/** P2.2 — nego harga per baris SO tertaut (mekanisme harga khusus SO, diputus Manajer; lantai = harga kontrak). */
function NegoBox({ orderId, nego, canNego, onChanged }) {
  const [open, setOpen] = useState("");
  const [price, setPrice] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!nego?.so_id) return null;
  const entriesOf = (ln) => (nego.entries || []).filter((e) => (ln.special_order_item_id ? e.special_order_item_id === ln.special_order_item_id : e.product_id === ln.product_id));
  const soOpen = ["reserved", "waiting_approval", "waiting_stock", "draft"].includes(nego.so_status);
  const submit = async (ln) => {
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/sales-orders/${nego.so_id}/request-special-price`, {
        special_order_item_id: ln.special_order_item_id || "", product_id: ln.product_id, requested_price: Number(price), reason });
      notifySuccess("Harga nego diajukan", "Menunggu keputusan Manajer di Pusat Persetujuan.");
      setOpen(""); setPrice(""); setReason("");
      onChanged?.();
    } catch (e) { setErr(e.response?.data?.detail?.message || e.response?.data?.detail || "Gagal mengajukan harga nego."); } finally { setBusy(false); }
  };
  const continueNormal = async (entry) => {
    setBusy(true); setErr("");
    try { await axios.post(`${API}/sales-orders/${nego.so_id}/approvals/${entry.id}/continue-normal-price`, {}); onChanged?.(); }
    catch (e) { setErr(e.response?.data?.detail || "Gagal."); } finally { setBusy(false); }
  };
  return (
    <div className="mt-2 rounded-lg border border-[#EFF0F2] p-2 text-[11px]" data-testid="od-nego">
      <p className="mb-1 flex items-center gap-1 font-semibold"><Handshake size={12} className="text-[#0058CC]" /> Harga nego · SO <span className="font-mono">{nego.so_number}</span></p>
      {(nego.lines || []).map((ln) => {
        const rows = entriesOf(ln);
        const pending = rows.find((e) => e.status === "pending");
        const rejected = rows.find((e) => e.status === "rejected");
        const k = `${ln.index}`;
        return (
          <div key={k} className="border-t border-[#F2F2F5] py-1.5 first:border-t-0" data-testid={`od-nego-line-${ln.index}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>{ln.product_name} · {fmtNum(ln.quantity)} {ln.unit} · <b>Rp {fmtNum(ln.price)}</b>/{ln.unit}{ln.price_source === "special_approval" ? " (harga nego)" : ""}</span>
              {canNego && soOpen && !pending && open !== k && (
                <button type="button" className="secondary-button !h-7 !text-[11px]" onClick={() => { setOpen(k); setErr(""); }} data-testid={`od-nego-open-${ln.index}`}>Ajukan harga nego</button>
              )}
            </div>
            {rows.filter((e) => ["pending", "rejected", "approved"].includes(e.status)).slice(-2).map((e) => (
              <p key={e.id} className={`text-[10.5px] ${e.status === "rejected" ? "text-[#C0392B]" : e.status === "pending" ? "text-[#B45309]" : "text-[#1B7F4B]"}`}>
                {NEGO_STATUS[e.status] || e.status}: Rp {fmtNum(e.requested_price)} · {e.requested_by}{e.decided_by ? ` → ${e.decided_by}` : ""}{e.decision_notes ? ` (${e.decision_notes})` : ""}
              </p>
            ))}
            {rejected && canNego && !pending && (
              <button type="button" className="secondary-button mt-1 !h-7 !text-[11px]" disabled={busy} onClick={() => continueNormal(rejected)} data-testid={`od-nego-normal-${ln.index}`}>Lanjut harga normal</button>
            )}
            {open === k && (
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <span>Rp</span><input type="number" min="0" className="input !w-28 !py-0.5 text-right" value={price} onChange={(e) => setPrice(e.target.value)} placeholder={String(ln.price)} data-testid={`od-nego-price-${ln.index}`} /><span>/{ln.unit}</span>
                <input className="input !w-56 !py-0.5" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="alasan (wajib)" data-testid={`od-nego-reason-${ln.index}`} />
                <button type="button" className="primary-button !h-7 !text-[11px]" disabled={busy || !Number(price) || !reason.trim()} onClick={() => submit(ln)} data-testid={`od-nego-submit-${ln.index}`}>Ajukan</button>
                <button type="button" className="secondary-button !h-7 !text-[11px]" onClick={() => setOpen("")}>Batal</button>
              </div>
            )}
          </div>
        );
      })}
      {!soOpen && <p className="text-[10.5px] text-[#6B6B73]">SO sudah melewati tahap pesanan — harga nego tidak bisa diajukan lagi.</p>}
      {err && <p className="mt-1 text-[10.5px] text-[#C0392B]" data-testid="od-nego-error">{typeof err === "string" ? err : JSON.stringify(err)}</p>}
    </div>
  );
}

function Cell({ label, children, testId }) {
  return <div className="rounded-lg border border-[#EFF0F2] bg-white p-2" data-testid={testId}><p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p><div className="mt-0.5">{children}</div></div>;
}
