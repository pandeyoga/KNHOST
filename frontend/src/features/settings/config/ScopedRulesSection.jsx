/**
 * ScopedRulesSection — KF-T5: "Aturan khusus pelanggan ini" / "Aturan khusus barang ini" (`docs/blueprint/unit/KF-T5.md`).
 *
 * Satu komponen untuk dua tempat: detail pelanggan (`crm/Customer360Panel.jsx`) dan ubah barang
 * (`admin/products/ProductMasterForm.jsx`). Isinya kunci Pusat Pengaturan yang oleh mesin memang dibaca per pelanggan
 * (denda, masa tenggang, toleransi selisih bayar) atau per barang (sisa & susut potong):
 *   · data  — `configApi.effective({ scope, customer_id | product_id, entity_id })` → tiap butir membawa `layer_value`
 *             (nilai milik pelanggan/barang ini, atau null) dan `inherited_value` (aturan PT-nya);
 *   · simpan — `configApi.save` lapisan `customer`/`product` (alasan wajib bila kunci berisiko tinggi — aturan server);
 *   · kembali ikut aturan PT — `configApi.clear` lapisan itu, dengan konfirmasi.
 * Tanpa izin ubah kunci (`can_edit`) kartu hanya-baca. 403 atau tanpa kunci → bagian tidak tampil.
 *
 * `ScopedRulesSummary` — baris di kartu Pusat Pengaturan (`SettingCard.jsx`): "Bisa dibedakan per pelanggan — n
 * pelanggan diatur khusus" dari `configApi.layers`; klik membuka daftar nama dan nilainya.
 */
import { useCallback, useEffect, useState } from "react";
import { RotateCcw, Save, SlidersHorizontal, Users } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import LoadingLine from "../../../components/LoadingLine";
import OkNotice from "../../../components/OkNotice";
import { askConfirm } from "../../../services/confirmService";
import SettingEditor from "./SettingEditor";
import { cleanCfgText, configApi, formatValue } from "./configApi";

export const KATA = {
  customer: { nama: "pelanggan", judul: "Aturan khusus pelanggan ini", param: "customer_id" },
  product: { nama: "barang", judul: "Aturan khusus barang ini", param: "product_id" },
};

/** Lapisan aturan khusus yang didukung kunci ini (`customer` / `product`), atau "" bila tidak ada. */
export function lapisanKhusus(item) {
  const s = item?.scopes || [];
  if (s.includes("customer")) return "customer";
  if (s.includes("product")) return "product";
  return "";
}

const punyaNilai = (v) => v !== null && v !== undefined;

/** Kalimat status kartu — dipakai kartu dan uji. */
export function kalimatStatus(item, scopeType, induk = "aturan PT") {
  const fv = (v) => formatValue(item, v);
  if (punyaNilai(item.layer_value)) {
    return `Khusus ${KATA[scopeType].nama} ini: ${fv(item.layer_value)} (${induk}: ${fv(item.inherited_value)})`;
  }
  return `Mengikuti ${induk}: ${fv(item.inherited_value)}`;
}

function ScopedRuleCard({ item, scopeType, scopeId, scopeLabel, induk, onDone }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(undefined);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const own = punyaNilai(item.layer_value);
  const canEdit = item.can_edit === true;
  const nilaiAwal = own ? item.layer_value : item.inherited_value;
  const nilai = draft !== undefined ? draft : nilaiAwal;
  const kurangAlasan = item.requires_reason && !reason.trim();
  const tid = `scoped-${item.key}`;

  const buka = () => { setDraft(undefined); setReason(""); setError(null); setEditing(true); };
  const tutup = () => { setEditing(false); setDraft(undefined); setReason(""); setError(null); };

  const simpan = async () => {
    setBusy(true);
    setError(null);
    try {
      await configApi.save([{ key: item.key, value: nilai, scope_type: scopeType, scope_id: scopeId, reason: reason.trim() }]);
      tutup();
      await onDone("Aturan khusus tersimpan.");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const kembali = async () => {
    const ok = await askConfirm({
      title: "Hapus aturan khusus ini?",
      message: `${scopeLabel || `${KATA[scopeType].nama[0].toUpperCase()}${KATA[scopeType].nama.slice(1)} ini`} akan kembali mengikuti aturan PT.`,
      confirmLabel: "Kembali ikut aturan PT", testId: `${tid}-clear-confirm`,
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await configApi.clear({ key: item.key, scope_type: scopeType, scope_id: scopeId, reason: "Kembali ikut aturan PT" });
      tutup();
      await onDone("Kembali mengikuti aturan PT.");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="cfg-card" data-testid={`${tid}-card`}>
      <header className="cfg-card-head">
        <div className="cfg-card-title"><h3>{cleanCfgText(item.label)}</h3></div>
        {own ? <div className="cfg-card-badges"><span className="badge-purple">Khusus</span></div> : null}
      </header>
      <p className="cfg-hint-sm">{cleanCfgText(item.help)}</p>
      <p className="text-fs-13 text-kn-text" data-testid={`${tid}-status`}>
        {own ? <b>{kalimatStatus(item, scopeType, induk)}</b> : kalimatStatus(item, scopeType, induk)}
      </p>
      {error ? <ErrorNotice message={error} testId={`${tid}-error`} /> : null}
      {canEdit && editing ? (
        <div className="cfg-edit-zone">
          <div className="cfg-edit-row">
            <SettingEditor entry={item} value={nilai} onChange={setDraft} disabled={busy} testId={`${tid}-input`} />
          </div>
          <input className="form-input cfg-input-wide" value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder={item.requires_reason ? "Alasan perubahan (wajib untuk aturan berisiko tinggi)" : "Alasan perubahan (opsional)"}
            data-testid={`${tid}-reason`} />
          <div className="cfg-edit-actions">
            <button type="button" className="btn-primary btn-sm" onClick={simpan} disabled={busy || kurangAlasan}
              data-testid={`${tid}-save`}>
              <Save size={13} /> {busy ? "Menyimpan…" : "Simpan"}
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={tutup} disabled={busy}
              data-testid={`${tid}-cancel`}>Batal</button>
          </div>
        </div>
      ) : null}
      {canEdit && !editing ? (
        <div className="cfg-edit-actions">
          <button type="button" className="btn-secondary btn-sm" onClick={buka} disabled={busy} data-testid={`${tid}-edit`}>
            <SlidersHorizontal size={13} /> Atur khusus
          </button>
          {own ? (
            <button type="button" className="btn-secondary btn-sm" onClick={kembali} disabled={busy}
              data-testid={`${tid}-clear`}>
              <RotateCcw size={13} /> Kembali ikut aturan PT
            </button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

export default function ScopedRulesSection({ scopeType, scopeId, scopeLabel = "", entityId = "" }) {
  const kata = KATA[scopeType];
  const ptDipilih = Boolean(entityId) && entityId !== "all";
  // Pelanggan: server memakai PT pelanggan bila `entity_id` kosong. Barang tanpa PT terpilih: nilai semua PT.
  const induk = scopeType === "product" && !ptDipilih ? "aturan semua PT" : "aturan PT";
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hidden, setHidden] = useState(false);
  const [ok, setOk] = useState("");

  const load = useCallback(async () => {
    if (!kata || !scopeId) return;
    setLoading(true);
    setError(null);
    try {
      const params = { scope: scopeType, [kata.param]: scopeId };
      if (ptDipilih) params.entity_id = entityId;
      const d = await configApi.effective(params);
      setItems(d?.items || []);
      setHidden(false);
    } catch (e) {
      if (e?.response?.status === 403) setHidden(true);
      else setError(e);
    } finally {
      setLoading(false);
    }
  }, [kata, scopeType, scopeId, entityId, ptDipilih]);

  useEffect(() => { setOk(""); load(); }, [load]);

  if (!kata || !scopeId || hidden) return null;
  if (!loading && !error && items && items.length === 0) return null;

  const selesai = async (pesan) => { setOk(pesan); await load(); };
  return (
    <section className="section-card" data-testid={`scoped-rules-${scopeType}`}>
      <div className="section-head">
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={14} className="text-kn-action" aria-hidden="true" />
          <h3 className="text-fs-13 font-bold">{kata.judul}</h3>
        </div>
      </div>
      <div className="section-body space-y-2">
        <p className="cfg-hint-sm">Kosong berarti {kata.nama} mengikuti aturan PT-nya.</p>
        {loading && !items ? <LoadingLine text="Memuat aturan…" testId={`scoped-rules-${scopeType}-loading`} /> : null}
        {error ? <ErrorNotice message={error} onRetry={load} testId={`scoped-rules-${scopeType}-error`} /> : null}
        {ok ? <OkNotice message={ok} onDismiss={() => setOk("")} testId={`scoped-rules-${scopeType}-ok`} /> : null}
        {(items || []).map((it) => (
          <ScopedRuleCard key={it.key} item={it} scopeType={scopeType} scopeId={scopeId} scopeLabel={scopeLabel}
            induk={induk} onDone={selesai} />
        ))}
      </div>
    </section>
  );
}

/** Baris kartu Pusat Pengaturan untuk kunci berlapis pelanggan/barang (KF-T5). Kunci lain: tidak tampil. */
export function ScopedRulesSummary({ item }) {
  const layer = lapisanKhusus(item);
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!layer) return undefined;
    let alive = true;
    Promise.resolve()
      .then(() => configApi.layers({ key: item.key, scope_type: layer }))
      .then((d) => { if (alive) setData(d || { rows: [], total: 0 }); })
      .catch(() => { if (alive) setData(null); });
    return () => { alive = false; };
  }, [item.key, layer]);

  if (!layer) return null;
  const kata = KATA[layer];
  const n = data?.total;
  const rows = data?.rows || [];
  return (
    <div className="cfg-hint-sm" data-testid={`cfg-scoped-${item.key}`}>
      <Users size={12} className="mr-1 inline align-[-2px]" aria-hidden="true" />
      Bisa dibedakan per {kata.nama}
      {typeof n === "number" ? (
        n > 0 ? (
          <>
            {" — "}
            <button type="button" className="cfg-link-btn" onClick={() => setOpen((v) => !v)}
              data-testid={`cfg-scoped-count-${item.key}`}>
              {n} {kata.nama} diatur khusus
            </button>
          </>
        ) : <span data-testid={`cfg-scoped-count-${item.key}`}>{` — 0 ${kata.nama} diatur khusus`}</span>
      ) : null}
      {open && rows.length > 0 ? (
        <ul className="mt-1 space-y-0.5" data-testid={`cfg-scoped-list-${item.key}`}>
          {rows.map((r) => (
            <li key={r.scope_id}>
              <b>{r.scope_label}</b>: {formatValue(item, r.value)}
            </li>
          ))}
          {n > rows.length ? <li>Menampilkan {rows.length} dari {n} {kata.nama}.</li> : null}
        </ul>
      ) : null}
    </div>
  );
}
