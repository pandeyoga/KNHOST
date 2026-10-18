"""Penilai eval Tanya KN: alternatif sah diterima, jawaban salah tetap ditolak."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/tools/ai_eval")
from run_eval import _args_match_semantic  # noqa: E402

QS = {q["id"]: q for q in json.loads(Path("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/tools/ai_eval/questions_v1.json").read_text())["questions"]}


def _ok(q, tool, args):
    cands = [q["expected"]] + q.get("alternatives", [])
    return any(c["tool"] == tool and _args_match_semantic(c["args"], args) for c in cands)


def test_seven_questions_have_alternatives():
    assert [i for i, q in QS.items() if q.get("alternatives")] == ["q047", "q053", "q057", "q074", "q076", "q091", "q093"]


def test_alternatives_accept_valid_paths():
    assert _ok(QS["q047"], "run_report", {"report": "ar_aging"})
    assert _ok(QS["q057"], "forecast", {"kind": "cashflow"})
    assert _ok(QS["q093"], "query_metrics", {"metrics": ["received_qty"], "group_by": ["unit"], "compare": "previous_period"})
    assert _ok(QS["q076"], "list_records", {"record_type": "shipments"})


def test_wrong_answers_still_fail():
    assert not _ok(QS["q047"], "run_report", {"report": "stock_health"})
    assert not _ok(QS["q057"], "forecast", {"kind": "demand"})
    assert not _ok(QS["q093"], "query_metrics", {"metrics": ["net_sales"]})
    assert not _ok(QS["q053"], "list_records", {"record_type": "shipments"})
