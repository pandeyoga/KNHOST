/**
 * PindahSaldoModals — Kas & Bank bagian 1 (Tugas 6): dua pop-up `FormModal` alat pindah saldo (spesifikasi §5.3).
 *
 *  · `SiapkanModal` — "Siapkan pindah saldo": per rekening akun buku besar tujuan (sub-akun baru buatan sistem, atau akun
 *    bagan PT yang sudah ada dari `GET /api/gl/accounts?entity_id=`), ringkasan total & PT (N5) →
 *    `POST /api/kas-per-rekening/{entity_id}/siapkan {pilihan_akun}` (hanya rekening yang pilihannya diubah).
 *  · `SetujuiModal` — orang kedua: memuat ULANG pratinjau saat dibuka (angka terbaru), menampilkan total, akun per
 *    rekening, kas lama tanpa rekening, dan rekening berselisih + kotak centang "sudah diperiksa" (R10), lalu
 *    `POST /api/kas-per-rekening/usulan/{id}/setujui {sidik, selisih_diperiksa}` dengan sidik angka yang DILIHAT.
 *    409 "Angka berubah, muat ulang." → kalimatnya tampil di pop-up dan angka dimuat ulang (sidik baru, centang
 *    dikosongkan); 409 selisih belum dicentang → kalimatnya tampil dan kotak centang ditampilkan.
 * Galat server tampil di dalam pop-up (bilah galat layar ada di belakang lapisan pop-up).
 */
import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Landmark } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency } from "../../../utils/formatters";
import { KasTanpaRekening, TabelRekening } from "./PindahSaldoTables";
import { akunPilihan, angkaBerubah, rekeningBerselisih, selisihBelumDicentang } from "./cutoverShared";

export function SiapkanModal({ open, pv, entityId, pt, onClose, onDone }) {
  const [akun, setAkun] = useState([]);
  const [pilihan, setPilihan] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return undefined;
    let hidup = true;
    setPilihan({});
    setErr("");
    axios.get(`${API}/gl/accounts`, { params: { entity_id: entityId, active_only: true } })
      .then((r) => { if (hidup) setAkun(Array.isArray(r.data) ? r.data : []); })
      .catch(() => { if (hidup) setAkun([]); });   // tanpa daftar akun: tetap bisa memakai sub-akun buatan sistem
    return () => { hidup = false; };
  }, [open, entityId]);

  const rekening = pv?.rekening || [];
  const opsi = (r) => [
    { value: "", label: r.akun_tujuan_baru ? `Sub-akun baru ${r.akun_tujuan} (dibuat sistem)`
      : `${r.akun_tujuan}${r.akun_tujuan_nama ? ` · ${r.akun_tujuan_nama}` : ""} (akun sekarang)` },
    ...akunPilihan(akun, r, entityId).filter((a) => a.code !== r.akun_tujuan)
      .map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` })),
  ];

  async function siapkan() {
    if (busy) return;
    setBusy(true);
    setErr("");
    const pilihan_akun = Object.fromEntries(Object.entries(pilihan).filter(([, v]) => v));
    try {
      const r = await axios.post(`${API}/kas-per-rekening/${entityId}/siapkan`, { pilihan_akun });
      onDone?.(r.data);
    } catch (e) {
      setErr(apiErrorText(e, "Pindah saldo belum bisa disiapkan."));
    } finally { setBusy(false); }
  }

  return (
    <FormModal open={open} onClose={onClose} title="Siapkan pindah saldo" icon={Landmark} size="lg" testId="ps-prepare-form"
      subtitle={`Akun buku besar per rekening untuk ${pt}`} onSubmit={siapkan} submitLabel="Siapkan usulan"
      submitTestId="ps-prepare-submit" busy={busy} error={err} submitDisabled={!rekening.length}>
      <div className="grid gap-3">
        <div className="overflow-x-auto">
          <table className="data-table w-full" data-testid="ps-prepare-accounts">
            <thead><tr><th>Rekening</th><th>Akun buku besar tujuan</th><th className="text-right">Dipindah</th></tr></thead>
            <tbody>
              {rekening.map((r) => (
                <tr key={r.id}>
                  <td className="font-semibold">{r.nama}</td>
                  <td className="min-w-[240px]">
                    <KNSelect data-testid={`ps-prepare-account-${r.id}`} className="field" value={pilihan[r.id] || ""}
                      options={opsi(r)} onValueChange={(v) => setPilihan((p) => ({ ...p, [r.id]: v || "" }))} />
                  </td>
                  <td className="text-right tabular-nums">{formatCurrency(r.dipindah)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="rounded-md border border-kn-divider px-3 py-2 text-fs-13 text-kn-text" data-testid="ps-prepare-summary">
          Saldo kas <b className="tabular-nums">{formatCurrency(pv?.total_dipindah)}</b> di {pt} akan dipindah dari akun kas
          lama ke akun buku besar tiap rekening. Usulan ini baru berlaku sesudah disetujui orang lain; angkanya dihitung
          ulang saat disetujui dan jurnalnya bertanggal hari persetujuan.
        </p>
      </div>
    </FormModal>
  );
}

export function SetujuiModal({ usulan, entityId, pt, onClose, onDone }) {
  const [pv, setPv] = useState(null);
  const [muat, setMuat] = useState("memuat");
  const [centang, setCentang] = useState(false);
  const [paksaCentang, setPaksaCentang] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function muatAngka() {
    setMuat("memuat");
    try {
      const r = await axios.get(`${API}/kas-per-rekening/${entityId}/pratinjau`);
      setPv(r.data || null);
      setCentang(false);
      setMuat("siap");
      return true;
    } catch (e) {
      setPv(null);
      setMuat("galat");
      setErr(apiErrorText(e, "Angka pindah saldo belum bisa dimuat."));
      return false;
    }
  }
  useEffect(() => { muatAngka(); }, [usulan?.id, entityId]);   // eslint-disable-line react-hooks/exhaustive-deps

  const selisih = useMemo(() => rekeningBerselisih(pv), [pv]);
  const perluCentang = selisih.length > 0 || paksaCentang;

  async function setujui() {
    if (busy || !pv) return;
    setBusy(true);
    setErr("");
    const body = { sidik: pv.sidik, selisih_diperiksa: perluCentang ? centang : false };
    try {
      const r = await axios.post(`${API}/kas-per-rekening/usulan/${usulan.id}/setujui`, body);
      onDone?.(r.data);
    } catch (e) {
      const teks = apiErrorText(e, "Pindah saldo belum bisa disetujui.");
      if (angkaBerubah(teks)) {
        await muatAngka();   // angka terbaru tampil; penyetuju memeriksa lagi lalu menyetujui dengan sidik baru
      } else if (selisihBelumDicentang(teks)) {
        setPaksaCentang(true);
      }
      setErr(teks);
    } finally { setBusy(false); }
  }

  return (
    <FormModal open onClose={onClose} title={`Setujui ${usulan.label || "pindah saldo"}`} icon={CheckCircle2} size="lg"
      testId="ps-approve-form" subtitle={`Disiapkan ${usulan.disiapkan_oleh || "—"} · angka terbaru dihitung ulang sekarang`}
      onSubmit={setujui} submitLabel="Setujui pindah saldo" submitTestId="ps-approve-submit" busy={busy} error={err}
      submitDisabled={muat !== "siap" || (perluCentang && !centang)}>
      {muat === "memuat" && <p className="text-fs-13 text-kn-text-2" role="status" data-testid="ps-approve-loading">Menghitung ulang…</p>}
      {pv && muat === "siap" && (
        <div className="grid gap-3">
          <p className="rounded-md border border-kn-divider px-3 py-2 text-fs-13 text-kn-text" data-testid="ps-approve-summary">
            <b className="tabular-nums" data-testid="ps-approve-total">{formatCurrency(pv.total_dipindah)}</b> dipindah ke akun
            buku besar per rekening {pt}. Jurnalnya bertanggal hari ini; sesudah disetujui kas baru {pt} masuk akun rekening
            masing-masing dan langkah ini tidak bisa diulang.
          </p>
          <TabelRekening pv={pv} testId="ps-approve-accounts" />
          <KasTanpaRekening pv={pv} />
          {perluCentang && (
            <div className="rounded-md border border-kn-warning-soft bg-kn-warning-soft px-3 py-2" data-testid="ps-approve-diff">
              {selisih.length > 0 && (
                <ul className="mb-1 grid gap-0.5 text-fs-13">
                  {selisih.map((r) => (
                    <li key={r.id} data-testid={`ps-approve-diff-${r.id}`}>
                      Rekening <b>{r.nama}</b> berselisih <b className="tabular-nums">{formatCurrency(r.selisih)}</b> dengan
                      buku kasnya sesudah dipindah.
                    </li>
                  ))}
                </ul>
              )}
              <label className="inline-flex items-center gap-2 text-fs-13 text-kn-text">
                <input type="checkbox" className="h-4 w-4" data-testid="ps-approve-diff-check" checked={centang}
                  onChange={(e) => setCentang(e.target.checked)} />
                Selisih sudah saya periksa
              </label>
            </div>
          )}
        </div>
      )}
    </FormModal>
  );
}
