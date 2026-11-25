import { useEffect, useState } from "react";
import { PackageCheck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import { apiErrorText } from "../../utils/apiError";
import { entityShortById } from "../../utils/entityLabel";
import { useEntityScope } from "../../context/EntityScopeContext";

/**
 * Baris barang untuk pratinjau (R6): `quantity` + `unit` = satuan jual pesanan, sama dengan `_lines_of` di server
 * dan Faktur Komersial. `order.order_lines` (dari baris antrean) dipakai bila ada; selain itu dari `order.items`
 * (gudang unik dari alokasi + gudang barang, digabung ", ").
 */
export function orderLinesOf(order) {
  if (Array.isArray(order?.order_lines)) return order.order_lines;
  return (order?.items || []).map((it) => {
    const names = [];
    for (const n of [...(it.allocations || []).map((a) => a?.warehouse_name), it.warehouse_name]) {
      if (n && !names.includes(n)) names.push(n);
    }
    return { product_name: it.product_name || "", sku: it.sku || "", quantity: Number(it.quantity) || 0,
      unit: it.unit || "", warehouse: names.join(", ") };
  });
}

const uniqueWarehouses = (lines) => {
  const out = [];
  for (const l of lines) for (const n of String(l.warehouse || "").split(", ")) if (n && !out.includes(n)) out.push(n);
  return out;
};

/**
 * ReleaseToWarehouseDialog — pratinjau + konfirmasi LEPAS / TERUSKAN KE GUDANG (Meja gelombang 1, Task 10).
 * order: { id, number, title, entity_id, order_lines?, items? }. Pesanan tanpa baris barang (mis. dari Pelacak SO)
 * dimuat dulu lewat `GET /sales-orders/{id}`. Galat `run` tampil di dalam pop-up (`<testId>-error`).
 */
export default function ReleaseToWarehouseDialog({ order, mode = "release", run, onClose, onDone, testId = "release-confirm" }) {
  const { entities } = useEntityScope();
  const forward = mode === "forward";
  const needsLoad = !forward && !!order?.id && order?.order_lines == null && order?.items == null;
  const [loaded, setLoaded] = useState(null);
  const [loading, setLoading] = useState(needsLoad);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!needsLoad) return undefined;
    let aktif = true;
    axios.get(`${API}/sales-orders/${order.id}`)
      .then((r) => { if (aktif) setLoaded(r?.data || {}); })
      .catch((e) => { if (aktif) setErr(apiErrorText(e, "Gagal memuat barang pesanan.")); })
      .finally(() => { if (aktif) setLoading(false); });
    return () => { aktif = false; };
  }, [needsLoad, order?.id]);

  const src = loaded ? { ...order, ...loaded, title: order.title || loaded.customer_name } : order;
  const lines = orderLinesOf(src);
  const warehouses = uniqueWarehouses(lines);
  const entityId = order?.entity_id || loaded?.entity_id || "";
  const pt = entityId ? entityShortById(entities, entityId, "—") : "—";
  const number = order?.number || loaded?.number || "";

  const kirim = async () => {
    if (busy || loading) return;
    setBusy(true); setErr("");
    try { onDone?.(await run()); }
    catch (e) { setErr(apiErrorText(e, forward ? "Gagal meneruskan ke gudang." : "Gagal melepas pesanan ke gudang.")); }
    finally { setBusy(false); }
  };

  const label = forward ? "Teruskan ke gudang" : "Lepas ke gudang";
  return (
    <FormModal open onClose={onClose} size="md" icon={PackageCheck} title={`${label}?`}
      subtitle="Periksa pesanan, PT, gudang, dan barangnya sebelum dilanjutkan." testId={testId}
      busy={busy} error={err} submitLabel={busy ? "Memproses…" : label} submitDisabled={loading}
      submitTestId={`${testId}-submit`} onSubmit={kirim}>
      <div className="space-y-2" data-testid={`${testId}-preview`}>
        <dl className="rounded-md border border-kn-border px-3 py-2 text-fs-13 space-y-1">
          <div className="flex justify-between gap-3">
            <dt className="text-kn-text-2">Pesanan</dt>
            <dd className="text-right font-semibold" data-testid={`${testId}-order`}>
              {[number, order?.title].filter(Boolean).join(" · ") || "—"}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-kn-text-2">PT</dt>
            <dd className="text-right" data-testid={`${testId}-pt`}>{pt}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-kn-text-2">Gudang</dt>
            <dd className="text-right" data-testid={`${testId}-warehouse`}>{loading ? "Memuat…" : (warehouses.join(", ") || "—")}</dd>
          </div>
        </dl>
        {loading ? (
          <p className="text-fs-13 text-kn-text-2" data-testid={`${testId}-loading`}>Memuat barang pesanan…</p>
        ) : lines.length === 0 ? (
          <p className="text-fs-13 text-kn-text-2" data-testid={`${testId}-no-lines`}>Belum ada baris barang.</p>
        ) : (
          <ul className="divide-y divide-kn-border rounded-md border border-kn-border text-fs-13">
            {lines.map((l, i) => (
              <li key={i} data-testid={`${testId}-line-${i}`} className="flex justify-between gap-3 px-3 py-1.5">
                <span className="min-w-0">
                  <span className="block truncate">{l.product_name || "—"}</span>
                  {l.sku ? <span className="block text-fs-12 text-kn-text-2">{l.sku}</span> : null}
                </span>
                <span className="whitespace-nowrap text-right tabular-nums">
                  {Number(l.quantity || 0).toLocaleString("id-ID")} {l.unit}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </FormModal>
  );
}
