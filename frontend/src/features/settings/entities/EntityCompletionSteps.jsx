/**
 * EntityCompletionSteps (KP-T2 · KP-10, KP-24) — "Lengkapi PT": butir kesiapan PT sebagai langkah bernomor.
 *
 * SATU sumber tautan dan teks untuk tiga tempat: langkah ke-5 wizard Tambah Badan Usaha, bagian "Kesiapan" di detail
 * PT, dan tab Kesiapan (`EntityReadinessPanel`). Isinya dihitung server (`GET /api/entities/{id}/readiness`, 16 butir);
 * komponen ini tidak mengarang status sendiri.
 *
 * Tombol **Lengkapi** lebih dulu mengganti PT aktif ke PT ini (fungsi yang sama dengan pemilih PT di kepala layar —
 * `EntityScopeContext.pickEntity` = `App.onSelectEntity`), lalu membuka layar tujuan lewat jalur navigasi baku
 * (`AppNavContext.go`) dengan preset tab bila ada. Baris "Penyiapan awal" yang belum siap bertombol
 * **Ulangi penyiapan** (`POST …/provisioning/retry`, izin ubah PT — ditentukan pemanggil lewat `canRetry`).
 *
 * Komponen terkendali: data kesiapan dari pemanggil (`data`), hasil ulang penyiapan dikembalikan lewat `onUpdated`.
 * `WizardCompletionStep` = isi langkah ke-5 wizard Tambah Badan Usaha untuk PT yang baru tersimpan.
 */
import { useEffect, useState } from "react";
import { CheckCircle2, XCircle, ExternalLink, ListChecks, Loader2, RotateCcw } from "lucide-react";

import { useAppNav } from "../../../context/AppNavContext";
import { useEntityScope } from "../../../context/EntityScopeContext";
import { errText, getReadiness, retryProvisioning } from "./entityApi";

/** KP-T9 — layar Badan Usaha & Akses dipecah menjadi tab hub; id lamanya (`entities-access` + `tab`, dari data lama)
 *  dipetakan ke tab barunya. */
const OLD_PART_VIEW = { entities: "settings-pt-profile", readiness: "settings-pt-readiness", accounts: "settings-accounts",
  roles: "permission-matrix", "role-reality": "settings-role-check" };

/** Layar tujuan tombol Lengkapi. */
export function completionView(item) {
  if (item?.view === "entities-access") return OLD_PART_VIEW[item.tab || "entities"] || "settings-pt-profile";
  return item?.view || "";
}

/** Preset tujuan: Profil PT membuka detail PT ini; tab pecahan lain tanpa preset; layar lain hanya tab. */
export function completionPreset(item, entityId) {
  const view = completionView(item);
  if (view === "settings-pt-profile") return { entity_id: entityId };
  if (Object.values(OLD_PART_VIEW).includes(view)) return null;
  return item?.tab ? { tab: item.tab } : null;
}

export default function EntityCompletionSteps({ entityId, data, loading = false, error = "", canRetry = false,
  onUpdated, onNavigated, testId = "entity-completion" }) {
  const { go } = useAppNav();
  const { selectedEntity, pickEntity } = useEntityScope();
  const [busy, setBusy] = useState(false);
  const [retryError, setRetryError] = useState("");
  const items = data?.items || [];

  const open = (item) => {
    if (!item?.view) return;
    if (entityId && selectedEntity !== entityId) pickEntity(entityId);   // ganti PT aktif dulu
    const preset = completionPreset(item, entityId);
    go(completionView(item), preset ? { preset } : {});
    onNavigated?.(item);
  };

  const retry = async () => {
    setBusy(true);
    setRetryError("");
    try {
      const res = await retryProvisioning(entityId);
      const failed = Object.values(res?.errors || {});
      if (failed.length) setRetryError(failed.join(" "));
      onUpdated?.(res?.readiness || null, res);
    } catch (e) {
      setRetryError(errText(e, "Gagal mengulang penyiapan PT."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid={testId}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <ListChecks size={15} className="text-kn-special-text" />
        <h3 className="text-fs-14 font-bold text-kn-text" data-testid={`${testId}-title`}>Lengkapi PT</h3>
        {data && (
          <span className="ml-auto text-fs-12 font-bold tabular-nums text-kn-text-2" data-testid={`${testId}-summary`}>
            {data.ready ?? 0} dari {data.total ?? items.length} hal sudah siap
          </span>
        )}
      </div>

      {error && <p className="mb-2 text-fs-12 text-kn-danger-text" data-testid={`${testId}-error`}>{error}</p>}
      {retryError && (
        <p className="mb-2 text-fs-12 text-kn-danger-text" data-testid={`${testId}-retry-error`}>{retryError}</p>
      )}

      {loading && !data ? (
        <div className="grid gap-2" data-testid={`${testId}-loading`}>
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-10 animate-pulse rounded bg-kn-neutral-soft" />)}
        </div>
      ) : !data ? (
        <p className="py-6 text-center text-fs-13 text-kn-text-2" data-testid={`${testId}-empty`}>
          Pilih PT untuk melihat daftar kesiapannya.
        </p>
      ) : (
        <ol className="grid gap-1.5" data-testid={`${testId}-list`}>
          {items.map((it, idx) => (
            <li key={it.key} data-testid={`${testId}-item-${it.key}`} data-ready={it.ready ? "ya" : "tidak"}
                className={`flex flex-wrap items-start gap-2 rounded-md border px-3 py-2 ${
                  it.ready ? "border-kn-divider bg-white" : "border-kn-danger-soft bg-kn-danger-soft"}`}>
              <span className="w-6 shrink-0 text-right text-fs-12 font-bold tabular-nums text-kn-text-2">{idx + 1}.</span>
              {it.ready
                ? <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-kn-success-text" aria-label="Siap" />
                : <XCircle size={14} className="mt-0.5 shrink-0 text-kn-danger-text" aria-label="Belum siap" />}
              <div className="min-w-0 flex-1">
                <p className="text-fs-13 font-bold text-kn-text">{it.label}</p>
                <p className="text-fs-12 text-kn-text" data-testid={`${testId}-detail-${it.key}`}>{it.detail}</p>
                {!it.ready && it.how_to && (
                  <p className="text-fs-12 text-kn-text-2" data-testid={`${testId}-howto-${it.key}`}>{it.how_to}</p>
                )}
              </div>
              {it.key === "provisioning" && !it.ready && canRetry && (
                <button type="button" className="secondary-button" data-testid={`${testId}-retry`}
                        disabled={busy} onClick={retry}>
                  {busy ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />} Ulangi penyiapan
                </button>
              )}
              {it.view && (
                <button type="button" className="link-button" data-testid={`${testId}-goto-${it.key}`}
                        onClick={() => open(it)}>
                  Lengkapi <ExternalLink size={12} />
                </button>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}


/** KP-T2 — langkah ke-5 wizard: kesiapan PT baru (dari jawaban simpan, atau dimuat bila tidak ikut). */
export function WizardCompletionStep({ created, canManage = false }) {
  const [readiness, setReadiness] = useState(created?.readiness || null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (readiness || !created?.id) return;
    getReadiness(created.id).then(setReadiness).catch((e) => setError(errText(e, "Gagal memuat daftar kesiapan.")));
  }, [created?.id]);   // sekali per PT baru

  return (
    <div className="grid gap-2.5" data-testid="entity-wizard-panel-5">
      <div className="notice-bar success" data-testid="entity-wizard-saved">
        <span className="text-fs-12">
          “{created?.legal_name || created?.name || created?.short_name}” tersimpan. Nomor dokumennya berawalan{" "}
          {created?.provisioning?.number_preview || created?.doc_prefix}.
        </span>
      </div>
      <EntityCompletionSteps entityId={created?.id} data={readiness} loading={!readiness && !error} error={error}
        canRetry={canManage} onUpdated={(r) => { if (r) setReadiness(r); }} testId="entity-wizard-completion" />
      <p className="text-fs-12 text-kn-text-2" data-testid="entity-wizard-later">
        Langkah ini bisa dilanjutkan kapan saja dari tab Kesiapan.
      </p>
    </div>
  );
}
