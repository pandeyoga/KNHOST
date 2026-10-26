// WhatsAppSettings — panel pengaturan integrasi WhatsApp + aturan auto-kirim (admin/manager).
// Fase 4 · R2 — L-03: `div fixed inset-0 z-[70]` buatan sendiri (tanpa Esc) → `FormModal` baku (kaki Simpan
// menempel di tab Koneksi, layar penuh di HP). L-01: `TabBtn` buatan sendiri → `PageTabs` (`wa-tab-*` tetap).
// Testid lain tetap (`wa-settings-modal` = kartu pop-up, `wa-set-*`).
import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import PageTabs from "../../components/PageTabs";
import { Switch } from "@/components/ui/switch";
import { Save, Loader2, MessageCircle, Settings2, Zap } from "lucide-react";
import WhatsAppRules from "./WhatsAppRules";

export default function WhatsAppSettings({ open, onClose }) {
  const [s, setS] = useState(null);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [tab, setTab] = useState("settings");
  const [docTypes, setDocTypes] = useState([]);

  useEffect(() => {
    if (open) {
      setMsg(""); setErr(""); setToken(""); setTab("settings");
      axios.get(`${API}/deliveries/whatsapp/settings`).then((r) => setS(r.data)).catch(() => setErr("Gagal memuat pengaturan."));
      axios.get(`${API}/pdf/doc-types`).then((r) => setDocTypes(r.data || [])).catch(() => {});
    }
  }, [open]);

  const patch = (k, v) => setS((prev) => ({ ...(prev || {}), [k]: v }));

  const save = async () => {
    setBusy(true); setErr(""); setMsg("");
    try {
      const payload = {
        provider: s.provider, simulate: s.simulate, enabled: s.enabled,
        phone_number_id: s.phone_number_id, default_country_code: s.default_country_code,
        sender_label: s.sender_label,
      };
      if (token.trim()) payload.access_token = token.trim();
      const r = await axios.put(`${API}/deliveries/whatsapp/settings`, payload);
      setS(r.data); setToken(""); setMsg("Pengaturan tersimpan.");
    } catch (e) { setErr(e.response?.data?.detail || "Gagal menyimpan."); }
    finally { setBusy(false); }
  };

  if (!open) return null;

  return (
    <FormModal open onClose={onClose} size="sm" icon={MessageCircle} title="Pengaturan WhatsApp" testId="wa-settings-modal"
      busy={busy}
      footer={tab === "settings" && s ? (
        <div className="flex gap-2">
          <button type="button" className="secondary-button flex-1" onClick={onClose} disabled={busy} data-testid="wa-set-cancel">Batal</button>
          <button type="button" className="primary-button flex-1 justify-center" onClick={save} disabled={busy} data-testid="wa-set-save">
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Simpan Pengaturan
          </button>
        </div>
      ) : null}>
      <PageTabs testId="wa-tabs" ariaLabel="Pengaturan WhatsApp" value={tab} onChange={setTab}
        tabs={[
          { key: "settings", label: "Koneksi", icon: Settings2, testId: "wa-tab-settings" },
          { key: "rules", label: "Aturan Auto-Kirim", icon: Zap, testId: "wa-tab-rules" },
        ]} />
      <div>
        {tab === "rules" ? (
          <WhatsAppRules docTypes={docTypes} />
        ) : !s ? (
          <div className="flex justify-center py-8"><Loader2 size={22} className="animate-spin text-[#0058CC]" /></div>
        ) : (
          <div className="grid gap-3">
            {err && <div className="notice-bar danger !py-1.5"><span className="text-[11.5px]">{err}</span></div>}
            {msg && <div className="notice-bar success !py-1.5"><span className="text-[11.5px]">{msg}</span></div>}
            <label className="flex items-center justify-between gap-3 rounded-lg border border-[#EDEEF1] px-3 py-2">
              <span className="text-[12.5px] font-medium">Mode simulasi (tidak kirim nyata)</span>
              <Switch checked={!!s.simulate} onCheckedChange={(v) => patch("simulate", v)} data-testid="wa-set-simulate" />
            </label>
            <label className="flex items-center justify-between gap-3 rounded-lg border border-[#EDEEF1] px-3 py-2">
              <span className="text-[12.5px] font-medium">Integrasi aktif</span>
              <Switch checked={!!s.enabled} onCheckedChange={(v) => patch("enabled", v)} data-testid="wa-set-enabled" />
            </label>
            <div className="grid gap-1">
              <label className="text-[11px] font-bold uppercase tracking-[0.03em] text-[#6B6B73]">Provider</label>
              <KNSelect value={s.provider} onValueChange={(v) => patch("provider", v)}
                options={(s.available_providers || ["simulated"]).map((p) => ({ value: p, label: p === "simulated" ? "Simulasi" : "Meta WhatsApp Cloud" }))}
                className="field" data-testid="wa-set-provider" />
            </div>
            <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
              <div className="grid gap-1">
                <label className="text-[11px] font-bold uppercase tracking-[0.03em] text-[#6B6B73]">Kode Negara</label>
                <input className="form-input" value={s.default_country_code || ""} onChange={(e) => patch("default_country_code", e.target.value)} data-testid="wa-set-cc" />
              </div>
              <div className="grid gap-1">
                <label className="text-[11px] font-bold uppercase tracking-[0.03em] text-[#6B6B73]">Label Pengirim</label>
                <input className="form-input" value={s.sender_label || ""} onChange={(e) => patch("sender_label", e.target.value)} data-testid="wa-set-label" />
              </div>
            </div>
            <div className="grid gap-1">
              <label className="text-[11px] font-bold uppercase tracking-[0.03em] text-[#6B6B73]">Phone Number ID (Meta)</label>
              <input className="form-input" value={s.phone_number_id || ""} onChange={(e) => patch("phone_number_id", e.target.value)} placeholder="opsional (mode nyata)" data-testid="wa-set-pnid" />
            </div>
            <div className="grid gap-1">
              <label className="text-[11px] font-bold uppercase tracking-[0.03em] text-[#6B6B73]">Access Token {s.has_token && <span className="text-[#1F7A45]">(tersimpan)</span>}</label>
              <input className="form-input" type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder={s.has_token ? "•••• (isi untuk mengganti)" : "opsional (mode nyata)"} data-testid="wa-set-token" />
            </div>
          </div>
        )}
      </div>
    </FormModal>
  );
}
