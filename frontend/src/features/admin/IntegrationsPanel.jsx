import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { Sparkles, KeyRound, CheckCircle2, AlertCircle, ShieldAlert } from "lucide-react";
import LinkCard from "../../components/LinkCard";

// FASE H5 — Panel Integrasi AI (Anthropic Claude). Keputusan 1a.
// Key TIDAK pernah ditampilkan plaintext — hanya status has_key.
// KP-T8 — wewenang = izin `integration.manage` (prop `canManage`, dihitung `can(...)` di pemanggil). Hidup/mati dan
// model pengenal gambar (KP-31) pindah ke Pusat Pengaturan (`integrations.anthropic.*`); kartu ini menampilkan nilai
// yang dipakai mesin + kunci penyedia. Peringatan bila kunci enkripsi server (`secrets_key_configured`) belum dipasang.
export default function IntegrationsPanel({ canManage = true }) {
  const [cfg, setCfg] = useState(null);
  const [secretsOk, setSecretsOk] = useState(true);
  const [loading, setLoading] = useState(true);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { load(); }, []); // eslint-disable-line
  async function load() {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/integrations`);
      setCfg(r.data?.anthropic || {}); setSecretsOk(r.data?.secrets_key_configured !== false); setApiKey("");
    } catch (e) { setErr(e.response?.data?.detail || "Gagal memuat konfigurasi."); }
    finally { setLoading(false); }
  }

  async function save({ clear = false } = {}) {
    setBusy(true); setErr(""); setMsg("");
    const payload = {};
    if (clear) payload.anthropic_clear_key = true;
    else if (apiKey.trim()) payload.anthropic_api_key = apiKey.trim();
    if (!Object.keys(payload).length) { setBusy(false); setErr("Isi API key dulu."); return; }
    try {
      const r = await axios.put(`${API}/admin/integrations`, payload);
      setCfg(r.data?.anthropic || {}); setSecretsOk(r.data?.secrets_key_configured !== false); setApiKey("");
      setMsg(clear ? "API key dihapus." : "Konfigurasi tersimpan.");
    } catch (e) { setErr(e.response?.data?.detail || "Gagal menyimpan."); }
    finally { setBusy(false); }
  }

  const hasKey = !!cfg?.has_key;
  const enabled = !!cfg?.enabled;
  const active = hasKey && enabled;

  return (
    <section className="section-card" data-testid="integrations-panel">
      <div className="section-head flex items-center !justify-start gap-2"><Sparkles size={15} className="text-[#0058CC]" /><h2 className="text-[13px] font-bold">Integrasi AI — Anthropic Claude</h2></div>
      <div className="section-body">
        {loading ? (
          <p className="text-[12px] text-[#6B6B73] py-4">Memuat…</p>
        ) : (
          <div className="grid gap-3 max-w-[560px]">
            {!secretsOk && (
              <div className="flex items-center gap-2 rounded-lg bg-kn-warning-soft px-3 py-2 text-fs-12 font-semibold text-kn-warning-text" data-testid="integrations-secrets-warning">
                <ShieldAlert size={15} /> Kunci enkripsi server belum dipasang. Rahasia yang disimpan sekarang belum terenkripsi.
              </div>
            )}
            <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-semibold ${active ? "bg-[#E7F5EC] text-[#1F7A45]" : "bg-[#FBF3E2] text-[#B7791F]"}`} data-testid="integrations-status">
              {active ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
              {active ? "AI aktif — auto-tag galeri tersedia." : hasKey ? "Key tersimpan, tetapi AI dinonaktifkan." : "AI nonaktif — belum ada API key. Galeri tetap berfungsi penuh."}
            </div>

            {err && <div className="notice-bar danger !py-1.5" data-testid="integrations-error"><span className="text-[11.5px]">{err}</span></div>}
            {msg && <div className="notice-bar success !py-1.5" data-testid="integrations-msg"><span className="text-[11.5px]">{msg}</span></div>}

            <div className="grid gap-1">
              <label className="text-[11px] font-bold uppercase text-[#6B6B73] flex items-center gap-1"><KeyRound size={12} /> API Key</label>
              <input data-testid="integrations-apikey" type="password" className="form-input" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                placeholder={hasKey ? "•••• tersimpan — isi untuk mengganti" : "Masukkan Anthropic API key (sk-ant-…)"} />
              <p className="text-[10.5px] text-[#9A9BA3]">Key disimpan aman di server & tidak pernah ditampilkan kembali.</p>
            </div>

            <p className="text-fs-12 text-kn-text-2" data-testid="integrations-model-used">Model dipakai: {cfg?.model || "—"}</p>
            <LinkCard testId="integrations-registry-link" what="Hidup/mati dan model pengenal gambar"
              where="Pengaturan › Sistem › AI & Tampilan" view="settings-cfg-system" />

            {canManage && (
              <div className="flex items-center gap-2 pt-1">
                <button data-testid="integrations-save" className="btn-primary" onClick={() => save()} disabled={busy}>{busy ? "Menyimpan…" : "Simpan Kunci"}</button>
                {hasKey && <button data-testid="integrations-clear" className="btn-secondary" onClick={() => save({ clear: true })} disabled={busy}>Hapus Key</button>}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
