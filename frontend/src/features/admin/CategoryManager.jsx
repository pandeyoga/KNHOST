/**
 * CategoryManager — EPIC2 Master Kategori Produk (admin).
 * CRUD kategori produk: list (dengan product_count) + form create/edit + soft-delete.
 * Self-contained: fetch & mutasi via axios + API (path literal). Memanggil `onChanged`
 * setelah mutasi agar form produk (AdminView) refresh opsi dropdown.
 *
 * Fase 3 · P2 (L-03) — form yang dulu panel tetap 360 px di kiri (selalu terbuka, mendesak daftar) → pop-up baku
 * `FormModal` lewat tombol "Kategori baru" / "Ubah" (di HP layar penuh; isian sama).
 */
import { useCallback, useEffect, useState } from "react";
import { Power, Pencil, Plus, RefreshCw, Tag } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import FormModal from "../../components/FormModal";
import ErrorNotice from "../../components/ErrorNotice";
import useListSearch from "@/hooks/useListSearch";
import useUomConversions from "../../hooks/useUomConversions";
import { uomSelectOptions } from "../../utils/uomCatalog";
import { askConfirm } from "@/services/confirmService";

const EMPTY = { code: "", name: "", base_unit: "meter", description: "", sort_order: 0, status: "active" };

export default function CategoryManager({ onChanged }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  // FASE U — satuan dasar kategori dari MASTER satuan (`uoms`). Dulu 5 nilai diketik
  // di berkas ini: kategori produk yang dijual per `panel` tidak bisa dibuat sama
  // sekali walau pemilik sudah menambah PANEL di Master Data → UOM.
  useUomConversions();
  const baseUnitOptions = uomSelectOptions({
    dimensions: ["length", "weight", "count"],
    extra: [form.base_unit].filter(Boolean),
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/product-categories`);
      setRows(Array.isArray(res.data) ? res.data : []);
      setError("");
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal memuat kategori. Coba lagi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const resetForm = () => { setForm(EMPTY); setEditingId(null); setFormError(""); setFormOpen(false); };
  const openCreate = () => { setForm({ ...EMPTY }); setEditingId(null); setFormError(""); setFormOpen(true); };

  const startEdit = (row) => {
    setEditingId(row.id);
    setForm({
      code: row.code || "", name: row.name || "", base_unit: row.base_unit || "meter",
      description: row.description || "", sort_order: row.sort_order || 0, status: row.status || "active",
    });
    setFormError("");
    setFormOpen(true);
  };

  const save = async () => {
    if (!form.name.trim()) { setFormError("Nama kategori wajib diisi."); return; }
    setSaving(true);
    setFormError("");
    try {
      if (editingId) {
        await axios.patch(`${API}/product-categories/${editingId}`, { data: form });
      } else {
        await axios.post(`${API}/product-categories`, form);
      }
      resetForm();
      await load();
      if (onChanged) onChanged();
    } catch (e) {
      setFormError(e.response?.data?.detail || "Gagal menyimpan kategori.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (row) => {
    const ok = await askConfirm({
      title: `Nonaktifkan kategori "${row.name}"?`,
      message: "Kategori tidak lagi bisa dipilih untuk produk baru. Produk yang sudah memakainya tetap utuh.",
      confirmLabel: "Nonaktifkan",
      danger: true,
      testId: "category-deactivate-confirm",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/product-categories/${row.id}`);
      await load();
      if (onChanged) onChanged();
    } catch (e) {
      setError(e.response?.data?.detail || "Gagal menonaktifkan kategori.");
    }
  };

  const srch = useListSearch(rows, null, { testId: "category", placeholder: "Cari kode / nama kategori…" });
  const activeRows = srch.pageRows;

  return (
    <section className="grid items-start gap-3" data-testid="category-manager">
      <FormModal open={formOpen} onClose={resetForm} testId="category-form" icon={Tag} size="md"
        title={editingId ? "Ubah Kategori" : "Kategori Baru"} subtitle="Kategori produk + satuan dasar bawaan untuk produk barunya."
        onSubmit={save} busy={saving} error={formError}
        submitLabel={saving ? "Menyimpan…" : editingId ? "Simpan Perubahan" : "Simpan Kategori"}
        submitTestId="category-save-button" cancelTestId="category-cancel-edit-button">
        <div className="grid gap-2">
          <label className="field-label" htmlFor="category-name-field">Nama kategori *</label>
          <input id="category-name-field" data-testid="category-name-input" className="field" placeholder="mis. Batik"
            value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />

          <label className="field-label" htmlFor="category-code-field">Kode (opsional)</label>
          <input id="category-code-field" data-testid="category-code-input" className="field" placeholder="otomatis dari nama (BATIK)"
            value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />

          <label className="field-label">Satuan dasar bawaan</label>
          <KNSelect data-testid="category-base-unit-input" className="field" value={form.base_unit}
            onValueChange={(v) => setForm({ ...form, base_unit: v })} options={baseUnitOptions} />

          <label className="field-label" htmlFor="category-description-field">Deskripsi</label>
          <input id="category-description-field" data-testid="category-description-input" className="field" placeholder="Deskripsi singkat"
            value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />

          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <label className="field-label" htmlFor="category-sort-field">Urutan tampil</label>
              <input id="category-sort-field" data-testid="category-sort-order-input" className="field" type="number"
                value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })} />
            </div>
            <div>
              <label className="field-label">Status</label>
              <KNSelect data-testid="category-status-input" className="field" value={form.status}
                onValueChange={(v) => setForm({ ...form, status: v })}
                options={[{ value: "active", label: "Aktif" }, { value: "inactive", label: "Nonaktif" }]} />
            </div>
          </div>
        </div>
      </FormModal>

      {/* ─── List ─── */}
      <div className="section-card">
        <div className="section-head">
          <h2>Daftar Kategori {rows.length > 0 ? `(${rows.length})` : ""}</h2>
          <div className="ml-auto flex items-center gap-2">
            <button data-testid="category-create-button" className="primary-button" onClick={openCreate}>
              <Plus size={14} /> Kategori Baru
            </button>
            <button data-testid="category-refresh-button" className="icon-button" onClick={load} aria-label="Muat ulang" title="Muat ulang">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>
        <div className="section-body">
          <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="category-list-error" />
          {srch.toolbar}

          {loading ? (
            <div className="grid gap-2" data-testid="category-loading">
              {[0, 1, 2, 3].map((i) => <div key={i} className="h-10 bg-[#F5F5F7] rounded animate-pulse" />)}
            </div>
          ) : activeRows.length === 0 ? (
            <div data-testid="category-empty" className="flex flex-col items-center justify-center gap-2 py-10 text-center">
              <Tag size={28} className="text-[#C7C7CC]" />
              <p className="text-[13px] text-[#8E8E93]">Belum ada kategori. Tambahkan kategori pertama Anda.</p>
              <button className="secondary-button" data-testid="category-empty-add-button" onClick={openCreate}>
                <Plus size={14} /> Buat Kategori
              </button>
            </div>
          ) : (
            <>
              {/* HP: kartu ringkas — status & tombol ubah/nonaktifkan selalu terlihat tanpa gulir samping. */}
              <div className="grid gap-2 md:hidden" data-testid="category-cards">
                {activeRows.map((row) => (
                  <div key={row.id} data-testid={`category-card-${row.id}`} className="flex items-center gap-2 rounded-md border border-[#EFF0F2] bg-white p-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-1.5 text-[13px] font-semibold text-[#1C1C1E]">
                        <span className="truncate">{row.name}</span>
                        <span className={`status-pill shrink-0 ${row.status === "active" ? "pill-success" : "pill-muted"}`}>
                          {row.status === "active" ? "Aktif" : "Nonaktif"}
                        </span>
                      </p>
                      <p className="truncate text-[11px] text-[#6B6B73]">
                        <span className="font-mono">{row.code}</span> · satuan {row.base_unit || "—"} · {row.product_count ?? 0} produk
                      </p>
                    </div>
                    <button className="icon-button shrink-0" onClick={() => startEdit(row)} aria-label={`Ubah ${row.name}`}>
                      <Pencil size={13} />
                    </button>
                    <button className="icon-button shrink-0" onClick={() => remove(row)} aria-label={`Nonaktifkan ${row.name}`} title="Nonaktifkan">
                      {/* G4-17 — ikon ⏻ (nonaktifkan) seperti master lain; tempat sampah = hapus. */}
                      <Power size={13} className="text-[#D14343]" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="hidden overflow-x-auto md:block">
                <table className="data-table" data-testid="category-table">
                  <thead>
                    <tr>
                      <th>Kode</th>
                      <th>Nama</th>
                      <th>Satuan Dasar</th>
                      <th className="text-right">Jumlah Produk</th>
                      <th className="text-center">Status</th>
                      <th className="text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeRows.map((row) => (
                      <tr key={row.id} data-testid={`category-row-${row.id}`}>
                        <td className="font-mono text-[11px] text-[#6B6B73]">{row.code}</td>
                        <td className="font-semibold text-[#1C1C1E]">{row.name}</td>
                        <td className="text-[#3C3C43]">{row.base_unit}</td>
                        <td className="text-right tabular-nums" data-testid={`category-count-${row.id}`}>{row.product_count ?? 0}</td>
                        <td className="text-center">
                          <span className={`status-pill ${row.status === "active" ? "pill-success" : "pill-muted"}`}>
                            {row.status === "active" ? "Aktif" : "Nonaktif"}
                          </span>
                        </td>
                        <td>
                          <div className="flex items-center justify-end gap-1">
                            <button data-testid={`category-edit-${row.id}`} className="icon-button" onClick={() => startEdit(row)} aria-label={`Ubah ${row.name}`} title="Ubah">
                              <Pencil size={13} />
                            </button>
                            <button data-testid={`category-delete-${row.id}`} className="icon-button" onClick={() => remove(row)} aria-label={`Nonaktifkan ${row.name}`} title="Nonaktifkan">
                              {/* G4-17 — ikon ⏻ (nonaktifkan) seperti master lain; tempat sampah = hapus. */}
                      <Power size={13} className="text-[#D14343]" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
