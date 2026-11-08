/**
 * PREP-D2 — rincian satu kasus antrean periksa gate (dibuka di DetailModal dari GateReviewQueue).
 * Bukti per roll: antena, RSSI puncak, waktu pertama/terakhir terbaca, dokumen, alasan (istilah Indonesia).
 * Tindakan (izin approve, alasan wajib, beraudit di server): terima sebagai lewat/tiba · tolak · abaikan ·
 * minta pindai ulang handheld · akui kunci gate · tutup kasus · ulangi transaksi yang gagal.
 */
import { useCallback, useEffect, useState } from "react";
import { Lock, RefreshCw, X } from "lucide-react";
import FormModal from "../../components/FormModal";
import ErrorNotice from "../../components/ErrorNotice";
import axios, { API } from "../../services/apiClient";
import { canCurrent } from "../../config/roles";
import { Pill, fmtTime } from "./rfidShared";
import {
  ACTION_LABEL, CASE_KIND, DIRECTION, ROLL_STATE, TXN_MODE, VERDICT, codesText, errorText, fmtRssi, reasonText,
} from "./u300Labels";

const ACTIONS = {
  accept: { title: "Terima roll sebagai lewat/tiba", label: "Alasan menerima (hasil cek fisik)", submit: "Terima",
    hint: "Transaksi dicatat lewat jalur yang sama dengan gate (tiba Putaway / terima transfer / bukti keluar)." },
  reject: { title: "Tolak roll", label: "Alasan menolak", submit: "Tolak",
    hint: "Roll dianggap TIDAK sah lewat; tanda lewat dari lintasan ini dilepas. Stok tidak berubah." },
  ignore: { title: "Abaikan roll", label: "Alasan mengabaikan", submit: "Abaikan", hint: "Tidak ada perubahan data roll." },
  rescan: { title: "Minta pindai ulang dengan handheld", label: "Catatan untuk petugas gudang", submit: "Kirim permintaan",
    hint: "Petugas gudang mendapat notifikasi; roll selesai otomatis bila handheld melengkapinya." },
  dismiss: { title: "Tutup kasus", label: "Catatan hasil pemeriksaan", submit: "Tutup kasus",
    hint: "Roll yang masih terbuka ditandai diabaikan." },
  latch: { title: "Akui kunci gate", label: "Catatan pemeriksaan fisik & dokumen", submit: "Buka kunci gate",
    hint: "Membuka kunci tidak mengubah hasil lintasan menjadi hijau dan tidak mengubah stok." },
};

function Evidence({ ev }) {
  if (!ev) return <span className="text-[11px] text-[#8E8E93]">tanpa bacaan</span>;
  return (
    <div className="text-[11px] text-[#3C3C43]">
      <div>puncak {fmtRssi(ev.peak_rssi)} · {ev.count}× baca</div>
      <div className="text-[#6B6B73]">{(ev.antennas || []).map((a) => `antena ${a.antenna}: ${fmtRssi(a.peak_rssi)}`).join(" · ")}</div>
      <div className="text-[#6B6B73]">{fmtTime(ev.first_seen)} – {fmtTime(ev.last_seen)}</div>
    </div>
  );
}

export default function GateReviewDetail({ caseId, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState([]);
  const [modal, setModal] = useState(null);
  const [text, setText] = useState("");
  const [modalError, setModalError] = useState("");
  const approver = canCurrent("wms", "approve");
  const url = `${API}/rfid/v2/ops/reviews/${encodeURIComponent(caseId)}`;
  const load = useCallback(async () => {
    try { setData((await axios.get(url)).data); setError(""); } catch (e) { setError(errorText(e)); }
  }, [url]);
  useEffect(() => { load(); }, [load]);
  const open = data?.status === "open";
  const actionable = (data?.rolls || []).filter((r) => ["open", "rescan"].includes(r.state));
  const toggle = (key) => setPicked((p) => (p.includes(key) ? p.filter((k) => k !== key) : [...p, key]));
  const ask = (kind) => { setModal(kind); setText(""); setModalError(""); };
  const submit = async () => {
    setBusy(true); setModalError("");
    try {
      const body = { roll_keys: picked };
      if (modal === "accept") await axios.post(`${url}/rolls/accept`, { ...body, reason: text });
      else if (modal === "reject" || modal === "ignore") await axios.post(`${url}/rolls/reject`, { ...body, reason: text, mode: modal });
      else if (modal === "rescan") await axios.post(`${url}/rolls/rescan`, { ...body, note: text });
      else if (modal === "dismiss") await axios.post(`${url}/dismiss`, { reason: text });
      else if (modal === "latch") await axios.post(`${url}/acknowledge-latch`, { note: text });
      setModal(null); setPicked([]); await load(); onChanged?.();
    } catch (e) { setModalError(errorText(e)); } finally { setBusy(false); }
  };
  const retry = async () => {
    setBusy(true); setError("");
    try { await axios.post(`${url}/retry`, {}); await load(); onChanged?.(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  const v = VERDICT[data?.verdict] || VERDICT.UNKNOWN;
  const docs = (data?.sources || []).map((s) => s.display_ref || "dokumen").join(", ");
  const failed = (data?.rolls || []).some((r) => (r.codes || []).includes("TXN_FAILED") && ["open", "rescan"].includes(r.state));
  const cfg = ACTIONS[modal] || {};
  return (
    <section className="section-card" data-testid="gate-review-detail">
      <div className="section-head flex-wrap">
        <h2>{CASE_KIND[data?.kind] || "Kasus antrean periksa"}{data?.device_name ? ` — ${data.device_name}` : ""}</h2>
        <span className="flex items-center gap-2">
          <Pill color={v.color} testId="gate-review-verdict">{v.short}</Pill>
          <Pill color={open ? "orange" : "green"}>{open ? "Terbuka" : "Selesai"}</Pill>
          <button type="button" className="secondary-button !py-1 text-[12px]" onClick={load} disabled={busy}><RefreshCw size={12} /> Perbarui</button>
          <button type="button" aria-label="Tutup rincian" className="secondary-button !py-1" onClick={onClose}><X size={14} /></button>
        </span>
      </div>
      <div className="section-body space-y-3">
        {error && <ErrorNotice message={error} onRetry={load} />}
        {data && (
          <>
            <p className="text-[12px] text-[#3C3C43]" data-testid="gate-review-meta">
              {fmtTime(data.created_at)} · arah {DIRECTION[data.direction] || "—"} · dokumen {docs || "—"}
              <br /><span className="text-[11px] text-[#6B6B73]">{TXN_MODE[data.txn_mode] || ""}</span>
            </p>
            {data.latch_open && (
              <div className="rounded-lg border border-[#F3C5BD] bg-[#FBE9E7] p-2 text-[12px] text-[#C0341D]" data-testid="gate-review-latch">
                <Lock size={12} className="inline" /> Gate TERKUNCI oleh lintasan merah ini — periksa fisik lalu akui kunci gate.
                {approver && <button type="button" className="primary-button !py-1 ml-2 text-[12px]" data-testid="gate-review-ack"
                  disabled={busy} onClick={() => ask("latch")}>Akui kunci gate</button>}
              </div>
            )}
            {(data.reasons || []).length > 0 && (
              <ul className="space-y-0.5" data-testid="gate-review-reasons">
                {data.reasons.map((r) => (
                  <li key={r.code} className="text-[12px]"><Pill color={r.level === "RED" ? "red" : "orange"}>{r.level === "RED" ? "pelanggaran" : "periksa"}</Pill>{" "}
                    <b>{reasonText(r.code)}</b>{r.message ? ` — ${r.message}` : ""}</li>
                ))}
              </ul>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[12px]" data-testid="gate-review-rolls">
                <thead><tr className="text-[11px] text-[#6B6B73]">
                  <th className="p-2" /><th className="p-2">Roll</th><th className="p-2">Alasan</th><th className="p-2">Bukti bacaan</th>
                  <th className="p-2">Status</th>
                </tr></thead>
                <tbody>
                  {(data.rolls || []).map((r) => {
                    const st = ROLL_STATE[r.state] || ROLL_STATE.open;
                    const can = open && ["open", "rescan"].includes(r.state);
                    return (
                      <tr key={r.key} className="border-t border-[#EFF0F2] align-top" data-testid={`gate-review-roll-${r.key}`}>
                        <td className="p-2">{can && approver && (
                          <input type="checkbox" aria-label={`Pilih roll ${r.roll_no || r.epc || ""}`} checked={picked.includes(r.key)}
                            onChange={() => toggle(r.key)} />)}</td>
                        <td className="p-2"><b>{r.roll_no || "Tag tak dikenal"}</b>
                          <div className="text-[10px] text-[#6B6B73]">{r.epc || "—"}</div>
                          <div className="text-[10px] text-[#6B6B73]">{r.source_ref?.display_ref || "tanpa dokumen"}</div></td>
                        <td className="p-2">{codesText(r.codes)}
                          {(r.messages || []).slice(0, 2).map((m) => <div key={m} className="text-[11px] text-[#6B6B73]">{m}</div>)}</td>
                        <td className="p-2"><Evidence ev={r.evidence} /></td>
                        <td className="p-2"><Pill color={st.color}>{st.label}</Pill>
                          {(r.actions || []).slice(-2).map((a) => (
                            <div key={`${a.type}-${a.at}`} className="text-[10px] text-[#6B6B73]">
                              {ACTION_LABEL[a.type] || "Tindakan"} · {a.by || "Sistem"} · {fmtTime(a.at)}{a.reason ? ` — ${a.reason}` : ""}</div>))}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {open && approver && (
              <div className="flex flex-wrap gap-2" data-testid="gate-review-actions">
                <button type="button" className="primary-button !py-1 text-[12px]" data-testid="gate-review-accept"
                  disabled={busy || !picked.length} onClick={() => ask("accept")}>Terima sebagai lewat/tiba</button>
                <button type="button" className="secondary-button !py-1 text-[12px]" data-testid="gate-review-reject"
                  disabled={busy || !picked.length} onClick={() => ask("reject")}>Tolak</button>
                <button type="button" className="secondary-button !py-1 text-[12px]" disabled={busy || !picked.length}
                  onClick={() => ask("ignore")}>Abaikan</button>
                <button type="button" className="secondary-button !py-1 text-[12px]" data-testid="gate-review-rescan"
                  disabled={busy || !picked.length} onClick={() => ask("rescan")}>Minta pindai ulang handheld</button>
                {failed && <button type="button" className="secondary-button !py-1 text-[12px]" disabled={busy} onClick={retry}>Ulangi transaksi</button>}
                <button type="button" className="secondary-button !py-1 text-[12px]" data-testid="gate-review-dismiss"
                  disabled={busy || data.latch_open} onClick={() => ask("dismiss")}>Tutup kasus</button>
              </div>
            )}
            {open && !approver && actionable.length > 0 && (
              <p className="text-[11px] text-[#6B6B73]">Tindak lanjut antrean butuh izin persetujuan gudang (Admin Gudang / Manajer).</p>
            )}
          </>
        )}
      </div>
      <FormModal open={!!modal} onClose={() => setModal(null)} title={cfg.title || ""} subtitle={cfg.hint || ""}
        onSubmit={submit} submitLabel={cfg.submit || "Simpan"} busy={busy} error={modalError}
        submitDisabled={text.trim().length < 5} testId="gate-review-form" size="sm">
        <label className="block text-[12px] text-[#6B6B73]">{cfg.label}
          <textarea className="field mt-1 w-full" rows={3} value={text} data-testid="gate-review-reason"
            onChange={(e) => setText(e.target.value)} placeholder="Minimal 5 huruf" />
        </label>
        {["accept", "reject", "ignore", "rescan"].includes(modal) && (
          <p className="mt-1 text-[11px] text-[#6B6B73]">{picked.length} roll dipilih.</p>
        )}
      </FormModal>
    </section>
  );
}
