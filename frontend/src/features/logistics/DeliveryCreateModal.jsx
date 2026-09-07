import { useEffect, useState } from "react";
import KNDatePicker from "../../components/KNDatePicker";
import { X } from "lucide-react";
import { useEscapeClose } from "../../utils/escapeLayers";
import KNSelect from "../../components/KNSelect";
import { createDelivery, listDrivers, unassignedShipments } from "./logisticsApi";

// FB-02 — buat pengiriman dari Surat Jalan yang belum diangkut (satu pesanan per pengiriman).
export default function DeliveryCreateModal({ params, onClose, onCreated, preselectShipmentId = "" }) {
  const [ships, setShips] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [picked, setPicked] = useState([]);
  const [mode, setMode] = useState("expedition");
  const [f, setF] = useState({ courier_name: "", service_level: "", tracking_no: "", vehicle_plate: "", driver_name: "", driver_user_id: "", eta: "", destination: "", receiver_phone: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    unassignedShipments(params).then((rows) => {
      setShips(rows);
      if (preselectShipmentId && rows.some((r) => r.id === preselectShipmentId)) setPicked([preselectShipmentId]);
    }).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat Surat Jalan."));
    listDrivers(params).then(setDrivers).catch(() => setDrivers([]));
  }, []); // eslint-disable-line
  useEscapeClose(true, onClose, busy);
  function pickDriver(uid) {
    const u = drivers.find((x) => x.id === uid);
    setF({ ...f, driver_user_id: uid, driver_name: u ? u.name : f.driver_name });
  }

  const pickedOrder = ships.find((s) => picked.includes(s.id))?.order_id;
  function toggle(s) {
    if (picked.includes(s.id)) return setPicked(picked.filter((x) => x !== s.id));
    if (pickedOrder && s.order_id !== pickedOrder) { setErr("Satu pengiriman hanya untuk Surat Jalan dari SATU pesanan."); return; }
    setErr(""); setPicked([...picked, s.id]);
    if (!f.destination && s.shipping_address) setF({ ...f, destination: s.shipping_address });
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function save() {
    if (!picked.length) { setErr("Pilih minimal 1 Surat Jalan."); return; }
    setBusy(true); setErr("");
    try { const d = await createDelivery({ shipment_ids: picked, mode, ...f }); onCreated(d.id); }
    catch (e) { setErr(e.response?.data?.detail || "Gagal membuat pengiriman."); }
    finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" data-testid="logistics-create-modal" onClick={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
      <div className="modal-card !max-w-[680px]">
        <div className="flex items-center justify-between"><p className="modal-title !mb-0">Buat Pengiriman</p><button className="icon-button" onClick={onClose}><X size={16} /></button></div>
        {err && <div className="notice-bar danger !my-2 !py-1.5" data-testid="logistics-create-error"><span className="text-[11.5px]">{err}</span></div>}
        <div className="grid gap-1 mt-2">
          <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Surat Jalan yang diangkut *</label>
          {ships.length === 0 ? <p className="text-[11.5px] text-[#9A9BA3]" data-testid="logistics-no-shipments">Tidak ada Surat Jalan yang menunggu diangkut (semua sudah punya pengiriman).</p> : (
            <div className="max-h-[200px] overflow-auto rounded-lg border border-[#E1E4EA] divide-y divide-[#F0F1F3]">
              {ships.map((s) => (
                <label key={s.id} className={`flex items-center gap-2 px-2.5 py-1.5 text-[11.5px] cursor-pointer hover:bg-[#F7F9FC] ${pickedOrder && s.order_id !== pickedOrder ? "opacity-50" : ""}`} data-testid={`logistics-ship-${s.id}`}>
                  <input type="checkbox" checked={picked.includes(s.id)} onChange={() => toggle(s)} className="h-4 w-4 accent-[#0058CC]" />
                  <span className="font-mono font-bold text-[#0058CC]">{s.shipment_no}</span>
                  <span className="font-semibold">{s.order_number}</span>
                  <span className="text-[#6B6B73] truncate">{s.customer_name} · {s.product_name} · {s.qty} {s.unit}</span>
                </label>
              ))}
            </div>
          )}
        </div>
        <div className="grid gap-2.5 sm:grid-cols-2 mt-3">
          <div className="grid gap-1"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">Moda</label>
            <KNSelect data-testid="logistics-mode" value={mode} onValueChange={setMode} className="field"
              options={[{ value: "expedition", label: "Ekspedisi (pihak ketiga)" }, { value: "own_fleet", label: "Armada sendiri" }]} /></div>
          <div className="grid gap-1"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">ETA (perkiraan tiba)</label>
            <KNDatePicker data-testid="logistics-eta" value={f.eta} onChange={(v) => setF((x) => ({ ...x, eta: v }))} placeholder="Pilih tanggal ETA" /></div>
          {mode === "expedition" ? (<>
            <div className="grid gap-1"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">Ekspedisi</label>
              <input data-testid="logistics-courier" className="form-input" placeholder="mis. JNE, SiCepat, Indah Cargo" value={f.courier_name} onChange={set("courier_name")} /></div>
            <div className="grid gap-1"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">No. Resi</label>
              <input data-testid="logistics-tracking" className="form-input" placeholder="boleh diisi nanti, wajib sebelum berangkat" value={f.tracking_no} onChange={set("tracking_no")} /></div>
          </>) : (<>
            <div className="grid gap-1"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">Plat kendaraan</label>
              <input data-testid="logistics-plate" className="form-input" placeholder="B 1234 XYZ" value={f.vehicle_plate} onChange={set("vehicle_plate")} /></div>
            <div className="grid gap-1"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">Sopir</label>
              {drivers.length ? (
                <KNSelect data-testid="logistics-driver-select" value={f.driver_user_id} onValueChange={pickDriver} className="field"
                  options={[{ value: "", label: "— pilih akun sopir —" }, ...drivers.map((u) => ({ value: u.id, label: u.name }))]} />
              ) : null}
              <input data-testid="logistics-driver" className="form-input" placeholder="Nama sopir (bila tidak punya akun)" value={f.driver_name} onChange={set("driver_name")} /></div>
          </>)}
          <div className="grid gap-1 sm:col-span-2"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">Alamat tujuan</label>
            <input data-testid="logistics-destination" className="form-input" value={f.destination} onChange={set("destination")} /></div>
          <div className="grid gap-1 sm:col-span-2"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">Telepon penerima</label>
            <input data-testid="logistics-receiver-phone" type="tel" className="form-input" placeholder="kosong → otomatis dari alamat kirim / kontak pelanggan" value={f.receiver_phone} onChange={set("receiver_phone")} /></div>
          <div className="grid gap-1 sm:col-span-2"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">Catatan</label>
            <input data-testid="logistics-notes" className="form-input" value={f.notes} onChange={set("notes")} /></div>
        </div>
        <div className="modal-actions mt-3">
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Batal</button>
          <button data-testid="logistics-create-submit" className="btn-primary" onClick={save} disabled={busy || !ships.length}>{busy ? "Menyimpan…" : "Buat Pengiriman"}</button>
        </div>
      </div>
    </div>
  );
}
