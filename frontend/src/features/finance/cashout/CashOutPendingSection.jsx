/**
 * CashOutPendingSection — Kas & Bank bagian 2 (Tugas 4) · Kas & Bank › Transaksi Kas, bagian "Menunggu persetujuan".
 *
 * Pengajuan kas keluar manual di atas batas PT (`cash_out_requests`, nomor `PKK-`) yang menunggu orang kedua. Templat
 * daftar (`04_POLA_UI` §2.A): kepala satu baris (judul + jumlah + ?) · tabel nomor, tanggal, rekening, kategori,
 * nominal, pengaju · aksi baris di kolom kanan · halaman + Unduh. Nomor = `DocLink` → pratinjau dokumen (registri
 * `cash_out_request`, kaki: Jejak + Buka layar penuh). Bagian tidak digambar bila tidak ada yang menunggu (hemat ruang,
 * §1.4) — kecuali galat muat/aksi, yang tetap tampil di sini.
 *
 * Sumber: `GET /api/cash-out-requests?status=menunggu_persetujuan` (berhalaman; baris membawa `kontrol` untuk pengguna).
 * Aksi (izin, bukan peran — `cashOutShared.aksiPengajuan`): Setujui & Tolak `cash.approve` (nonaktif untuk pengaju dengan
 * kalimat server `kontrol.pesan` / `kontrol.tolak_pesan`), Batal pengaju (`cash.create`) atau `cash.delete`. Satu pop-up per
 * aksi: Setujui = `askConfirm` (nominal & PT, N5), Tolak = `askReason` (alasan wajib ≥ 5 huruf), Batal = `askReason`.
 * Kirim lewat `moneyPost` + `useIntentKey` (N4). Galat server (409 anggaran / periode / sudah diputus) tampil apa adanya
 * di bagian ini; hasil sukses = toast.
 */
import { useEffect, useMemo, useState } from "react";
import { Ban, Check, Clock, XCircle } from "lucide-react";
import { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import PaginationBar from "../../../components/PaginationBar";
import { HelpTip } from "../../../components/ListPageParts";
import { can } from "../../../config/roles";
import useIntentKey from "../../../hooks/useIntentKey";
import { usePagedList } from "../../../hooks/usePagedList";
import { askConfirm, askReason } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";
import { notifySuccess } from "../../../utils/feedback";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { moneyPost } from "../../../utils/moneyRequest";
import DocLink from "../../documents/preview/DocLink";
import { categoryLabel } from "../../purchasing/cashCategories";
import { ALASAN_MIN, MENUNGGU, TEKS_BANTU, aksiPengajuan } from "./cashOutShared";

const CSV = [
  { key: "number", header: "Nomor" },
  { key: "txn_date", header: "Tanggal", type: "date" },
  { key: "account_name", header: "Rekening" },
  { header: "Kategori", get: (d) => categoryLabel(d.category) },
  { key: "description", header: "Keterangan" },
  { key: "amount", header: "Nominal", type: "num" },
  { header: "Pengaju", get: (d) => d.pengaju?.name || d.created_by || "" },
];

export default function CashOutPendingSection({ currentUser, selectedEntity, entityName = () => "", refreshKey = 0,
  sorot = "", onDecided }) {
  const perms = currentUser?.permissions;
  const scoped = Boolean(selectedEntity) && selectedEntity !== "all";
  const params = useMemo(() => ({ status: MENUNGGU, ...(scoped ? { entity_id: selectedEntity } : {}) }),
    [scoped, selectedEntity]);
  const paged = usePagedList("/cash-out-requests", { pageSize: 10, params, enabled: can(perms, "cash", "view") });
  const [err, setErr] = useState("");
  const [sibukId, setSibukId] = useState("");
  const intent = useIntentKey("pkk");
  // Pengajuan baru dari form (202) / kas yang dianulir dll. → muat ulang daftar ini.
  useEffect(() => { if (refreshKey) paged.refresh(); }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const rows = paged.items || [];
  if (!paged.error && !err && !(paged.total > 0)) return null;
  const pt = (eid) => entityName(eid) || "PT ini";

  /** Satu aksi pengajuan. Galat server ditampilkan apa adanya di bagian ini; daftar selalu dimuat ulang. */
  async function kirim(d, aksi, body, pesan) {
    setSibukId(d.id);
    setErr("");
    try {
      const r = await intent.send({ id: d.id, aksi, ...body },
        (k) => moneyPost(`${API}/cash-out-requests/${d.id}/${aksi}`, body, k));
      notifySuccess(pesan(r?.data || d));
      if (aksi === "approve") onDecided?.();
    } catch (e) {
      setErr(apiErrorText(e, "Pengajuan kas keluar belum bisa diproses."));
    } finally {
      setSibukId("");
      await paged.refresh();
    }
  }

  const ringkas = (d) => `${formatCurrency(d.amount)} keluar dari ${d.account_name || "rekening PT"} (${pt(d.entity_id)})`
    + ` — ${categoryLabel(d.category)}${d.description ? ` · ${d.description}` : ""}.`;

  async function setujui(d) {
    const ok = await askConfirm({
      title: `Setujui kas keluar ${d.number}?`, confirmLabel: "Setujui", testId: "cash-out-approve-confirm",
      message: `${ringkas(d)} Diajukan ${d.pengaju?.name || d.created_by || "—"}. Kas keluar dan jurnalnya tercatat `
        + `sekarang dengan tanggal ${formatDate(d.txn_date)}; saldo kas berkurang.`,
    });
    if (ok) {
      await kirim(d, "approve", {}, (x) => `Kas keluar ${x.number || d.number} disetujui`
        + `${x.cash_number ? ` — kas ${x.cash_number} tercatat` : ""}.`);
    }
  }

  async function tolak(d) {
    const alasan = await askReason({
      title: `Tolak kas keluar ${d.number}?`, danger: true,
      message: `${ringkas(d)} Tidak ada kas yang tercatat; pengaju diberi tahu alasannya.`,
      reasonLabel: "Alasan penolakan", reasonRequired: true, reasonMinLength: ALASAN_MIN, confirmLabel: "Tolak",
      testId: "cash-out-reject-reason",
    });
    if (alasan === null || alasan === undefined) return;
    await kirim(d, "reject", { alasan }, (x) => `Pengajuan ${x.number || d.number} ditolak.`);
  }

  async function batal(d) {
    const alasan = await askReason({
      title: `Batalkan pengajuan ${d.number}?`, danger: true,
      message: `${ringkas(d)} Kasnya belum tercatat, jadi pengajuan cukup ditandai dibatalkan.`,
      reasonLabel: "Alasan pembatalan", reasonRequired: true, reasonMinLength: ALASAN_MIN, confirmLabel: "Batalkan",
      testId: "cash-out-cancel-reason",
    });
    if (alasan === null || alasan === undefined) return;
    await kirim(d, "cancel", { alasan }, (x) => `Pengajuan ${x.number || d.number} dibatalkan.`);
  }

  return (
    <div className="section-card mb-3" data-testid="cash-out-pending">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <Clock size={16} className="text-kn-warning-text" aria-hidden="true" />
          <h2 data-testid="cash-out-pending-title">Menunggu persetujuan</h2>
          {paged.total > 0 && <span className="tab-badge" data-testid="cash-out-pending-count">{paged.total}</span>}
          <HelpTip text={TEKS_BANTU} testId="cash-out-pending-help" />
        </div>
      </div>
      {err && (
        <div className="px-3 pb-2">
          <ErrorNotice message={err} onDismiss={() => setErr("")} testId="cash-out-error" />
        </div>
      )}
      {paged.error ? (
        <div className="px-3 pb-3">
          <ErrorNotice message={paged.error} onRetry={paged.refresh} testId="cash-out-list-error" />
        </div>
      ) : rows.length === 0 ? (
        <p className="px-3 pb-3 text-fs-12 text-kn-text-2" data-testid="cash-out-pending-done">
          {paged.loading ? "Memuat pengajuan…" : "Tidak ada lagi kas keluar yang menunggu persetujuan."}
        </p>
      ) : (
        <div className="overflow-x-auto border-t border-kn-divider">
          <table className="data-table head-wrap w-full" data-testid="cash-out-table">
            <thead><tr>
              <th>Nomor</th><th>Tanggal</th><th>Rekening</th><th>Kategori / Keterangan</th>
              <th className="text-right">Nominal</th><th>Pengaju</th><th className="col-sticky-end text-right">Aksi</th>
            </tr></thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id} data-testid={`cash-out-row-${d.id}`} className={d.id === sorot ? "row-focus" : undefined}>
                  <td className="whitespace-nowrap">
                    <DocLink docType="cash_out_request" docId={d.id} number={d.number} entityId={d.entity_id} perms={perms}
                      className="font-mono font-semibold" testId={`cash-out-open-${d.id}`} />
                    {!scoped && <span className="block text-fs-12 text-kn-text-2">{entityName(d.entity_id)}</span>}
                  </td>
                  <td className="whitespace-nowrap text-kn-text-2" data-testid={`cash-out-date-${d.id}`}>{formatDate(d.txn_date)}</td>
                  <td className="whitespace-nowrap" data-testid={`cash-out-account-${d.id}`}>{d.account_name || "—"}</td>
                  <td className="min-w-[180px]">
                    <p className="font-semibold" data-testid={`cash-out-category-${d.id}`}>{categoryLabel(d.category)}</p>
                    {d.description && <p className="text-fs-12 text-kn-text-2">{d.description}</p>}
                    {d.terbit_error && (
                      <p className="max-w-[260px] text-fs-12 text-kn-danger-text" data-testid={`cash-out-publish-error-${d.id}`}>
                        Kas belum terbit: {d.terbit_error}
                      </p>
                    )}
                  </td>
                  <td className="whitespace-nowrap text-right font-bold tabular-nums text-kn-danger-text"
                    data-testid={`cash-out-amount-${d.id}`}>−{formatCurrency(d.amount)}</td>
                  <td className="whitespace-nowrap" data-testid={`cash-out-requester-${d.id}`}>{d.pengaju?.name || d.created_by || "—"}</td>
                  <td className="col-sticky-end text-right">
                    <BarisAksi d={d} aksi={aksiPengajuan(d, perms, currentUser)} mati={sibukId === d.id}
                      onSetujui={() => setujui(d)} onTolak={() => tolak(d)} onBatal={() => batal(d)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!paged.error && paged.total > 0 && (
        <div className="px-3 pb-3">
          <PaginationBar page={paged.page} pageSize={paged.pageSize} total={paged.total} hasMore={paged.hasMore}
            loading={paged.loading} onPrev={paged.prev} onNext={paged.next} testId="cash-out-pager" label="pengajuan"
            exportConfig={{ columns: CSV, rows, fetchAll: paged.fetchAll, filename: "pengajuan-kas-keluar" }}
            exportSpec={{ dataset: "cash_out_requests", label: "pengajuan-kas-keluar",
              filters: [["status", "eq", MENUNGGU]], sort: [{ key: "created_at", dir: "desc" }] }} />
        </div>
      )}
    </div>
  );
}

function BarisAksi({ d, aksi, mati, onSetujui, onTolak, onBatal }) {
  const alasan = [aksi.setujui, aksi.tolak, aksi.batal].map((a) => a?.alasan).find(Boolean) || "";
  if (!aksi.setujui && !aksi.tolak && !aksi.batal) return null;
  return (
    <div className="flex flex-col items-end gap-1" data-testid={`cash-out-actions-${d.id}`}>
      <div className="flex flex-wrap justify-end gap-1.5">
        {aksi.setujui && (
          <button type="button" className="primary-button btn-sm" data-testid={`cash-out-approve-${d.id}`}
            disabled={mati || Boolean(aksi.setujui.alasan)} title={aksi.setujui.alasan || undefined} onClick={onSetujui}>
            <Check size={13} aria-hidden="true" />{aksi.setujui.label}
          </button>
        )}
        {aksi.tolak && (
          <button type="button" className="secondary-button btn-sm" data-testid={`cash-out-reject-${d.id}`}
            disabled={mati || Boolean(aksi.tolak.alasan)} title={aksi.tolak.alasan || undefined} onClick={onTolak}>
            <XCircle size={13} aria-hidden="true" />{aksi.tolak.label}
          </button>
        )}
        {aksi.batal && (
          <button type="button" className="secondary-button btn-sm text-kn-danger-text" data-testid={`cash-out-cancel-${d.id}`}
            disabled={mati || Boolean(aksi.batal.alasan)} onClick={onBatal}>
            <Ban size={13} aria-hidden="true" />{aksi.batal.label}
          </button>
        )}
      </div>
      {alasan && (
        // Sel aksi `text-right` mewarisi `white-space: nowrap` (kolom angka) — kalimat alasan dibungkus sendiri.
        <span className="max-w-[260px] whitespace-normal break-words text-left text-fs-12 text-kn-text-2"
          data-testid={`cash-out-action-note-${d.id}`}>
          {alasan}
        </span>
      )}
    </div>
  );
}
