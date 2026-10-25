/**
 * LocationFields — alamat bertingkat ala e-commerce (2026-09):
 * Negara → Provinsi → Kota/Kabupaten → Kecamatan → Kode pos, semua dari registry resmi
 * (/api/wilayah). Kode pos hanya bisa dipilih dari kode pos kecamatan terpilih; mengetik
 * kode pos 5 angka di isian Kode pos mengisi provinsi/kota/kecamatan otomatis.
 *
 * value  : { country, country_code, province, province_code, city, city_code, district, district_code, postal_code }
 * onChange(patch) — patch berisi kunci di atas (gabungkan ke state form).
 *
 * UAT 24 Okt (audit UI tahap 2) — G0-08 · P-11:
 *  · Label kalimat biasa + * (wajib) seperti form induknya (`labelStyle="caps"` untuk gaya lama MAJUSCULE 10px).
 *  · SATU isian kode pos: dulu ada dua ("Isi cepat dari kode pos" + "Kode pos"). Kini isian Kode pos bisa diketik
 *    (5 angka → wilayah terisi otomatis) atau dipilih dari daftar kode pos kecamatan; tombol kecil untuk berganti.
 *  · `col-span-full` (bukan `col-span-2`): di grid satu kolom `col-span-2` membuat kolom implisit sehingga blok
 *    alamat hanya setengah lebar. Grid dalam kini 1 kolom di HP, 2 kolom mulai `sm`.
 *  · Galat kelengkapan baru tampil setelah pengguna mengubah isian di blok ini (atau induk memberi `showErrors`
 *    setelah submit) dan diletakkan di bawah isian yang kurang — dulu "Pilih kode pos." langsung merah saat form
 *    ubah dibuka, dan selalu di bawah Kecamatan.
 */
import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import axios, { API } from "../services/apiClient";
import KNSelect from "./KNSelect";

const EMPTY = { province: "", province_code: "", city: "", city_code: "", district: "", district_code: "", postal_code: "" };
const cache = {};
async function fetchCached(url) {
  if (!cache[url]) cache[url] = axios.get(url).then((r) => r.data).catch(() => { delete cache[url]; return []; });
  return cache[url];
}

export function locationSummary(v = {}) {
  return [v.district, v.city, v.province, v.postal_code].filter(Boolean).join(", ") || v.city || "";
}

export function locationIncomplete(v = {}) {
  if ((v.country_code || "ID") !== "ID") return !v.postal_code ? "Kode pos wajib diisi." : "";
  if (!v.province_code) return "Pilih provinsi.";
  if (!v.city_code) return "Pilih kota/kabupaten.";
  if (!v.postal_code) return "Pilih kode pos.";
  return "";
}

/** Isian mana yang dimaksud pesan `locationIncomplete` — supaya galat ditempel di dekat isiannya. */
function incompleteField(v = {}) {
  if ((v.country_code || "ID") !== "ID") return v.postal_code ? "" : "postal";
  if (!v.province_code) return "province";
  if (!v.city_code) return "city";
  if (!v.postal_code) return "postal";
  return "";
}

export default function LocationFields({
  value = {}, onChange, testId = "loc", required = true, compact = false,
  labelStyle = "sentence", showErrors = false,
}) {
  const [countries, setCountries] = useState([]);
  const [provinces, setProvinces] = useState([]);
  const [regencies, setRegencies] = useState([]);
  const [districts, setDistricts] = useState([]);
  const [quick, setQuick] = useState("");
  const [quickMsg, setQuickMsg] = useState("");
  const [touched, setTouched] = useState(false);
  // Mode isian kode pos: ketik (cari wilayah dari kode pos) vs pilih dari daftar kode pos kecamatan.
  const [typing, setTyping] = useState(!value.city_code);
  const cc = value.country_code || "ID";

  useEffect(() => { fetchCached(`${API}/wilayah/countries`).then(setCountries); fetchCached(`${API}/wilayah/provinces`).then(setProvinces); }, []);
  useEffect(() => { if (value.province_code) fetchCached(`${API}/wilayah/regencies?province_code=${value.province_code}`).then(setRegencies); else setRegencies([]); }, [value.province_code]);
  useEffect(() => { if (value.city_code) fetchCached(`${API}/wilayah/districts?regency_code=${value.city_code}`).then(setDistricts); else setDistricts([]); }, [value.city_code]);

  const postalOptions = useMemo(() => {
    const d = districts.find((x) => x.code === value.district_code);
    const codes = d ? d.postal_codes : [...new Set(districts.flatMap((x) => x.postal_codes))].sort();
    return codes.map((c) => ({ value: c, label: c }));
  }, [districts, value.district_code]);

  const change = (patch) => { setTouched(true); onChange(patch); };
  const setCountry = (code) => {
    const c = countries.find((x) => x.code === code);
    change({ ...EMPTY, country_code: code, country: c?.name || code });
  };
  const setProvince = (code) => change({ ...EMPTY, province_code: code, province: provinces.find((p) => p.code === code)?.name || "" });
  const setCity = (code) => { setTyping(false); change({ city_code: code, city: regencies.find((r) => r.code === code)?.name || "", district: "", district_code: "", postal_code: "" }); };
  const setDistrict = (code) => {
    const d = districts.find((x) => x.code === code);
    change({ district_code: code, district: d?.name || "", postal_code: d && d.postal_codes.length === 1 ? d.postal_codes[0] : "" });
  };

  const applyQuick = async (raw) => {
    const code = raw.replace(/\D/g, "").slice(0, 5);
    setQuick(code); setQuickMsg(""); setTouched(true);
    if (code.length !== 5) return;
    const hits = await axios.get(`${API}/wilayah/postal-code/${code}`).then((r) => r.data).catch(() => []);
    if (!hits.length) { setQuickMsg(`Kode pos ${code} tidak ditemukan.`); return; }
    const h = hits[0];
    onChange({ country_code: "ID", country: "Indonesia", province: h.province, province_code: h.province_code, city: h.city, city_code: h.city_code,
      district: hits.length === 1 ? h.district : "", district_code: hits.length === 1 ? h.district_code : "", postal_code: code });
    setQuickMsg(hits.length === 1 ? `${h.district}, ${h.city}, ${h.province}` : `${h.city}, ${h.province} — pilih kecamatan (${hits.length} kecamatan memakai kode ini).`);
    setTyping(false);
  };

  // Pesan kurang lengkap baru tampil setelah pengguna mengubah isian di blok ini, atau induk meminta (submit).
  // Submit tetap ditolak lewat `locationIncomplete` di induk.
  const typingNow = typing || !value.city_code;
  const err = required && (touched || showErrors) ? locationIncomplete(value) : "";
  const errAt = err ? incompleteField(value) : "";
  const grid = compact ? "grid gap-2 sm:grid-cols-2" : "grid gap-3 sm:grid-cols-2";
  const L = ({ children, req = required }) => (labelStyle === "caps"
    ? <label className="text-[10px] font-bold uppercase tracking-wide text-[#6B6B73]">{children}</label>
    : <label className="mb-1 block text-[11px] font-semibold text-[#4A4B53]">{children}{req && <span className="text-red-500"> *</span>}</label>);
  const Err = ({ at }) => (errAt === at
    ? <p data-testid={`${testId}-error`} className="mt-0.5 text-[11px] text-[#C0392B]">{err}</p> : null);
  const toggleCls = "text-[10.5px] font-semibold text-[#0058CC] hover:underline";

  return (
    <div data-testid={`${testId}-fields`} className="col-span-full space-y-2">
      <div className={grid}>
        <div><L>Negara</L>
          <KNSelect data-testid={`${testId}-country`} className="field" value={cc} onValueChange={setCountry}
            options={countries.map((c) => ({ value: c.code, label: c.name }))} placeholder="Negara" /></div>
        {cc !== "ID" && (
          <div><L>Kode pos</L><input data-testid={`${testId}-postal-foreign`} className="field" value={value.postal_code || ""} onChange={(e) => change({ postal_code: e.target.value })} placeholder="Kode pos" />
            <Err at="postal" /></div>
        )}
      </div>
      {cc === "ID" ? (
        <div className={grid}>
          <div><L>Provinsi</L>
            <KNSelect data-testid={`${testId}-province`} className="field" searchable value={value.province_code || ""} onValueChange={setProvince}
              options={provinces.map((p) => ({ value: p.code, label: p.name }))} placeholder="Pilih provinsi" />
            <Err at="province" /></div>
          <div><L>Kota / Kabupaten</L>
            <KNSelect data-testid={`${testId}-city`} className="field" searchable disabled={!value.province_code} value={value.city_code || ""} onValueChange={setCity}
              options={regencies.map((r) => ({ value: r.code, label: r.name }))} placeholder={value.province_code ? "Pilih kota/kabupaten" : "Pilih provinsi dahulu"} />
            <Err at="city" /></div>
          <div><L req={false}>Kecamatan</L>
            <KNSelect data-testid={`${testId}-district`} className="field" searchable disabled={!value.city_code} value={value.district_code || ""} onValueChange={setDistrict}
              options={districts.map((d) => ({ value: d.code, label: d.name }))} placeholder={value.city_code ? "Pilih kecamatan" : "Pilih kota dahulu"} /></div>
          <div>
            <div className="flex items-baseline justify-between gap-2">
              <L>Kode pos</L>
              {value.city_code && (
                <button type="button" data-testid={`${testId}-postal-mode`} className={toggleCls}
                  onClick={() => { setTyping((t) => !t); setQuickMsg(""); }}>
                  {typingNow ? "Pilih dari daftar" : "Ketik kode pos"}
                </button>
              )}
            </div>
            {typingNow ? (
              <div className="relative">
                <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
                <input data-testid={`${testId}-postal-quick`} className="field !pl-8" inputMode="numeric" aria-label="Kode pos"
                  placeholder="Ketik 5 angka — wilayah terisi otomatis" value={quick} onChange={(e) => applyQuick(e.target.value)} />
              </div>
            ) : (
              <KNSelect data-testid={`${testId}-postal`} className="field" searchable disabled={!value.city_code} value={value.postal_code || ""} onValueChange={(v) => change({ postal_code: v })}
                options={postalOptions} placeholder={value.city_code ? "Pilih kode pos" : "Pilih kota dahulu"} />
            )}
            {quickMsg && <p data-testid={`${testId}-postal-quick-msg`} className="mt-0.5 text-[10.5px] text-[#6B6B73]">{quickMsg}</p>}
            <Err at="postal" />
          </div>
        </div>
      ) : (
        <div className={grid}>
          <div><L req={false}>Provinsi / Negara bagian</L><input data-testid={`${testId}-province-foreign`} className="field" value={value.province || ""} onChange={(e) => change({ province: e.target.value })} /></div>
          <div><L req={false}>Kota</L><input data-testid={`${testId}-city-foreign`} className="field" value={value.city || ""} onChange={(e) => change({ city: e.target.value })} /></div>
        </div>
      )}
    </div>
  );
}
