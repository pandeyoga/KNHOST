/**
 * SchemeSimulation — KA-9 · bagian **Simulasi** tab Skema & Tarif (rancangan komisi per artikel §6.6 "Simulasi").
 *
 * Pilih sales (daftar sales PT) + bulan, boleh menambah tarif percobaan (kategori atau artikel; belum disimpan) →
 * `POST /api/incentive-rates/simulate` (tidak menulis apa pun) → tabel per artikel: yard · tarif · pengali harga (+alasan)
 * · pengali capaian · komisi "Aturan sekarang", "Dengan perubahan", dan "Selisih", total ketiganya, dan catatan server
 * (`catatan`). Keputusan R18 (tinjauan akhir I3): kedua kolom sama-sama menghitung pesanan bulan itu dengan aturan HARI INI
 * (tanpa potret pesanan), jadi selisihnya murni efek perubahan; angka yang dibayar (aturan saat pesanan dibuat) tampil
 * sebagai baris info "Komisi bulan ini menurut aturan saat pesanan dibuat" (`komisi_menurut_potret`); `tanda` server
 * (strategi berjenjang, mode gaji tanpa komisi otomatis) tampil sebagai peringatan. Server
 * menolak 403 bila pengguna tidak berwenang melihat komisi sales itu — kalimatnya ditampilkan apa adanya. `roster` = daftar
 * sales PT dari induk (`GET /api/incentive/targets`); `null` = belum/tidak bisa dimuat; `rosterAlasan` = kalimat pengganti
 * pemilih sales (mis. tanpa izin Kinerja & Insentif). R16 — hasil dihapus begitu sales, bulan, atau tarif percobaan
 * berubah (tidak ada hasil basi), judul hasil "Hasil untuk {sales} · {bulan}"; daftar artikel tarif percobaan dibatasi 200
 * per muat dan ditulis bila terpotong, dengan kotak cari untuk mempersempit.
 */
import { useRef, useState } from "react";
import { Calculator, Plus, Trash2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "../../components/MoneyInput";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDecimal, formatPeriod } from "../../utils/formatters";
import { bulanIni, pilihanBulan } from "./MyIncentiveCard";

const unik = (arr, v) => (arr.some((x) => JSON.stringify(x) === JSON.stringify(v)) ? arr : [...arr, v]);
const bulat = (v) => Math.round(Number(v || 0) * 100) / 100;

/** Gabung rincian mesin "sekarang" (`a`) dan "dengan perubahan" (`b`) per artikel (atau SKU bila tanpa artikel). */
export function gabungSimulasi(sekarang, dengan) {
  const peta = new Map();
  const tambah = (rows, sisi) => (rows || []).forEach((r) => {
    const kunci = r.template_id || `sku:${r.sku || r.name || ""}`;
    const g = peta.get(kunci) || { kunci, nama: r.name || r.sku || "—", kode: r.sku || "", kategori: r.category || "", a: null, b: null };
    const s = g[sisi] || { yard: 0, tarif: [], harga: [], capaian: [], komisi: 0, dibatasi: false };
    s.yard = bulat(s.yard + Number(r.qty_base || 0));
    s.komisi = bulat(s.komisi + Number(r.commission || 0));
    s.tarif = unik(s.tarif, Number(r.rate || 0));
    s.harga = unik(s.harga, { faktor: r.price_factor, alasan: r.price_reason_label || "" });
    s.capaian = unik(s.capaian, r.achievement_factor ?? null);
    s.dibatasi = s.dibatasi || !!r.capped;
    g[sisi] = s;
    peta.set(kunci, g);
  });
  tambah(sekarang, "a");
  tambah(dengan, "b");
  return [...peta.values()].map((g) => ({ ...g, yard: (g.a || g.b).yard }))
    .sort((x, y) => x.nama.localeCompare(y.nama, "id"));
}

const kali = (v) => (v === null || v === undefined ? "—" : `×${formatDecimal(v, 2, 0)}`);
const teksTarif = (s) => (s ? s.tarif.map((t) => formatCurrency(t)).join(" / ") : "—");
const teksHarga = (s) => (s ? s.harga.map((h) => `${kali(h.faktor)}${h.alasan ? ` (${h.alasan})` : ""}`).join("; ") : "—");
const teksCapaian = (s) => (s ? s.capaian.map(kali).join(" / ") : "—");
// KA-11 — yard dua sisi: tarif percobaan bisa memberi tarif ke baris yang sekarang tanpa tarif (tidak berkomisi), jadi yard
// kolom kanan bisa lebih besar dari kolom kiri; satu angka saja menyesatkan.
const teksYard = (s) => (s ? formatDecimal(s.yard, 2, 0) : "—");
const banding = (a, b) => (a === b ? a : `${a} → ${b}`);
const teksSelisih = (n) => `${n >= 0 ? "+" : "−"}${formatCurrency(Math.abs(n))}`;
export const TEKS_INFO_POTRET = "Komisi bulan ini menurut aturan saat pesanan dibuat:";

export const BATAS_ARTIKEL = 200;
export const TEKS_ARTIKEL_TERPOTONG = `Menampilkan ${BATAS_ARTIKEL} artikel pertama — cari untuk mempersempit`;
const kunciArtikel = (c, q) => `${c}\u0001${(q || "").trim().toLowerCase()}`;

export default function SchemeSimulation({ entityId, roster, rosterAlasan = "" }) {
  const [sales, setSalesRaw] = useState("");
  const [bulan, setBulanRaw] = useState(bulanIni());
  const [draf, setDrafRaw] = useState([]);        // [{ kategori, artikel, tarif, cari }]
  const [kategori, setKategori] = useState(null); // daftar kategori (dimuat saat tarif percobaan pertama ditambah)
  const [artikel, setArtikel] = useState({});     // kategori + cari → { items: [{ value, label }], total }
  const [hasil, setHasil] = useState(null);
  const [untuk, setUntuk] = useState(null);       // { nama, bulan } hasil yang tampil
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // R16 — masukan berubah = hasil lama dibuang, dan hitungan yang masih berjalan dianggap basi (nomor hitung naik).
  const hitungKe = useRef(0);
  const basi = () => { hitungKe.current += 1; setHasil(null); setBusy(false); };
  const setSales = (v) => { setSalesRaw(v); basi(); };
  const setBulan = (v) => { setBulanRaw(v); basi(); };
  const setDraf = (f) => { setDrafRaw(f); basi(); };

  const muatArtikel = async (c, q = "") => {
    const k = kunciArtikel(c, q);
    if (!c || artikel[k]) return;
    try {
      const r = await axios.get(`${API}/incentive-rates/articles`, { params: { entity_id: entityId, category: c,
        ...(q.trim() ? { search: q.trim() } : {}), page: 1, page_size: BATAS_ARTIKEL } });
      setArtikel((a) => ({ ...a, [k]: { total: r.data?.total || 0,
        items: (r.data?.items || []).map((t) => ({ value: t.template_id, label: `${t.code} · ${t.name}` })) } }));
    } catch (e) {
      setArtikel((a) => ({ ...a, [k]: { items: [], total: 0 } }));
      setErr(`Daftar artikel ${c} tidak bisa dimuat. ${apiErrorText(e) || ""}`.trim());
    }
  };
  const tambahDraf = async () => {
    setDraf((d) => [...d, { kategori: "", artikel: "", tarif: "", cari: "", q: "" }]);
    if (kategori) return;
    try {
      const r = await axios.get(`${API}/incentive-rates/categories`, { params: { entity_id: entityId } });
      setKategori((r.data?.items || []).map((c) => ({ value: c.category, label: c.category })));
    } catch (e) { setKategori([]); setErr(apiErrorText(e) || "Daftar kategori tidak bisa dimuat."); }
  };
  const ubahDraf = (i, patch) => setDraf((d) => d.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  // Mengetik kata cari bukan perubahan tarif percobaan: hasil tidak dibuang.
  const ketikCari = (i, cari) => setDrafRaw((d) => d.map((r, k) => (k === i ? { ...r, cari } : r)));

  const hitung = async () => {
    const kurang = draf.findIndex((r) => !r.kategori || !(Number(r.tarif) >= 0) || r.tarif === "");
    if (kurang >= 0) { setErr(`Lengkapi tarif percobaan baris ${kurang + 1} (kategori dan tarif), atau hapus barisnya.`); return; }
    const no = hitungKe.current + 1;
    hitungKe.current = no;
    setBusy(true); setErr("");
    try {
      const r = await axios.post(`${API}/incentive-rates/simulate`, { entity_id: entityId, sales_id: sales, period: bulan,
        draft_rates: draf.map((d) => ({ ...(d.artikel ? { template_id: d.artikel } : { category: d.kategori }), per_unit_amount: Number(d.tarif) })) });
      if (hitungKe.current !== no) return;          // masukan berubah selagi menghitung: jawaban ini basi
      setHasil(r.data || null);
      setUntuk({ nama: (roster || []).find((x) => x.id === sales)?.name || "sales ini", bulan });
    } catch (e) {
      if (hitungKe.current !== no) return;
      setHasil(null); setErr(apiErrorText(e) || "Simulasi gagal dihitung.");
    } finally { if (hitungKe.current === no) setBusy(false); }
  };

  const rows = hasil ? gabungSimulasi(hasil.sekarang?.breakdown, hasil.dengan_perubahan?.breakdown) : [];
  const totA = Number(hasil?.sekarang?.total_incentive || 0);
  const totB = Number(hasil?.dengan_perubahan?.total_incentive || 0);
  const tanda = Array.isArray(hasil?.tanda) ? hasil.tanda : [];
  return (
    <div className="space-y-3" data-testid="scheme-sim">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-[220px]"><span className="field-label">Sales</span>
          {rosterAlasan ? <p className="text-fs-12 text-kn-text-2" data-testid="scheme-sim-sales-denied">{rosterAlasan}</p> : (
            <KNSelect data-testid="scheme-sim-sales" className="field" value={sales} placeholder="Pilih sales"
              options={(roster || []).map((x) => ({ value: x.id, label: x.name }))} onValueChange={(v) => setSales(v || "")} />)}</div>
        <div className="w-[200px]"><span className="field-label">Bulan</span>
          <KNSelect data-testid="scheme-sim-month" className="field" value={bulan} options={pilihanBulan(bulanIni())}
            onValueChange={(v) => v && setBulan(v)} /></div>
      </div>
      <div className="space-y-1.5" data-testid="scheme-sim-drafts">
        <p className="text-fs-12 font-semibold text-kn-text">Tarif percobaan (belum disimpan, boleh kosong)</p>
        {draf.map((d, i) => {
          const daftar = artikel[kunciArtikel(d.kategori, d.q)];
          const terpotong = !!daftar && daftar.total > daftar.items.length;
          return (
          <div key={i} className="space-y-1">
          <div className="flex flex-wrap items-end gap-2">
            <div className="w-[180px]"><KNSelect data-testid={`scheme-sim-draft-cat-${i}`} className="field" value={d.kategori}
              placeholder="Kategori" options={kategori || []} onValueChange={(v) => { ubahDraf(i, { kategori: v || "", artikel: "", cari: "", q: "" }); muatArtikel(v); }} /></div>
            <div className="w-[240px]"><KNSelect data-testid={`scheme-sim-draft-art-${i}`} className="field" value={d.artikel}
              placeholder="Seluruh kategori" disabled={!d.kategori}
              options={[{ value: "", label: "Seluruh kategori" }, ...(daftar?.items || [])]} onValueChange={(v) => ubahDraf(i, { artikel: v || "" })} /></div>
            <div className="w-[170px]"><MoneyInput testId={`scheme-sim-draft-rate-${i}`} className="field" value={d.tarif} showPreview={false}
              onChange={(v) => ubahDraf(i, { tarif: v })} aria-label="Tarif percobaan per satuan dasar" /></div>
            <button type="button" className="icon-button" aria-label="Hapus tarif percobaan" data-testid={`scheme-sim-draft-remove-${i}`}
              onClick={() => setDraf((x) => x.filter((_, k) => k !== i))}><Trash2 size={13} className="text-kn-danger-text" /></button>
          </div>
          {(terpotong || d.q || d.cari) && (
            <div className="flex flex-wrap items-center gap-2 pl-[188px] text-fs-12 text-kn-text-2">
              {terpotong && <span data-testid={`scheme-sim-draft-capped-${i}`}>{TEKS_ARTIKEL_TERPOTONG}</span>}
              <input className="field w-[220px]" data-testid={`scheme-sim-draft-search-${i}`} value={d.cari}
                placeholder="Cari artikel (nama atau kode), tekan Enter" aria-label="Cari artikel tarif percobaan"
                onChange={(e) => ketikCari(i, e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); ubahDraf(i, { artikel: "", q: d.cari }); muatArtikel(d.kategori, d.cari); } }} />
            </div>
          )}
          </div>
          );
        })}
        <button type="button" className="secondary-button btn-sm" data-testid="scheme-sim-draft-add" onClick={tambahDraf}>
          <Plus size={13} aria-hidden="true" />Tambah tarif percobaan</button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="scheme-sim-run" disabled={!sales || busy}
          onClick={hitung}><Calculator size={13} aria-hidden="true" />{busy ? "Menghitung…" : "Hitung simulasi"}</button>
        {!sales && !rosterAlasan && <span className="text-fs-12 text-kn-text-2" data-testid="scheme-sim-why">{!roster
          ? "Daftar sales belum bisa dimuat (lihat bagian 1)." : roster.length ? "Pilih sales dulu." : "Belum ada sales di PT ini."}</span>}
      </div>
      {err && <ErrorNotice testId="scheme-sim-error" message={err} onDismiss={() => setErr("")} />}
      {hasil && (
        <div className="space-y-2" data-testid="scheme-sim-result">
          {untuk && <p className="text-fs-13 font-semibold text-kn-text" data-testid="scheme-sim-for">{`Hasil untuk ${untuk.nama} · ${formatPeriod(untuk.bulan)}`}</p>}
          {tanda.map((t) => (
            <p key={t.kode} className="text-fs-12 font-semibold text-kn-warning-text" data-testid={`scheme-sim-flag-${t.kode}`}>{t.pesan}</p>
          ))}
          <dl className="flex flex-wrap gap-x-6 gap-y-1 text-fs-13">
            <div><dt className="text-fs-12 text-kn-text-2">Aturan sekarang</dt>
              <dd className="font-bold tabular-nums whitespace-nowrap" data-testid="scheme-sim-total-now">{formatCurrency(totA)}</dd></div>
            <div><dt className="text-fs-12 text-kn-text-2">Dengan perubahan</dt>
              <dd className="font-bold tabular-nums whitespace-nowrap" data-testid="scheme-sim-total-new">{formatCurrency(totB)}</dd></div>
            <div><dt className="text-fs-12 text-kn-text-2">Selisih</dt>
              <dd className="font-bold tabular-nums whitespace-nowrap" data-testid="scheme-sim-total-diff">{teksSelisih(totB - totA)}</dd></div>
          </dl>
          {hasil.komisi_menurut_potret !== undefined && hasil.komisi_menurut_potret !== null && (
            <p className="text-fs-12 text-kn-text-2" data-testid="scheme-sim-actual">
              {`${TEKS_INFO_POTRET} ${formatCurrency(Number(hasil.komisi_menurut_potret || 0))}`}</p>
          )}
          {!busy && rows.length === 0 ? (
            <p className="text-fs-13 text-kn-text-2" data-testid="scheme-sim-empty">Tidak ada baris komisi untuk sales ini pada bulan itu.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full" data-testid="scheme-sim-table">
                <thead><tr><th>Artikel</th><th className="text-right">Yard / satuan dasar</th><th className="text-right">Tarif</th>
                  <th>Pengali harga</th><th className="text-right">Pengali capaian</th><th className="text-right">Aturan sekarang</th>
                  <th className="text-right">Dengan perubahan</th><th className="text-right">Selisih</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.kunci} data-testid={`scheme-sim-row-${r.kunci}`}>
                      <td className="min-w-[150px] break-words"><span className="block font-semibold">{r.nama}</span>
                        <span className="block font-mono text-fs-12 text-kn-text-2">{r.kode}</span></td>
                      <td className="whitespace-nowrap text-right tabular-nums" data-testid={`scheme-sim-yard-${r.kunci}`}>{banding(teksYard(r.a), teksYard(r.b))}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{banding(teksTarif(r.a), teksTarif(r.b))}</td>
                      <td className="min-w-[180px] text-fs-12">{banding(teksHarga(r.a), teksHarga(r.b))}</td>
                      <td className="text-right tabular-nums">{banding(teksCapaian(r.a), teksCapaian(r.b))}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{r.a ? formatCurrency(r.a.komisi) : "—"}
                        {r.a?.dibatasi && <span className="block text-fs-12 text-kn-text-2">dibatasi batas margin</span>}</td>
                      <td className="whitespace-nowrap text-right font-semibold tabular-nums">{r.b ? formatCurrency(r.b.komisi) : "—"}
                        {r.b?.dibatasi && <span className="block text-fs-12 font-normal text-kn-text-2">dibatasi batas margin</span>}</td>
                      <td className="whitespace-nowrap text-right tabular-nums" data-testid={`scheme-sim-diff-${r.kunci}`}>
                        {teksSelisih(Number(r.b?.komisi || 0) - Number(r.a?.komisi || 0))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {hasil.catatan && <p className="text-fs-12 text-kn-text-2" data-testid="scheme-sim-note">{hasil.catatan}</p>}
        </div>
      )}
    </div>
  );
}
