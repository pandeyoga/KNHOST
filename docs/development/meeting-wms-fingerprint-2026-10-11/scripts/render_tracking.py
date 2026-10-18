from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "BACKLOG.json").read_text(encoding="utf-8"))
lines = ["# Tracker Implementasi dan Validasi", "",
         "Sumber status: BACKLOG.json. File ini dihasilkan scripts/render_tracking.py; ubah JSON lalu render ulang.", "",
         "Semua status awal belum dikerjakan. implemented_pending_validation berbeda dari validated.", "",
         "## Fase", "", "| Fase | Judul | Status | Dependensi | Bukti |", "|---|---|---|---|---|"]
for row in data["phases"]:
    ev = "; ".join(row.get("evidence", [])) or "—"
    lines.append(f"| {row['id']} | {row['title']} | {row['status']} | {', '.join(row['dependencies']) or '—'} | {ev} |")
lines += ["", "## Kebutuhan", "", "| IMP | Kebutuhan | Fase utama | Status | Commit implementasi / verifikasi | Bukti / issue |", "|---|---|---|---|---|---|"]
for row in data["requirements"]:
    ev = "; ".join(row.get("evidence", []) + row.get("open_issues", [])) or "—"
    commits = f"{row.get('implementation_commit') or '—'} / {row.get('verified_commit') or '—'}"
    lines.append(f"| {row['id']} | {row['title']} | {row['primary_phase']} | {row['status']} | {commits} | {ev} |")
lines += ["", "## Keputusan", "", "| DEC | Topik | Status | Sumber keputusan / alasan |", "|---|---|---|---|"]
for row in data["decisions"]:
    source = row.get("confirmation_ref") or row.get("reason") or "—"
    lines.append(f"| {row['id']} | {row['topic']} | {row['status']} | {source} |")
lines += ["", "## Pengujian", "", "| ACC | Fase | Skenario | Hasil | Commit / evidence |", "|---|---|---|---|---|"]
for row in data["acceptance"]:
    ev = "; ".join(row.get("evidence", [])) or "—"
    lines.append(f"| {row['id']} | {row['phase']} | {row['title']} | {row['status']} | {row.get('verified_commit') or '—'}; {ev} |")
(ROOT / "TRACKER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("TRACKER.md updated from BACKLOG.json")
