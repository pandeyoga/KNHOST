import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { CheckCircle2, FlaskConical, KeyRound, PlugZap, ScanText, AlertTriangle } from "lucide-react";

// GRN Fase 4 — kunci OpenAI untuk baca otomatis surat jalan. Admin only; key tidak pernah ditampilkan kembali.
export default function OpenAiIntegrationPanel() {
  const [cfg, setCfg] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const load = () => axios.get(`${API}/admin/integrations`).then((r) => setCfg(r.data?.openai || {})).catch((e) => setErr(e.response?.data?.detail || "Gagal memuat konfigurasi."));
  useEffect(() => { load(); }, []);
  const act = async (fn) => {
    setBusy(true); setErr(""); setMsg("");
    try { setMsg(await fn()); setApiKey(""); } catch (e) { const d = e?.response?.data?.detail; setErr(typeof d === "string" ? d : d?.message || "Aksi gagal."); } finally { setBusy(false); load(); }
  };
  const save = () => act(() => axios.put(`${API}/admin/integrations`, { openai_api_key: apiKey.trim() }).then(() => "Kunci tersimpan — jalankan \"Uji koneksi\"."));
  const clear = () => act(() => axios.put(`${API}/admin/integrations`, { openai_clear_key: true }).then(() => "Kunci OpenAI dihapus."));
  const test = () => act(() => axios.post(`${API}/admin/integrations/openai/test`).then((r) => `Uji koneksi LULUS — ${r.data?.models_seen ?? 0} model terlihat.`));
  const has = !!cfg?.has_key, verified = !!cfg?.verified_at;
  return (
    <section className="section-card" data-testid="openai-integration-panel">
      <div className="section-head flex items-center gap-2"><ScanText size={15} className="text-[#0F766E]" /><h2 className="text-[13px] font-bold">Integrasi AI — OpenAI (Baca Otomatis Surat Jalan)</h2></div>
      <div className="section-body">
        {!cfg && !err ? <p className="py-4 text-[12px] text-[#6B6B73]">Memuat…</p> : (
          <div className="grid max-w-[560px] gap-3">
            <div data-testid="openai-status" className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-semibold ${has && verified ? "bg-[#E7F5EC] text-[#1F7A45]" : "bg-[#FBF3E2] text-[#B7791F]"}`}>
              {has && verified ? <CheckCircle2 size={15} /> : has ? <AlertTriangle size={15} /> : <FlaskConical size={15} />}
              {!has ? "BELUM DIKONFIGURASI — baca otomatis SJ tidak bisa dipakai; kedatangan tetap bisa diisi manual."
                : verified ? `KEY TERUJI — ${String(cfg.verified_at).slice(0, 16).replace("T", " ")}${cfg.source === "env" ? " (dari env OPENAI_API_KEY)" : ""}.`
                  : `KEY TERSIMPAN${cfg.source === "env" ? " (env)" : ""}, BELUM DIUJI — klik "Uji koneksi".`}
            </div>
            {err && <div className="notice-bar danger !py-1.5" data-testid="openai-error"><span className="text-[11.5px]">{err}</span></div>}
            {msg && <div className="notice-bar success !py-1.5" data-testid="openai-msg"><span className="text-[11.5px]">{msg}</span></div>}
            <div className="grid gap-1">
              <label className="flex items-center gap-1 text-[11px] font-bold uppercase text-[#6B6B73]"><KeyRound size={12} /> OpenAI API Key</label>
              <input data-testid="openai-apikey" type="password" className="form-input" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                placeholder={has ? "•••• tersimpan — isi untuk mengganti" : "sk-… dari platform.openai.com/api-keys"} />
              <p className="text-[10.5px] text-[#9A9BA3]">Foto surat jalan dikirim ke OpenAI (store=false). Aktifkan per badan usaha lewat konfigurasi <code>receiving.ocr_enabled</code>; model, anggaran bulanan & tarif diatur di grup Penerimaan.</p>
            </div>
            <div className="flex items-center gap-2 pt-1">
              <button data-testid="openai-save" className="btn-primary" onClick={save} disabled={busy || !apiKey.trim()}>{busy ? "Menyimpan…" : "Simpan Kunci"}</button>
              {has && <button data-testid="openai-test" className="btn-secondary" onClick={test} disabled={busy}><PlugZap size={13} /> Uji koneksi</button>}
              {has && cfg.source !== "env" && <button data-testid="openai-clear" className="btn-secondary" onClick={clear} disabled={busy}>Hapus Key</button>}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
