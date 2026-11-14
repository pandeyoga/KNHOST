/**
 * DualControlView — KF-T6: Pengaturan › Persetujuan › Kontrol dua orang (`docs/blueprint/unit/KF-T6.md`).
 *
 * Satu tabel untuk setiap aturan "pengaju tidak boleh memutuskan sendiri", per lapisan (Semua PT / satu PT):
 * jumlah orang (1/2), batas nominal di atasnya selalu dua orang, dan sumber nilainya. Tombol "Tim kecil" menjadikan
 * semua aksi cukup satu orang pada lapisan terpilih (keputusan pemilik: finance belum tentu dua orang).
 *
 * Baca: `GET /api/kontrol/aturan` (izin `settings.view`). Simpan: `PUT /api/config/values` (banyak butir, SATU
 * alasan) — validasi, wajib-alasan, riwayat, dan jejak audit sama dengan Pusat Pengaturan; tidak ada jalur tulis baru.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Save, ShieldCheck, Users } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { askConfirm, askReason } from "../../../services/confirmService";
import ErrorNotice from "../../../components/ErrorNotice";
import KNSelect from "../../../components/KNSelect";
import LoadingLine from "../../../components/LoadingLine";
import MoneyInput from "../../../components/MoneyInput";
import OkNotice from "../../../components/OkNotice";
import { entityOptions, entityShortById } from "../../../utils/entityLabel";
import { parseDecimal } from "../../../utils/decimalInput";
import { formatCurrency } from "../../../utils/formatters";

export const SEMUA_PT = "all";
const OPSI_ORANG = [{ value: "1", label: "Cukup satu orang" }, { value: "2", label: "Harus dua orang" }];

/** Label sumber nilai — tanpa istilah teknis (L1). */
export function sumberLabel(sumber, layerAll) {
  if (sumber === "entity") return "Aturan PT ini";
  if (sumber === "global") return layerAll ? "Aturan semua PT" : "Mengikuti semua PT";
  return "Bawaan";
}

/** Butir `PUT /api/config/values` dari perubahan layar (dipakai tombol simpan & uji). */
export function itemsPerubahan(data, draft, layer, reason) {
  const scope = layer === SEMUA_PT ? { scope_type: "global", scope_id: "" } : { scope_type: "entity", scope_id: layer };
  const out = [];
  const push = (key, value) => out.push({ key, value, reason, ...scope });
  (data?.rows || []).forEach((r) => {
    const d = draft.rows[r.aksi] || {};
    if (d.min_orang !== undefined && d.min_orang !== r.min_orang) push(r.kunci_min_orang, d.min_orang);
    const batas = d.batas_nominal === undefined ? null : (parseDecimal(String(d.batas_nominal || "0")) || 0);
    if (r.punya_nominal && batas !== null && batas !== Number(r.batas_nominal || 0)) push(r.kunci_batas, batas);
  });
  if (draft.admin_boleh_sendiri !== undefined && draft.admin_boleh_sendiri !== data?.admin_boleh_sendiri) {
    push("kontrol.admin_boleh_sendiri", draft.admin_boleh_sendiri);
  }
  if (draft.admin_tetap_dua_orang !== undefined) {
    const a = [...draft.admin_tetap_dua_orang].sort().join("|");
    if (a !== [...(data?.admin_tetap_dua_orang || [])].sort().join("|")) {
      push("kontrol.admin_tetap_dua_orang", draft.admin_tetap_dua_orang);
    }
  }
  return out;
}

const KOSONG = { rows: {} };

export default function DualControlView({ selectedEntity, entities = [] }) {
  const awal = selectedEntity && selectedEntity !== SEMUA_PT ? selectedEntity : SEMUA_PT;
  const [layer, setLayer] = useState(awal);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(KOSONG);
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState("");

  const layerAll = layer === SEMUA_PT;
  const namaLapisan = layerAll ? "Semua PT" : entityShortById(entities, layer, "PT terpilih");
  const opsiLapisan = useMemo(() => [{ value: SEMUA_PT, label: "Semua PT" },
    ...entityOptions(entities).filter((o) => o.value && o.value !== SEMUA_PT)], [entities]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = layerAll ? {} : { entity_id: layer };
      const r = await axios.get(`${API}/kontrol/aturan`, { params });
      setData(r.data);
      setDraft(KOSONG);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [layer, layerAll]);

  useEffect(() => { load(); }, [load]);

  const canEdit = !!data?.can_edit;
  const nilai = (r, f) => (draft.rows[r.aksi] || {})[f] ?? r[f];
  const ubahBaris = (aksi, patch) => {
    setOk("");
    setDraft((d) => ({ ...d, rows: { ...d.rows, [aksi]: { ...(d.rows[aksi] || {}), ...patch } } }));
  };
  const adminBoleh = draft.admin_boleh_sendiri ?? data?.admin_boleh_sendiri;
  const adminTetap = draft.admin_tetap_dua_orang ?? data?.admin_tetap_dua_orang ?? [];
  const perubahan = itemsPerubahan(data, draft, layer, "");

  const kirim = async (items) => {
    setBusy(true);
    setError(null);
    try {
      await axios.put(`${API}/config/values`, { items });
      setOk("Aturan kontrol dua orang tersimpan.");
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const simpan = async () => {
    if (!perubahan.length) return;
    const reason = await askReason({
      title: "Simpan aturan kontrol dua orang",
      message: `${perubahan.length} perubahan untuk ${namaLapisan}. Tulis alasan perubahan (tercatat di riwayat).`,
      confirmLabel: "Simpan perubahan", testId: "dual-save-confirm",
    });
    if (!reason) return;
    await kirim(itemsPerubahan(data, draft, layer, reason));
  };

  const timKecil = async () => {
    const reason = await askReason({
      title: "Tim kecil — semua cukup satu orang",
      message: `Semua aksi untuk ${namaLapisan} akan cukup diputuskan satu orang. Batas nominal tidak diubah. Lanjutkan?`,
      confirmLabel: "Lanjutkan", testId: "dual-small-team-confirm",
    });
    if (!reason) return;
    const scope = layerAll ? { scope_type: "global", scope_id: "" } : { scope_type: "entity", scope_id: layer };
    await kirim((data?.rows || []).map((r) => ({ key: r.kunci_min_orang, value: "1", reason, ...scope })));
  };

  const batal = async () => {
    if (await askConfirm({ title: "Buang perubahan?", message: "Perubahan yang belum disimpan akan hilang.",
      confirmLabel: "Buang", testId: "dual-discard-confirm" })) setDraft(KOSONG);
  };

  const bagian = data?.bagian || [];
  return (
    <div className="cfg-hub" data-testid="dual-control-view">
      <p className="cfg-group-intro">
        <ShieldCheck size={13} className="mr-1 inline align-[-2px] text-[#0058CC]" aria-hidden="true" />
        Atur aksi mana yang <b>harus diputuskan orang lain</b> selain pengajunya. "Cukup satu orang" berarti pengaju boleh
        memutuskan dokumennya sendiri; di atas batas nominal, dokumen selalu butuh orang kedua.
      </p>
      <div className="cfg-toolbar">
        <div className="cfg-scope-box" data-testid="dual-scope-box">
          <span className="cfg-scope-caption">Berlaku untuk</span>
          <KNSelect value={layer} onValueChange={(v) => { setOk(""); setLayer(v || SEMUA_PT); }} options={opsiLapisan}
            className="field cfg-select-sm" data-testid="dual-scope" />
        </div>
        {canEdit ? (
          <button type="button" className="btn-secondary btn-sm" onClick={timKecil} disabled={busy || loading}
            data-testid="dual-small-team">
            <Users size={13} /> Tim kecil — semua cukup satu orang
          </button>
        ) : null}
      </div>

      {error ? <ErrorNotice message={error} onRetry={load} testId="dual-error" /> : null}
      {ok ? <OkNotice message={ok} testId="dual-ok" /> : null}
      {loading && !data ? <LoadingLine text="Memuat aturan kontrol dua orang…" testId="dual-loading" /> : null}
      {data && !canEdit ? (
        <div className="cfg-notice info" data-testid="dual-readonly">
          <ShieldCheck size={15} />
          <span>
            Anda dapat melihat aturan ini, tetapi tidak dapat mengubahnya
            {layerAll ? " untuk Semua PT (khusus peran lintas PT dengan akses kelola pengaturan)." : "."}
          </span>
        </div>
      ) : null}

      {data ? (
        <>
          {bagian.map((b) => {
            const baris = data.rows.filter((r) => r.bagian === b);
            if (!baris.length) return null;
            return (
              <section key={b} className="section-card mt-3" data-testid={`dual-section-${b}`}>
                <h3 className="text-[13px] font-semibold mb-2">{b}</h3>
                <table className="data-table">
                  <thead>
                    <tr><th>Aksi</th><th>Jumlah orang</th><th>Dua orang di atas (Rp)</th><th>Sumber</th></tr>
                  </thead>
                  <tbody>
                    {baris.map((r) => (
                      <tr key={r.aksi} data-testid={`dual-row-${r.aksi}`}>
                        <td>{r.label}</td>
                        <td>
                          <KNSelect value={nilai(r, "min_orang")} options={OPSI_ORANG} disabled={!canEdit || busy}
                            onValueChange={(v) => ubahBaris(r.aksi, { min_orang: v })}
                            className="field cfg-select-sm" data-testid={`dual-min-${r.aksi}`} />
                        </td>
                        <td>
                          {r.punya_nominal ? (
                            canEdit ? (
                              <MoneyInput value={nilai(r, "batas_nominal")} disabled={busy}
                                onChange={(v) => ubahBaris(r.aksi, { batas_nominal: v })} testId={`dual-limit-${r.aksi}`} />
                            ) : <span data-testid={`dual-limit-${r.aksi}`}>{formatCurrency(r.batas_nominal || 0)}</span>
                          ) : <span className="text-[#8E8E93]" data-testid={`dual-limit-${r.aksi}`}>—</span>}
                        </td>
                        <td data-testid={`dual-source-${r.aksi}`}>{sumberLabel(r.sumber, layerAll)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            );
          })}

          <section className="section-card mt-3" data-testid="dual-admin">
            <h3 className="text-[13px] font-semibold mb-2">Pengecualian Admin</h3>
            <label className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={!!adminBoleh} disabled={!canEdit || busy} data-testid="dual-admin-self"
                onChange={(e) => { setOk(""); setDraft((d) => ({ ...d, admin_boleh_sendiri: e.target.checked })); }} />
              Admin boleh memutuskan dokumennya sendiri (tiap kejadian dicatat di jejak persetujuan)
            </label>
            <p className="text-[12px] text-[#6B6B73] mt-2 mb-1">Tetap dua orang walau Admin:</p>
            <div className="grid gap-1 sm:grid-cols-2">
              {data.rows.map((r) => (
                <label key={r.aksi} className="flex items-center gap-2 text-[12px]">
                  <input type="checkbox" checked={adminTetap.includes(r.aksi)} disabled={!canEdit || busy}
                    data-testid={`dual-admin-keep-${r.aksi}`}
                    onChange={(e) => {
                      setOk("");
                      const next = e.target.checked ? [...adminTetap, r.aksi] : adminTetap.filter((x) => x !== r.aksi);
                      setDraft((d) => ({ ...d, admin_tetap_dua_orang: next }));
                    }} />
                  {r.label}
                </label>
              ))}
            </div>
          </section>

          {canEdit ? (
            <div className="flex gap-2 justify-end mt-3">
              <button type="button" className="btn-secondary btn-sm" onClick={batal} disabled={!perubahan.length || busy}
                data-testid="dual-discard">Buang perubahan</button>
              <button type="button" className="btn-primary btn-sm" onClick={simpan} disabled={!perubahan.length || busy}
                data-testid="dual-save">
                <Save size={13} /> Simpan perubahan
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
