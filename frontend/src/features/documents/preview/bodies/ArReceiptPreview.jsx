/**
 * Isi pratinjau kwitansi: fakta + alokasi ke pesanan. Data dari `GET /ar-receipts/{id}` (sudah termuat).
 * Alokasi dengan `order_id` dan izin baca pesanan = tombol yang menumpuk pratinjau pesanan; selain itu teks biasa.
 * F1 (§5.8) — kwitansi yang lahir dari satu baris mutasi bank (`source = "mutasi_bank"`, `bank_line_id`) menulis
 * "Lahir dari mutasi bank {tanggal} · {rekening} · ref …" (tanggal & rekening kwitansi = tanggal & rekening mutasi).
 * F1 §5.6 / R12 (gelombang akhir) — kwitansi itu, selama masih tertaut mutasinya (`bank_verified`), punya aksi
 * "Batalkan kwitansi dari mutasi" bagi pemegang `ar_receipt.void` + `cash.create` (izin rute yang sama): alasan ≥ 5 huruf
 * → `voidLineReceipt(bank_line_id)` (lepas tautan + batal kwitansi dalam satu permintaan; mutasi tidak diproses otomatis
 * lagi) → peringatan pesanan yang sudah dilepas ke gudang tampil di rincian. Tautan yang sudah dilepas (`bank_verified`
 * salah) = batal kwitansi biasa di Riwayat Pembayaran. Server tetap penentu (409 berkalimat tampil di rincian).
 */
import { useState } from "react";
import { XCircle } from "lucide-react";
import ErrorNotice from "../../../../components/ErrorNotice";
import { can } from "../../../../config/roles";
import { useEntityScope } from "../../../../context/EntityScopeContext";
import useIntentKey from "../../../../hooks/useIntentKey";
import { askReason } from "../../../../services/confirmService";
import { apiErrorText } from "../../../../utils/apiError";
import { entityShortById } from "../../../../utils/entityLabel";
import { notifySuccess } from "../../../../utils/feedback";
import { formatCurrency, formatDate } from "../../../../utils/formatters";
import { CustomerCardLink, DocPill } from "../../../finance/cards/partyCards";
import { ALASAN_BATAL_MIN, voidLineReceipt } from "../../../finance/bank/bankLineReceiptApi";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

export default function ArReceiptPreview({ doc, push, canPush, currentUser }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const [batal, setBatal] = useState(null);   // { peringatan } sesudah "Batalkan kwitansi dari mutasi" berhasil
  const [galat, setGalat] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const batalIntent = useIntentKey("f1batalkw");
  const alokasi = (Array.isArray(doc.allocations) ? doc.allocations : []).map((a, i) => ({ ...a, idx: i }));
  const bisaBuka = canPush("sales_order");
  const snap = doc.account_snapshot || {};
  const rekening = snap.name || [snap.bank_name, snap.account_number].filter(Boolean).join(" ");
  const dariMutasi = doc.source === "mutasi_bank" && Boolean(doc.bank_line_id);
  const asalMutasi = dariMutasi
    ? [`Lahir dari mutasi bank${doc.receipt_date ? ` ${formatDate(doc.receipt_date)}` : ""}`, rekening,
      doc.reference_no ? `ref ${doc.reference_no}` : ""].filter(Boolean).join(" · ") : "";
  const status = batal ? "void" : doc.status;
  const bisaBatal = dariMutasi && status !== "void" && Boolean(doc.bank_verified)
    && can(perms || {}, "ar_receipt", "void") && can(perms || {}, "cash", "create");

  async function batalkan() {
    if (sibuk) return;
    setGalat("");
    const reason = await askReason({
      title: `Batalkan kwitansi ${doc.number} dari mutasi?`, danger: true, reasonLabel: "Alasan membatalkan",
      message: `Kwitansi ${formatCurrency(doc.amount)} yang lahir dari mutasi bank dibatalkan dan tautan mutasinya `
        + "dilepas dalam satu langkah; mutasi kembali \"Perlu keputusan\" di Rekonsiliasi Bank dan tidak diproses "
        + "otomatis lagi. Bila pesanannya sudah dilepas ke gudang, barang tidak ditahan otomatis.",
      reasonMinLength: ALASAN_BATAL_MIN, confirmLabel: "Batalkan kwitansi", testId: "doc-preview-ar-receipt-void-reason",
    });
    if (reason === null) return;
    setSibuk(true);
    try {
      const out = await batalIntent.send({ line: doc.bank_line_id, reason },
        (k) => voidLineReceipt(doc.bank_line_id, reason, k));
      notifySuccess(`Kwitansi ${out?.receipt?.number || doc.number} dibatalkan`,
        "Mutasinya kembali perlu keputusan di Rekonsiliasi Bank dan tidak diproses otomatis lagi.");
      setBatal({ peringatan: out?.peringatan || "" });
    } catch (e) {
      setGalat(apiErrorText(e, "Kwitansi belum bisa dibatalkan dari mutasi."));
    } finally { setSibuk(false); }
  }

  const kolom = [
    { key: "order", label: "Pesanan", render: (a) => {
      const nomor = a.order_number || "—";
      if (!a.order_id || !bisaBuka) return <span data-testid={`doc-preview-alloc-${a.idx}-text`}>{nomor}</span>;
      return (
        <button type="button" className="link-button text-left" data-testid={`doc-preview-alloc-${a.idx}`}
          title="Lihat ringkasan pesanan"
          onClick={() => push({ docType: "sales_order", docId: a.order_id, number: a.order_number, ...(doc.entity_id ? { entityId: doc.entity_id } : {}) })}>
          {nomor}
        </button>);
    } },
    { key: "applied", label: "Dialokasikan", align: "right", render: (a) => <span className="font-semibold">{formatCurrency(a.applied)}</span> },
  ];

  return (
    <div className="grid gap-3" data-testid="doc-preview-ar-receipt">
      {asalMutasi && <p className="notice-bar info text-fs-12" data-testid="doc-preview-ar-receipt-source">{asalMutasi}</p>}
      {batal?.peringatan && (
        <p className="notice-bar warning text-fs-12" data-testid="doc-preview-ar-receipt-void-warning">{batal.peringatan}</p>
      )}
      <ErrorNotice message={galat} onDismiss={() => setGalat("")} testId="doc-preview-ar-receipt-void-error" />
      <PreviewFacts items={[
        { key: "customer", label: "Pelanggan", content: doc.customer_name
          ? <CustomerCardLink id={doc.customer_id} name={doc.customer_name} perms={perms} testId="doc-preview-customer" /> : "" },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: status ? <DocPill status={status} testId="doc-preview-status" /> : "" },
        { key: "date", label: "Tanggal", content: doc.receipt_date ? formatDate(doc.receipt_date) : "" },
        { key: "method", label: "Metode", content: doc.method || doc.payment_method_code },
        { key: "reference", label: "Referensi", content: doc.reference_no },
      ]} />
      <PreviewLines columns={kolom} rows={alokasi} empty="Belum dialokasikan ke pesanan." />
      <PreviewTotals rows={[{ label: "Jumlah kwitansi", value: doc.amount != null ? formatCurrency(doc.amount) : "", strong: true }]} />
      {bisaBatal && (
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="secondary-button btn-sm text-kn-danger-text" disabled={sibuk}
            data-testid="doc-preview-ar-receipt-void-line" onClick={batalkan}>
            <XCircle size={13} aria-hidden="true" />{sibuk ? "Memproses…" : "Batalkan kwitansi dari mutasi"}
          </button>
        </div>
      )}
    </div>
  );
}
