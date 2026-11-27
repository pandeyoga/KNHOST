/**
 * Isi pratinjau pengajuan kas keluar manual (Kas & Bank bagian 2, Tugas 4): fakta pengajuan (PT, status, tanggal kas,
 * rekening, kategori, keterangan, nominal, pengaju, putusan + alasan), kas yang terbit sesudah disetujui (nomor, tanggal,
 * jurnal, keadaan), kalimat kontrol dua orang untuk pembuka, dan riwayat (`jejak`).
 * Data dari `GET /cash-out-requests/{id}` (pengajuan + `kas` + `kontrol` bila menunggu). Hanya-baca: Setujui / Tolak /
 * Batal ada di Kas & Bank › Transaksi Kas bagian "Menunggu persetujuan"; "Buka layar penuh" membuka bagian itu (pengajuan
 * menunggu) atau baris kasnya di Transaksi Kas (pengajuan disetujui) — registri `cash_out_request`.
 */
import StatusBadge from "../../../../components/StatusBadge";
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate, formatDateTime } from "../../../../utils/formatters";
import { JEJAK_LABEL, MENUNGGU, statusPengajuan } from "../../../finance/cashout/cashOutShared";
import { categoryLabel } from "../../../purchasing/cashCategories";
import { PreviewFacts, PreviewTotals } from "../previewParts";

/** Keadaan kas yang terbit dalam kalimat: dibatalkan / jurnal gagal / jurnal terbit. */
export function keteranganKasPengajuan(k) {
  if (!k) return "";
  if (k.status === "void") return "Dibatalkan";
  if (k.gl_status === "failed") return `Jurnal gagal${k.gl_error ? `: ${k.gl_error}` : ""}`;
  return k.journal_number ? `Jurnal ${k.journal_number}` : "Jurnal menunggu";
}

export default function CashOutRequestPreview({ doc }) {
  const { entities } = useEntityScope() || {};
  const st = statusPengajuan(doc.status);
  const jejak = Array.isArray(doc.jejak) ? doc.jejak : [];
  const kas = doc.kas || null;
  const menunggu = doc.status === MENUNGGU;
  const tunggu = menunggu && doc.kontrol?.ditolak ? doc.kontrol.pesan : "";
  return (
    <div className="grid gap-3" data-testid="doc-preview-cash-out-request">
      {doc.terbit_error && menunggu && (
        <p className="notice-bar warning text-fs-12" data-testid="doc-preview-cor-publish-error">Kas belum terbit: {doc.terbit_error}</p>
      )}
      <PreviewFacts testId="doc-preview-cor-facts" items={[
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities || [], doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: <StatusBadge status={doc.status} label={st.label} tone={st.tone} icon={st.icon}
          testId="doc-preview-status" /> },
        { key: "date", label: "Tanggal kas", content: doc.txn_date ? formatDate(doc.txn_date) : "" },
        { key: "account", label: "Rekening", content: doc.account_name },
        { key: "category", label: "Kategori", content: doc.category ? categoryLabel(doc.category) : "" },
        { key: "description", label: "Keterangan", content: doc.description },
        { key: "requester", label: "Pengaju", content: doc.pengaju?.name || doc.created_by },
        { key: "requested", label: "Diajukan", content: doc.created_at ? formatDateTime(doc.created_at) : "" },
        { key: "approver", label: "Disetujui", content: doc.disetujui_oleh
          ? `${doc.disetujui_oleh}${doc.disetujui_pada ? ` · ${formatDateTime(doc.disetujui_pada)}` : ""}` : "" },
        { key: "rejecter", label: "Ditolak", content: doc.ditolak_oleh
          ? `${doc.ditolak_oleh}${doc.ditolak_pada ? ` · ${formatDateTime(doc.ditolak_pada)}` : ""}` : "" },
        { key: "reject_reason", label: "Alasan tolak", content: doc.alasan_tolak },
        { key: "canceller", label: "Dibatalkan", content: doc.dibatalkan_oleh
          ? `${doc.dibatalkan_oleh}${doc.dibatalkan_pada ? ` · ${formatDateTime(doc.dibatalkan_pada)}` : ""}` : "" },
        { key: "cancel_reason", label: "Alasan batal", content: doc.alasan_batal },
      ]} />
      {tunggu && <p className="text-fs-12 text-kn-text-2" data-testid="doc-preview-cor-control">{tunggu}</p>}
      {kas ? (
        <PreviewFacts testId="doc-preview-cor-cash" items={[
          { key: "number", label: "Kas", content: <span className="font-mono">{kas.number || "—"}</span> },
          { key: "date", label: "Tanggal", content: kas.txn_date ? formatDate(kas.txn_date) : "" },
          { key: "state", label: "Keterangan", content: keteranganKasPengajuan(kas) },
        ]} />
      ) : (
        <p className="text-fs-12 text-kn-text-2" data-testid="doc-preview-cor-cash-empty">
          {menunggu ? "Kas dan jurnalnya terbit sesudah disetujui orang kedua." : "Tidak ada kas yang tercatat."}
        </p>
      )}
      <PreviewTotals rows={[{ label: "Nominal kas keluar", value: formatCurrency(Number(doc.amount) || 0), strong: true }]} />
      {jejak.length > 0 && (
        <ol className="grid gap-1 border-t border-kn-divider pt-2" data-testid="doc-preview-cor-history">
          {jejak.map((j, i) => (
            <li key={`${j.aksi}-${i}`} className="text-fs-12 text-kn-text-2">
              <span className="font-semibold text-kn-text">{JEJAK_LABEL[j.aksi] || j.aksi}</span>
              {j.oleh ? ` · ${j.oleh}` : ""}{j.pada ? ` · ${formatDateTime(j.pada)}` : ""}{j.catatan ? ` — ${j.catatan}` : ""}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
