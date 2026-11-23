/**
 * KartuAkrual — KM-T5 · kartu "Akrual komisi bulanan" (KA-9: dipindah dari Target & Aturan ke tab Skema & Tarif).
 *
 * Komisi otomatis satu PT pada satu bulan: status jurnal akrual dan tombol "Bukukan akrual komisi {bulan}" /
 * "Bukukan koreksi akrual komisi {bulan}" (konfirmasi menyebut nominal & PT). Sumber `GET /api/sales/incentive/gl-status`,
 * `POST /api/sales/incentive/post-gl`; tombol = izin `sales_force.post`. Akrual hanya untuk sakelar PT yang mengakru
 * komisi (`MODE_AKRU`, KA-7: termasuk "keduanya dibayar"); `pay_on_invoice` mengakui beban saat gaji diposting.
 */
import { useCallback, useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import StatusBadge from "../../components/StatusBadge";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatPeriod } from "../../utils/formatters";
import { canCurrent } from "../../config/roles";
import { bulanIni, pilihanBulan } from "./MyIncentiveCard";
import { MODE_AKRU } from "./incentiveModes";

export const TEKS_AKRUAL_SEMUA_PT = "Pilih satu PT untuk membukukan akrual komisi.";
export const TEKS_AKRUAL_TIDAK_DIPAKAI = "PT ini mengakui beban komisi saat gaji diposting, jadi akrual bulanan tidak dipakai.";
export const TEKS_AKRUAL_IZIN = "Membukukan akrual butuh akses Posting di modul Pengawasan Tim Sales & Kredit.";

/** Tombol akrual: { label, nilai, alasan } — alasan "" = boleh. */
export function rencanaAkrual(st, bulan, bolehPosting) {
  const nama = formatPeriod(bulan);
  const est = Number(st?.estimate || 0);
  const sudah = Number(st?.amount || 0);
  const koreksi = !!st?.posted;
  const nilai = koreksi ? est - sudah : est;
  let alasan = "";
  if (!bolehPosting) alasan = TEKS_AKRUAL_IZIN;
  else if (koreksi && Math.abs(nilai) < 1) alasan = `Akrual komisi ${nama} sudah dibukukan.`;
  else if (!koreksi && est < 1) alasan = `Tidak ada komisi untuk dibukukan pada ${nama}.`;
  return { label: `${koreksi ? "Bukukan koreksi akrual komisi" : "Bukukan akrual komisi"} ${nama}`, nilai, alasan };
}

export default function KartuAkrual({ canWrite, mode, pt }) {
  const [bulan, setBulan] = useState(bulanIni());
  const [st, setSt] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const aktif = canWrite && MODE_AKRU.includes(mode);
  const load = useCallback(async () => {
    if (!aktif) return;
    setState("loading");
    try { const r = await axios.get(`${API}/sales/incentive/gl-status`, { params: { period: bulan } }); setSt(r.data); setErr(""); setState("ready"); }
    catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [aktif, bulan]);
  useEffect(() => { load(); }, [load]);
  if (!canWrite) return <p className="text-fs-13 text-kn-text-2" data-testid="ins-accrual-all">{TEKS_AKRUAL_SEMUA_PT}</p>;
  if (!MODE_AKRU.includes(mode)) return <p className="text-fs-13 text-kn-text-2" data-testid="ins-accrual-na">{TEKS_AKRUAL_TIDAK_DIPAKAI}</p>;
  const rencana = rencanaAkrual(st, bulan, canCurrent("sales_force", "post"));
  const bukukan = async () => {
    const ok = await askConfirm({ title: `${rencana.label}?`,
      message: `Beban komisi ${formatCurrency(rencana.nilai)} dibukukan ke buku ${pt}: Dr Beban Insentif Penjualan / Cr Hutang Insentif Penjualan.`,
      confirmLabel: "Ya, bukukan" });
    if (!ok) return;
    setBusy(true); setMsg("");
    try { const r = await axios.post(`${API}/sales/incentive/post-gl`, null, { params: { period: bulan } }); setMsg(r.data?.message || "Akrual dibukukan."); await load(); }
    catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
    finally { setBusy(false); }
  };
  return (
    <div className="space-y-2" data-testid="ins-accrual">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-[200px]"><label className="field-label">Bulan</label>
          <KNSelect data-testid="ins-accrual-month" value={bulan} className="field" options={pilihanBulan(bulanIni())} onValueChange={(v) => v && setBulan(v)} /></div>
        {state === "ready" && (st?.posted
          ? <StatusBadge tone="success" icon="check" label="Sudah dibukukan" testId="ins-accrual-status" />
          : <StatusBadge tone="warning" icon="clock" label="Belum dibukukan" testId="ins-accrual-status" />)}
      </div>
      {state === "loading" ? (
        <p className="text-fs-13 text-kn-text-2" role="status" data-testid="ins-accrual-loading">Memeriksa akrual…</p>
      ) : state === "error" ? (
        <ErrorNotice testId="ins-accrual-error" message={`Akrual tidak bisa diperiksa. ${err}`.trim()} onRetry={load} />
      ) : (
        <>
          <p className="text-fs-13 text-kn-text" data-testid="ins-accrual-text">
            {st?.posted ? <>Sudah dibukukan <span className="whitespace-nowrap">{formatCurrency(st.amount)}</span> (jurnal {st.journal_number || "—"}). Komisi otomatis saat ini <span className="whitespace-nowrap">{formatCurrency(st.estimate)}</span>.</>
              : <>Komisi otomatis {formatPeriod(bulan)} di {pt}: <span className="whitespace-nowrap font-semibold">{formatCurrency(st?.estimate)}</span>.</>}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" data-testid="ins-accrual-post" className="primary-button btn-sm whitespace-nowrap"
              disabled={!!rencana.alasan || busy} onClick={bukukan}>{busy ? "Membukukan…" : rencana.label}</button>
            {rencana.alasan && <span className="text-fs-12 text-kn-text-2" data-testid="ins-accrual-why">{rencana.alasan}</span>}
          </div>
          {msg && <div className="notice-bar success" data-testid="ins-accrual-msg"><span className="text-fs-12">{msg}</span></div>}
        </>
      )}
    </div>
  );
}
