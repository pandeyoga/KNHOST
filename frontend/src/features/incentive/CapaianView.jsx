/**
 * CapaianView — KM-T2 · SDM › Kinerja & Insentif › **Capaian** (view `incentive-capaian`).
 *
 * Pemutus insentif memilih periode lalu melihat per sales: target & capaian omzet, target & capaian pencairan, kualitas
 * harga jual. Setiap angka Omzet / Retur / Uang masuk bisa ditelusuri sampai dokumennya (panel telusur
 * `CapaianSourcesPanel`, pop-up rincian baku `DetailModal`); baris yang dicentang dijumlahkan DI LAYAR dari angka yang sedang tampil (tanpa permintaan baru).
 * Layar ini hanya membaca angka. KM-T3 — satu tombol tulis: "Buat lembar insentif dari tampilan ini" (izin
 * `incentive.prepare`, sales dicentang) membuat lembar draf berisi satu baris per sales; nominalnya diketik di lembar.
 *
 * Sumber: GET /api/incentive/achievement (izin `incentive.view`; kolom margin hanya bila server mengirimnya — izin
 * `incentive.view_margin`) · GET …/achievement/sources · GET …/achievement/export (.xlsx). "Semua PT" → satu kalimat
 * (definisi angka berbeda di tiap PT), tanpa memanggil server.
 *
 * Lebar tabel (1024 px, kartu ± 750 px): kolom dipilih per kelompok ("Kolom": Ringkas · Omzet · Pencairan · Kualitas
 * harga · Lain · Semua kolom); semua pilihan selain "Semua kolom" muat di kartu (angka uang tanpa "Rp", keterangan di atas
 * tabel). "Semua kolom" bergulir di wadahnya dengan kolom nama menempel di kiri; tidak ada kolom aksi.
 * Tampilan tersimpan (saringan, pengelompokan, kolom) di peramban per pengguna: `kn.capaian.tampilan.<id pengguna>`.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, BarChart3, ClipboardList, Download, Save, Search } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNDatePicker from "../../components/KNDatePicker";
import KNSelect from "../../components/KNSelect";
import { useEntityScope } from "../../context/EntityScopeContext";
import { useAppNav } from "../../context/AppNavContext";
import { canCurrent } from "../../config/roles";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate, formatDecimal, todayWib } from "../../utils/formatters";
import { pilihanPeriode } from "./IncentiveSetupView";
import CapaianSourcesPanel from "./CapaianSourcesPanel";
import { pilihanDasar } from "./IncentiveSheetDetail";

export const TEKS_SEMUA_PT = "Pilih satu PT untuk melihat Capaian. Definisi angka berbeda di tiap PT.";
export const TEKS_MEMUAT = "Memuat capaian…";
export const TEKS_GALAT = "Capaian gagal dimuat.";
export const TEKS_KOSONG = "Belum ada penjualan atau uang masuk pada periode ini.";
export const JENIS_PERIODE = [{ value: "month", label: "Bulan" }, { value: "quarter", label: "Triwulan" },
  { value: "year", label: "Tahun" }, { value: "range", label: "Rentang tanggal" }];
export const BANDING = [{ value: "none", label: "Tidak" }, { value: "prev", label: "Periode sebelumnya" },
  { value: "yoy", label: "Periode sama tahun lalu" }];
export const KELOMPOK = [{ value: "sales", label: "Sales" }, { value: "customer", label: "Pelanggan" },
  { value: "category", label: "Kategori produk" }, { value: "price_source", label: "Sumber harga" }];
export const PILIHAN_KOLOM = [{ value: "ringkas", label: "Ringkas" }, { value: "omzet", label: "Omzet" },
  { value: "pencairan", label: "Pencairan" }, { value: "harga", label: "Kualitas harga" }, { value: "lain", label: "Lain" },
  { value: "semua", label: "Semua kolom" }];
const NAMA_KELOMPOK = { sales: "sales", customer: "pelanggan", category: "kategori", price_source: "sumber harga" };
const JUDUL_KELOMPOK = { sales: "Sales", customer: "Pelanggan", category: "Kategori produk", price_source: "Sumber harga" };
export const GRUP = { omzet: "Omzet", pencairan: "Pencairan", harga: "Kualitas harga", lain: "Lain" };

/** Kolom tabel — kelompok, judul persis spesifikasi, jenis angka. `perSales` = hanya saat dikelompokkan per sales. */
export const KOLOM = [
  { f: "target_sales", g: "omzet", label: "Target", kind: "target", perSales: true },
  { f: "omzet", g: "omzet", label: "Omzet", kind: "money", drill: "omzet", ringkas: true },
  { f: "pct_omzet", g: "omzet", label: "% capaian", kind: "pct", perSales: true, ringkas: true },
  { f: "retur", g: "omzet", label: "Retur", kind: "money", drill: "retur" },
  { f: "omzet_bersih", g: "omzet", label: "Omzet bersih", kind: "money", compare: true, ringkas: true },
  { f: "target_collection", g: "pencairan", label: "Target", kind: "target", perSales: true },
  { f: "uang_masuk", g: "pencairan", label: "Uang masuk", kind: "money", drill: "uang_masuk", compare: true, ringkas: true },
  { f: "pct_pencairan", g: "pencairan", label: "% capaian", kind: "pct", perSales: true, ringkas: true },
  { f: "sisa_piutang", g: "pencairan", label: "Sisa piutang", kind: "money", perSales: true },
  { f: "lewat_tempo", g: "pencairan", label: "Lewat tempo", kind: "money", perSales: true },
  { f: "realisasi_harga_pct", g: "harga", label: "Realisasi harga", kind: "pct", ringkas: true },
  { f: "rata_potongan_pct", g: "harga", label: "Rata-rata potongan", kind: "pct" },
  { f: "porsi_bawah_acuan_pct", g: "harga", label: "Di bawah harga acuan", kind: "pct" },
  { f: "margin_pct", g: "harga", label: "Margin", kind: "pct", margin: true },
  { f: "pelanggan_baru", g: "lain", label: "Pelanggan baru", kind: "count", perSales: true },
  { f: "jumlah_pesanan", g: "lain", label: "Pesanan", kind: "count" },
  { f: "catatan_data", g: "lain", label: "Catatan data", kind: "notes" },
];
const METRIK_LABEL = { omzet: "Omzet", retur: "Retur", uang_masuk: "Uang masuk" };

/** Kolom yang tampil untuk pilihan `kolom`; margin hanya bila server mengirimnya (izin `incentive.view_margin`). */
export function kolomTampil(kolom, { perSales, marginVisible }) {
  return KOLOM.filter((c) => (!c.perSales || perSales) && (!c.margin || marginVisible)
    && (kolom === "semua" || (kolom === "ringkas" ? c.ringkas : c.g === kolom)));
}

/** Persen satu desimal dengan koma: 86.2 → "86,2 %"; kosong → "—". */
export const persen = (v) => (v === null || v === undefined ? "—" : `${formatDecimal(v, 1, 1)} %`);
/** Angka uang di sel tabel (tanpa "Rp" — keterangan di atas tabel): 1000000000 → "1.000.000.000"; kosong → "—". */
export const angka = (v) => (v === null || v === undefined ? "—" : Math.round(Number(v)).toLocaleString("id-ID"));

/** "Omzet: … · Pencairan: … · Milik: … · Harga acuan: … — berlaku sejak {tanggal} (versi {n})". */
export function barisDefinisi(def) {
  if (!def) return "";
  const lbl = (f) => (def.labels || []).find((x) => x.field === f)?.value_label || "—";
  return `Omzet: ${lbl("dasar_omzet")} · Pencairan: ${lbl("isi_pencairan")} · Milik: ${lbl("pemilik_angka")} · `
    + `Harga acuan: ${lbl("harga_acuan")} — berlaku sejak ${formatDate(def.effective_from)} (versi ${def.version})`;
}

/** Peringatan pencocokan bila omzet atau pencairan belum cocok dengan pembukuan; "" bila cocok. */
export function teksPeringatan(rec) {
  if (!rec || (rec.omzet_ok && rec.pencairan_ok)) return "";
  return `Angka belum cocok dengan pembukuan (omzet selisih ${formatCurrency(Math.abs(rec.omzet_diff || 0))}, pencairan `
    + `selisih ${formatCurrency(Math.abs(rec.pencairan_diff || 0))}). Lihat rinciannya di tab Target & Aturan.`;
}

/** Selisih terhadap pembanding: "+Rp 480.000.000 dari Sep 2026" (dua bagian supaya angka tidak terpotong). */
export function selisihPembanding(cur, prev, label) {
  if (cur === null || cur === undefined || !label) return null;
  const d = Number(cur || 0) - Number(prev || 0);
  return { angka: `${d < 0 ? "−" : "+"}${formatCurrency(Math.abs(d))}`, dari: `dari ${label}` };
}

/** Bilah jumlah pilihan dari angka yang SEDANG TAMPIL (tanpa permintaan ke server). "" = tidak ada pilihan. */
export function teksPilihan(rows, selected) {
  const pilih = (rows || []).filter((r) => selected.has(r.key));
  if (!pilih.length) return "";
  const n = pilih.length;
  const om = pilih.reduce((s, r) => s + Number(r.omzet_bersih || 0), 0);
  let out = `${n} baris dipilih · Omzet bersih: jumlah ${formatCurrency(om)} · rata-rata ${formatCurrency(Math.round(om / n))}`;
  if (pilih.every((r) => r.uang_masuk !== null && r.uang_masuk !== undefined)) {
    const um = pilih.reduce((s, r) => s + Number(r.uang_masuk || 0), 0);
    out += ` · Uang masuk: jumlah ${formatCurrency(um)} · rata-rata ${formatCurrency(Math.round(um / n))}`;
  }
  return out;
}

/** Jam data WIB "HH:MM" dari stempel ISO. */
export function jamData(iso) {
  const d = iso ? new Date(iso) : null;
  if (!d || Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Jakarta" }).replace(".", ":");
}

/** KM-T3 — konfirmasi bila pencocokan angka KM-T1 merah sebelum lembar dibuat dari Capaian. */
export const TEKS_REKON_MERAH = "Angka omzet atau pencairan belum cocok dengan pembukuan. Tetap buat lembar?";

/** KM-T3 — alasan "Buat lembar insentif dari tampilan ini" mati (ditulis di samping tombol). "" = boleh. */
export function alasanBuatLembar({ canPrepare, perSales, nPilih }) {
  if (!canPrepare) return "Membuat lembar butuh akses Siapkan lembar insentif di modul Kinerja & Insentif.";
  if (!perSales) return "Kelompokkan menurut Sales untuk membuat lembar.";
  if (!nPilih) return "Centang sales yang akan dibuatkan lembar.";
  return "";
}

export const kunciTampilan = (userId) => `kn.capaian.tampilan.${userId || "anon"}`;
const BAWAAN = { jenis: "month", banding: "none", kumulatif: false, kelompok: "sales", kolom: "ringkas", adaAngka: true, cari: "" };

export function bacaTampilan(userId) {
  try {
    const raw = window.localStorage.getItem(kunciTampilan(userId));
    return raw ? { ...BAWAAN, ...JSON.parse(raw) } : { ...BAWAAN };
  } catch (_) { return { ...BAWAAN }; }
}

function simpanTampilan(userId, v) {
  try { window.localStorage.setItem(kunciTampilan(userId), JSON.stringify(v)); return true; } catch (_) { return false; }
}

function Sel({ c, row, cmp, onDrill }) {
  const v = row[c.f];
  if (c.kind === "notes") {
    const n = row.catatan_data || [];
    return n.length ? <ul className="space-y-0.5 text-fs-12 text-kn-warning-text">{n.map((x) => <li key={x.code}>{x.text}</li>)}</ul>
      : <span className="text-kn-text-2">—</span>;
  }
  if (c.kind === "pct") return <span className={v === null || v === undefined ? "text-kn-text-2" : ""}>{persen(v)}</span>;
  if (c.kind === "count") return <span className={!v ? "text-kn-text-2" : ""}>{v ?? "—"}</span>;
  if (c.kind === "target") return <span className={!v ? "text-kn-text-2" : ""}>{v ? angka(v) : "—"}</span>;
  const nol = v === null || v === undefined || Number(v) === 0;
  const isi = c.drill && !nol ? (
    <button type="button" className="link-button tabular-nums" data-testid={`cap-drill-${c.drill}-${row.key || "tanpa"}`} onClick={() => onDrill(c.drill, row)}>{angka(v)}</button>
  ) : <span className={nol ? "text-kn-text-2" : ""}>{v === null || v === undefined ? "—" : angka(v)}</span>;
  const sel = c.compare && cmp ? selisihPembanding(v, cmp.by_key?.[row.key]?.[c.f], cmp.label) : null;
  return (<>{isi}{sel && <span className="block text-fs-12 text-kn-text-2" data-testid={`cap-cmp-${c.f}-${row.key || "tanpa"}`}>
    <span className="whitespace-nowrap">{sel.angka}</span> <span className="whitespace-nowrap">{sel.dari}</span></span>}</>);
}

export default function CapaianView({ currentUser }) {
  const { selectedEntity } = useEntityScope();
  const allPt = !selectedEntity || selectedEntity === "all";
  const uid = currentUser?.id || "";
  const [view, setView] = useState(() => bacaTampilan(uid));
  const [periode, setPeriode] = useState("");
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [selected, setSelected] = useState(() => new Set());
  const [panel, setPanel] = useState(null);
  const [msg, setMsg] = useState("");
  const [busyExport, setBusyExport] = useState(false);
  const [exportErr, setExportErr] = useState("");
  const ubah = (patch) => { setView((v) => ({ ...v, ...patch })); setMsg(""); };
  // KM-T3 — buat lembar insentif dari sales yang dicentang.
  const nav = useAppNav();
  const canPrepare = canCurrent("incentive", "prepare");
  const [lembar, setLembar] = useState(null);
  const [komponen, setKomponen] = useState([]);
  const [busyLembar, setBusyLembar] = useState(false);
  const [errLembar, setErrLembar] = useState("");
  const kunciLembar = useIntentKey("isheet-cap");

  // `periode` = pilihan pengguna; kosong = periode berjalan menurut server (tahun buku PT), tanpa memuat dua kali.
  const params = useMemo(() => {
    const p = { period_type: view.jenis, group_by: view.kelompok, compare: view.banding };
    if (view.jenis === "range") { p.date_from = dari; p.date_to = sampai; } else if (periode) p.period = periode;
    if (view.kumulatif && view.jenis === "month") p.cumulative = true;
    return p;
  }, [view.jenis, view.kelompok, view.banding, view.kumulatif, periode, dari, sampai]);
  const rangeBelumLengkap = view.jenis === "range" && (!dari || !sampai);

  const load = useCallback(async () => {
    if (allPt || rangeBelumLengkap) return;
    setState("loading");
    try {
      const r = await axios.get(`${API}/incentive/achievement`, { params });
      setData(r.data); setErr(""); setState("ready"); setSelected(new Set());
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [params, allPt, rangeBelumLengkap]);
  const periodeTampil = periode || (data?.period?.type === view.jenis ? data?.period?.key : "") || "";
  // Telusur & ekspor memakai periode yang SEDANG TAMPIL (bukan "periode berjalan" saat pengguna belum memilih).
  const paramsTampil = useMemo(() => (data?.period?.key && view.jenis !== "range" && data.period.type === view.jenis
    ? { ...params, period: data.period.key } : params), [params, data, view.jenis]);
  useEffect(() => { load(); }, [load, selectedEntity]);

  const perSales = (data?.group_by || view.kelompok) === "sales";
  const cols = kolomTampil(view.kolom, { perSales, marginVisible: !!data?.margin_visible });
  const help = data?.definition?.columns || {};
  const rows = useMemo(() => data?.rows || [], [data]);
  const ber = rows.filter((r) => r.has_numbers);
  const tampil = useMemo(() => {
    const q = (view.cari || "").trim().toLowerCase();
    return rows.filter((r) => (!view.adaAngka || r.has_numbers) && (!q || String(r.name || "").toLowerCase().includes(q)));
  }, [rows, view.cari, view.adaAngka]);
  const pilihan = teksPilihan(tampil, selected);
  const cmp = data?.compare?.label ? data.compare : null;
  const semua = tampil.length > 0 && tampil.every((r) => selected.has(r.key));
  const togel = (k) => setSelected((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });
  const togelSemua = () => setSelected((s) => {
    const n = new Set(s);
    tampil.forEach((r) => (semua ? n.delete(r.key) : n.add(r.key)));
    return n;
  });
  const grupTampil = [...new Set(cols.map((c) => c.g))].map((g) => ({ g, n: cols.filter((c) => c.g === g).length }));
  const peringatan = teksPeringatan(data?.reconciliation);
  const periodeLabel = data?.period?.label || "";
  const salesDipilih = perSales ? tampil.filter((r) => r.key && selected.has(r.key)).map((r) => r.key) : [];
  const alasanLembar = alasanBuatLembar({ canPrepare, perSales, nPilih: salesDipilih.length });
  const kompLembar = komponen.find((c) => c.id === lembar?.component_id);
  const jenisLembar = kompLembar && kompLembar.basis_period_type !== "free" ? kompLembar.basis_period_type : (lembar?.jenis || "month");
  const bukaLembar = async () => {
    setErrLembar("");
    setLembar({ pay_period: todayWib().slice(0, 7), component_id: "", jenis: "month", periode: "" });
    try {
      const r = await axios.get(`${API}/incentive/sheets/options`);
      setKomponen(r.data?.components || []);
    } catch (e) { setErrLembar(apiErrorText(e) || "Daftar komponen gagal dimuat."); }
  };
  const pilihKomponen = (id) => {
    const c = komponen.find((x) => x.id === id);
    const jenis = c && c.basis_period_type !== "free" ? c.basis_period_type : "month";
    const tampilSama = data?.period?.type === jenis && !data?.period?.cumulative;
    setLembar((l) => ({ ...l, component_id: id, jenis, periode: tampilSama ? data.period.key : "" }));
  };
  const buatLembar = async () => {
    if (!lembar?.pay_period || !lembar?.component_id || !lembar?.periode) { setErrLembar("Isi periode bayar, komponen, dan periode dasar."); return; }
    const rec = data?.reconciliation;
    if (rec && !(rec.omzet_ok && rec.pencairan_ok)) {
      const ok = await askConfirm({ title: "Angka belum cocok dengan pembukuan", message: TEKS_REKON_MERAH, confirmLabel: "Tetap buat lembar" });
      if (!ok) return;
    }
    const body = { pay_period: lembar.pay_period, lines: salesDipilih.map((sid) => ({
      sales_id: sid, component_id: lembar.component_id, basis_period_type: jenisLembar, basis_period: lembar.periode })) };
    setBusyLembar(true); setErrLembar("");
    try {
      const r = await kunciLembar.send(body, (k) => moneyPost(`${API}/incentive/sheets`, body, k));
      setLembar(null);
      nav.go("incentive-sheets", { focus: { type: "incentive_sheet", id: r.data?.id, number: r.data?.number } });
    } catch (e) { setErrLembar(apiErrorText(e) || "Lembar gagal dibuat."); } finally { setBusyLembar(false); }
  };

  const drill = (metric, row) => setPanel({
    metric, metricLabel: METRIK_LABEL[metric], name: row.name, periodLabel: periodeLabel,
    params: { ...paramsTampil, compare: undefined, ...(perSales ? { sales_id: row.key } : { key: row.key }) },
  });
  const simpan = () => setMsg(simpanTampilan(uid, view) ? "Tampilan disimpan di peramban ini." : "Tampilan tidak bisa disimpan di peramban ini.");
  const ekspor = async () => {
    setBusyExport(true); setExportErr("");
    try {
      // Isi berkas = daftar yang sedang dilihat: saringan + cari + "hanya yang ada angkanya" (KN_37 §6).
      const r = await axios.get(`${API}/incentive/achievement/export`, {
        params: { ...paramsTampil, compare: undefined, q: (view.cari || "").trim() || undefined, only_numbers: view.adaAngka || undefined },
        responseType: "blob" });
      const cd = String(r.headers?.["content-disposition"] || "");
      const m = /filename="([^"]+)"/.exec(cd);
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = m ? m[1] : `capaian-${todayWib()}.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setExportErr(apiErrorText(e) || "Ekspor Excel gagal."); } finally { setBusyExport(false); }
  };

  if (allPt) {
    return (
      <div className="space-y-4" data-testid="incentive-capaian-view">
        <EntityScopeBanner testId="cap-scope" />
        <div className="section-card section-pad text-fs-13 text-kn-text-2" data-testid="cap-all-pt">{TEKS_SEMUA_PT}</div>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="incentive-capaian-view">
      <EntityScopeBanner testId="cap-scope" />
      <div className="section-card" data-testid="cap-card">
        <div className="section-head"><h2 className="flex items-center gap-2"><BarChart3 size={16} className="text-kn-action" aria-hidden="true" />Capaian</h2></div>
        <div className="section-body space-y-3">
          <div className="flex flex-wrap items-end gap-3" data-testid="cap-filters">
            <div className="w-[150px]"><label className="field-label">Periode</label>
              <KNSelect data-testid="cap-period-type" value={view.jenis} className="field" options={JENIS_PERIODE}
                onValueChange={(v) => { ubah({ jenis: v, ...(v !== "month" ? { kumulatif: false } : {}) }); setPeriode(""); }} /></div>
            {view.jenis === "range" ? (
              <>
                <div className="w-[170px]"><label className="field-label">Dari tanggal</label>
                  <KNDatePicker data-testid="cap-date-from" value={dari} onChange={setDari} max={sampai || undefined} /></div>
                <div className="w-[170px]"><label className="field-label">Sampai tanggal</label>
                  <KNDatePicker data-testid="cap-date-to" value={sampai} onChange={setSampai} min={dari || undefined} /></div>
              </>
            ) : (
              <div className="w-[190px]"><label className="field-label">{JENIS_PERIODE.find((j) => j.value === view.jenis)?.label}</label>
                <KNSelect data-testid="cap-period" value={periodeTampil} className="field" options={pilihanPeriode(view.jenis, periodeTampil)} onValueChange={setPeriode} /></div>
            )}
            <div className="w-[200px]"><label className="field-label">Bandingkan dengan</label>
              <KNSelect data-testid="cap-compare" value={view.banding} className="field" options={BANDING} onValueChange={(v) => ubah({ banding: v })} /></div>
            <div className="w-[170px]"><label className="field-label">Kelompokkan menurut</label>
              <KNSelect data-testid="cap-group" value={view.kelompok} className="field" options={KELOMPOK} onValueChange={(v) => ubah({ kelompok: v })} /></div>
            <div className="w-[150px]"><label className="field-label">Kolom</label>
              <KNSelect data-testid="cap-columns" value={view.kolom} className="field" options={PILIHAN_KOLOM} onValueChange={(v) => ubah({ kolom: v })} /></div>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2" data-testid="cap-toolbar">
            <label className="relative block w-full max-w-[260px]">
              <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-kn-text-2" aria-hidden="true" />
              <input data-testid="cap-search" className="field pl-7" placeholder="Cari nama…" aria-label="Cari nama"
                value={view.cari} onChange={(e) => ubah({ cari: e.target.value })} />
            </label>
            <label className="flex items-center gap-1.5 text-fs-13 text-kn-text">
              <input type="checkbox" data-testid="cap-cumulative" checked={!!view.kumulatif} disabled={view.jenis !== "month"}
                onChange={(e) => ubah({ kumulatif: e.target.checked })} />Kumulatif tahun berjalan</label>
            {view.jenis !== "month" && <span className="text-fs-12 text-kn-text-2" data-testid="cap-cumulative-why">Kumulatif hanya untuk periode Bulan.</span>}
            <label className="flex items-center gap-1.5 text-fs-13 text-kn-text">
              <input type="checkbox" data-testid="cap-only-numbers" checked={!!view.adaAngka} onChange={(e) => ubah({ adaAngka: e.target.checked })} />
              Hanya yang ada angkanya</label>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="cap-save-view" onClick={simpan}>
                <Save size={13} aria-hidden="true" /> Simpan tampilan</button>
              <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="cap-export"
                disabled={busyExport || state !== "ready" || rangeBelumLengkap} onClick={ekspor}><Download size={13} aria-hidden="true" /> {busyExport ? "Mengekspor…" : "Ekspor Excel"}</button>
              {!busyExport && (state !== "ready" || rangeBelumLengkap) && <span className="text-fs-12 text-kn-text-2" data-testid="cap-export-why">Ekspor menunggu capaian termuat.</span>}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2" data-testid="cap-sheet-bar">
            <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="cap-make-sheet"
              disabled={!!alasanLembar || state !== "ready"} onClick={bukaLembar}>
              <ClipboardList size={13} aria-hidden="true" /> Buat lembar insentif dari tampilan ini</button>
            {alasanLembar && <span className="text-fs-12 text-kn-text-2" data-testid="cap-make-sheet-why">{alasanLembar}</span>}
          </div>
          {msg && <div className="notice-bar success" data-testid="cap-msg"><span className="text-fs-12">{msg}</span></div>}
          {exportErr && <ErrorNotice testId="cap-export-error" message={exportErr} />}
          {data?.definition && <p className="text-fs-12 text-kn-text-2" data-testid="cap-definition">{barisDefinisi(data.definition)}</p>}
          {peringatan && state === "ready" && (
            <div className="notice-bar warning" role="alert" data-testid="cap-warning">
              <AlertTriangle size={14} aria-hidden="true" /><span className="text-fs-12">{peringatan}</span></div>
          )}
          {state === "ready" && (data?.notes || []).map((n) => <p key={n} className="text-fs-12 text-kn-text-2" data-testid="cap-note">{n}</p>)}
        </div>
        {rangeBelumLengkap ? (
          <div className="section-pad text-fs-13 text-kn-text-2" data-testid="cap-range-hint">Pilih tanggal awal dan akhir (paling panjang 366 hari).</div>
        ) : state === "loading" ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="cap-loading">{TEKS_MEMUAT}</div>
        ) : state === "error" ? (
          <div className="section-pad"><ErrorNotice testId="cap-error" message={`${TEKS_GALAT} ${err}`.trim()} onRetry={load} /></div>
        ) : ber.length === 0 ? (
          <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="cap-empty">{TEKS_KOSONG}</div>
        ) : (
          <>
            <p className="px-3 pb-1 text-fs-12 text-kn-text-2" data-testid="cap-caption">
              {periodeLabel} · angka uang dalam rupiah{cmp ? ` · dibandingkan dengan ${cmp.label}` : ""}
              {view.kolom === "semua" ? " · geser tabel ke samping untuk kolom lain" : ""}</p>
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full" data-testid="cap-table">
                <thead>
                  <tr>
                    <th rowSpan={2} className="sticky left-0 z-[2] bg-white min-w-[170px] align-bottom" title={help.sales}>
                      <label className="flex items-center gap-2">
                        <input type="checkbox" aria-label="Pilih semua baris yang tampil" checked={semua} onChange={togelSemua} data-testid="cap-check-all" />
                        {JUDUL_KELOMPOK[data?.group_by] || "Sales"}</label>
                    </th>
                    {grupTampil.map(({ g, n }) => <th key={g} colSpan={n} className="text-center border-l border-kn-divider">{GRUP[g]}</th>)}
                  </tr>
                  <tr>
                    {cols.map((c) => <th key={c.f} className="text-right" title={help[c.f]} data-testid={`cap-head-${c.f}`}>{c.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {tampil.map((r) => (
                    <tr key={r.key || "tanpa"} data-testid={`cap-row-${r.key || "tanpa"}`}>
                      <td className="sticky left-0 z-[1] bg-white min-w-[170px] max-w-[240px]">
                        <label className="flex items-start gap-2">
                          <input type="checkbox" className="mt-0.5" aria-label={`Pilih ${r.name}`} checked={selected.has(r.key)} onChange={() => togel(r.key)} data-testid={`cap-check-${r.key || "tanpa"}`} />
                          <span className="min-w-0 break-words">{r.name}
                            {view.kolom !== "lain" && view.kolom !== "semua" && (r.catatan_data || []).length > 0 && (
                              <span className="flex items-center gap-1 text-fs-12 text-kn-warning-text"><AlertTriangle size={11} aria-hidden="true" />{(r.catatan_data || []).length} catatan data</span>)}
                          </span>
                        </label>
                      </td>
                      {cols.map((c) => <td key={c.f} className={c.kind === "notes" ? "min-w-[180px]" : "text-right tabular-nums"}><Sel c={c} row={r} cmp={cmp} onDrill={drill} /></td>)}
                    </tr>
                  ))}
                </tbody>
                {data?.totals && tampil.length === rows.filter((r) => !view.adaAngka || r.has_numbers).length && (
                  <tfoot>
                    <tr className="font-semibold" data-testid="cap-total">
                      <td className="sticky left-0 z-[1] bg-white">Total</td>
                      {cols.map((c) => <td key={c.f} className={c.kind === "notes" ? "" : "text-right tabular-nums"}>
                        {c.kind === "notes" ? "" : <Sel c={{ ...c, drill: undefined }} row={{ ...data.totals, key: "__total" }} cmp={cmp ? { ...cmp, by_key: { __total: cmp.totals } } : null} onDrill={() => {}} />}</td>)}
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-kn-divider px-3 py-2 text-fs-12 text-kn-text-2">
              <span data-testid="cap-count">{tampil.length} dari {rows.length} {NAMA_KELOMPOK[data?.group_by] || "sales"}
                {view.adaAngka && rows.length > ber.length ? ` · ${rows.length - ber.length} tanpa angka disembunyikan` : ""}</span>
              {data?.facts_as_of && <span data-testid="cap-asof">Data per pukul {jamData(data.facts_as_of)} WIB</span>}
            </div>
          </>
        )}
      </div>
      {pilihan && (
        <div className="sticky bottom-3 z-20 notice-bar info shadow-md" role="status" data-testid="cap-selection">
          <span className="text-fs-13">{pilihan}</span>
          <button type="button" className="link-button whitespace-nowrap" data-testid="cap-selection-clear" onClick={() => setSelected(new Set())}>Hapus pilihan</button>
        </div>
      )}
      <CapaianSourcesPanel request={panel} onClose={() => setPanel(null)} />
      <FormModal open={!!lembar} onClose={() => setLembar(null)} title="Buat Lembar Insentif"
        subtitle={`${salesDipilih.length} sales dipilih · nominal diketik di lembar`} icon={ClipboardList} testId="cap-sheet-form"
        onSubmit={buatLembar} submitLabel="Buat Lembar" busy={busyLembar} error={errLembar}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div><label className="field-label">Periode bayar <span className="req">*</span></label>
            <KNSelect data-testid="cap-sheet-pay" value={lembar?.pay_period || ""} className="field"
              options={pilihanPeriode("month", lembar?.pay_period || todayWib().slice(0, 7))}
              onValueChange={(v) => setLembar((l) => ({ ...l, pay_period: v }))} /></div>
          <div><label className="field-label">Komponen <span className="req">*</span></label>
            <KNSelect data-testid="cap-sheet-comp" value={lembar?.component_id || ""} className="field" placeholder="Pilih komponen"
              emptyText="Belum ada komponen aktif. Tambahkan di tab Target & Aturan."
              options={komponen.map((c) => ({ value: c.id, label: `${c.name} (${c.basis_label})` }))} onValueChange={pilihKomponen} /></div>
          <div><label className="field-label">Periode dasar <span className="req">*</span></label>
            <KNSelect data-testid="cap-sheet-basis" value={lembar?.periode || ""} className="field" placeholder="Pilih periode"
              options={pilihanDasar(jenisLembar, lembar?.periode)} onValueChange={(v) => setLembar((l) => ({ ...l, periode: v }))} /></div>
        </div>
      </FormModal>
    </div>
  );
}
