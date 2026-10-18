import { useCallback, useEffect, useState } from "react";
import { Award, Loader2, Plus, Power, Save } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import { apiErrorText } from "../../../utils/apiError";
import { can } from "../../../config/roles";
import { invalidateDomainEnums } from "../../../hooks/useDomainEnums";

const EMPTY = { code: "", name: "", rank: "", description: "", max_points: "" };

function GradeRow({ g, perms, onSaved, onError }) {
  const [edit, setEdit] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn) => {
    setBusy(true); onError("");
    try { await fn(); setEdit(null); setReason(""); onSaved(); } catch (e) { onError(apiErrorText(e, "Gagal menyimpan grade.")); } finally { setBusy(false); }
  };
  const save = () => run(() => axios.patch(`${API}/master/grades/${g.code}`, {
    name: edit.name, rank: Number(edit.rank), description: edit.description,
    max_points: edit.max_points === "" || edit.max_points === null ? null : Number(edit.max_points) }));
  const toggle = () => run(() => axios.post(`${API}/master/grades/${g.code}/active`, { active: !g.active, reason }));
  return (
    <tr data-testid={`grade-row-${g.code}`} className={g.active ? "" : "opacity-60"}>
      <td className="px-3 py-2 font-semibold">{g.code}</td>
      <td className="px-3 py-2">{edit ? <input className="input" data-testid={`grade-edit-name-${g.code}`} value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /> : g.name}</td>
      <td className="px-3 py-2 text-right">{edit ? <input className="input w-16" type="number" data-testid={`grade-edit-rank-${g.code}`} value={edit.rank} onChange={(e) => setEdit({ ...edit, rank: e.target.value })} /> : g.rank}</td>
      <td className="px-3 py-2 text-right">{edit ? <input className="input w-20" type="number" data-testid={`grade-edit-points-${g.code}`} value={edit.max_points ?? ""} onChange={(e) => setEdit({ ...edit, max_points: e.target.value })} /> : (g.max_points ?? "—")}</td>
      <td className="px-3 py-2 text-right" data-testid={`grade-usage-${g.code}`}>{g.rolls_using}</td>
      <td className="px-3 py-2"><span data-testid={`grade-status-${g.code}`} className={g.active ? "pill-success" : "pill-muted"}>{g.active ? "Aktif" : (g.historical ? "Historis" : "Nonaktif")}</span></td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap items-center gap-1.5">
          {can(perms, "grade_master", "update") && (edit
            ? <button type="button" disabled={busy} data-testid={`grade-save-${g.code}`} className="primary-button !py-1 text-[11px]" onClick={save}><Save size={12} /> Simpan</button>
            : <button type="button" data-testid={`grade-edit-${g.code}`} className="secondary-button !py-1 text-[11px]" onClick={() => setEdit({ name: g.name, rank: g.rank, description: g.description || "", max_points: g.max_points ?? "" })}>Ubah</button>)}
          {can(perms, "grade_master", "activate") && (
            <>
              <input className="input !py-1 text-[11px] w-40" placeholder="Alasan aktif/nonaktif" data-testid={`grade-reason-${g.code}`} value={reason} onChange={(e) => setReason(e.target.value)} />
              <button type="button" disabled={busy || reason.trim().length < 5} data-testid={`grade-toggle-${g.code}`} className="secondary-button !py-1 text-[11px] disabled:opacity-50" onClick={toggle}>
                <Power size={12} /> {g.active ? "Nonaktifkan" : "Aktifkan"}
              </button>
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

/** L01 LN-012 — Master Grade Mutu: tambah · ubah · aktif/nonaktif (hak terpisah), tanpa hapus fisik. */
export default function GradeMasterView({ currentUser }) {
  const perms = currentUser?.permissions || {};
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try { setRows((await axios.get(`${API}/master/grades`)).data || []); } catch (e) { setErr(apiErrorText(e, "Gagal memuat master grade.")); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const saved = () => { invalidateDomainEnums(); setMsg("Tersimpan — semua form grade memakai daftar terbaru."); load(); };
  const create = async () => {
    setErr(""); setMsg("");
    try {
      await axios.post(`${API}/master/grades`, { ...form, rank: Number(form.rank),
        max_points: form.max_points === "" ? null : Number(form.max_points) });
      setForm(EMPTY); saved();
    } catch (e) { setErr(apiErrorText(e, "Gagal menambah grade.")); }
  };
  return (
    <section className="section-card" data-testid="grade-master-view">
      <div className="section-head"><div className="flex items-center gap-2"><Award size={15} className="text-[#0058CC]" /><h2>Master Grade Mutu</h2></div></div>
      <p className="px-3 pt-2 text-[11.5px] text-[#3C3C43]">Urutan mutu memakai rank (1 = terbaik). Grade nonaktif tidak bisa dipilih di form baru mana pun; roll & dokumen lama tetap terbaca. Batas poin 4-point opsional — kosong = pakai ambang Pengaturan QC.</p>
      {loading ? <div className="p-4"><Loader2 className="animate-spin" size={16} /></div> : (
        <div className="overflow-x-auto p-3">
          <table className="w-full text-[12px]" data-testid="grade-master-table">
            <thead><tr className="text-left text-[#8E8E93]"><th className="px-3 py-1">Kode</th><th className="px-3 py-1">Nama</th><th className="px-3 py-1 text-right">Rank</th><th className="px-3 py-1 text-right">Maks. poin</th><th className="px-3 py-1 text-right">Roll memakai</th><th className="px-3 py-1">Status</th><th className="px-3 py-1">Aksi</th></tr></thead>
            <tbody>{rows.map((g) => <GradeRow key={g.code} g={g} perms={perms} onSaved={saved} onError={setErr} />)}</tbody>
          </table>
        </div>
      )}
      {can(perms, "grade_master", "create") && (
        <div className="flex flex-wrap items-end gap-2 border-t border-[#E5E7EB] p-3 text-[11.5px]" data-testid="grade-create-form">
          <input className="input w-20" placeholder="Kode" maxLength={2} data-testid="grade-new-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} />
          <input className="input w-48" placeholder="Nama, mis. A3 — Baik minus" data-testid="grade-new-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="input w-20" type="number" placeholder="Rank" data-testid="grade-new-rank" value={form.rank} onChange={(e) => setForm({ ...form, rank: e.target.value })} />
          <input className="input w-24" type="number" placeholder="Maks. poin" data-testid="grade-new-points" value={form.max_points} onChange={(e) => setForm({ ...form, max_points: e.target.value })} />
          <button type="button" className="primary-button !py-1.5 text-[12px]" data-testid="grade-new-submit" disabled={!form.code || !form.name || !form.rank} onClick={create}><Plus size={13} /> Tambah Grade</button>
        </div>
      )}
      {msg && <p className="px-3 pb-3 text-[11px] text-[#126E2C]" data-testid="grade-master-msg">{msg}</p>}
      {err && <p className="px-3 pb-3 text-[11px] text-[#C0392B]" data-testid="grade-master-error">{err}</p>}
    </section>
  );
}
