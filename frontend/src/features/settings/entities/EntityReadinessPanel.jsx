/**
 * EntityReadinessPanel (FASE E-3 / E1.9) — “apa lagi yang kurang?” per badan usaha.
 *
 * Badan usaha baru sering “lahir setengah jadi”: ada di daftar, tetapi belum punya
 * pengguna/rekening/harga — lalu orang menyimpulkan aplikasinya rusak karena
 * layarnya kosong. Panel ini menjawabnya dengan angka terhitung dan tombol yang
 * MENGANTAR ke layar penyelesaiannya, bukan sekadar daftar centang statis.
 *
 * KP-T2 — judul "Kesiapan PT"; daftar butir memakai `EntityCompletionSteps` (sumber tautan & teks yang sama dengan
 * langkah "Lengkapi PT" di wizard dan bagian Kesiapan di detail PT). Pilihan awal = PT aktif bila ada.
 */
import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, RefreshCw } from "lucide-react";

import FilterChips from "../../../components/FilterChips";
import EntityCompletionSteps from "./EntityCompletionSteps";
import { getReadiness, errText } from "./entityApi";

export default function EntityReadinessPanel({ entities = [], selectedEntity = "", canManage = false, onError }) {
  const active = entities.filter((e) => e.status === "active");
  const pickDefault = () => (active.find((e) => e.id === selectedEntity) || active[0])?.id || "";
  const [entityId, setEntityId] = useState(pickDefault);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!entityId && active.length) setEntityId(pickDefault());
  }, [active, entityId]);

  const load = useCallback(async () => {
    if (!entityId) return;
    setLoading(true);
    try {
      setData(await getReadiness(entityId));
    } catch (e) {
      onError?.(errText(e, "Gagal memuat daftar kesiapan."));
    } finally {
      setLoading(false);
    }
  }, [entityId, onError]);

  useEffect(() => { load(); }, [load]);

  const pct = data?.percent ?? 0;
  const tone = pct === 100 ? "text-kn-success-text" : pct >= 60 ? "text-kn-warning-text" : "text-kn-danger-text";
  const bar = pct === 100 ? "bg-kn-success-solid" : pct >= 60 ? "bg-kn-warning-text" : "bg-kn-danger";

  return (
    <div className="section-card" data-testid="entity-readiness-panel">
      <div className="section-head">
        <div className="flex items-center gap-2">
          <ClipboardCheck size={15} className="text-kn-special-text" />
          <h2 data-testid="entity-readiness-title">Kesiapan PT</h2>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <FilterChips testId="readiness-pick" ariaLabel="Pilih PT" value={entityId} onChange={setEntityId}
            options={active.map((e) => ({ key: e.id, label: e.short_name || e.legal_name }))} />
          <button type="button" className="icon-button" aria-label="Muat ulang"
                  data-testid="readiness-refresh" onClick={load}>
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      <div className="section-body">
        {data && (
          <div className={`mb-3 rounded-md border px-3 py-2 ${pct === 100
            ? "border-kn-success-soft bg-kn-success-soft" : "border-kn-warning-soft bg-kn-warning-soft"}`}
               data-testid="readiness-summary">
            <p className="text-fs-13 font-bold text-kn-text">
              {data.ready} dari {data.total} hal sudah siap
              <span className={`ml-2 tabular-nums ${tone}`}>({pct}%)</span>
            </p>
            <p className="text-fs-12 text-kn-text-2">
              {pct === 100
                ? "PT ini sudah lengkap dan siap dipakai transaksi sehari-hari."
                : "Selesaikan baris bertanda merah di bawah. Selama belum lengkap, sebagian "
                  + "layar bisa terlihat kosong — bukan karena rusak, tetapi karena datanya "
                  + "memang belum ada."}
            </p>
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-white">
              <div style={{ width: `${pct}%` }} className={`h-full ${bar}`} />
            </div>
          </div>
        )}
        <EntityCompletionSteps
          entityId={entityId}
          data={data}
          loading={loading}
          canRetry={canManage}
          onUpdated={(r) => (r ? setData(r) : load())}
          testId="readiness-steps"
        />
      </div>
    </div>
  );
}
