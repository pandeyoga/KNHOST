import { useEffect, useState } from "react";
import axios, { API } from "../../../services/apiClient";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";

// GL-08 — Finance/Admin mengubah langsung (tanpa persetujuan kedua), alasan wajib, berlaku ke jurnal baru.
export function MappingEditDialog({ row, entityId, scopeLabel, onClose, onSaved }) {
  const [cands, setCands] = useState(null);   // null = sedang dimuat
  const [code, setCode] = useState(row.account_code);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    axios.get(`${API}/gl/account-mappings/${row.key}/candidates`, { params: entityId ? { entity_id: entityId } : {} })
      .then((r) => setCands(r.data || [])).catch(() => setCands([]));
  }, [row.key, entityId]);
  const canReset = (entityId && row.source === "entity") || (!entityId && row.source === "global");
  const run = async (fn) => {
    setBusy(true); setErr("");
    try { await fn(); onSaved(); } catch (e) { setErr(e.response?.data?.detail || e.message); } finally { setBusy(false); }
  };
  const save = () => run(() => axios.put(`${API}/gl/account-mappings/${row.key}`, { account_code: code, entity_id: entityId || "", reason }));
  const reset = () => run(() => axios.post(`${API}/gl/account-mappings/${row.key}/reset`, { entity_id: entityId || "", reason }));
  return (
    <FormModal open onClose={onClose} title={`Ubah akun · ${row.label}`} testId="glmap-edit-modal">
      <div className="grid gap-3 text-[12px]">
        <p className="text-[#6B6B73]">Berlaku untuk: <b data-testid="glmap-edit-scope">{scopeLabel}</b>. Pilihan hanya menampilkan akun berjenis {row.allowed_type_labels.join(" / ")} yang aktif dan bisa diposting.</p>
        <label className="grid gap-1"><span>Akun <span className="text-[#B42318]">*</span></span>
          <KNSelect searchable data-testid="glmap-edit-account" className="field" value={code} onValueChange={setCode}
            options={(cands || []).map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` }))} placeholder="Cari kode / nama akun" />
        </label>
        {/* UAT 24 Okt (audit UI tahap 2) — G1-08: daftar kandidat kosong dijelaskan, bukan sekadar "Tidak ada hasil". */}
        {cands && cands.length === 0 && (
          <p className="rounded-md bg-[#FFF1F1] border border-[#F5C2C0] px-2 py-1.5 text-[11px] text-[#B42318]" data-testid="glmap-edit-no-cands">
            Tidak ada akun berjenis {row.allowed_type_labels.join(" / ")} yang aktif &amp; bisa dijurnal. Tambahkan atau aktifkan akunnya di Bagan Akun dulu.
          </p>
        )}
        <label className="grid gap-1"><span>Alasan perubahan <span className="text-[#B42318]">*</span></span>
          <textarea data-testid="glmap-edit-reason" className="field min-h-[64px]" value={reason} onChange={(e) => setReason(e.target.value)} placeholder={`Mengapa akun ${String(row.label || "").toLowerCase()} diubah? (min. 5 huruf)`} />
        </label>
        <p className="rounded-md bg-[#FFF8E6] border border-[#F5D68A] px-2 py-1.5 text-[11px]" data-testid="glmap-edit-warning">Perubahan berlaku untuk jurnal baru; jurnal lama tidak diposting ulang.</p>
        {err && <p className="text-[#B42318]" data-testid="glmap-edit-error">{err}</p>}
        <div className="flex justify-between gap-2">
          {canReset ? <button type="button" className="secondary-button text-xs" disabled={busy || reason.trim().length < 5} data-testid="glmap-edit-reset" onClick={reset}>{entityId ? "Kembali ke global" : "Kembali ke bawaan"}</button> : <span />}
          <span className="flex gap-2">
            <button type="button" className="secondary-button text-xs" onClick={onClose} data-testid="glmap-edit-cancel">Batal</button>
            <button type="button" className="primary-button text-xs" disabled={busy || !code || reason.trim().length < 5} data-testid="glmap-edit-save" onClick={save}>Simpan</button>
          </span>
        </div>
      </div>
    </FormModal>
  );
}
