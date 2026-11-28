/**
 * CashCountsView — Kas & Bank bagian 3 (Tugas 4b) · Keuangan › Kas & Bank › **Opname Kas** (view `cash-counts`, tab
 * TERSEMBUNYI — hub tetap 6 tab tampak; bilah tab menyorot Rekening & Saldo). Spesifikasi §5.3, §5.4.
 *
 * Templat daftar (`04_POLA_UI` §2.A): judul satu baris (+ ?) · bilah daftar (cari · Status ▾ · Rekening ▾ · jumlah ·
 * + Hitung) · tabel nomor, dihitung, rekening, saldo buku, uang fisik, selisih, status · aksi baris di kolom kanan ·
 * halaman + Unduh CSV. Nomor = `DocLink` → pratinjau dokumen (registri `cash_count`, kaki: Jejak + Buka layar penuh).
 *
 * Sumber: `GET /api/cash-counts` (berhalaman; baris menunggu membawa `kontrol` untuk pengguna) dan `GET /api/bank-accounts`
 * (pilihan saringan rekening = rekening tunai). Aksi (izin, bukan peran — `cashCountShared.aksiOpname`): Hitung
 * `cash.create` (pop-up `CashCountForm`), Setujui `cash.approve` (pop-up `CashCountApproveModal`: perlakuan + karyawan;
 * nonaktif bagi penghitung dengan kalimat server), Tolak `cash.approve` (`askReason` ≥ 5 huruf; penghitung boleh menolak
 * hitungannya sendiri). Semua kirim lewat `moneyPost` + `useIntentKey`.
 * Tautan masuk: Pusat Persetujuan (preset `{status}`), kartu rekening Rekening & Saldo (preset `{hitung, account_id}` →
 * pop-up Hitung terisi), pratinjau "Buka layar penuh" (preset `{status, account_id, sorot}`), notifikasi & Jejak
 * (`focusDoc` `cash_count` → pratinjau), Meja Keuangan "Buka layar penuh" (`focusDoc` `bank_account` → saringan rekening).
 */
import { useEffect, useMemo, useState } from "react";
import { Calculator, Check, Plus, XCircle } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import EntityScopeBanner from "../../../components/EntityScopeBanner";
import FocusNotice from "../../../components/FocusNotice";
import KNSelect from "../../../components/KNSelect";
import PaginationBar from "../../../components/PaginationBar";
import StatusBadge from "../../../components/StatusBadge";
import { ListToolbar, PageHeader, SearchInput } from "../../../components/ListPageParts";
import { can } from "../../../config/roles";
import { useAppNav } from "../../../context/AppNavContext";
import { useEntityScope } from "../../../context/EntityScopeContext";
import useFocusDoc, { gulirKe } from "../../../hooks/useFocusDoc";
import useIntentKey from "../../../hooks/useIntentKey";
import { usePagedList } from "../../../hooks/usePagedList";
import useViewPreset from "../../../hooks/useViewPreset";
import { askReason } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";
import { entityShortById } from "../../../utils/entityLabel";
import { notifySuccess } from "../../../utils/feedback";
import { formatCurrency, formatDateTime } from "../../../utils/formatters";
import { moneyPost } from "../../../utils/moneyRequest";
import DocLink from "../../documents/preview/DocLink";
import CashCountApproveModal from "./CashCountApproveModal";
import CashCountForm from "./CashCountForm";
import {
  ALASAN_MIN, PILIHAN_STATUS, TEKS_BANTU, aksiOpname, jenisKas, labelRekeningTunai, rekeningTunai, selisihNada,
  selisihTeks, statusOpname,
} from "./cashCountShared";

const CSV = [
  { key: "number", header: "Nomor" },
  { key: "dihitung_pada", header: "Dihitung", type: "date" },
  { key: "account_name", header: "Rekening" },
  { header: "Jenis kas", get: (d) => jenisKas(d) },
  { key: "saldo_buku", header: "Saldo buku", type: "num" },
  { key: "jumlah_fisik", header: "Uang fisik", type: "num" },
  { key: "selisih", header: "Selisih", type: "num" },
  { header: "Status", get: (d) => statusOpname(d.status).label },
  { key: "perlakuan_label", header: "Perlakuan" },
  { key: "karyawan_nama", header: "Karyawan" },
  { header: "Penghitung", get: (d) => d.penghitung?.name || d.created_by || "" },
  { key: "catatan", header: "Catatan" },
];

export default function CashCountsView({ currentUser, selectedEntity, focusDoc, onClearFocus }) {
  const perms = currentUser?.permissions;
  const nav = useAppNav();
  const { entities = [] } = useEntityScope() || {};
  const scoped = Boolean(selectedEntity) && selectedEntity !== "all";
  const [status, setStatus] = useState("");
  const [rekeningId, setRekeningId] = useState("");
  const [cari, setCari] = useState("");
  const [sorot, setSorot] = useState("");
  const [hitung, setHitung] = useState(null);      // { accountId } — pop-up Hitung terbuka
  const [setujui, setSetujui] = useState(null);    // opname yang sedang disetujui
  const [rekening, setRekening] = useState([]);
  const [err, setErr] = useState("");
  const [sibukId, setSibukId] = useState("");
  const intent = useIntentKey("opka");

  useEffect(() => {
    let hidup = true;
    axios.get(`${API}/bank-accounts`, { params: scoped ? { entity_id: selectedEntity } : {} })
      .then((r) => { if (hidup) setRekening(rekeningTunai(r.data)); })
      .catch(() => { if (hidup) setRekening([]); });
    return () => { hidup = false; };
  }, [scoped, selectedEntity]);

  useViewPreset("cash-counts", (p) => {
    if (p.status !== undefined) setStatus(p.status || "");
    if (p.account_id !== undefined) setRekeningId(p.account_id || "");
    if (p.sorot) { setSorot(p.sorot); gulirKe(`opk-row-${p.sorot}`, 600); }
    if (p.hitung && can(perms, "cash", "create")) setHitung({ accountId: p.hitung });
  });

  const params = useMemo(() => ({
    ...(scoped ? { entity_id: selectedEntity } : {}), ...(status ? { status } : {}), ...(rekeningId ? { account_id: rekeningId } : {}),
  }), [scoped, selectedEntity, status, rekeningId]);
  const paged = usePagedList("/cash-counts", { pageSize: 25, params, search: cari });
  const rows = paged.items || [];

  const fokus = useFocusDoc(focusDoc, ["cash_count", "bank_account"], (id, fd) => {
    if (fd.focus_type === "bank_account") {   // Meja Keuangan "Buka layar penuh": riwayat opname rekening itu
      setStatus("");
      setRekeningId(id);
      return true;
    }
    setSorot(id);
    nav.openDocPreview({ docType: "cash_count", docId: id, ...(fd.number ? { number: fd.number } : {}) });
    return true;
  }, onClearFocus);

  const opsiRekening = useMemo(() => [{ value: "", label: "Semua rekening tunai" },
    ...rekening.map((a) => ({ value: a.id, label: `${labelRekeningTunai(a, scoped ? "" : entityShortById(entities, a.entity_id, ""))}`
      + `${a.is_active === false ? " · nonaktif" : ""}` }))], [rekening, scoped, entities]);

  /** Satu aksi opname → "" bila berhasil, kalimat galat bila ditolak. Galat aksi dari pop-up tampil di pop-up itu. */
  async function kirim(d, aksi, body, pesan, { diPopup = false } = {}) {
    setSibukId(d.id);
    setErr("");
    try {
      const r = await intent.send({ id: d.id, aksi, ...body }, (k) => moneyPost(`${API}/cash-counts/${d.id}/${aksi}`, body, k));
      notifySuccess(pesan(r.data || d));
      await paged.refresh();
      return "";
    } catch (e) {
      const teks = apiErrorText(e, "Opname kas belum bisa diproses.");
      if (!diPopup) setErr(teks);
      await paged.refresh();
      return teks;
    } finally { setSibukId(""); }
  }

  async function tolak(d) {
    const alasan = await askReason({
      title: `Tolak opname ${d.number}?`, danger: true,
      message: `${selisihTeks(d)} di ${d.account_name}. Tidak ada kas atau jurnal yang dicatat; penghitung menghitung ulang `
        + "rekening ini (opname baru).",
      reasonLabel: "Alasan penolakan", reasonMinLength: ALASAN_MIN, confirmLabel: "Tolak", testId: "opk-reject-reason",
    });
    if (alasan === null || alasan === undefined) return;
    await kirim(d, "reject", { alasan }, (x) => `Opname ${x.number} ditolak — rekening ${x.account_name} perlu dihitung ulang.`);
  }

  return (
    <div className="space-y-3" data-testid="cash-counts-view">
      <PageHeader icon={Calculator} title="Opname Kas" help={TEKS_BANTU} testId="opk-header" />
      <EntityScopeBanner testId="opk-scope" />
      <FocusNotice {...fokus} testId="opk-focus-notice" />
      <ErrorNotice message={err} onDismiss={() => setErr("")} testId="opk-error" />
      <ListToolbar testId="opk-toolbar"
        count={paged.total > 0 ? <span data-testid="opk-count">{paged.total} opname</span> : null}
        actions={can(perms, "cash", "create") ? (
          <button type="button" className="primary-button whitespace-nowrap" data-testid="opk-create"
            onClick={() => setHitung({ accountId: rekeningId })}>
            <Plus size={14} aria-hidden="true" /> Hitung kas
          </button>
        ) : null}>
        <SearchInput testId="opk-search" placeholder="Cari nomor, rekening, penghitung, karyawan" value={cari} onChange={setCari}
          className="min-w-[200px] flex-1 sm:max-w-[300px]" />
        <KNSelect data-testid="opk-status" aria-label="Status" className="field !w-auto min-w-[180px]" value={status}
          options={PILIHAN_STATUS} onValueChange={(v) => setStatus(v || "")} />
        <KNSelect data-testid="opk-account" aria-label="Rekening" className="field !w-auto min-w-[200px]" value={rekeningId}
          options={opsiRekening} onValueChange={(v) => setRekeningId(v || "")} />
      </ListToolbar>

      <div className="section-card" data-testid="opk-list">
        {paged.error ? (
          <div className="section-pad"><ErrorNotice message={paged.error} onRetry={paged.refresh} testId="opk-list-error" /></div>
        ) : paged.loading && rows.length === 0 ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="opk-loading">Memuat opname kas…</div>
        ) : rows.length === 0 ? (
          <div className="section-pad text-center text-fs-13 text-kn-text-2" data-testid="opk-empty">
            {cari.trim() || status || rekeningId ? "Tidak ada opname yang cocok dengan saringan." : "Belum ada opname kas."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="opk-table">
              <thead><tr>
                <th>Nomor</th><th>Dihitung</th><th>Rekening</th><th className="text-right">Saldo buku</th>
                <th className="text-right">Uang fisik</th><th className="text-right">Selisih</th><th>Status</th>
                <th className="col-sticky-end text-right">Aksi</th>
              </tr></thead>
              <tbody>
                {rows.map((d) => {
                  const st = statusOpname(d.status);
                  return (
                    <tr key={d.id} data-testid={`opk-row-${d.id}`} className={d.id === sorot ? "row-focus" : undefined}>
                      <td className="whitespace-nowrap">
                        <DocLink docType="cash_count" docId={d.id} number={d.number} entityId={d.entity_id} perms={perms}
                          className="font-mono font-semibold" testId={`opk-open-${d.id}`} />
                        {!scoped && <span className="block text-fs-12 text-kn-text-2">{entityShortById(entities, d.entity_id, "")}</span>}
                      </td>
                      <td className="whitespace-nowrap">
                        {d.dihitung_pada ? formatDateTime(d.dihitung_pada) : "—"}
                        <span className="block text-fs-12 text-kn-text-2">{d.penghitung?.name || d.created_by || ""}</span>
                      </td>
                      <td className="min-w-[180px]">
                        {d.account_name}
                        <span className="block text-fs-12 text-kn-text-2">{jenisKas(d)}</span>
                      </td>
                      <td className="text-right tabular-nums">{formatCurrency(d.saldo_buku)}</td>
                      <td className="text-right tabular-nums">{formatCurrency(d.jumlah_fisik)}</td>
                      <td className={`text-right tabular-nums font-semibold ${selisihNada(d)}`} data-testid={`opk-diff-${d.id}`}>
                        {selisihTeks(d)}
                      </td>
                      <td>
                        <StatusBadge status={d.status} label={st.label} tone={st.tone} icon={st.icon} testId={`opk-status-${d.id}`} />
                        {d.perlakuan_label && (
                          <span className="mt-0.5 block text-fs-12 text-kn-text-2" data-testid={`opk-treatment-${d.id}`}>
                            {d.perlakuan_label}{d.karyawan_nama ? ` · ${d.karyawan_nama}` : ""}
                          </span>
                        )}
                        {d.status === "ditolak" && d.alasan_tolak && (
                          <span className="mt-0.5 block max-w-[220px] text-fs-12 text-kn-text-2">{d.alasan_tolak}</span>
                        )}
                        {d.terbit_error && d.status === "menunggu_persetujuan" && (
                          <span className="mt-0.5 block max-w-[220px] text-fs-12 text-kn-danger-text" data-testid={`opk-publish-error-${d.id}`}>
                            Kas belum terbit: {d.terbit_error}
                          </span>
                        )}
                      </td>
                      <td className="col-sticky-end text-right">
                        <BarisAksi d={d} aksi={aksiOpname(d, perms)} mati={sibukId === d.id}
                          onSetujui={() => setSetujui(d)} onTolak={() => tolak(d)} />
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
              loading={paged.loading} onPrev={paged.prev} onNext={paged.next} testId="opk-pager" label="opname"
              exportConfig={{ columns: CSV, rows, fetchAll: paged.fetchAll, filename: "opname-kas" }}
              exportSpec={{ dataset: "cash_counts", label: "opname-kas", search: cari,
                filters: [["status", "eq", status], ["account_id", "eq", rekeningId]],
                sort: [{ key: "dihitung_pada", dir: "desc" }] }} />
          </div>
        )}
      </div>

      {hitung && (
        <CashCountForm open onClose={() => setHitung(null)} entityId={scoped ? selectedEntity : ""}
          accountId={hitung.accountId || ""} onSaved={() => paged.refresh()} />
      )}
      {setujui && (
        <CashCountApproveModal key={setujui.id} doc={setujui} onClose={() => setSetujui(null)}
          onSetujui={async (d, body) => {
            const salah = await kirim(d, "approve", body, (x) => `Selisih opname ${x.number} disetujui`
              + `${x.cash_number ? ` — kas penyesuaian ${x.cash_number} tercatat` : ""}.`, { diPopup: true });
            if (!salah) setSetujui(null);
            return salah;
          }} />
      )}
    </div>
  );
}

function BarisAksi({ d, aksi, mati, onSetujui, onTolak }) {
  const alasan = [aksi.setujui, aksi.tolak].map((a) => a?.alasan).find(Boolean) || "";
  if (!aksi.setujui && !aksi.tolak) return null;
  return (
    <div className="flex flex-col items-end gap-1" data-testid={`opk-actions-${d.id}`}>
      <div className="flex flex-wrap justify-end gap-1.5">
        {aksi.setujui && (
          <button type="button" className="primary-button btn-sm" data-testid={`opk-approve-${d.id}`}
            disabled={mati || Boolean(aksi.setujui.alasan)} onClick={onSetujui}>
            <Check size={13} aria-hidden="true" />{aksi.setujui.label}
          </button>
        )}
        {aksi.tolak && (
          <button type="button" className="secondary-button btn-sm text-kn-danger-text" data-testid={`opk-reject-${d.id}`}
            disabled={mati || Boolean(aksi.tolak.alasan)} onClick={onTolak}>
            <XCircle size={13} aria-hidden="true" />{aksi.tolak.label}
          </button>
        )}
      </div>
      {alasan && (
        // Sel aksi `text-right` mewarisi `white-space: nowrap` (kolom angka) — kalimat alasan dibungkus sendiri.
        <span className="max-w-[260px] whitespace-normal break-words text-left text-fs-12 text-kn-text-2" data-testid={`opk-action-note-${d.id}`}>
          {alasan}
        </span>
      )}
    </div>
  );
}
