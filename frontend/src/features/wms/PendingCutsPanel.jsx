/**
 * PendingCutsPanel (WM-02) — antrean potong: reservasi panjang di roll induk yang belum
 * dipotong fisik. Konfirmasi potong (panjang aktual + waste) melahirkan roll anak tanpa tag.
 */
import { useEffect, useState } from "react";
import { Scissors, Printer } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { printCutChildLabels } from "../../utils/rollLabels";

const nf = new Intl.NumberFormat("id-ID");

export default function PendingCutsPanel({ whId }) {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastChild, setLastChild] = useState(null);

  const load = async () => {
    try {
      const r = await axios.get(`${API}/inventory/pending-cuts`);
      setItems((r.data.items || []).filter((i) => !whId || i.warehouse_id === whId));
    } catch (e) { setMsg(e?.response?.data?.detail || "Gagal memuat antrean potong"); }
  };
  useEffect(() => { load(); }, [whId]); // eslint-disable-line react-hooks/exhaustive-deps

  const cut = async (it) => {
    const f = form[it.reservation_id] || {};
    setBusy(true);
    try {
      const r = await axios.post(`${API}/inventory/rolls/${it.roll_id}/reservations/${it.reservation_id}/cut`, {
        actual_length: f.actual !== undefined && f.actual !== "" ? Number(f.actual) : null,
        waste: Number(f.waste || 0),
      });
      setMsg(`Potong tercatat — roll anak ${r.data.child.roll_no} (${r.data.child.length_remaining}). Pasang tag/label baru lalu verifikasi sebelum muat.`);
      setLastChild(r.data.child);
      await load();
      await loadKids();
    } catch (e) { setMsg(e?.response?.data?.detail || "Gagal konfirmasi potong"); } finally { setBusy(false); }
  };

  const set = (id, k, v) => setForm((s) => ({ ...s, [id]: { ...(s[id] || {}), [k]: v } }));
  const [kids, setKids] = useState([]);
  const [scan, setScan] = useState({});
  const loadKids = async () => {
    try {
      const r = await axios.get(`${API}/inventory/cut-children-unverified`);
      setKids((r.data.items || []).filter((i) => !whId || i.warehouse_id === whId));
    } catch (_) { /* panel utama sudah menampilkan galat */ }
  };
  useEffect(() => { loadKids(); }, [whId]); // eslint-disable-line react-hooks/exhaustive-deps
  const verify = async (k) => {
    setBusy(true);
    try {
      await axios.post(`${API}/inventory/rolls/${k.id}/verify-identity`, { scanned_code: scan[k.id] || "" });
      setMsg(`Identitas ${k.roll_no} terverifikasi lewat label — siap dimuat.`);
      await loadKids();
    } catch (e) { setMsg(e?.response?.data?.detail || "Verifikasi label gagal"); } finally { setBusy(false); }
  };

  return (
    <section className="section-card" data-testid="pending-cuts-panel">
      <div className="section-head"><h2 className="text-[13px] font-bold flex items-center gap-1.5">
        <Scissors size={15} className="text-[#0058CC]" /> Antrean Potong Roll ({items.length})</h2></div>
      <div className="section-body space-y-2">
        {msg && <div data-testid="pending-cuts-msg" className="flex flex-wrap items-center gap-2 rounded-lg bg-[#F7FAFF] px-3 py-2 text-[12px] font-semibold">
          <span className="flex-1">{msg}</span>
          {lastChild && (
            <button data-testid="cut-print-label-btn" onClick={() => printCutChildLabels([lastChild])}
              className="inline-flex items-center gap-1 rounded-lg bg-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-white">
              <Printer size={13} /> Cetak Label {lastChild.roll_no} (QR + Barcode)</button>)}
        </div>}
        {items.length === 0 && <p className="text-[12px] text-[#8E8E93]" data-testid="pending-cuts-empty">Tidak ada reservasi yang menunggu dipotong.</p>}
        {items.map((it) => (
          <div key={it.reservation_id} data-testid={`pending-cut-${it.reservation_id}`}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-[#DCE6F5] p-2 text-[12px]">
            <span className="flex-1 font-semibold">{it.roll_no} · pesan {nf.format(it.qty)} {it.unit} dari {nf.format(it.parent_length)} {it.unit}</span>
            <input data-testid={`pending-cut-actual-${it.reservation_id}`} className="field w-24" type="number" step="0.01"
              placeholder={`aktual ${it.qty}`} value={(form[it.reservation_id] || {}).actual ?? ""}
              onChange={(e) => set(it.reservation_id, "actual", e.target.value)} />
            <input data-testid={`pending-cut-waste-${it.reservation_id}`} className="field w-20" type="number" step="0.01"
              placeholder="waste" value={(form[it.reservation_id] || {}).waste ?? ""}
              onChange={(e) => set(it.reservation_id, "waste", e.target.value)} />
            <button data-testid={`pending-cut-confirm-${it.reservation_id}`} disabled={busy} onClick={() => cut(it)}
              className="rounded-lg bg-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
              Konfirmasi Potong
            </button>
          </div>
        ))}
        <div className="flex items-center gap-2 pt-3">
          <h3 className="flex-1 text-[12px] font-bold" data-testid="unverified-kids-title">
            Roll anak menunggu verifikasi identitas ({kids.length})</h3>
          {kids.length > 1 && (
            <button data-testid="label-print-all-btn" onClick={() => printCutChildLabels(kids)}
              className="inline-flex items-center gap-1 rounded-lg border border-[#DCE6F5] px-2.5 py-1 text-[11px] font-semibold">
              <Printer size={12} /> Cetak semua label</button>)}
        </div>
        <p className="text-[11px] text-[#6B7280]">Gudang dengan RFID: cetak tag & selesaikan sesi verifikasi. Tanpa RFID: pindai label/QR roll (berisi nomor roll).</p>
        {kids.map((k) => (
          <div key={k.id} data-testid={`unverified-kid-${k.id}`}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-[#F5D0A9] p-2 text-[12px]">
            <span className="flex-1 font-semibold">{k.roll_no} · {nf.format(k.length_remaining)} {k.unit}
              {k.product_name && <span className="ml-1 font-normal text-[#6B7280]">· {k.product_name} · dari {k.parent_roll_no || "-"}</span>}</span>
            <button data-testid={`label-print-btn-${k.id}`} onClick={() => printCutChildLabels([k])}
              className="inline-flex items-center gap-1 rounded-lg border border-[#DCE6F5] px-2.5 py-1.5 text-[11px] font-semibold">
              <Printer size={12} /> Cetak Label</button>
            <input data-testid={`label-scan-input-${k.id}`} className="field w-44" placeholder="scan label / ketik no. roll"
              value={scan[k.id] || ""} onChange={(e) => setScan((s) => ({ ...s, [k.id]: e.target.value }))}
              onKeyDown={(e) => { if (e.key === "Enter") verify(k); }} />
            <button data-testid={`label-verify-btn-${k.id}`} disabled={busy || !scan[k.id]} onClick={() => verify(k)}
              className="rounded-lg bg-[#15803D] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
              Verifikasi Label</button>
          </div>
        ))}
      </div>
    </section>
  );
}
