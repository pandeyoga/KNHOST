/**
 * EntityMasterKindPanel — tabel master BERLAPIS (global → badan usaha) untuk SATU jenis master (fase 3 · P2).
 *
 * KENAPA DIEKSTRAK: keputusan pemilik 26 Okt (D-01/D-02) — data yang sama dulu diedit di DUA layar:
 *   · Template Dokumen Dasar (AdminView) dan Master per Badan Usaha kind `document-templates` (koleksi sama);
 *   · Kategori Beban (editor akun COA) dan Master per Badan Usaha kind `expense-categories`.
 * Layar utamanya kini merender panel INI (lapisan global/khusus PT + baris baru) dengan form terlengkap dari layar
 * lamanya (`renderForm` / `fieldOptions`); Master per Badan Usaha cukup menautkan. Satu aturan lapisan, satu tempat.
 *
 * Yang dijaga (sama seperti sejak FASE E-4): setiap baris berlencana asal (Global / Badan usaha ini); baris global
 * yang ditimpa diredupkan; "Buat khusus <PT>" menyalin baris global; "Kembalikan ke global" melepas salinan; baris
 * global hanya bisa diubah di mode Semua Badan Usaha (server menolak 409). Hak tulis per jenis dihitung SERVER
 * (`data.can`). L-03/L-06: ubah baris = pop-up `FormModal` (dulu sel tabel diketik langsung); tabel = `ResponsiveTable`
 * (kolom aksi menempel kanan, kartu di HP).
 *
 * Props: `kind` · `entities` · `selectedEntity` · `fieldOptions` ({ field: options } untuk isian `select`) ·
 *   `renderForm({ mode, values, setValues })` (isi form khusus; bawaan = isian `CREATE_FIELDS[kind]`) ·
 *   `rowActions(row)` (aksi tambahan, mis. Pratinjau) · `notice` (node di atas tabel) · `onChanged()` · `testId`
 *   · `includeInactive` (baris nonaktif ikut tampil supaya bisa diaktifkan lagi) · `showRibbon` · `hintOverride`.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, CheckCircle2, Copy, Globe, Info, Layers3, Pencil, Plus, RefreshCw, RotateCcw, Search, X } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import KNSelect from "../../../components/KNSelect";
import FormModal from "../../../components/FormModal";
import ResponsiveTable from "../../../components/ResponsiveTable";
import useUomConversions from "../../../hooks/useUomConversions";   // FASE U
import { uomSelectOptions } from "../../../utils/uomCatalog";        // FASE U
import { entityShortById } from "../../../utils/entityLabel";
import { formatCurrency } from "../../../utils/formatters";
import { stripInternalCodes } from "../../../utils/cleanText";
import { apiErrorText } from "../../../utils/apiError";
import { askConfirm } from "../../../services/confirmService";
import { COLUMNS, CREATE_FIELDS, cellText, defaultsFor, parseFieldValue, toInputValue } from "./masterFieldsConfig";

export const cleanHint = (t) => stripInternalCodes(String(t || "").replace(/`([^`]+)`/g, "$1"));
const errText = (e, fb) => apiErrorText(e, fb) || fb;

/** Pita konteks — pengguna harus tahu ia sedang mengubah milik siapa. */
export function EntityScopeRibbon({ groupMode, entityLabel, testId = "em-scope-ribbon" }) {
  return (
    <div data-testid={testId}
      className={`flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-[12px] ${
        groupMode ? "border-[#F5C97B] bg-[#FFF7E6] text-[#8C4A00]" : "border-[#D6E6FF] bg-[#F0F6FF] text-[#004099]"}`}>
      {groupMode ? <Globe size={14} /> : <Building2 size={14} />}
      <span>
        {groupMode ? (
          <>Anda berada di mode <b>Semua Badan Usaha</b>. Di sini Anda mengubah nilai <b>Global</b> — perubahannya
            berlaku untuk <b>semua</b> badan usaha.</>
        ) : (
          <>Anda sedang mengatur <b>{entityLabel}</b>. Baris berlencana <b>Global</b> milik semua badan usaha dan tidak
            bisa diubah dari sini — pakai <b>Buat khusus {entityLabel}</b> untuk membuat salinannya.</>
        )}
      </span>
    </div>
  );
}

/** Isian bawaan (dari `CREATE_FIELDS[kind]`). */
export function MasterFields({ kind, values, setValues, fieldOptions = {} }) {
  useUomConversions();
  const optionsOf = (f) => fieldOptions[f.key]
    || (f.optionsFrom === "uom" ? uomSelectOptions({ dimensions: ["length", "weight", "count"] }) : (f.options || []));
  return (
    <div className="grid gap-2.5 sm:grid-cols-2">
      {(CREATE_FIELDS[kind] || []).map((f) => {
        const type = fieldOptions[f.key] ? "select" : f.type;
        return (
          <label key={f.key} className="grid gap-1 text-[11px] text-[#6B6B73]">
            <span className="font-semibold">{f.label}{f.required && <span className="text-[#C0392B]"> *</span>}</span>
            {type === "select" ? (
              <KNSelect data-testid={`em-form-${f.key}`} value={values[f.key] ?? ""} searchable={optionsOf(f).length > 12}
                onValueChange={(v) => setValues({ ...values, [f.key]: v })} options={optionsOf(f)} placeholder="Pilih…" />
            ) : type === "checkbox" ? (
              <input data-testid={`em-form-${f.key}`} type="checkbox" checked={Boolean(values[f.key])}
                onChange={(e) => setValues({ ...values, [f.key]: e.target.checked })} className="h-4 w-4" />
            ) : (
              <input data-testid={`em-form-${f.key}`} type={type === "number" ? "number" : "text"} className="field"
                value={toInputValue(f, values[f.key]) ?? ""} placeholder={f.placeholder || ""}
                onChange={(e) => setValues({ ...values, [f.key]: parseFieldValue(f, e.target.value) })} />
            )}
            {f.hint && <span className="text-[10px] text-[#8E8E93]" data-testid={`em-form-hint-${f.key}`}>{cleanHint(f.hint)}</span>}
          </label>
        );
      })}
    </div>
  );
}

export default function EntityMasterKindPanel({
  kind, entities = [], selectedEntity = "all", fieldOptions = {}, renderForm = null, rowActions = null,
  notice: topNotice = null, onChanged, testId = "em-panel", showRibbon = false, hintOverride = "", headerExtra = null,
  includeInactive = false,
}) {
  const activeList = useMemo(
    () => (entities || []).filter((e) => e.status !== "inactive" && e.status !== "archived"), [entities]);
  const groupMode = !selectedEntity || selectedEntity === "all";
  const entityLabel = groupMode ? "Semua Badan Usaha" : entityShortById(activeList, selectedEntity);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [busyId, setBusyId] = useState("");
  const [form, setForm] = useState(null);           // { mode: "create"|"edit", id, values, global }
  const [formErr, setFormErr] = useState("");

  // Keputusan owner 2026-10-21 — hak tulis per jenis master dihitung SERVER: data.can.{create,update,override,revert}.
  const canOp = (op) => !!data?.can?.[op];
  const manage = data?.manage !== false;

  const loadRows = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/entity-masters/${kind}`, { params: { include_inactive: includeInactive } });
      setData(res.data || null);
      setError("");
    } catch (e) {
      setData(null);
      setError(errText(e, "Gagal memuat baris master."));
    } finally { setLoading(false); }
  }, [kind, includeInactive]);
  useEffect(() => { loadRows(); }, [loadRows, selectedEntity]);

  const flash = (msg) => { setNotice(msg); setTimeout(() => setNotice(""), 4000); };
  const changed = async () => { await loadRows(); onChanged?.(); };

  const rows = useMemo(() => {
    const all = data?.rows || [];
    const q = search.trim().toLowerCase();
    return q ? all.filter((r) => JSON.stringify(r).toLowerCase().includes(q)) : all;
  }, [data, search]);
  const columns = COLUMNS[kind] || [{ key: data?.name_field || "name", label: "Nama" }];
  const fields = CREATE_FIELDS[kind] || [];
  const nameOf = (row) => row.name || row.label || row.code || row.doc_type || row.document_type || "ini";

  async function doOverride(row) {
    // G5-26 — dulu satu klik langsung POST salinan.
    if (!(await askConfirm({
      title: `Buat salinan khusus ${entityLabel}?`,
      message: `Baris global “${nameOf(row)}” disalin menjadi milik ${entityLabel}. `
        + "Setelah itu perubahan global tidak lagi berlaku untuk badan usaha ini sampai salinannya dikembalikan ke global.",
      confirmLabel: "Buat salinan",
    }))) return;
    setBusyId(row.id); setError("");
    try {
      await axios.post(`${API}/entity-masters/${kind}/${row.id}/override`);
      flash(`Salinan khusus ${entityLabel} dibuat — sekarang bisa diubah tanpa memengaruhi badan usaha lain.`);
      await changed();
    } catch (e) { setError(errText(e, "Gagal membuat salinan khusus badan usaha.")); } finally { setBusyId(""); }
  }

  async function doRevert(row) {
    if (!(await askConfirm({
      title: "Kembalikan ke nilai Global?",
      message: `Salinan khusus “${nameOf(row)}” dilepas; badan usaha ini kembali memakai baris Global.`,
      confirmLabel: "Kembalikan ke global",
    }))) return;
    setBusyId(row.id); setError("");
    try {
      const res = await axios.delete(`${API}/entity-masters/${kind}/${row.id}`);
      flash(res.data?.fell_back_to_global
        ? "Override dilepas — nilainya kembali mengikuti baris Global."
        : "Override dilepas. Tidak ada baris Global untuk kunci ini, jadi nilainya kini tidak diatur.");
      await changed();
    } catch (e) { setError(errText(e, "Gagal melepas override.")); } finally { setBusyId(""); }
  }

  const openCreate = () => { setFormErr(""); setForm({ mode: "create", values: defaultsFor(kind), global: false }); };
  const openEdit = (row) => { setFormErr(""); setForm({ mode: "edit", id: row.id, values: { ...row } }); };
  const setValues = (values) => setForm((f) => ({ ...f, values }));
  const missing = fields.filter((f) => f.required && !String(form?.values?.[f.key] ?? "").trim());

  async function saveForm() {
    if (!form) return;
    if (missing.length) { setFormErr(`Lengkapi dulu: ${missing.map((m) => m.label).join(", ")}.`); return; }
    if (form.mode === "create" && form.global && !groupMode && !(await askConfirm({
      title: "Simpan sebagai baris Global?",
      message: `Baris ini akan berlaku untuk SEMUA badan usaha, bukan hanya ${entityLabel}.`,
      confirmLabel: "Simpan sebagai Global", danger: true,
    }))) return;
    setBusyId("form"); setFormErr("");
    try {
      if (form.mode === "edit") {
        const body = Object.fromEntries(Object.entries(form.values)
          .filter(([k]) => !["id", "entity_id", "entity_scope", "source_label", "owner_label", "is_overridden",
            "is_active", "can_edit_here", "created_at", "created_by", "updated_at"].includes(k)));
        await axios.patch(`${API}/entity-masters/${kind}/${form.id}`, { data: body });
        flash("Perubahan tersimpan.");
      } else {
        const body = { ...form.values };
        if (form.global || groupMode) body.entity_id = "all";
        await axios.post(`${API}/entity-masters/${kind}`, body);
        flash(form.global || groupMode ? "Baris baru dibuat sebagai Global — berlaku untuk semua badan usaha."
          : `Baris baru dibuat khusus ${entityLabel}.`);
      }
      setForm(null);
      await changed();
    } catch (e) { setFormErr(errText(e, "Gagal menyimpan baris master.")); } finally { setBusyId(""); }
  }

  const tableCols = [
    ...columns.map((c, i) => ({
      key: c.key, header: c.label, align: c.align, mobile: i === 0 ? "title" : undefined, priority: i,
      className: c.mono ? "font-mono text-[11px] text-[#6B6B73]" : "",
      render: (r) => <span className="line-clamp-2">{cellText(c, r, formatCurrency)}</span>,
    })),
    { key: "_source", header: "Asal", align: "center", mobile: "badge", render: (r) => (
      <span>
        <span data-testid={`em-source-${r.id}`} className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[9px] font-bold ${
          r.entity_scope === "global" ? "bg-[#F5F5F7] text-[#6B6B73]" : "bg-[#EFF4FF] text-[#0058CC]"}`}>{r.source_label}</span>
        {r.is_overridden && (
          <span data-testid={`em-overridden-${r.id}`} className="mt-0.5 block text-[9px] font-semibold text-[#8C4A00]">
            ditimpa {entityLabel}
          </span>
        )}
      </span>
    ) },
  ];
  const actions = (r) => {
    const isGlobal = r.entity_scope === "global";
    return (
      <span className="inline-flex flex-wrap justify-end gap-1">
        {rowActions ? rowActions(r) : null}
        {manage && canOp("override") && isGlobal && !groupMode && !r.is_overridden && (
          <button data-testid={`em-override-${r.id}`} className="secondary-button text-[11px]" disabled={busyId === r.id}
            title={`Salin baris ini menjadi milik ${entityLabel}`} onClick={() => doOverride(r)}>
            <Copy size={12} /> Buat khusus {entityLabel}
          </button>
        )}
        {manage && canOp("revert") && !isGlobal && (
          <button data-testid={`em-revert-${r.id}`} className="secondary-button text-[11px]" disabled={busyId === r.id}
            title="Lepas override — kembali mengikuti nilai Global" onClick={() => doRevert(r)}>
            <RotateCcw size={12} /> Kembalikan ke global
          </button>
        )}
        {manage && canOp("update") && r.can_edit_here && (
          <button data-testid={`em-edit-${r.id}`} className="primary-button text-[11px]" onClick={() => openEdit(r)}>
            <Pencil size={12} /> Ubah
          </button>
        )}
      </span>
    );
  };

  const hint = hintOverride || cleanHint(data?.hint);
  return (
    <div className="grid gap-3" data-testid={testId}>
      {showRibbon && <EntityScopeRibbon groupMode={groupMode} entityLabel={entityLabel} />}
      {notice && (
        <div data-testid="em-notice"
          className="flex items-center gap-2 rounded-md border border-[#BDE5CC] bg-[#E6F6EC] px-3 py-2 text-[12px] text-[#1B7F4B]">
          <CheckCircle2 size={14} /><span>{notice}</span>
          <button className="ml-auto" onClick={() => setNotice("")} aria-label="Tutup"><X size={13} /></button>
        </div>
      )}
      <ErrorNotice message={error} onRetry={loadRows} onDismiss={() => setError("")} testId="em-error" />
      <section className="section-card">
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            <Layers3 size={15} className="text-[#0058CC]" />
            <span className="kicker">{entityLabel}</span>
            <h2 data-testid="em-rows-title">{data?.label || "Master"}</h2>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search size={13} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-[#8E8E93]" />
              <input data-testid="em-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari baris…"
                className="h-8 w-[180px] rounded-md border border-[#E5E5EA] bg-white pl-7 pr-2 text-[12px] focus:border-[#0058CC] focus:outline-none" />
            </div>
            {headerExtra}
            {manage && canOp("create") && (
              <button data-testid="em-toggle-create" className="secondary-button text-[11.5px]" onClick={openCreate}>
                <Plus size={13} /> Baris baru
              </button>
            )}
            <button data-testid="em-refresh-rows" className="icon-button" onClick={loadRows} aria-label="Muat ulang">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
        <div className="section-body grid gap-3">
          {hint && (
            <div className="flex items-start gap-2 rounded-md border border-[#D6E6FF] bg-[#F0F6FF] px-3 py-2 text-[11.5px] text-[#004099]">
              <Info size={14} className="mt-0.5 shrink-0" /><span data-testid="em-hint">{hint}</span>
            </div>
          )}
          {topNotice}
          {data?.summary && !loading && (
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <span data-testid="em-summary-global" className="rounded bg-[#F5F5F7] px-2 py-1 font-semibold text-[#6B6B73]">
                {data.summary.global} baris Global
              </span>
              <span data-testid="em-summary-entity" className="rounded bg-[#EFF4FF] px-2 py-1 font-semibold text-[#0058CC]">
                {data.summary.entity} khusus badan usaha
              </span>
              {data.summary.overridden > 0 && (
                <span data-testid="em-summary-overridden" className="rounded bg-[#FFF7E6] px-2 py-1 font-semibold text-[#8C4A00]">
                  {data.summary.overridden} baris Global sedang ditimpa
                </span>
              )}
            </div>
          )}
          <ResponsiveTable testId="em" rows={rows} rowKey="id" columns={tableCols} actions={actions} stickyActions
            loading={loading} rowClassName={(r) => (r.is_overridden ? "opacity-55" : "")}
            empty={<span data-testid="em-empty">{search ? `Tidak ada baris yang cocok dengan "${search}".`
              : `Belum ada baris ${data?.label || "master"} untuk ${entityLabel}.`}</span>} />
        </div>
      </section>

      <FormModal open={!!form} onClose={() => setForm(null)} testId="em-create-form" icon={form?.mode === "edit" ? Pencil : Plus}
        size={renderForm ? "lg" : "md"}
        title={`${form?.mode === "edit" ? "Ubah" : "Baris Baru"} · ${data?.label || "Master"}`}
        subtitle={form?.mode === "edit"
          ? (form?.values?.entity_scope === "global" ? "Baris Global — berlaku untuk semua badan usaha." : `Khusus ${form?.values?.owner_label || entityLabel}.`)
          : (groupMode || form?.global ? "Berlaku Global — untuk semua badan usaha." : `Khusus ${entityLabel}.`)}
        onSubmit={saveForm} submitLabel={busyId === "form" ? "Menyimpan…" : "Simpan baris"} busy={busyId === "form"}
        submitDisabled={missing.length > 0} error={formErr} submitTestId="em-form-save" cancelTestId="em-form-cancel">
        {form && (renderForm
          ? renderForm({ mode: form.mode, values: form.values, setValues })
          : <MasterFields kind={kind} values={form.values} setValues={setValues} fieldOptions={fieldOptions} />)}
        {form?.mode === "create" && !groupMode && (
          <label data-testid="em-form-global-toggle" className="mt-3 flex cursor-pointer items-center gap-2 text-[11.5px] text-[#3A3A3C]">
            <input type="checkbox" checked={!!form.global} onChange={(e) => setForm((f) => ({ ...f, global: e.target.checked }))} />
            <span>Jadikan <b>Global</b> — berlaku untuk semua badan usaha, bukan hanya {entityLabel}.
              {form.global && <b className="ml-1 text-[#8C4A00]">Perubahan ini memengaruhi seluruh grup.</b>}</span>
          </label>
        )}
      </FormModal>
    </div>
  );
}
