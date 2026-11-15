/**
 * PREP-B — layar desktop "Pendaftaran awal gedung" (tab Stock Opname · metode Pendaftaran awal).
 *
 * Kenapa ada: klien tidak yakin isi & jumlah stoknya (KEPUTUSAN_GATE_RFID §8) — stok lama tidak ditautkan ke data
 * lama, tetapi DIDAFTARKAN ULANG dari fisik per gedung (roll + tag lahir bersamaan). Layar ini: daftar sesi, buat sesi
 * (gedung, cakupan zona/rak, mode pembekuan K-OPN-03, mode EPC K-OPN-05), lalu rincian sesi di sebelahnya (progres per
 * rak, rekonsiliasi per produk, persetujuan massal). Isian lapangan dilakukan di HP (Pindai › Daftar Awal).
 */
import { useEffect, useState } from "react";
import { Plus, RefreshCw, ScanLine } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import FormModal from "../../../components/FormModal";
import ErrorNotice from "../../../components/ErrorNotice";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { EPC_OPTIONS, FREEZE_OPTIONS, STATUS_LABEL, regApi, scopeOptions } from "./registrationApi";
import StatusBadge from "../../../components/StatusBadge";   // FIX-8 — lencana baku
import EmptyState from "../../../components/EmptyState";   // FIX-8 — memuat ≠ kosong
import { formatDate } from "../../../utils/formatters";   // FIX-8 (G-OUT-01) — tanggal WIB
import RegistrationDetail from "./RegistrationDetail";
import ExportMenu from "../../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)
import ListLimitNote from "../../wms/ListLimitNote";   // FIX-7 (B3b LST-01)

const EMPTY = { warehouse_id: "", name: "", notes: "", freeze_mode: "zone", epc_mode: "read", node_ids: [] };

export default function InitialRegistration({ warehouses = [] }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [zones, setZones] = useState([]);
  const [formErr, setFormErr] = useState("");
  const [busy, setBusy] = useState(false);

  const [listMeta, setListMeta] = useState(null);   // FIX-7 — jumlah sungguhan (header server)
  const [moreBusy, setMoreBusy] = useState(false);
  const metaOf = (r, shown) => (Number.isFinite(r.total) ? { total: r.total, truncated: shown < r.total, shown, skip: 0 } : null);
  const load = async () => {
    setLoading(true);
    try { const r = await regApi.listPage(); setRows(r.rows); setListMeta(metaOf(r, r.rows.length)); setErr(""); }
    catch (e) { setErr(apiErrorText(e, "Gagal memuat sesi pendaftaran")); }
    setLoading(false);
  };
  const loadMore = async () => {   // FIX-7 (B3b LST-01) — dulu 200 sesi terbaru tanpa tanda
    setMoreBusy(true);
    try {
      const r = await regApi.listPage({ skip: rows.length });
      const seen = new Set(rows.map((x) => x.id));
      const next = [...rows, ...r.rows.filter((x) => !seen.has(x.id))];
      setRows(next); setListMeta(metaOf(r, next.length));
    } catch (e) { setErr(apiErrorText(e, "Gagal memuat sesi berikutnya")); }
    setMoreBusy(false);
  };
  useEffect(() => { load(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!form.warehouse_id) { setZones([]); return; }
    axios.get(`${API}/warehouses/${form.warehouse_id}/locations`)
      .then((r) => setZones(r.data?.zones || []))
      .catch((e) => setFormErr(apiErrorText(e, "Gagal memuat struktur gudang")));
  }, [form.warehouse_id]);

  const toggleNode = (id) => setForm((f) => ({ ...f, node_ids: f.node_ids.includes(id) ? f.node_ids.filter((x) => x !== id) : [...f.node_ids, id] }));

  const create = async () => {
    setBusy(true); setFormErr("");
    try {
      const s = await regApi.create(form);
      setCreating(false); setForm(EMPTY);
      await load();
      setSelectedId(s.id);
    } catch (e) { setFormErr(apiErrorText(e, "Gagal membuat sesi pendaftaran")); }
    setBusy(false);
  };

  const zoneMode = form.freeze_mode === "zone";
  const options = scopeOptions(zones);
  return (
    <section className="section-card" data-testid="reg-panel">
      <div className="section-head max-sm:!flex-col max-sm:!items-start max-sm:gap-2">
        <div className="min-w-0">
          <span className="kicker">Stock Opname · Pendaftaran awal gedung</span>
          <h2>Daftar ulang stok dari fisik (roll + tag lahir bersamaan)</h2>
        </div>
        <div className="flex items-center gap-2">
          <ExportMenu dataset="cycle_count_sessions" label="pendaftaran-awal" scope="work" testId="reg-export"
            filters={[["mode", "eq", "registration"]]} sort={[{ key: "created_at", dir: "desc" }]} />
          <button className="primary-button" data-testid="reg-new" onClick={() => { setCreating(true); setFormErr(""); }}><Plus size={13} /> Sesi baru</button>
          <button className="secondary-button" data-testid="reg-refresh" onClick={load} aria-label="Muat ulang"><RefreshCw size={13} className={loading ? "animate-spin" : ""} /></button>
        </div>
      </div>
      {err && <div className="mx-4 mb-2"><ErrorNotice message={err} onRetry={load} onDismiss={() => setErr("")} testId="reg-error" /></div>}
      <div className="section-body">
        <p className="mb-3 text-[11.5px] text-[#6B6B73]">
          Data lama hanya pembanding. Tim gudang menempel tag & mengisi baris di HP (<b>Pindai › Daftar Awal</b>);
          di sini progres per rak, perbandingan per produk dan persetujuan massal oleh pemegang wewenang ACC opname.
        </p>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[300px_1fr]">
          <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-3" data-testid="reg-list">
            <div className="mb-2 flex items-center justify-between"><h3 className="text-[13px] font-bold">Sesi</h3><span className="text-[11px] text-[#6B6B73]">{rows.length} sesi</span></div>
            {rows.length === 0 && <EmptyState kind={loading ? "loading" : "empty"} what="sesi pendaftaran awal" compact testId="reg-empty" />}
            <div className="grid max-h-[28rem] gap-1.5 overflow-auto">
              {rows.map((s) => (
                <button key={s.id} type="button" data-testid={`reg-session-${s.id}`} onClick={() => setSelectedId(s.id)}
                  className={`rounded-lg border bg-white p-2.5 text-left ${selectedId === s.id ? "border-[#007AFF]" : "border-[#EFF0F2] hover:border-[#C7C7CC]"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[12px] font-bold">{s.number || s.name}</span>
                    <StatusBadge status={s.status} domain="registration" label={STATUS_LABEL[s.status] || s.status_label} />
                  </div>
                  <p className="mt-0.5 text-[11px] text-[#6B6B73]">{s.warehouse_name} · {(s.registration?.node_labels || []).join(", ")}</p>
                  <p className="text-[10.5px] text-[#8E8E93]">{s.freeze?.active ? "Beku aktif" : "Tidak membekukan"} · {formatDate(s.created_at)}</p>
                </button>
              ))}
            </div>
            <ListLimitNote meta={listMeta} noun="sesi" onMore={loadMore} loading={moreBusy} testId="reg-limit" />
          </div>
          {selectedId ? <RegistrationDetail key={selectedId} sessionId={selectedId} onChanged={load} /> : (
            <div className="rounded-md border border-dashed border-[#C7C7CC] p-8 text-center text-[12.5px] text-[#6B6B73]" data-testid="reg-pick-hint">
              <ScanLine size={28} className="mx-auto mb-2 text-[#C7C7CC]" />Pilih sesi di kiri, atau buat sesi baru per gedung.
            </div>
          )}
        </div>
      </div>

      <FormModal open={creating} onClose={() => setCreating(false)} title="Sesi pendaftaran awal gedung" icon={ScanLine}
        subtitle="Gedung, cakupan, cara pembekuan & sumber EPC. Pembekuan aktif saat sesi DIMULAI."
        testId="reg-create-modal" onSubmit={create} submitLabel="Buat sesi" submitTestId="reg-create-submit" busy={busy}
        error={formErr} submitDisabled={!form.warehouse_id || (zoneMode && !form.node_ids.length)}>
        <div className="grid gap-2">
          <KNSelect data-testid="reg-create-wh" className="field" value={form.warehouse_id} placeholder="Pilih gedung/gudang"
            onValueChange={(v) => setForm({ ...form, warehouse_id: v, node_ids: [] })}
            options={warehouses.map((w) => ({ value: w.id, label: [w.name, w.city].filter(Boolean).join(" — ") }))} />
          <KNSelect data-testid="reg-create-freeze" className="field" value={form.freeze_mode}
            onValueChange={(v) => setForm({ ...form, freeze_mode: v })} options={FREEZE_OPTIONS} />
          <KNSelect data-testid="reg-create-epc" className="field" value={form.epc_mode}
            onValueChange={(v) => setForm({ ...form, epc_mode: v })} options={EPC_OPTIONS} />
          {form.warehouse_id && (
            <fieldset className="rounded-md border border-[#EFF0F2] p-2" data-testid="reg-create-scope">
              <legend className="px-1 text-[11px] font-semibold text-[#6B6B73]">
                Cakupan {zoneMode ? "(wajib — zona/rak yang dibekukan)" : "(kosong = seluruh gedung)"}
              </legend>
              {options.length === 0 && <p className="text-[11.5px] text-[#8E8E93]">Gudang belum punya struktur zona/rak.</p>}
              <div className="grid max-h-56 gap-1 overflow-auto sm:grid-cols-2">
                {options.map((o) => (
                  <label key={o.id} className={`flex items-center gap-2 text-[12px] ${o.kind === "rak" ? "pl-4" : "font-semibold"}`}>
                    <input type="checkbox" checked={form.node_ids.includes(o.id)} onChange={() => toggleNode(o.id)} data-testid={`reg-scope-${o.id}`} />
                    {o.label}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <input className="field" placeholder="Nama sesi (opsional)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="reg-create-name" />
          <textarea className="field" rows={2} placeholder="Catatan (opsional)" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
      </FormModal>
    </section>
  );
}
