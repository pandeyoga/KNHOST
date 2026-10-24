/**
 * ReturnPoliciesView (R0) — Master Kebijakan Retur Jual.
 * CRUD kebijakan retur jual dengan scope global / kategori / customer + eligibility fields.
 * Koleksi kanonik: sales_return_policies (prefix srp_). Endpoint: /api/sales-return-policies.
 */
import { useEffect, useMemo, useState } from "react";
import ReturnAssumptionsPanel from "./ReturnAssumptionsPanel";
import CutlossSimulator from "./CutlossSimulator";
import axios, { API } from "../../services/apiClient";
import { ScrollText, Plus, X, Pencil, Power, ShieldCheck } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import useListSearch from "@/hooks/useListSearch";
import FormModal from "../../components/FormModal";
import ConfirmModal from "../../components/ConfirmModal";
import { can } from "../../config/roles";

const RETURN_TYPES = [
  { value: "retur", label: "Retur" }, { value: "bs", label: "Barang Sisa" },
  { value: "penggantian", label: "Penggantian" }, { value: "komplain", label: "Komplain" },
  { value: "garansi", label: "Garansi" },
];
const OUTCOMES = [
  { value: "refund", label: "Pengembalian Dana Tunai" }, { value: "store_credit", label: "Store Credit" },
  { value: "nego", label: "Nego (Diskon)" }, { value: "reject", label: "Tolak" },
];
const EMPTY = {
  name: "", scope: "global", scope_ref: "", window_days: 30,
  allowed_return_types: RETURN_TYPES.map((t) => t.value),
  allowed_outcomes: OUTCOMES.map((o) => o.value),
  restocking_fee_pct: 0, require_inspection: true, enforce_window: false,
  link_to_supplier_window: false, condition_requirements: "", notes: "",
};

function ScopePill({ scope }) {
  const map = { global: "pill-success", category: "pill-warning", customer: "pill-muted" };
  const label = { global: "Umum", category: "Kategori", customer: "Pelanggan" };
  return <span className={`status-pill ${map[scope] || "pill-muted"}`} data-testid={`policy-scope-${scope}`}>{label[scope] || scope}</span>;
}

export default function ReturnPoliciesView({ currentUser }) {
  const [rows, setRows] = useState([]);
  const srch = useListSearch(rows, null, { testId: "policy", placeholder: "Cari kebijakan…" });
  const [cats, setCats] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [delTarget, setDelTarget] = useState(null);
  // Audit UI 24 Okt (037) — jendela default kebijakan baru = batas umum pelanggan di panel atas
  // (dulu form selalu 30 hari sementara panel menyatakan 21 hari).
  const [defaultWindow, setDefaultWindow] = useState(30);

  const canManage = can(currentUser?.permissions, "sales_return", "policy");   // keputusan owner 2026-10-21 — /sales-return-policies

  useEffect(() => { load(); loadMeta(); }, []); // eslint-disable-line

  async function load() {
    setLoading(true); setError("");
    try {
      const res = await axios.get(`${API}/sales-return-policies`);
      setRows(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat kebijakan retur.");
    } finally { setLoading(false); }
  }
  async function loadMeta() {
    const [c, cu, st] = await Promise.all([
      axios.get(`${API}/product-categories`).catch(() => ({ data: [] })),
      axios.get(`${API}/customers`).catch(() => ({ data: [] })),
      axios.get(`${API}/settings/effective`).catch(() => ({ data: {} })),
    ]);
    const win = parseInt(st.data?.returns?.customer_window_days, 10);
    if (win > 0) setDefaultWindow(win);
    setCats(Array.isArray(c.data) ? c.data : []);
    const cud = Array.isArray(cu.data) ? cu.data : (cu.data?.items || []);
    setCustomers(cud);
  }

  const scopeRefOptions = useMemo(() => {
    if (form.scope === "category") {
      return [{ value: "", label: "— Pilih Kategori —" },
        ...cats.map((c) => ({ value: c.name || c.id, label: c.name || c.id }))];
    }
    if (form.scope === "customer") {
      return [{ value: "", label: "— Pilih Pelanggan —" },
        ...customers.map((c) => ({ value: c.id, label: `${c.name}${c.code ? ` (${c.code})` : ""}` }))];
    }
    return [];
  }, [form.scope, cats, customers]);

  function openCreate() { setEditId(null); setForm({ ...EMPTY, window_days: defaultWindow }); setShowForm(true); }
  function openEdit(p) {
    setEditId(p.id);
    setForm({ ...EMPTY, ...p, window_days: p.window_days ?? defaultWindow });
    setShowForm(true);
  }

  const toggle = (field, val) => setForm((f) => {
    const cur = Array.isArray(f[field]) ? f[field] : [];
    return { ...f, [field]: cur.includes(val) ? cur.filter((x) => x !== val) : [...cur, val] };
  });

  async function submit() {
    if (!form.name.trim()) { setError("Nama kebijakan wajib diisi."); return; }
    if ((form.scope === "category" || form.scope === "customer") && !form.scope_ref) {
      setError("Pilih kategori/pelanggan untuk cakupan kebijakan ini terlebih dahulu."); return;
    }
    const payload = {
      ...form,
      window_days: parseInt(form.window_days, 10) || 0,
      restocking_fee_pct: parseFloat(form.restocking_fee_pct) || 0,
    };
    try {
      if (editId) {
        await axios.patch(`${API}/sales-return-policies/${editId}`, { data: payload });
        setNotice(`Kebijakan "${form.name}" diperbarui.`);
      } else {
        await axios.post(`${API}/sales-return-policies`, payload);
        setNotice(`Kebijakan "${form.name}" dibuat.`);
      }
      setShowForm(false); setEditId(null); setForm(EMPTY); await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal menyimpan kebijakan.");
    }
  }

  async function doDelete(p) {
    try {
      await axios.delete(`${API}/sales-return-policies/${p.id}`);
      setNotice(`Kebijakan "${p.name}" dinonaktifkan.`); setDelTarget(null); await load();
    } catch (e) { setError(e.response?.data?.detail || "Gagal menonaktifkan."); setDelTarget(null); }
  }

  return (
    <div data-testid="return-policies-view" className="view-container">
      <div className="view-header">
        <div>
          <h1 className="view-title">Kebijakan Retur Jual</h1>
          <p className="view-subtitle">Aturan retur per cakupan (umum / kategori / pelanggan): jendela hari, jenis retur, inspeksi wajib, biaya restok.</p>
        </div>
        {canManage && (
          <button data-testid="create-policy-button" onClick={openCreate} className="primary-button">
            <Plus size={13} /> Buat Kebijakan
          </button>
        )}
      </div>

      {notice && (
        <div className="notice-bar success" data-testid="policy-notice">
          <span>{notice}</span><button onClick={() => setNotice("")}><X size={13} /></button>
        </div>
      )}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="policy-error" />
      <ReturnAssumptionsPanel canManage={canManage} />
      <CutlossSimulator />

      {/* FASE P4 — form kebijakan retur menjadi POP-UP (dulu form panjang ini menyelip
          di atas daftar kebijakan). Logika form tidak diubah. */}
      <FormModal
        open={showForm && canManage}
        onClose={() => { setShowForm(false); setEditId(null); }}
        title={editId ? "Ubah Kebijakan Retur" : "Kebijakan Retur Baru"}
        subtitle="Jendela retur, biaya restok, jenis retur & penyelesaian yang diizinkan"
        icon={ShieldCheck}
        size="lg"
        testId="policy-form"
        onSubmit={submit}
        submitLabel={editId ? "Simpan Perubahan" : "Buat Kebijakan"}
        submitTestId="submit-policy-button"
        cancelTestId="cancel-policy-button"
        error={error}
      >
        <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Nama Kebijakan" req>
                <input data-testid="policy-name-input" value={form.name} className="field"
                  onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="mis. Retur Standar 30 Hari" />
              </Field>
              <Field label="Cakupan">
                <KNSelect data-testid="policy-scope-select" value={form.scope} className="field"
                  onValueChange={(v) => setForm({ ...form, scope: v, scope_ref: "" })}
                  options={[{ value: "global", label: "Umum (semua transaksi)" },
                    { value: "category", label: "Per Kategori" }, { value: "customer", label: "Per Pelanggan" }]} />
              </Field>
              {form.scope !== "global" && (
                <Field label={form.scope === "category" ? "Kategori" : "Pelanggan"} req>
                  <KNSelect data-testid="policy-scoperef-select" value={form.scope_ref} className="field"
                    onValueChange={(v) => setForm({ ...form, scope_ref: v })}
                    placeholder="Pilih..." options={scopeRefOptions} />
                </Field>
              )}
              <Field label="Jendela Retur (hari)">
                <input data-testid="policy-window-input" type="number" min="0" className="field"
                  value={form.window_days} onChange={(e) => setForm({ ...form, window_days: e.target.value })} placeholder={String(defaultWindow)} />
                <p className="mt-1 text-[11px] text-[#6B6B73]" data-testid="policy-window-hint">Batas umum saat ini {defaultWindow} hari dari Surat Jalan — isi angka lain bila kebijakan ini berbeda.</p>
              </Field>
              <Field label="Biaya Restok (%)">
                <input data-testid="policy-restocking-input" type="number" min="0" max="100" step="0.1" className="field tabular-nums"
                  value={form.restocking_fee_pct} onChange={(e) => setForm({ ...form, restocking_fee_pct: e.target.value })} placeholder="0" />
              </Field>
            </div>

            <div>
              <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1.5">Jenis Retur yang Diizinkan</label>
              <div className="flex flex-wrap gap-3">
                {RETURN_TYPES.map((t) => (
                  <label key={t.value} className="flex items-center gap-1.5 text-[11px] cursor-pointer">
                    <input type="checkbox" data-testid={`policy-type-${t.value}`}
                      checked={form.allowed_return_types.includes(t.value)} onChange={() => toggle("allowed_return_types", t.value)} />
                    {t.label}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1.5">Penyelesaian yang Diizinkan</label>
              <div className="flex flex-wrap gap-3">
                {OUTCOMES.map((o) => (
                  <label key={o.value} className="flex items-center gap-1.5 text-[11px] cursor-pointer">
                    <input type="checkbox" data-testid={`policy-outcome-${o.value}`}
                      checked={form.allowed_outcomes.includes(o.value)} onChange={() => toggle("allowed_outcomes", o.value)} />
                    {o.label}
                  </label>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap gap-4 pt-1">
              <label className="flex items-center gap-1.5 text-[11px] cursor-pointer">
                <input type="checkbox" data-testid="policy-require-inspection"
                  checked={form.require_inspection} onChange={(e) => setForm({ ...form, require_inspection: e.target.checked })} />
                Inspeksi wajib
              </label>
              <label className="flex items-center gap-1.5 text-[11px] cursor-pointer">
                <input type="checkbox" data-testid="policy-enforce-window"
                  checked={form.enforce_window} onChange={(e) => setForm({ ...form, enforce_window: e.target.checked })} />
                Tolak bila di luar jendela retur (bukan hanya peringatan)
              </label>
              <label className="flex items-center gap-1.5 text-[11px] cursor-pointer">
                <input type="checkbox" data-testid="policy-link-supplier"
                  checked={form.link_to_supplier_window} onChange={(e) => setForm({ ...form, link_to_supplier_window: e.target.checked })} />
                Samakan tenggat dengan batas retur supplier
              </label>
            </div>

            <Field label="Syarat Kondisi Barang">
              <input data-testid="policy-condition-input" className="field" value={form.condition_requirements}
                onChange={(e) => setForm({ ...form, condition_requirements: e.target.value })} placeholder="mis. kondisi asli, sertakan bukti foto" />
            </Field>
            <Field label="Catatan">
              <textarea data-testid="policy-notes-input" className="field" rows="2" value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Catatan kebijakan..." />
            </Field>
        </div>
      </FormModal>

      {/* Audit UI 24 Okt (037) — tabel grid buatan sendiri → .table-container + .data-table: di HP kepala kolom
          tidak lagi bertumpuk ("NAMA / / SCOPE"), tabel digeser horizontal dan tombol aksi tetap terjangkau. */}
      <div className="section-card">
        {srch.toolbar}
        {loading ? (
          <div className="py-10 text-center text-[12px] text-[#6B6B73]">Memuat kebijakan...</div>
        ) : srch.shown.length === 0 ? (
          <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid="policy-empty">
            <ScrollText className="mx-auto mb-2 text-gray-300" size={28} />
            <p>Belum ada kebijakan retur. {canManage ? "Buat kebijakan pertama." : ""}</p>
          </div>
        ) : (
          <div className="table-container !rounded-none !border-x-0 !border-b-0">
            <table className="data-table" style={{ minWidth: 640 }}>
              <thead>
                <tr className="whitespace-nowrap">
                  <th>Nama / Cakupan</th><th>Jendela</th><th>Inspeksi</th><th>Jenis / Restok</th><th className="text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {srch.pageRows.map((p) => (
                  <tr key={p.id} data-testid={`policy-row-${p.id}`}>
                    <td>
                      <p className="text-[12px] font-semibold flex flex-wrap items-center gap-1.5">{p.name} <ScopePill scope={p.scope} /></p>
                      <p className="text-[11px] text-[#6B6B73]">{p.scope_ref || "semua transaksi"}</p>
                    </td>
                    <td className="text-[11.5px] tabular-nums whitespace-nowrap">{p.window_days} hari</td>
                    <td>{p.require_inspection
                      ? <span className="status-pill pill-success"><ShieldCheck size={9} className="inline" /> Wajib</span>
                      : <span className="status-pill pill-muted">Opsional</span>}</td>
                    <td>
                      <p className="text-[11px] text-[#6B6B73]">{(p.allowed_return_types || []).length} jenis · restok {Number(p.restocking_fee_pct || 0)}%</p>
                      {p.enforce_window && <p className="text-[11px] text-[#A05000]">di luar jendela ditolak</p>}
                    </td>
                    <td className="text-right whitespace-nowrap">
                      {canManage && (
                        <span className="inline-flex items-center justify-end gap-1">
                          <button data-testid={`edit-policy-${p.id}`} onClick={() => openEdit(p)} className="icon-button" title="Ubah"><Pencil size={13} /></button>
                          <button data-testid={`delete-policy-${p.id}`} onClick={() => setDelTarget(p)} className="icon-button text-red-400 hover:text-red-600" title="Nonaktifkan"><Power size={13} /></button>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {srch.pager}
      </div>

      <ConfirmModal
        open={!!delTarget}
        title={`Nonaktifkan "${delTarget?.name || "Kebijakan"}"`}
        message="Kebijakan yang dinonaktifkan tidak lagi dipakai untuk evaluasi retur baru."
        confirmLabel="Nonaktifkan" danger
        onConfirm={() => doDelete(delTarget)} onCancel={() => setDelTarget(null)}
        testId="policy-delete-modal"
      />
    </div>
  );
}

function Field({ label, req, children }) {
  return (
    <div>
      <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">
        {label} {req && <span className="req">*</span>}
      </label>
      {children}
    </div>
  );
}
