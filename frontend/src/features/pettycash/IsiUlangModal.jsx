/**
 * IsiUlangModal — Kas & Bank bagian 3 (Tugas 4a): pop-up baku `FormModal` "Isi ulang" dana tetap kas kecil (rancangan
 * §5.2, §7.8 butir 4). Dibuka dari kartu rekening (Rekening & Saldo) dan dari Kas Kecil › Dana tetap — satu komponen.
 *
 * Memuat posisi `GET /api/kas-kecil/dana-tetap/{id}` setiap dibuka (angka terbaru): dana tetap, saldo buku, sisa panjar
 * di tangan karyawan (`panjar_belum_lpj`, ketetapan R3), dan **nominal isi ulang hanya-baca** (= usulan server; server menghitung ulang saat disimpan dan MENOLAK nominal
 * dari klien, jadi kiriman tidak memuat `nominal`). Pengguna memilih rekening sumber (bank / kas besar PT yang sama,
 * daftar `sumber` dari server) dan catatan opsional. Isi ulang yang masih terbuka, rekening tanpa dana tetap, atau tidak
 * perlu diisi ulang → tombol kirim nonaktif dengan kalimat server `alasan_isi_ulang` (sama dengan penolakan rute).
 * Kirim `POST …/{id}/isi-ulang` `{sumber_account_id, catatan?, nominal_dilihat}` lewat `moneyPost` + `useIntentKey`
 * (`nominal_dilihat` = angka yang ditampilkan; usulan berubah → 409 server); galat server tampil di dalam pop-up dan posisi
 * dimuat ulang. Hasilnya Pindah Dana bertanda isi ulang: selesai, atau menunggu orang kedua (`kontrol.pindah_dana`) di Pindah Dana.
 * Izin: pemanggil hanya membuka pop-up ini untuk pemegang `cash.create`.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCcw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import { useEntityScope } from "../../context/EntityScopeContext";
import useIntentKey from "../../hooks/useIntentKey";
import { apiErrorText } from "../../utils/apiError";
import { entityShortById } from "../../utils/entityLabel";
import { formatCurrency, formatDate } from "../../utils/formatters";
import { moneyPost } from "../../utils/moneyRequest";
import { labelSumber } from "../finance/jenisKas";

export const TEKS_RUMUS = "Nominal = dana tetap − saldo buku − sisa panjar di tangan karyawan; dihitung ulang sistem saat "
  + "disimpan.";
export const TEKS_TANPA_SUMBER = "PT ini belum punya rekening bank atau kas besar aktif untuk sumber isi ulang. "
  + "Tambahkan di Rekening & Saldo.";

function Angka({ label, value, testId, strong = false }) {
  return (
    <div className="min-w-0 rounded-md border border-kn-divider px-2.5 py-1.5">
      <dt className="text-fs-12 text-kn-text-2">{label}</dt>
      <dd className={`tabular-nums ${strong ? "text-fs-14 font-bold text-kn-text" : "text-fs-13 font-semibold text-kn-text"}`}
        data-testid={testId}>{formatCurrency(value)}</dd>
    </div>
  );
}

export default function IsiUlangModal({ open, accountId, accountName = "", onClose, onSaved }) {
  const { entities = [] } = useEntityScope() || {};
  const [pos, setPos] = useState(null);
  const [muat, setMuat] = useState("memuat");   // memuat | siap | galat
  const [sumber, setSumber] = useState("");
  const [catatan, setCatatan] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const intent = useIntentKey("isiulang");
  const hidup = useRef(true);
  useEffect(() => { hidup.current = true; return () => { hidup.current = false; }; }, []);

  const muatPosisi = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/kas-kecil/dana-tetap/${accountId}`);
      if (!hidup.current) return;
      const p = r.data || null;
      setPos(p);
      setMuat("siap");
      const daftar = p?.sumber || [];
      setSumber((s) => (daftar.length === 1 ? daftar[0].id : daftar.some((x) => x.id === s) ? s : ""));
    } catch (e) {
      if (!hidup.current) return;
      setPos(null);
      setMuat("galat");
      setErr(apiErrorText(e, "Posisi dana tetap belum bisa dimuat."));
    }
  }, [accountId]);

  useEffect(() => {
    if (!open || !accountId) return;
    setErr(""); setCatatan(""); setSumber(""); setPos(null); setMuat("memuat");
    muatPosisi();
  }, [open, accountId, muatPosisi]);

  const nama = pos?.account_name || accountName || "kas kecil";
  const bisa = Boolean(pos?.bisa_isi_ulang);
  const daftarSumber = pos?.sumber || [];
  const sumberDoc = daftarSumber.find((s) => s.id === sumber);
  const menunggu = pos?.isi_ulang_menunggu;
  const lama = pos?.panjar_tanpa_rekening;
  const pt = pos?.entity_id ? entityShortById(entities, pos.entity_id, "PT ini") : "PT ini";

  async function simpan() {
    if (busy || !bisa || !sumber) return;
    setBusy(true);
    setErr("");
    // `nominal_dilihat` = usulan yang DITAMPILKAN (bukan nominal klien — server tetap menghitung ulang): bila usulan
    // berubah sejak dimuat (kas di sela), server menolak 409 "Usulan berubah, muat ulang" alih-alih menerbitkan nominal
    // lain tanpa diberi tahu (tinjauan akhir Minor 5 / N5). Galat tampil di pop-up dan posisi dimuat ulang (`catch`).
    const body = { sumber_account_id: sumber, ...(catatan.trim() ? { catatan: catatan.trim() } : {}),
      nominal_dilihat: Number(pos?.usulan_isi_ulang) || 0 };
    try {
      const r = await intent.send(body, (k) => moneyPost(`${API}/kas-kecil/dana-tetap/${accountId}/isi-ulang`, body, k));
      onSaved?.(r.data);
    } catch (e) {
      setErr(apiErrorText(e, "Isi ulang belum bisa dicatat."));
      await muatPosisi();
    } finally {
      if (hidup.current) setBusy(false);
    }
  }

  return (
    <FormModal open={open} onClose={onClose} title={`Isi ulang ${nama}`} icon={RefreshCcw} size="md" testId="refill-form"
      subtitle="Pindah Dana dari rekening bank atau kas besar PT yang sama ke rekening kas kecil ini."
      onSubmit={simpan} submitLabel="Isi ulang" submitTestId="refill-form-submit" cancelTestId="refill-form-cancel"
      busy={busy} error={err} submitDisabled={muat !== "siap" || !bisa || !sumber}>
      {muat === "memuat" && (
        <p className="text-fs-13 text-kn-text-2" role="status" data-testid="refill-loading">Memuat posisi dana tetap…</p>
      )}
      {pos && (
        <div className="grid gap-3">
          <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="refill-position">
            <Angka label="Dana tetap" value={pos.dana_tetap} testId="refill-dana-tetap" />
            <Angka label="Saldo buku" value={pos.saldo_buku} testId="refill-saldo" />
            <Angka label="Sisa panjar" value={pos.panjar_belum_lpj} testId="refill-panjar" />
            <Angka label="Nominal isi ulang" value={pos.usulan_isi_ulang} testId="refill-amount" strong />
          </dl>
          <p className="text-fs-12 text-kn-text-2">{TEKS_RUMUS}</p>
          {Number(lama?.jumlah) > 0 && (
            <p className="text-fs-12 text-kn-warning-text" data-testid="refill-old-advances">
              {lama.jumlah} panjar lama tanpa rekening ({formatCurrency(lama.total)}{lama.nomor?.length ? ` · ${lama.nomor.join(", ")}` : ""})
              tidak dihitung ke rekening mana pun — periksa sebelum mengisi ulang.
            </p>
          )}
          {menunggu && (
            <p className="text-fs-12 text-kn-text" data-testid="refill-pending">
              Isi ulang terbuka: <b className="font-mono">{menunggu.number}</b> · {menunggu.status_label}
              {" · "}<span className="tabular-nums">{formatCurrency(menunggu.nominal)}</span>
              {menunggu.rekening_asal_nama ? ` dari ${menunggu.rekening_asal_nama}` : ""}
              {menunggu.tanggal ? ` · ${formatDate(menunggu.tanggal)}` : ""}
            </p>
          )}
          {!bisa ? (
            <p className="text-fs-13 font-semibold text-kn-warning-text" data-testid="refill-reason">{pos.alasan_isi_ulang}</p>
          ) : daftarSumber.length === 0 ? (
            <p className="text-fs-13 font-semibold text-kn-warning-text" data-testid="refill-no-source">{TEKS_TANPA_SUMBER}</p>
          ) : (
            <>
              <div>
                <label className="field-label">Dari rekening <span className="req">*</span></label>
                <KNSelect data-testid="refill-source" className="field" value={sumber} placeholder="Pilih rekening sumber"
                  options={daftarSumber.map((s) => ({ value: s.id, label: labelSumber(s) }))} onValueChange={(v) => setSumber(v || "")} />
              </div>
              <div>
                <label className="field-label">Catatan</label>
                <input data-testid="refill-note" className="field" maxLength={500} value={catatan}
                  onChange={(e) => setCatatan(e.target.value)} placeholder={`Isi ulang dana tetap ${nama}`} />
              </div>
              {sumberDoc && (
                <p className="rounded-md border border-kn-divider px-3 py-2 text-fs-13 text-kn-text" data-testid="refill-summary">
                  <b className="tabular-nums">{formatCurrency(pos.usulan_isi_ulang)}</b> dipindah dari <b>{sumberDoc.name}</b> ke{" "}
                  <b>{nama}</b> di {pt}. Bila Pindah Dana perlu disetujui orang kedua, isi ulang menunggu di Kas &amp; Bank ›
                  Pindah Dana.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </FormModal>
  );
}
