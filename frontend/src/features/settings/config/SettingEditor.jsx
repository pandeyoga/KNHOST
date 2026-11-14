/**
 * SettingEditor — kontrol input yang menyesuaikan TIPE setting.
 *
 * Satu komponen untuk semua tipe (bool/int/pct/money/decimal/duration/enum/text/list/table)
 * sehingga UI Pusat Pengaturan bisa di-generate dari registry backend — UI dan mesin
 * tidak mungkin lagi berbeda (akar masalah "tombol palsu").
 */
import { useEffect, useState } from "react";
import KNSelect from "../../../components/KNSelect";
import SettingTableEditor, { MultiChoice } from "./SettingTableEditor";

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
      {(entry.min !== null || entry.max !== null) && (
        <span className="cfg-bounds">
          batas {entry.min ?? "−∞"} … {entry.max ?? "∞"}
        </span>
      )}
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
      <span className="cfg-bounds">satu butir per baris · urutan berpengaruh</span>
    </div>
  );
}

function ListField({ value, onChange, disabled, testId }) {
  const text = Array.isArray(value) ? value.join(", ") : String(value ?? "");
  return (
    <div className="cfg-num-wrap">
      <input
        className="form-input cfg-input cfg-input-wide"
        value={text}
        disabled={disabled}
        placeholder="pisahkan dengan koma, mis. 30, 60, 90"
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

function TableField({ entry, value, onChange, disabled, testId }) {
  return (
    <SettingTableEditor entry={entry} value={value} onChange={onChange}
      disabled={disabled} testId={testId} />
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
    case "int":
    case "duration":
    case "pct":
    case "money":
    case "decimal":
      return (
        <NumberField entry={entry} value={value} onChange={onChange}
          disabled={disabled} testId={tid} />
      );
    case "list":
      if (entry.value_format === "regex") return <LinesField value={value} onChange={onChange} disabled={disabled} testId={tid} />;
      // KP-T7 — daftar berpilihan (mis. peran penerima WhatsApp): kotak centang, bukan teks berkoma berisi id
      if ((entry.options || []).length) {
        return <MultiChoice options={entry.options} value={value} onChange={onChange} disabled={disabled}
          testId={tid} label={entry.label} />;
      }
      return <ListField value={value} onChange={onChange} disabled={disabled} testId={tid} />;
    case "table":
      return <TableField entry={entry} value={value} onChange={onChange} disabled={disabled} testId={tid} />;
    default:
      return (
        <input
          className="form-input cfg-input cfg-input-wide"
          value={value ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          data-testid={tid}
        />
      );
  }
}
