/**
 * PWA untuk aplikasi HP sales / Admin Sales:
 *  - MobileInstallCard : pasang aplikasi ke layar utama (Android: prompt asli; iOS: panduan Bagikan →
 *                        Tambah ke Layar Utama). Disembunyikan bila sudah berjalan sebagai aplikasi.
 *  - MobilePushCard    : aktifkan notifikasi HP (Web Push). Izin diminta HANYA setelah pengguna
 *                        mengetuk tombol + penjelasan manfaat; status ditolak → panduan membuka
 *                        pengaturan situs (web tidak bisa membuka pengaturan langsung).
 *  - syncPushSubscription / dropPushSubscription : sinkron langganan dengan akun yang login.
 */
import { useEffect, useState } from "react";
import { BellRing, BellOff, Download, Share, PlusSquare, CheckCircle2, Send, Smartphone } from "lucide-react";
import axios, { API } from "../../../services/apiClient";

const ua = () => (typeof navigator !== "undefined" ? navigator.userAgent || "" : "");
export const isIOS = () => /iphone|ipad|ipod/i.test(ua()) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
export const isStandalone = () => window.matchMedia?.("(display-mode: standalone)")?.matches || window.navigator.standalone === true;
export const pushSupported = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

function b64ToUint8(b64) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function currentSubscription() {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

/** Pastikan langganan perangkat ini tercatat untuk akun yang sedang login (tanpa meminta izin). */
export async function syncPushSubscription() {
  try {
    if (!pushSupported() || Notification.permission !== "granted") return false;
    const sub = await currentSubscription();
    if (!sub) return false;
    await axios.post(`${API}/push/subscribe`, { ...sub.toJSON(), device_label: deviceLabel() });
    return true;
  } catch { return false; }
}

/** Saat keluar: lepas perangkat dari akun ini supaya HP bersama tidak menerima pesan orang lain. */
export async function dropPushSubscription() {
  try {
    const sub = await currentSubscription();
    if (sub) await axios.post(`${API}/push/unsubscribe`, { endpoint: sub.endpoint });
  } catch { /* sesi mungkin sudah habis */ }
}

function deviceLabel() {
  const u = ua();
  if (/android/i.test(u)) return "Android";
  if (isIOS()) return "iPhone/iPad";
  return "Browser";
}

export function MobileInstallCard() {
  const [prompt, setPrompt] = useState(() => window.__knInstallPrompt || null);
  const [installed, setInstalled] = useState(isStandalone());
  const [showIos, setShowIos] = useState(false);
  useEffect(() => {
    const onPrompt = () => setPrompt(window.__knInstallPrompt || null);
    const onInstalled = () => setInstalled(true);
    window.addEventListener("kn:install-available", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => { window.removeEventListener("kn:install-available", onPrompt); window.removeEventListener("appinstalled", onInstalled); };
  }, []);
  if (installed) {
    return (
      <div className="m-card flex items-center gap-3 p-3" data-testid="m-pwa-installed">
        <CheckCircle2 size={18} className="text-[#1B7F4B]" />
        <p className="text-[12px] text-[#3C3C43]">Berjalan sebagai aplikasi terpasang.</p>
      </div>
    );
  }
  const install = async () => {
    if (prompt) {
      prompt.prompt();
      const choice = await prompt.userChoice.catch(() => null);
      if (choice?.outcome === "accepted") setInstalled(true);
      window.__knInstallPrompt = null; setPrompt(null);
      return;
    }
    setShowIos((v) => !v);
  };
  return (
    <div className="m-card p-3" data-testid="m-pwa-install">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: "linear-gradient(135deg,#0058CC,#6B219A)" }}><Smartphone size={18} color="#fff" /></span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-bold">Pasang aplikasi di HP</p>
          <p className="text-[11px] m-muted">Buka dari layar utama, layar penuh, tetap bisa melihat data terakhir saat sinyal hilang.</p>
        </div>
      </div>
      <button className="primary-button mt-2.5 flex w-full items-center justify-center gap-2 py-2.5" onClick={install} data-testid="m-pwa-install-btn">
        <Download size={15} /> {prompt ? "Pasang sekarang" : "Cara memasang"}
      </button>
      {showIos && !prompt && (
        <ol className="mt-2 space-y-1.5 rounded-xl bg-[#F7F8FA] p-2.5 text-[11.5px] text-[#3C3C43]" data-testid="m-pwa-install-steps">
          {isIOS() ? (
            <>
              <li className="flex items-center gap-1.5">1. Buka halaman ini di <b>Safari</b>.</li>
              <li className="flex items-center gap-1.5">2. Ketuk <Share size={13} /> <b>Bagikan</b> di bawah layar.</li>
              <li className="flex items-center gap-1.5">3. Pilih <PlusSquare size={13} /> <b>Tambah ke Layar Utama</b> → <b>Tambah</b>.</li>
            </>
          ) : (
            <>
              <li>1. Buka menu <b>⋮</b> di Chrome (kanan atas).</li>
              <li>2. Pilih <b>Instal aplikasi</b> / <b>Tambahkan ke layar utama</b>.</li>
            </>
          )}
        </ol>
      )}
    </div>
  );
}

export function MobilePushCard() {
  const supported = pushSupported();
  const [perm, setPerm] = useState(supported ? Notification.permission : "unsupported");
  const [subscribed, setSubscribed] = useState(false);
  const [explain, setExplain] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [help, setHelp] = useState(false);
  const iosNeedsInstall = isIOS() && !isStandalone();

  useEffect(() => {
    if (!supported) return;
    currentSubscription().then((s) => { setSubscribed(!!s); if (s && Notification.permission === "granted") syncPushSubscription(); });
  }, [supported]);

  const enable = async () => {
    setBusy(true); setMsg(null);
    try {
      const p = Notification.permission === "granted" ? "granted" : await Notification.requestPermission();
      setPerm(p);
      if (p !== "granted") { setMsg({ ok: false, text: p === "denied" ? "Izin notifikasi ditolak. Aktifkan dari pengaturan situs untuk menerima pemberitahuan." : "Izin belum diberikan." }); return; }
      const { data } = await axios.get(`${API}/push/public-key`);
      if (!data?.public_key) throw new Error("Server belum siap mengirim notifikasi.");
      const reg = await navigator.serviceWorker.ready;
      let sub = await reg.pushManager.getSubscription();
      if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8(data.public_key) });
      await axios.post(`${API}/push/subscribe`, { ...sub.toJSON(), device_label: deviceLabel() });
      setSubscribed(true); setExplain(false);
      setMsg({ ok: true, text: "Notifikasi HP aktif di perangkat ini." });
    } catch (e) {
      setMsg({ ok: false, text: e?.response?.data?.detail || e?.message || "Gagal mengaktifkan notifikasi." });
    } finally { setBusy(false); }
  };
  const disable = async () => {
    setBusy(true); setMsg(null);
    try {
      const sub = await currentSubscription();
      if (sub) { await axios.post(`${API}/push/unsubscribe`, { endpoint: sub.endpoint }).catch(() => {}); await sub.unsubscribe(); }
      setSubscribed(false); setMsg({ ok: true, text: "Notifikasi HP dimatikan untuk perangkat ini." });
    } finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true); setMsg(null);
    try { const { data } = await axios.post(`${API}/push/test`); setMsg({ ok: data.ok, text: data.ok ? "Notifikasi uji dikirim — cek bilah notifikasi HP." : "Belum terkirim — coba matikan lalu aktifkan lagi." }); }
    catch (e) { setMsg({ ok: false, text: e?.response?.data?.detail || "Gagal mengirim uji." }); } finally { setBusy(false); }
  };

  const active = supported && perm === "granted" && subscribed;
  return (
    <div className="m-card p-3" data-testid="m-push-card">
      <div className="flex items-center gap-3">
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${active ? "bg-[#E6F6EC]" : "bg-[#EAF2FF]"}`}>
          {active ? <BellRing size={18} className="text-[#1B7F4B]" /> : <BellOff size={18} className="text-[#0058CC]" />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-bold">Notifikasi HP</p>
          <p className="text-[11px] m-muted" data-testid="m-push-status">
            {!supported ? "Browser ini belum mendukung notifikasi push." : iosNeedsInstall && !active ? "Di iPhone: pasang aplikasi ke layar utama dulu (iOS 16.4+)." :
              active ? "Aktif — pesanan, persetujuan & giliran Anda muncul walau aplikasi ditutup." : perm === "denied" ? "Diblokir di pengaturan browser." : "Belum aktif di perangkat ini."}
          </p>
        </div>
      </div>
      {supported && !active && perm !== "denied" && !iosNeedsInstall && !explain && (
        <button className="primary-button mt-2.5 w-full py-2.5" onClick={() => setExplain(true)} data-testid="m-push-enable">Aktifkan notifikasi</button>
      )}
      {explain && (
        <div className="mt-2.5 rounded-xl border border-[#CBDFFF] bg-[#F2F7FF] p-2.5" data-testid="m-push-explain">
          <p className="text-[11.5px] text-[#31465F]">Anda akan diberi tahu saat pesanan perlu ditindak, harga khusus diputus, permintaan internal diproses, atau ada tagihan jatuh tempo — tanpa harus membuka aplikasi. Setelah ini browser akan meminta izin.</p>
          <div className="mt-2 flex gap-2">
            <button className="secondary-button flex-1 py-2 text-[12px]" onClick={() => setExplain(false)} data-testid="m-push-explain-later">Nanti</button>
            <button className="primary-button flex-1 py-2 text-[12px]" disabled={busy} onClick={enable} data-testid="m-push-explain-continue">{busy ? "Memproses…" : "Lanjutkan"}</button>
          </div>
        </div>
      )}
      {supported && perm === "denied" && (
        <div className="mt-2">
          <button className="secondary-button w-full py-2.5 text-[12px]" onClick={() => setHelp((v) => !v)} data-testid="m-push-open-settings">Cara membuka pengaturan notifikasi</button>
          {help && (
            <ol className="mt-2 space-y-1 rounded-xl bg-[#F7F8FA] p-2.5 text-[11.5px] text-[#3C3C43]" data-testid="m-push-settings-steps">
              {isIOS() ? (<><li>1. Buka <b>Pengaturan</b> iPhone → <b>Notifikasi</b>.</li><li>2. Pilih <b>Kain Nusantara</b> → aktifkan <b>Izinkan Notifikasi</b>.</li></>)
                : (<><li>1. Ketuk ikon gembok / ⓘ di sebelah alamat situs.</li><li>2. Pilih <b>Izin</b> / <b>Setelan situs</b> → <b>Notifikasi</b> → <b>Izinkan</b>.</li><li>3. Kembali ke sini lalu ketuk <b>Aktifkan notifikasi</b>.</li></>)}
            </ol>
          )}
          <button className="mt-2 w-full py-1.5 text-[12px] font-semibold text-[#0058CC]" onClick={() => setPerm(Notification.permission)} data-testid="m-push-recheck">Sudah diizinkan? Periksa lagi</button>
        </div>
      )}
      {active && (
        <div className="mt-2.5 grid grid-cols-2 gap-2">
          <button className="secondary-button flex items-center justify-center gap-1 py-2 text-[12px]" disabled={busy} onClick={test} data-testid="m-push-test"><Send size={13} /> Kirim uji</button>
          <button className="secondary-button py-2 text-[12px]" disabled={busy} onClick={disable} data-testid="m-push-disable">Matikan</button>
        </div>
      )}
      {msg && <div className={`notice-bar ${msg.ok ? "success" : "danger"} mt-2 text-xs`} data-testid="m-push-msg">{msg.text}</div>}
    </div>
  );
}
