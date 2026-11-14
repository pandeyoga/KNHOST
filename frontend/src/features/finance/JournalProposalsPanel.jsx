/**
 * JournalProposalsPanel — KF-T6 (GL-06): jurnal manual yang menunggu orang kedua (Buku Besar › Jurnal).
 *
 * Bila aturan "Jurnal manual" di Pengaturan › Persetujuan › Kontrol dua orang = "Harus dua orang" (atau nilainya di atas
 * batas nominal), jurnal manual tersimpan sebagai USULAN (`/api/gl/journal-proposals`) dan baru diposting setelah orang
 * lain yang berwenang menyetujuinya. Pengusul tidak bisa menyetujui usulannya sendiri (server menolak 403).
 *
 *  · `JournalProposalBanner` — pita "{n} jurnal manual menunggu orang kedua" + tombol buka saringan.
 *  · `JournalProposalsPanel` — daftar berhalaman dengan tombol Setujui (konfirmasi nominal + PT) dan Tolak (alasan).
 */
import { useEffect, useState } from "react";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import PaginationBar from "../../components/PaginationBar";
import { usePagedList } from "../../hooks/usePagedList";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { confirmMoney, reasonMoney } from "../../utils/moneyConfirm";
import { formatCurrency, formatDate, formatDateTime } from "../../utils/formatters";

/** Kolom CSV layar (INV-UI-07); Excel lewat Pusat Export dataset `journal_proposals`. */
const PROPOSAL_CSV_COLUMNS = [
  { header: "Tanggal jurnal", get: (p) => p?.payload?.date || "" },
  { header: "Keterangan", get: (p) => p?.payload?.description || "" },
  { key: "total_debit", header: "Nilai", type: "num" },
  { key: "proposed_by", header: "Diajukan oleh" },
  { key: "proposed_at", header: "Tanggal diajukan", type: "date" },
];

export function JournalProposalBanner({ refreshKey, onOpen }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/gl/journal-proposals`, { params: { status: "pending", page: 1, page_size: 1 } })
      .then((r) => { if (alive) setCount(Number(r.data?.total || 0)); })
      .catch(() => { if (alive) setCount(0); });   // pita hanya petunjuk; daftar lengkap punya galatnya sendiri
    return () => { alive = false; };
  }, [refreshKey]);
  if (!count) return null;
  return (
    <div className="notice-bar warning mb-2 flex items-center gap-2" data-testid="gl-proposal-banner">
      <Clock size={14} /> <span>{count} jurnal manual menunggu orang kedua</span>
      <button type="button" className="link-button ml-auto" onClick={onOpen}
        data-testid="gl-proposal-banner-open">Lihat</button>
    </div>
  );
}

export default function JournalProposalsPanel({ refreshKey, entities = [], onChanged, onNotice }) {
  const paged = usePagedList("/gl/journal-proposals", { params: { status: "pending" }, pageSize: 20 });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");
  const approveIntent = useIntentKey("jpa");
  const rejectIntent = useIntentKey("jpr");
  useEffect(() => { paged.refresh(); }, [refreshKey]); // eslint-disable-line

  const label = (p) => p?.payload?.description || "Jurnal manual";
  const approve = async (p) => {
    if (!(await confirmMoney({
      title: `Setujui jurnal manual “${label(p)}”?`,
      effect: `Jurnal diposting ke buku besar dengan pengusul ${p.proposed_by || "—"} dan Anda sebagai penyetuju.`,
      amount: p.total_debit, entityId: p.entity_id, entities, confirmLabel: "Setujui & Posting",
      testId: "jprop-approve-confirm",
    }))) return;
    setBusy(p.id); setError(null);
    try {
      const r = await approveIntent.send({ id: p.id, aksi: "approve" },
        (k) => moneyPost(`${API}/gl/journal-proposals/${p.id}/approve`, undefined, k));
      onNotice && onNotice(`Jurnal ${r?.data?.journal_number || ""} diposting.`.replace("  ", " "));
      paged.refresh(); onChanged && onChanged();
    } catch (e) {
      setError(e);
    } finally {
      setBusy("");
    }
  };
  const reject = async (p) => {
    const reason = await reasonMoney({
      title: `Tolak jurnal manual “${label(p)}”?`, effect: "Usulan ditolak; tidak ada jurnal yang diposting.",
      amount: p.total_debit, entityId: p.entity_id, entities, confirmLabel: "Tolak", danger: true,
      reasonLabel: "Alasan penolakan", testId: "jprop-reject-confirm",
    });
    if (reason === null) return;
    setBusy(p.id); setError(null);
    try {
      const body = { reason };
      await rejectIntent.send({ id: p.id, ...body },
        (k) => moneyPost(`${API}/gl/journal-proposals/${p.id}/reject`, body, k));
      onNotice && onNotice("Usulan jurnal ditolak.");
      paged.refresh(); onChanged && onChanged();
    } catch (e) {
      setError(e);
    } finally {
      setBusy("");
    }
  };

  return (
    <div data-testid="gl-proposals">
      {error ? <ErrorNotice message={error} onDismiss={() => setError(null)} testId="gl-proposals-error" /> : null}
      {paged.error ? <ErrorNotice message={paged.error} onRetry={paged.refresh} testId="gl-proposals-load-error" /> : null}
      {paged.loading ? (
        <div className="grid gap-2" data-testid="gl-proposals-loading">{[0, 1, 2].map((i) => <div key={i} className="h-10 bg-kn-neutral-soft rounded animate-pulse" />)}</div>
      ) : paged.items.length === 0 ? (
        <div data-testid="gl-proposals-empty" className="py-12 text-center text-fs-12 text-kn-text-2">
          Tidak ada jurnal manual yang menunggu persetujuan.
        </div>
      ) : (
        <div className="overflow-auto rounded-md border border-kn-divider">
          <table className="w-full text-fs-12">
            <thead>
              <tr className="text-left text-fs-12 font-bold uppercase text-kn-text-2 bg-kn-neutral-soft border-b border-kn-divider">
                <th className="px-3 py-2">Tanggal</th>
                <th className="px-3 py-2">Keterangan</th>
                <th className="px-3 py-2 text-right">Nilai</th>
                <th className="px-3 py-2">Diajukan</th>
                <th className="px-3 py-2 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {paged.items.map((p) => (
                <tr key={p.id} data-testid={`gl-proposal-row-${p.id}`} className="border-b border-kn-divider last:border-0">
                  <td className="px-3 py-2">{formatDate(p.payload?.date)}</td>
                  <td className="px-3 py-2 max-w-[280px] truncate">{label(p)}</td>
                  <td className="px-3 py-2 text-right tabular-nums font-semibold">{formatCurrency(p.total_debit)}</td>
                  <td className="px-3 py-2 text-fs-12 text-kn-text-2">{p.proposed_by}<br />
                    <span className="text-fs-12 text-kn-text-2">{formatDateTime(p.proposed_at)}</span></td>
                  <td className="px-3 py-2 text-right">
                    <div className="inline-flex gap-1">
                      <button type="button" className="secondary-button btn-sm"
                        onClick={() => approve(p)} disabled={!!busy} data-testid={`gl-proposal-approve-${p.id}`}>
                        <CheckCircle2 size={12} /> Setujui
                      </button>
                      <button type="button" className="danger-button btn-sm"
                        onClick={() => reject(p)} disabled={!!busy} data-testid={`gl-proposal-reject-${p.id}`}>
                        <XCircle size={12} /> Tolak
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!paged.loading && paged.items.length > 0 && (
        <div className="mt-2">
          <PaginationBar page={paged.page} pageSize={paged.pageSize} total={paged.total} hasMore={paged.hasMore}
            loading={paged.loading} onPrev={paged.prev} onNext={paged.next} onPageSize={paged.setPageSize}
            testId="gl-proposals-pager" label="usulan"
            exportConfig={{ columns: PROPOSAL_CSV_COLUMNS, rows: paged.items, fetchAll: paged.fetchAll,
              filename: "usulan-jurnal-manual" }}
            exportSpec={{ dataset: "journal_proposals", label: "usulan-jurnal-manual",
              filters: [["status", "eq", "pending"]], sort: [{ key: "proposed_at", dir: "desc" }] }} />
        </div>
      )}
    </div>
  );
}
