/** Tahap PENGEMBALIAN BARANG (permintaan pemilik 23 Okt) — antara ACC dan QC: BAGAIMANA barang kembali (dijemput armada
 *  KN / dikirim pelanggan via ekspedisi + resi / diantar pelanggan), KAPAN dikirim/dijemput, dan BERAPA roll yang
 *  sudah DITERIMA gudang (dari scan terima per roll di tab Logistik & perjalanan). Dulu tersebar di tiga panel
 *  (tonggak manual "SJ Kirim Toko", scan, biaya logistik) tanpa satu tempat yang menjawab "barangnya sudah di mana?". */
import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Loader2, PackageCheck, Truck } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { Panel } from "../../components/DetailParts";
import KNSelect from "../../components/KNSelect";
import KNDateTimePicker from "../../components/KNDateTimePicker";
import { apiErrorText } from "../../utils/apiError";
import { fmtDateTime } from "./ReturnShared";

export const SHIPMENT_METHODS = [
  { value: "pickup_fleet", label: "Dijemput armada KN" },
  { value: "customer_courier", label: "Dikirim pelanggan via ekspedisi" },
  { value: "customer_dropoff", label: "Diantar sendiri oleh pelanggan" },
];
const STAGE = { received: "Diterima", arrived: "Tiba di gudang tujuan", in_transit: "Dalam perjalanan antar-gudang" };

/** Ringkasan penerimaan: roll klaim, yang sudah di gudang, dan barang tanpa roll. */
export function receiptOf(ret) {
  const locs = ret.roll_locations || {};
  const rolls = (ret.items || []).flatMap((it) => (it.roll_ids || []).map((rid) => ({ rid, no: (it.roll_nos || {})[rid] || rid, loc: locs[rid] })));
  const received = rolls.filter((r) => r.loc && r.loc.stage !== "in_transit").length;
  const rollless = (ret.items || []).some((it) => !(it.roll_ids || []).length);
  const complete = rolls.length ? received === rolls.length && (!rollless || !!ret.goods_arrived_at) : !!ret.goods_arrived_at;
  return { rolls, received, rollless, complete };
}

// Di LUAR komponen panel: komponen yang didefinisikan di dalam render dibuat ulang tiap ketikan → isian dipasang
// ulang & fokus hilang setiap huruf.
function Step({ done, title, children, testId }) {
  return (
    <div className="flex gap-2.5" data-testid={testId}>
      {done ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-[#15803D]" /> : <Circle size={16} className="mt-0.5 shrink-0 text-[#C7C7CC]" />}
      <div className="min-w-0 flex-1">
        <p className={`text-[12px] ${done ? "font-semibold text-[#1C1C1E]" : "text-[#3C3C43]"}`}>{title}</p>
        {children}
      </div>
    </div>
  );
}

export default function ReturnShipmentPanel({ ret, canEdit, onChanged }) {
  const sh = ret.return_shipment || {};
  const [f, setF] = useState({ method: sh.method || "", courier: sh.courier || "", tracking_no: sh.tracking_no || "",
    driver: sh.driver || "", vehicle: sh.vehicle || "", scheduled_at: sh.scheduled_at || "", note: sh.note || "" });
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    const s = ret.return_shipment || {};
    setF({ method: s.method || "", courier: s.courier || "", tracking_no: s.tracking_no || "", driver: s.driver || "",
      vehicle: s.vehicle || "", scheduled_at: s.scheduled_at || "", note: s.note || "" });
  }, [ret.id, ret.return_shipment]);
  const { rolls, received, rollless, complete } = receiptOf(ret);
  const open = ["approved", "inspecting"].includes(ret.status);
  const editable = canEdit && open && !complete;
  const shipped = !!ret.shipped_to_store_at;
  const set = (patch) => setF((x) => ({ ...x, ...patch }));

  async function save(markShipped) {
    setBusy(markShipped ? "ship" : "plan"); setErr("");
    try {
      await axios.put(`${API}/sales-returns/${ret.id}/return-shipment`, { ...f, shipped: markShipped });
      onChanged?.();
    } catch (e) { setErr(apiErrorText(e, "Gagal menyimpan pengembalian barang.")); }
    finally { setBusy(""); }
  }
  async function markArrived() {
    setBusy("arrive"); setErr("");
    try { await axios.post(`${API}/sales-returns/${ret.id}/milestone`, { milestone: "goods_arrived" }); onChanged?.(); }
    catch (e) { setErr(apiErrorText(e, "Gagal menandai barang sampai.")); }
    finally { setBusy(""); }
  }

  return (
    <Panel icon={Truck} title="Pengembalian barang" testId="return-shipment-panel">
      <div className="space-y-3">
        <Step done={shipped} testId="return-shipment-step-ship"
          title={shipped ? `Barang dikirim/dijemput · ${fmtDateTime(ret.shipped_to_store_at)}` : "Barang belum dikirim/dijemput dari pelanggan"}>
          {sh.method && (
            <p className="mt-0.5 text-[11.5px] text-[#6B6B73]" data-testid="return-shipment-info">
              {sh.method_label}
              {sh.courier ? ` · ${sh.courier}` : ""}{sh.tracking_no ? ` · resi ${sh.tracking_no}` : ""}
              {sh.driver ? ` · sopir ${sh.driver}` : ""}{sh.vehicle ? ` · ${sh.vehicle}` : ""}
              {!sh.shipped && sh.scheduled_at ? ` · dijadwalkan ${fmtDateTime(sh.scheduled_at)}` : ""}
              {sh.note ? ` · ${sh.note}` : ""}
            </p>
          )}
          {editable && (
            <div className="mt-2 space-y-2 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-2.5" data-testid="return-shipment-form">
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="block text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Cara barang kembali *
                  <KNSelect className="form-select mt-1" value={f.method} onValueChange={(v) => set({ method: v })} searchable={false}
                    placeholder="Pilih cara kembali" options={SHIPMENT_METHODS} data-testid="return-shipment-method" />
                </label>
                {f.method === "customer_courier" && <>
                  <label className="block text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Ekspedisi *
                    <input className="form-input mt-1" value={f.courier} onChange={(e) => set({ courier: e.target.value })}
                      placeholder="mis. JNE, J&T, Lalamove" data-testid="return-shipment-courier" />
                  </label>
                  <label className="block text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">No. resi *
                    <input className="form-input mt-1" value={f.tracking_no} onChange={(e) => set({ tracking_no: e.target.value })}
                      data-testid="return-shipment-tracking" />
                  </label>
                </>}
                {f.method === "pickup_fleet" && <>
                  <label className="block text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Sopir
                    <input className="form-input mt-1" value={f.driver} onChange={(e) => set({ driver: e.target.value })} data-testid="return-shipment-driver" />
                  </label>
                  <label className="block text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Kendaraan / plat
                    <input className="form-input mt-1" value={f.vehicle} onChange={(e) => set({ vehicle: e.target.value })} data-testid="return-shipment-vehicle" />
                  </label>
                  <label className="block text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73]">Jadwal jemput
                    <KNDateTimePicker className="mt-1 normal-case tracking-normal font-normal" value={f.scheduled_at} onChange={(v) => set({ scheduled_at: v })}
                      data-testid="return-shipment-schedule" />
                  </label>
                </>}
                <label className="block text-[10.5px] font-semibold uppercase tracking-wide text-[#6B6B73] sm:col-span-2">Catatan
                  <input className="form-input mt-1" value={f.note} onChange={(e) => set({ note: e.target.value })} data-testid="return-shipment-note" />
                </label>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                {!shipped && (
                  <button type="button" className="secondary-button" disabled={!!busy || !f.method} onClick={() => save(false)} data-testid="return-shipment-plan">
                    {busy === "plan" && <Loader2 size={13} className="spin" />} Simpan rencana
                  </button>
                )}
                <button type="button" className="primary-button" disabled={!!busy || !f.method} onClick={() => save(true)} data-testid="return-shipment-ship">
                  {busy === "ship" ? <Loader2 size={13} className="spin" /> : <Truck size={13} />} {shipped ? "Perbarui data kirim" : "Barang sudah dikirim/dijemput"}
                </button>
              </div>
            </div>
          )}
        </Step>

        <Step done={complete} testId="return-shipment-step-receive"
          title={rolls.length ? `Diterima gudang: ${received}/${rolls.length} roll` : (ret.goods_arrived_at ? `Barang sampai · ${fmtDateTime(ret.goods_arrived_at)}` : "Barang belum sampai di gudang")}>
          {rolls.length > 0 && (
            <ul className="mt-1 flex flex-wrap gap-1.5" data-testid="return-shipment-rolls">
              {rolls.map((r) => (
                <li key={r.rid} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10.5px] ${
                  r.loc ? "border-[#BFE3CC] bg-[#EAF7EF] text-[#1B7F4B]" : "border-[#E5E5EA] bg-white text-[#6B6B73]"}`}>
                  <span className="font-mono font-semibold">{r.no}</span>
                  {r.loc ? `· ${STAGE[r.loc.stage] || r.loc.stage}${r.loc.warehouse_name ? ` @ ${r.loc.warehouse_name}` : ""}` : "· belum discan"}
                </li>
              ))}
            </ul>
          )}
          {open && !complete && (
            <p className="mt-1 text-[11px] text-[#6B6B73]">
              {rolls.length ? "Gudang menscan TERIMA tiap roll saat barang tiba (tab Logistik & perjalanan › Scan). QC per roll terbuka begitu roll itu diterima." : ""}
              {rollless ? " Barang tanpa roll: tandai sampai sesudah dicek gudang." : ""}
            </p>
          )}
          {open && rollless && !ret.goods_arrived_at && canEdit && shipped && (
            <button type="button" className="secondary-button mt-1.5" onClick={markArrived} disabled={!!busy} data-testid="return-shipment-arrived">
              {busy === "arrive" ? <Loader2 size={13} className="spin" /> : <PackageCheck size={13} />} Tandai barang sampai
            </button>
          )}
        </Step>
        {err && <p className="text-[11.5px] font-semibold text-[#A8221A]" data-testid="return-shipment-error">{err}</p>}
      </div>
    </Panel>
  );
}
