/** Rincian OD — panel info: item custom (kiri), pelanggan + riwayat status (kanan). Gaya seragam dgn panel Fase 2–4. */
import { Fragment } from "react";
import { Clock, Package, User, History } from "lucide-react";
import { STATUS_STYLE, fmtDate, fmtDay } from "./SpecialOrderShared";
import { K, Panel, Cell, Timeline } from "../../components/DetailParts";
import { formatCurrency, formatQty } from "../../utils/formatters";


export function SpecialOrderInfoPanels({ order }) {
  const ci = order.custom_item || {};
  // 23 Okt — OD multi-item: dulu "Jumlah"/"Harga target" hanya item PERTAMA sementara "Nilai pesanan" = semua item.
  const items = (order.items || []).filter((i) => i.status !== "cancelled");
  const multi = items.length > 1;
  const units = [...new Set(items.map((i) => i.unit || "meter"))];
  const specs = Object.entries(ci.specifications || {}).filter(([, v]) => v !== "" && v != null);
  const addr = order.shipping_address;
  return (
    <div className="grid items-start gap-3 md:grid-cols-2" data-testid="special-order-info-panels">
      <Panel testId="od-item-panel" icon={Package} title={multi ? `Ringkasan pesanan · ${items.length} item` : "Rincian item custom"}>
        <div className="grid gap-2.5 text-[12px]">
          {/* UAT 23 Okt — `custom_item.description` = JUDUL OD; dulu berlabel "Deskripsi" sehingga tampak bertentangan
              dengan nama item (mis. judul "kain athena warna khusus", item "test"). */}
          <div><K>Judul pesanan</K><p className="font-semibold" data-testid="od-item-description">{order.title || ci.description || "—"}</p></div>
          {!multi && items[0]?.description && items[0].description !== (order.title || ci.description) && (
            <div><K>Item</K><p data-testid="od-item-line-desc">{items[0].description}</p></div>
          )}
          {specs.length > 0 ? (
            <div><K>Spesifikasi custom</K>
              <dl className="mt-0.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11.5px]">
                {specs.map(([k, v]) => <Fragment key={k}><dt className="capitalize text-[#6B6B73]">{k.replace(/_/g, " ")}</dt><dd className="font-medium">{String(v)}</dd></Fragment>)}
              </dl>
            </div>
          ) : !multi && <p className="text-[11px] italic text-[#9A9BA3]">Belum ada spesifikasi teknis di item ini.</p>}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {multi ? (
              <Cell label="Jumlah" testId="od-item-qty">
                {units.length === 1 ? <><b>{formatQty(items.reduce((a, i) => a + Number(i.quantity || 0), 0))}</b> {units[0]}</> : <b>{items.length} item</b>}
              </Cell>
            ) : <Cell label="Jumlah" testId="od-item-qty"><b>{formatQty(ci.quantity)}</b> {ci.unit}</Cell>}
            <Cell label="Harga target" testId="od-item-target">{multi ? "per item" : formatCurrency(ci.target_price)}</Cell>
            <Cell label="Nilai pesanan" testId="od-item-total"><b className="text-[#0058CC]">{formatCurrency(order.total_amount)}</b></Cell>
            <Cell label="Tenggat kirim" testId="od-item-eta">{order.expected_delivery ? <><Clock size={11} className="mr-1 inline" />{fmtDay(order.expected_delivery)}</> : "—"}</Cell>
          </div>
          {order.notes && <div><K>Catatan</K><p className="whitespace-pre-wrap text-[11.5px] text-[#3C3C43]">{order.notes}</p></div>}
        </div>
      </Panel>

      <div className="grid gap-3">
        <Panel testId="od-customer-panel" icon={User} title="Info pelanggan">
          <div className="grid gap-1.5 text-[12px] sm:grid-cols-2">
            <div><K>Nama</K><p className="font-semibold">{order.customer_name || "—"}</p></div>
            {order.customer_phone && <div><K>Telepon</K><p>{order.customer_phone}</p></div>}
            {order.customer_email && <div><K>Email</K><p className="truncate" title={order.customer_email}>{order.customer_email}</p></div>}
            {addr && (addr.street || addr.city) && (
              <div className="sm:col-span-2"><K>Alamat kirim</K>
                <p className="text-[11.5px]">{[addr.street, [addr.city, addr.province].filter(Boolean).join(", "), addr.postal_code].filter(Boolean).join(" · ")}</p>
              </div>
            )}
          </div>
        </Panel>

        {order.status_history?.length > 0 && (
          <Panel testId="od-status-timeline" icon={History} title={`Riwayat status · ${order.status_history.length}`}>
            {/* 23 Okt — entri PERISTIWA (status tidak berubah, mis. "Desain … ACC → proofing dibuat") dulu berjudul status
                lama ("Terkonfirmasi") sehingga tampak seperti OD dikonfirmasi berkali-kali; kini judulnya peristiwanya. */}
            <Timeline items={order.status_history.map((h, i, all) => {
              const st = STATUS_STYLE[h.status] || {};
              const prev = i > 0 ? all[i - 1].status : null;
              const event = prev === h.status && !!h.note;
              const title = event ? h.note : (h.status === "confirmed" && prev === "pending_approval" ? "Disetujui" : st.label || h.status);
              return { icon: event ? Clock : st.icon || Clock, title, note: event ? null : h.note, meta: `${fmtDate(h.timestamp)} · ${h.user_name || h.user || "sistem"}` };
            }).reverse()} />
          </Panel>
        )}
      </div>
    </div>
  );
}
