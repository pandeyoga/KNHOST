/**
 * PutawayOrdersPanel (FASE R2) — Putaway Order (PA) antar-gedung + BTG.
 * Saran per (pemilik × kategori) berbasis storage_rules → buat PA → kirim →
 * konfirmasi tiba (validasi EPC gate/handheld) → BTG terbit; mismatch = exception.
 * PREP-C (K-GDG-10) — draf otomatis (panel draf), tiba BERTAHAP per trip ("Catat trip"), penutupan sisa
 * (kembali ke transit / exception), status "Tiba Sebagian" & "Dikembalikan".
 */
import { useEffect, useState } from "react";
import { Truck, ClipboardList, CheckCircle2, AlertTriangle, Send, Zap, RotateCcw, PackageCheck } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import axios, { API } from "../../services/apiClient";
import { askReason } from "../../services/confirmService";
import PutawayDraftsPanel from "./PutawayDraftsPanel";
import { ARRIVAL_STATUSES, parseCodes, pendingCount, statusOf, tripMessage } from "./putawayUtils";

const nf = new Intl.NumberFormat("id-ID");
const q = (v) => nf.format(Math.round((v || 0) * 100) / 100);
// G3 D4-PA-03 — total per satuan; meter/kg/yard tidak pernah dijumlah jadi satu angka
const qtyLabel = (o) => {
  const byUnit = o.qty_by_unit && Object.keys(o.qty_by_unit).length ? o.qty_by_unit : null;
  if (byUnit) return Object.entries(byUnit).map(([u, v]) => `${q(v)} ${u}`).join(" + ");
  const units = [...new Set((o.items || []).map((i) => i.unit || "meter"))];
  if (units.length > 1) return units.map((u) => `${q((o.items || []).filter((i) => (i.unit || "meter") === u).reduce((s, i) => s + (i.qty || 0), 0))} ${u}`).join(" + ");
  return `${q(o.total_qty)} ${units[0] || "m"}`;
};
export default function PutawayOrdersPanel({ whId, selectedEntity }) {
  const [suggest, setSuggest] = useState(null);
  const [orders, setOrders] = useState([]);
  const [destByGroup, setDestByGroup] = useState({});
  const [confirmFor, setConfirmFor] = useState(null);
  const [epcInput, setEpcInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const load = async () => {
    setError("");
    try {
      const [s, o] = await Promise.all([
        whId ? axios.get(`${API}/putaway-orders/suggest`, { params: { from_warehouse_id: whId } }) : Promise.resolve({ data: null }),
        axios.get(`${API}/putaway-orders`, { params: whId ? { warehouse_id: whId } : {} }),
      ]);
      setSuggest(s.data); setOrders(o.data.orders || []);
    } catch (e) { setError(e.response?.data?.detail || e.message); }
  };
  useEffect(() => { load(); setConfirmFor(null); }, [whId, selectedEntity]); // eslint-disable-line

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(""), 3500); };
  // UAT 24 Okt (P9.3b) — gudang tanpa RFID: pindai label QR roll di transit → roll siap masuk Putaway Order.
  const [labelInput, setLabelInput] = useState("");
  const [labelRes, setLabelRes] = useState(null);
  const verifyLabels = async () => {
    const codes = labelInput.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);
    if (!codes.length || !whId) return;
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/putaway-orders/verify-labels`, { warehouse_id: whId, codes });
      setLabelRes(r.data); setLabelInput("");
      flash(`${r.data.verified.length} roll terverifikasi lewat label QR.`);
      await load();
    } catch (e) { fail(e, "Gagal memverifikasi label."); } finally { setBusy(false); }
  };
  const fail = (e, f) => {   // detail objek (mis. 409 SAGA_IN_PROGRESS) → kalimatnya, bukan objek mentah
    const d = e.response?.data?.detail;
    setError(typeof d === "string" ? d : (d?.message || f));
  };
  const active = orders.filter((o) => !["draft", "cancelled"].includes(o.status));   // draf tampil di panel draf

  const createPA = async (gi, group) => {
    const to = destByGroup[gi] || group.candidates?.[0]?.warehouse_id;
    if (!to) { setError("Pilih gudang tujuan dulu."); return; }
    setBusy(true); setError("");
    try {
      const r = await axios.post(`${API}/putaway-orders`, {
        from_warehouse_id: whId, to_warehouse_id: to,
        roll_ids: group.rolls.map((x) => x.id),
      });
      flash(`${r.data.pa_number} dibuat → ${r.data.to_warehouse_name} (${r.data.item_count} roll).`);
      await load();
    } catch (e) { fail(e, "Gagal membuat PA"); } finally { setBusy(false); }
  };

  const dispatch = async (id) => {
    setBusy(true);
    try { await axios.post(`${API}/putaway-orders/${id}/dispatch`); flash("PA dikirim — barang menuju gudang tujuan."); await load(); }
    catch (e) { fail(e, "Gagal dispatch"); } finally { setBusy(false); }
  };

  const confirm = async (pa, epcs, manualReason, simulated = false) => {
    setBusy(true);
    try {
      // FIX-3a (K-B3b-09) — simulasi dikirim sebagai penanda; server yang menentukan roll & menandai hasilnya.
      const body = manualReason ? { manual_all: true, reason: manualReason }
        : (simulated ? { simulated: true } : { scanned_epcs: epcs || [] });
      const r = await axios.post(`${API}/putaway-orders/${pa.id}/confirm-arrival`, body);
      const d = r.data;
      flash(d.btg_number
        ? `Tiba tervalidasi — BTG ${d.btg_number} terbit (${d.arrived_count} roll${d.exception_count ? `, ${d.exception_count} EXCEPTION` : ""}).`
        : "Semua item EXCEPTION — cek ulang dengan handheld.");
      setConfirmFor(null); setEpcInput(""); await load();
    } catch (e) { fail(e, "Gagal konfirmasi tiba"); } finally { setBusy(false); }
  };

  // PREP-C — satu trip tiba (handheld): yang terbaca tiba, sisanya TETAP menunggu (bukan exception).
  const trip = async (pa, epcs) => {
    if (!epcs.length) { setError("Tempel/pindai minimal satu EPC atau label roll untuk trip ini."); return; }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/putaway-orders/${pa.id}/arrival-trips`, { epcs, client_trip_id: `ui-${Date.now()}` });
      flash(tripMessage(r.data)); setEpcInput("");
      if (!ARRIVAL_STATUSES.includes(r.data.status)) setConfirmFor(null);
      await load();
    } catch (e) { fail(e, "Gagal mencatat trip tiba"); } finally { setBusy(false); }
  };
  const closeRest = async (pa, action) => {
    const why = await askReason({
      title: action === "return_transit" ? "Kembalikan roll yang belum tiba ke transit?" : "Jadikan roll yang belum tiba EXCEPTION?",
      message: `${pendingCount(pa)} roll belum tiba. PA ditutup sesudah keputusan ini.`,
      confirmLabel: "Tutup PA", reasonMinLength: 10, testId: "pa-close-dialog",   // server: MIN_CLOSE_REASON = 10
    });
    if (!why || !why.trim()) return;
    setBusy(true);
    try {
      await axios.post(`${API}/putaway-orders/${pa.id}/close`, { action, reason: why.trim() });
      flash("PA ditutup."); setConfirmFor(null); await load();
    } catch (e) { fail(e, "Gagal menutup PA"); } finally { setBusy(false); }
  };

  const resolve = async (pa, rollIds, action) => {
    // FIX-3a (K-14) — alasan wajib ≥ 5 huruf, ditegakkan server.
    const why = await askReason({
      title: action === "accept" ? "Terima roll exception (scan ulang OK)?" : "Kembalikan roll exception ke transit?",
      message: "Tulis hasil pengecekan ulang — tercatat di jejak perintah putaway.",
      confirmLabel: action === "accept" ? "Terima" : "Kembalikan", reasonMinLength: 5, testId: "pa-exc-dialog",
    });
    if (!why || !why.trim()) return;
    setBusy(true);
    try {
      await axios.post(`${API}/putaway-orders/${pa.id}/resolve-exception`, { roll_ids: rollIds, action, reason: why.trim() });
      flash(action === "accept" ? "Exception diterima — barang masuk gudang tujuan." : "Barang dikembalikan ke antrean transit.");
      await load();
    } catch (e) { fail(e, "Gagal resolve exception"); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-3" data-testid="pa-panel">
      {error && <div data-testid="pa-error" className="rounded-lg bg-[#FBE9E7] px-3 py-2 text-[12px] font-semibold text-[#C0341D]">{error}</div>}
      {msg && <div data-testid="pa-msg" className="rounded-lg bg-[#E7F7EC] px-3 py-2 text-[12px] font-semibold text-[#1B7E3B]">{msg}</div>}

      {/* P9.3b — verifikasi label QR (tanpa RFID) */}
      {whId && (
        <section className="section-card" data-testid="pa-label-verify">
          <div className="section-head"><h2 className="text-[13px] font-bold">Pindai label QR roll (gudang tanpa RFID)</h2></div>
          <div className="section-body">
            <p className="mb-2 text-[11.5px] text-[#6B6B73]">Pindai label roll yang baru dihitung di transit (nomor roll). Roll yang cocok menjadi <b>siap disimpan ke rak</b> dan muncul di saran di bawah.</p>
            <div className="flex flex-wrap items-center gap-2">
              <input data-testid="pa-label-input" className="field min-w-[260px] flex-1" value={labelInput}
                onChange={(e) => setLabelInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") verifyLabels(); }}
                placeholder="Pindai / ketik nomor roll (pisahkan spasi)" aria-label="Nomor roll dari label QR" />
              <button type="button" className="primary-button" data-testid="pa-label-verify-btn" disabled={busy || !labelInput.trim()} onClick={verifyLabels}>Verifikasi label</button>
            </div>
            {labelRes && (
              <p data-testid="pa-label-result" className="mt-2 text-[11.5px] text-[#4A4A52]">
                Terverifikasi {labelRes.verified.length}
                {labelRes.skipped.length > 0 && <> · dilewati {labelRes.skipped.map((x) => `${x.roll_no} (${x.why})`).join(", ")}</>}
                {labelRes.not_found.length > 0 && <> · tidak ada di gudang ini: {labelRes.not_found.join(", ")}</>}
              </p>
            )}
          </div>
        </section>
      )}

      {/* PREP-C — draf otomatis (K-GDG-10) */}
      <PutawayDraftsPanel drafts={orders.filter((o) => o.status === "draft")} whId={whId} onChanged={load} />

      {/* Saran putaway */}
      <section className="section-card">
        <div className="section-head"><h2 className="text-[13px] font-bold flex items-center gap-1.5">
          <ClipboardList size={15} className="text-[#0058CC]" /> Siap Simpan ke Rak dari {suggest?.warehouse_from?.name || "—"} ({suggest?.ready_count ?? 0} roll)</h2></div>
        <div className="section-body">
          {!suggest || suggest.groups.length === 0 ? (
            <p className="py-6 text-center text-[12px] text-[#8E8E93]" data-testid="pa-suggest-empty">
              Tidak ada roll siap disimpan ke rak (perlu tag RFID terverifikasi atau label QR terpindai, routing SIMPAN).
            </p>
          ) : suggest.groups.map((g, gi) => (
            <div key={gi} data-testid={`pa-group-${gi}`} className="mb-2 rounded-lg border border-[#EFF0F2] p-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <div className="min-w-0 flex-1">
                  <p className="text-[12.5px] font-bold">Kategori: {g.category || "—"} <span className="rounded bg-[#F3E9FA] px-1 text-[10px] font-bold text-[#6B219A]">Grade {g.grade || "A"}</span> <span className="font-normal text-[#6B6B73]">· {g.rolls.length} roll · {q(g.qty)} {g.unit || g.rolls[0]?.unit || "m"}</span></p>
                  <p className="truncate text-[10.5px] text-[#8E8E93]">{g.rolls.slice(0, 4).map((r) => r.roll_no).join(", ")}{g.rolls.length > 4 ? ` +${g.rolls.length - 4} lagi` : ""}</p>
                </div>
                <KNSelect data-testid={`pa-dest-${gi}`} value={destByGroup[gi] || g.candidates?.[0]?.warehouse_id || ""}
                  onValueChange={(v) => setDestByGroup((d) => ({ ...d, [gi]: v }))}
                  options={(g.candidates || []).map((c) => ({
                    value: c.warehouse_id,
                    label: `${c.warehouse_name}${c.same_site ? " · site sama" : ""}`,
                  }))}
                  className="field !py-1 !px-2 w-auto text-[12px]" placeholder="Gudang tujuan" />
                <button data-testid={`pa-create-${gi}`} disabled={busy || !(g.candidates || []).length}
                  onClick={() => createPA(gi, g)}
                  className="flex items-center gap-1 rounded-lg bg-[#0058CC] px-3 py-1.5 text-[12px] font-semibold text-white disabled:opacity-40">
                  <Send size={12} /> Buat PA
                </button>
              </div>
              {(g.candidates || []).length === 0 && (
                <p className="mt-1 text-[11px] font-semibold text-[#C0341D]">Tidak ada gudang tujuan yang aturannya cocok — atur aturannya di Master Gudang.</p>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Daftar PA */}
      <section className="section-card">
        <div className="section-head"><h2 className="text-[13px] font-bold flex items-center gap-1.5">
          <Truck size={15} className="text-[#0058CC]" /> Putaway Orders ({active.length})</h2></div>
        <div className="section-body space-y-2">
          {active.length === 0 && <p className="py-6 text-center text-[12px] text-[#8E8E93]">Belum ada Perintah Simpan ke Rak.</p>}
          {active.map((o) => {
            const [color, label] = statusOf(o);
            const excItems = (o.items || []).filter((i) => i.status === "exception");
            const waiting = pendingCount(o);
            return (
              <div key={o.id} data-testid={`pa-row-${o.id}`} className="rounded-lg border border-[#EFF0F2] p-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] font-bold">{o.pa_number}
                      {o.btg_number && <span className="ml-2 rounded bg-[#E6F6EC] px-1.5 py-0.5 text-[10px] font-bold text-[#1B7F4B]">BTG {o.btg_number}</span>}
                    </p>
                    <p className="text-[11px] text-[#6B6B73]">{o.from_warehouse_name} → <b>{o.to_warehouse_name}</b> · {o.item_count} roll · <span data-testid={`pa-qty-${o.id}`}>{qtyLabel(o)}</span>
                      {(o.arrival_trips || []).length > 0 && <span data-testid={`pa-trips-${o.id}`}> · {o.arrival_trips.length} trip · {waiting} roll menunggu</span>}</p>
                  </div>
                  <span className="rounded px-2 py-0.5 text-[10.5px] font-bold" style={{ color, background: `${color}18` }}>{label}</span>
                  {o.status === "open" && (
                    <button data-testid={`pa-dispatch-${o.id}`} disabled={busy} onClick={() => dispatch(o.id)}
                      className="rounded-lg bg-[#FF9500] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">Kirim</button>
                  )}
                  {ARRIVAL_STATUSES.includes(o.status) && (
                    <button data-testid={`pa-confirm-${o.id}`} disabled={busy}
                      onClick={() => { setConfirmFor(confirmFor === o.id ? null : o.id); setEpcInput(""); }}
                      className="rounded-lg bg-[#1B7F4B] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                      Konfirmasi Tiba
                    </button>
                  )}
                </div>

                {confirmFor === o.id && (
                  <div className="mt-2 rounded-lg border border-[#DCE6F5] bg-[#F7FAFF] p-2.5" data-testid={`pa-confirm-box-${o.id}`}>
                    <p className="text-[11.5px] font-semibold">Validasi gate-in gudang tujuan — tempel EPC/label hasil baca. <b>Catat trip</b> = muatan ini saja (roll lain tetap menunggu); <b>Validasi & tutup</b> = roll yang tidak terbaca menjadi exception.</p>
                    <textarea data-testid={`pa-epc-input-${o.id}`} className="field mt-1 h-14 w-full font-mono text-[11px]"
                      value={epcInput} onChange={(e) => setEpcInput(e.target.value)} placeholder="E2XX-XXXX-…" />
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      <button data-testid={`pa-trip-submit-${o.id}`} disabled={busy} onClick={() => trip(o, parseCodes(epcInput))}
                        className="flex items-center gap-1 rounded-lg bg-[#0058CC] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                        <PackageCheck size={12} /> Catat trip (tiba sebagian)
                      </button>
                      <button data-testid={`pa-confirm-submit-${o.id}`} disabled={busy}
                        onClick={() => confirm(o, parseCodes(epcInput))}
                        className="rounded-lg bg-[#1B7F4B] px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40">
                        <CheckCircle2 size={12} className="mr-1 inline" /> Validasi & tutup (BTG)
                      </button>
                      {o.rfid_simulation && (   /* FIX-3a (FRM-10) — hanya saat mode simulasi RFID PT aktif */
                        <button data-testid={`pa-confirm-sim-${o.id}`} disabled={busy}
                          onClick={() => confirm(o, null, "", true)}
                          className="flex items-center gap-1 rounded-lg border border-[#1B7F4B] px-3 py-1.5 text-[11px] font-semibold text-[#1B7F4B] disabled:opacity-40">
                          <Zap size={12} /> Simulasi Scan Semua
                        </button>
                      )}
                      <button data-testid={`pa-confirm-manual-${o.id}`} disabled={busy}
                        onClick={async () => {
                          const why = await askReason({
                            title: "Konfirmasi MANUAL semua roll tiba tanpa scan?",
                            message: "Butuh izin approve. Roll dianggap tiba tanpa hasil scan EPC.",
                            confirmLabel: "Konfirmasi manual", reasonMinLength: 10,   // server: MIN_OVERRIDE_REASON = 10
                            testId: "pa-confirm-manual-dialog",
                          });
                          if (why && why.trim()) confirm(o, null, why.trim());
                        }}
                        className="rounded-lg border border-[#8C4A00] px-3 py-1.5 text-[11px] font-semibold text-[#8C4A00] disabled:opacity-40">
                        Manual (tanpa scan)
                      </button>
                    </div>
                    {o.status === "partially_received" && waiting > 0 && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5" data-testid={`pa-close-box-${o.id}`}>
                        <span className="text-[11px] text-[#6B6B73]">{waiting} roll belum tiba —</span>
                        <button data-testid={`pa-close-return-${o.id}`} disabled={busy} onClick={() => closeRest(o, "return_transit")}
                          className="rounded border border-[#8C4A00] px-2 py-1 text-[10.5px] font-semibold text-[#8C4A00] disabled:opacity-40">Kembali ke transit & tutup</button>
                        <button data-testid={`pa-close-exception-${o.id}`} disabled={busy} onClick={() => closeRest(o, "exception")}
                          className="rounded border border-[#C0341D] px-2 py-1 text-[10.5px] font-semibold text-[#C0341D] disabled:opacity-40">Jadikan exception & tutup</button>
                      </div>
                    )}
                  </div>
                )}

                {excItems.length > 0 && (
                  <div className="mt-2 rounded-lg bg-[#FFF4E5] p-2.5" data-testid={`pa-exceptions-${o.id}`}>
                    <p className="flex items-center gap-1 text-[11.5px] font-bold text-[#8C4A00]">
                      <AlertTriangle size={13} /> {excItems.length} roll EXCEPTION (EPC tak terbaca saat tiba)</p>
                    {excItems.map((i) => (
                      <div key={i.roll_id} className="mt-1 flex flex-wrap items-center gap-2 text-[11.5px]">
                        <span className="flex-1">{i.roll_no} · {i.sku} <span className="font-mono text-[10px] text-[#8E8E93]">{i.epc}</span></span>
                        <button data-testid={`pa-exc-accept-${i.roll_id}`} disabled={busy}
                          onClick={() => resolve(o, [i.roll_id], "accept")}
                          className="rounded bg-[#1B7F4B] px-2 py-1 text-[10.5px] font-semibold text-white disabled:opacity-40">
                          Scan ulang OK → Terima
                        </button>
                        <button data-testid={`pa-exc-return-${i.roll_id}`} disabled={busy}
                          onClick={() => resolve(o, [i.roll_id], "return_transit")}
                          className="flex items-center gap-1 rounded border border-[#8C4A00] px-2 py-1 text-[10.5px] font-semibold text-[#8C4A00] disabled:opacity-40">
                          <RotateCcw size={11} /> Kembali ke transit
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
