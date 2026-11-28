/**
 * CashCountForm — Kas & Bank bagian 3 (Tugas 4b): satu pop-up `FormModal` "Hitung kas" (opname kas, spesifikasi §5.3).
 *
 * Isian: rekening tunai aktif (`GET /api/bank-accounts`, `account_type="cash"`; rekening bank dicocokkan lewat
 * Rekonsiliasi Bank), jumlah uang fisik ATAU rincian pecahan opsional (lembar × pecahan, menjumlah ke total — jumlah fisik
 * lalu terkunci = total), catatan. **Hitung buta:** saldo buku TIDAK ditampilkan sebelum disimpan (pilihan rekening tanpa
 * saldo) — server memotretnya saat hitungan disimpan; sesudah tersimpan pop-up yang sama menampilkan nomor `OPK-`, saldo
 * buku, uang fisik, selisih, dan langkah berikutnya (tanpa selisih = selesai; ada selisih = menunggu orang kedua).
 * Kirim `POST /api/cash-counts` lewat `moneyPost` + `useIntentKey` (awalan `/api/cash-counts` berkunci idempotensi).
 * Galat server (mis. 409 "masih menunggu keputusan selisih") tampil di dalam pop-up.
 *
 * Dipakai di Kas & Bank › Opname Kas (tombol Hitung, preset `hitung` dari kartu rekening) dan di Meja Keuangan (baris
 * "Opname kas jatuh tempo" — aksi di tempat). `accountId` = rekening terpilih awal; `onSaved(doc)` dipanggil begitu
 * server menerima hitungan (daftar/meja dimuat ulang), pop-up tetap terbuka menampilkan hasilnya sampai ditutup.
 */
import { useEffect, useMemo, useState } from "react";
import { Calculator, ListOrdered } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import MoneyInput from "@/components/MoneyInput";
import EntityScopeBanner from "../../../components/EntityScopeBanner";
import { useEntityScope } from "../../../context/EntityScopeContext";
import useIntentKey from "../../../hooks/useIntentKey";
import { moneyPost } from "../../../utils/moneyRequest";
import { apiErrorText } from "../../../utils/apiError";
import { entityShortById } from "../../../utils/entityLabel";
import { formatCurrency, formatDateTime } from "../../../utils/formatters";
import {
  MENUNGGU, PECAHAN_RUPIAH, badanHitung, labelRekeningTunai, rekeningTunai, selisihNada, selisihTeks, totalPecahan,
  validasiHitung,
} from "./cashCountShared";

const KOSONG = { account_id: "", jumlah_fisik: "", catatan: "", pakaiPecahan: false, lembar: {} };

export default function CashCountForm({ open, onClose, onSaved, entityId = "", accountId = "" }) {
  const { entities = [] } = useEntityScope() || {};
  const scoped = Boolean(entityId) && entityId !== "all";
  const [form, setForm] = useState(KOSONG);
  const [rekening, setRekening] = useState([]);
  const [muat, setMuat] = useState("memuat");   // memuat | siap | galat
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [hasil, setHasil] = useState(null);     // opname yang baru tersimpan (jawaban server)
  const intent = useIntentKey("opk");
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  useEffect(() => {
    if (!open) return undefined;
    let hidup = true;
    setForm({ ...KOSONG, account_id: accountId || "" });
    setErr("");
    setHasil(null);
    setMuat("memuat");
    axios.get(`${API}/bank-accounts`, { params: scoped ? { entity_id: entityId } : {} })
      .then((r) => {
        if (!hidup) return;
        const list = rekeningTunai(r.data).filter((a) => a.is_active !== false && (!scoped || a.entity_id === entityId));
        setRekening(list);
        setMuat("siap");
        // Rekening awal yang tidak bisa dihitung (bank / nonaktif / PT lain) tidak dipilihkan.
        if (accountId && !list.some((a) => a.id === accountId)) set({ account_id: "" });
      })
      // Galat tidak ditelan menjadi "belum ada rekening": pop-up menulis galatnya dan tombol simpan nonaktif.
      .catch((e) => { if (hidup) { setMuat("galat"); setErr(apiErrorText(e, "Rekening tunai belum bisa dimuat.")); } });
    return () => { hidup = false; };
  }, [open, entityId, accountId, scoped]);

  const opsi = useMemo(() => rekening.map((a) => ({
    value: a.id, label: labelRekeningTunai(a, scoped ? "" : entityShortById(entities, a.entity_id, "")) })),
  [rekening, scoped, entities]);
  const total = totalPecahan(form.lembar);
  const loaded = muat === "siap";   // memuat & galat dibedakan dari "belum ada rekening tunai"

  async function simpan() {
    if (busy) return;
    const salah = validasiHitung(form);
    if (salah) { setErr(salah); return; }
    setBusy(true);
    setErr("");
    const body = badanHitung(form);
    try {
      const r = await intent.send(body, (k) => moneyPost(`${API}/cash-counts`, body, k));
      setHasil(r.data || null);
      onSaved?.(r.data || null);
    } catch (e) {
      setErr(apiErrorText(e, "Hitungan kas belum bisa disimpan."));
    } finally { setBusy(false); }
  }

  if (hasil) {
    return (
      <FormModal open={open} onClose={onClose} title={`Opname ${hasil.number || ""} tercatat`} icon={Calculator} size="md"
        testId="opk-form" subtitle={hasil.account_name || ""}
        footer={(
          <div className="flex justify-end">
            <button type="button" className="primary-button" data-testid="opk-form-done" onClick={onClose}>Selesai</button>
          </div>
        )}>
        <HasilHitung doc={hasil} />
      </FormModal>
    );
  }

  return (
    <FormModal open={open} onClose={onClose} title="Hitung kas" icon={Calculator} size="md" testId="opk-form"
      subtitle="Hitung uang fisik di rekening tunai; saldo buku dipotret saat hitungan disimpan."
      onSubmit={simpan} submitLabel="Simpan hitungan" submitTestId="opk-form-submit" cancelTestId="opk-form-cancel"
      busy={busy} error={err} submitDisabled={!loaded || rekening.length === 0}>
      <div className="grid gap-3">
        <EntityScopeBanner variant="form" testId="opk-form-scope" className="" />
        {loaded && rekening.length === 0 && (
          <p className="text-fs-12 text-kn-text-2" data-testid="opk-form-no-accounts">
            Belum ada rekening kas tunai aktif{scoped ? " di PT ini" : ""}. Tambahkan rekening tunai di Rekening &amp; Saldo.
          </p>
        )}
        <div>
          <label className="field-label">Rekening tunai <span className="req">*</span></label>
          <KNSelect data-testid="opk-form-account" className="field" value={form.account_id} placeholder="Pilih rekening tunai"
            options={opsi} onValueChange={(v) => set({ account_id: v || "" })} />
        </div>
        {form.pakaiPecahan ? (
          <RincianPecahan lembar={form.lembar} total={total} onChange={(lembar) => set({ lembar })}
            onTutup={() => set({ pakaiPecahan: false, jumlah_fisik: total > 0 ? String(total) : form.jumlah_fisik })} />
        ) : (
          <div>
            <label className="field-label">Jumlah uang fisik (Rp) <span className="req">*</span></label>
            <MoneyInput testId="opk-form-amount" value={form.jumlah_fisik} onChange={(v) => set({ jumlah_fisik: v })} placeholder="0" />
            <button type="button" className="link-button mt-1 inline-flex items-center gap-1" data-testid="opk-form-denoms-toggle"
              onClick={() => set({ pakaiPecahan: true })}>
              <ListOrdered size={13} aria-hidden="true" /> Hitung per pecahan
            </button>
          </div>
        )}
        <div>
          <label className="field-label">Catatan</label>
          <input data-testid="opk-form-note" className="field" maxLength={500} value={form.catatan}
            onChange={(e) => set({ catatan: e.target.value })} placeholder="mis. Hitung tutup toko, disaksikan kepala toko" />
        </div>
      </div>
    </FormModal>
  );
}

/** Rincian pecahan: lembar per pecahan → subtotal; total = jumlah uang fisik (terkunci selama rincian dipakai). */
function RincianPecahan({ lembar, total, onChange, onTutup }) {
  return (
    <div className="grid gap-2 rounded-md border border-kn-divider p-2" data-testid="opk-form-denoms">
      <div className="flex items-center justify-between gap-2">
        <span className="text-fs-12 font-semibold text-kn-text">Rincian pecahan</span>
        <button type="button" className="link-button" data-testid="opk-form-denoms-close" onClick={onTutup}>
          Isi jumlah total saja
        </button>
      </div>
      <div className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
        {PECAHAN_RUPIAH.map((nilai) => {
          const n = Math.max(0, Math.floor(Number(lembar[nilai]) || 0));
          return (
            <label key={nilai} className="grid grid-cols-[88px_72px_minmax(0,1fr)] items-center gap-2 text-fs-12 text-kn-text">
              <span className="tabular-nums">{formatCurrency(nilai)}</span>
              <input type="number" min={0} step={1} inputMode="numeric" className="field !h-8 tabular-nums"
                data-testid={`opk-form-denom-${nilai}`} aria-label={`Lembar ${formatCurrency(nilai)}`}
                value={lembar[nilai] ?? ""} placeholder="0"
                onChange={(e) => onChange({ ...lembar, [nilai]: e.target.value })} />
              <span className="text-right tabular-nums text-kn-text-2">{n > 0 ? formatCurrency(nilai * n) : ""}</span>
            </label>
          );
        })}
      </div>
      <p className="flex justify-between border-t border-kn-divider pt-1.5 text-fs-13" data-testid="opk-form-denoms-total">
        <span>Jumlah uang fisik</span><b className="tabular-nums">{formatCurrency(total)}</b>
      </p>
    </div>
  );
}

/** Hasil hitungan dari server: angka yang dipotret + langkah berikutnya. */
export function HasilHitung({ doc }) {
  const menunggu = doc.status === MENUNGGU;
  return (
    <div className="grid gap-3" data-testid="opk-form-result">
      <dl className="grid gap-1 text-fs-13">
        <div className="flex justify-between gap-3" data-testid="opk-form-result-book">
          <dt className="text-kn-text-2">Saldo buku saat dihitung</dt><dd className="tabular-nums">{formatCurrency(doc.saldo_buku)}</dd>
        </div>
        <div className="flex justify-between gap-3" data-testid="opk-form-result-physical">
          <dt className="text-kn-text-2">Uang fisik</dt><dd className="tabular-nums">{formatCurrency(doc.jumlah_fisik)}</dd>
        </div>
        <div className="flex justify-between gap-3 border-t border-kn-divider pt-1" data-testid="opk-form-result-diff">
          <dt className="text-kn-text-2">Selisih</dt><dd className={`font-semibold tabular-nums ${selisihNada(doc)}`}>{selisihTeks(doc)}</dd>
        </div>
      </dl>
      <p className="text-fs-12 text-kn-text-2" data-testid="opk-form-result-next">
        {menunggu
          ? `Opname ${doc.number} menunggu keputusan orang kedua yang berizin menyetujui kas: selisih kas`
            + `${doc.boleh_piutang ? " atau piutang karyawan" : ""}. Kas rekening belum berubah sampai diputuskan.`
          : `Opname ${doc.number} selesai — uang fisik sama dengan saldo buku, tanpa jurnal.`}
        {doc.dihitung_pada ? ` Dihitung ${formatDateTime(doc.dihitung_pada)}.` : ""}
      </p>
    </div>
  );
}
