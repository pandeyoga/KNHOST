/**
 * CashCountApproveModal — Kas & Bank bagian 3 (Tugas 4b): satu pop-up `FormModal` "Setujui selisih opname" (§5.3).
 *
 * Isi: angka yang dipotret saat dihitung (rekening, saldo buku, uang fisik, selisih lebih/kurang, penghitung), pilihan
 * **perlakuan** (selisih kas; piutang karyawan hanya untuk kekurangan kas — `boleh_piutang` server), pemilih karyawan HR
 * PT pemilik rekening (`GET /api/cash-counts/karyawan?entity_id=` — `cash.approve`, tanpa izin SDM) bila piutang
 * karyawan, dan ringkasan dampak (nominal, arah kas, rekening, akun lawan, tanggal hitung — pola N5) di atas tombol kirim.
 * Kirim `POST /api/cash-counts/{id}/approve {perlakuan, karyawan_id}` lewat `onSetujui` (pemanggil memakai `moneyPost` +
 * `useIntentKey`); galat server (409 periode tertutup / digantikan / 403 kontrol dua orang) tampil di pop-up ini.
 */
import { useEffect, useMemo, useState } from "react";
import { Check } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency, formatDateTime } from "../../../utils/formatters";
import { opsiPerlakuan, ringkasanSetujui, selisihNada, selisihTeks } from "./cashCountShared";

export default function CashCountApproveModal({ doc, onClose, onSetujui }) {
  const opsi = useMemo(() => opsiPerlakuan(doc), [doc]);
  // Setujui ulang (kas penyesuaian sudah tercatat sebelumnya) memakai perlakuan & karyawan yang sama — server menolak
  // perlakuan lain dengan 409 berkalimat; pilihan yang sudah tercatat di dokumen dipakai sebagai isian awal.
  const awal = opsi.some((o) => o.value === doc.perlakuan) ? doc.perlakuan : (opsi.length === 1 ? opsi[0].value : "");
  const [perlakuan, setPerlakuan] = useState(awal);
  const [karyawanId, setKaryawanId] = useState(awal === "piutang_karyawan" ? doc.karyawan_id || "" : "");
  const [karyawan, setKaryawan] = useState(null);   // null = belum dimuat
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const piutang = perlakuan === "piutang_karyawan";

  useEffect(() => {
    if (!piutang || karyawan !== null) return undefined;
    let hidup = true;
    axios.get(`${API}/cash-counts/karyawan`, { params: { entity_id: doc.entity_id } })
      .then((r) => { if (hidup) setKaryawan(Array.isArray(r.data) ? r.data : []); })
      .catch((e) => { if (hidup) { setKaryawan([]); setErr(apiErrorText(e, "Daftar karyawan belum bisa dimuat.")); } });
    return () => { hidup = false; };
  }, [piutang, karyawan, doc.entity_id]);

  const opsiKaryawan = (karyawan || []).map((k) => ({ value: k.id, label: k.code ? `${k.name} · ${k.code}` : k.name }));
  const terpilih = (karyawan || []).find((k) => k.id === karyawanId) || null;
  const siap = Boolean(perlakuan) && (!piutang || Boolean(karyawanId));
  const ringkas = ringkasanSetujui(doc, perlakuan, terpilih);

  async function kirim() {
    if (busy || !siap) return;
    setBusy(true);
    setErr("");
    const salah = await onSetujui(doc, { perlakuan, karyawan_id: piutang ? karyawanId : "" });
    setErr(salah || "");
    setBusy(false);
  }

  return (
    <FormModal open onClose={onClose} title={`Setujui selisih opname ${doc.number}`} icon={Check} size="sm" testId="opk-approve-form"
      subtitle={`${doc.account_name || "Rekening tunai"} · dihitung ${doc.penghitung?.name || doc.created_by || "—"}`
        + `${doc.dihitung_pada ? `, ${formatDateTime(doc.dihitung_pada)}` : ""}`}
      submitLabel={doc.terbit_error ? "Setujui lagi" : "Setujui"} submitTestId="opk-approve-submit" busy={busy} error={err}
      submitDisabled={!siap} onSubmit={kirim}>
      <div className="grid gap-3">
        <dl className="grid gap-1 text-fs-13" data-testid="opk-approve-facts">
          <div className="flex justify-between gap-3"><dt className="text-kn-text-2">Saldo buku saat dihitung</dt>
            <dd className="tabular-nums">{formatCurrency(doc.saldo_buku)}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-kn-text-2">Uang fisik</dt>
            <dd className="tabular-nums">{formatCurrency(doc.jumlah_fisik)}</dd></div>
          <div className="flex justify-between gap-3 border-t border-kn-divider pt-1"><dt className="text-kn-text-2">Selisih</dt>
            <dd className={`font-semibold tabular-nums ${selisihNada(doc)}`}>{selisihTeks(doc)}</dd></div>
        </dl>
        {doc.terbit_error && (
          <p className="text-fs-12 text-kn-danger-text" data-testid="opk-approve-publish-error">Kas belum terbit: {doc.terbit_error}</p>
        )}
        <div>
          <label className="field-label">Perlakuan selisih <span className="req">*</span></label>
          <KNSelect data-testid="opk-approve-treatment" className="field" value={perlakuan} placeholder="Pilih perlakuan"
            options={opsi} onValueChange={(v) => { setPerlakuan(v || ""); setErr(""); }} />
          {!doc.boleh_piutang && (
            <p className="mt-1 text-fs-12 text-kn-text-2">Kelebihan kas dibukukan sebagai selisih kas; piutang karyawan hanya untuk kekurangan.</p>
          )}
        </div>
        {piutang && (
          <div>
            <label className="field-label">Karyawan yang menanggung <span className="req">*</span></label>
            <KNSelect data-testid="opk-approve-employee" className="field" value={karyawanId}
              placeholder={karyawan === null ? "Memuat karyawan…" : "Pilih karyawan"} disabled={karyawan === null}
              options={opsiKaryawan} onValueChange={(v) => setKaryawanId(v || "")} />
            {karyawan !== null && karyawan.length === 0 && !err && (
              <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="opk-approve-no-employee">
                Belum ada karyawan aktif di PT ini (SDM › Karyawan).
              </p>
            )}
          </div>
        )}
        {ringkas && (
          <p className="rounded-md border border-kn-divider px-3 py-2 text-fs-13 text-kn-text" data-testid="opk-approve-summary">{ringkas}</p>
        )}
      </div>
    </FormModal>
  );
}
