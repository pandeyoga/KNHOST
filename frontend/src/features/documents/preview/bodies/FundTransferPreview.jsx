/**
 * Isi pratinjau Pindah Dana (Kas & Bank bagian 1, Tugas 6): fakta dokumen, kas-kasnya (kas keluar rekening asal, biaya
 * transfer, kas masuk rekening tujuan — nomor kas, rekening, tanggal, nominal, jurnal), ringkasan uang, dan riwayat.
 * Data dari `GET /fund-transfers/{id}` (dokumen + `kas` + `kontrol` untuk pembuka). Hanya-baca: aksi Setujui / Terima /
 * Batal ada di layar Kas & Bank › Pindah Dana ("Buka layar penuh"). Kas dokumen tidak punya pratinjau sendiri → teks.
 */
import StatusBadge from "../../../../components/StatusBadge";
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate, formatDateTime, formatDatesInText } from "../../../../utils/formatters";
import { JEJAK_LABEL, statusPindahDana } from "../../../finance/fundtransfer/fundTransferShared";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

const KOLOM_KAS = [
  { key: "number", label: "Kas", render: (k) => <span className="font-mono text-fs-12">{k.number || "—"}</span> },
  { key: "peran", label: "Untuk" },
  { key: "account_name", label: "Rekening", render: (k) => k.account_name || "—" },
  { key: "txn_date", label: "Tanggal", render: (k) => (k.txn_date ? formatDate(k.txn_date) : "—") },
  { key: "amount", label: "Nominal", align: "right", render: (k) => (
    <span className={`tabular-nums ${k.direction === "in" ? "text-kn-success-text" : "text-kn-danger-text"}`}>
      {k.direction === "in" ? "+" : "−"}{formatCurrency(k.amount)}
    </span>) },
  { key: "status", label: "Keterangan", render: (k) => keteranganKas(k) },
];

/** Keadaan kas dalam kalimat: dibatalkan (dengan jurnal pembaliknya) / jurnal gagal / jurnal terbit / dicocokkan. */
export function keteranganKas(k) {
  if (k.status === "void") return `Dibatalkan${k.void_journal_number ? ` · pembalik ${k.void_journal_number}` : ""}`;
  if (k.gl_status === "failed") return `Jurnal gagal${k.gl_error ? `: ${k.gl_error}` : ""}`;
  const bagian = [k.journal_number ? `Jurnal ${k.journal_number}` : "Jurnal menunggu"];
  if (Number(k.reconciled_amount) > 0) bagian.push("dicocokkan mutasi bank");
  return bagian.join(" · ");
}

export default function FundTransferPreview({ doc }) {
  const { entities } = useEntityScope();
  const st = statusPindahDana(doc.status);
  const kas = (Array.isArray(doc.kas) ? doc.kas : []).map((k, i) => ({ ...k, id: k.id || `kas-${i}` }));
  const jejak = Array.isArray(doc.jejak) ? doc.jejak : [];
  const nominal = Number(doc.nominal) || 0;
  const biaya = Number(doc.biaya) || 0;
  const tunggu = doc.status === "menunggu_persetujuan" && doc.kontrol?.ditolak ? doc.kontrol.pesan : "";
  return (
    <div className="grid gap-3" data-testid="doc-preview-fund-transfer">
      {doc.terbit_error && doc.status === "menunggu_persetujuan" && (
        <p className="notice-bar warning text-fs-12" data-testid="doc-preview-ft-publish-error">Kas belum terbit: {doc.terbit_error}</p>
      )}
      {doc.batal_tertunda && (
        <p className="notice-bar warning text-fs-12" data-testid="doc-preview-ft-cancel-pending">
          Pembatalan belum tuntas{doc.batal_gl_error ? `: ${doc.batal_gl_error}` : "."} Teruskan dari layar Pindah Dana atau
          Keuangan › Posting Gagal.
        </p>
      )}
      <PreviewFacts items={[
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: <StatusBadge status={doc.status} label={st.label} tone={st.tone} icon={st.icon}
          testId="doc-preview-status" /> },
        { key: "from", label: "Dari", content: doc.rekening_asal },
        { key: "to", label: "Ke", content: doc.rekening_tujuan },
        { key: "send", label: "Tanggal kirim", content: doc.tanggal_kirim ? formatDate(doc.tanggal_kirim) : "" },
        { key: "receive", label: doc.tanggal_diterima ? "Diterima" : "Rencana tiba",
          content: doc.tanggal_diterima ? formatDate(doc.tanggal_diterima) : (doc.dua_tahap ? formatDate(doc.tanggal_terima) : "") },
        { key: "note", label: "Catatan", content: doc.catatan },
        { key: "reason", label: "Alasan batal", content: doc.alasan_batal },
      ]} />
      {tunggu && <p className="text-fs-12 text-kn-text-2" data-testid="doc-preview-ft-control">{tunggu}</p>}
      <PreviewLines columns={KOLOM_KAS} rows={kas} testId="doc-preview-ft-cash"
        empty={doc.status === "menunggu_persetujuan" ? "Kas terbit sesudah disetujui." : "Belum ada kas."} />
      <PreviewTotals rows={[
        { label: "Nominal dipindah", value: formatCurrency(nominal), strong: true },
        { label: "Biaya transfer", value: biaya > 0 ? formatCurrency(biaya) : "" },
        { label: "Keluar dari rekening asal", value: biaya > 0 ? formatCurrency(nominal + biaya) : "" },
      ]} />
      {jejak.length > 0 && (
        <ol className="grid gap-1 border-t border-kn-divider pt-2" data-testid="doc-preview-ft-history">
          {jejak.map((j, i) => (
            <li key={`${j.aksi}-${i}`} className="text-fs-12 text-kn-text-2">
              <span className="font-semibold text-kn-text">{JEJAK_LABEL[j.aksi] || j.aksi}</span>
              {/* catatan server memuat tanggal ISO ("diterima 2026-11-27") → tanggal baku ("27 Nov 2026") */}
              {j.oleh ? ` · ${j.oleh}` : ""}{j.pada ? ` · ${formatDateTime(j.pada)}` : ""}{j.catatan ? ` — ${formatDatesInText(j.catatan)}` : ""}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
