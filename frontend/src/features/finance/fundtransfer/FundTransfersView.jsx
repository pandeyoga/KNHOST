/**
 * FundTransfersView — Kas & Bank bagian 1 (Tugas 6) · Keuangan › Kas & Bank › Pindah Dana (view `fund-transfers`).
 *
 * Templat daftar (`04_POLA_UI` §2.A): judul satu baris (+ ?) · bilah daftar (cari · Status ▾ · jumlah · Unduh · + Pindah
 * Dana) · tabel nomor, tanggal, asal → tujuan, nominal, biaya, status · aksi baris di kolom kanan · halaman + Unduh.
 * Nomor = `DocLink` → pratinjau dokumen (registri `fund_transfer`, kaki: Jejak + Buka layar penuh).
 *
 * Sumber: `GET /api/fund-transfers` (berhalaman; baris menunggu membawa `kontrol` untuk pengguna — tombol Setujui
 * nonaktif dengan alasan tertulis bila ia pembuatnya). Aksi (izin, bukan peran — `fundTransferShared.aksiPindahDana`):
 * buat & Terima `cash.create`, Batal `cash.delete`, Setujui `cash.approve`. Satu pop-up per aksi: buat = `FormModal`
 * (`FundTransferForm`), Terima = `FormModal` bertanggal, Setujui = `askConfirm` (nominal & PT, N5), Batal = `askReason`
 * (≥ 5 huruf; "Teruskan pembatalan" yang terhenti = `askConfirm` dengan alasan yang sudah tercatat). Semua kirim
 * lewat `moneyPost` + `useIntentKey` (N4). Galat aksi tampil di bilah galat layar / di pop-up.
 * Tautan masuk: antrean persetujuan & butir tutup buku (preset `{status}`), Posting Gagal & Jejak (`focusDoc`
 * `fund_transfer` → pratinjau dokumennya).
 */
import { useMemo, useState } from "react";
import { ArrowDownLeft, ArrowRight, ArrowRightLeft, Check, Plus, XCircle } from "lucide-react";
import { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import EntityScopeBanner from "../../../components/EntityScopeBanner";
import EntityGatedButton from "../../../components/EntityGatedButton";
import FocusNotice from "../../../components/FocusNotice";
import FormModal from "../../../components/FormModal";
import KNDatePicker from "../../../components/KNDatePicker";
import KNSelect from "../../../components/KNSelect";
import PaginationBar from "../../../components/PaginationBar";
import StatusBadge from "../../../components/StatusBadge";
import { ListToolbar, PageHeader, SearchInput } from "../../../components/ListPageParts";
import { can } from "../../../config/roles";
import { useAppNav } from "../../../context/AppNavContext";
import { useEntityScope } from "../../../context/EntityScopeContext";
import useFocusDoc from "../../../hooks/useFocusDoc";
import useIntentKey from "../../../hooks/useIntentKey";
import { usePagedList } from "../../../hooks/usePagedList";
import useViewPreset from "../../../hooks/useViewPreset";
import { askConfirm, askReason } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";
import { entityShortById } from "../../../utils/entityLabel";
import { notifySuccess } from "../../../utils/feedback";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { moneyPost } from "../../../utils/moneyRequest";
import DocLink from "../../documents/preview/DocLink";
import FundTransferForm from "./FundTransferForm";
import { ALASAN_MIN, PILIHAN_STATUS, aksiPindahDana, statusPindahDana } from "./fundTransferShared";

export const TEKS_BANTU = "Pindah Dana mencatat uang yang pindah antar dua rekening PT yang sama: setor tunai ke bank, "
  + "isi kas kecil, atau pindah antar bank. Kas keluar rekening asal dan kas masuk rekening tujuan tercatat berpasangan; "
  + "biaya transfer dibebankan ke rekening asal. Bila uang tiba belakangan, dokumen berstatus Dalam perjalanan sampai "
  + "dicatat Terima. Pindah dana antar-PT dicatat lewat menu Antar-PT.";

const CSV = [
  { key: "number", header: "Nomor" },
  { key: "tanggal_kirim", header: "Tanggal kirim", type: "date" },
  { key: "rekening_asal", header: "Dari" },
  { key: "rekening_tujuan", header: "Ke" },
  { key: "nominal", header: "Nominal", type: "num" },
  { key: "biaya", header: "Biaya transfer", type: "num" },
  { header: "Status", get: (d) => statusPindahDana(d.status).label },
  { key: "catatan", header: "Catatan" },
];

export default function FundTransfersView({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  const perms = currentUser?.permissions;
  const nav = useAppNav();
  const { entities = [] } = useEntityScope() || {};
  const scoped = Boolean(selectedEntity) && selectedEntity !== "all";
  const pt = entityShortById(entities, selectedEntity, "PT ini");
  const [status, setStatus] = useState("");
  const [cari, setCari] = useState("");
  const [buat, setBuat] = useState(false);
  const [terima, setTerima] = useState(null);   // dokumen yang sedang dicatat Terima
  const [err, setErr] = useState("");
  const [sibukId, setSibukId] = useState("");
  const intent = useIntentKey("pdna");

  useViewPreset("fund-transfers", (p) => { if (p.status !== undefined) setStatus(p.status || ""); });
  const params = useMemo(() => ({ ...(scoped ? { entity_id: selectedEntity } : {}), ...(status ? { status } : {}) }),
    [scoped, selectedEntity, status]);
  const paged = usePagedList("/fund-transfers", { pageSize: 25, params, search: cari });
  const rows = paged.items || [];

  const fokus = useFocusDoc(focusDoc, "fund_transfer", (id, fd) => {
    setStatus("");
    if (fd.number) setCari(fd.number);
    nav.openDocPreview({ docType: "fund_transfer", docId: id, ...(fd.number ? { number: fd.number } : {}) });
    return true;
  }, onClearFocus);

  /** Satu aksi dokumen → "" bila berhasil, kalimat galat bila ditolak. Galat aksi dari pop-up tampil di pop-up itu. */
  async function kirim(d, aksi, body, pesan, { diPopup = false } = {}) {
    setSibukId(d.id);
    setErr("");
    try {
      const r = await intent.send({ id: d.id, aksi, ...body }, (k) => moneyPost(`${API}/fund-transfers/${d.id}/${aksi}`, body, k));
      notifySuccess(pesan(r.data || d));
      await paged.refresh();
      return "";
    } catch (e) {
      const teks = apiErrorText(e, "Pindah Dana belum bisa diproses.");
      if (!diPopup) setErr(teks);
      await paged.refresh();
      return teks;
    } finally { setSibukId(""); }
  }

  async function setujui(d) {
    const ok = await askConfirm({
      title: `Setujui Pindah Dana ${d.number}?`, confirmLabel: "Setujui", testId: "ft-approve-confirm",
      message: `${formatCurrency(d.nominal)} dari ${d.rekening_asal} ke ${d.rekening_tujuan} (${entityShortById(entities, d.entity_id, pt)})`
        + `${Number(d.biaya) > 0 ? `, biaya transfer ${formatCurrency(d.biaya)}` : ""}. `
        + (d.dua_tahap ? "Kas keluar rekening asal tercatat; dana dalam perjalanan sampai dicatat Terima."
          : "Kas keluar dan kas masuk langsung tercatat."),
    });
    if (ok) await kirim(d, "approve", {}, (x) => `Pindah Dana ${x.number} disetujui — ${statusPindahDana(x.status).label.toLowerCase()}.`);
  }

  async function batal(d) {
    const ringkas = `${formatCurrency(d.nominal)} dari ${d.rekening_asal} ke ${d.rekening_tujuan}. `;
    if (d.status === "batal") {
      // Tinjauan akhir Minor 8 — meneruskan pembatalan yang terhenti memakai alasan yang sudah tercatat (server
      // mengabaikan alasan baru), jadi cukup konfirmasi yang menyebut alasan itu.
      const ok = await askConfirm({
        title: `Teruskan pembatalan ${d.number}?`, danger: true, confirmLabel: "Teruskan", testId: "ft-cancel-resume",
        message: `${ringkas}Kas dokumen ini yang belum dibalik dibalik sekarang dengan alasan yang sudah tercatat: `
          + `"${d.alasan_batal || "—"}".`,
      });
      if (ok) await kirim(d, "cancel", { alasan: d.alasan_batal || "Teruskan pembatalan" }, (x) => `Pembatalan ${x.number} diteruskan.`);
      return;
    }
    const alasan = await askReason({
      title: `Batalkan Pindah Dana ${d.number}?`, danger: true,
      message: ringkas
        + (d.status === "menunggu_persetujuan" && !Object.keys(d.kas_ids || {}).length
          ? "Kasnya belum terbit, jadi dokumen cukup ditandai batal."
          : "Semua kas dokumen ini dibalik dengan jurnal pembalik; ditolak bila salah satunya sudah dicocokkan dengan "
            + "mutasi bank (lepas dulu di Rekonsiliasi)."),
      reasonLabel: "Alasan pembatalan", reasonMinLength: ALASAN_MIN, confirmLabel: "Batalkan",
      testId: "ft-cancel-reason",
    });
    if (alasan === null || alasan === undefined) return;
    await kirim(d, "cancel", { alasan }, (x) => `Pindah Dana ${x.number} dibatalkan.`);
  }

  return (
    <div className="space-y-3" data-testid="fund-transfers-view">
      <PageHeader icon={ArrowRightLeft} title="Pindah Dana" help={TEKS_BANTU} testId="ft-header" />
      <EntityScopeBanner testId="ft-scope" />
      <FocusNotice {...fokus} testId="ft-focus-notice" />
      <ErrorNotice message={err} onDismiss={() => setErr("")} testId="ft-error" />
      <ListToolbar testId="ft-toolbar"
        count={paged.total > 0 ? <span data-testid="ft-count">{paged.total} dokumen</span> : null}
        actions={can(perms, "cash", "create") ? (
          <EntityGatedButton selectedEntity={selectedEntity} what="mencatat Pindah Dana" data-testid="ft-create"
            className="primary-button whitespace-nowrap" onClick={() => setBuat(true)}>
            <Plus size={14} aria-hidden="true" /> Pindah Dana
          </EntityGatedButton>
        ) : null}>
        <SearchInput testId="ft-search" placeholder="Cari nomor, rekening, atau catatan" value={cari} onChange={setCari}
          className="min-w-[200px] flex-1 sm:max-w-[300px]" />
        <KNSelect data-testid="ft-status" aria-label="Status" className="field !w-auto min-w-[180px]" value={status}
          options={PILIHAN_STATUS} onValueChange={(v) => setStatus(v || "")} />
      </ListToolbar>

      <div className="section-card" data-testid="ft-list">
        {paged.error ? (
          <div className="section-pad"><ErrorNotice message={paged.error} onRetry={paged.refresh} testId="ft-list-error" /></div>
        ) : paged.loading && rows.length === 0 ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="ft-loading">Memuat Pindah Dana…</div>
        ) : rows.length === 0 ? (
          <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="ft-empty">
            {cari.trim() || status ? "Tidak ada Pindah Dana yang cocok dengan saringan." : "Belum ada Pindah Dana."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="ft-table">
              <thead><tr>
                <th>Nomor</th><th>Tanggal</th><th>Dari → Ke</th><th className="text-right">Nominal</th>
                <th className="text-right">Biaya</th><th>Status</th><th className="col-sticky-end text-right">Aksi</th>
              </tr></thead>
              <tbody>
                {rows.map((d) => {
                  const st = statusPindahDana(d.status);
                  const aksi = aksiPindahDana(d, perms);
                  const mati = sibukId === d.id;
                  return (
                    <tr key={d.id} data-testid={`ft-row-${d.id}`}>
                      <td className="whitespace-nowrap">
                        <DocLink docType="fund_transfer" docId={d.id} number={d.number} entityId={d.entity_id} perms={perms}
                          className="font-mono font-semibold" testId={`ft-open-${d.id}`} />
                        {!scoped && <span className="block text-fs-12 text-kn-text-2">{entityShortById(entities, d.entity_id, "")}</span>}
                      </td>
                      <td className="whitespace-nowrap">
                        {formatDate(d.tanggal_kirim)}
                        {d.dua_tahap && (
                          <span className="block text-fs-12 text-kn-text-2" data-testid={`ft-receive-plan-${d.id}`}>
                            {d.tanggal_diterima ? `diterima ${formatDate(d.tanggal_diterima)}` : `tiba ${formatDate(d.tanggal_terima)}`}
                          </span>
                        )}
                      </td>
                      <td className="min-w-[200px]">
                        <span className="inline-flex flex-wrap items-center gap-1">
                          {d.rekening_asal}<ArrowRight size={12} aria-label="ke" className="text-kn-text-2" />{d.rekening_tujuan}
                        </span>
                        {d.catatan && <span className="block text-fs-12 text-kn-text-2">{d.catatan}</span>}
                        {/* Kas & Bank 3 — isi ulang kas kecil: nominal dihitung sistem dari posisi dana tetap */}
                        {d.jenis_label && (
                          <span className="mt-0.5 block"><StatusBadge tone="special" icon="tag" label={d.jenis_label} testId={`ft-kind-${d.id}`} /></span>
                        )}
                      </td>
                      <td className="text-right tabular-nums font-semibold">{formatCurrency(d.nominal)}</td>
                      <td className="text-right tabular-nums">{Number(d.biaya) > 0 ? formatCurrency(d.biaya) : "—"}</td>
                      <td>
                        <StatusBadge status={d.status} label={st.label} tone={st.tone} icon={st.icon} testId={`ft-status-${d.id}`} />
                        {d.terbit_error && d.status === "menunggu_persetujuan" && (
                          <span className="mt-0.5 block max-w-[220px] text-fs-12 text-kn-danger-text" data-testid={`ft-publish-error-${d.id}`}>
                            Kas belum terbit: {d.terbit_error}
                          </span>
                        )}
                        {d.batal_tertunda && d.batal_gl_error && (
                          <span className="mt-0.5 block max-w-[220px] text-fs-12 text-kn-danger-text">{d.batal_gl_error}</span>
                        )}
                      </td>
                      <td className="col-sticky-end text-right">
                        <BarisAksi d={d} aksi={aksi} mati={mati} onSetujui={() => setujui(d)} onTerima={() => setTerima(d)}
                          onBatal={() => batal(d)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!paged.error && paged.total > 0 && (
          <div className="px-3 pb-3">
            <PaginationBar page={paged.page} pageSize={paged.pageSize} total={paged.total} hasMore={paged.hasMore}
              loading={paged.loading} onPrev={paged.prev} onNext={paged.next} testId="ft-pager" label="Pindah Dana"
              exportConfig={{ columns: CSV, rows, fetchAll: paged.fetchAll, filename: "pindah-dana" }}
              exportSpec={{ dataset: "fund_transfers", label: "pindah-dana", search: cari,
                filters: [["status", "eq", status]], sort: [{ key: "tanggal_kirim", dir: "desc" }] }} />
          </div>
        )}
      </div>

      <FundTransferForm open={buat && scoped} onClose={() => setBuat(false)} entityId={scoped ? selectedEntity : ""}
        entityLabel={pt} onSaved={async (doc) => {
          setBuat(false);
          notifySuccess(`Pindah Dana ${doc?.number || ""} dicatat — ${statusPindahDana(doc?.status).label.toLowerCase()}.`);
          await paged.refresh();
        }} />
      {terima && (
        <TerimaModal key={terima.id} doc={terima} onClose={() => setTerima(null)}
          onTerima={async (d, tanggal) => {
            const salah = await kirim(d, "receive", { tanggal },
              (x) => `Dana Pindah Dana ${x.number} diterima ${x.rekening_tujuan}.`, { diPopup: true });
            if (!salah) setTerima(null);
            return salah;
          }} />
      )}
    </div>
  );
}

function BarisAksi({ d, aksi, mati, onSetujui, onTerima, onBatal }) {
  const alasan = [aksi.setujui, aksi.terima, aksi.batal].map((a) => a?.alasan).find(Boolean) || "";
  return (
    <div className="flex flex-col items-end gap-1" data-testid={`ft-actions-${d.id}`}>
      <div className="flex flex-wrap justify-end gap-1.5">
        {aksi.setujui && (
          <button type="button" className="primary-button btn-sm" data-testid={`ft-approve-${d.id}`}
            disabled={mati || Boolean(aksi.setujui.alasan)} onClick={onSetujui}>
            <Check size={13} aria-hidden="true" />{aksi.setujui.label}
          </button>
        )}
        {aksi.terima && (
          <button type="button" className="primary-button btn-sm" data-testid={`ft-receive-${d.id}`}
            disabled={mati || Boolean(aksi.terima.alasan)} onClick={onTerima}>
            <ArrowDownLeft size={13} aria-hidden="true" />{aksi.terima.label}
          </button>
        )}
        {aksi.batal && (
          <button type="button" className="secondary-button btn-sm text-kn-danger-text" data-testid={`ft-cancel-${d.id}`}
            disabled={mati || Boolean(aksi.batal.alasan)} onClick={onBatal}>
            <XCircle size={13} aria-hidden="true" />{aksi.batal.label}
          </button>
        )}
      </div>
      {(alasan || aksi.catatan) && (
        // Sel aksi `text-right` mewarisi `white-space: nowrap` (kolom angka) — kalimat alasan dibungkus sendiri.
        <span className="max-w-[260px] whitespace-normal break-words text-left text-fs-12 text-kn-text-2" data-testid={`ft-action-note-${d.id}`}>
          {alasan || aksi.catatan}
        </span>
      )}
    </div>
  );
}

/** Satu pop-up "Terima dana": tanggal uang masuk rekening tujuan (bawaan = rencana, tidak sebelum tanggal kirim). */
function TerimaModal({ doc, onClose, onTerima }) {
  const [tanggal, setTanggal] = useState(doc.tanggal_terima || "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <FormModal open onClose={onClose} title={`Terima Pindah Dana ${doc.number}`} icon={ArrowDownLeft} size="sm" testId="ft-receive-form"
      subtitle={`${formatCurrency(doc.nominal)} masuk ${doc.rekening_tujuan}`} submitLabel="Catat diterima"
      submitTestId="ft-receive-submit" busy={busy} error={err} submitDisabled={!tanggal}
      onSubmit={async () => {
        if (tanggal < doc.tanggal_kirim) { setErr("Tanggal terima tidak boleh sebelum tanggal kirim."); return; }
        setBusy(true);
        setErr((await onTerima(doc, tanggal)) || "");
        setBusy(false);
      }}>
      <div className="grid gap-2">
        <label className="field-label">Tanggal dana masuk <span className="req">*</span></label>
        <KNDatePicker data-testid="ft-receive-date" value={tanggal} min={doc.tanggal_kirim} clearable={false} onChange={setTanggal} />
        <p className="text-fs-12 text-kn-text-2">
          Dikirim {formatDate(doc.tanggal_kirim)} dari {doc.rekening_asal}. Kas masuk {doc.rekening_tujuan} dicatat pada tanggal ini.
        </p>
      </div>
    </FormModal>
  );
}
