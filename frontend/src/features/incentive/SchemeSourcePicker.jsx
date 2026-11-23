/**
 * SchemeSourcePicker — KA-9 · bagian **1. Sumber insentif** tab Skema & Tarif (rancangan komisi per artikel §6.5).
 *
 * Tiga pilihan untuk PT aktif: Komisi otomatis · Lembar Insentif · Keduanya dibayar. Nilai yang disimpan = kunci Pusat
 * Pengaturan `hr.payroll_commission_mode` lapisan PT (`PUT /api/config/values`, alasan wajib lewat `askReason`; riwayat
 * & berlaku-mulai tetap milik Pusat Pengaturan). Pemetaan pilihan ↔ mode: `incentiveModes.js`. Mode `pay_on_invoice` /
 * `off` tampil dengan label registri dan tautan "Ubah di Pusat Pengaturan"; memilih "Keduanya" dari `pay_on_invoice`
 * menyebut perubahan cara pembukuan di dialog alasan.
 *
 * Label & hak ubah dari `GET /api/config/registry?q=hr.payroll_commission_mode` (`can_edit` = izin kunci; registri tidak
 * terbaca → pilihan terkunci). Mode sekarang dari induk (`GET /api/incentive/targets` → `commission_mode`).
 */
import { useEffect, useState } from "react";
import { AlertTriangle, Settings2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import { askReason } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { openConfig } from "../settings/config/configDeepLink";
import { butuhKonfirmasiAkru, MODE_KEDUANYA, MODE_LEMBAR, MODE_OTOMATIS, modeDariPilihan, pilihanSumber } from "./incentiveModes";

export const KUNCI_MODE = "hr.payroll_commission_mode";
export const TEKS_PERINGATAN_KEDUANYA = "Insentif dari dua sumber dibayar bersama.";
export const TEKS_UBAH_PEMBUKUAN = "Cara pembukuan berubah menjadi dicadangkan tiap bulan.";
export const TEKS_MODE_TANPA_IZIN = "Mengubah sumber insentif butuh akses pengaturan penggajian (modul SDM & Penggajian).";

const PILIHAN = [
  { key: "otomatis", label: "Komisi otomatis", sub: "Dihitung dari tarif komisi di bawah, dibayar lewat gaji." },
  { key: "lembar", label: "Lembar Insentif", sub: "Nominal diputuskan pimpinan di Lembar Insentif yang disahkan." },
  { key: "keduanya", label: "Keduanya dibayar", sub: "Komisi otomatis dan Lembar Insentif sama-sama masuk gaji." },
];
const CADANGAN_LABEL = { [MODE_OTOMATIS]: "Komisi otomatis", [MODE_LEMBAR]: "Lembar Insentif", [MODE_KEDUANYA]: "Keduanya dibayar" };

export default function SchemeSourcePicker({ entityId, pt, mode, onSaved }) {
  const [entry, setEntry] = useState(null);       // butir registri (options + can_edit); null = belum/tidak terbaca
  const [regErr, setRegErr] = useState("");       // galat selain 403 saat membaca registri (403 = tanpa izin ubah)
  const [muat, setMuat] = useState(0);
  const [pilihan, setPilihan] = useState(pilihanSumber(mode));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => { setPilihan(pilihanSumber(mode)); }, [mode]);
  useEffect(() => {
    let hidup = true;
    axios.get(`${API}/config/registry`, { params: { q: KUNCI_MODE } })
      .then((r) => { if (hidup) { setEntry((r.data?.entries || []).find((e) => e.key === KUNCI_MODE) || null); setRegErr(""); } })
      .catch((e) => {
        if (!hidup) return;
        setEntry(null);
        setRegErr(e?.response?.status === 403 ? "" : `Pilihan sumber insentif tidak bisa dimuat. ${apiErrorText(e) || ""}`.trim());
      });
    return () => { hidup = false; };
  }, [muat]);

  const label = (m) => (entry?.options || []).find((o) => o.value === m)?.label || CADANGAN_LABEL[m] || "Diatur di Pusat Pengaturan";
  const bolehUbah = !!entry?.can_edit;
  const baru = modeDariPilihan(pilihan, mode);
  const berubah = pilihan !== "lain" && baru !== mode;

  const simpan = async () => {
    const pembukuan = butuhKonfirmasiAkru(pilihan, mode);
    const reason = await askReason({
      title: `Ubah sumber insentif ${pt}?`,
      message: `Sumber insentif ${pt} menjadi "${label(baru)}", berlaku untuk gaji berikutnya.`
        + `${pilihan === "keduanya" ? ` ${TEKS_PERINGATAN_KEDUANYA}` : ""}${pembukuan ? ` ${TEKS_UBAH_PEMBUKUAN}` : ""}`,
      reasonLabel: "Alasan perubahan", confirmLabel: "Simpan sumber insentif", testId: "scheme-source-confirm",
    });
    if (reason === null) return;
    setBusy(true); setErr(""); setMsg("");
    try {
      await axios.put(`${API}/config/values`, { items: [{ key: KUNCI_MODE, value: baru, scope_type: "entity",
        scope_id: entityId, reason }] });
      setMsg(`Sumber insentif ${pt} kini: ${label(baru)}.`);
      if (onSaved) await onSaved();
    } catch (e) { setErr(apiErrorText(e) || "Sumber insentif gagal disimpan."); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-2" data-testid="scheme-source">
      <p className="flex flex-wrap items-center gap-2 text-fs-13 text-kn-text" data-testid="scheme-source-current">
        <span>Sekarang di {pt}: <b>{label(mode)}</b></span>
        {pilihanSumber(mode) === "lain" && (
          <button type="button" className="link-button text-fs-12" data-testid="scheme-source-open-config"
            onClick={() => openConfig({ key: KUNCI_MODE })}><Settings2 size={12} aria-hidden="true" /> Ubah di Pusat Pengaturan</button>
        )}
      </p>
      <fieldset className="grid grid-cols-1 gap-2 sm:grid-cols-3" disabled={!bolehUbah || busy}>
        <legend className="sr-only">Sumber insentif</legend>
        {PILIHAN.map((p) => (
          <label key={p.key} className={`flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 ${pilihan === p.key
            ? "border-kn-action bg-kn-neutral-soft" : "border-kn-divider"}`}>
            <input type="radio" name="sumber-insentif" className="mt-0.5" data-testid={`scheme-source-${p.key}`} value={p.key}
              checked={pilihan === p.key} onChange={() => setPilihan(p.key)} />
            <span className="min-w-0">
              <span className="block text-fs-13 font-semibold text-kn-text">{p.label}</span>
              <span className="block text-fs-12 text-kn-text-2">{p.sub}</span>
            </span>
          </label>
        ))}
      </fieldset>
      {pilihan === "keduanya" && (
        <p className="flex items-center gap-1.5 text-fs-12 font-semibold text-kn-warning-text" data-testid="scheme-source-warning">
          <AlertTriangle size={13} aria-hidden="true" />{TEKS_PERINGATAN_KEDUANYA}</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="scheme-source-save"
          disabled={!bolehUbah || !berubah || busy} onClick={simpan}>{busy ? "Menyimpan…" : "Simpan sumber insentif"}</button>
        <span className="text-fs-12 text-kn-text-2" data-testid="scheme-source-why">
          {!bolehUbah ? (regErr ? "" : TEKS_MODE_TANPA_IZIN)
            : pilihan === "otomatis" && baru === mode && pilihanSumber(mode) === "lain" ? `Komisi otomatis sudah berjalan: ${label(mode)}.`
              : berubah ? `Akan disimpan: ${label(baru)}.` : "Pilih sumber lain lalu simpan."}
        </span>
      </div>
      {regErr && <ErrorNotice testId="scheme-source-registry-error" message={regErr} onRetry={() => setMuat((n) => n + 1)} />}
      {msg && <div className="notice-bar success" data-testid="scheme-source-msg"><span className="text-fs-12">{msg}</span></div>}
      {err && <ErrorNotice testId="scheme-source-error" message={err} onDismiss={() => setErr("")} />}
    </div>
  );
}
