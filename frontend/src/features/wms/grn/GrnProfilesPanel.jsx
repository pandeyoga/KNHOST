import { useEffect, useState } from "react";
import { GraduationCap, Plus, X } from "lucide-react";
import { KNSelect } from "../../../components/KNSelect";
import { ErrorBox, inputCls } from "./GrnBits";
import { errText, grnApi } from "./grnApi";
import { LOCALE_LABEL } from "./GrnOcrBits";

const LOCALE_OPTIONS = [{ value: "unknown", label: "Otomatis (belajar dari SJ)" }, { value: "id", label: "Indonesia — 1.250,00" }, { value: "en", label: "Inggris — 1,250.00" }];

function LearnedBox({ p, onPatch }) {
  const [notes, setNotes] = useState(p.format_notes || "");
  const id = p.partner_id;
  return (
    <div data-testid={`grn-profile-learned-${id}`} className="space-y-1.5 rounded-lg border border-[#D6EFEA] bg-[#F4FBF9] p-2">
      <p className="flex items-center gap-1 font-semibold text-[#0F766E]"><GraduationCap size={12} /> Petunjuk untuk AI saat membaca SJ mitra ini</p>
      <textarea data-testid={`grn-profile-notes-${id}`} rows={2} className={`${inputCls} !text-[11px]`} value={notes} onChange={(e) => setNotes(e.target.value)}
        placeholder='Mis. "Nomor PO ditulis dalam kurung di kolom keterangan. Qty kirim di kolom A/Pjg (yard), bukan Asal Greige."' />
      <div className="flex justify-end"><button data-testid={`grn-profile-notes-save-${id}`} disabled={notes === (p.format_notes || "")} className="font-semibold text-[#0058CC] disabled:opacity-40" onClick={() => onPatch(id, { format_notes: notes })}>Simpan catatan</button></div>
      {(p.corrections || []).length ? (
        <ul className="space-y-0.5 text-[10.5px]" data-testid={`grn-profile-corrections-${id}`}>
          {p.corrections.map((c, i) => <li key={i}>{c.field}: <span className="font-mono text-[#B4231F] line-through">{c.ocr}</span> → <span className="font-mono font-semibold">{c.final}</span> <span className="text-[#8E8E93]">({c.grn_number})</span></li>)}
          <li><button data-testid={`grn-profile-corrections-clear-${id}`} className="text-[10px] text-[#B4231F]" onClick={() => onPatch(id, { clear_corrections: true })}>Lupakan semua koreksi</button></li>
        </ul>
      ) : <p className="text-[10.5px] text-[#8E8E93]">Belum ada koreksi — dipelajari saat kedatangan ditutup atau dijadikan sampel uji.</p>}
    </div>
  );
}

function ProfileCard({ p, onPatch }) {
  const [alias, setAlias] = useState("");
  const id = p.partner_id;
  return (
    <div data-testid={`grn-profile-${id}`} className="min-w-0 space-y-2 rounded-xl border border-[#EFF0F2] bg-white p-3 text-[11px]">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[12.5px] font-bold">{p.partner_name || id}</p>
          <p className="text-[10.5px] text-[#6B6B73]">{p.partner_type === "makloon" ? "Makloon" : "Supplier"} · {p.confirmed_count} SJ terkonfirmasi · terakhir {p.last_grn_number || "-"}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold uppercase text-[#6B6B73]">Akurasi baca</p>
          <p data-testid={`grn-profile-accuracy-${id}`} className="font-mono text-[15px] font-bold">{p.ocr_accuracy_pct == null ? "—" : `${p.ocr_accuracy_pct}%`}</p>
          <p className="text-[9.5px] text-[#8E8E93]">{p.ocr_lines_corrected}/{p.ocr_lines_total} baris dikoreksi</p>
        </div>
      </div>
      <div className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[140px_minmax(0,1fr)]">
        <span className="font-semibold">Format angka</span>
        <div>
          <KNSelect data-testid={`grn-profile-locale-${id}`} value={p.locale_locked ? p.number_locale : "unknown"} onValueChange={(v) => onPatch(id, { number_locale: v })} options={LOCALE_OPTIONS} searchable={false} />
          <p data-testid={`grn-profile-active-locale-${id}`} className="mt-0.5 text-[10px] text-[#6B6B73]">
            Dipakai sekarang: <b>{LOCALE_LABEL[p.active_locale]}</b>{p.locale_locked ? " (dikunci admin)" : ` · bukti: Indonesia ${p.locale_votes.id} · Inggris ${p.locale_votes.en}${p.confirmed_count < 3 ? " · aktif otomatis setelah 3 SJ" : ""}`}
          </p>
        </div>
        <span className="font-semibold">Nama lain di SJ</span>
        <div className="flex flex-wrap items-center gap-1.5">
          {p.aliases.map((a) => (
            <span key={a} data-testid={`grn-profile-alias-${id}-${a}`} className="inline-flex items-center gap-1 rounded-full bg-[#F2F2F7] px-2 py-0.5">
              {a}<button aria-label="Hapus nama lain" data-testid={`grn-profile-alias-remove-${id}-${a}`} onClick={() => onPatch(id, { remove_alias: a })}><X size={10} /></button>
            </span>
          ))}
          <input data-testid={`grn-profile-alias-input-${id}`} className={`${inputCls} !w-full sm:!w-44 !py-1`} placeholder="Tambah nama lain" value={alias} onChange={(e) => setAlias(e.target.value)} />
          <button data-testid={`grn-profile-alias-add-${id}`} disabled={!alias.trim()} className="text-[#0058CC] disabled:opacity-40" onClick={async () => { if (await onPatch(id, { add_alias: alias })) setAlias(""); }}><Plus size={13} /></button>
        </div>
      </div>
      <LearnedBox p={p} onPatch={onPatch} />
      <div>
        <p className="mb-1 font-semibold">Barang yang dikenali ({p.item_map.length})</p>
        {p.item_map.length ? (
          <ul className="divide-y divide-[#EFF0F2] rounded-lg border border-[#EFF0F2]">
            {p.item_map.map((it) => (
              <li key={it.key} data-testid={`grn-profile-item-${id}-${it.product_id}`} className="flex items-center gap-2 px-2 py-1">
                <span className="flex-1 truncate font-mono text-[10.5px]">{it.text}</span>
                <span className="text-[10.5px]">→ {it.product_name}</span>
                <span className="text-[10px] text-[#8E8E93]">{it.count}×</span>
                <button aria-label="Lupakan pemetaan" data-testid={`grn-profile-item-remove-${id}-${it.product_id}`} onClick={() => onPatch(id, { remove_item_key: it.key })}><X size={11} className="text-[#B4231F]" /></button>
              </li>
            ))}
          </ul>
        ) : <p className="text-[10.5px] text-[#8E8E93]">Belum ada — dipelajari dari baris yang dicek pengguna saat kedatangan ditutup.</p>}
      </div>
    </div>
  );
}

/** Profil surat jalan per mitra: dipelajari otomatis dari SJ yang sudah dicek & ditutup, bisa dikoreksi admin. */
export default function GrnProfilesPanel() {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { grnApi.profiles().then(setRows).catch((e) => setErr(errText(e))); }, []);
  const onPatch = async (id, body) => {
    setErr("");
    try { const p = await grnApi.patchProfile(id, body); setRows((r) => r.map((x) => (x.partner_id === id ? p : x))); return true; } catch (e) { setErr(errText(e)); return false; }
  };
  return (
    <div className="space-y-3" data-testid="grn-profiles">
      <p className="text-[11px] text-[#6B6B73]">Sistem mempelajari format angka, nama lain pengirim, dan barang yang sering dikirim tiap mitra dari surat jalan yang sudah dicek pengguna. Hasil baca tetap wajib dicek manusia.</p>
      <ErrorBox text={err} />
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">{(rows || []).map((p) => <ProfileCard key={p.partner_id} p={p} onPatch={onPatch} />)}</div>
      {rows && !rows.length && <p data-testid="grn-profiles-empty" className="text-[11px] text-[#6B6B73]">Belum ada profil. Profil lahir saat kedatangan pertama mitra ditutup.</p>}
    </div>
  );
}
