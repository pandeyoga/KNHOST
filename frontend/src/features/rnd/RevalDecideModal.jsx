/** L03 LN-034 — hasil teknis uji ulang (lulus/gagal) untuk satu supplier: tanpa harga, tanpa kontrak baru. */
import { useEffect, useState } from "react";
import { ClipboardCheck } from "lucide-react";
import FormModal from "../../components/FormModal";
import KNSelect from "../../components/KNSelect";
import { Field, Footer, Hint } from "./RndField";
import { revalContractOptions } from "./rndApi";

const TYPE = { purchase: "pembelian", makloon: "makloon" };

function ContractField({ sampleId, value, onChange }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    revalContractOptions(sampleId).then((r) => setRows(r?.items || [])).catch(() => setRows([]));
  }, [sampleId]);
  return (
    <Field label="Referensi kontrak existing (opsional — hanya dicatat, isi kontrak tidak diubah)">
      <KNSelect data-testid="reval-contract-select" className="field" value={value} searchable
        options={[{ value: "", label: rows.length ? "— tanpa referensi kontrak —" : "— tidak ada kontrak supplier ini —" },
          ...rows.map((c) => ({ value: c.id, label: `${c.contract_number} · ${TYPE[c.contract_type] || c.contract_type}${c.product_id ? "" : " · umum"}${c.valid_to ? ` · s.d. ${c.valid_to}` : ""}${c.status === "terminated" ? " · dihentikan (referensi historis)" : ""}` }))]}
        onValueChange={onChange} />
    </Field>
  );
}

export default function RevalDecideModal({ sample, onClose, onConfirm, busy }) {
  const rv = sample.revalidation || {};
  const rounds = (sample.rounds || []).filter((r) => r.supplier_id === rv.supplier_id && r.result);
  const hasAcc = rounds.some((r) => r.result === "acc");
  const [result, setResult] = useState(hasAcc ? "pass" : "fail");
  const [note, setNote] = useState("");
  const [contractId, setContractId] = useState("");
  const noteOk = result === "pass" || note.trim().length >= 5;
  const passBlocked = result === "pass" && !hasAcc;
  return (
    <FormModal open onClose={onClose} size="md" testId="reval-decide-modal" icon={ClipboardCheck}
      title="Hasil Uji Ulang" subtitle={`${sample.number} · ${rv.supplier_name || ""} · siklus ${rv.cycle_no || 1}`}
      footer={<Footer onClose={onClose} onConfirm={() => onConfirm({ result, note, contract_id: contractId })} busy={busy} icon={ClipboardCheck}
        testId="reval-decide-confirm" confirmLabel={result === "pass" ? "Simpan: Lulus" : "Simpan: Gagal"}
        disabled={!noteOk || passBlocked} title={passBlocked ? "Belum ada round ACC dari supplier ini" : !noteOk ? "Tulis temuan kegagalan" : ""} />}>
      <div className="grid gap-3">
        <Hint testId="reval-decide-info">Keputusan teknis untuk <b>{rv.supplier_name}</b> saja. Tidak ada harga baru, kontrak tidak dibuat atau diubah, dan SKU {sample.product_sku} tetap.</Hint>
        <div className="flex gap-1.5" data-testid="reval-result-picker">
          {[["pass", "Lulus"], ["fail", "Gagal"]].map(([v, l]) => (
            <button key={v} type="button" data-testid={`reval-result-${v}`} onClick={() => setResult(v)}
              className={`rounded-full px-4 py-1.5 text-[11.5px] font-semibold transition-[background-color,color] ${result === v
                ? (v === "pass" ? "bg-[#1A7A3A] text-white" : "bg-[#C0392B] text-white") : "bg-[#F2F3F5] text-[#3C3C43]"}`}>{l}</button>
          ))}
        </div>
        {passBlocked && <Hint tone="warn" testId="reval-no-acc">Belum ada round ACC dari supplier ini — hanya bisa dinyatakan gagal.</Hint>}
        {result === "fail" && <Hint tone="danger" testId="reval-fail-info">Hasil gagal masuk <b>Menunggu keputusan PIC</b>. Produksi, stok, dan kontrak yang berjalan tidak dihentikan otomatis.</Hint>}
        <Field label={result === "fail" ? "Temuan kegagalan * (min. 5 karakter)" : "Catatan"}>
          <textarea className="field" rows={3} data-testid="reval-decide-note" value={note} onChange={(e) => setNote(e.target.value)}
            placeholder={result === "fail" ? "mis. ΔE 2.4 di atas toleransi, handfeel lebih kasar" : "mis. warna & handfeel sesuai acuan"} />
        </Field>
        <ContractField sampleId={sample.id} value={contractId} onChange={setContractId} />
      </div>
    </FormModal>
  );
}
