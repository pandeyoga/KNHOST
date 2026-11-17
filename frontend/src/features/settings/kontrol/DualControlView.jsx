/**
 * DualControlView — KF-T6: Pengaturan › Persetujuan › Kontrol dua orang (`docs/blueprint/unit/KF-T6.md`).
 *
 * Satu tabel untuk setiap aturan "pengaju tidak boleh memutuskan sendiri", per lapisan (Semua PT / satu PT):
 * jumlah orang (1/2), batas nominal di atasnya selalu dua orang, dan sumber nilainya. Tombol "Tim kecil" menjadikan
 * semua aksi cukup satu orang pada lapisan terpilih (keputusan pemilik: finance belum tentu dua orang).
 *
 * Baca: `GET /api/kontrol/aturan` (izin `settings.view`). Simpan: `PUT /api/config/values` (banyak butir, SATU
 * alasan) — validasi, wajib-alasan, riwayat, dan jejak audit sama dengan Pusat Pengaturan; tidak ada jalur tulis baru.
 *
 * Pola UI 16 Nov (`docs/blueprint/04_POLA_UI.md` §2.D, pemilik M43): daftar padat, SATU baris per aksi — nama (?) ·
 * jumlah orang ▾ · batas nominal (hanya bila berlaku: aksi bernominal yang "Cukup satu orang") · sumber. Tanpa baris
 * gema "Rp 0" di bawah isian; paragraf pengantar pindah ke ikon ?; satu tombol Simpan di bilah simpan bawah.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, ChevronDown, ChevronRight, Eye, Save, Users } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { askConfirm, askReason } from "../../../services/confirmService";
import ErrorNotice from "../../../components/ErrorNotice";
import KNSelect from "../../../components/KNSelect";
import LoadingLine from "../../../components/LoadingLine";
import MoneyInput from "../../../components/MoneyInput";
import OkNotice from "../../../components/OkNotice";
import { HelpTip } from "../../../components/ListPageParts";
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
/** Warna lencana sumber = warna lapisan Pusat Pengaturan (bawaan abu · grup biru · PT ungu). */
const SUMBER_TONE = { entity: "badge-purple", global: "badge-blue" };

const BANTUAN = "Atur aksi mana yang harus diputuskan orang lain selain pengajunya. \"Cukup satu orang\" berarti pengaju "
  + "boleh memutuskan dokumennya sendiri; di atas batas nominal, dokumen selalu butuh orang kedua (0 = tanpa batas). "
  + "\"Harus dua orang\" berarti selalu orang lain yang memutuskan.";

/** Penjelasan satu baris aksi (ikon ? di nama) — kalimat dampak yang sama dengan registri pengaturan. */
export function bantuanAksi(r) {
  return `Harus dua orang: pengaju “${r.label}” tidak bisa memutuskannya sendiri — rekan lain yang berwenang yang `
    + `memutuskan. Cukup satu orang: pengaju boleh memutuskan sendiri${r.punya_nominal
      ? ", kecuali nilainya di atas batas nominal (0 = tanpa batas)." : "."}`;
}

/** Batas nominal hanya berlaku untuk aksi bernominal yang "Cukup satu orang" (dua orang = selalu dua orang). */
export const batasBerlaku = (r, minOrang) => Boolean(r.punya_nominal) && String(minOrang) === "1";

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
  const [adminOpen, setAdminOpen] = useState(false);

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

  // Kolom batas: isian hanya bila berlaku; selain itu "—" (aksi tanpa nominal, atau "Harus dua orang").
  const kolomBatas = (r) => {
    if (!batasBerlaku(r, nilai(r, "min_orang"))) {
      return (
        <span className="text-kn-text-2" data-testid={`dual-limit-${r.aksi}`}
          title={r.punya_nominal ? "Selalu dua orang — batas nominal tidak dipakai" : "Aksi ini tanpa nominal"}>—</span>
      );
    }
    if (!canEdit) {
      const batas = Number(r.batas_nominal || 0);
      return (
        <span data-testid={`dual-limit-${r.aksi}`}>
          {batas > 0 ? `dua orang di atas ${formatCurrency(batas)}` : "tanpa batas nominal"}
        </span>
      );
    }
    return (
      <span className="cfg-dual-amount">
        <span className="whitespace-nowrap">dua orang di atas</span>
        <span className="cfg-dual-money">
          <MoneyInput value={nilai(r, "batas_nominal")} disabled={busy} showPreview={false}
            aria-label={`${r.label}: dua orang di atas (Rp)`}
            onChange={(v) => ubahBaris(r.aksi, { batas_nominal: v })} testId={`dual-limit-${r.aksi}`} />
        </span>
      </span>
    );
  };

  const bagian = data?.bagian || [];
  const jumlahTetap = adminTetap.filter((a) => (data?.rows || []).some((r) => r.aksi === a)).length;
  return (
    <div className="cfg-hub cfg-group-view" data-testid="dual-control-view">
      <div className="cfg-toolbar">
        <div className="cfg-scope-box" data-testid="dual-scope-box">
          <span className="cfg-scope-caption"><Building2 size={13} /> Berlaku untuk</span>
          <KNSelect value={layer} onValueChange={(v) => { setOk(""); setLayer(v || SEMUA_PT); }} options={opsiLapisan}
            className="field cfg-select-sm" data-testid="dual-scope" />
        </div>
        <HelpTip text={BANTUAN} testId="dual-help" label="Tentang kontrol dua orang" />
        {canEdit ? (
          <button type="button" className="btn-secondary btn-sm ml-auto" onClick={timKecil} disabled={busy || loading}
            data-testid="dual-small-team">
            <Users size={13} /> Tim kecil — semua cukup satu orang
          </button>
        ) : null}
      </div>

      {error ? <ErrorNotice message={error} onRetry={load} testId="dual-error" /> : null}
      {ok ? <OkNotice message={ok} testId="dual-ok" /> : null}
      {loading && !data ? <LoadingLine text="Memuat aturan kontrol dua orang…" testId="dual-loading" /> : null}
      {data && !canEdit ? (
        <p className="cfg-readonly-line" data-testid="dual-readonly">
          <Eye size={13} aria-hidden="true" />
          Hanya baca — Anda dapat melihat aturan ini, tetapi tidak dapat mengubahnya
          {layerAll ? " untuk Semua PT (khusus peran lintas PT dengan akses kelola pengaturan)." : "."}
        </p>
      ) : null}

      {data ? (
        <>
          {bagian.map((b) => {
            const baris = data.rows.filter((r) => r.bagian === b);
            if (!baris.length) return null;
            return (
              <section key={b} className="cfg-section" data-testid={`dual-section-${b}`}>
                <h4 className="cfg-section-title">{b}</h4>
                <div className="cfg-rows">
                  {baris.map((r) => (
                    <div key={r.aksi} className="cfg-dual-row" data-testid={`dual-row-${r.aksi}`}>
                      <span className="cfg-row-name">
                        <span className="cfg-row-title">{r.label}</span>
                        <HelpTip text={bantuanAksi(r)} testId={`dual-help-${r.aksi}`} label={`Tentang ${r.label}`} />
                      </span>
                      <KNSelect value={nilai(r, "min_orang")} options={OPSI_ORANG} disabled={!canEdit || busy}
                        onValueChange={(v) => ubahBaris(r.aksi, { min_orang: v })} aria-label={`${r.label}: jumlah orang`}
                        className="field cfg-select-sm" data-testid={`dual-min-${r.aksi}`} />
                      <span className="cfg-dual-limit">{kolomBatas(r)}</span>
                      <span className="cfg-dual-source">
                        <span className={SUMBER_TONE[r.sumber] || "badge-muted"} title="Asal nilai yang berlaku sekarang"
                          data-testid={`dual-source-${r.aksi}`}>{sumberLabel(r.sumber, layerAll)}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}

          <section className="cfg-section" data-testid="dual-admin">
            <h4 className="cfg-section-title">Pengecualian Admin</h4>
            <div className="cfg-rows">
              <div className="cfg-row">
                <span className="cfg-row-name">
                  <label className="cfg-row-title" htmlFor="dual-admin-self">Admin boleh memutuskan dokumennya sendiri</label>
                  <HelpTip text="Bila dicentang, Admin tidak terkena aturan dua orang; tiap kejadian dicatat di jejak persetujuan."
                    testId="dual-admin-self-help" label="Tentang pengecualian Admin" />
                </span>
                <input type="checkbox" id="dual-admin-self" checked={!!adminBoleh} disabled={!canEdit || busy}
                  data-testid="dual-admin-self"
                  onChange={(e) => { setOk(""); setDraft((d) => ({ ...d, admin_boleh_sendiri: e.target.checked })); }} />
              </div>
              <div>
                <div className="cfg-row">
                  <button type="button" className="cfg-card-toggle" aria-expanded={adminOpen}
                    aria-label="Buka daftar aksi yang tetap dua orang walau Admin" data-testid="dual-admin-keep-toggle"
                    onClick={() => setAdminOpen((v) => !v)}>
                    {adminOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </button>
                  <span className="cfg-row-name">
                    <span className="cfg-row-title">Tetap dua orang walau Admin</span>
                    <HelpTip text="Admin pun tidak boleh memutuskan sendiri untuk aksi yang dicentang di daftar ini."
                      testId="dual-admin-keep-help" label="Tentang daftar tetap dua orang" />
                  </span>
                  <span className="cfg-row-val" data-testid="dual-admin-keep-count">
                    {adminBoleh ? `${jumlahTetap} aksi` : "tidak berlaku — Admin ikut aturan dua orang"}
                  </span>
                  <button type="button" className="btn-secondary btn-sm" onClick={() => setAdminOpen((v) => !v)}
                    data-testid="dual-admin-keep-open">{adminOpen ? "Tutup" : (canEdit ? "Ubah" : "Lihat")}</button>
                </div>
                {adminOpen ? (
                  <div className="cfg-row-body cfg-check-grid" data-testid="dual-admin-keep-list">
                    {data.rows.map((r) => (
                      <label key={r.aksi} className="cfg-check">
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
                ) : null}
              </div>
            </div>
          </section>

          {canEdit ? (
            <div className="cfg-savebar" data-testid="dual-savebar">
              {perubahan.length ? (
                <span className="text-fs-12 text-kn-warning-text" data-testid="dual-dirty-count">
                  {perubahan.length} perubahan belum disimpan
                </span>
              ) : null}
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
