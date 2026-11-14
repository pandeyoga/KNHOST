/**
 * SettingEditor — kontrol input yang menyesuaikan TIPE setting.
 *
 * Satu komponen untuk semua tipe (bool/int/pct/money/decimal/duration/enum/text/list/table)
 * sehingga UI Pusat Pengaturan bisa di-generate dari registry backend — UI dan mesin
 * tidak mungkin lagi berbeda (akar masalah "tombol palsu").
 *
 * KF-T4 (KF-13) — editor dipilih dari `type` + `items` / `value_format` / `ref` / `row_shape` registry, supaya pemilik
 * tidak mengetik kode: daftar peran & pilihan = kotak centang; daftar berurutan = baris yang bisa digeser; deret angka
 * dan daftar teks = baris tambah/hapus; pola & teks berbaris = kotak multi-baris; tanggal = pemilih tanggal; rujukan
 * master (syarat bayar, satuan, departemen) = daftar pilih; rupiah = isian berpemisah ribuan.
 */
import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Lock, Plus, Trash2 } from "lucide-react";
import KNSelect from "../../../components/KNSelect";
import KNDatePicker from "../../../components/KNDatePicker";
import SettingTableEditor from "./SettingTableEditor";
import { formatValue, idNum } from "./configApi";

/** "paling kecil … · paling besar …" dengan satuan kunci (KF-T4). */
function Bounds({ entry }) {
  const lo = entry.min ?? null;
  const hi = entry.max ?? null;
  if (lo === null && hi === null) return null;
  const parts = [];
  if (lo !== null) parts.push(`paling kecil ${formatValue(entry, lo)}`);
  if (hi !== null) parts.push(`paling besar ${formatValue(entry, hi)}`);
  return <span className="cfg-bounds">{parts.join(" · ")}</span>;
}

function NumberField({ entry, value, onChange, disabled, testId }) {
  const step = entry.step ?? (entry.type === "int" || entry.type === "duration" ? 1 : 0.1);
  return (
    <div className="cfg-num-wrap">
      <input
        type="number"
        className="form-input cfg-input"
        value={value ?? ""}
        min={entry.min ?? undefined}
        max={entry.max ?? undefined}
        step={step}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
        data-testid={testId}
      />
      {entry.unit ? <span className="cfg-unit">{entry.unit}</span> : null}
      <Bounds entry={entry} />
    </div>
  );
}

/** KF-T4 — rupiah: isian berpemisah ribuan ("1.000.000"), nilai tersimpan tetap angka. */
function MoneyField({ entry, value, onChange, disabled, testId }) {
  const shown = value === "" || value === null || value === undefined ? "" : idNum(value, 0);
  return (
    <div className="cfg-num-wrap">
      <span className="cfg-unit">Rp</span>
      <input
        type="text"
        inputMode="numeric"
        className="form-input cfg-input tabular-nums"
        value={shown}
        disabled={disabled}
        onChange={(e) => {
          const digits = e.target.value.replace(/[^\d]/g, "");
          onChange(digits === "" ? "" : Number(digits));
        }}
        data-testid={testId}
      />
      <Bounds entry={entry} />
    </div>
  );
}

// FIX-3a (B3b FRM-19) — daftar POLA REGEX: satu butir per baris. Pemisah koma memecah kuantor `\d{3,5}` menjadi dua
// butir rusak; server kini juga menolak regex tak sah (value_format "regex").
const NL = "\n";

function LinesField({ value, onChange, disabled, testId }) {
  const asText = (v) => (Array.isArray(v) ? v.join(NL) : String(v ?? ""));
  const [draft, setDraft] = useState(asText(value));
  const key = JSON.stringify(value);
  useEffect(() => { setDraft(asText(value)); }, [key]);
  return (
    <div className="cfg-num-wrap">
      <textarea
        className="form-input cfg-input cfg-input-wide font-mono text-[12px]"
        rows={Math.max(2, Math.min(8, draft.split(NL).length))}
        value={draft}
        disabled={disabled}
        placeholder="satu pola per baris"
        onChange={(e) => {
          setDraft(e.target.value);
          onChange(e.target.value.split(NL).map((x) => x.trim()).filter((x) => x !== ""));
        }}
        data-testid={testId}
      />
      <span className="cfg-bounds">satu pola per baris · urutan berpengaruh</span>
    </div>
  );
}

/** KF-T4 — teks berbaris (`multiline`) dan teks JSON (`json_map`): kotak multi-baris, nilai tersimpan tetap teks. */
function MultilineField({ entry, value, onChange, disabled, testId }) {
  const text = String(value ?? "");
  return (
    <div className="cfg-num-wrap cfg-col">
      <textarea
        className={`form-input cfg-input cfg-input-wide ${entry.value_format === "json_map" ? "font-mono text-[12px]" : ""}`}
        rows={Math.max(3, Math.min(10, text.split(NL).length + 1))}
        value={text}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
      />
    </div>
  );
}

/** KF-T4 — kotak centang dari pilihan (`items: "options"` → `options`; `items: "roles"` → `ref_options` peran). */
function ChecklistField({ choices, value, onChange, disabled, testId }) {
  const set = new Set((Array.isArray(value) ? value : []).map(String));
  const toggle = (v) => {
    const cur = Array.isArray(value) ? value : [];
    onChange(set.has(String(v)) ? cur.filter((x) => String(x) !== String(v)) : [...cur, v]);
  };
  return (
    <div className="cfg-check-grid" data-testid={testId} role="group">
      {choices.map((o) => (
        <label key={o.value} className="cfg-check" data-testid={`${testId}-opt-${o.value}`}>
          <input type="checkbox" checked={set.has(String(o.value))} disabled={disabled}
            onChange={() => toggle(o.value)} />
          <span>{o.label}</span>
        </label>
      ))}
    </div>
  );
}

/** KF-T4 — daftar berurutan: centang + geser naik/turun; `allocation.priority_order` mengunci "PT pemilik stok" di
 *  urutan pertama (server menolak urutan lain). */
function OrderedField({ entry, choices, value, onChange, disabled, testId }) {
  const cur = Array.isArray(value) ? value.map(String) : [];
  const locked = entry.key === "allocation.priority_order" ? "owner" : "";
  const label = (v) => (choices.find((o) => String(o.value) === v) || {}).label || v;
  const unused = choices.filter((o) => !cur.includes(String(o.value)));
  const move = (i, d) => {
    const next = [...cur];
    const j = i + d;
    if (j < 0 || j >= next.length || next[j] === locked || next[i] === locked) return;
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };
  return (
    <div className="cfg-order" data-testid={testId}>
      <ol className="cfg-order-list">
        {cur.map((v, i) => (
          <li key={v} className="cfg-order-row" data-testid={`${testId}-row-${v}`}>
            <span className="cfg-order-n">{i + 1}.</span>
            <span className="cfg-order-label">{label(v)}</span>
            {v === locked ? (
              <span className="cfg-hint-sm"><Lock size={11} /> selalu pertama</span>
            ) : (
              <>
                <button type="button" className="icon-button" disabled={disabled || i === 0 || cur[i - 1] === locked}
                  onClick={() => move(i, -1)} aria-label={`Naikkan ${label(v)}`}
                  data-testid={`${testId}-up-${v}`}><ArrowUp size={13} /></button>
                <button type="button" className="icon-button" disabled={disabled || i === cur.length - 1}
                  onClick={() => move(i, 1)} aria-label={`Turunkan ${label(v)}`}
                  data-testid={`${testId}-down-${v}`}><ArrowDown size={13} /></button>
                <button type="button" className="icon-button" disabled={disabled}
                  onClick={() => onChange(cur.filter((x) => x !== v))} aria-label={`Hapus ${label(v)}`}
                  data-testid={`${testId}-del-${v}`}><Trash2 size={13} /></button>
              </>
            )}
          </li>
        ))}
      </ol>
      {unused.length ? (
        <div className="cfg-order-add">
          {unused.map((o) => (
            <button key={o.value} type="button" className="btn-secondary btn-sm" disabled={disabled}
              onClick={() => onChange([...cur, String(o.value)])} data-testid={`${testId}-add-${o.value}`}>
              <Plus size={12} /> {o.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** KF-T4 — deret angka menaik (`int_asc`, mis. kolom umur piutang) dengan pratinjau kolom laporan. */
function IntAscField({ entry, value, onChange, disabled, testId }) {
  const cur = Array.isArray(value) ? value : [];
  const set = (i, v) => onChange(cur.map((x, k) => (k === i ? (v === "" ? "" : Number(v)) : x)));
  const nums = cur.map(Number).filter((n) => Number.isFinite(n) && n > 0);
  let prev = 0;
  const kolom = nums.map((n) => { const t = `${prev + 1}–${n}`; prev = n; return t; });
  return (
    <div className="cfg-col" data-testid={testId}>
      <div className="cfg-int-list">
        {cur.map((x, i) => (
          <span key={i} className="cfg-int-item">
            <input type="number" min={1} step={1} className="form-input cfg-input-xs" value={x ?? ""} disabled={disabled}
              onChange={(e) => set(i, e.target.value)} data-testid={`${testId}-${i}`}
              aria-label={`Batas ke-${i + 1}`} />
            <button type="button" className="icon-button" disabled={disabled}
              onClick={() => onChange(cur.filter((_, k) => k !== i))} aria-label={`Hapus batas ke-${i + 1}`}>
              <Trash2 size={12} /></button>
          </span>
        ))}
        <button type="button" className="btn-secondary btn-sm" disabled={disabled}
          onClick={() => onChange([...cur, (nums[nums.length - 1] || 0) + 30])} data-testid={`${testId}-add`}>
          <Plus size={12} /> Tambah batas
        </button>
      </div>
      {nums.length ? (
        <span className="cfg-bounds" data-testid={`${testId}-preview`}>
          kolom {kolom.join(", ")}, di atas {nums[nums.length - 1]} {entry.unit || "hari"}
        </span>
      ) : null}
    </div>
  );
}

/** KF-T4 — daftar butir teks (`items: "text"`), tambah/hapus butir. */
function TextListField({ value, onChange, disabled, testId }) {
  const cur = Array.isArray(value) ? value : [];
  return (
    <div className="cfg-int-list" data-testid={testId}>
      {cur.map((x, i) => (
        <span key={i} className="cfg-int-item">
          <input className="form-input cfg-input-sm" value={x ?? ""} disabled={disabled}
            onChange={(e) => onChange(cur.map((y, k) => (k === i ? e.target.value : y)))}
            data-testid={`${testId}-${i}`} aria-label={`Butir ke-${i + 1}`} />
          <button type="button" className="icon-button" disabled={disabled}
            onClick={() => onChange(cur.filter((_, k) => k !== i))} aria-label={`Hapus butir ke-${i + 1}`}>
            <Trash2 size={12} /></button>
        </span>
      ))}
      <button type="button" className="btn-secondary btn-sm" disabled={disabled}
        onClick={() => onChange([...cur, ""])} data-testid={`${testId}-add`}><Plus size={12} /> Tambah butir</button>
    </div>
  );
}

/** Cadangan untuk daftar tanpa `items` (mis. kunci yang diubah di layar lain): satu kotak berkoma. */
function ListField({ value, onChange, disabled, testId }) {
  const text = Array.isArray(value) ? value.join(", ") : String(value ?? "");
  return (
    <div className="cfg-num-wrap">
      <input
        className="form-input cfg-input cfg-input-wide"
        value={text}
        disabled={disabled}
        placeholder="pisahkan dengan koma"
        onChange={(e) =>
          onChange(
            e.target.value
              .split(",")
              .map((x) => x.trim())
              .filter((x) => x !== "")
              .map((x) => (Number.isNaN(Number(x)) ? x : Number(x)))
          )
        }
        data-testid={testId}
      />
      <span className="cfg-bounds">urutan berpengaruh</span>
    </div>
  );
}

function ListEditor({ entry, value, onChange, disabled, testId }) {
  if (entry.value_format === "regex") return <LinesField value={value} onChange={onChange} disabled={disabled} testId={testId} />;
  const choices = entry.items === "roles" ? (entry.ref_options || []) : (entry.options || []);
  if (entry.items === "options" && entry.ordered) {
    return <OrderedField entry={entry} choices={choices} value={value} onChange={onChange} disabled={disabled} testId={testId} />;
  }
  if (entry.items === "options" || entry.items === "roles") {
    return <ChecklistField choices={choices} value={value} onChange={onChange} disabled={disabled} testId={testId} />;
  }
  if (entry.items === "int_asc") return <IntAscField entry={entry} value={value} onChange={onChange} disabled={disabled} testId={testId} />;
  if (entry.items === "text") return <TextListField value={value} onChange={onChange} disabled={disabled} testId={testId} />;
  // KP-T7 — daftar berpilihan tanpa `items` (mis. peran penerima WhatsApp): kotak centang berlabel, bukan teks berkoma.
  if (!entry.items && (entry.options || []).length) {
    return <ChecklistField choices={entry.options} value={value} onChange={onChange} disabled={disabled} testId={testId} />;
  }
  return <ListField value={value} onChange={onChange} disabled={disabled} testId={testId} />;
}

function TextEditor({ entry, value, onChange, disabled, testId }) {
  if (entry.ref) {
    const opts = entry.ref_options || [];
    // Bawaan kosong (mis. departemen penerima) → pilihan "tidak diisi" (KNSelect tidak menerima nilai kosong).
    const KOSONG = "__kosong__";
    const bolehKosong = entry.default === "" || entry.default === null;
    const withEmpty = bolehKosong ? [{ value: KOSONG, label: "— tidak diisi —" }, ...opts] : opts;
    return (
      <KNSelect value={value ? value : (bolehKosong ? KOSONG : "")} onValueChange={(v) => onChange(v === KOSONG ? "" : v)}
        options={withEmpty} className="field cfg-select"
        placeholder={opts.length ? "Pilih…" : "Belum ada pilihan di master"} disabled={disabled} data-testid={testId} />
    );
  }
  if (entry.value_format === "date") {
    return <KNDatePicker value={value || ""} onChange={onChange} disabled={disabled} placeholder="Kosong = hari ini"
      data-testid={testId} />;
  }
  if (entry.value_format === "multiline" || entry.value_format === "json_map") {
    return <MultilineField entry={entry} value={value} onChange={onChange} disabled={disabled} testId={testId} />;
  }
  return (
    <input
      className="form-input cfg-input cfg-input-wide"
      value={value ?? ""}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      data-testid={testId}
    />
  );
}

export default function SettingEditor({ entry, value, onChange, disabled, testId }) {
  const tid = testId || `cfg-input-${entry.key}`;
  switch (entry.type) {
    case "bool":
      return (
        <div className="cfg-switch-row">
          <button
            type="button"
            role="switch"
            aria-checked={!!value}
            aria-label={entry.label}
            className={`cfg-switch ${value ? "on" : "off"}`}
            disabled={disabled}
            onClick={() => onChange(!value)}
            data-testid={tid}
          >
            <span className="cfg-switch-knob" />
          </button>
          <span className={`cfg-switch-label ${value ? "on" : ""}`}>
            {value ? "Ya / Aktif" : "Tidak / Mati"}
          </span>
        </div>
      );
    case "enum":
      return (
        <KNSelect
          value={value ?? ""}
          onValueChange={onChange}
          options={entry.options || []}
          className="field cfg-select"
          placeholder="Pilih…"
          disabled={disabled}
          data-testid={tid}
        />
      );
    case "money":
      return <MoneyField entry={entry} value={value} onChange={onChange} disabled={disabled} testId={tid} />;
    case "int":
    case "duration":
    case "pct":
    case "decimal":
      return (
        <NumberField entry={entry} value={value} onChange={onChange}
          disabled={disabled} testId={tid} />
      );
    case "list":
      return <ListEditor entry={entry} value={value} onChange={onChange} disabled={disabled} testId={tid} />;
    case "table":
      return <SettingTableEditor entry={entry} value={value} onChange={onChange} disabled={disabled} testId={tid} />;
    default:
      return <TextEditor entry={entry} value={value} onChange={onChange} disabled={disabled} testId={tid} />;
  }
}
