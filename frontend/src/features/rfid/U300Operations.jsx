import { useCallback, useEffect, useRef, useState } from "react";
import axios, { API } from "../../services/apiClient";

const errorText = (e) => { const d = e.response?.data?.detail; return typeof d === "string" ? d : d?.message || e.message; };

export default function U300Operations({ device, isAdmin }) {
  const [data, setData] = useState(null), [error, setError] = useState("");
  const [busy, setBusy] = useState(false), [sources, setSources] = useState([]);
  const [kind, setKind] = useState("shipment"), [direction, setDirection] = useState("out");
  const [selectedSources, setSelectedSources] = useState([]), [notes, setNotes] = useState({});
  const [cursor, setCursor] = useState(null), [previousPages, setPreviousPages] = useState([]);
  const requestSequence = useRef(0);
  const base = `${API}/rfid/v2/ops/devices/${encodeURIComponent(device.id)}`;
  const load = useCallback(async () => {
    const sequence = ++requestSequence.current;
    try { const result = await axios.get(base, { params: { cursor: cursor || undefined, limit: 50 } }); if (sequence === requestSequence.current) { setData(result.data); setError(""); } }
    catch (e) { if (sequence === requestSequence.current) setError(errorText(e)); }
  }, [base, cursor]);
  useEffect(() => { load(); const timer = setInterval(load, 10000); return () => { clearInterval(timer); requestSequence.current++; }; }, [load]);
  useEffect(() => {
    let active = true; setSelectedSources([]); setSources([]);
    axios.get(`${base}/sources`, { params: { source_type: kind, direction } }).then(r => { if (active) setSources(r.data.sources); })
      .catch(e => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, [base, kind, direction]);
  const act = async (fn) => { setBusy(true); setError(""); try { await fn(); await load(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } };
  const gate = data?.config?.logical_gates?.[0];
  const selectSource = (id, checked) => setSelectedSources(current => checked ? (kind === "shipment" ? [...current, id].slice(0, 20) : [id]) : current.filter(value => value !== id));
  const downloadEvidence = async (passage) => {
    const result = await axios.get(`${base}/passages/${encodeURIComponent(passage.local_passage_id)}/evidence`, { responseType: "blob" });
    const url = URL.createObjectURL(result.data), link = document.createElement("a");
    link.href = url; link.download = `u300-evidence-${passage.local_passage_id.replace(/[^a-zA-Z0-9_-]/g, "_")}.json`;
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const upload = async (event) => {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    await act(async () => { if (file.size > 1000000) throw new Error("Profil maksimal 1 MB."); await axios.put(`${base}/config`, JSON.parse(await file.text())); });
  };
  return <section className="mt-3 border rounded-lg p-3 text-sm space-y-3" aria-label={`Operasional U300 ${device.name}`}>
    <div className="flex justify-between"><strong>Integrasi reader U300</strong><button disabled={busy} onClick={load}>Perbarui</button></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <p>Profil: {data?.config_version || "belum diterbitkan"} · Gate: {gate?.logical_gate_id || "—"}</p>
    <p>Antrean reader: {data?.telemetry?.pending_event_count ?? "belum ada laporan"} · Radio: {data?.telemetry?.radio_state || "—"}</p>
    {isAdmin && <label className="block">Unggah profil commissioning JSON <input type="file" accept=".json,application/json" disabled={busy} onChange={upload} /></label>}
    {gate && <>
      <p>Pilih dokumen yang sedang melewati gate. Satu lintasan dapat memuat sampai 20 SJ dari gudang ini. Nomor SJ tetap terpisah; seluruh roll dalam gabungan dokumen harus terbaca. Transfer dan putaway dipilih satu per lintasan.</p>
      <div className="flex flex-wrap gap-2">
        <select aria-label="Jenis dokumen gate" value={kind} onChange={e => setKind(e.target.value)}><option value="shipment">Surat jalan penjualan</option><option value="wh_transfer">Transfer fisik antar gudang</option><option value="putaway">Putaway</option></select>
        <select aria-label="Arah gate" value={direction} onChange={e => setDirection(e.target.value)}><option value="out">Keluar</option><option value="in">Masuk</option></select>
        <button disabled={busy || !selectedSources.length} onClick={() => act(() => axios.post(`${base}/manifest`, { logical_gate_id: gate.logical_gate_id, sources: selectedSources.map(id => ({ source_type: kind, source_id: id })), direction }))}>Gunakan {selectedSources.length || "pilihan"} dokumen</button>
      </div>
      <fieldset className="max-h-48 overflow-y-auto border rounded p-2"><legend>Dokumen aktif yang akan lewat</legend>
        {sources.length === 0 && <p>Belum ada dokumen aktif untuk gudang dan arah ini.</p>}
        {sources.map(s => <label className="block" key={s.id}><input type="checkbox" checked={selectedSources.includes(s.id)} disabled={busy || (kind === "shipment" && selectedSources.length >= 20 && !selectedSources.includes(s.id))} onChange={e => selectSource(s.id, e.target.checked)} /> {s.label}</label>)}
      </fieldset>
      <p>Manifest aktif: {data.bindings?.map(b => `${b.source_ref.display_ref} (${b.roll_ids.length} roll, ${b.direction === "out" ? "keluar" : "masuk"})`).join(", ") || "belum dipilih"}</p>
      <p className="text-xs">Pergantian manifest berlaku untuk lintasan baru. Riwayat dan manifest lintasan yang sudah dimulai tetap disimpan.</p>
    </>}
    <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr><th>Waktu / lintasan</th><th>Hasil</th><th>Cocok / kurang / lebih</th><th>Tindak lanjut</th></tr></thead><tbody>
      {(data?.passages || []).map(p => <tr key={p.local_passage_id} className="border-t align-top"><td className="p-2">{new Date(p.created_at).toLocaleString("id-ID")}<br /><small>{p.local_passage_id}</small></td>
        <td className="p-2">{p.decision?.verdict || "Merekam"}<br /><small>{p.decision?.reason_code || p.state}</small></td>
        <td className="p-2">{p.decision ? `${p.decision.counts.matched} / ${p.decision.counts.missing} / ${p.decision.counts.extra}` : "—"}</td>
        <td className="p-2">{p.decision?.latched && !p.acknowledged ? <><input aria-label={`Catatan pemeriksaan ${p.local_passage_id}`} placeholder="Hasil pemeriksaan" value={notes[p.local_passage_id] || ""} onChange={e => setNotes({ ...notes, [p.local_passage_id]: e.target.value })} /><button disabled={busy || (notes[p.local_passage_id] || "").trim().length < 5} onClick={() => act(() => axios.post(`${API}/rfid/v2/passages/${encodeURIComponent(p.local_passage_id)}/acknowledge`, { device_id: device.id, note: notes[p.local_passage_id] }))}>Catat pemeriksaan dan reset alarm</button></> : p.acknowledged ? "Sudah diperiksa" : "—"}<button className="block mt-2" disabled={busy} onClick={() => act(() => downloadEvidence(p))}>Unduh bukti lintasan</button></td></tr>)}
    </tbody></table></div>
    <div className="flex gap-3"><button disabled={busy || previousPages.length === 0} onClick={() => { setCursor(previousPages[previousPages.length - 1]); setPreviousPages(previousPages.slice(0, -1)); }}>Halaman sebelumnya</button><button disabled={busy || !data?.next_cursor} onClick={() => { setPreviousPages([...previousPages, cursor]); setCursor(data.next_cursor); }}>Riwayat lebih lama</button><button disabled={busy || !cursor} onClick={() => { setCursor(null); setPreviousPages([]); }}>Kembali ke terbaru</button></div>
    <p className="text-xs text-gray-600">Reset alarm tidak mengubah hasil lintasan menjadi hijau dan tidak mengubah stok. Riwayat hanya menampilkan dokumen dalam cakupan akses Anda. Bukti lintasan berisi snapshot data; mengunduhnya tidak menghapus atau mengubah evidence.</p>
  </section>;
}
