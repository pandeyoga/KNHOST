"""Cetak Jejak Dokumen — seluruh rantai dokumen satu jangkar sebagai satu PDF audit."""
from typing import Any, Dict, Optional

from core_utils import now_iso
from services import doc_refs_service as refs
from services import pdf_service as svc
from services.pdf_engine import fmt_rp, render_html, render_pdf
from services.pdf_resolvers import fmt_date


def _col(key: str, label: str, align: str = "") -> Dict[str, str]:
    return {"key": key, "label": label, "align": align}


async def build_trace_doc(doc_type: str, doc_id: str, depth: Optional[int], printed_by: str) -> Dict[str, Any]:
    tr = await refs.trace(doc_type, doc_id, depth=depth)
    a = tr["anchor"] or {}
    num = {n["key"]: n["number"] for n in tr["nodes"]}
    items = [{"no": i, "stage": n["label"], "number": n["number"] + (" ★" if n.get("is_anchor") else ""),
              "title": n.get("title") or "-", "date": fmt_date(n.get("date")) if n.get("date") else "-",
              "status": n.get("status") or "-", "amount": fmt_rp(n["amount"]) if n.get("amount") else "-",
              "level": str(n.get("level", 0))}
             for i, n in enumerate(tr["nodes"], 1)]
    edges = [{"from": num.get(e["from"], e["from"]), "rel": e.get("rel_label") or e.get("rel", ""),
              "to": num.get(e["to"], e["to"]), "note": e.get("note") or "-",
              "kind": "Otomatis (jurnal/kas)" if e.get("derived") else "Tersimpan"}
             for e in tr["edges"]]
    notes = "★ = dokumen jangkar. Kolom 'Lvl' = jarak dari jangkar."
    if tr.get("truncated"):
        notes += f" Masih ada {tr['truncated']} tautan di luar kedalaman {tr['depth']} — naikkan kedalaman untuk jejak lengkap."
    return {
        "title": "Jejak Dokumen (Audit Trail)", "number": a.get("number", doc_id),
        "date": fmt_date(now_iso()), "status": a.get("status") or "",
        "meta": [{"label": "Jangkar", "value": f"{a.get('label', doc_type)} — {a.get('title') or '-'}"},
                 {"label": "Nilai jangkar", "value": fmt_rp(a.get("amount")) if a.get("amount") else "-"},
                 {"label": "Dokumen terkait", "value": str(tr["node_count"])},
                 {"label": "Relasi", "value": str(tr["edge_count"])},
                 {"label": "Kedalaman", "value": str(tr["depth"])},
                 {"label": "Dicetak oleh", "value": f"{printed_by} · {fmt_date(now_iso())}"}],
        "columns": [_col("no", "No", "num"), _col("stage", "Jenis Dokumen"), _col("number", "Nomor"),
                    _col("title", "Pihak / Keterangan"), _col("date", "Tanggal"), _col("status", "Status"),
                    _col("amount", "Nilai", "num"), _col("level", "Lvl", "num")],
        "items": items,
        "extra_tables": [{"title": "Relasi Antar Dokumen", "note": "",
                          "columns": [_col("from", "Dokumen"), _col("rel", "Relasi"), _col("to", "Dokumen Tujuan"),
                                      _col("note", "Catatan"), _col("kind", "Jenis Tautan")],
                          "items": edges}] if edges else [],
        "notes": notes,
        "signatures": [{"label": "Dicetak", "role": "", "name": printed_by},
                       {"label": "Diperiksa", "role": "Auditor", "name": ""}],
        "entity_id": a.get("entity_id") or "",
    }


async def render_trace(doc_type: str, doc_id: str, depth: Optional[int], printed_by: str, fmt: str = "pdf"):
    doc = await build_trace_doc(doc_type, doc_id, depth, printed_by)
    cfg = await svc.get_template_cfg(svc.DEFAULT_CODE)
    branding = await svc.get_branding(doc.pop("entity_id") or None)
    html = render_html(cfg, branding, doc)
    if fmt == "html":
        return html, "text/html", doc
    pdf, _ = render_pdf(html)
    return pdf, "application/pdf", doc
