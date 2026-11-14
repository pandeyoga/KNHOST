/**
 * WhatsAppConnectionPanel — KP-T8 (KP-16): SATU koneksi WhatsApp untuk Pengingat dan Kirim Dokumen
 * (Pengaturan › Integrasi & Sistem › Integrasi & Audit).
 *
 * Sumber: GET/PUT `/admin/integrations/whatsapp`, POST `…/whatsapp/adopt` (dua koneksi lama berbeda → pilih satu,
 * alasan wajib) dan `…/whatsapp/test` (kirim uji lewat Outbox). Token hanya-tulis: server tidak pernah
 * mengirimnya, layar hanya tahu "Sudah terisi". Wewenang: izin `integration.manage` (`can`), bukan nama peran.
 */
import { useEffect, useState } from "react";
import { MessageCircle, AlertTriangle, Send, CheckCircle2, Info, KeyRound } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import apiErrorText from "../../utils/apiError";
import KNSelect from "../../components/KNSelect";
import ConfirmModal from "../../components/ConfirmModal";

const PROVIDER_OPTS = [
  { value: "simulated", label: "Simulasi (tercatat di Outbox, tidak dikirim)" },
  { value: "fonnte", label: "Fonnte (satu token, teks bebas)" },
  { value: "meta_cloud", label: "Meta WhatsApp Cloud (resmi, wajib template)" },
];
const PEMAKAI = { alerts: "Pengingat", documents: "Kirim Dokumen" };
const kosong = { provider: "simulated", token: "", phone_number_id: "", sender_label: "", default_country_code: "62", template_name: "" };

function Isian({ label, children }) {
  return (<div className="grid gap-1"><label className="text-fs-12 font-semibold text-kn-text-2">{label}</label>{children}</div>);
}

function Ringkas({ r, testId }) {
  const token = r.provider === "fonnte" ? r.has_fonnte_token : r.has_access_token;
  return (
    <p className="text-fs-12 text-kn-text" data-testid={testId}>
      {r.provider_label}{r.phone_number_id ? ` · nomor pengirim ${r.phone_number_id}` : ""}
      {r.sender_label ? ` · ${r.sender_label}` : ""} · token {token ? "ada" : "tidak ada"}
    </p>
  );
}

export default function WhatsAppConnectionPanel({ canManage = false }) {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState(kosong);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [testPhone, setTestPhone] = useState("");
  const [adoptFrom, setAdoptFrom] = useState("");

  useEffect(() => { load(); }, []); // eslint-disable-line
  function isi(d) {
    setCfg(d);
    setForm({ provider: d.provider || "simulated", token: "", phone_number_id: d.phone_number_id || "",
      sender_label: d.sender_label || "", default_country_code: d.default_country_code || "62", template_name: d.template_name || "" });
  }
  async function load() {
    setLoading(true);
    try { isi((await axios.get(`${API}/admin/integrations/whatsapp`)).data); setErr(""); }
    catch (e) { setErr(apiErrorText(e, "Gagal memuat koneksi WhatsApp.")); }
    finally { setLoading(false); }
  }
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function save() {
    setBusy(true); setErr(""); setMsg("");
    const payload = { provider: form.provider, phone_number_id: form.phone_number_id, sender_label: form.sender_label,
      default_country_code: form.default_country_code, template_name: form.template_name };
    if (form.token.trim()) payload[form.provider === "fonnte" ? "fonnte_token" : "access_token"] = form.token.trim();
    try { isi((await axios.put(`${API}/admin/integrations/whatsapp`, payload)).data); setMsg("Koneksi WhatsApp tersimpan."); }
    catch (e) { setErr(apiErrorText(e, "Gagal menyimpan koneksi WhatsApp.")); }
    finally { setBusy(false); }
  }
  async function kirimUji() {
    setBusy(true); setErr(""); setMsg("");
    try {
      const { data } = await axios.post(`${API}/admin/integrations/whatsapp/test`, { phone: testPhone });
      if (data.status === "failed") setErr(`Pengiriman gagal: ${data.error || "periksa kredensial penyedia"}`);
      else setMsg(data.status === "sent" ? `Pesan uji terkirim ke ${data.to}.` : `Mode simulasi: pesan uji dicatat di Outbox untuk ${data.to}.`);
    } catch (e) { setErr(apiErrorText(e, "Gagal mengirim pesan uji.")); }
    finally { setBusy(false); }
  }
  async function adopt(reason) {
    try {
      isi((await axios.post(`${API}/admin/integrations/whatsapp/adopt`, { from: adoptFrom, reason })).data);
      setMsg(`Koneksi ${PEMAKAI[adoptFrom]} kini dipakai Pengingat dan Kirim Dokumen.`); setAdoptFrom("");
    } catch (e) { setErr(apiErrorText(e, "Gagal memakai koneksi itu.")); setAdoptFrom(""); }
  }

  const hasToken = form.provider === "fonnte" ? cfg?.has_fonnte_token : cfg?.has_access_token;
  const dipakai = cfg?.used_by?.alerts && cfg?.used_by?.documents;

  return (
    <section className="section-card" data-testid="wa-connection-panel">
      <div className="section-head flex items-center !justify-start gap-2"><MessageCircle size={15} className="text-kn-action" /><h2 className="text-fs-13 font-bold">WhatsApp</h2></div>
      <div className="section-body">
        {loading ? (
          <p className="text-fs-12 text-kn-text-2 py-4">Memuat…</p>
        ) : (
          <div className="grid gap-3 max-w-[560px]">
            <p className={`flex items-start gap-1.5 text-fs-12 font-semibold ${dipakai ? "text-kn-success-text" : "text-kn-text-2"}`}
              data-testid="wa-connection-used-by">
              {dipakai ? <CheckCircle2 size={14} className="mt-px shrink-0" aria-hidden="true" /> : <Info size={14} className="mt-px shrink-0" aria-hidden="true" />}
              {dipakai ? "Dipakai oleh: Pengingat · Kirim dokumen"
                : "Belum dipakai — Pengingat dan Kirim dokumen masih memakai pengaturannya masing-masing sampai koneksi ini disimpan."}
            </p>
            {!canManage && <p className="text-fs-12 text-kn-text-2" data-testid="wa-connection-readonly">Hanya-baca: mengubah koneksi butuh akses mengatur integrasi.</p>}
            {cfg?.conflict && (
              <div className="rounded-lg bg-kn-warning-soft px-3 py-2 grid gap-2" data-testid="wa-connection-conflict">
                <p className="text-fs-12 font-bold text-kn-warning-text flex items-center gap-1"><AlertTriangle size={14} /> Ada dua koneksi WhatsApp berbeda</p>
                <div className="grid gap-1">
                  <p className="text-fs-12 font-semibold text-kn-text">Pengingat</p>
                  <Ringkas r={cfg.conflict.alerts} testId="wa-conflict-alerts" />
                  <p className="text-fs-12 font-semibold text-kn-text">Kirim Dokumen</p>
                  <Ringkas r={cfg.conflict.documents} testId="wa-conflict-documents" />
                </div>
                {canManage && (
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="secondary-button" data-testid="wa-adopt-alerts" onClick={() => setAdoptFrom("alerts")}>Pakai koneksi Pengingat untuk keduanya</button>
                    <button type="button" className="secondary-button" data-testid="wa-adopt-documents" onClick={() => setAdoptFrom("documents")}>Pakai koneksi Kirim Dokumen untuk keduanya</button>
                  </div>
                )}
              </div>
            )}
            {cfg?.secret_error && <div className="notice-bar danger" data-testid="wa-connection-secret-error"><span className="text-fs-12">{cfg.secret_error}</span></div>}
            {err && <div className="notice-bar danger" data-testid="wa-connection-error"><span className="text-fs-12">{err}</span></div>}
            {msg && <div className="notice-bar success" data-testid="wa-connection-msg"><span className="text-fs-12">{msg}</span></div>}

            <Isian label="Penyedia">
              <KNSelect data-testid="wa-connection-provider" value={form.provider} onValueChange={(v) => set("provider", v)}
                options={PROVIDER_OPTS} className="field" disabled={!canManage} />
            </Isian>
            {form.provider !== "simulated" && (
              <Isian label="Token">
                <input data-testid="wa-connection-token" type="password" className="form-input" value={form.token} disabled={!canManage}
                  onChange={(e) => set("token", e.target.value)} placeholder={hasToken ? "Sudah terisi — isi untuk mengganti" : "Tempel token dari penyedia"} />
                <p className="inline-flex items-center gap-1 text-fs-12 text-kn-text-2" data-testid="wa-connection-token-state">
                  {hasToken ? <CheckCircle2 size={12} className="text-kn-success-text" aria-hidden="true" /> : <KeyRound size={12} aria-hidden="true" />}
                  {hasToken ? "Sudah terisi" : "Belum terisi"} · token tidak pernah ditampilkan kembali.
                </p>
              </Isian>
            )}
            {form.provider === "meta_cloud" && (
              <Isian label="ID nomor pengirim">
                <input data-testid="wa-connection-pnid" className="form-input" value={form.phone_number_id} disabled={!canManage}
                  onChange={(e) => set("phone_number_id", e.target.value)} placeholder="mis. 104561239581234" />
              </Isian>
            )}
            <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
              <Isian label="Nama pengirim">
                <input data-testid="wa-connection-label" className="form-input" value={form.sender_label} disabled={!canManage}
                  onChange={(e) => set("sender_label", e.target.value)} placeholder="mis. Kain Nusantara" />
              </Isian>
              <Isian label="Kode negara bawaan">
                <input data-testid="wa-connection-cc" className="form-input" value={form.default_country_code} disabled={!canManage}
                  onChange={(e) => set("default_country_code", e.target.value)} placeholder="62" />
              </Isian>
            </div>
            {form.provider === "meta_cloud" && (
              <Isian label="Nama template">
                <input data-testid="wa-connection-template" className="form-input" value={form.template_name} disabled={!canManage}
                  onChange={(e) => set("template_name", e.target.value)} placeholder="mis. erp_alert_internal" />
              </Isian>
            )}
            {canManage && (
              <div className="flex flex-wrap items-end gap-2 pt-1">
                <button type="button" data-testid="wa-connection-save" className="primary-button" onClick={save} disabled={busy}>{busy ? "Menyimpan…" : "Simpan"}</button>
                <input data-testid="wa-connection-test-phone" className="form-input !w-[180px]" value={testPhone}
                  onChange={(e) => setTestPhone(e.target.value)} placeholder="Nomor uji, mis. 0812…" />
                <button type="button" data-testid="wa-connection-test" className="secondary-button" onClick={kirimUji} disabled={busy || !testPhone.trim()}><Send size={13} /> Kirim uji</button>
                {!testPhone.trim() && <span className="text-fs-12 text-kn-text-2" data-testid="wa-connection-test-hint">Isi nomor tujuan untuk kirim uji.</span>}
              </div>
            )}
          </div>
        )}
      </div>
      <ConfirmModal open={!!adoptFrom} title={`Pakai koneksi ${PEMAKAI[adoptFrom] || ""} untuk keduanya`}
        message="Pengingat dan Kirim Dokumen akan memakai satu koneksi yang sama. Konfigurasi lama yang lain tidak dipakai lagi."
        confirmLabel="Pakai koneksi ini" withReason reasonRequired reasonLabel="Alasan"
        onConfirm={(reason) => adopt(reason)} onCancel={() => setAdoptFrom("")} testId="wa-adopt-modal" />
    </section>
  );
}
