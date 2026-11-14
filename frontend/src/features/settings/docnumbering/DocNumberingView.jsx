/**
 * DocNumberingView — KP-T5: Pengaturan › Dokumen & Cetak › **Penomoran Dokumen** (`docs/blueprint/unit/KP-T5.md`).
 *
 * Satu tabel untuk semua jenis nomor dokumen, per lapisan (Semua PT = aturan grup / satu PT): contoh nomor berikutnya
 * (dihitung server dari penghitung nyata), awalan, lebar angka, sisipan tanggal, kapan angka mulai lagi dari 1, deret
 * per PT atau bersama, dan sumber nilainya. Nilai bawaan = bentuk nomor yang terbit sebelum layar ini ada.
 *
 * Baca `GET /api/doc-numbering?entity_id=` (izin `settings.view`). Ubah lewat pop-up: pratinjau tiga nomor
 * `POST /api/doc-numbering/preview` saat mengetik, simpan `PUT /api/doc-numbering/{kind}` (alasan wajib), kembalikan
 * `DELETE /api/doc-numbering/{kind}` — tombol hanya untuk pemegang `settings.manage` (`can(...)`).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Hash, Pencil, RotateCcw } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { askReason } from "../../../services/confirmService";
import { can } from "../../../config/roles";
import ErrorNotice from "../../../components/ErrorNotice";
import FormModal from "../../../components/FormModal";
import KNSelect from "../../../components/KNSelect";
import OkNotice from "../../../components/OkNotice";
import { apiErrorText } from "../../../utils/apiError";
import { SearchBox } from "../../../components/ListControls";
import { entityOptions, entityShortById } from "../../../utils/entityLabel";

export const SEMUA_PT = "all";
export const TOKEN_OPTIONS = [
  { value: "", label: "Tanpa sisipan" },
  { value: "YY", label: "Tahun 2 angka (26)" },
  { value: "YYYY", label: "Tahun 4 angka (2026)" },
  { value: "YYMM", label: "Tahun dan bulan (2611)" },
  { value: "YYYYMM", label: "Tahun dan bulan (202611)" },
  { value: "YYMMDD", label: "Tanggal (261114)" },
];
export const RESET_OPTIONS = [
  { value: "tidak", label: "Tidak pernah" },
  { value: "tahunan", label: "Tiap tahun" },
  { value: "bulanan", label: "Tiap bulan" },
  { value: "harian", label: "Tiap hari" },
];
export const SCOPE_OPTIONS = [
  { value: "per_pt", label: "Per PT" },
  { value: "bersama", label: "Bersama semua PT" },
];
const label = (opts, v) => (opts.find((o) => o.value === (v || "")) || {}).label || "—";
export const tokenLabel = (v) => label(TOKEN_OPTIONS, v);
export const resetLabel = (v) => label(RESET_OPTIONS, v);
export const scopeLabel = (v) => label(SCOPE_OPTIONS, v);
export const HEAD_NOTE = "Perubahan hanya berlaku untuk dokumen baru. Nomor yang sudah terbit tidak berubah.";

/** Isi `PUT`/`preview` dari draf pop-up (lebar sebagai angka; Deret hanya pada baris grup). */
export function bodyFromDraft(draft, layerAll) {
  const out = { prefix: (draft.prefix || "").trim().toUpperCase(), width: Number(draft.width),
    date_token: draft.date_token || "", reset: draft.reset || "tidak" };
  if (layerAll && draft.scope) out.scope = draft.scope;
  return out;
}

function Skeleton() {
  return (
    <div className="mt-3 grid gap-2" data-testid="docnum-loading" aria-busy="true" aria-label="Memuat penomoran dokumen">
      {[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-7 rounded bg-kn-neutral-soft animate-pulse" />)}
    </div>
  );
}

function EditModal({ row, layer, layerAll, namaLapisan, onClose, onSaved }) {
  const [draft, setDraft] = useState(() => ({ ...row.format, width: String(row.format.width) }));
  const [pv, setPv] = useState({ samples: row.samples || [], warnings: [] });
  const [pvError, setPvError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const timer = useRef(null);

  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const r = await axios.post(`${API}/doc-numbering/preview`,
          { kind: row.kind, entity_id: layer, ...bodyFromDraft(draft, layerAll) });
        setPv(r.data);
        setPvError("");
      } catch (e) {
        setPvError(apiErrorText(e, "Pratinjau gagal dimuat."));
      }
    }, 300);
    return () => clearTimeout(timer.current);
  }, [draft, row.kind, layer, layerAll]);

  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const simpan = async () => {
    const reason = await askReason({
      title: `Ubah format nomor ${row.label}`,
      message: `Format baru untuk ${namaLapisan}. ${HEAD_NOTE} Tulis alasan perubahan (tercatat di riwayat).`,
      confirmLabel: "Simpan format", testId: "docnum-save-confirm",
    });
    if (!reason) return;
    setBusy(true);
    setError("");
    try {
      const r = await axios.put(`${API}/doc-numbering/${row.kind}`,
        { entity_id: layer, ...bodyFromDraft(draft, layerAll), reason, expected_version: row.version });
      onSaved(r.data);
    } catch (e) {
      setError(apiErrorText(e, "Format nomor gagal disimpan."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <FormModal open onClose={onClose} title={`Ubah format nomor · ${row.label}`} subtitle={`Berlaku untuk ${namaLapisan}`}
      icon={Hash} testId="docnum-edit" onSubmit={simpan} submitLabel="Simpan" busy={busy} error={error}
      submitTestId="docnum-edit-save">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1">
          <span className="kicker">Awalan</span>
          <input className="field font-mono" value={draft.prefix} maxLength={12} data-testid="docnum-edit-prefix"
            onChange={(e) => set({ prefix: e.target.value.toUpperCase() })} />
        </label>
        <label className="grid gap-1">
          <span className="kicker">Lebar angka</span>
          <input className="field" type="number" min="3" max="8" value={draft.width} data-testid="docnum-edit-width"
            onChange={(e) => set({ width: e.target.value })} />
        </label>
        <div className="grid gap-1">
          <span className="kicker">Sisipan tanggal</span>
          <KNSelect value={draft.date_token || ""} options={TOKEN_OPTIONS} onValueChange={(v) => set({ date_token: v || "" })}
            className="field" data-testid="docnum-edit-token" />
        </div>
        <div className="grid gap-1">
          <span className="kicker">Mulai lagi dari 1</span>
          <KNSelect value={draft.reset || "tidak"} options={RESET_OPTIONS} onValueChange={(v) => set({ reset: v || "tidak" })}
            className="field" data-testid="docnum-edit-reset" />
        </div>
        <div className="grid gap-1 sm:col-span-2">
          <span className="kicker">Deret</span>
          <KNSelect value={draft.scope} options={SCOPE_OPTIONS} disabled={!layerAll} onValueChange={(v) => set({ scope: v })}
            className="field" data-testid="docnum-edit-scope" />
          {!layerAll ? (
            <span className="text-fs-12 text-kn-text-2" data-testid="docnum-edit-scope-note">
              Pilihan per PT atau bersama diatur untuk seluruh grup (pilih "Semua PT").
            </span>
          ) : null}
        </div>
      </div>
      <div className="mt-3 rounded-md border border-kn-divider bg-kn-neutral-soft p-2.5" data-testid="docnum-edit-preview">
        <p className="kicker mb-1">Tiga nomor berikutnya</p>
        {pvError ? <p className="text-fs-12 text-kn-danger-text" data-testid="docnum-edit-preview-error">{pvError}</p> : (
          <p className="font-mono text-fs-13 text-kn-text">{(pv.samples || []).join(" · ") || "—"}</p>
        )}
        {(pv.warnings || []).map((w) => (
          <p key={w} className="mt-1 text-fs-12 text-kn-warning-text" data-testid="docnum-edit-warning">{w}</p>
        ))}
      </div>
    </FormModal>
  );
}

export default function DocNumberingView({ selectedEntity, entities = [], currentUser }) {
  const awal = selectedEntity && selectedEntity !== SEMUA_PT ? selectedEntity : SEMUA_PT;
  const [layer, setLayer] = useState(awal);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [edit, setEdit] = useState(null);
  const [cari, setCari] = useState("");
  const [ok, setOk] = useState("");
  const [warnings, setWarnings] = useState([]);

  const layerAll = layer === SEMUA_PT;
  const canEdit = can(currentUser?.permissions, "settings", "manage");
  const namaLapisan = layerAll ? "Semua PT (aturan grup)" : entityShortById(entities, layer, "PT terpilih");
  const opsiLapisan = useMemo(() => [{ value: SEMUA_PT, label: "Semua PT" },
    ...entityOptions(entities).filter((o) => o.value && o.value !== SEMUA_PT)], [entities]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await axios.get(`${API}/doc-numbering`, { params: { entity_id: layer } });
      setData(r.data);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [layer]);

  useEffect(() => { load(); }, [load]);

  const kembalikan = async (row) => {
    const reason = await askReason({
      title: `Kembalikan format ${row.label}`,
      message: `${layerAll ? "Format grup dihapus; jenis ini kembali ke bawaan." : "Format khusus PT ini dihapus; PT mengikuti aturan grup."} ${HEAD_NOTE}`,
      confirmLabel: "Kembalikan", testId: "docnum-reset-confirm",
    });
    if (!reason) return;
    try {
      await axios.delete(`${API}/doc-numbering/${row.kind}`, { params: { entity_id: layer, reason } });
      setOk(`Format ${row.label} dikembalikan.`);
      setWarnings([]);
      await load();
    } catch (e) {
      setError(e);
    }
  };

  const rows = data?.rows || [];
  const kunciCari = cari.trim().toLowerCase();
  const cocok = (r) => !kunciCari || `${r.label} ${r.format?.prefix || ""}`.toLowerCase().includes(kunciCari);
  const groups = data?.groups || [];
  return (
    <div className="cfg-hub" data-testid="docnum-view">
      <div className="cfg-toolbar">
        <div className="cfg-scope-box" data-testid="docnum-scope-box">
          <span className="cfg-scope-caption">Berlaku untuk</span>
          <KNSelect value={layer} onValueChange={(v) => { setOk(""); setWarnings([]); setLayer(v || SEMUA_PT); }}
            options={opsiLapisan} className="field cfg-select-sm" data-testid="docnum-scope" />
        </div>
        <p className="text-fs-12 text-kn-text-2" data-testid="docnum-head-note">{HEAD_NOTE}</p>
      </div>
      <p className="cfg-group-intro" data-testid="docnum-banner">
        <Hash size={13} className="mr-1 inline align-[-2px] text-kn-action" aria-hidden="true" />
        Menampilkan format untuk <b>{namaLapisan}</b>.
        {layerAll ? " Baris di sini berlaku bagi PT yang tidak punya format khusus." : " Kolom Sumber menunjukkan asal nilainya."}
      </p>
      {error ? <ErrorNotice message={error} onRetry={load} testId="docnum-error" /> : null}
      {ok ? <OkNotice message={ok} testId="docnum-ok" /> : null}
      {warnings.map((w) => <p key={w} className="text-fs-12 text-kn-warning-text" data-testid="docnum-warning">{w}</p>)}
      {loading && !data ? <Skeleton /> : null}
      {data ? (
        <div className="mt-3 max-w-sm">
          <SearchBox value={cari} onChange={setCari} placeholder="Cari jenis dokumen atau awalan" testId="docnum-search" />
        </div>
      ) : null}
      {data && cari && !rows.some(cocok) ? (
        <p className="mt-3 text-fs-13 text-kn-text-2" data-testid="docnum-search-empty">Tidak ada jenis dokumen yang cocok dengan “{cari}”.</p>
      ) : null}
      {data ? groups.map((g) => {
        const baris = rows.filter((r) => r.group === g && cocok(r));
        if (!baris.length) return null;
        return (
          <section key={g} className="section-card section-pad mt-3" data-testid={`docnum-group-${g}`}>
            <h3 className="mb-2 text-fs-14 font-semibold">{g} <span className="text-fs-12 font-normal text-kn-text-2">· {baris.length} jenis</span></h3>
            <div className="overflow-x-auto">
              <table className="data-table head-wrap">
                <thead>
                  <tr>
                    <th>Jenis dokumen</th><th>Contoh nomor berikutnya</th><th>Awalan</th><th>Lebar angka</th>
                    <th>Sisipan tanggal</th><th>Mulai lagi dari 1</th><th>Deret</th><th>Sumber</th>
                    <th className="col-sticky-end" aria-label="Aksi" />
                  </tr>
                </thead>
                <tbody>
                  {baris.map((r) => (
                    <tr key={r.kind} data-testid={`docnum-row-${r.kind}`} className={r.locked ? "text-kn-text-2" : ""}>
                      <td>
                        {r.label}
                        {r.locked ? <span className="block text-fs-12 text-kn-text-2" data-testid={`docnum-locked-${r.kind}`}>{r.locked_note}</span> : null}
                      </td>
                      <td className="font-mono" data-testid={`docnum-next-${r.kind}`}>{r.next_preview}</td>
                      <td className="font-mono">{r.format.prefix}</td>
                      <td>{r.format.width}</td>
                      <td>{tokenLabel(r.format.date_token)}</td>
                      <td>{resetLabel(r.format.reset)}</td>
                      <td className="whitespace-nowrap">{scopeLabel(r.format.scope)}</td>
                      <td className="whitespace-nowrap" data-testid={`docnum-source-${r.kind}`}>{r.source_label}</td>
                      <td className="col-sticky-end whitespace-nowrap">
                        {canEdit && !r.locked ? (
                          <>
                            <button type="button" className="btn-secondary btn-sm" data-testid={`docnum-edit-${r.kind}`}
                              onClick={() => { setOk(""); setEdit(r); }}>
                              <Pencil size={12} /> Ubah
                            </button>
                            {(layerAll ? r.source === "grup" : r.source === "pt") ? (
                              <button type="button" className="btn-secondary btn-sm ml-1" data-testid={`docnum-reset-${r.kind}`}
                                onClick={() => kembalikan(r)}>
                                <RotateCcw size={12} /> Kembalikan ke bawaan
                              </button>
                            ) : null}
                          </>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      }) : null}
      {edit ? (
        <EditModal row={edit} layer={layer} layerAll={layerAll} namaLapisan={namaLapisan} onClose={() => setEdit(null)}
          onSaved={async (saved) => {
            setEdit(null);
            setOk(`Format ${saved.label} tersimpan.`);
            setWarnings(saved.warnings || []);
            await load();
          }} />
      ) : null}
    </div>
  );
}
