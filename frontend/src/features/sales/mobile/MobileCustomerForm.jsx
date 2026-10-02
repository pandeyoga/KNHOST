import { useState } from "react";
import { ArrowLeft, UserPlus } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import LocationFields, { locationIncomplete } from "../../../components/LocationFields";
import { errText } from "../../finance/amendments/amendmentApi";

const EMPTY = { name: "", pic_name: "", phone: "", email: "", city: "", address: "" };

/** Tambah pelanggan dari HP — data dasar yang sama dengan desktop; sales pembuat otomatis jadi PIC. */
export default function MobileCustomerForm({ user, selectedEntity, onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const valid = form.name.trim() && form.pic_name.trim() && form.phone.trim() && form.address.trim().length >= 3 && !locationIncomplete(form);

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true); setErr("");
    try {
      const body = { ...form, ...(selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}) };
      const r = await axios.post(`${API}/customers`, body);
      onCreated?.(r.data);
    } catch (e) {
      setErr(errText(e, "Pelanggan gagal disimpan."));
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-[140] flex flex-col bg-[#F2F2F7]" data-testid="m-customer-form">
      <div className="m-subpage-head">
        <button className="m-subpage-back" onClick={onClose} data-testid="m-customer-form-close"><ArrowLeft size={17} /> Batal</button>
        <span className="m-subpage-title">Pelanggan Baru</span>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3 pb-28">
        <div className="m-card space-y-2.5 p-4">
          <Field label="Nama toko / pelanggan" req><input className="field" value={form.name} onChange={set("name")} placeholder="PT / Toko …" data-testid="m-customer-form-name" /></Field>
          <Field label="Nama PIC toko" req><input className="field" value={form.pic_name} onChange={set("pic_name")} placeholder="Nama PIC di pihak pelanggan" data-testid="m-customer-form-pic" /></Field>
          <Field label="No. HP / WhatsApp PIC" req><input className="field" inputMode="tel" value={form.phone} onChange={set("phone")} placeholder="08…" data-testid="m-customer-form-phone" /></Field>
          <Field label="Email (opsional)"><input className="field" inputMode="email" value={form.email} onChange={set("email")} data-testid="m-customer-form-email" /></Field>
        </div>
        <div className="m-card space-y-2.5 p-4">
          <p className="text-[12px] font-bold">Alamat toko <span className="text-[#C0392B]">*</span></p>
          <LocationFields testId="m-customer-form-loc" compact value={form} onChange={(patch) => setForm((p) => ({ ...p, ...patch }))} />
          <input className="field" value={form.address} onChange={set("address")} placeholder="Jalan, nomor, patokan" data-testid="m-customer-form-address" />
        </div>
        <p className="rounded-xl border border-[#CDE9D6] bg-[#F4FCF6] px-3 py-2 text-[11px] text-[#1A7A3A]" data-testid="m-customer-form-owner">
          {user?.role === "sales" ? <>Sales penanggung jawab: <b>{user?.name}</b> (akun Anda) — otomatis.</> : <>Sales penanggung jawab diatur di Manajemen Pelanggan (desktop).</>}
          {" "}Segment, kebijakan lot & limit kredit bisa dilengkapi nanti.
        </p>
        {err && <div className="notice-bar danger text-xs" data-testid="m-customer-form-error">{err}</div>}
      </div>
      <div className="fixed inset-x-0 bottom-0 border-t border-[#E5E5EA] bg-white p-3" style={{ paddingBottom: "calc(12px + env(safe-area-inset-bottom))" }}>
        <button className="primary-button flex w-full items-center justify-center gap-2 py-3" disabled={!valid || busy} onClick={submit} data-testid="m-customer-form-submit">
          <UserPlus size={16} /> {busy ? "Menyimpan…" : "Simpan pelanggan"}
        </button>
      </div>
    </div>
  );
}

function Field({ label, req, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11.5px] font-semibold text-[#4A4B53]">{label} {req && <span className="text-[#C0392B]">*</span>}</span>
      {children}
    </label>
  );
}
