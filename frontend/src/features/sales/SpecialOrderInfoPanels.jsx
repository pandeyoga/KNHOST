/** Rincian OD — panel info: item custom (kiri), pelanggan + riwayat status (kanan). Gaya seragam dgn panel Fase 2–4. */
import { Fragment } from "react";
import { Clock, Package, User, History } from "lucide-react";
import { STATUS_STYLE, fmtNum, fmtDate, fmtDay } from "./SpecialOrderShared";
import { K, Panel, Cell, Timeline } from "../../components/DetailParts";


export function SpecialOrderInfoPanels({ order }) {
  const ci = order.custom_item || {};
  const specs = Object.entries(ci.specifications || {}).filter(([, v]) => v !== "" && v != null);
  const addr = order.shipping_address;
  return (
    <div className="grid items-start gap-3 md:grid-cols-2" data-testid="special-order-info-panels">
      <Panel testId="od-item-panel" icon={Package} title="Rincian item custom">
        <div className="grid gap-2.5 text-[12px]">
          <div><K>Deskripsi</K><p className="font-semibold" data-testid="od-item-description">{ci.description || order.title || "—"}</p></div>
          {specs.length > 0 ? (
            <div><K>Spesifikasi custom</K>
              <dl className="mt-0.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11.5px]">
                {specs.map(([k, v]) => <Fragment key={k}><dt className="capitalize text-[#6B6B73]">{k.replace(/_/g, " ")}</dt><dd className="font-medium">{String(v)}</dd></Fragment>)}
              </dl>
            </div>
          ) : <p className="text-[11px] italic text-[#9A9BA3]">Belum ada spesifikasi custom di item — lihat panel Spesifikasi target di atas.</p>}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Cell label="Jumlah" testId="od-item-qty"><b>{fmtNum(ci.quantity, 2)}</b> {ci.unit}</Cell>
            <Cell label="Harga target" testId="od-item-target">Rp {fmtNum(ci.target_price, 0)}</Cell>
            <Cell label="Nilai pesanan" testId="od-item-total"><b className="text-[#0058CC]">Rp {fmtNum(order.total_amount, 0)}</b></Cell>
            <Cell label="Perkiraan kirim" testId="od-item-eta"><Clock size={11} className="mr-1 inline" />{fmtDay(order.expected_delivery)}</Cell>
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
            <Timeline items={order.status_history.slice().reverse().map((h) => {
              const st = STATUS_STYLE[h.status] || {};
              return { icon: st.icon || Clock, title: st.label || h.status, note: h.note, meta: `${fmtDate(h.timestamp)} · ${h.user || "sistem"}` };
            })} />
          </Panel>
        )}
      </div>
    </div>
  );
}
