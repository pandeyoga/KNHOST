/**
 * LaporBayarDialog (LB-T7) — pop-up "Lapor bayar" di rincian pesanan: pelanggan sudah transfer, sales melaporkan dengan
 * bukti; Finance memeriksa lalu Terima (kwitansi terbit) atau Tolak. Satu pop-up (`FormModal`), tanpa layar baru.
 *
 * Props: `{ order, shortfall, camera, onClose, onDone }` — `camera` (HP) = input berkas membuka kamera belakang; `order` = pesanan (id, number, entity_id, receiving_account_id);
 * `shortfall` = nominal bawaan (kurang bayar dari gerbang bayar — satu hitungan server); `onDone()` dipanggil sesudah
 * laporan terbentuk (muat ulang daftar).
 *
 * Aturan yang dicerminkan dari server (server tetap penentu): nominal > 0; cara bayar dari daftar induk PT, bukan
 * tunai dan bukan yang berjatuh tempo (giro/cek); rekening dari `bank-accounts/receiving` PT pesanan; rekening ≠ rekening
 * instruksi bayar pesanan → "Alasan rekening berbeda" wajib (`mismatch_note`); nomor referensi wajib bila PT memintanya
 * (`payment.wajib_nomor_referensi`) dan cara bayarnya memakai referensi; bukti wajib.
 * Urutan kirim: buat laporan → unggah bukti. Bila unggah gagal laporan tetap ada; baris laporan menawarkan unggah ulang.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Send } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import KNDatePicker from "../../../components/KNDatePicker";
import MoneyInput from "../../../components/MoneyInput";
import { formatCurrency, todayWib } from "../../../utils/formatters";
import { heldMoney } from "../../../utils/parseMoney";
import { apiErrorText } from "../../../utils/apiError";
import { notifySuccess } from "../../../utils/feedback";
import { toast } from "../../../hooks/use-toast";
import useIntentKey from "../../../hooks/useIntentKey";
import { usePaymentMethods } from "../../../config/paymentMethods";
import { accountText } from "../../pos/CheckoutPaymentDestination";
import { ALASAN_MIN, createReport, proofProblem, uploadProof } from "./payReportApi";

export const PESAN_BUKTI_BELUM = "Bukti belum terunggah — unggah ulang dari daftar laporan.";

export default function LaporBayarDialog({ order, shortfall = 0, camera = false, onClose, onDone }) {
  const entityId = order?.entity_id || "";
  const pm = usePaymentMethods("masuk", entityId);
  // Server menolak tunai (tanpa bukti transfer) dan cara bayar berjatuh tempo (giro/cek): jangan ditawarkan.
  const methodRows = useMemo(
    () => pm.methods.filter((m) => m.needs_account === "bank" && !m.needs_due_date), [pm.methods]);
  const [amount, setAmount] = useState(() => String(Math.max(Number(shortfall) || 0, 0) || ""));
  const [date, setDate] = useState(todayWib());
  const [method, setMethod] = useState("");
  const [accounts, setAccounts] = useState({ key: "", rows: [], loading: false, failed: false });
  const [accountId, setAccountId] = useState("");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [mismatchNote, setMismatchNote] = useState("");
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState("");
  const [refRequired, setRefRequired] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const intent = useIntentKey("lb");
  const proofIntent = useIntentKey("lbup");
  const touched = useRef(false);

  const methodRow = methodRows.find((m) => m.code === method) || null;
  const methodOptions = useMemo(() => methodRows.map((m) => ({ value: m.code, label: m.name })), [methodRows]);

  useEffect(() => {   // cara bayar bawaan: satu-satunya pilihan
    if (!method && methodRows.length === 1) setMethod(methodRows[0].code);
  }, [methodRows, method]);

  useEffect(() => {   // pengaturan PT: nomor referensi wajib?
    let alive = true;
    axios.get(`${API}/settings/effective`, { params: entityId ? { entity_id: entityId } : {} })
      .then((r) => { if (alive) setRefRequired(Boolean(r.data?.payment?.wajib_nomor_referensi)); })
      .catch(() => { if (alive) setRefRequired(false); });
    return () => { alive = false; };
  }, [entityId]);

  useEffect(() => {   // rekening penerimaan PT pesanan untuk cara bayar itu
    if (!method) { setAccounts({ key: "", rows: [], loading: false, failed: false }); return undefined; }
    let alive = true;
    const key = `${entityId}|${method}`;
    setAccounts({ key, rows: [], loading: true, failed: false });
    axios.get(`${API}/bank-accounts/receiving`, { params: { ...(entityId ? { entity_id: entityId } : {}), method } })
      .then((r) => {
        if (!alive) return;
        const rows = Array.isArray(r.data) ? r.data : [];
        setAccounts({ key, rows, loading: false, failed: false });
        // Isi otomatis: rekening instruksi bayar pesanan → bawaan PT → satu-satunya; pilihan pengguna tidak ditimpa.
        setAccountId((cur) => {
          if (touched.current && rows.some((a) => a.id === cur)) return cur;
          const pick = rows.find((a) => a.id === order?.receiving_account_id) || rows.find((a) => a.is_default)
            || (rows.length === 1 ? rows[0] : null);
          return pick ? pick.id : "";
        });
      })
      .catch(() => { if (alive) setAccounts({ key, rows: [], loading: false, failed: true }); });
    return () => { alive = false; };
  }, [entityId, method]); // eslint-disable-line react-hooks/exhaustive-deps

  const num = heldMoney(amount);
  const beda = Boolean(accountId && order?.receiving_account_id && accountId !== order.receiving_account_id);
  const chosen = accounts.rows.find((a) => a.id === accountId) || null;
  const needRef = refRequired && Boolean(methodRow?.needs_reference);

  // Alasan tombol kirim mati ("" = boleh) — tampil di samping tombol supaya tidak membingungkan.
  const block = (() => {
    if (!(num > 0)) return "Isi nominal yang dilaporkan.";
    if (!date) return "Isi tanggal transfer.";
    if (!method) return "Pilih cara bayar.";
    if (accounts.loading) return "Memuat rekening penerima…";
    if (!accounts.rows.length) return "Belum ada rekening penerimaan untuk cara bayar ini — minta Finance mengaturnya di Kas & Bank.";
    if (!accountId) return "Pilih rekening tujuan.";
    if (needRef && !reference.trim()) return `Isi nomor referensi (wajib untuk ${methodRow?.name || "cara bayar ini"}).`;
    if (beda && mismatchNote.trim().length < ALASAN_MIN) return "Isi alasan rekening berbeda dari instruksi bayar pesanan.";
    if (!file) return "Lampirkan bukti bayar.";
    return "";
  })();

  const pickFile = (e) => {
    const f = e.target.files?.[0] || null;
    const p = f ? proofProblem(f) : "";
    setFileError(p);
    setFile(p ? null : f);
  };

  const submit = async () => {
    if (inFlight.current || block) return;
    inFlight.current = true;
    setBusy(true); setError("");
    const body = {
      amount: num, transfer_date: date, account_id: accountId, method,
      ...(reference.trim() ? { reference_no: reference.trim() } : {}),
      ...(note.trim() ? { note: note.trim() } : {}),
      ...(beda ? { mismatch_note: mismatchNote.trim() } : {}),
    };
    let rep;
    try {
      rep = await intent.send(body, (k) => createReport(order.id, body, k));
    } catch (e) {
      setError(apiErrorText(e, "Laporan bayar belum bisa dikirim."));
      setBusy(false); inFlight.current = false;
      return;
    }
    try {
      await proofIntent.send({ id: rep.id, n: file.name, s: file.size }, (k) => uploadProof(rep.id, file, k));
      notifySuccess("Laporan bayar dikirim ke Finance", `${rep.number || ""} · ${formatCurrency(num)}`.trim());
    } catch (e) {
      // Laporan sudah ada tetapi tanpa bukti — Finance tidak bisa menerimanya; baris laporan menawarkan unggah ulang.
      // R15 M4 — ini kabar GAGAL (bukti belum ada → Finance belum bisa menerima), bukan sukses: toast galat.
      toast({ title: "Laporan bayar dibuat, bukti belum terunggah", variant: "destructive",
        description: `${PESAN_BUKTI_BELUM} ${apiErrorText(e, "")}`.trim() });
    }
    setBusy(false); inFlight.current = false;
    onDone?.(rep);
  };

  return (
    <FormModal open onClose={onClose} title="Lapor bayar" subtitle={order?.number ? `Pesanan ${order.number}` : ""}
      icon={Send} size="md" testId="lapor-bayar-modal" busy={busy} error={error}
      onSubmit={submit} submitLabel="Kirim ke Finance" submitDisabled={Boolean(block)} submitTestId="lapor-bayar-submit">
      <div className="space-y-3">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div>
            <label className="field-label" htmlFor="lapor-bayar-amount">Nominal ditransfer *</label>
            <MoneyInput testId="lapor-bayar-amount" id="lapor-bayar-amount" className="field" value={amount} onChange={setAmount} placeholder="0" />
          </div>
          <div>
            <span className="field-label">Tanggal transfer *</span>
            <KNDatePicker data-testid="lapor-bayar-date" value={date} max={todayWib()} clearable={false}
              onChange={(d) => setDate(d || "")} />
          </div>
          <div>
            <span className="field-label">Cara bayar *</span>
            <KNSelect data-testid="lapor-bayar-method" className="field" value={method} options={methodOptions}
              placeholder="Pilih cara bayar" onValueChange={(v) => { if (v === method) return; setMethod(v); touched.current = false; setAccountId(""); }} />
          </div>
          <div>
            <span className="field-label">Rekening tujuan *</span>
            <KNSelect data-testid="lapor-bayar-account" className="field" value={accountId}
              disabled={!method || accounts.loading || accounts.rows.length === 0} placeholder="Pilih rekening tujuan"
              options={accounts.rows.map((a) => ({ value: a.id, label: `${a.name} · ${accountText(a)}` }))}
              onValueChange={(id) => { touched.current = true; setAccountId(id); }} />
            {accounts.failed && <p className="mt-1 text-fs-12 text-kn-danger-text">Daftar rekening gagal dimuat. Tutup lalu buka lagi.</p>}
          </div>
        </div>

        {beda && (
          <div className="rounded-md border border-kn-divider bg-kn-warning-soft px-3 py-2" data-testid="lapor-bayar-mismatch">
            <p className="text-fs-12 font-semibold text-kn-warning-text">
              Rekening ini berbeda dari rekening pada instruksi bayar pesanan{chosen ? ` (dipilih: ${chosen.name})` : ""}.
            </p>
            <label className="field-label mt-2 block" htmlFor="lapor-bayar-mismatch-note">Alasan rekening berbeda *</label>
            <textarea id="lapor-bayar-mismatch-note" data-testid="lapor-bayar-mismatch-note" className="field" rows={2}
              value={mismatchNote} placeholder="Contoh: pelanggan transfer ke rekening yang lain"
              onChange={(e) => setMismatchNote(e.target.value)} />
          </div>
        )}

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div>
            <label className="field-label" htmlFor="lapor-bayar-reference">{`No. referensi${needRef ? " *" : ""}`}</label>
            <input id="lapor-bayar-reference" data-testid="lapor-bayar-reference" className="field" value={reference}
              maxLength={80} placeholder="Nomor transaksi di bukti transfer" onChange={(e) => setReference(e.target.value)} />
          </div>
          <div>
            <label className="field-label" htmlFor="lapor-bayar-note">Catatan</label>
            <input id="lapor-bayar-note" data-testid="lapor-bayar-note" className="field" value={note} maxLength={500}
              placeholder="Opsional" onChange={(e) => setNote(e.target.value)} />
          </div>
        </div>

        <div>
          <label className="field-label" htmlFor="lapor-bayar-file">Bukti bayar * (foto atau PDF, maks. 10 MB)</label>
          {/* HP: `capture="environment"` membuka kamera belakang — foto bukti langsung dari HP sales (galeri tetap bisa). */}
          <input id="lapor-bayar-file" data-testid="lapor-bayar-file" type="file" className="field"
            {...(camera ? { accept: "image/*,application/pdf", capture: "environment" }
              : { accept: "image/jpeg,image/png,image/webp,image/gif,application/pdf" })}
            onChange={pickFile} />
          {file && <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="lapor-bayar-file-name">{file.name}</p>}
          {fileError && <p className="mt-1 text-fs-12 text-kn-danger-text" data-testid="lapor-bayar-file-error">{fileError}</p>}
        </div>
        {block && <p className="text-fs-12 text-kn-text-2" data-testid="lapor-bayar-block">{block}</p>}
      </div>
    </FormModal>
  );
}
