/**
 * RateFormModal — KA-9 · pop-up tarif komisi tab Skema & Tarif (satu pop-up untuk tiga tingkat) + `BulkRateModal`
 * ("Ubah banyak" beberapa artikel sekaligus).
 *
 * Tingkat kategori / artikel / varian (rancangan komisi per artikel §6.2, §6.6): isian tarif (Rp per satuan dasar) dan
 * batas margin (%); pengali harga khusus (pita + aturan asal harga) hanya di tingkat artikel. Batas margin tarif baru
 * terisi bawaan PT (`commission.default_margin_cap_pct`, bagian 5). Ubah banyak = `POST /api/incentive-rates/bulk`.
 *
 * Keputusan R15 — **Berlaku untuk**: "PT ini" / "Semua PT". Tarif yang sudah ada di tingkat itu diubah DI TEMPAT
 * (`PATCH /api/incentive-rates/{id}`, `{data:{…}}`) dan lingkupnya ditulis. Belum ada tarif → `POST /api/incentive-rates`
 * dengan `entity_id` = PT atau `"all"`. Mode "Semua PT" di kepala aplikasi (`semuaPtSaja`) = hanya lingkup Semua PT.
 * R16 — tarif Semua PT yang terlihat dari satu PT: bawaan "PT ini" (membuat tarif khusus PT); "Semua PT" harus dipilih
 * sendiri dan memunculkan "Mengubah tarif ini berlaku untuk semua PT.". Muat pita khusus diabaikan bila sasaran/lingkup
 * sudah berganti sebelum jawabannya datang.
 */
import { useEffect, useRef, useState } from "react";
import { Layers, Percent, Plus, Trash2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "../../components/MoneyInput";
import { REASON_MIN_LENGTH } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";

export const TEKS_BERLAKU = "Tarif berlaku untuk pesanan yang dibuat sesudah disimpan; pesanan lama memakai tarif saat pesanan dibuat.";
const TINGKAT = { kategori: "kategori", artikel: "artikel", varian: "varian" };
const SUMBER = [
  { key: "special_approval", label: "Harga khusus" },
  { key: "customer", label: "Harga pelanggan" },
  { key: "special_order", label: "Pesanan khusus" },
];
const CARA = [{ value: "ikut_pita", label: "Ikut cara harga" }, { value: "pengali_tetap", label: "Pengali tetap" }];

/** "3,5" / "3.5" / 3.5 → 3.5; kosong/tidak sah → NaN. */
export const angka = (v) => (v === "" || v === null || v === undefined ? NaN : Number(String(v).replace(",", ".")));
const teksAngka = (v) => (v === null || v === undefined ? "" : String(v).replace(".", ","));

/** Galat isian tarif & batas margin ("" = sah). */
export function periksaTarif(jumlah, batas) {
  if (!(angka(jumlah) >= 0)) return "Isi tarif per satuan dasar (angka, boleh 0).";
  const b = angka(batas);
  if (!(b >= 0 && b <= 100)) return "Batas margin harus angka 0–100 (0 = tidak dibatasi).";
  return "";
}

function pitaDari(rows) {
  return (rows || []).map((r) => ({ sampai: r.sampai_pct === null || r.sampai_pct === undefined ? null : teksAngka(r.sampai_pct),
    pengali: teksAngka(r.pengali) }));
}
function sumberDari(rows) {
  const ada = Object.fromEntries((rows || []).map((r) => [r.sumber, r]));
  return Object.fromEntries(SUMBER.map((s) => [s.key, { cara: ada[s.key]?.cara || "ikut_pita", pengali: teksAngka(ada[s.key]?.pengali ?? 1) }]));
}

/** Pita & aturan asal harga khusus satu artikel (null = ikut PT). */
function PengaliKhusus({ pita, setPita, sumber, setSumber, terkunci }) {
  if (terkunci) {
    return <p className="text-fs-12 text-kn-text-2" data-testid="rate-form-special-locked">{terkunci}</p>;
  }
  const ubahPita = (i, patch) => setPita(pita.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  return (
    <div className="space-y-3 rounded-md border border-kn-divider p-3" data-testid="rate-form-special">
      <p className="text-fs-13 font-semibold text-kn-text">Pengali harga khusus artikel ini</p>
      <label className="flex items-center gap-2 text-fs-13">
        <input type="checkbox" data-testid="rate-form-bands-own" checked={!!pita}
          onChange={(e) => setPita(e.target.checked ? [{ sampai: null, pengali: "1" }] : null)} />
        Pita pengali sendiri (tidak dicentang = ikut pita PT di bagian 3)
      </label>
      {pita && (
        <div className="space-y-1.5" data-testid="rate-form-bands">
          {pita.map((r, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2 text-fs-13">
              {r.sampai === null ? <span className="w-[210px] text-kn-text-2">Selebihnya</span> : (
                <label className="flex w-[210px] items-center gap-1">Sampai
                  <input className="field w-20 text-right" inputMode="decimal" data-testid={`rate-form-band-limit-${i}`}
                    value={r.sampai} onChange={(e) => ubahPita(i, { sampai: e.target.value })} aria-label="Sampai selisih (%)" />
                  % di bawah acuan</label>)}
              <label className="flex items-center gap-1">× <input className="field w-20 text-right" inputMode="decimal"
                data-testid={`rate-form-band-factor-${i}`} value={r.pengali} onChange={(e) => ubahPita(i, { pengali: e.target.value })}
                aria-label="Pengali komisi" /></label>
              {r.sampai !== null && (
                <button type="button" className="icon-button" aria-label="Hapus pita" data-testid={`rate-form-band-remove-${i}`}
                  onClick={() => setPita(pita.filter((_, k) => k !== i))}><Trash2 size={13} className="text-kn-danger-text" /></button>)}
            </div>
          ))}
          <button type="button" className="secondary-button btn-sm" data-testid="rate-form-band-add"
            onClick={() => setPita([...pita.slice(0, -1), { sampai: "", pengali: "1" }, pita[pita.length - 1]])}>
            <Plus size={13} aria-hidden="true" /> Tambah pita</button>
        </div>
      )}
      <label className="flex items-center gap-2 text-fs-13">
        <input type="checkbox" data-testid="rate-form-sources-own" checked={!!sumber}
          onChange={(e) => setSumber(e.target.checked ? sumberDari([]) : null)} />
        Aturan harga khusus & pesanan khusus sendiri (tidak dicentang = ikut aturan PT)
      </label>
      {sumber && (
        <div className="space-y-1.5" data-testid="rate-form-sources">
          {SUMBER.map((s) => (
            <div key={s.key} className="flex flex-wrap items-center gap-2 text-fs-13">
              <span className="w-[130px]">{s.label}</span>
              <div className="w-[170px]"><KNSelect data-testid={`rate-form-source-cara-${s.key}`} className="field" value={sumber[s.key].cara}
                options={CARA} onValueChange={(v) => v && setSumber({ ...sumber, [s.key]: { ...sumber[s.key], cara: v } })} /></div>
              {sumber[s.key].cara === "pengali_tetap" && (
                <label className="flex items-center gap-1">× <input className="field w-20 text-right" inputMode="decimal"
                  data-testid={`rate-form-source-factor-${s.key}`} value={sumber[s.key].pengali} aria-label={`Pengali tetap ${s.label}`}
                  onChange={(e) => setSumber({ ...sumber, [s.key]: { ...sumber[s.key], pengali: e.target.value } })} /></label>)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * `sasaran` = { tingkat: "kategori"|"artikel"|"varian", nama, category?, template_id?, product_id?, rate (tarif yang
 * berlaku, boleh null), adaDiTingkat (tarif yang berlaku ada di tingkat ini — milik PT ini atau Semua PT) }.
 */
export const LINGKUP = [{ key: "pt", label: "PT ini" }, { key: "semua_pt", label: "Semua PT" }];
export const TEKS_LINGKUP_SEMUA = "Tarif Semua PT berlaku untuk setiap PT yang tidak punya tarif sendiri di tingkat ini.";
export const TEKS_UBAH_SEMUA = "Mengubah tarif ini berlaku untuk semua PT.";

export default function RateFormModal({ sasaran, entityId, pt, bawaanBatas, semuaPtSaja = false, onClose, onSaved }) {
  const [jumlah, setJumlah] = useState("");
  const [batas, setBatas] = useState("");
  const [lingkup, setLingkup] = useState("pt");
  const [pita, setPita] = useState(null);
  const [sumber, setSumber] = useState(null);
  const [khusus, setKhusus] = useState("");       // "" = siap; selain itu alasan isian khusus terkunci
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const muatKe = useRef(0);                       // R16 — nomor muat pita terakhir; jawaban lama diabaikan
  const artikel = sasaran?.tingkat === "artikel";
  const ada = !!(sasaran?.rate && sasaran?.adaDiTingkat);
  const lingkupAda = ada ? (sasaran.rate.asal_lingkup === "semua_pt" ? "semua_pt" : "pt") : null;

  /** Isi awal untuk lingkup `l`: tarif yang ada bila lingkupnya sama (diubah di tempat), selain itu isian baru. */
  const isiAwal = (l) => {
    const r = ada && l === lingkupAda ? sasaran.rate : null;
    setJumlah(r ? String(r.per_unit_amount ?? 0) : "");
    setBatas(r ? String(r.margin_cap_pct ?? 0) : bawaanBatas === null || bawaanBatas === undefined ? "" : String(bawaanBatas));
    setPita(null); setSumber(null); setErr(""); setKhusus("");
    const no = muatKe.current + 1;
    muatKe.current = no;
    if (artikel && r?.rate_id) {
      // Pita/aturan khusus tarif ini tidak ikut di daftar artikel — dibaca dari daftar tarif supaya tidak tertimpa.
      setKhusus("Memuat pengali khusus…");
      axios.get(`${API}/incentive-rates`, { params: { entity_id: entityId } }).then((res) => {
        if (muatKe.current !== no) return;          // sasaran/lingkup sudah berganti
        const doc = (Array.isArray(res.data) ? res.data : []).find((d) => d.id === r.rate_id);
        setPita(doc?.price_bands ? pitaDari(doc.price_bands) : null);
        setSumber(doc?.price_source_rules ? sumberDari(doc.price_source_rules) : null);
        setKhusus("");
      }).catch(() => {
        if (muatKe.current !== no) return;
        setKhusus("Pengali khusus artikel ini tidak bisa dimuat; isiannya tidak diubah saat menyimpan.");
      });
    }
  };
  // Pop-up ditutup: jawaban muat yang masih berjalan tidak boleh mengisi pop-up berikutnya.
  useEffect(() => { if (!sasaran) muatKe.current += 1; }, [sasaran]);
  useEffect(() => {
    if (!sasaran) return;
    // R16 — tarif Semua PT dilihat dari satu PT: bawaan "PT ini"; "Semua PT" harus dipilih sendiri.
    const l = semuaPtSaja ? "semua_pt" : "pt";
    setLingkup(l);
    isiAwal(l);
  }, [sasaran]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!sasaran) return null;
  const ubah = ada && lingkup === lingkupAda;     // ubah tarif yang ada di tempat
  // Lingkup boleh dipilih bila belum ada tarif di tingkat ini, atau tarif yang terlihat milik Semua PT (boleh diganti
  // tarif khusus PT ini). Tarif milik PT ini diubah di tempat saja.
  const bolehPilih = !semuaPtSaja && (!ada || lingkupAda === "semua_pt");
  const namaLingkup = (l) => (l === "semua_pt" ? "Semua PT" : `PT ini (${pt})`);
  const judul = `${ubah ? "Ubah" : "Atur"} tarif ${TINGKAT[sasaran.tingkat]} ${sasaran.nama}`;
  // Tarif yang dipakai sekarang (bila pop-up ini tidak sedang mengubahnya di tempat). R16 — dari tarif Semua PT disebut jelas.
  const r0 = sasaran.rate;
  const ikut = !r0 || ubah ? ""
    : r0.asal_lingkup === "semua_pt"
      ? `Sekarang memakai tarif Semua PT ${formatCurrency(r0.per_unit_amount)}${ada ? "" : ` (tingkat ${r0.asal_tingkat || "kategori"})`}.`
      : !ada ? `Sekarang memakai tarif ${r0.asal_tingkat || "kategori"}: ${formatCurrency(r0.per_unit_amount)}.` : "";
  const gantiLingkup = (l) => { setLingkup(l); isiAwal(l); };

  const simpan = async () => {
    const salah = periksaTarif(jumlah, batas);
    if (salah) { setErr(salah); return; }
    const isi = { per_unit_amount: angka(jumlah), margin_cap_pct: angka(batas) };
    if (artikel && !khusus) {
      isi.price_bands = pita ? pita.map((r) => ({ sampai_pct: r.sampai === null ? null : angka(r.sampai), pengali: angka(r.pengali) })) : null;
      isi.price_source_rules = sumber ? SUMBER.map((s) => ({ sumber: s.key, cara: sumber[s.key].cara,
        pengali: sumber[s.key].cara === "pengali_tetap" ? angka(sumber[s.key].pengali) : 1 })) : null;
    }
    setBusy(true); setErr("");
    try {
      if (ubah) await axios.patch(`${API}/incentive-rates/${sasaran.rate.rate_id}`, { data: isi });
      else {
        const kunci = sasaran.tingkat === "kategori" ? { category: sasaran.category }
          : sasaran.tingkat === "artikel" ? { template_id: sasaran.template_id } : { product_id: sasaran.product_id };
        await axios.post(`${API}/incentive-rates`, { entity_id: lingkup === "semua_pt" ? "all" : entityId, ...kunci, ...isi });
      }
      await onSaved(`Tarif ${TINGKAT[sasaran.tingkat]} ${sasaran.nama} tersimpan untuk ${lingkup === "semua_pt" ? "Semua PT" : pt}.`);
    } catch (e) { setErr(apiErrorText(e) || "Tarif gagal disimpan."); } finally { setBusy(false); }
  };

  return (
    <FormModal open onClose={onClose} testId="rate-form" icon={Percent} size="md" title={judul} subtitle={pt}
      onSubmit={simpan} busy={busy} error={err} submitLabel={busy ? "Menyimpan…" : "Simpan tarif"} submitTestId="rate-form-save">
      <div className="space-y-3">
        <div data-testid="rate-form-scope">
          <span className="field-label">Berlaku untuk</span>
          {bolehPilih ? (
            <div className="flex flex-wrap gap-4 pt-1" role="radiogroup" aria-label="Berlaku untuk">
              {LINGKUP.map((l) => (
                <label key={l.key} className="flex items-center gap-1.5 text-fs-13">
                  <input type="radio" name="lingkup-tarif" value={l.key} data-testid={`rate-form-scope-${l.key}`}
                    checked={lingkup === l.key} onChange={() => gantiLingkup(l.key)} />
                  {l.key === "pt" ? namaLingkup("pt") : l.label}
                  {ada && l.key === lingkupAda ? <span className="text-kn-text-2">(ubah tarif ini)</span> : null}
                </label>
              ))}
            </div>
          ) : (
            <p className="pt-1 text-fs-13 font-semibold text-kn-text" data-testid="rate-form-scope-fixed">{namaLingkup(lingkup)}</p>
          )}
          {lingkup === "semua_pt" && <p className="mt-1 text-fs-12 text-kn-warning-text" data-testid="rate-form-scope-warning">
            {ubah ? TEKS_UBAH_SEMUA : TEKS_LINGKUP_SEMUA}</p>}
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div><label className="field-label" htmlFor="rate-form-amount">Tarif (Rp per satuan dasar) <span className="req">*</span></label>
            <MoneyInput id="rate-form-amount" testId="rate-form-amount" className="field" value={jumlah} onChange={setJumlah} />
            {ikut && <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="rate-form-inherit">{ikut}</p>}</div>
          <div><label className="field-label" htmlFor="rate-form-margin">Batas margin (%) <span className="req">*</span></label>
            <input id="rate-form-margin" className="field text-right" inputMode="decimal" data-testid="rate-form-margin" value={batas}
              onChange={(e) => setBatas(e.target.value)} />
            <p className="mt-1 text-fs-12 text-kn-text-2">Komisi satu baris paling banyak persen ini dari margin barisnya. 0 = tidak dibatasi.</p></div>
        </div>
        {artikel && <PengaliKhusus pita={pita} setPita={setPita} sumber={sumber} setSumber={setSumber} terkunci={khusus} />}
        <p className="text-fs-12 text-kn-text-2">{TEKS_BERLAKU}</p>
      </div>
    </FormModal>
  );
}

/** "Ubah banyak": satu tarif untuk beberapa artikel sekaligus (buat bila belum ada, ubah bila sudah) — alasan wajib. */
export function BulkRateModal({ ids, entityId, pt, onClose, onSaved }) {
  const [jumlah, setJumlah] = useState("");
  const [batas, setBatas] = useState("");
  const [alasan, setAlasan] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const simpan = async () => {
    if (!(angka(jumlah) >= 0)) { setErr("Isi tarif per satuan dasar (angka, boleh 0)."); return; }
    if (batas !== "" && !(angka(batas) >= 0 && angka(batas) <= 100)) { setErr("Batas margin harus angka 0–100, atau kosongkan."); return; }
    if (alasan.trim().length < REASON_MIN_LENGTH) { setErr(`Tulis alasan perubahan (minimal ${REASON_MIN_LENGTH} huruf).`); return; }
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/incentive-rates/bulk`, { entity_id: entityId, template_ids: ids,
        per_unit_amount: angka(jumlah), margin_cap_pct: batas === "" ? null : angka(batas), reason: alasan.trim() });
      await onSaved(r.data || {});
    } catch (e) { setErr(apiErrorText(e) || "Tarif gagal disimpan."); } finally { setBusy(false); }
  };
  return (
    <FormModal open onClose={onClose} testId="rates-bulk-form" icon={Layers} size="md" title={`Ubah tarif ${ids.length} artikel`}
      subtitle={pt} onSubmit={simpan} busy={busy} error={err} submitLabel={busy ? "Menyimpan…" : `Simpan tarif ${ids.length} artikel`}>
      <div className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div><label className="field-label" htmlFor="rates-bulk-amount">Tarif (Rp per satuan dasar) <span className="req">*</span></label>
            <MoneyInput id="rates-bulk-amount" testId="rates-bulk-amount" className="field" value={jumlah} onChange={setJumlah} /></div>
          <div><label className="field-label" htmlFor="rates-bulk-margin">Batas margin (%)</label>
            <input id="rates-bulk-margin" className="field text-right" inputMode="decimal" data-testid="rates-bulk-margin" value={batas}
              onChange={(e) => setBatas(e.target.value)} />
            <p className="mt-1 text-fs-12 text-kn-text-2">Kosong = batas tarif yang ada tidak diubah; tarif baru memakai bawaan PT.</p></div>
        </div>
        <div><label className="field-label" htmlFor="rates-bulk-reason">Alasan perubahan <span className="req">*</span></label>
          <textarea id="rates-bulk-reason" className="field" rows={2} data-testid="rates-bulk-reason" value={alasan} onChange={(e) => setAlasan(e.target.value)}
            placeholder="Contoh: penyesuaian tarif Batik mulai Desember" /></div>
        <p className="text-fs-12 text-kn-text-2">{TEKS_BERLAKU}</p>
      </div>
    </FormModal>
  );
}
