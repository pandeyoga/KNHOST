/**
 * ChartOfAccountsParts — konstanta & pop-up Bagan Akun (dipisah dari ChartOfAccounts.jsx agar < 500 baris).
 *
 * Fase 3 · P4 (L-03) — tiga pop-up buatan sendiri diganti cangkang baku:
 *  · form "Tambah Akun" yang dulu DISELIPKAN di atas tabel (inline) → `AddAccountModal` (FormModal);
 *  · "Ubah Akun" (`div fixed inset-0`) → `EditAccountModal` (FormModal; galat server tampil di dalam pop-up);
 *  · "Detail & riwayat" (`div fixed inset-0`) → `AccountDetailModal` (DetailModal framed + PageTabs).
 * Isian, aturan simpan & testid isian tidak berubah.
 */
import { apiErrorText } from "../../utils/apiError";
import { useState } from "react";
import { BookOpen, Pencil, Plus } from "lucide-react";
import AuditHistoryPanel from "../../components/AuditHistoryPanel";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";
import DetailModal from "../../components/DetailModal";
import PageTabs from "../../components/PageTabs";

export const TYPE_META = {
  asset: { label: "Aset", tone: "bg-[#E7F0FF] text-[#0058CC]" },
  liability: { label: "Kewajiban", tone: "bg-[#FDEDE7] text-[#C0392B]" },
  equity: { label: "Ekuitas", tone: "bg-[#F3EAFB] text-[#6B219A]" },
  income: { label: "Pendapatan", tone: "bg-[#E6F6EC] text-[#1B7F4B]" },
  expense: { label: "Beban", tone: "bg-[#FFF4E0] text-[#B45309]" },
};
export const TYPE_ORDER = ["asset", "liability", "equity", "income", "expense"];
export const TYPE_OPTIONS = TYPE_ORDER.map((t) => ({ value: t, label: TYPE_META[t].label }));
export const EMPTY_FORM = { code: "", name: "", type: "asset", parent_code: "", is_postable: true };

/** Tambah akun — dulu form inline di atas tabel (`coa-add-form`), kini pop-up. */
export function AddAccountModal({ open, scopeEntityId, scopeLabel, parentOptions, onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const close = () => { setForm(EMPTY_FORM); setErr(""); onClose(); };

  const submit = async () => {
    if (!form.code.trim() || !form.name.trim()) return;
    setSaving(true); setErr("");
    try {
      const params = scopeEntityId ? { entity_id: scopeEntityId } : {};
      await axios.post(`${API}/gl/accounts`, form, { params });
      setForm(EMPTY_FORM);
      await onSaved();
    } catch (e) {
      setErr(apiErrorText(e, "Gagal membuat akun."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <FormModal open={open} onClose={close} title="Tambah Akun" icon={Plus} size="md"
      subtitle={scopeEntityId
        ? `Akun akan dibuat khusus untuk PT ${scopeLabel}.`
        : "Akun akan dibuat sebagai template global (semua PT)."}
      testId="coa-add-form" onSubmit={submit} busy={saving} error={err}
      submitDisabled={!form.code.trim() || !form.name.trim()}
      submitLabel={saving ? "Menyimpan..." : "Simpan Akun"} submitTestId="coa-form-submit">
      <div className="grid gap-3 sm:grid-cols-2">
        <Labeled label="Kode Akun">
          <input data-testid="coa-form-code" className="field py-1 text-[12px] tabular-nums" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="6-5000" required />
        </Labeled>
        <Labeled label="Nama Akun">
          <input data-testid="coa-form-name" className="field py-1 text-[12px]" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Beban Pemasaran" required />
        </Labeled>
        <Labeled label="Tipe">
          <KNSelect data-testid="coa-form-type" className="field py-1 text-[12px]" value={form.type} onValueChange={(v) => setForm({ ...form, type: v })} options={TYPE_OPTIONS} />
        </Labeled>
        <Labeled label="Akun Induk (opsional)">
          <KNSelect data-testid="coa-form-parent" className="field py-1 text-[12px]" value={form.parent_code} onValueChange={(v) => setForm({ ...form, parent_code: v })} options={parentOptions} placeholder="— Tanpa induk —" />
        </Labeled>
        <Labeled label="Jenis Akun">
          <div className="flex gap-1 mt-0.5">
            {[{ k: true, t: "Detail" }, { k: false, t: "Kelompok" }].map((o) => (
              <button type="button" key={String(o.k)} data-testid={`coa-form-postable-${o.k}`}
                aria-pressed={form.is_postable === o.k}
                className={`flex-1 text-[12px] font-semibold rounded-md py-1 border ${form.is_postable === o.k ? "bg-[#6B219A] text-white border-[#6B219A]" : "bg-white border-[#EFF0F2] text-[#6B6B73]"}`}
                onClick={() => setForm({ ...form, is_postable: o.k })}>{o.t}</button>
            ))}
          </div>
        </Labeled>
      </div>
    </FormModal>
  );
}

export function EditAccountModal({ acc, scopeEntityId, scopeLabel, onClose, onSaved }) {
  const [name, setName] = useState(acc.name);
  const [isActive, setIsActive] = useState(acc.is_active !== false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const save = async () => {
    setSaving(true); setErr("");
    try {
      const params = scopeEntityId ? { entity_id: scopeEntityId } : {};
      await axios.patch(`${API}/gl/accounts/${acc.code}`, { name: name.trim(), is_active: isActive }, { params });
      await onSaved();
    } catch (e) {
      // Dulu pop-up ditutup lalu galat tampil di halaman; kini galat tampil di pop-up (isian tidak hilang).
      setErr(apiErrorText(e, "Gagal menyimpan akun."));
    } finally {
      setSaving(false);
    }
  };

  const willOverride = scopeEntityId && acc.entity_id !== scopeEntityId;

  return (
    <FormModal open onClose={onClose} title={`Ubah Akun ${acc.code}`} icon={Pencil} size="sm"
      testId="coa-edit-modal" onSubmit={save} busy={saving} error={err}
      submitLabel={saving ? "Menyimpan..." : "Simpan"} submitTestId="coa-edit-save">
      <div className="space-y-3">
        <Labeled label="Nama Akun">
          <input data-testid="coa-edit-name" className="field py-1.5 text-[13px]" value={name} onChange={(e) => setName(e.target.value)} />
        </Labeled>
        <label className="flex items-center gap-2 text-[12px] text-[#3C3C43]">
          <input data-testid="coa-edit-active" type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          {/* G1-22 — akun kelompok (is_postable=false) memang tidak bisa dijurnal; label mengikuti jenisnya. */}
          {acc.is_postable === false ? "Akun aktif (kelompok — tidak dijurnal)" : "Akun aktif (dapat dijurnal)"}
        </label>
        {willOverride && (
          <p data-testid="coa-edit-override-note" className="text-[11px] text-[#6B219A] bg-[#F3EAFB] rounded-md px-2 py-1.5">
            Perubahan ini akan membuat <b>override</b> khusus untuk PT <b>{scopeLabel}</b>. Template global & PT lain tidak terpengaruh.
          </p>
        )}
        {acc.system && !scopeEntityId && <p className="text-[11px] text-[#8E8E93]">Akun baku sistem — hanya nama & status aktif yang dapat diubah.</p>}
      </div>
    </FormModal>
  );
}

export function AccountDetailModal({ acc, canAudit, scopeLabel, entities, onClose }) {
  const [tab, setTab] = useState("info");
  const layer = acc.entity_id ? (entities.find((e) => e.id === acc.entity_id)?.short_name || "Badan usaha tidak dikenal") : "Template global";
  const info = [
    ["Kode", acc.code], ["Nama", acc.name], ["Jenis", TYPE_META[acc.type]?.label || acc.type],
    ["Induk", acc.parent_code || "—"], ["Saldo normal", acc.normal_balance === "debit" ? "Debit" : "Kredit"],
    ["Detail/Kelompok", acc.is_postable ? "Detail (dapat dijurnal)" : "Kelompok (tidak dijurnal)"], ["Status", acc.is_active === false ? "Nonaktif" : "Aktif"],
    ["Lapisan", layer], ["Dilihat sebagai", scopeLabel], ["Akun sistem", acc.system ? "Ya" : "Tidak"],
  ];
  return (
    // INV-UI-01 — DetailModal memakai overlayDismiss (opsi dropdown ber-portal tidak menutup pop-up); × melayang.
    <DetailModal onClose={onClose} framed size="md" label={`Akun ${acc.code}`} testId="coa-detail-modal">
      <div className="flex items-center gap-2 pb-2 pr-6">
        <BookOpen size={15} className="text-[#6B219A] shrink-0" />
        <h3 className="font-bold text-[14px] truncate" data-testid="coa-detail-title">
          <span className="font-mono tabular-nums text-[#6B6B73]">{acc.code}</span> · {acc.name}
        </h3>
      </div>
      <PageTabs testId="coa-detail-tabs" value={tab} onChange={setTab} ariaLabel="Rincian akun" tabs={[
        { key: "info", label: "Rincian", testId: "coa-detail-tab-info" },
        { key: "history", label: "Riwayat Perubahan", testId: "coa-detail-tab-history", hidden: !canAudit },
      ]} />
      <div className="pt-3">
        {tab === "info" && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[12px]" data-testid="coa-detail-info">
            {info.map(([k, v]) => (
              <div key={k}><dt className="text-[10px] font-bold uppercase text-[#8E8E93]">{k}</dt><dd className="text-[#1C1C1E]">{v}</dd></div>
            ))}
          </dl>
        )}
        {tab === "history" && canAudit && (
          <AuditHistoryPanel entityType="gl_account" entityId={acc.code} testIdPrefix="coa-history" showLayer />
        )}
      </div>
    </DetailModal>
  );
}

export function Labeled({ label, children }) {
  return (
    <div>
      <label className="text-[10px] font-bold uppercase text-[#8E8E93]">{label}</label>
      {children}
    </div>
  );
}

export function Kpi({ label, value, icon: Icon, tone = "", testId }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body flex items-center gap-3 py-3">
        <div className="w-9 h-9 rounded-lg bg-[#F3EAFB] flex items-center justify-center"><Icon size={17} className="text-[#6B219A]" /></div>
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
          <p className={`text-[17px] font-bold tabular-nums truncate ${tone || "text-[#1C1C1E]"}`} data-testid={`${testId}-value`}>{value}</p>
        </div>
      </div>
    </div>
  );
}
