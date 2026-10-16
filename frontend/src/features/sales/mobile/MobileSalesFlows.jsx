/**
 * Alur penjualan HP yang melengkapi versi web:
 *  - Manajemen pelanggan : kredit, kontak (telepon/WA), ubah data, tambah alamat, catat tindak lanjut.
 *  - Detail Pesanan Khusus (OD): tahapan, spesifikasi, harga final, ajukan draf, keputusan pelanggan
 *    (ACC / minta revisi / tolak) + foto bukti.
 *  - Aksi retur: ajukan draf + unggah foto bukti.
 * Endpoint & wewenang sama dengan layar desktop (Customer360Panel, SpecialOrderDetail, SalesReturns).
 */
import { useEffect, useState } from "react";
import { ArrowLeft, Camera, Check, MessageCircle, Phone, Plus, RotateCcw, Send, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import LocationFields, { locationIncomplete } from "../../../components/LocationFields";
import { formatCurrency, formatQty } from "../../../utils/formatters";

export const errText = (e, fb) => {
  const d = e?.response?.data?.detail;
  if (!d) return fb;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || "").join("; ") || fb;
  return d.message || fb;
};
const fmtDate = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" }) : "-");
const waNumber = (p) => String(p || "").replace(/\D/g, "").replace(/^0/, "62");

function Sheet({ title, onClose, children, footer, testId }) {
  return (
    <div className="fixed inset-0 z-[140] flex flex-col bg-[#F2F2F7]" data-testid={testId}>
      <div className="m-subpage-head">
        <button className="m-subpage-back" onClick={onClose} data-testid={`${testId}-close`}><ArrowLeft size={17} /> Batal</button>
        <span className="m-subpage-title">{title}</span>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3 pb-28">{children}</div>
      {footer && <div className="fixed inset-x-0 bottom-0 border-t border-[#E5E5EA] bg-white p-3" style={{ paddingBottom: "calc(12px + env(safe-area-inset-bottom))" }}>{footer}</div>}
    </div>
  );
}
const Field = ({ label, req, children }) => (
  <label className="block"><span className="mb-1 block text-[11.5px] font-semibold text-[#4A4B53]">{label} {req && <span className="text-[#C0392B]">*</span>}</span>{children}</label>
);

/* ───────────────────────── Pelanggan ───────────────────────── */

const CREDIT = { ok: ["Aman", "#1B7F4B", "#E6F6EC"], warning: ["Waspada", "#8A5300", "#FFF4E5"], blocked: ["Diblokir", "#C0392B", "#FDEDE7"] };

export function CustomerCreditCard({ credit }) {
  if (!credit) return null;
  const [label, fg, bg] = CREDIT[credit.status] || CREDIT.ok;
  const limit = Number(credit.credit_limit || 0);
  const used = Number(credit.ar_outstanding || 0);
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div className="m-card p-3" data-testid="m-customer-credit">
      <div className="flex items-center justify-between">
        <p className="text-[12px] font-bold">Kredit pelanggan</p>
        <span className="rounded px-1.5 py-0.5 text-[10px] font-bold" style={{ color: fg, background: bg }} data-testid="m-customer-credit-status">{label}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#EFF0F2]"><div className="h-full rounded-full" style={{ width: `${pct}%`, background: fg }} /></div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-[10.5px]">
        <div><p className="m-muted">Limit</p><p className="font-bold tabular-nums text-[12px]">{limit ? formatCurrency(limit) : "Tanpa limit"}</p></div>
        <div><p className="m-muted">Tersedia</p><p className="font-bold tabular-nums text-[12px] text-[#1B7F4B]" data-testid="m-customer-credit-available">{formatCurrency(credit.available_credit)}</p></div>
        <div><p className="m-muted">Lewat tempo</p><p className="font-bold tabular-nums text-[12px] text-[#C0392B]">{formatCurrency(credit.overdue_amount)}</p></div>
      </div>
      {credit.max_overdue_days > 0 && <p className="mt-1 text-[10.5px] text-[#C0392B]">Tunggakan terlama {credit.max_overdue_days} hari · {credit.open_orders || 0} pesanan terbuka</p>}
      {credit.status === "blocked" && <p className="mt-1 text-[10.5px] text-[#8A5300]">Pesanan baru akan tertahan sampai tunggakan dibayar atau manajer memberi izin kredit.</p>}
    </div>
  );
}

export function CustomerContactBar({ customer }) {
  const phone = customer?.phone || customer?.contacts?.[0]?.phone;
  if (!phone) return null;
  return (
    <div className="grid grid-cols-2 gap-2" data-testid="m-customer-contact-bar">
      <a href={`tel:${phone}`} className="secondary-button flex items-center justify-center gap-1.5 py-2.5 text-[12px]" data-testid="m-customer-call"><Phone size={14} /> Telepon</a>
      <a href={`https://wa.me/${waNumber(phone)}`} target="_blank" rel="noreferrer" className="secondary-button flex items-center justify-center gap-1.5 py-2.5 text-[12px]" data-testid="m-customer-wa"><MessageCircle size={14} /> WhatsApp</a>
    </div>
  );
}

export function CustomerEditSheet({ customer, onClose, onSaved }) {
  const [f, setF] = useState({ name: customer.name || "", pic_name: customer.pic_name || "", phone: customer.phone || "", email: customer.email || "", city: customer.city || "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const valid = f.name.trim() && f.phone.trim();
  const save = async () => {
    setBusy(true); setErr("");
    try { const r = await axios.patch(`${API}/customers/${customer.id}`, { data: f }); onSaved?.(r.data); }
    catch (e) { setErr(errText(e, "Perubahan gagal disimpan.")); } finally { setBusy(false); }
  };
  return (
    <Sheet title="Ubah Data Pelanggan" onClose={onClose} testId="m-customer-edit"
      footer={<button className="primary-button w-full py-3" disabled={!valid || busy} onClick={save} data-testid="m-customer-edit-save">{busy ? "Menyimpan…" : "Simpan perubahan"}</button>}>
      <div className="m-card space-y-2.5 p-4">
        <Field label="Nama toko / pelanggan" req><input className="field" value={f.name} onChange={set("name")} data-testid="m-customer-edit-name" /></Field>
        <Field label="Nama PIC"><input className="field" value={f.pic_name} onChange={set("pic_name")} data-testid="m-customer-edit-pic" /></Field>
        <Field label="No. HP / WhatsApp" req><input className="field" inputMode="tel" value={f.phone} onChange={set("phone")} data-testid="m-customer-edit-phone" /></Field>
        <Field label="Email"><input className="field" inputMode="email" value={f.email} onChange={set("email")} data-testid="m-customer-edit-email" /></Field>
        <Field label="Kota"><input className="field" value={f.city} onChange={set("city")} data-testid="m-customer-edit-city" /></Field>
      </div>
      <p className="px-1 text-[11px] m-muted">Limit kredit, segmen & sales penanggung jawab diatur manajer di Manajemen Pelanggan.</p>
      {err && <div className="notice-bar danger text-xs" data-testid="m-customer-edit-error">{err}</div>}
    </Sheet>
  );
}

export function CustomerAddressSheet({ customer, onClose, onSaved }) {
  const [f, setF] = useState({ label: "Gudang / Cabang", recipient_name: customer.pic_name || "", phone: customer.phone || "", address: "", city: "", is_primary: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const valid = f.recipient_name.trim() && f.address.trim().length >= 3 && !locationIncomplete(f);
  const save = async () => {
    setBusy(true); setErr("");
    try { const r = await axios.post(`${API}/customers/${customer.id}/addresses`, { ...f, city: f.city || f.regency || "" }); onSaved?.(r.data); }
    catch (e) { setErr(errText(e, "Alamat gagal disimpan.")); } finally { setBusy(false); }
  };
  return (
    <Sheet title="Tambah Alamat Kirim" onClose={onClose} testId="m-address-form"
      footer={<button className="primary-button w-full py-3" disabled={!valid || busy} onClick={save} data-testid="m-address-form-save">{busy ? "Menyimpan…" : "Simpan alamat"}</button>}>
      <div className="m-card space-y-2.5 p-4">
        <Field label="Label alamat"><input className="field" value={f.label} onChange={set("label")} data-testid="m-address-form-label" /></Field>
        <Field label="Nama penerima" req><input className="field" value={f.recipient_name} onChange={set("recipient_name")} data-testid="m-address-form-recipient" /></Field>
        <Field label="No. HP penerima"><input className="field" inputMode="tel" value={f.phone} onChange={set("phone")} data-testid="m-address-form-phone" /></Field>
        <LocationFields testId="m-address-form-loc" compact value={f} onChange={(patch) => setF((x) => ({ ...x, ...patch }))} />
        <Field label="Alamat lengkap" req><input className="field" value={f.address} onChange={set("address")} placeholder="Jalan, nomor, patokan" data-testid="m-address-form-address" /></Field>
        <label className="flex items-center gap-2 text-[12px]"><input type="checkbox" checked={f.is_primary} onChange={set("is_primary")} data-testid="m-address-form-primary" /> Jadikan alamat utama</label>
      </div>
      {err && <div className="notice-bar danger text-xs" data-testid="m-address-form-error">{err}</div>}
    </Sheet>
  );
}

const OUTCOMES = [["contacted", "Sudah dihubungi"], ["promised", "Janji bayar"], ["paid", "Sudah bayar"], ["no_response", "Tidak merespons"], ["escalated", "Eskalasi ke manajer"]];
export const outcomeLabel = (o) => (OUTCOMES.find(([k]) => k === o) || [o, o])[1];

export function CustomerFollowupSheet({ customer, orders = [], onClose, onSaved }) {
  const [f, setF] = useState({ note: "", outcome: "contacted", next_action_date: "", order_id: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const save = async () => {
    setBusy(true); setErr("");
    try { const r = await axios.post(`${API}/customers/${customer.id}/followups`, { customer_id: customer.id, ...f }); onSaved?.(r.data); }
    catch (e) { setErr(errText(e, "Tindak lanjut gagal disimpan.")); } finally { setBusy(false); }
  };
  return (
    <Sheet title="Catat Tindak Lanjut" onClose={onClose} testId="m-followup-form"
      footer={<button className="primary-button w-full py-3" disabled={!f.note.trim() || busy} onClick={save} data-testid="m-followup-form-save">{busy ? "Menyimpan…" : "Simpan tindak lanjut"}</button>}>
      <div className="m-card space-y-2.5 p-4">
        <p className="text-[11.5px] m-muted">Jejak penagihan / kunjungan untuk <b>{customer.name}</b> — terlihat juga oleh finance & manajer.</p>
        <div className="flex flex-wrap gap-1.5">
          {OUTCOMES.map(([k, l]) => (
            <button key={k} onClick={() => setF({ ...f, outcome: k })} data-testid={`m-followup-outcome-${k}`}
              className={`h-9 rounded-full border px-3 text-[12px] font-semibold ${f.outcome === k ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C]"}`}>{l}</button>
          ))}
        </div>
        {orders.length > 0 && (
          <Field label="Untuk pesanan (opsional)">
            <select className="field" value={f.order_id} onChange={(e) => setF({ ...f, order_id: e.target.value })} data-testid="m-followup-order">
              <option value="">— Umum —</option>
              {orders.map((o) => <option key={o.id} value={o.id}>{o.number} · sisa {formatCurrency(Number(o.grand_total || 0) - Number(o.paid || 0))}</option>)}
            </select>
          </Field>
        )}
        <Field label="Catatan" req><textarea className="field" rows={3} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} placeholder="Hasil pembicaraan, janji bayar, dll." data-testid="m-followup-note" /></Field>
        <Field label="Tindak lanjut berikutnya"><input type="date" className="field" value={f.next_action_date} onChange={(e) => setF({ ...f, next_action_date: e.target.value })} data-testid="m-followup-date" /></Field>
      </div>
      {err && <div className="notice-bar danger text-xs" data-testid="m-followup-form-error">{err}</div>}
    </Sheet>
  );
}

/* ───────────────────────── Pesanan Khusus (OD) ───────────────────────── */

export const OD_STATUS = {
  draft: ["Draf", "#6B6B73", "#F2F3F5"], pending_approval: ["Menunggu persetujuan", "#8A5300", "#FFF4E5"], approved: ["Disetujui", "#1B7F4B", "#E6F6EC"],
  confirmed: ["Terkonfirmasi", "#0058CC", "#EAF2FF"], in_production: ["Dalam produksi", "#6B219A", "#F3E8FA"], ready: ["Siap", "#1B7F4B", "#E6F6EC"],
  shipped: ["Dikirim", "#0058CC", "#EAF2FF"], done: ["Selesai", "#1B7F4B", "#E6F6EC"], cancelled: ["Dibatalkan", "#C0392B", "#FDEDE7"], rejected: ["Ditolak", "#C0392B", "#FDEDE7"],
};
export const OdStatus = ({ status, testId }) => {
  const [l, fg, bg] = OD_STATUS[status] || [status, "#6B6B73", "#F2F3F5"];
  return <span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ color: fg, background: bg }} data-testid={testId}>{l}</span>;
};
const DECISIONS = [["acc", "ACC", Check], ["revisi", "Minta revisi", RotateCcw], ["tolak", "Tolak", X]];

function PhotoPicker({ files, setFiles, testId }) {
  return (
    <div>
      <label className="secondary-button flex w-full cursor-pointer items-center justify-center gap-1.5 py-2.5 text-[12px]" data-testid={`${testId}-btn`}>
        <Camera size={14} /> {files.length ? `${files.length} foto dipilih` : "Ambil / pilih foto bukti"}
        <input type="file" accept="image/*,application/pdf" capture="environment" multiple className="hidden"
          onChange={(e) => setFiles([...files, ...Array.from(e.target.files || [])])} data-testid={`${testId}-input`} />
      </label>
      {files.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {files.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded-full bg-[#F2F3F5] px-2 py-0.5 text-[10.5px]">
              {f.name.slice(0, 18)} <button onClick={() => setFiles(files.filter((_, j) => j !== i))} aria-label="Hapus foto"><X size={11} /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function OdCustomerDecision({ od, onChanged }) {
  const [mode, setMode] = useState("");
  const [note, setNote] = useState("");
  const [contact, setContact] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const review = od.chain?.review || {};
  const locked = !!od.chain?.pricing?.locked;
  const canDecide = review.ready && !locked && od.status !== "cancelled" && od.customer_decision !== "acc";
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/special-orders/${od.id}/customer-decision`, { decision: mode, note, decided_at: date, contact_name: contact });
      const decId = r.data.decision?.id;
      for (const file of files) {
        const fd = new FormData(); fd.append("file", file); fd.append("decision_id", decId);
        await axios.post(`${API}/special-orders/${od.id}/customer-decision/evidence`, fd);
      }
      setMode(""); setNote(""); setFiles([]); onChanged?.("Keputusan pelanggan tersimpan.");
    } catch (e) { setErr(errText(e, "Gagal menyimpan keputusan pelanggan.")); } finally { setBusy(false); }
  };
  const history = od.customer_decisions || [];
  return (
    <div className="m-card p-3" data-testid="m-od-customer-decision">
      <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Persetujuan pelanggan atas sampel</p>
      {od.customer_decision === "acc" && <p className="mt-1 text-[12px] font-semibold text-[#1B7F4B]" data-testid="m-od-customer-acc">Pelanggan sudah ACC · {od.customer_decision_at || ""}</p>}
      {!review.ready && <p className="mt-1 text-[11.5px] m-muted" data-testid="m-od-customer-not-ready">Aktif setelah R&D menutup sampling (pemenang sampel / desain ACC).</p>}
      {review.ready && review.sample && <p className="mt-1 text-[11.5px]">Dasar: sampel <b>{review.sample.number}</b></p>}
      {canDecide && (
        <>
          <div className="mt-2 grid grid-cols-3 gap-1.5">
            {DECISIONS.map(([k, l, Icon]) => (
              <button key={k} onClick={() => setMode(k)} data-testid={`m-od-decision-${k}`}
                className={`flex h-10 items-center justify-center gap-1 rounded-xl border text-[12px] font-semibold ${mode === k ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white"}`}><Icon size={13} /> {l}</button>
            ))}
          </div>
          {mode && (
            <div className="mt-2 space-y-2">
              <input className="field" placeholder="Nama kontak pelanggan" value={contact} onChange={(e) => setContact(e.target.value)} data-testid="m-od-decision-contact" />
              <input type="date" className="field" value={date} onChange={(e) => setDate(e.target.value)} data-testid="m-od-decision-date" />
              <textarea className="field" rows={2} placeholder={mode === "revisi" ? "Apa yang perlu direvisi?" : "Catatan"} value={note} onChange={(e) => setNote(e.target.value)} data-testid="m-od-decision-note" />
              <PhotoPicker files={files} setFiles={setFiles} testId="m-od-decision-photo" />
              <button className="primary-button w-full py-2.5" disabled={busy || (mode !== "acc" && !note.trim())} onClick={submit} data-testid="m-od-decision-submit">{busy ? "Menyimpan…" : "Simpan keputusan"}</button>
            </div>
          )}
        </>
      )}
      {err && <div className="notice-bar danger mt-2 text-xs" data-testid="m-od-decision-error">{err}</div>}
      {history.length > 0 && (
        <div className="mt-2 border-t border-[#EFF0F2] pt-2">
          {history.slice().reverse().map((h) => (
            <p key={h.id} className="text-[11px]"><b>{(DECISIONS.find(([k]) => k === h.decision) || [h.decision, h.decision])[1]}</b> · {h.decided_at || fmtDate(h.created_at)}{h.contact_name ? ` · ${h.contact_name}` : ""}{h.note ? ` — ${h.note}` : ""}{(h.evidence || []).length ? ` · ${(h.evidence || []).length} bukti` : ""}</p>
          ))}
        </div>
      )}
    </div>
  );
}

export function MobileSpecialOrderDetail({ id, onBack }) {
  const [od, setOd] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => axios.get(`${API}/special-orders/${id}`).then((r) => setOd(r.data)).catch((e) => setErr(errText(e, "Gagal memuat pesanan khusus.")));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = async () => {
    setBusy(true); setErr("");
    try { const r = await axios.post(`${API}/special-orders/${id}/submit`); setOd((o) => ({ ...o, ...r.data })); setMsg("Diajukan untuk persetujuan."); load(); }
    catch (e) { setErr(errText(e, "Gagal mengajukan.")); } finally { setBusy(false); }
  };
  if (!od) return <div className="p-3">{err ? <div className="notice-bar danger text-xs">{err}</div> : <p className="text-xs m-muted">Memuat…</p>}</div>;
  const item = od.custom_item || {};
  const pricing = od.chain?.pricing || {};
  const phases = od.chain?.phases || [];
  const phaseIdx = phases.findIndex(([k]) => k === (od.chain?.phase || od.status));
  return (
    <div className="space-y-2 p-3" data-testid="m-od-detail">
      <button className="m-subpage-back" onClick={onBack} data-testid="m-od-back"><ArrowLeft size={17} /> Pesanan khusus</button>
      <div className="m-card p-4">
        <div className="flex items-start justify-between gap-2"><p className="text-[15px] font-bold">{od.number}</p><OdStatus status={od.status} testId="m-od-status" /></div>
        <p className="text-[12px] text-[#3C3C43]">{od.customer_name}</p>
        <p className="mt-1 text-[13px] font-semibold">{item.description || item.name}</p>
        <p className="text-[11.5px] m-muted">{formatQty(item.quantity)} {item.unit} · target kirim {fmtDate(od.expected_delivery)}{item.target_price ? ` · target ${formatCurrency(item.target_price)}/${item.unit}` : ""}</p>
        {item.specifications && Object.keys(item.specifications).length > 0 && (
          <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 rounded-xl bg-[#F7F8FA] p-2.5 text-[11px]" data-testid="m-od-specs">
            {Object.entries(item.specifications).map(([k, v]) => <p key={k}><span className="m-muted capitalize">{k}: </span>{String(v)}</p>)}
          </div>
        )}
        {pricing.locked && <p className="mt-2 text-[12px]" data-testid="m-od-final-price">Harga final <b>{formatCurrency(pricing.final_unit_price)}</b>/{pricing.unit} · total {formatCurrency(pricing.total)}</p>}
        {od.chain?.so && <p className="mt-1 text-[11.5px] text-[#1B7F4B]">Sudah menjadi pesanan {od.chain.so.number}</p>}
        {od.status === "draft" && <button className="primary-button mt-3 flex w-full items-center justify-center gap-1.5 py-2.5" disabled={busy} onClick={submit} data-testid="m-od-submit"><Send size={14} /> Ajukan untuk persetujuan</button>}
      </div>
      {msg && <div className="notice-bar success text-xs" data-testid="m-od-msg">{msg}</div>}
      {err && <div className="notice-bar danger text-xs" data-testid="m-od-error">{err}</div>}
      {phases.length > 0 && (
        <div className="m-card p-3" data-testid="m-od-phases">
          <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Tahapan</p>
          <div className="no-scrollbar flex gap-1.5 overflow-x-auto">
            {phases.map(([k, l], i) => (
              <span key={k} className={`shrink-0 rounded-full px-2.5 py-1 text-[10.5px] font-semibold ${i < phaseIdx ? "bg-[#E6F6EC] text-[#1B7F4B]" : i === phaseIdx ? "bg-[#0058CC] text-white" : "bg-[#F2F3F5] text-[#8E8E93]"}`}>{l}</span>
            ))}
          </div>
        </div>
      )}
      <OdCustomerDecision od={od} onChanged={(m) => { setMsg(m); load(); }} />
      {(od.status_history || []).length > 0 && (
        <div className="m-card p-3" data-testid="m-od-history">
          <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Riwayat</p>
          {od.status_history.slice().reverse().map((h, i) => (
            <p key={i} className="text-[11px]"><b>{(OD_STATUS[h.status] || [h.status])[0]}</b> · {fmtDate(h.timestamp)} · {h.user}{h.note ? ` — ${h.note}` : ""}</p>
          ))}
        </div>
      )}
    </div>
  );
}

/* ───────────────────────── Retur ───────────────────────── */

export function MobileReturnActions({ ret, onChanged }) {
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const terminal = ["settled", "credit_settled", "rejected", "cancelled", "completed"].includes(ret.status);
  const submit = async () => {
    setBusy(true); setMsg(null);
    try { await axios.post(`${API}/sales-returns/${ret.id}/submit`); setMsg({ ok: true, text: `${ret.number} diajukan — menunggu diproses gudang/manajer.` }); onChanged?.(); }
    catch (e) { setMsg({ ok: false, text: errText(e, "Gagal mengajukan retur.") }); } finally { setBusy(false); }
  };
  const upload = async () => {
    setBusy(true); setMsg(null);
    try {
      for (const f of files) { const fd = new FormData(); fd.append("file", f); await axios.post(`${API}/sales-returns/${ret.id}/attachments`, fd); }
      setMsg({ ok: true, text: `${files.length} bukti terunggah.` }); setFiles([]); onChanged?.();
    } catch (e) { setMsg({ ok: false, text: errText(e, "Unggah bukti gagal.") }); } finally { setBusy(false); }
  };
  return (
    <div className="m-card space-y-2 p-3" data-testid="m-return-actions">
      {ret.status === "draft" && <button className="primary-button flex w-full items-center justify-center gap-1.5 py-2.5" disabled={busy} onClick={submit} data-testid="m-return-submit-draft"><Send size={14} /> Ajukan retur ini</button>}
      {!terminal && (
        <>
          <p className="text-[11px] m-muted">Foto kain cacat / surat jalan mempercepat pemeriksaan. {(ret.attachments || []).length ? `${ret.attachments.length} bukti sudah terlampir.` : ""}</p>
          <PhotoPicker files={files} setFiles={setFiles} testId="m-return-photo" />
          {files.length > 0 && <button className="secondary-button flex w-full items-center justify-center gap-1.5 py-2.5 text-[12px]" disabled={busy} onClick={upload} data-testid="m-return-upload"><Plus size={14} /> Unggah {files.length} bukti</button>}
        </>
      )}
      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"} text-xs`} data-testid="m-return-action-msg">{msg.text}</div>}
    </div>
  );
}

