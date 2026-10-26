import { apiErrorText } from "../../utils/apiError";
import { useEffect, useMemo, useState } from "react";
import KNDatePicker from "@/components/KNDatePicker";
import axios, { API } from "../../services/apiClient";
import { Percent } from "lucide-react";
import { formatCurrency } from "../../utils/formatters";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";

/**
 * InputTaxCreateModal (Fase 5.5) — catat Faktur Pajak Masukan dari Vendor Bill.
 * DPP/PPN otomatis dari bill; user mengisi NSFP supplier (16-digit) + tanggal faktur.
 *
 * Fase 3 · P4 (L-03) — `.modal-card` buatan sendiri → FormModal baku (Esc/klik latar aman, layar penuh di HP,
 * galat tampil DI DALAM pop-up — dulu dikirim ke halaman di belakang pop-up sehingga tak terlihat). Isian tetap.
 */
const KODE_OPTIONS = [
  { value: "01", label: "01 — Penyerahan ke ber-NPWP (normal)" },
  { value: "02", label: "02 — Pemungut Bendaharawan" },
  { value: "03", label: "03 — Pemungut Selain Bendaharawan" },
  { value: "07", label: "07 — PPN Tidak Dipungut" },
  { value: "08", label: "08 — PPN Dibebaskan" },
];

export default function InputTaxCreateModal({ open, bills, onClose, onCreated, onError }) {
  const [billId, setBillId] = useState("");
  const [nsfp, setNsfp] = useState("");
  const [fakturDate, setFakturDate] = useState("");
  const [kode, setKode] = useState("01");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { if (!open) reset(); }, [open]);
  function reset() { setBillId(""); setNsfp(""); setFakturDate(""); setKode("01"); setNotes(""); setErr(""); }

  const bill = useMemo(() => (bills || []).find((b) => b.vendor_bill_id === billId), [bills, billId]);
  const billOptions = useMemo(() => (bills || []).map((b) => ({
    value: b.vendor_bill_id,
    label: `${b.bill_number} · ${b.supplier_name} · PPN ${formatCurrency(b.ppn_amount)}`,
  })), [bills]);

  async function submit() {
    if (!billId) { setErr("Pilih tagihan supplier sumber dulu."); return; }
    if (!nsfp.trim()) { setErr("NSFP (Nomor Seri Faktur Pajak) wajib diisi."); return; }
    setBusy(true); setErr("");
    try {
      const body = { vendor_bill_id: billId, nsfp: nsfp.trim(), faktur_date: fakturDate || "", kode_transaksi: kode, notes };
      const r = await axios.post(`${API}/input-tax-invoices`, body);
      onCreated?.(r.data);
    } catch (e) {
      const msg = apiErrorText(e, "Gagal mencatat Faktur Pajak Masukan.");
      setErr(msg);
      onError?.(msg);
    } finally { setBusy(false); }
  }

  return (
    <FormModal open={open} onClose={onClose} size="md" icon={Percent} testId="input-tax-create-modal"
      title="Catat Faktur Pajak Masukan" subtitle="DPP & PPN diambil dari tagihan supplier; isi NSFP dari pemasok."
      onSubmit={submit} submitLabel={busy ? "Menyimpan..." : "Catat Faktur Masukan"} submitTestId="it-submit"
      busy={busy} submitDisabled={!billId || !nsfp.trim()} error={err}>
        <div className="space-y-3">
          <Field label="Tagihan Supplier ber-PPN" req>
            {(bills || []).length === 0 ? (
              // UAT 24 Okt (audit UI tahap 2) — G1-37: tanpa tagihan, isian lain disembunyikan & ada jalan keluar.
              <p className="notice-bar warning !mb-0 text-[11.5px]" data-testid="it-no-bills">
                Belum ada tagihan supplier ber-PPN (terposting/lunas) yang belum dicatat.
                Posting tagihannya dulu di Tagihan Supplier.{" "}
                <a href="?view=vendor-bills" className="font-semibold underline" data-testid="it-goto-vendor-bills">Buka Tagihan Supplier</a>
              </p>
            ) : (
              <KNSelect value={billId} onValueChange={setBillId} options={billOptions}
                        className="field" placeholder="Pilih tagihan supplier..." data-testid="it-bill-select" />
            )}
          </Field>

          {bill && (
            <div className="grid grid-cols-2 gap-3 rounded-md bg-[#FAFBFC] border border-[#EFF0F2] p-3 sm:grid-cols-3" data-testid="it-bill-preview">
              <Info label="DPP" value={formatCurrency(bill.dpp)} />
              <Info label={`PPN (${bill.ppn_rate || 0}%)`} value={formatCurrency(bill.ppn_amount)} strong />
              <Info label="Total Tagihan" value={formatCurrency(bill.grand_total)} />
              <Info label="Supplier" value={bill.supplier_name} />
              <Info label="NPWP" value={bill.supplier_npwp || "—"} />
              <Info label="PO" value={bill.po_number || "—"} />
            </div>
          )}

          {(bills || []).length > 0 && (<>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="NSFP — No. Seri Faktur Pajak (16 digit)" req>
              <input data-testid="it-nsfp-input" value={nsfp} onChange={(e) => setNsfp(e.target.value)}
                className="field tabular-nums" placeholder="010.000-00.00000000" />
            </Field>
            <Field label="Tanggal Faktur Pajak">
              <KNDatePicker data-testid="it-faktur-date" value={fakturDate} onChange={setFakturDate} />
            </Field>
          </div>

          {/* Audit UI 24 Okt (067): label kode transaksi panjang → isian selebar modal agar tak terpotong. */}
          <Field label="Kode Transaksi">
            <KNSelect value={kode} onValueChange={setKode} options={KODE_OPTIONS} className="field" data-testid="it-kode-select" />
          </Field>
          <div>
            <Field label="Catatan">
              <input data-testid="it-notes-input" value={notes} onChange={(e) => setNotes(e.target.value)}
                className="field" placeholder="opsional" />
            </Field>
          </div>
          </>)}
        </div>
    </FormModal>
  );
}

function Field({ label, req, children }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-[#4A4B53] mb-1">{label}{req && <span className="text-red-500"> *</span>}</label>
      {children}
    </div>
  );
}

function Info({ label, value, strong }) {
  return (
    <div>
      <p className="text-[11px] font-bold uppercase text-[#9A9BA3]">{label}</p>
      <p className={`text-[12px] ${strong ? "font-bold" : "font-medium"} tabular-nums truncate text-[#0F1115]`}>{value}</p>
    </div>
  );
}
