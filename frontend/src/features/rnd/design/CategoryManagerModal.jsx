/** CategoryManagerModal — master Kategori Pattern & Kategori Design (admin & manager bisa menambah pilihan sendiri).
 *
 * Fase 4 · R4 (L-03) — `FormModal` baku (dulu lapisan `fixed inset-0` buatan sendiri tanpa Esc berlapis): galat
 * tampil di kaki pop-up, layar penuh di HP. Pilihan jenis master = `PageTabs` (dulu pil ungu buatan sendiri);
 * aksen ungu → biru baku (L-08). Testid lama (`category-*`) dipertahankan. */
import { useEffect, useState } from "react";
import { Plus, Tags } from "lucide-react";
import FormModal from "../../../components/FormModal";
import PageTabs from "../../../components/PageTabs";
import { createCategory, patchCategory, studioCategories } from "../rndApi";
import { errMsg } from "../rndMeta";

const TYPES = [
  { key: "pattern", label: "Kategori Pattern", testId: "category-type-pattern" },
  { key: "design", label: "Kategori Design", testId: "category-type-design" },
];

export default function CategoryManagerModal({ designType = "pattern", onClose }) {
  const [type, setType] = useState(designType);
  const [rows, setRows] = useState([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => studioCategories({ design_type: type, status: "all" }).then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, [type]); // eslint-disable-line react-hooks/exhaustive-deps

  const add = async () => {
    setErr(""); setBusy(true);
    try {
      await createCategory({ design_type: type, code, name });
      setCode(""); setName(""); await load();
    } catch (e) { setErr(errMsg(e, "Kategori gagal ditambah.")); } finally { setBusy(false); }
  };
  const toggle = async (r) => {
    setErr("");
    try { await patchCategory(r.id, { status: r.status === "active" ? "inactive" : "active" }); await load(); }
    catch (e) { setErr(errMsg(e, "Gagal mengubah status.")); }
  };

  return (
    <FormModal open onClose={onClose} busy={busy} error={err} size="sm" icon={Tags} title="Master Kategori Desain"
      subtitle="Pilihan di sini muncul di form desainer. Tambah kode + nama untuk memperluas pilihan; nonaktifkan bila tidak dipakai lagi."
      testId="category-manager-modal"
      footer={(
        <div className="flex justify-end">
          <button type="button" className="secondary-button" onClick={onClose} disabled={busy} data-testid="category-manager-close">Tutup</button>
        </div>
      )}>
      <div className="space-y-3">
        <PageTabs testId="category-type-tabs" value={type} onChange={(k) => { setType(k); setErr(""); }} tabs={TYPES}
          ariaLabel="Jenis kategori" className="!mb-0" />
        <div className="flex flex-wrap gap-2">
          <input className="field !w-24 uppercase" placeholder="KODE" value={code} maxLength={6} data-testid="category-code-input"
            aria-label="Kode kategori" onChange={(e) => setCode(e.target.value.toUpperCase())} />
          <input className="field min-w-0 flex-1" placeholder="Nama kategori" value={name} data-testid="category-name-input"
            aria-label="Nama kategori" onChange={(e) => setName(e.target.value)} />
          <button type="button" className="primary-button" disabled={busy || code.length < 2 || !name.trim()} onClick={add} data-testid="category-add-button">
            <Plus size={13} /> Tambah
          </button>
        </div>
        <div className="divide-y divide-[#F0F0F2] rounded-lg border border-[#EFF0F2]">
          {rows.map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-2 px-3 py-1.5 text-[12px]" data-testid={`category-row-${r.code}`}>
              <span className="min-w-0"><b className="font-mono">{r.code}</b> <span className="ml-2">{r.name}</span></span>
              <button type="button" className={`shrink-0 text-[10.5px] ${r.status === "active" ? "text-[#1A7A3A]" : "text-[#9A9BA3]"}`}
                onClick={() => toggle(r)} data-testid={`category-toggle-${r.code}`}>
                {r.status === "active" ? "aktif · nonaktifkan" : "nonaktif · aktifkan"}
              </button>
            </div>
          ))}
          {rows.length === 0 && <p className="px-3 py-3 text-[11px] text-[#9A9BA3]">Belum ada kategori.</p>}
        </div>
      </div>
    </FormModal>
  );
}
