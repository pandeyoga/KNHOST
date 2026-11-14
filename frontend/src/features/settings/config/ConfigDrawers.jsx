/**
 * ConfigDrawers — panel penjelas yang menjawab 3 pertanyaan user:
 *
 *  1. WhyThisValueDrawer  — "Kenapa nilainya begini?"  (jejak lapisan, mana yang menang)
 *  2. SimulatorPanel      — "Coba dulu"                (lihat akibat sebelum menyimpan)
 *  3. ChangeHistoryDrawer — "Riwayat"                  (siapa, kapan, dari→ke, alasan)
 *
 * Ketiganya sengaja memakai bahasa awam, bukan istilah teknis.
 */
import { useEffect, useState } from "react";
import { X, Layers, FlaskConical, History, Play, Check, AlertTriangle, Ban, Clock } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import KNSelect from "../../../components/KNSelect";
import KNDatePicker from "../../../components/KNDatePicker";
import { configApi, errMsg, formatValue, idNum, scopeText, shortVal, LAYER_TONE, VERDICT_TONE } from "./configApi";
import { formatDateTime } from "../../../utils/formatters";

function Shell({ title, subtitle, icon, onClose, children, testId }) {
  return (
    <div className="cfg-drawer-backdrop" data-testid={`${testId}-backdrop`}>
      <div className="cfg-drawer" data-testid={testId} role="dialog" aria-label={title}>
        <div className="cfg-drawer-head">
          <div className="cfg-drawer-title">
            {icon}
            <div>
              <h3>{title}</h3>
              {subtitle ? <p>{subtitle}</p> : null}
            </div>
          </div>
          <button className="icon-button" onClick={onClose} data-testid={`${testId}-close`}
            aria-label="Tutup">
            <X size={16} />
          </button>
        </div>
        <div className="cfg-drawer-body">{children}</div>
      </div>
    </div>
  );
}

const PADANAN = { legacy_global: "global", legacy_entity: "entity" };
function mergeLayers(list) {
  const src = (list || []).map((x) => ({ ...x }));
  const out = [];
  src.forEach((l) => {
    const to = PADANAN[l.layer];
    if (!to) { out.push(l); return; }
    const twin = src.find((x) => x.layer === to);
    if (!twin) { out.push({ ...l, layer: to }); return; }
    if (l.present && !twin.present) {
      Object.assign(twin, { present: true, value: l.value, note: l.note,
        changed_by: twin.changed_by || l.changed_by, changed_at: twin.changed_at || l.changed_at });
    }
    if (l.winner) twin.winner = true;
  });
  return out;
}

/* ─── 1. Kenapa nilainya begini? ─────────────────────────────────────────── */
export function WhyThisValueDrawer({ entry, ctx, onClose }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    setErr("");
    configApi
      .explain({ key: entry.key, ...ctx })
      .then((d) => alive && setData(d))
      .catch((e) => alive && setErr(errMsg(e, "Gagal memuat jejak nilai.")));
    return () => { alive = false; };
  }, [entry.key, ctx]);

  // KF-T4 (KF-UX-21) — satu baris per lapisan yang dikenal pengguna: lapisan lama digabung ke padanannya (Aturan grup
  // / Khusus PT); yang ditampilkan nilai pemenang di antara keduanya.
  const layers = mergeLayers(data?.explain || []);
  return (
    <Shell
      testId="cfg-why-drawer"
      icon={<Layers size={18} />}
      title="Kenapa nilainya begini?"
      subtitle={entry.label}
      onClose={onClose}
    >
      <ErrorNotice message={err} />
      {!data && !err ? <p className="cfg-hint">Memuat…</p> : null}
      {data ? (
        <>
          <div className="cfg-why-answer" data-testid="cfg-why-answer">
            <span className="cfg-why-value">{formatValue(entry, data.value)}</span>
            {/* KF-T3 — nilai yang dipakai mesin ditentukan penimpa terdaftar, bukan lapisan tersimpan. */}
            {data.overridden_by ? (
              <span className={`badge-${LAYER_TONE.override}`} data-testid="cfg-why-overridden">
                ditentukan oleh: {data.overridden_by.label}
              </span>
            ) : (
              <span className={`badge-${LAYER_TONE[data.source_layer] || "muted"}`}>
                ditentukan oleh: {data.source_label}
              </span>
            )}
          </div>
          <p className="cfg-hint">
            Sistem memakai nilai yang paling khusus: nilai khusus PT menang atas aturan grup, dan aturan grup
            menang atas bawaan sistem.
          </p>
          <ol className="cfg-layer-list" data-testid="cfg-layer-list">
            {layers.map((l, i) => (
              <li
                key={`${l.layer}-${i}`}
                className={`cfg-layer ${l.winner ? "winner" : ""} ${l.present ? "" : "empty"}`}
                data-testid={`cfg-layer-${l.layer}`}
              >
                <div className="cfg-layer-head">
                  <span className={`badge-${LAYER_TONE[l.layer] || "muted"}`}>{l.label}</span>
                  {/* G5-61 — nama PT, bukan id (`ent_ks…`); lapisan grup tidak menyebut cakupan teknis. */}
                  {l.scope_id && l.layer !== "global" ? <span className="cfg-scope-id">{scopeText(l.layer === "entity" || String(l.scope_id).startsWith("ent_") ? "entity" : l.layer, l.scope_id).split(": ").pop()}</span> : null}
                  {l.winner ? (
                    <span className="cfg-layer-win">
                      <Check size={12} /> DIPAKAI
                    </span>
                  ) : l.present ? (
                    <span className="cfg-layer-lose">kalah oleh nilai yang lebih khusus</span>
                  ) : (
                    <span className="cfg-layer-lose">belum diatur</span>
                  )}
                </div>
                <div className="cfg-layer-val">
                  {l.present ? formatValue(entry, l.value) : "—"}
                </div>
                <p className="cfg-layer-note">{l.note}</p>
                {l.changed_by ? (
                  <p className="cfg-layer-meta">
                    diubah oleh <b>{l.changed_by}</b>
                    {l.changed_at ? ` · ${String(l.changed_at).slice(0, 19).replace("T", " ")}` : ""}
                    {l.reason ? ` · alasan: “${l.reason}”` : ""}
                  </p>
                ) : null}
                {(l.scheduled || []).length > 0 ? (
                  <p className="cfg-layer-sched">
                    <Clock size={12} /> {l.scheduled.length} perubahan terjadwal:
                    {l.scheduled.map((s, k) => (
                      <span key={k}>
                        {" "}
                        {formatValue(entry, s.value)} mulai{" "}
                        {String(s.effective_from).slice(0, 10)}
                        {k < l.scheduled.length - 1 ? " ·" : ""}
                      </span>
                    ))}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
          <details className="cfg-wiring-box" data-testid="cfg-why-wiring">
            <summary>Detail teknis</summary>
            <h4>Bagian sistem yang memakai pengaturan ini</h4>
            <ul>
              {(entry.consumers || []).map((c) => (
                <li key={c}><code>{c}</code></li>
              ))}
              {(entry.consumers || []).length === 0 ? <li>—</li> : null}
            </ul>
            {data.wiring ? (
              <p className="cfg-hint-sm">
                Tersambung ke sistem? <b>{data.wiring.wiring_status === "OK" ? "Ya" : data.wiring.wiring_status}</b>
                {data.wiring.consumers_stale?.length
                  ? ` · rujukan basi: ${data.wiring.consumers_stale.join(", ")}`
                  : ""}
              </p>
            ) : null}
          </details>
        </>
      ) : null}
    </Shell>
  );
}

/* ─── 2. Coba dulu (Simulator) ───────────────────────────────────────────── */
export function SimulatorPanel({ entry, ctx, draftValue, onClose }) {
  const [sample, setSample] = useState({});
  const [useDraft, setUseDraft] = useState(draftValue !== undefined);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (nextSample = sample, withDraft = useDraft) => {
    setBusy(true); setErr("");
    try {
      const overrides = withDraft && draftValue !== undefined ? { [entry.key]: draftValue } : {};
      const d = await configApi.simulate({
        simulator: entry.simulate || "", key: entry.key,
        sample: nextSample, overrides, ctx,
      });
      setRes(d);
      setSample(d.sample || nextSample);
    } catch (e) {
      setErr(errMsg(e, "Simulasi gagal."));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { run({}, useDraft); /* eslint-disable-line */ }, []);

  const Icon = { ok: Check, warn: AlertTriangle, block: Ban }[res?.verdict] || Check;
  return (
    <Shell
      testId="cfg-simulator"
      icon={<FlaskConical size={18} />}
      title="Coba dulu — lihat akibatnya"
      subtitle={entry.label}
      onClose={onClose}
    >
      <ErrorNotice message={err} onRetry={() => run()} />
      <p className="cfg-hint">
        Masukkan contoh angka, lalu lihat aturan mana yang menang dan hasil hitungnya.
        Tidak ada yang disimpan di langkah ini.
      </p>

      {draftValue !== undefined ? (
        <label className="cfg-check-row" data-testid="cfg-sim-use-draft">
          <input type="checkbox" checked={useDraft}
            onChange={(e) => { setUseDraft(e.target.checked); run(sample, e.target.checked); }} />
          <span>Pakai nilai yang sedang saya isi ({formatValue(entry, draftValue)}) — belum tersimpan</span>
        </label>
      ) : null}

      {(res?.inputs || []).length > 0 ? (
        <div className="cfg-sim-inputs" data-testid="cfg-sim-inputs">
          {res.inputs.map((inp) => (
            <label key={inp.name} className="cfg-sim-field">
              <span>{inp.label}{inp.unit ? ` (${inp.unit})` : ""}</span>
              {inp.type === "bool" ? (
                <input type="checkbox" checked={!!sample[inp.name]}
                  onChange={(e) => setSample({ ...sample, [inp.name]: e.target.checked })}
                  data-testid={`cfg-sim-in-${inp.name}`} />
              ) : (
                <input
                  className="form-input cfg-input"
                  type={inp.type === "text" ? "text" : "number"}
                  value={sample[inp.name] ?? inp.default ?? ""}
                  onChange={(e) => setSample({
                    ...sample,
                    [inp.name]: inp.type === "text" ? e.target.value : Number(e.target.value),
                  })}
                  data-testid={`cfg-sim-in-${inp.name}`}
                />
              )}
            </label>
          ))}
        </div>
      ) : null}

      <button className="btn-primary cfg-sim-run" onClick={() => run()} disabled={busy}
        data-testid="cfg-sim-run">
        <Play size={14} /> {busy ? "Menghitung…" : "Hitung ulang"}
      </button>

      {res ? (
        <>
          <div className={`cfg-sim-result tone-${VERDICT_TONE[res.verdict] || "muted"}`}
            data-testid="cfg-sim-result">
            <Icon size={16} />
            <span>{res.result}</span>
          </div>
          <h4 className="cfg-sub">Langkah hitung</h4>
          <table className="data-table cfg-sim-steps" data-testid="cfg-sim-steps">
            <tbody>
              {(res.steps || []).map((s, i) => (
                <tr key={i}>
                  <td>{s.label}</td>
                  <td className="tabular-nums cfg-right"><b>{s.value}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
          <h4 className="cfg-sub">Aturan yang dipakai</h4>
          <table className="data-table" data-testid="cfg-sim-resolved">
            <thead>
              <tr><th>Pengaturan</th><th>Nilai</th><th>Asal</th></tr>
            </thead>
            <tbody>
              {(res.resolved || []).map((r) => (
                <tr key={r.key} className={r.hypothetical ? "cfg-row-hyp" : ""}>
                  <td>{r.label}</td>
                  <td className="tabular-nums">{String(r.value)}</td>
                  <td>
                    <span className={`badge-${LAYER_TONE[r.source_layer] || "muted"}`}>
                      {r.hypothetical ? "sedang dicoba" : r.source_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </Shell>
  );
}

/* ─── 3. Riwayat perubahan ───────────────────────────────────────────────── */
// KF-T4 (KF-UX-19) — satu tabel untuk laci per kartu/kelompok dan tab Riwayat: saringan PT · orang · rentang tanggal
// · kelompok, nilai diformat seperti di kartu, "Muat berikutnya" dengan jumlah total, "Pulihkan nilai ini" (laci kartu).
const HAL = 50;

function HistoryTable({ rows, onRestore, testId }) {
  return (
    <div className="cfg-table-wrap">
      <table className="data-table" data-testid={testId}>
        <thead>
          <tr>
            <th>Waktu</th><th>Pengaturan</th><th>Berlaku untuk</th>
            <th>Dari → Ke</th><th>Oleh</th><th>Alasan</th>{onRestore ? <th aria-label="Aksi" /> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-testid={`cfg-history-row-${r.id}`}>
              <td className="cfg-nowrap">
                {formatDateTime(r.changed_at)}
                {r.scheduled ? <span className="badge-orange cfg-ml">terjadwal</span> : null}
                {r.cancelled ? (
                  <span className="badge-muted cfg-ml" data-testid={`cfg-history-cancelled-${r.id}`}
                    title={r.cancel_reason ? `Alasan pembatalan: ${r.cancel_reason}` : undefined}>dibatalkan</span>
                ) : null}
              </td>
              <td>{r.label}</td>
              <td><span className="badge-muted">{scopeText(r.scope_type, r.scope_id, r.scope_label)}</span></td>
              <td className="tabular-nums">
                <span className="cfg-from">{r.type ? formatValue(r, r.prev_value) : shortVal(r.prev_value)}</span>
                {" → "}
                <b>{r.cleared ? "dicabut (ikut nilai grup)" : r.type ? formatValue(r, r.value) : shortVal(r.value)}</b>
              </td>
              <td>{r.changed_by || "—"}</td>
              <td>{r.reason || "—"}</td>
              {onRestore ? (
                <td>
                  {!r.cleared && !r.cancelled ? (
                    <button type="button" className="cfg-link-btn" onClick={() => onRestore(r)}
                      data-testid={`cfg-history-restore-${r.id}`}>Pulihkan nilai ini</button>
                  ) : null}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Saringan + muat bertahap. `fixed` = saringan yang dikunci pemanggil (`key` / `group`). */
function useHistory(fixed) {
  const [f, setF] = useState({ entity: "", changed_by: "", date_from: "", date_to: "", group: "" });
  const [rows, setRows] = useState(null);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const params = (offset) => ({
    ...fixed, limit: HAL, offset,
    ...(f.group && !fixed.group && !fixed.key ? { group: f.group } : {}),
    ...(f.entity ? { scope_type: "entity", scope_id: f.entity } : {}),
    ...(f.changed_by.trim() ? { changed_by: f.changed_by.trim() } : {}),
    ...(f.date_from ? { date_from: f.date_from } : {}), ...(f.date_to ? { date_to: f.date_to } : {}),
  });
  const fetchPage = async (offset) => {
    setBusy(true); setErr("");
    try {
      const d = await configApi.history(params(offset));
      setRows((cur) => (offset ? [...(cur || []), ...(d.rows || [])] : (d.rows || [])));
      setTotal(d.total ?? (d.rows || []).length);
    } catch (e) { setErr(errMsg(e, "Gagal memuat riwayat.")); }
    setBusy(false);
  };
  const key = JSON.stringify({ fixed, f });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchPage(0); }, [key]);
  return { f, setF, rows, total, err, busy, more: () => fetchPage((rows || []).length) };
}

function HistoryFilters({ h, entities = [], groups = null }) {
  const set = (k) => (v) => h.setF((cur) => ({ ...cur, [k]: v }));
  const ptOpts = [{ value: "__semua__", label: "Semua PT" }, ...(entities || []).map((e) => ({
    value: e.id, label: e.short_name || e.legal_name || e.name || "PT" }))];
  return (
    <div className="cfg-history-filters" data-testid="cfg-history-filters">
      <KNSelect value={h.f.entity || "__semua__"} onValueChange={(v) => set("entity")(v === "__semua__" ? "" : v)}
        options={ptOpts} className="field cfg-select-sm" data-testid="cfg-history-entity" />
      {groups ? (
        <KNSelect value={h.f.group || "__semua__"} onValueChange={(v) => set("group")(v === "__semua__" ? "" : v)}
          options={[{ value: "__semua__", label: "Semua kelompok" }, ...groups.map((g) => ({ value: g.id, label: g.label }))]}
          className="field cfg-select-sm" data-testid="cfg-history-group" />
      ) : null}
      <input className="form-input cfg-input-sm" placeholder="Diubah oleh…" value={h.f.changed_by}
        onChange={(e) => set("changed_by")(e.target.value)} data-testid="cfg-history-by" />
      <KNDatePicker value={h.f.date_from} onChange={set("date_from")} placeholder="Dari tanggal"
        data-testid="cfg-history-from" />
      <KNDatePicker value={h.f.date_to} onChange={set("date_to")} placeholder="Sampai tanggal"
        data-testid="cfg-history-to" />
    </div>
  );
}

function HistoryBody({ h, onRestore, testId, empty }) {
  return (
    <>
      <ErrorNotice message={h.err} />
      {h.rows === null && !h.err ? <p className="cfg-hint">Memuat…</p> : null}
      {h.rows && h.rows.length === 0 ? <p className="cfg-empty" data-testid={`${testId}-empty`}>{empty}</p> : null}
      {h.rows && h.rows.length > 0 ? <HistoryTable rows={h.rows} onRestore={onRestore} testId={testId} /> : null}
      <p className="cfg-hint-sm" data-testid={`${testId}-total`}>
        {idNum((h.rows || []).length, 0)} dari {idNum(h.total, 0)} perubahan
        {h.rows && h.rows.length < h.total ? (
          <> · <button type="button" className="cfg-link-btn" disabled={h.busy} onClick={h.more}
            data-testid={`${testId}-more`}>Muat berikutnya</button></>
        ) : null}
      </p>
    </>
  );
}

export function ChangeHistoryDrawer({ entry, group = "", groupLabel = "", entities = [], onClose, onRestore = null }) {
  const h = useHistory(entry?.key ? { key: entry.key } : group ? { group } : {});
  return (
    <Shell
      testId="cfg-history"
      icon={<History size={18} />}
      title="Riwayat perubahan"
      subtitle={entry?.label || groupLabel || "Semua pengaturan"}
      onClose={onClose}
    >
      <p className="cfg-hint">Semua perubahan pengaturan, terbaru dulu. Nilai lama tidak pernah dihapus.</p>
      <HistoryFilters h={h} entities={entities} />
      <HistoryBody h={h} onRestore={entry ? onRestore : null} testId="cfg-history-table"
        empty="Belum ada perubahan — nilainya masih sesuai bawaan sistem." />
    </Shell>
  );
}

/* Riwayat di tab "Riwayat Perubahan" (tanpa harus buka laci). */
export function ChangeHistoryInline({ entities = [], groups = [] }) {
  const h = useHistory({});
  return (
    <>
      <HistoryFilters h={h} entities={entities} groups={groups} />
      <HistoryBody h={h} testId="cfg-history-inline" empty="Belum ada perubahan pengaturan yang cocok." />
    </>
  );
}
