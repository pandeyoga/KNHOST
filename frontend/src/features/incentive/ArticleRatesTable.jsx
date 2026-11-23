/**
 * ArticleRatesTable — KA-9 · bagian **2. Tarif komisi** tab Skema & Tarif: pohon tiga tingkat Kategori → Artikel →
 * Varian (pemilik 23 Nov: "user baru bisa memutuskan category dulu saja"; rancangan komisi per artikel §6.2, §6.6).
 *
 * Tingkat atas = kategori (`GET /api/incentive-rates/categories`): tarif kategori + "n artikel bertarif sendiri"; kategori
 * tanpa tarif ditulis "Belum ada tarif — sales tidak mendapat komisi untuk kategori ini" + "Atur tarif kategori". Buka
 * kategori → artikelnya (`GET …/articles?category=`, 50 per muat): tarif sendiri atau "ikut kategori Rp …". Buka artikel →
 * varian (`GET …/articles/{id}/variants`): "ikut artikel" / "ikut kategori" / tarif sendiri. Tarif yang tampil dipilih
 * server dengan fungsi mesin komisi (`commission_rules.pilih_tarif`), jadi layar = angka yang dipakai mesin.
 *
 * Bilah daftar: cari artikel lintas kategori · Kategori ▾ · jumlah · [Ubah banyak (n)] [Unduh Excel] [Unggah Excel]. Ubah
 * satu tarif = pop-up `RateFormModal` (R15: "Berlaku untuk" PT ini / Semua PT; tarif Semua PT diubah di tempat); "Hapus
 * tarif" milik PT ini (artikel/varian: kembali ikut tingkat di atasnya) beralasan — tarif Semua PT dihapus dari mode
 * "Semua PT" (`GroupRatesList`); Riwayat per tarif = Jejak Audit (`audit.view`). Tombol menurut izin: ubah `sales_force.update`, hapus `sales_force.delete`
 * (`canCurrent`, sama dengan izin endpoint). Unggah Excel = `RatesExcelImport`.
 * Tinjauan akhir M6 — konfirmasi "Hapus tarif" menyebut tarif pengganti yang sebenarnya (`fallback` dari server: tarif yang
 * berlaku bila tarif PT ini di tingkat itu dihapus — tarif Semua PT di tingkat yang sama, atau tingkat di atasnya).
 */
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Download, History, Layers, Pencil, Trash2, Upload } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import AuditHistoryPanel from "../../components/AuditHistoryPanel";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import { ListToolbar, SearchInput } from "../../components/ListPageParts";
import { askReason } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, todayWib } from "../../utils/formatters";
import { canCurrent } from "../../config/roles";
import RateFormModal, { BulkRateModal } from "./RateFormModal";
import RatesExcelImport from "./RatesExcelImport";

export const TEKS_KATEGORI_TANPA_TARIF = "Belum ada tarif — sales tidak mendapat komisi untuk kategori ini";
export const TEKS_TANPA_UBAH = "Mengubah tarif komisi butuh akses Ubah di modul Pengawasan Tim Sales & Kredit.";
export const TEKS_MULAI = "Mulai dari tarif kategori: cukup atur tarif tiap kategori. Tarif artikel dan varian boleh "
  + "menyusul — tanpa isian, artikel ikut kategorinya dan varian ikut artikelnya.";
const UKURAN = 50;
const CARI = "__cari__";

/** Ringkasan tarif satu baris pohon: { teks, sub, sendiri (tarif PT ini di tingkat itu), adaDiTingkat (tarif di tingkat
 *  itu ada — milik PT ini atau Semua PT; R15: keduanya diubah di tempat lewat pop-up), lingkup, kosong }. */
export function ringkasTarif(tingkat, rate) {
  if (!rate) {
    return { teks: tingkat === "kategori" ? TEKS_KATEGORI_TANPA_TARIF : "Belum ada tarif — kategorinya belum bertarif",
      sub: "", sendiri: false, adaDiTingkat: false, lingkup: "", kosong: true };
  }
  const asal = tingkat === "kategori" ? "kategori" : (rate.asal_tingkat || "kategori");
  const semuaPt = rate.asal_lingkup === "semua_pt";
  const rp = formatCurrency(rate.per_unit_amount);
  const lingkup = semuaPt ? "semua_pt" : "pt";
  if (asal === tingkat) {
    return { teks: rp, sub: semuaPt ? "tarif Semua PT" : tingkat === "kategori" ? "tarif kategori" : "tarif sendiri",
      sendiri: !semuaPt, adaDiTingkat: true, lingkup, kosong: false };
  }
  return { teks: `ikut ${asal} ${rp}${semuaPt ? " (Semua PT)" : ""}`, sub: "", sendiri: false, adaDiTingkat: false, lingkup,
    kosong: false };
}

const LINGKUP_TEKS = { pt: "PT ini", semua_pt: "Semua PT" };

/** M6 — kalimat akibat menghapus tarif PT ini di satu tingkat. `fallback` (server) = tarif yang berlaku sesudahnya
 *  (`{per_unit_amount, asal_tingkat, asal_lingkup}`), `{tanpa_tarif:true}` = tanpa tarif; tanpa `fallback` = kalimat umum. */
export function akibatHapus(tingkat, fallback, kategori = "") {
  if (fallback?.tanpa_tarif) {
    return `Sesudah dihapus, ${tingkat} ini tidak punya tarif lagi — sales tidak mendapat komisi untuknya.`;
  }
  if (fallback) {
    const asal = `tarif ${fallback.asal_tingkat || "kategori"} ${LINGKUP_TEKS[fallback.asal_lingkup] || ""}`.trim();
    return `Sesudah dihapus, ${tingkat} ini memakai ${asal} ${formatCurrency(fallback.per_unit_amount)}.`;
  }
  return tingkat === "artikel" ? `Artikel ini kembali ikut tarif artikel Semua PT bila ada, atau tarif kategori ${kategori}.`
    : tingkat === "varian" ? "Varian ini kembali ikut tarif artikelnya (PT ini atau Semua PT), atau tarif kategori bila artikelnya tidak bertarif."
      : "Kategori ini memakai tarif Semua PT bila ada; bila tidak, sales tidak mendapat komisi untuk kategori ini.";
}

/** Batas margin tampil: "50 %" · 0/kosong = "tidak dibatasi". */
const teksBatas = (rate) => (!rate ? "—" : Number(rate.margin_cap_pct || 0) > 0
  ? `${String(rate.margin_cap_pct).replace(".", ",")} %` : "tidak dibatasi");

function SelTarif({ r, testId }) {
  return (
    <td className="text-right" data-testid={testId}>
      <span className={`${r.kosong ? "text-kn-warning-text" : r.sub ? "font-semibold text-kn-text" : "text-kn-text-2"} ${r.kosong ? "" : "whitespace-nowrap"}`}>{r.teks}</span>
      {r.sub && <span className="block text-fs-12 text-kn-text-2">{r.sub}</span>}
    </td>
  );
}

export default function ArticleRatesTable({ entityId, pt, ptPendek, bawaanBatas, bolehSemuaPt = true, dasarHarga = "" }) {
  const canUpdate = canCurrent("sales_force", "update");
  const canDelete = canCurrent("sales_force", "delete");
  const canAudit = canCurrent("audit", "view");
  const [kat, setKat] = useState({ state: "loading", items: [], err: "" });
  const [buka, setBuka] = useState({});          // kategori → terbuka
  const [artikel, setArtikel] = useState({});    // kategori | CARI → { state, items, total, page, err }
  const [bukaArt, setBukaArt] = useState({});    // template_id → terbuka
  const [varian, setVarian] = useState({});      // template_id → { state, items, err }
  const [cari, setCari] = useState("");
  const [term, setTerm] = useState("");
  const [filterKat, setFilterKat] = useState("");
  const [pilih, setPilih] = useState({});        // template_id → nama artikel (ubah banyak)
  const [sasaran, setSasaran] = useState(null);  // pop-up tarif
  const [bulk, setBulk] = useState(false);
  const [impor, setImpor] = useState(false);
  const [riwayat, setRiwayat] = useState(null);
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState("");
  const status = useRef({});
  status.current = { buka, bukaArt, artikel, term, filterKat };
  const urutan = useRef({});                     // kunci daftar → nomor muat terakhir (jawaban lama diabaikan)

  const muatKategori = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/incentive-rates/categories`, { params: { entity_id: entityId } });
      setKat({ state: "ready", items: r.data?.items || [], err: "" });
    } catch (e) { setKat({ state: "error", items: [], err: apiErrorText(e) || "" }); }
  }, [entityId]);

  const muatArtikel = useCallback(async (kunci, page = 1, ukuran = UKURAN) => {
    const { term: t, filterKat: fk } = status.current;
    const params = kunci === CARI
      ? { entity_id: entityId, search: t, ...(fk ? { category: fk } : {}), page, page_size: ukuran }
      : { entity_id: entityId, category: kunci, page, page_size: ukuran };
    const no = (urutan.current[kunci] || 0) + 1;
    urutan.current[kunci] = no;
    setArtikel((a) => ({ ...a, [kunci]: { items: [], ...(a[kunci] || {}), state: "loading" } }));
    try {
      const r = await axios.get(`${API}/incentive-rates/articles`, { params });
      if (urutan.current[kunci] !== no) return;   // pencarian lebih baru sudah dikirim
      const d = r.data || {};
      setArtikel((a) => {
        const lama = page > 1 ? (a[kunci]?.items || []) : [];
        const ada = new Set(lama.map((x) => x.template_id));
        const items = [...lama, ...(d.items || []).filter((x) => !ada.has(x.template_id))];
        // R16 — `page` = jumlah halaman ber-UKURAN yang sudah termuat (muat ulang berukuran besar sesudah menyimpan
        // tetap membuat "berikutnya" meminta halaman yang benar, tanpa baris kembar).
        return { ...a, [kunci]: { state: "ready", err: "", total: d.total || 0, items,
          page: Math.max(1, Math.ceil(items.length / UKURAN)) } };
      });
    } catch (e) {
      if (urutan.current[kunci] !== no) return;
      setArtikel((a) => ({ ...a, [kunci]: { items: [], ...(a[kunci] || {}), state: "error", err: apiErrorText(e) || "" } }));
    }
  }, [entityId]);

  const muatVarian = useCallback(async (tid) => {
    setVarian((v) => ({ ...v, [tid]: { items: [], ...(v[tid] || {}), state: "loading" } }));
    try {
      const r = await axios.get(`${API}/incentive-rates/articles/${tid}/variants`, { params: { entity_id: entityId } });
      setVarian((v) => ({ ...v, [tid]: { state: "ready", items: r.data?.items || [], err: "" } }));
    } catch (e) { setVarian((v) => ({ ...v, [tid]: { items: [], state: "error", err: apiErrorText(e) || "" } })); }
  }, [entityId]);

  /** Sesudah menulis: kategori + daftar artikel yang terbuka (sebanyak yang sudah dimuat) + varian yang terbuka. Daftar
   *  yang tertutup dibuang dari simpanan (R16) supaya dibuka lagi = dimuat baru, bukan angka lama. */
  const muatUlang = useCallback(async () => {
    const s = status.current;
    const kunci = [...(s.term ? [CARI] : []), ...Object.keys(s.buka).filter((k) => s.buka[k])];
    setArtikel((a) => Object.fromEntries(Object.entries(a).filter(([k]) => kunci.includes(k))));
    setVarian((v) => Object.fromEntries(Object.entries(v).filter(([t]) => s.bukaArt[t])));
    await Promise.all([muatKategori(),
      ...kunci.map((k) => muatArtikel(k, 1, Math.min(200, Math.max(UKURAN, (s.artikel[k]?.items || []).length)))),
      ...Object.keys(s.bukaArt).filter((t) => s.bukaArt[t]).map(muatVarian)]);
  }, [muatKategori, muatArtikel, muatVarian]);

  useEffect(() => {
    setBuka({}); setBukaArt({}); setArtikel({}); setVarian({}); setPilih({});
    muatKategori();
  }, [muatKategori]);
  useEffect(() => { const t = window.setTimeout(() => setTerm(cari.trim()), 300); return () => window.clearTimeout(t); }, [cari]);
  useEffect(() => { if (term) muatArtikel(CARI); }, [term, filterKat, muatArtikel]);
  useEffect(() => {
    if (!filterKat || term) return;
    setBuka((b) => ({ ...b, [filterKat]: true }));
    if (!status.current.artikel[filterKat]) muatArtikel(filterKat);
  }, [filterKat, term, muatArtikel]);

  const togKategori = (c) => {
    setNotice("");
    const jadi = !buka[c];
    setBuka((b) => ({ ...b, [c]: jadi }));
    if (jadi && !artikel[c]) muatArtikel(c);
  };
  const togArtikel = (tid) => {
    setNotice("");
    const jadi = !bukaArt[tid];
    setBukaArt((b) => ({ ...b, [tid]: jadi }));
    if (jadi && !varian[tid]) muatVarian(tid);
  };
  const tersimpan = async (pesan) => { setSasaran(null); setNotice(pesan); setErr(""); await muatUlang(); };

  const hapus = async ({ tingkat, nama, rate, kategori, fallback }) => {
    const akibat = akibatHapus(tingkat, fallback, kategori);
    const reason = await askReason({ title: `Hapus tarif ${tingkat} ${nama}?`,
      message: `${akibat} Berlaku untuk pesanan yang dibuat sesudah dihapus.`, reasonLabel: "Alasan penghapusan",
      confirmLabel: "Hapus tarif", danger: true, testId: "rates-delete-confirm" });
    if (reason === null) return;
    setNotice("");
    try {
      await axios.delete(`${API}/incentive-rates/${rate.rate_id}`, { params: { reason } });
      setNotice(`Tarif ${tingkat} ${nama} dihapus.`); setErr("");
      await muatUlang();
    } catch (e) { setErr(apiErrorText(e) || "Tarif gagal dihapus."); }
  };

  const unduh = async () => {
    setNotice("");
    try {
      const r = await axios.get(`${API}/incentive-rates/export`, { params: { entity_id: entityId }, responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `tarif-komisi-${ptPendek || "pt"}-${todayWib()}.xlsx`;
      document.body.appendChild(a); a.click(); a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setErr(apiErrorText(e) || "Excel tarif gagal diunduh."); }
  };

  // Fungsi biasa (bukan komponen) supaya sel aksi tidak dipasang ulang tiap render.
  const aksi = ({ prefix, id, info, sasaranBaru, labelAtur = "Atur tarif" }) => (
    <td className="col-sticky-end text-right">
      <div className="flex items-center justify-end gap-1">
        {canUpdate && (
          <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`${prefix}-edit-${id}`}
            onClick={() => { setNotice(""); setSasaran(sasaranBaru); }}>{info.adaDiTingkat ? <><Pencil size={12} aria-hidden="true" />Ubah</> : labelAtur}</button>)}
        {canDelete && info.sendiri && (
          <button type="button" className="secondary-button btn-sm whitespace-nowrap text-kn-danger-text" data-testid={`${prefix}-delete-${id}`}
            onClick={() => hapus(sasaranBaru)}><Trash2 size={12} aria-hidden="true" />Hapus tarif</button>)}
        {canAudit && info.adaDiTingkat && (
          <button type="button" className="icon-button" aria-label={`Riwayat tarif ${sasaranBaru.nama}`} data-testid={`${prefix}-history-${id}`}
            onClick={() => setRiwayat({ id: sasaranBaru.rate.rate_id, nama: sasaranBaru.nama })}><History size={13} /></button>)}
      </div>
    </td>
  );

  const barisVarian = (a) => {
    const v = varian[a.template_id];
    if (!v || v.state === "loading") return <tr><td colSpan={5} className="pl-16 text-fs-12 text-kn-text-2" role="status">Memuat varian…</td></tr>;
    if (v.state === "error") return <tr><td colSpan={5} className="pl-16"><ErrorNotice message={`Varian tidak bisa dimuat. ${v.err}`.trim()} onRetry={() => muatVarian(a.template_id)} /></td></tr>;
    if (!v.items.length) return <tr><td colSpan={5} className="pl-16 text-fs-12 text-kn-text-2">Artikel ini belum punya varian aktif.</td></tr>;
    return v.items.map((p) => {
      const info = ringkasTarif("varian", p.rate);
      return (
        <tr key={p.product_id} data-testid={`rates-var-${p.product_id}`}>
          <td />
          <td className="pl-16"><span className="block break-words text-fs-13">{p.name || p.sku}</span>
            <span className="block font-mono text-fs-12 text-kn-text-2">{p.sku}</span></td>
          <SelTarif r={info} testId={`rates-var-rate-${p.product_id}`} />
          <td className={`text-right tabular-nums ${info.adaDiTingkat ? "" : "text-kn-text-2"}`}>{teksBatas(p.rate)}</td>
          {aksi({ prefix: "rates-var", id: p.product_id, info, sasaranBaru: { tingkat: "varian", nama: p.sku || p.name,
            product_id: p.product_id, rate: p.rate, sendiri: info.sendiri, adaDiTingkat: info.adaDiTingkat, fallback: p.fallback } })}
        </tr>
      );
    });
  };

  const barisArtikel = (kunci, cariMode) => {
    const d = artikel[kunci];
    if (!d || (d.state === "loading" && !d.items.length)) return <tr><td colSpan={5} className="pl-8 text-fs-12 text-kn-text-2" role="status">Memuat artikel…</td></tr>;
    if (d.state === "error") return <tr><td colSpan={5} className="pl-8"><ErrorNotice message={`Artikel tidak bisa dimuat. ${d.err}`.trim()} onRetry={() => muatArtikel(kunci)} /></td></tr>;
    if (!d.items.length) return <tr><td colSpan={5} className="pl-8 text-fs-12 text-kn-text-2" data-testid="rates-art-empty">{cariMode ? `Tidak ada artikel yang cocok dengan “${term}”.` : "Belum ada artikel aktif di kategori ini."}</td></tr>;
    return (
      <>
        {d.items.map((a) => {
          const info = ringkasTarif("artikel", a.rate);
          return (
            <Fragment key={a.template_id}>
              <tr data-testid={`rates-art-${a.template_id}`}>
                <td>{canUpdate && <input type="checkbox" aria-label={`Pilih ${a.name}`} data-testid={`rates-art-pick-${a.template_id}`}
                  checked={!!pilih[a.template_id]} onChange={() => setPilih((s) => {
                    const n = { ...s };
                    if (n[a.template_id]) delete n[a.template_id]; else n[a.template_id] = a.name;
                    return n;
                  })} />}</td>
                <td className={cariMode ? "" : "pl-8"}>
                  <button type="button" className="ghost-button items-start text-left" aria-expanded={!!bukaArt[a.template_id]}
                    data-testid={`rates-art-toggle-${a.template_id}`} onClick={() => togArtikel(a.template_id)}>
                    {bukaArt[a.template_id] ? <ChevronDown size={14} className="mt-0.5 shrink-0" aria-hidden="true" /> : <ChevronRight size={14} className="mt-0.5 shrink-0" aria-hidden="true" />}
                    <span className="min-w-0"><span className="block break-words text-fs-13 font-semibold text-kn-text">{a.name}</span>
                      <span className="block text-fs-12 text-kn-text-2"><span className="font-mono">{a.code}</span>
                        {cariMode && a.category ? ` · ${a.category}` : ""}
                        {a.variant_exceptions ? ` · ${a.variant_exceptions} varian bertarif sendiri` : ""}</span></span>
                  </button>
                </td>
                <SelTarif r={info} testId={`rates-art-rate-${a.template_id}`} />
                <td className={`text-right tabular-nums ${info.adaDiTingkat ? "" : "text-kn-text-2"}`}>{teksBatas(a.rate)}</td>
                {aksi({ prefix: "rates-art", id: a.template_id, info, sasaranBaru: { tingkat: "artikel", nama: a.name,
                  template_id: a.template_id, kategori: a.category, rate: a.rate, sendiri: info.sendiri,
                  adaDiTingkat: info.adaDiTingkat, fallback: a.fallback } })}
              </tr>
              {bukaArt[a.template_id] && barisVarian(a)}
            </Fragment>
          );
        })}
        {d.items.length < d.total && (
          <tr><td colSpan={5} className="pl-8">
            <button type="button" className="link-button text-fs-12" data-testid={`rates-more-${kunci}`} disabled={d.state === "loading"}
              onClick={() => muatArtikel(kunci, (d.page || 1) + 1)}>Tampilkan {Math.min(UKURAN, d.total - d.items.length)} artikel berikutnya ({d.items.length} dari {d.total})</button>
          </td></tr>
        )}
      </>
    );
  };

  const kategori = kat.items.filter((c) => !filterKat || c.category === filterKat);
  const nPilih = Object.keys(pilih).length;
  const belumAdaTarif = kat.state === "ready" && kat.items.length > 0 && kat.items.every((c) => !c.rate);
  return (
    <div className="space-y-2" data-testid="rates-tree">
      <ListToolbar testId="rates-toolbar" count={kat.state !== "ready" ? null : term ? `${artikel[CARI]?.total ?? 0} artikel` : `${kategori.length} kategori`}
        actions={<>
          {canUpdate && <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="rates-bulk"
            disabled={!nPilih} onClick={() => { setNotice(""); setBulk(true); }}><Layers size={13} aria-hidden="true" />{nPilih ? `Ubah banyak (${nPilih})` : "Ubah banyak"}</button>}
          <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="rates-download" onClick={unduh}>
            <Download size={13} aria-hidden="true" />Unduh Excel</button>
          {canUpdate && <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="rates-upload"
            onClick={() => { setNotice(""); setImpor(true); }}><Upload size={13} aria-hidden="true" />Unggah Excel</button>}
        </>}>
        <SearchInput value={cari} onChange={setCari} placeholder="Cari artikel (nama atau kode)" testId="rates-search" />
        <div className="w-[200px]"><KNSelect data-testid="rates-category-filter" className="field" value={filterKat}
          placeholder="Semua kategori" options={[{ value: "", label: "Semua kategori" }, ...kat.items.map((c) => ({ value: c.category, label: c.category }))]}
          onValueChange={(v) => setFilterKat(v || "")} /></div>
      </ListToolbar>
      {!canUpdate && <p className="text-fs-12 text-kn-text-2" data-testid="rates-why">{TEKS_TANPA_UBAH}</p>}
      {canUpdate && nPilih > 0 && (
        <p className="text-fs-12 text-kn-text-2" data-testid="rates-picked">{nPilih} artikel dipilih untuk Ubah banyak.{" "}
          <button type="button" className="link-button text-fs-12" data-testid="rates-pick-clear" onClick={() => setPilih({})}>Batalkan pilihan</button></p>
      )}
      {belumAdaTarif && <p className="text-fs-12 text-kn-text" data-testid="rates-start-hint">{TEKS_MULAI}</p>}
      {notice && <div className="notice-bar success" data-testid="rates-notice"><span className="text-fs-12">{notice}</span></div>}
      {err && <ErrorNotice testId="rates-error" message={err} onDismiss={() => setErr("")} />}

      {kat.state === "loading" ? (
        <p className="text-fs-13 text-kn-text-2" role="status" data-testid="rates-loading">Memuat tarif komisi…</p>
      ) : kat.state === "error" ? (
        <ErrorNotice testId="rates-load-error" message={`Tarif komisi tidak bisa dimuat. ${kat.err}`.trim()} onRetry={muatKategori} />
      ) : !kat.items.length ? (
        <p className="text-fs-13 text-kn-text-2" data-testid="rates-empty">Belum ada kategori dengan artikel aktif. Tambahkan kategori dan artikel di Master Produk.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table head-wrap w-full" data-testid="rates-table">
            <thead><tr><th className="w-8"><span className="sr-only">Pilih</span></th><th>{term ? "Artikel" : "Kategori / artikel / varian"}</th>
              <th className="text-right">Tarif per satuan dasar</th><th className="text-right">Batas margin</th>
              <th className="col-sticky-end"><span className="sr-only">Aksi</span></th></tr></thead>
            <tbody>
              {term ? barisArtikel(CARI, true) : kategori.map((c) => {
                const info = ringkasTarif("kategori", c.rate);
                return (
                  <Fragment key={c.category}>
                    <tr data-testid={`rates-cat-${c.category}`} className="bg-kn-neutral-soft">
                      <td />
                      <td>
                        <button type="button" className="ghost-button items-start text-left" aria-expanded={!!buka[c.category]}
                          data-testid={`rates-cat-toggle-${c.category}`} onClick={() => togKategori(c.category)}>
                          {buka[c.category] ? <ChevronDown size={14} className="mt-0.5 shrink-0" aria-hidden="true" /> : <ChevronRight size={14} className="mt-0.5 shrink-0" aria-hidden="true" />}
                          <span><span className="block text-fs-13 font-bold text-kn-text">{c.category}</span>
                            <span className="block text-fs-12 text-kn-text-2">{c.articles} artikel{c.articles_own_rate ? ` · ${c.articles_own_rate} bertarif sendiri` : ""}</span></span>
                        </button>
                      </td>
                      <SelTarif r={info} testId={`rates-cat-rate-${c.category}`} />
                      <td className="text-right tabular-nums">{teksBatas(c.rate)}</td>
                      {aksi({ prefix: "rates-cat", id: c.category, info, labelAtur: "Atur tarif kategori",
                        sasaranBaru: { tingkat: "kategori", nama: c.category, category: c.category, rate: c.rate, sendiri: info.sendiri,
                          adaDiTingkat: info.adaDiTingkat, fallback: c.fallback } })}
                    </tr>
                    {buka[c.category] && barisArtikel(c.category, false)}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <RateFormModal sasaran={sasaran} entityId={entityId} pt={pt} bawaanBatas={bawaanBatas} bolehSemuaPt={bolehSemuaPt}
        dasarHarga={dasarHarga} onClose={() => setSasaran(null)} onSaved={tersimpan} />
      {bulk && <BulkRateModal ids={Object.keys(pilih)} entityId={entityId} pt={pt} onClose={() => setBulk(false)}
        onSaved={async (r) => {
          const n = nPilih;
          setBulk(false); setPilih({});
          await tersimpan(`Tarif ${n} artikel disimpan: ${r.created || 0} baru, ${r.updated || 0} diubah.`);
        }} />}
      {impor && <RatesExcelImport entityId={entityId} pt={pt} onClose={() => setImpor(false)}
        onApplied={async (r) => { setImpor(false); await tersimpan(`Excel diterapkan: ${r.created || 0} tarif baru, ${r.updated || 0} diubah.`); }} />}
      {riwayat && (
        <FormModal open onClose={() => setRiwayat(null)} testId="rates-history" icon={History} size="lg" title={`Riwayat tarif ${riwayat.nama}`} subtitle={pt}>
          <AuditHistoryPanel entityType="incentive_rate" entityId={riwayat.id} testIdPrefix="rates-history-list" />
        </FormModal>
      )}
    </div>
  );
}
