import { useEffect, useMemo, useState } from "react";
import LocationFields, { locationIncomplete } from "../../components/LocationFields";
import { namaOrang, namaUsaha } from "../../utils/text";
import MoneyInput from "@/components/MoneyInput";
import axios, { API } from "../../services/apiClient";
import { UserPlus, Edit3, Loader2 } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";
import FormSection from "../../components/FormSection";
import { CustomerSalesTeam, customerTeamError } from "./CustomerSalesTeam";
import { can, categoryOf } from "../../config/roles";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";
import { parseDecimal } from "../../utils/decimalInput";
import { PAYMENT_METHODS as METHODS, LOT_POLICY_OPTIONS, lotPolicyLabel, paymentMethodLabel } from "./crmUtils";

const LOC_KEYS = ["country", "country_code", "province", "province_code", "city", "city_code", "district", "district_code", "postal_code"];
const pickLoc = (o = {}) => Object.fromEntries(LOC_KEYS.map((k) => [k, o[k] || ""]));
const SEGMENTS = ["Retail", "Wholesale", "Distributor", "VIP"];
// PK-45 (K-28) — plafon & status blokir hanya diubah pemegang izin kredit, lewat PUT /customers/{id}/credit + alasan.
const CREDIT_STATUS = [{ value: "active", label: "Aktif" }, { value: "inactive", label: "Nonaktif" }, { value: "blocked", label: "Blokir" }];
const CREDIT_REASON_MIN_LETTERS = 5;   // K-14 — dihitung HURUF, sama dengan server (input_rules.count_letters)
const countLetters = (t) => (String(t || "").match(/\p{L}/gu) || []).length;
const toLimit = (v) => { const n = parseDecimal(v); return Number.isFinite(n) ? n : 0; };

/**
 * CustomerFormModal — SATU-SATUNYA form pelanggan (CRM-lite KN_17; fase 3 · P3 D-05).
 *
 * Keputusan pemilik D-05: tiga form pelanggan (CRM, POS "Pelanggan Baru", HP) → form ini, isian LENGKAP di semua
 * tempat (segmen, sales penanggung jawab & tim, kebijakan lot, metode bayar/termin/DP, limit kredit, NPWP, alamat
 * terstruktur). Dibangun di atas `FormModal` (layar penuh 1 kolom di HP) + `FormSection` bernomor (L-03/L-10).
 *
 * Props: `open` · `editTarget` (null = buat baru) · `currentUser` · `salesUsers` · `selectedEntity` · `onClose`
 *   · `onSaved(customer, isEdit)` · `variant` ("crm" bawaan | "pos": urutan seksi untuk kasir — Profil pembayaran
 *   sebelum Kebijakan lot, dua seksi opsional itu terlipat DENGAN ringkasan nilainya; TIDAK ada isian yang dibuang)
 *   · `testId` (bawaan "customer-form-modal"; badan `${testId}-body`, kekurangan `${testId}-missing`, galat
 *   `${testId}-error`) · `submitTestId` (bawaan "customer-form-submit").
 * Galat validasi & server tampil DI DALAM pop-up (INV-UI-03) — `onError` lama tidak dipakai lagi (dulu bilah galat
 * layar induk tertutup lapisan modal).
 */
export default function CustomerFormModal({
  open, editTarget, currentUser, salesUsers, selectedEntity, onClose, onSaved,
  variant = "crm", testId = "customer-form-modal", submitTestId = "customer-form-submit",
}) {
  const isEdit = !!editTarget;
  const role = currentUser?.role;
  const isSales = categoryOf(role) === "sales";   // PR-T4 — = pemilik otomatis di server (kategori kerja "sales")
  const isManager = !isSales;   // admin/manager/sales_admin/… — wajib memilih sales penanggung jawab
  const pos = variant === "pos";
  // PK-45 — izin dari server (bukan nama peran): kredit = plafon & status; ubah = isian lain (PATCH).
  const canCredit = can(currentUser?.permissions, "customer", "manage_credit");
  const canUpdate = can(currentUser?.permissions, "customer", "update");

  const [f, setF] = useState(blank());
  const [methods, setMethods] = useState(["tunai", "tempo"]);
  const [salesTeam, setSalesTeam] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // UAT 24 Okt (audit UI tahap 2) — setelah simpan gagal validasi, blok alamat ikut menampilkan kekurangannya
  // (`showErrors` LocationFields — API G0) dan daftar "Lengkapi: …" tampil di kaki pop-up.
  const [tried, setTried] = useState(false);
  const [creditReason, setCreditReason] = useState("");
  const [created, setCreated] = useState(null);   // pelanggan baru sudah tersimpan; simpan ulang hanya mengulang kredit

  function blank() {
    return { name: "", segment: "Retail", assigned_sales_id: "", pic_name: "", phone: "", email: "",
      city: "", address: "", npwp: "", credit_limit: "", tags: "", status: "active",
      enforce_single_dye_lot: false, lot_policy: "",
      default_method: "tempo", term_days: 30, dp_percent: 30 };
  }

  // UAT 24 Okt (audit UI tahap 2) — G2-09: form ubah kini juga memuat "Alamat toko" (alamat UTAMA pelanggan).
  const primaryAddr = useMemo(() => {
    const list = editTarget?.addresses || [];
    return list.find((a) => a.is_primary) || list[0] || null;
  }, [editTarget]);

  useEffect(() => {
    if (!open) return;
    setTried(false);
    setError("");
    setCreditReason("");
    setCreated(null);
    if (editTarget) {
      const pp = editTarget.payment_profile || {};
      setF({
        name: editTarget.name || "", segment: editTarget.segment || "Retail",
        assigned_sales_id: editTarget.assigned_sales_id || "", pic_name: editTarget.pic_name || "",
        phone: editTarget.phone || "", email: editTarget.email || "", city: editTarget.city || "", ...pickLoc(editTarget),
        address: primaryAddr?.address || "", npwp: editTarget.npwp || "",
        credit_limit: editTarget.credit_limit || "", tags: (editTarget.tags || []).join(", "),
        status: editTarget.status || "active",
        enforce_single_dye_lot: !!editTarget.enforce_single_dye_lot, lot_policy: editTarget.lot_policy || "",
        default_method: pp.default_method || "tempo", term_days: pp.term_days ?? 30, dp_percent: pp.dp_percent ?? 30,
      });
      setMethods(pp.allowed_methods || ["tunai", "tempo"]);
      setSalesTeam(Array.isArray(editTarget.sales_team) ? editTarget.sales_team : []);
    } else {
      setF(blank());
      setMethods(["tunai", "tempo"]);
      setSalesTeam([]);
    }
  }, [open, editTarget, primaryAddr]);

  const salesOptions = useMemo(() => [
    { value: "", label: "— Pilih Sales —" },
    ...(salesUsers || []).map((s) => ({ value: s.id, label: s.name })),
  ], [salesUsers]);

  // Sales yang login = otomatis penanggung jawab (tak perlu memilih dirinya sendiri).
  useEffect(() => {
    if (open && !isEdit && isSales && currentUser?.id) setF((s) => ({ ...s, assigned_sales_id: currentUser.id }));
  }, [open, isEdit, isSales, currentUser?.id]);

  const assignedSalesName = useMemo(
    () => (salesUsers || []).find((s) => s.id === f.assigned_sales_id)?.name
      || (isSales && f.assigned_sales_id === currentUser?.id ? currentUser?.name : "") || "",
    [salesUsers, f.assigned_sales_id, isSales, currentUser]
  );

  function set(k, v) { setF((s) => ({ ...s, [k]: v })); }
  function setAssignedSales(v) {
    setF((s) => ({ ...s, assigned_sales_id: v }));
    setSalesTeam([]);  // ganti PIC → reset tim (hindari PIC basi)
  }
  // G2-09 — melepas metode yang sedang jadi default memindah default ke metode yang tersisa (dulu jadi kosong).
  function toggleMethod(m) {
    const next = methods.includes(m) ? methods.filter((x) => x !== m) : [...methods, m];
    setMethods(next);
    if (!next.includes(f.default_method)) set("default_method", next[0] || "");
  }
  const usesTempo = methods.includes("tempo");
  const usesDp = methods.includes("dp");
  const addressRequired = !isEdit || !!primaryAddr;
  // PK-45 — nilai awal plafon/status (yang dipakai mesin) vs isian; perubahan oleh pemegang izin wajib beralasan.
  const initialLimit = isEdit ? toLimit(editTarget?.credit_limit) : 0;
  const initialStatus = isEdit ? (editTarget?.status || "active") : "active";
  const limitNow = toLimit(f.credit_limit);
  const limitChanged = canCredit && limitNow !== initialLimit;
  const statusChanged = canCredit && f.status !== initialStatus;
  const creditChanged = limitChanged || statusChanged;

  // Kekurangan isian WAJIB — satu daftar untuk kaki pop-up (dulu POS & CRM punya pesan berbeda).
  const missing = [
    !f.name.trim() && "nama toko",
    !f.pic_name.trim() && "nama PIC",
    !f.phone.trim() && "No. HP",
    !!locationIncomplete(pickLoc(f)) && "wilayah alamat",
    addressRequired && f.address.trim().length < 3 && "jalan/nomor",
    !isEdit && isManager && !f.assigned_sales_id && "sales penanggung jawab",
    creditChanged && countLetters(creditReason) < CREDIT_REASON_MIN_LETTERS && "alasan perubahan kredit",
  ].filter(Boolean);

  // PK-45 — kirim plafon/status lewat endpoint kredit (hanya isian yang berubah) beserta alasannya.
  async function saveCredit(customerId) {
    const body = { reason: creditReason.trim() };
    if (limitChanged) body.credit_limit = limitNow;
    if (statusChanged) body.status = f.status;
    const r = await axios.put(`${API}/customers/${customerId}/credit`, body);
    return r.data;
  }

  // Isian selain plafon/status (PK-45: keduanya tidak lagi lewat PATCH).
  async function patchCustomer(payment_profile, tags) {
    const body = { data: {
      name: f.name, segment: f.segment, pic_name: f.pic_name, phone: f.phone, email: f.email,
      ...pickLoc(f), npwp: f.npwp, tags, payment_profile,
      enforce_single_dye_lot: !!f.enforce_single_dye_lot, lot_policy: f.lot_policy || "",
      sales_team: salesTeam,
    }};
    // G2-09 — alamat & lokasi diubah → alamat UTAMA ikut diperbarui (alamat lain tidak disentuh).
    const loc = pickLoc(f);
    const addrChanged = primaryAddr && (f.address.trim() !== (primaryAddr.address || "")
      || LOC_KEYS.some((k) => (loc[k] || "") !== (primaryAddr[k] || "")));
    if (addrChanged) {
      body.data.addresses = (editTarget.addresses || []).map((a) => (a.id === primaryAddr.id
        ? { ...a, ...loc, address: f.address.trim(), city: loc.city || a.city } : a));
    }
    const r = await axios.patch(`${API}/customers/${editTarget.id}`, body);
    if (!primaryAddr && f.address.trim().length >= 3) {
      await axios.post(`${API}/customers/${editTarget.id}/addresses`, {
        label: "Alamat Utama", recipient_name: f.pic_name, phone: f.phone, city: loc.city || f.city,
        address: f.address.trim(), is_primary: true, ...loc });
    }
    return r.data;
  }

  async function submit() {
    setTried(true);
    setError("");
    if (missing.length) return;
    const tErr = customerTeamError(salesTeam);
    if (tErr) { setError(tErr); return; }
    const payment_profile = {
      allowed_methods: methods.length ? methods : ["tunai"],
      default_method: (methods.includes(f.default_method) ? f.default_method : methods[0]) || "tunai",
      term_days: usesTempo ? Number(f.term_days) || 0 : 0,
      dp_percent: usesDp ? Number(f.dp_percent) || 0 : 0, installment_count: 0, installment_interval_days: 30,
    };
    const tags = f.tags.split(",").map((t) => t.trim()).filter(Boolean);
    setBusy(true);
    try {
      if (isEdit) {
        let saved = editTarget;
        // PK-45 — pemegang izin kredit TANPA izin ubah pelanggan: hanya plafon/status yang dikirim (PATCH pasti ditolak).
        if (canUpdate || !canCredit) saved = await patchCustomer(payment_profile, tags);
        if (creditChanged) {
          try { saved = await saveCredit(editTarget.id); } catch (e) {
            setError(apiErrorText(e, "Plafon dan status kredit belum tersimpan.")); return;
          }
        }
        await onSaved?.(saved, true);
      } else {
        const body = {
          name: f.name, pic_name: f.pic_name, phone: f.phone, email: f.email,
          type: f.segment, segment: f.segment, ...pickLoc(f), address: f.address,
          // PK-45 — plafon & status pelanggan baru dikirim lewat endpoint kredit (beralasan) sesudah pelanggan terbuat.
          npwp: f.npwp, credit_limit: 0,
          assigned_sales_id: f.assigned_sales_id, tags, payment_profile,
          enforce_single_dye_lot: !!f.enforce_single_dye_lot, lot_policy: f.lot_policy || "",
          sales_team: salesTeam,
          entity_id: (selectedEntity && selectedEntity !== "all") ? selectedEntity : "",
        };
        const cust = created || (await axios.post(`${API}/customers`, body)).data;
        setCreated(cust);
        let saved = cust;
        if (creditChanged) {
          try { saved = await saveCredit(cust.id); } catch (e) {
            setError(`Pelanggan ${cust.name || ""} sudah tersimpan, tetapi plafon/status kredit belum: `
              + `${apiErrorText(e, "coba simpan lagi.")}`);
            return;
          }
        }
        await onSaved?.(saved, false);
      }
    } catch (e) {
      setError(apiErrorText(e, "Gagal menyimpan pelanggan."));
    } finally { setBusy(false); }
  }

  if (!open) return null;

  const methodSummary = `${methods.map(paymentMethodLabel).join(", ") || "—"} · bawaan ${paymentMethodLabel(f.default_method)}`
    + `${usesTempo ? ` · tempo ${f.term_days || 0} hari` : ""}${usesDp ? ` · DP ${f.dp_percent || 0}%` : ""}`;
  const lotSummary = `${lotPolicyLabel(f.lot_policy)}${f.enforce_single_dye_lot ? " · paksa 1 dye lot" : ""}`;

  const lotSection = (n) => (
    <FormSection key="lot" number={n} title="Kebijakan lot / dye lot" testId="customer-section-lot"
      collapsible defaultOpen={!pos} summary={lotSummary}>
      <div className="grid gap-2">
        <label data-testid="customer-enforce-dyelot" className="flex items-start gap-2 text-[11.5px] text-[#3C3C43] cursor-pointer">
          <input type="checkbox" className="mt-0.5" checked={f.enforce_single_dye_lot} onChange={(e) => set("enforce_single_dye_lot", e.target.checked)} />
          <span>Paksa <b>1 dye lot</b> saat alokasi (hindari belang warna antar roll)</span>
        </label>
        <Field label="Kebijakan lot">
          <KNSelect data-testid="customer-lot-policy" className="field w-full" value={f.lot_policy} onValueChange={(v) => set("lot_policy", v)}
            options={LOT_POLICY_OPTIONS} />
        </Field>
      </div>
    </FormSection>
  );

  const paySection = (n) => (
    <FormSection key="pay" number={n} title="Profil pembayaran" testId="customer-section-pay"
      collapsible defaultOpen={!pos} summary={methodSummary}>
      <div className="mb-2 flex flex-wrap gap-x-3 gap-y-2">
        {METHODS.map((m) => (
          <label key={m.key} className="flex items-center gap-1.5 text-[11.5px] cursor-pointer" data-testid={`customer-method-${m.key}`}>
            <input type="checkbox" checked={methods.includes(m.key)} onChange={() => toggleMethod(m.key)} />
            {m.label}
          </label>
        ))}
      </div>
      {/* G2-09 — Termin hanya bila Tempo dicentang, DP hanya bila DP + Sisa dicentang. */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Field label="Metode default">
          <KNSelect value={f.default_method} onValueChange={(v) => set("default_method", v)} className="field"
            data-testid="customer-default-method" placeholder="Centang minimal satu metode"
            options={METHODS.filter((m) => methods.includes(m.key)).map((m) => ({ value: m.key, label: m.label }))} />
        </Field>
        {usesTempo && (
          <Field label="Termin tempo (hari)">
            <input type="number" min={0} data-testid="customer-term-days" value={f.term_days} onChange={(e) => set("term_days", e.target.value)} className="field" />
          </Field>
        )}
        {usesDp && (
          <Field label="DP (%)">
            <input type="number" min={0} max={100} data-testid="customer-dp-percent" value={f.dp_percent} onChange={(e) => set("dp_percent", e.target.value)} className="field" />
          </Field>
        )}
      </div>
    </FormSection>
  );

  const submitLabel = isEdit ? "Simpan Perubahan" : "Buat Pelanggan";
  return (
    <FormModal open onClose={onClose} size="md" testId={testId} busy={busy} error={error}
      icon={isEdit ? Edit3 : UserPlus} title={isEdit ? "Ubah Pelanggan" : "Pelanggan Baru"}
      subtitle={isEdit ? "" : "Data lengkap sama dengan Manajemen Pelanggan — bisa langsung dipakai di pesanan."}
      onSubmit={submit}
      footer={(
        <div className="flex flex-wrap items-center justify-end gap-2">
          {tried && missing.length > 0 && (
            <p className="w-full text-[11px] font-semibold text-[#C0392B]" data-testid={`${testId}-missing`}>
              Lengkapi: {missing.join(", ")}.
            </p>
          )}
          <button type="button" className="secondary-button" disabled={busy} data-testid={`${testId}-cancel`}
            onClick={() => !busy && onClose?.()}>Batal</button>
          <button type="submit" className="primary-button" disabled={busy} data-testid={submitTestId}>
            {busy ? <Loader2 size={13} className="animate-spin" /> : (isEdit ? <Edit3 size={13} /> : <UserPlus size={13} />)}
            {busy ? "Menyimpan..." : submitLabel}
          </button>
        </div>
      )}>
      {/* ── 1. Data toko / pelanggan ── */}
      <FormSection number={1} title="Data toko / pelanggan" testId="customer-section-store" required>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Nama toko / pelanggan" req>
            <input data-testid="customer-name" value={f.name} onChange={(e) => set("name", e.target.value)} onBlur={(e) => set("name", namaUsaha(e.target.value))} className="field" placeholder="PT / Toko ..." />
          </Field>
          <Field label="Segmen" hint="Klasifikasi untuk laporan & analitik penjualan (Retail · Wholesale · Distributor · VIP). Tidak mengubah harga.">
            <KNSelect value={f.segment} onValueChange={(v) => set("segment", v)} className="field"
              data-testid="customer-segment" options={SEGMENTS.map((s) => ({ value: s, label: s }))} />
          </Field>
          <LocationFields testId="customer-loc" showErrors={tried} value={pickLoc(f)} onChange={(patch) => setF((p) => ({ ...p, ...patch }))} />
          <Field label="Alamat toko" req={addressRequired} hint={isEdit ? "Alamat utama pelanggan (alamat kirim lain tidak berubah)." : "Jalan, nomor, RT/RW, patokan."}>
            <input data-testid="customer-address" value={f.address} onChange={(e) => set("address", e.target.value)} className="field" placeholder="Jalan, nomor, RT/RW, patokan" />
          </Field>
          <Field label="Email toko" optional>
            <input data-testid="customer-email" value={f.email} onChange={(e) => set("email", e.target.value)} className="field" placeholder="email@..." />
          </Field>
          <Field label="NPWP" optional>
            <input data-testid="customer-npwp" value={f.npwp} onChange={(e) => set("npwp", e.target.value)} className="field" placeholder="00.000.000.0-000.000" />
          </Field>
          {canCredit ? (
            <>
              <Field label="Limit kredit (Rp)" hint="0 = tanpa limit">
                <MoneyInput testId="customer-credit-limit" value={f.credit_limit} onChange={(v) => set("credit_limit", v)} className="field" placeholder="0 = tanpa limit" />
              </Field>
              <Field label="Status">
                <KNSelect value={f.status} onValueChange={(v) => set("status", v)} className="field" data-testid="customer-status"
                  options={CREDIT_STATUS} />
              </Field>
              {creditChanged && (
                <div className="sm:col-span-2">
                  <Field label="Alasan perubahan kredit" req
                    hint={`Wajib bila plafon atau status diubah — tercatat di riwayat pelanggan (minimal ${CREDIT_REASON_MIN_LETTERS} huruf).`}>
                    <input data-testid="customer-credit-reason" value={creditReason} onChange={(e) => setCreditReason(e.target.value)}
                      className="field" placeholder="mis. tinjauan triwulan, pembayaran lancar" />
                  </Field>
                </div>
              )}
              {isEdit && !canUpdate && (
                <p className="sm:col-span-2 text-fs-12 text-kn-text-2" data-testid="customer-credit-only-note">
                  Anda hanya bisa mengubah plafon dan status pelanggan; isian lain tidak ikut tersimpan.
                </p>
              )}
            </>
          ) : (
            <div className="sm:col-span-2 grid gap-1 rounded-md border border-kn-divider bg-kn-neutral-soft px-3 py-2 text-fs-12 text-kn-text">
              <p data-testid="customer-credit-limit" data-readonly="true">
                Plafon kredit: <b>{initialLimit > 0 ? formatCurrency(initialLimit) : `${formatCurrency(0)} (tanpa batas)`}</b>
              </p>
              <p data-testid="customer-status" data-readonly="true">
                Status: <b>{(CREDIT_STATUS.find((o) => o.value === initialStatus) || {}).label || initialStatus}</b>
              </p>
              <p className="text-fs-12 text-kn-text-2" data-testid="customer-credit-readonly-note">
                Plafon dan status blokir diubah oleh pemegang akses kredit.
              </p>
            </div>
          )}
          <Field label="Tag (pisah koma)" optional>
            <input data-testid="customer-tags" value={f.tags} onChange={(e) => set("tags", e.target.value)} className="field" placeholder="grosir, premium" />
          </Field>
        </div>
      </FormSection>

      {/* ── 2. PIC toko — orang yang dihubungi di pihak PELANGGAN ── */}
      <FormSection number={2} title="PIC toko (pihak pelanggan)" testId="customer-section-pic" required
        subtitle="Orang di toko/pelanggan yang dihubungi sales untuk pesanan, tagihan, dan pengiriman.">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Nama PIC toko" req>
            <input data-testid="customer-pic" value={f.pic_name} onChange={(e) => set("pic_name", e.target.value)} onBlur={(e) => set("pic_name", namaOrang(e.target.value))} className="field" placeholder="mis. Ibu Rina (pemilik / kepala toko)" />
          </Field>
          <Field label="No. HP / WhatsApp PIC toko" req>
            <input data-testid="customer-phone" value={f.phone} inputMode="tel" onChange={(e) => set("phone", e.target.value)} className="field" placeholder="08..." />
          </Field>
        </div>
      </FormSection>

      {/* ── 3. Sales penanggung jawab — orang KITA yang memegang pelanggan ── */}
      <FormSection number={3} title="Sales penanggung jawab (internal)" testId="customer-section-sales" required={!isEdit && isManager}
        subtitle="Sales KN yang memegang pelanggan ini — menentukan kepemilikan data, target, dan insentif.">
        <div className="grid gap-2">
          {isSales && !isEdit ? (
            <p className="rounded-md border border-[#CDE9D6] bg-[#F4FCF6] px-3 py-2 text-[11.5px] text-[#1A7A3A]" data-testid="customer-assigned-sales-self">
              Otomatis: <b>{currentUser?.name}</b> (akun Anda). Pelanggan ini menjadi milik Anda.
            </p>
          ) : (
            <Field label="Sales penanggung jawab" req={!isEdit}>
              <KNSelect value={f.assigned_sales_id} onValueChange={setAssignedSales}
                className="field" data-testid="customer-assigned-sales" disabled={isEdit}
                options={salesOptions} placeholder="Sales" />
              {isEdit && <p className="text-[10px] text-[#9A9BA3] mt-0.5">Ganti sales lewat tombol Pindah Sales di detail pelanggan.</p>}
            </Field>
          )}
          <CustomerSalesTeam
            salesUsers={salesUsers}
            assignedSalesId={f.assigned_sales_id}
            assignedSalesName={assignedSalesName}
            value={salesTeam}
            onChange={setSalesTeam}
          />
        </div>
      </FormSection>

      {/* ── 4–5. Kebijakan lot & profil pembayaran — urutan menurut `variant` (kasir: pembayaran lebih dulu) ── */}
      {pos ? [paySection(4), lotSection(5)] : [lotSection(4), paySection(5)]}
    </FormModal>
  );
}

function Field({ label, req, optional = false, hint, children }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">{label}{req && <span className="text-red-500"> *</span>}{optional && !req && <span className="font-normal text-[#9A9BA3]"> (opsional)</span>}</label>
      {children}
      {hint && <p className="mt-0.5 text-[10px] leading-snug text-[#9A9BA3]">{hint}</p>}
    </div>
  );
}
