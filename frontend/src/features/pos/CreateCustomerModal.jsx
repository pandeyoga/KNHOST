import { useState } from "react";
import { X, UserPlus } from "lucide-react";
import LocationFields, { locationIncomplete } from "../../components/LocationFields";
import { roleLabel } from "../../config/roles";
import { apiErrorText } from "../../utils/apiError";

/** EPIC5 — Buat Pelanggan sebagai MODAL (dipanggil dari checkout step 1).
 * SALES REVAMP V2 — Kebijakan lot DIPINDAH ke Manajemen Pelanggan (CustomerFormModal).
 * Quick-add POS hanya data dasar; lot policy diatur di Manajemen Pelanggan. */
export default function CreateCustomerModal({ open, onClose, onCreateCustomer, user = null }) {
  const [form, setForm] = useState({
    name: "", pic_name: "", phone: "", city: "", address: "",
  });
  const [busy, setBusy] = useState(false);
  // UAT 24 Okt (audit UI tahap 2) — setelah "Buat Pelanggan" ditekan dengan isian belum lengkap, kekurangannya
  // ditampilkan (termasuk galat blok alamat lewat `showErrors` LocationFields — API G0), bukan tombol mati tanpa alasan.
  const [tried, setTried] = useState(false);
  const [err, setErr] = useState("");
  if (!open) return null;

  const missing = [
    !form.name.trim() && "nama toko",
    !form.pic_name.trim() && "nama PIC",
    !form.phone.trim() && "No. HP",
    (!form.city || locationIncomplete(form)) && "wilayah alamat",
    form.address.trim().length < 3 && "jalan/nomor",
  ].filter(Boolean);
  const valid = missing.length === 0;

  async function submit() {
    if (!valid) { setTried(true); return; }
    setBusy(true); setErr("");
    try {
      await onCreateCustomer(form);
      onClose();
    } catch (e) {
      setErr(apiErrorText(e, "Gagal membuat pelanggan."));
    } finally {
      setBusy(false);
    }
  }

  // UAT 24 Okt (audit UI tahap 2) — G2-01: di HP 390×820 kartu lebih tinggi dari layar sehingga judul/×
  // dan Batal/Buat terpotong. Kartu dibatasi tinggi layar; kepala & kaki tetap, isi digulir di dalam kartu.
  return (
    <div className="fixed inset-0 z-[120] flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:items-center" data-testid="create-customer-modal">
      <div className="flex max-h-[calc(100dvh-2rem)] w-full max-w-md flex-col rounded-xl bg-white shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-[#EFF0F2] px-4 py-3">
          <div className="flex items-center gap-2">
            <UserPlus size={16} className="text-[#0058CC]" />
            <h3 className="text-[14px] font-bold">Pelanggan Baru</h3>
          </div>
          <button data-testid="create-customer-close" className="icon-button" onClick={onClose} aria-label="Tutup"><X size={16} /></button>
        </div>
        <div className="grid min-h-0 flex-1 gap-2 overflow-y-auto p-4" data-testid="create-customer-body">
          <Label>Nama toko / pelanggan <Req /></Label>
          <input data-testid="new-customer-name-input" className="field" placeholder="PT / Toko ..." value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          {/* G2-22: setiap isian berlabel sendiri (placeholder bukan label). */}
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label>Nama PIC toko <Req /></Label>
              <input data-testid="new-customer-pic-input" className="field" placeholder="Nama PIC toko" value={form.pic_name} onChange={(e) => setForm({ ...form, pic_name: e.target.value })} />
            </div>
            <div className="grid gap-2">
              <Label>No. HP / WhatsApp PIC <Req /></Label>
              <input data-testid="new-customer-phone-input" className="field" inputMode="tel" placeholder="08…" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </div>
          </div>
          <Label>Alamat toko <Req /></Label>
          <div className="grid gap-2 sm:grid-cols-2">
            <LocationFields testId="new-customer-loc" compact showErrors={tried} value={form} onChange={(patch) => setForm((p) => ({ ...p, ...patch }))} />
          </div>
          <Label>Jalan, nomor, patokan <Req /></Label>
          <input data-testid="new-customer-address-input" className="field" placeholder="Jl. … No. …, dekat …" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          <p data-testid="new-customer-sales-note" className="rounded-md border border-[#CDE9D6] bg-[#F4FCF6] px-2.5 py-2 text-[10.5px] text-[#1A7A3A]">
            {user?.role === "sales"
              ? <>Sales penanggung jawab: <b>{user?.name}</b> (akun Anda) — otomatis, tak perlu dipilih.</>
              : <>Sales penanggung jawab & tim sales diatur di <b>Manajemen Pelanggan</b> (akun {user?.role ? roleLabel(user.role) : "non-sales"} tidak otomatis menjadi pemilik).</>}
          </p>
          <p data-testid="new-customer-lot-note" className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-2.5 py-2 text-[10.5px] text-[#6B6B73]">
            Segmen (untuk analitik), kebijakan lot / dye-lot &amp; tim sales diatur di <b>Manajemen Pelanggan</b>.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-t border-[#EFF0F2] px-4 py-3">
          {err && <p className="w-full text-[11px] text-[#C0392B]" data-testid="create-customer-error">{err}</p>}
          {tried && !valid && <p className="w-full text-[11px] text-[#C0392B]" data-testid="create-customer-missing">Lengkapi: {missing.join(", ")}.</p>}
          <button className="secondary-button" onClick={onClose}>Batal</button>
          <button data-testid="create-customer-button" className="primary-button" disabled={busy} aria-disabled={!valid} onClick={submit}>
            <UserPlus size={14} /> {busy ? "Menyimpan..." : "Buat Pelanggan"}
          </button>
        </div>
      </div>
    </div>
  );
}

const Label = ({ children }) => <p className="text-[10.5px] font-semibold text-[#4A4B53] -mb-1">{children}</p>;
const Req = () => <span className="text-red-500">*</span>;
