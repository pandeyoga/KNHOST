/**
 * PREP-B — layar HP "Daftar Awal" (Pindai › Daftar Awal): pendaftaran ulang roll fisik di lapangan, alur satu tangan
 *   EPC (pindai/tempel, banyak kode = antrean) → produk (pindai label supplier / pilih) → panjang → Simpan & lanjut.
 * Bin aktif diingat per sesi; produk & bin tetap terisi untuk roll berikutnya (rak biasanya berisi produk sama).
 * Mode EPC sistem (K-OPN-05): EPC dibuat server saat simpan → tulis ke tag → "Tag sudah ditulis".
 * Produk belum dikenali: simpan dengan keterangan (+ foto) — dipetakan penyetuju sebelum disetujui.
 */
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, Trash2 } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import ProductSelect from "../../components/ProductSelect";
import QtyDual from "../../components/QtyDual";
import useUomConversions from "../../hooks/useUomConversions";
import { apiErrorText } from "../../utils/apiError";
import { uomSelectOptions } from "../../utils/uomCatalog";
import { canonicalEpc, recalledBin, regApi, rememberBin, splitCodes } from "../inventory/registration/registrationApi";

const BIG = "w-full rounded-xl border border-[#E5E5EA] bg-white p-3 text-[16px]";

export default function MobileRegistration() {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const [sid, setSid] = useState("");
  const load = () => regApi.list({ status: "running" }).then((r) => { setRows(r); setErr(""); if (r.length === 1) setSid(r[0].id); })
    .catch((e) => { setErr(apiErrorText(e, "Gagal memuat sesi pendaftaran")); setRows([]); });
  useEffect(() => { load(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <div className="p-3"><ErrorNotice message={err} onRetry={load} testId="mreg-error" /></div>;
  if (rows === null) return <div className="p-6 text-center text-sm"><Loader2 className="inline animate-spin" size={16} /> Memuat…</div>;
  if (!rows.length) {
    return <div className="p-8 text-center text-sm text-[#6E6E73]" data-testid="mreg-empty">Belum ada sesi pendaftaran awal yang berjalan. Admin gudang membuat & memulai sesi di desktop (Stock Opname › Pendaftaran awal).</div>;
  }
  const session = rows.find((r) => r.id === sid);
  return (
    <div className="space-y-2 p-3" data-testid="mreg">
      {rows.length > 1 && (
        <KNSelect data-testid="mreg-session" className={BIG} value={sid} placeholder="Pilih sesi pendaftaran" onValueChange={setSid}
          options={rows.map((r) => ({ value: r.id, label: `${r.number || r.name} · ${r.warehouse_name}` }))} />
      )}
      {session && <FieldForm key={session.id} session={session} />}
    </div>
  );
}

function FieldForm({ session }) {
  const sid = session.id;
  const systemEpc = session.registration?.epc_mode === "system";
  useUomConversions();
  const epcRef = useRef(null);
  const [bins, setBins] = useState([]);
  const [bin, setBin] = useState(recalledBin(sid));
  const [epcText, setEpcText] = useState("");
  const [queue, setQueue] = useState([]);
  const [product, setProduct] = useState(null);
  const [label, setLabel] = useState("");
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState("");
  const [fromLabel, setFromLabel] = useState(false);
  const [more, setMore] = useState({ lot: "", dye_lot: "", grade: "", old_roll_no: "" });
  const [unrec, setUnrec] = useState(false);
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState(null);
  const [recent, setRecent] = useState([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    regApi.bins(sid).then(setBins).catch((e) => setErr(apiErrorText(e, "Gagal memuat bin cakupan")));
    regApi.lines(sid, { limit: 8 }).then(setRecent).catch(() => {});
  }, [sid]);
  const curBin = bins.find((b) => b.id === bin);
  const pickBin = (v) => { setBin(v); rememberBin(sid, v); };

  const takeEpcs = async (text) => {
    const codes = splitCodes(text);
    if (!codes.length) return;
    setErr("");
    const bad = codes.filter((c) => !canonicalEpc(c));
    try {
      const res = await regApi.epcCheck(sid, codes.map(canonicalEpc).filter(Boolean));
      const ok = res.filter((r) => r.ok).map((r) => r.epc);
      setQueue((q) => [...q, ...ok.filter((e) => !q.includes(e))]);
      const rejected = res.filter((r) => !r.ok).map((r) => r.message);
      if (bad.length) rejected.unshift(`${bad.length} kode bukan EPC (24 hex): ${bad.slice(0, 3).join(", ")}`);
      if (rejected.length) setErr(rejected.join(" · "));
      const old = res.find((r) => r.ok && r.matched_roll);
      if (old) setMsg(old.message);
    } catch (e) { setErr(apiErrorText(e, "Gagal memeriksa EPC")); }
    setEpcText("");
  };

  const decode = async () => {
    if (!label.trim()) return;
    try {
      const d = await regApi.labelDecode(sid, label.trim());
      if (d.product) { setProduct(d.product); setUnit(d.length_unit || d.product.base_unit); setUnrec(false); }
      if (d.length) { setQty(String(d.length)); setFromLabel(true); }
      setMore((m) => ({ ...m, lot: d.lot || m.lot, old_roll_no: d.old_roll_no || m.old_roll_no }));
      setMsg(d.redirected_from ? `Produk ${d.redirected_from.sku} sudah digantikan → ${d.product?.sku}.` : (d.message || "Label terbaca."));
      setErr("");
    } catch (e) { setErr(apiErrorText(e, "Label tidak terbaca")); }
  };

  const reset = () => {
    setQueue((q) => q.slice(1)); setQty(""); setFromLabel(false); setLabel(""); setNote(""); setPhoto(null);
    setMore((m) => ({ ...m, old_roll_no: "" }));
    setTimeout(() => epcRef.current?.focus(), 30);
  };

  const save = async () => {
    setBusy(true); setErr(""); setMsg("");
    const body = { bin_id: bin, qty: qty === "" ? null : Number(String(qty).replace(",", ".")), unit: unit || product?.base_unit,
      length_from_label: fromLabel, ...more, grade: more.grade || null,
      ...(systemEpc ? {} : { epc: queue[0] || "" }),
      ...(unrec ? { unrecognized: true, note } : { product_id: product?.id }) };
    try {
      const line = await regApi.addLine(sid, body);
      if (unrec && photo) await regApi.photo(sid, line.id, photo);
      setRecent((r) => [line, ...r].slice(0, 8));
      const where = line.matched_roll_no ? ` · roll lama ${line.matched_roll_no} dipakai ulang` : "";
      setMsg(systemEpc ? `Tersimpan. Tulis EPC ${line.epc_display} ke tag, lalu tekan "Tag sudah ditulis".` : `Tersimpan${where}.`);
      reset();
    } catch (e) { setErr(apiErrorText(e, "Gagal menyimpan baris")); }
    setBusy(false);
  };

  const written = async (line) => {
    try { await regApi.markWritten(sid, [line.id]); setRecent((r) => r.map((x) => (x.id === line.id ? { ...x, tag_state: "written" } : x))); }
    catch (e) { setErr(apiErrorText(e, "Gagal menandai tag")); }
  };
  const remove = async (line) => {
    try { await regApi.voidLine(sid, line.id); setRecent((r) => r.filter((x) => x.id !== line.id)); setMsg("Baris dibatalkan."); }
    catch (e) { setErr(apiErrorText(e, "Gagal membatalkan baris")); }
  };
  const rackDone = async () => {
    try { const p = await regApi.rack(sid, curBin.rack_id, true); setMsg(`Rak ${curBin.rack} ditandai selesai (${p.racks_done}/${p.racks_total}).`); }
    catch (e) { setErr(apiErrorText(e, "Gagal menandai rak")); }
  };

  const unitOpts = uomSelectOptions({ dimensions: ["length", "weight"], extra: [product?.base_unit, unit].filter(Boolean) });
  const ready = bin && (systemEpc || queue.length) && (unrec ? note.trim().length >= 3 : product && Number(String(qty).replace(",", ".")) > 0);
  return (
    <div className="space-y-2" data-testid="mreg-form">
      <div className="m-card space-y-2 p-3">
        <div className="flex items-baseline justify-between"><b className="text-[14px]">{session.number} · {session.warehouse_name}</b>
          <span className="text-xs text-red-700">Area beku</span></div>
        <KNSelect data-testid="mreg-bin" className={BIG} value={bin} placeholder="Bin aktif (pindai/pilih)" onValueChange={pickBin}
          options={bins.map((b) => ({ value: b.id, label: `${b.code} · ${b.zone} › ${b.rack}` }))} />
        {curBin && <button type="button" className="secondary-button w-full py-2 text-[13px]" onClick={rackDone} data-testid="mreg-rack-done">Rak {curBin.rack} selesai</button>}
      </div>

      <div className="m-card space-y-2 p-3">
        {!systemEpc && (
          <>
            <textarea ref={epcRef} rows={1} className={BIG} placeholder="Pindai / tempel EPC tag (boleh banyak)" value={epcText} autoFocus
              aria-label="EPC tag" data-testid="mreg-epc" onChange={(e) => setEpcText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); takeEpcs(epcText); } }} onBlur={() => takeEpcs(epcText)} />
            <div className="text-xs text-[#3C3C43]" data-testid="mreg-queue">
              {queue.length ? <>EPC aktif: <b className="tabular-nums">{queue[0]}</b>{queue.length > 1 ? ` · ${queue.length - 1} antre` : ""}</> : "Belum ada EPC — pindai tag yang ditempel."}
            </div>
          </>
        )}
        {systemEpc && <div className="text-xs text-[#3C3C43]" data-testid="mreg-system-epc">EPC dibuat sistem saat disimpan — tulis ke tag sebelum ditempel.</div>}
        <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={unrec} onChange={(e) => setUnrec(e.target.checked)} data-testid="mreg-unrec" /> Produk belum dikenali</label>
        {unrec ? (
          <>
            <input className={BIG} placeholder="Keterangan (warna/motif/kode di kain)" value={note} onChange={(e) => setNote(e.target.value)} data-testid="mreg-note" />
            <input type="file" accept="image/*" capture="environment" className="text-[13px]" onChange={(e) => setPhoto(e.target.files?.[0] || null)} data-testid="mreg-photo" />
          </>
        ) : (
          <>
            <input className={BIG} placeholder="Pindai label supplier (opsional)" value={label} onChange={(e) => setLabel(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); decode(); } }} data-testid="mreg-label" />
            <ProductSelect value={product?.id || ""} valueName={product ? `${product.sku} — ${product.name}` : ""} triggerTestId="mreg-product"
              onSelect={(p) => { setProduct(p); setUnit(p.base_unit || ""); }} />
          </>
        )}
        <div className="grid grid-cols-[1fr_120px] gap-2">
          <input inputMode="decimal" className={BIG} placeholder="Panjang" value={qty} onChange={(e) => { setQty(e.target.value); setFromLabel(false); }} data-testid="mreg-qty" />
          <KNSelect data-testid="mreg-unit" className={BIG} value={unit || product?.base_unit || ""} placeholder="Satuan" onValueChange={setUnit} options={unitOpts} />
        </div>
        <div className="text-xs" data-testid="mreg-length-state">{fromLabel ? "Panjang dari label (terverifikasi)." : "Panjang belum terverifikasi — diukur saat diambil/dipotong."}</div>
        <details className="text-[13px]">
          <summary>Lot, grade, nomor roll lama</summary>
          <div className="mt-2 grid gap-2">
            {[["lot", "Lot"], ["dye_lot", "Dye lot"], ["grade", "Grade (A/B/…)"], ["old_roll_no", "Nomor roll lama (label lama)"]].map(([k, ph]) => (
              <input key={k} className={BIG} placeholder={ph} value={more[k]} onChange={(e) => setMore({ ...more, [k]: e.target.value })} data-testid={`mreg-${k}`} />
            ))}
          </div>
        </details>
        {err && <ErrorNotice message={err} onDismiss={() => setErr("")} testId="mreg-save-error" />}
        {msg && <div className="rounded-lg bg-[#E6F6EC] p-2 text-xs" data-testid="mreg-msg">{msg}</div>}
        <button type="button" className="primary-button w-full py-3 text-[16px]" disabled={!ready || busy} onClick={save} data-testid="mreg-save">
          {busy ? <Loader2 className="inline animate-spin" size={16} /> : <CheckCircle2 size={16} />} Simpan & lanjut
        </button>
      </div>

      <div className="space-y-1" data-testid="mreg-recent">
        {recent.map((l) => (
          <div key={l.id} className="m-card flex items-center justify-between gap-2 p-2 text-xs" data-testid={`mreg-line-${l.id}`}>
            <div className="min-w-0"><b className="tabular-nums">{l.epc_display}</b> · {l.bin_code}
              <div className="truncate text-[#6E6E73]">{l.sku || "Belum dikenali"} · <QtyDual measure={l.qty ?? l.qty_input} unit={l.unit || l.unit_input} />{l.length_verified ? "" : " · belum terverifikasi"}</div></div>
            {l.tag_state === "pending_write" && <button type="button" className="secondary-button shrink-0 px-2 py-1" onClick={() => written(l)} data-testid={`mreg-written-${l.id}`}>Tag sudah ditulis</button>}
            {l.status === "draft" && <button type="button" aria-label="Batalkan baris" className="shrink-0 p-1 text-red-600" onClick={() => remove(l)} data-testid={`mreg-void-${l.id}`}><Trash2 size={14} /></button>}
          </div>
        ))}
      </div>
    </div>
  );
}
