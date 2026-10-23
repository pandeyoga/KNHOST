import { useEffect, useState } from "react";
import { Award, Check, Loader2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import useDomainEnums from "../../hooks/useDomainEnums";
import KNSelect from "../../components/KNSelect";

/** P04 IMP-11 / DEC-04 — form aturan grade per pelanggan (belum ada data; diisi Admin Sales). */
export default function CustomerGradeRulesCard({ selectedEntity = "all" }) {
  const [customers, setCustomers] = useState([]);
  const [cid, setCid] = useState("");
  const [rule, setRule] = useState({ min_grade: "", preferred_grades: [], accept_bs: false, note: "" });
  const { options, gradeRank } = useDomainEnums();
  const GRADES = options("grade").map((o) => o.value).filter((g) => g !== "BS");
  const meetsMin = (g) => !rule.min_grade || (gradeRank(g) ?? 99) <= (gradeRank(rule.min_grade) ?? 99);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const params = selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity, with_credit: false } : { with_credit: false };
    axios.get(`${API}/customers`, { params }).then((r) => setCustomers(Array.isArray(r.data) ? r.data : r.data?.items || []))
      .catch(() => setCustomers([]));
  }, [selectedEntity]);

  useEffect(() => {
    if (!cid) return;
    setMsg(""); setErr("");
    axios.get(`${API}/customers/${cid}/grade-rules`).then((r) => {
      const x = r.data?.rule;
      setRule({ min_grade: x?.min_grade || "", preferred_grades: x?.preferred_grades || [],
                accept_bs: !!x?.accept_bs, note: x?.note || "" });
      if (!x) setMsg("Belum ada aturan — rekomendasi grade tidak ditampilkan untuk pelanggan ini.");
    }).catch((e) => setErr(apiErrorText(e, "Gagal memuat aturan.")));
  }, [cid]);

  const toggle = (field, g) => setRule((r) => {
    const cur = r[field];
    const next = cur.includes(g) ? cur.filter((x) => x !== g) : [...cur, g];
    const out = { ...r, [field]: next };
    return out;
  });

  const save = async () => {
    setBusy(true); setErr(""); setMsg("");
    try {
      await axios.put(`${API}/customers/${cid}/grade-rules`, rule);
      setMsg("Aturan grade tersimpan — dipakai saat Ganti Roll & rekomendasi grade.");
    } catch (e) { setErr(apiErrorText(e, "Gagal menyimpan aturan.")); }
    finally { setBusy(false); }
  };

  const chip = (field, g) => {
    const on = rule[field].includes(g);
    return (
      <button key={g} type="button" data-testid={`grade-rule-prefer-${g}`} onClick={() => toggle(field, g)}
        className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold transition-colors ${on ? "bg-[#0058CC] text-white" : "bg-[#F2F3F5] text-[#3C3C43] hover:bg-[#E5E7EB]"}`}>{g}</button>
    );
  };

  return (
    <section className="section-card" data-testid="grade-rules-card">
      <div className="section-head"><div className="flex items-center gap-2"><Award size={15} className="text-[#0058CC]" /><h2>Aturan Grade Pelanggan</h2></div></div>
      <div className="grid gap-2.5 p-3 text-[11.5px]">
        <KNSelect data-testid="grade-rule-customer" className="input" value={cid} onValueChange={setCid} placeholder="Pilih pelanggan…" aria-label="Pelanggan"
          options={customers.map((c) => ({ value: c.id, label: c.name }))} />
        {cid && (
          <>
            <div><p className="mb-1 font-semibold">Minimum grade <span className="font-normal text-[#8E8E93]">(grade lebih tinggi boleh; lebih rendah ditolak · kosong = semua non-BS)</span></p>
              <KNSelect data-testid="grade-rule-min" className="input" value={rule.min_grade} aria-label="Grade minimum"
                onValueChange={(v) => { setRule((r) => ({ ...r, min_grade: v, preferred_grades: r.preferred_grades.filter((g) => !v || (gradeRank(g) ?? 99) <= (gradeRank(v) ?? 99)) })); }}
                options={[{ value: "", label: "— tanpa minimum —" }, ...GRADES.map((g) => ({ value: g, label: `${g} ke atas` }))]} /></div>
            <div><p className="mb-1 font-semibold">Prioritas rekomendasi</p>
              <div className="flex flex-wrap gap-1.5">{GRADES.filter(meetsMin).map((g) => chip("preferred_grades", g))}</div></div>
            <label className="flex items-center gap-2"><input type="checkbox" data-testid="grade-rule-accept-bs" checked={rule.accept_bs} onChange={(e) => setRule((r) => ({ ...r, accept_bs: e.target.checked }))} /> Pelanggan menerima BS</label>
            <input data-testid="grade-rule-note" className="input" placeholder="Catatan (opsional)" value={rule.note} onChange={(e) => setRule((r) => ({ ...r, note: e.target.value }))} />
            <button type="button" data-testid="grade-rule-save" disabled={busy} onClick={save} className="primary-button justify-center py-1.5 text-[12px] disabled:opacity-50">
              {busy ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Simpan Aturan
            </button>
          </>
        )}
        {msg && <p className="text-[11px] text-[#126E2C]" data-testid="grade-rule-msg">{msg}</p>}
        {err && <p className="text-[11px] text-[#C0392B]" data-testid="grade-rule-error">{err}</p>}
      </div>
    </section>
  );
}
