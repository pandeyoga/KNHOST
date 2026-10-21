/** Sub-fase 1.11 — Create return form. */
import { useState, useEffect, useRef } from "react";
import axios, { API } from "../../services/apiClient";
import { AlertCircle, ArrowLeft, Camera, CalendarClock, Loader2, Paperclip, RotateCcw, ShieldCheck, Trash2, X } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import { getStage, stageMeta } from "../../utils/soStatus";


export default function CreateReturnForm({ orders = [], token, onCreated, onCancel,
                                           variant = "page", initialOrderId = "" }) {
  // FASE P4 — `variant="modal"`: lepas chrome halaman (tombol kembali + judul besar)
  // karena FormModal sudah menyediakannya; tanpa ini pengguna melihat DUA judul.
  const isModal = variant === "modal";
  // FASE U — satuan baris retur dari MASTER SATUAN. Pesanan ber-satuan `panel` dulu
  // tidak bisa diretur dalam satuan yang sama (pilihannya hanya meter/kg/roll/pcs),
  // jadi petugas memilih satuan yang salah dan angka retur tidak bisa dicocokkan
  // dengan pesanan asalnya.
  // L08 LN-080 — baris retur diisi dari barang TERKIRIM (Surat Jalan); satuan ikut satuan kirim.
  const [orderId, setOrderId]       = useState("");
  const [returnType, setReturnType] = useState("retur");
  const [items, setItems]           = useState([]);
  const [shipped, setShipped]       = useState(null);
  const [notes, setNotes]           = useState("");
  const [submitNow, setSubmitNow]   = useState(true);
  const [cond, setCond]             = useState({ hangtag_missing: false, cut_by_customer: false, replacement_proof: false });
  const [saving, setSaving]         = useState(false);
  const [error, setError]           = useState(null);
  const [eligibility, setEligibility] = useState(null);
  const [checking, setChecking]     = useState(false);
  // L08 LN-080-T03 — bukti foto saat membuat retur; kewajiban per tahap dari kebijakan.
  const [files, setFiles]           = useState([]);
  const [evPolicy, setEvPolicy]     = useState(null);
  const [reasons, setReasons]       = useState([]);
  const [complaintCode, setComplaintCode] = useState("");

  // FE-09 — pemilih SO dicari & dipaginasi SERVER (`/sales-returns/eligible-orders`): hanya SO dalam scope yang
  // masih punya barang terkirim belum diklaim. Tidak lagi bergantung pada 200 SO terbaru yang diunduh peramban.
  // `orders` (opsional) hanya benih label, mis. SO yang dibawa dari layar lain.
  const [orderQ, setOrderQ]         = useState("");
  const [orderOpts, setOrderOpts]   = useState([]);
  const [orderMeta, setOrderMeta]   = useState({ total: 0, page: 1, has_more: false, loading: false, error: "" });
  const knownRef = useRef(Object.fromEntries((orders || []).map((o) => [o.id, o])));
  const searchSeq = useRef(0);
  async function searchOrders(q, page = 1) {
    const seq = ++searchSeq.current;
    setOrderMeta((m) => ({ ...m, loading: true, error: "" }));
    try {
      const r = await axios.get(`${API}/sales-returns/eligible-orders`, { params: { q, page, page_size: 20 } });
      if (seq !== searchSeq.current) return;   // hasil pencarian lama — abaikan
      const rows = r.data?.items || [];
      rows.forEach((o) => { knownRef.current[o.id] = o; });
      setOrderOpts((prev) => (page === 1 ? rows : [...prev, ...rows]));
      setOrderMeta({ total: r.data?.total || 0, page, has_more: !!r.data?.has_more, loading: false, error: "" });
    } catch (e) {
      if (seq !== searchSeq.current) return;
      setOrderMeta((m) => ({ ...m, loading: false, error: e.response?.data?.detail || "Gagal mencari pesanan." }));
    }
  }
  useEffect(() => {
    const t = setTimeout(() => searchOrders(orderQ.trim(), 1), 300);
    return () => clearTimeout(t);
  }, [orderQ]); // eslint-disable-line react-hooks/exhaustive-deps

  // FE-08 — hanya respons untuk SO yang MASIH dipilih boleh mengisi form (A lambat lalu B cepat tetap B).
  const activeOrderRef = useRef("");
  useEffect(() => {
    if (initialOrderId) handleOrderChange(initialOrderId);
    return () => { activeOrderRef.current = "__closed__"; };   // form ditutup saat memuat → respons diabaikan
  }, []); // eslint-disable-line
  useEffect(() => {
    axios.get(`${API}/sales-returns/meta/evidence-policy`).then((r) => setEvPolicy(r.data?.required || {})).catch(() => {});
    axios.get(`${API}/sales-returns/meta/complaint-reasons`).then((r) => setReasons(r.data?.items || [])).catch(() => {});
  }, []);
  const needsPhotoToSubmit = !!evPolicy?.submit && submitNow && files.length === 0;

  // R0 — cek kelayakan & deadline retur tiap kali order/tipe berubah.
  useEffect(() => {
    if (!orderId) { setEligibility(null); return; }
    let cancelled = false;
    (async () => {
      setChecking(true);
      try {
        const res = await axios.get(`${API}/sales-return-policies/eligibility`, {
          params: { order_id: orderId, return_type: returnType, ...cond },
        });
        if (!cancelled) setEligibility(res.data);
      } catch {
        if (!cancelled) setEligibility(null);
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => { cancelled = true; };
  }, [orderId, returnType, cond]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleOrderChange(id) {
    activeOrderRef.current = id;
    // Pilihan roll/qty/bukti milik SO sebelumnya tidak boleh terbawa ke SO baru.
    setOrderId(id); setShipped(null); setItems([]); setFiles([]); setError(null);
    if (!id) return;
    axios.get(`${API}/sales-returns/returnable`, { params: { order_id: id } }).then((r) => {
      if (activeOrderRef.current !== id) return;   // respons SO lama datang terlambat — abaikan
      setShipped(r.data);
      setItems(r.data.products.filter((p) => p.remaining > 0).map((p) => ({
        product_id: p.product_id, product_name: p.product_name, sku: p.sku, color: p.color,
        quantity_returned: "", unit: p.unit, reason: "", condition: "ok", roll_ids: [], max: p.remaining,
      })));
    }).catch((e) => { if (activeOrderRef.current === id) setError(e.response?.data?.detail || "Gagal memuat barang terkirim."); });
  }

  const rollsOf = (pid) => (shipped?.rolls || []).filter((r) => r.product_id === pid && r.remaining > 0);
  function toggleRoll(i, roll) {
    setItems((prev) => prev.map((it, idx) => {
      if (idx !== i) return it;
      const ids = it.roll_ids.includes(roll.roll_id) ? it.roll_ids.filter((x) => x !== roll.roll_id) : [...it.roll_ids, roll.roll_id];
      const sum = rollsOf(it.product_id).filter((r) => ids.includes(r.roll_id)).reduce((a, r) => a + r.remaining, 0);
      return { ...it, roll_ids: ids, quantity_returned: ids.length ? String(Math.round(sum * 100) / 100) : it.quantity_returned };
    }));
  }

  const updateItem = (i, f, v) => setItems(prev => prev.map((it, idx) => idx === i ? { ...it, [f]: v } : it));
  const removeItem = (i) => setItems(prev => prev.filter((_, idx) => idx !== i));

  async function handleSubmit(e) {
    e.preventDefault();
    if (!orderId) return setError("Pilih pesanan terlebih dahulu");
    const validItems = items.filter(it => it.product_id && parseFloat(it.quantity_returned) > 0);
    if (!validItems.length) return setError("Minimal 1 item dengan kuantitas > 0");
    if (needsPhotoToSubmit) return setError("Kebijakan mewajibkan bukti foto sebelum retur diajukan. Lampirkan foto atau simpan sebagai draf.");
    setSaving(true); setError(null);
    try {
      // Dengan foto: simpan draf → unggah foto → ajukan (bukti sudah ada saat tahap 'ajukan').
      const res = await axios.post(`${API}/sales-returns`, {
        order_id: orderId, return_type: returnType,
        items: validItems.map(({ max, sku, color, ...it }) => ({ ...it, quantity_returned: parseFloat(it.quantity_returned) })),
        notes, submit_now: submitNow && files.length === 0, ...cond,
        ...(complaintCode ? { complaint_code: complaintCode } : {}),
      }, { headers: { Authorization: `Bearer ${token}` } });
      let doc = res.data;
      if (files.length) {
        for (const f of files) {
          const fd = new FormData(); fd.append("file", f);
          await axios.post(`${API}/sales-returns/${doc.id}/attachments`, fd, { headers: { "Content-Type": "multipart/form-data" } });
        }
        doc = submitNow ? (await axios.post(`${API}/sales-returns/${doc.id}/submit`, {})).data
                        : (await axios.get(`${API}/sales-returns/${doc.id}`)).data;
      }
      onCreated(doc);
    } catch (err) {
      setError("Gagal membuat return: " + (err.response?.data?.detail || err.message));
    } finally { setSaving(false); }
  }

  return (
    <div data-testid="create-return-form" className={isModal ? "" : "view-container"}>
      {!isModal && (
        <button className="back-button" onClick={onCancel}><ArrowLeft size={14} /> Batal</button>
      )}

      {!isModal && (
        <div className="view-header">
          <div>
            <h1 className="view-title">Buat Return Baru</h1>
            <p className="view-subtitle">Retur barang, Barang Sisa (BS), penggantian, komplain & garansi (purna jual) dari pelanggan</p>
          </div>
        </div>
      )}

      {error && (
        <div className="notice-bar danger">
          <AlertCircle size={14} /> {error}
          <button onClick={() => setError(null)}><X size={12} /></button>
        </div>
      )}

      <form onSubmit={handleSubmit} className={isModal ? "" : "form-card"}>
        <div className="form-row-2col">
          <div className="form-group">
            <label className="form-label" htmlFor="ret-order">Pesanan (SO) <span className="req">*</span></label>
            <input data-testid="return-order-search" className="form-input mb-1.5" value={orderQ}
              onChange={(e) => setOrderQ(e.target.value)} placeholder="Cari nomor SO / nama pelanggan…" />
            <KNSelect
              data-testid="return-order-select"
              className="form-select"
              value={orderId}
              onValueChange={handleOrderChange}
              placeholder="-- Pilih pesanan --"
              options={[
                { value: "", label: "-- Pilih pesanan --" },
                ...(orderId && !orderOpts.some((o) => o.id === orderId) && knownRef.current[orderId]
                  ? [knownRef.current[orderId]] : []).concat(orderOpts)
                  .map(o => ({ value: o.id, label: `${o.number} — ${o.customer_name} (${stageMeta(getStage(o)).label})` })),
              ]}
            />
            <p className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-[#6B6B73]" data-testid="return-order-meta">
              {orderMeta.loading ? "Mencari…" : orderMeta.error ? <span className="text-[#A8221A]">{orderMeta.error}</span>
                : `${orderOpts.length} dari ${orderMeta.total} pesanan yang masih punya barang terkirim untuk diretur`}
              {orderMeta.has_more && !orderMeta.loading && (
                <button type="button" className="font-semibold text-[#0058CC] underline" data-testid="return-order-more"
                  onClick={() => searchOrders(orderQ.trim(), orderMeta.page + 1)}>Muat lagi</button>
              )}
            </p>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="ret-type">Tipe Return <span className="req">*</span></label>
            <KNSelect
              data-testid="return-type-select"
              className="form-select"
              value={returnType}
              onValueChange={setReturnType}
              options={[
                { value: "retur", label: "Retur (pelanggan kembalikan barang)" },
                { value: "bs", label: "Barang Sisa — BS (sisa penggunaan)" },
                { value: "penggantian", label: "Penggantian (cacat / salah kirim)" },
                { value: "komplain", label: "Komplain (keluhan kualitas)" },
                { value: "garansi", label: "Garansi (klaim jaminan)" },
              ]}
            />
          </div>
        </div>

        {/* R0 — Banner kelayakan & deadline retur (kebijakan retur jual) */}
        {orderId && (
          <div data-testid="return-eligibility-banner"
            className={`rounded-md border px-3 py-2.5 text-[11.5px] ${
              eligibility?.blocked ? "border-[#E5484D] bg-[#FDECEC]"
                : eligibility?.within_window === false ? "border-[#A05000] bg-[#FFF6E9]"
                : "border-[#EFF0F2] bg-[#FAFBFC]"}`}>
            {checking ? (
              <span className="flex items-center gap-1.5 text-[#6B6B73]"><Loader2 size={12} className="spin" /> Mengecek kebijakan retur...</span>
            ) : eligibility ? (
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <span className="flex items-center gap-1.5 font-semibold">
                    <ShieldCheck size={13} className="text-[#0058CC]" />
                    Kebijakan: {eligibility.policy?.name || "Default"}
                  </span>
                  <span className="flex items-center gap-1.5 tabular-nums" data-testid="eligibility-deadline">
                    <CalendarClock size={12} className="text-[#6B6B73]" />
                    {eligibility.deadline
                      ? <>Deadline retur: <b>{String(eligibility.deadline).slice(0, 10)}</b>
                          {eligibility.days_remaining != null && ` (${eligibility.days_remaining} hari lagi)`}</>
                      : `Window ${eligibility.window_days} hari (tgl kirim tidak diketahui)`}
                  </span>
                  {eligibility.require_inspection && (
                    <span className="status-pill pill-warning">Inspeksi wajib setelah disetujui</span>
                  )}
                </div>
                {(eligibility.warnings || []).map((w, i) => (
                  <p key={i} className="text-[#A05000] flex items-center gap-1" data-testid={`eligibility-warning-${i}`}>
                    <AlertCircle size={11} /> {w}
                  </p>
                ))}
                {eligibility.blocked && (
                  <p className="text-[#E5484D] font-semibold">Kebijakan memblokir retur di luar window. Hubungi manajer bila tetap perlu diproses.</p>
                )}
              </div>
            ) : (
              <span className="text-[#6B6B73]">Kebijakan retur tidak dapat dievaluasi untuk pesanan ini.</span>
            )}
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Item yang Diretur <span className="req">*</span></label>
          {orderId && shipped && !items.length && (
            <p className="text-[11.5px] text-[#A05000]" data-testid="return-nothing-shipped">Belum ada barang terkirim (Surat Jalan) yang masih bisa diretur untuk pesanan ini.</p>
          )}
          <div className="form-items-table">
            <div className="form-items-header">
              <span>Produk (dari Surat Jalan)</span><span>Qty</span><span>Satuan</span><span>Kondisi</span><span>Alasan</span><span></span>
            </div>
            {items.map((it, i) => (
              <div key={it.product_id} data-testid={`return-item-row-${i}`}>
              <div className="form-items-row">
                <div className="text-[11.5px]" data-testid={`item-product-${i}`}>
                  <b>{it.product_name || it.sku}</b>
                  <span className="block text-[10.5px] text-[#6B6B73]">{it.sku}{it.color ? ` · ${it.color}` : ""} · sisa {it.max} {it.unit}</span></div>
                <input data-testid={`item-qty-${i}`} className="form-input text-right" type="number"
                  min="0.01" step="0.01" max={it.max} placeholder="0.00"
                  value={it.quantity_returned} onChange={e => updateItem(i, "quantity_returned", e.target.value)} />
                <span className="text-[11.5px] self-center" data-testid={`item-unit-${i}`}>{it.unit}</span>
                <KNSelect data-testid={`item-condition-${i}`} className="form-select" value={it.condition}
                  onValueChange={v => updateItem(i, "condition", v)}
                  options={[
                    { value: "ok", label: "Baik" },
                    { value: "damaged", label: "Rusak" },
                  ]}
                />
                <input data-testid={`item-reason-${i}`} className="form-input" placeholder="Alasan..."
                  value={it.reason} onChange={e => updateItem(i, "reason", e.target.value)} />
                <button type="button" className="icon-button danger" onClick={() => removeItem(i)}
                  disabled={items.length === 1} data-testid={`remove-item-${i}`}>
                  <Trash2 size={12} />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5 px-1 pb-2" data-testid={`item-rolls-${i}`}>
                {rollsOf(it.product_id).map((r) => (
                  <label key={r.roll_id} className={`text-[10.5px] rounded-full border px-2 py-0.5 cursor-pointer ${it.roll_ids.includes(r.roll_id) ? "border-[#0058CC] bg-[#EEF4FF]" : "border-[#E1E4EA]"}`} data-testid={`item-roll-${r.roll_id}`}>
                    <input type="checkbox" className="mr-1 align-middle" checked={it.roll_ids.includes(r.roll_id)} onChange={() => toggleRoll(i, r)} />
                    <span className="font-mono">{r.roll_no || r.roll_id}</span> · {r.shipment_no} · {r.remaining} {r.unit}</label>
                ))}
              </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cek UI UAT v3 (S14) — sebab keluhan dari master; dulu hanya bisa diisi belakangan di detail retur. */}
        {reasons.length > 0 && (
          <div className="form-group">
            <label className="form-label">Sebab keluhan</label>
            <KNSelect data-testid="return-complaint-code" className="form-select" value={complaintCode}
              onValueChange={setComplaintCode} placeholder="-- Pilih sebab keluhan --"
              options={reasons.map((r) => ({ value: r.value, label: r.label }))} />
          </div>
        )}

        <div className="form-group">
          <label className="form-label" htmlFor="ret-notes">Catatan</label>
          <textarea id="ret-notes" data-testid="return-notes-input" className="textarea" rows={2}
            placeholder="Keterangan tambahan..." value={notes} onChange={e => setNotes(e.target.value)} />
        </div>

        <div className="form-group">
          <label className="form-label">Bukti foto {evPolicy?.submit ? <span className="req">* (wajib sebelum diajukan)</span> : <span className="text-[10.5px] text-[#6B6B73]">(boleh dilengkapi kemudian)</span>}</label>
          <div className="flex flex-wrap items-center gap-2">
            {/* Kamera HP langsung (capture) — foto ditambahkan ke daftar, bukan menimpa. */}
            <label data-testid="return-camera-capture" className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[#0058CC] px-3 py-1.5 text-xs font-semibold text-[#0058CC]">
              <Camera size={13} /> Ambil foto
              <input data-testid="return-camera-input" type="file" accept="image/*" capture="environment" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setFiles((cur) => [...cur, f]); e.target.value = ""; }} />
            </label>
            <input data-testid="return-photo-input" type="file" accept="image/*,.pdf" multiple className="form-input min-w-0 flex-1"
              onChange={(e) => { const add = Array.from(e.target.files || []); setFiles((cur) => [...cur, ...add]); e.target.value = ""; }} />
          </div>
          {files.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1.5" data-testid="return-photo-list">
              {files.map((f, i) => (
                <span key={`${f.name}-${i}`} className="inline-flex items-center text-[10.5px] rounded-full border border-[#E1E4EA] px-2 py-0.5"><Paperclip size={10} className="inline mr-1" />{f.name || `foto-${i + 1}.jpg`}
                  <button type="button" className="ml-1 text-[#C62828]" data-testid={`return-photo-remove-${i}`} onClick={() => setFiles((cur) => cur.filter((_, j) => j !== i))} aria-label="Hapus foto"><X size={10} /></button></span>
              ))}
            </div>
          )}
          {needsPhotoToSubmit && (
            <p className="text-[11px] text-[#A05000] mt-1" data-testid="return-photo-required-hint">Lampirkan minimal satu foto, atau hapus centang "Langsung kirim" untuk menyimpan draf.</p>
          )}
        </div>

        <div className="form-group" data-testid="return-condition-flags">
          <label className="form-label">Kondisi barang</label>
          <div className="flex flex-wrap gap-4 text-sm">
            {[["hangtag_missing", "Hangtag hilang"], ["cut_by_customer", "Kain sudah dipotong customer"], ["replacement_proof", "Ada bukti pengganti (foto/nota)"]].map(([k, l]) => (
              <label key={k} className="form-check-label">
                <input type="checkbox" data-testid={`return-cond-${k}`} checked={cond[k]}
                       onChange={(e) => setCond((c) => ({ ...c, [k]: e.target.checked }))} /> {l}
              </label>
            ))}
          </div>
          {(cond.hangtag_missing || cond.cut_by_customer) && (
            <p className="text-xs text-[#8A4B08] mt-1" data-testid="return-cond-note">
              Perhatian: kondisi ini tidak memblokir retur. Finance memutus saat penyelesaian dan wajib menulis catatan keputusan.
            </p>
          )}
        </div>

        <div className="form-group">
          <label className="form-check-label">
            <input type="checkbox" data-testid="submit-now-check" checked={submitNow}
              onChange={e => setSubmitNow(e.target.checked)} />
            {" "}Langsung kirim untuk persetujuan (lewati draf)
          </label>
        </div>

        <div className="form-actions">
          <button type="button" className="secondary-button" onClick={onCancel}>Batal</button>
          <button type="submit" data-testid="save-return-btn" className="primary-button" disabled={saving}>
            {saving ? <Loader2 size={14} className="spin" /> : <RotateCcw size={14} />} Buat Return
          </button>
        </div>
      </form>
    </div>
  );
}
