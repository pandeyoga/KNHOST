/**
 * PREP-B — rincian sesi pendaftaran awal (berdampingan dengan daftar sesi): status & pembekuan, progres per rak,
 * rekonsiliasi per produk×PT (data lama vs fisik, nilai biaya rata-rata K-OPN-02), pemetaan "produk belum dikenali",
 * dan persetujuan massal (per produk / seluruh sesi) oleh pemegang `inventory.approve_count`.
 */
import { useEffect, useState } from "react";
import { CheckCircle2, Lock, Play, Send, Undo2, XCircle } from "lucide-react";
import ErrorNotice from "../../../components/ErrorNotice";
import ProductSelect from "../../../components/ProductSelect";
import QtyDual from "../../../components/QtyDual";
import { canCurrent } from "../../../config/roles";
import { askConfirm, askReason } from "../../../services/confirmService";
import { apiErrorText } from "../../../utils/apiError";
import { formatCurrency } from "../../../utils/formatters";
import { GROUP_RESULT, STATUS_LABEL, STATUS_TONE, regApi } from "./registrationApi";

export default function RegistrationDetail({ sessionId, onChanged }) {
  const [s, setS] = useState(null);
  const [rec, setRec] = useState(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const approver = canCurrent("inventory", "approve_count");

  const load = async () => {
    try {
      const d = await regApi.get(sessionId);
      setS(d);
      setRec(["pending_approval", "approved", "approved_with_exceptions"].includes(d.status) ? await regApi.reconcile(sessionId) : null);
      setErr("");
    } catch (e) { setErr(apiErrorText(e, "Gagal memuat sesi")); }
  };
  useEffect(() => { load(); }, [sessionId]);   // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (fn, ok) => {
    setBusy(true); setMsg("");
    try { const out = await fn(); setMsg(typeof ok === "function" ? ok(out) : ok); await load(); onChanged?.(); } catch (e) { setErr(apiErrorText(e, "Aksi gagal")); }
    setBusy(false);
  };

  const start = async () => {
    if (await askConfirm({ title: "Mulai & bekukan area?", message: `Gerakan roll dari/ke ${s.freeze?.label || "cakupan"} akan DITOLAK sampai sesi disetujui/ditolak (${s.freeze_mode_label}).`, confirmLabel: "Mulai" }))
      act(() => regApi.start(sessionId), "Sesi berjalan — area dibekukan. Tim gudang bisa mulai mendaftar di HP.");
  };
  const submit = async () => {
    const p = s.progress || {};
    const warn = p.racks_done < p.racks_total ? ` ${p.racks_total - p.racks_done} rak belum ditandai selesai.` : "";
    if (await askConfirm({ title: "Ajukan persetujuan?", message: `${p.lines} roll terdaftar.${warn} Biaya rata-rata dibekukan saat diajukan.`, confirmLabel: "Ajukan" }))
      act(() => regApi.submit(sessionId), "Sesi diajukan — menunggu persetujuan.");
  };
  const approve = async (groupKeys, acceptExceptions = false) => {
    const groups = (rec?.groups || []).filter((g) => !groupKeys.length || groupKeys.includes(g.key));
    const noCost = groups.filter((g) => g.new > 0 && !(g.unit_cost > 0) && !g.result);
    const reason = await askReason({ title: groupKeys.length ? "Setujui produk ini?" : "Setujui seluruh sesi?", confirmLabel: "Setujui",
      message: "Roll baru & tag dibuat, roll lama yang cocok dipakai ulang, roll lama tak terdaftar dihapus, selisih dijurnal per produk." });
    if (!reason) return;
    let zero = "";
    if (noCost.length) {
      zero = await askReason({ title: "Alasan biaya nol", message: `${noCost.map((g) => g.sku).join(", ")}: tidak ada biaya rata-rata acuan.` });
      if (!zero) return;
    }
    act(() => regApi.approve(sessionId, { group_keys: groupKeys, reason, zero_cost_reason: zero, accept_exceptions: acceptExceptions }),
      (out) => (out.complete ? "Sesi tuntas — area terverifikasi pendaftaran & pembekuan dilepas." : "Sebagian diterapkan — lihat pengecualian per produk."));
  };
  const giveBack = async () => {
    const r = await askReason({ title: "Kembalikan ke lapangan?", message: "Sesi kembali Berjalan (pembekuan tetap) untuk diperbaiki." });
    if (r) act(() => regApi.giveBack(sessionId, r), "Sesi dikembalikan ke lapangan.");
  };
  const reject = async () => {
    const r = await askReason({ title: "Tolak sesi?", message: "Stok tidak berubah, semua baris dibatalkan, pembekuan dilepas.", danger: true, confirmLabel: "Tolak" });
    if (r) act(() => regApi.reject(sessionId, r), "Sesi ditolak — pembekuan dilepas.");
  };
  const mapLine = (lid, product) => act(() => regApi.patchLine(sessionId, lid, { product_id: product.id }), `Baris dipetakan ke ${product.sku || product.name}.`);
  const toggleRack = (rackId, done) => act(() => regApi.rack(sessionId, rackId, done), done ? "Rak ditandai selesai." : "Tanda selesai dicabut.");

  if (!s) return <div className="p-4">{err ? <ErrorNotice message={err} onRetry={load} testId="reg-detail-error" /> : <span className="text-[12px] text-[#6B6B73]">Memuat…</span>}</div>;
  const p = s.progress || {};
  const hasException = (rec?.groups || []).some((g) => g.result?.status === "exception");
  return (
    <div className="grid gap-3" data-testid="reg-detail">
      <div className="rounded-md border border-[#EFF0F2] bg-white p-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-[14px] font-bold">{s.number} · {s.name}</h3>
            <p className="text-[12px] text-[#6B6B73]">{s.warehouse_name} · {(s.registration?.node_labels || []).join(", ")} · {s.epc_mode_label}</p>
          </div>
          <span className={`rounded border px-2 py-0.5 text-[11px] font-bold ${STATUS_TONE[s.status] || ""}`} data-testid="reg-detail-status">{STATUS_LABEL[s.status] || s.status_label}</span>
        </div>
        <p className={`mt-2 flex items-center gap-1.5 text-[12px] ${s.freeze?.active ? "text-red-700" : "text-[#6B6B73]"}`} data-testid="reg-freeze">
          <Lock size={12} /> {s.freeze?.active ? `Dibekukan sejak ${String(s.freeze.since || "").slice(0, 16).replace("T", " ")}: ${s.freeze.label} (${s.freeze_mode_label})` : `Tidak membekukan · ${s.freeze_mode_label}`}
        </p>
        {s.registration?.verified_at && <p className="mt-1 text-[12px] font-semibold text-green-700" data-testid="reg-verified">Area terverifikasi pendaftaran {s.registration.verified_at.slice(0, 10)}</p>}
        {msg && <p className="mt-2 rounded border border-green-200 bg-green-50 p-2 text-[12px] text-green-700" data-testid="reg-msg">{msg}</p>}
        {err && <div className="mt-2"><ErrorNotice message={err} onDismiss={() => setErr("")} testId="reg-detail-error" /></div>}
        <div className="mt-2 flex flex-wrap gap-2">
          {s.status === "draft" && <button className="primary-button" disabled={busy} onClick={start} data-testid="reg-start"><Play size={13} /> Mulai & bekukan</button>}
          {s.status === "running" && <button className="primary-button" disabled={busy} onClick={submit} data-testid="reg-submit"><Send size={13} /> Ajukan persetujuan</button>}
          {approver && s.status === "pending_approval" && (
            <>
              <button className="primary-button !border-green-600 !bg-green-600" disabled={busy} onClick={() => approve([])} data-testid="reg-approve-all"><CheckCircle2 size={13} /> Setujui seluruh sesi</button>
              {hasException && <button className="secondary-button" disabled={busy} onClick={() => approve([], true)} data-testid="reg-accept-exc">Terima pengecualian & tuntaskan</button>}
              <button className="secondary-button" disabled={busy} onClick={giveBack} data-testid="reg-return"><Undo2 size={13} /> Kembalikan</button>
            </>
          )}
          {approver && ["draft", "running", "pending_approval"].includes(s.status) && !Object.keys(s.registration?.groups || {}).length &&
            <button className="secondary-button !border-red-300 !text-red-700" disabled={busy} onClick={reject} data-testid="reg-reject"><XCircle size={13} /> Tolak</button>}
        </div>
      </div>

      <div className="rounded-md border border-[#EFF0F2] bg-white p-3" data-testid="reg-progress">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-[13px] font-bold">Progres per rak</h3>
          <span className="text-[11.5px] text-[#6B6B73]">{p.racks_done}/{p.racks_total} rak selesai · {p.lines} roll terdaftar · {p.unmapped} belum dikenali · {p.unverified_length} panjang belum terverifikasi{p.pending_write ? ` · ${p.pending_write} tag belum ditulis` : ""}</span>
        </div>
        <table className="w-full text-[12px]">
          <thead><tr className="text-left text-[#8E8E93]"><th>Rak</th><th>Zona</th><th className="text-right">Bin</th><th className="text-right">Roll terdaftar</th><th className="text-right">Selesai</th></tr></thead>
          <tbody>
            {(p.racks || []).map((r) => (
              <tr key={r.rack_id} className="border-t border-[#F0F1F3]" data-testid={`reg-rack-${r.rack_id}`}>
                <td className="py-1 font-semibold">{r.rack}</td><td>{r.zone}</td><td className="text-right tabular-nums">{r.bins}</td>
                <td className="text-right tabular-nums">{r.lines}</td>
                <td className="text-right">
                  {s.status === "running"
                    ? <input type="checkbox" aria-label={`Rak ${r.rack} selesai`} checked={r.done} disabled={busy} onChange={(e) => toggleRack(r.rack_id, e.target.checked)} data-testid={`reg-rack-done-${r.rack_id}`} />
                    : (r.done ? "✓" : "—")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rec && (
        <div className="rounded-md border border-[#EFF0F2] bg-white p-3" data-testid="reg-reconcile">
          <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-[13px] font-bold">Rekonsiliasi per produk (data lama vs fisik)</h3>
            <span className="text-[11.5px] text-[#6B6B73]">{rec.totals.reused_rolls} dipakai ulang · {rec.totals.new_rolls} roll baru · {rec.totals.missing_rolls} hilang · selisih nilai {formatCurrency(rec.totals.value_net)}</span>
          </div>
          <p className="mb-2 text-[11px] text-[#8E8E93]">{rec.policy}</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-[12px]">
              <thead><tr className="text-left text-[#8E8E93]"><th>Produk · PT</th><th>Data lama</th><th>Terdaftar</th><th className="text-right">Cocok/baru/hilang</th><th className="text-right">Nilai selisih</th><th /></tr></thead>
              <tbody>
                {rec.groups.map((g) => (
                  <tr key={g.key} className="border-t border-[#F0F1F3] align-top" data-testid={`reg-group-${g.product_id}`}>
                    <td className="py-1"><b>{g.sku || "—"}</b> <span className="text-[#6B6B73]">{g.product_name}</span><div className="text-[10.5px] text-[#8E8E93]">{g.owner_entity_id}</div>
                      {(g.notes || []).map((n) => <div key={n} className="text-[10.5px] text-orange-700">{n}</div>)}
                      {(g.result?.exceptions || []).map((x) => <div key={x.line_id || x.roll_id} className="text-[10.5px] text-red-700">{x.epc || x.roll_no}: {x.message}</div>)}
                    </td>
                    <td><QtyDual rolls={g.old_rolls} measure={g.old_qty} unit={g.unit} /></td>
                    <td><QtyDual rolls={g.registered_rolls} measure={g.registered_qty} unit={g.unit} />{g.unverified_length ? <div className="text-[10.5px] text-amber-700">{g.unverified_length} panjang belum terverifikasi</div> : null}</td>
                    <td className="text-right tabular-nums">{g.reuse} / {g.new} / {g.missing_rolls}</td>
                    <td className="text-right tabular-nums">{formatCurrency(g.value_net)}<div className="text-[10.5px] text-[#8E8E93]">biaya rata-rata {formatCurrency(g.unit_cost)} · {g.cost_basis || "—"}</div></td>
                    <td className="text-right">
                      {g.result ? <span className="text-[11px] font-semibold" data-testid={`reg-group-result-${g.product_id}`}>{GROUP_RESULT[g.result.status] || g.result.status}</span>
                        : (approver && s.status === "pending_approval" &&
                          <button className="secondary-button !py-0.5 text-[11px]" disabled={busy} onClick={() => approve([g.key])} data-testid={`reg-approve-${g.product_id}`}>Setujui</button>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rec.unmapped.length > 0 && (
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-2" data-testid="reg-unmapped">
              <h4 className="text-[12px] font-bold text-amber-800">{rec.unmapped.length} baris "produk belum dikenali" — petakan sebelum seluruh sesi disetujui</h4>
              {rec.unmapped.map((u) => (
                <div key={u.id} className="mt-1.5 grid gap-1 sm:grid-cols-[1fr_260px] sm:items-center" data-testid={`reg-unmapped-${u.id}`}>
                  <span className="text-[12px]">{u.bin_code} · <QtyDual measure={u.qty} unit={u.unit} /> · {u.note}{u.has_photo ? " · ada foto" : ""}</span>
                  {approver && s.status === "pending_approval"
                    ? <ProductSelect onSelect={(prod) => mapLine(u.id, prod)} label="Petakan ke produk…" triggerTestId={`reg-map-${u.id}`} />
                    : <span className="text-[11px] text-[#8E8E93]">Dipetakan penyetuju</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
