"""Read-only integrity/consistency checks for an exported JSONL snapshot; no restore or deletion.

Snapshot skema 1 (agent 0.4: events) dan skema 2 (agent 0.5: items event/summary/edge, bench, events_v1_archive).
"""
import json
import sys
from pathlib import Path

TABLES = {1: {"state", "passages", "events", "batches", "audit"},
          2: {"state", "passages", "items", "batches", "audit", "bench", "events_v1_archive"}}
ITEM_KINDS = {"event", "summary", "edge"}


def verify(path):
    header = None
    footer = None
    records = 0
    passages = set()
    events = set()
    items = set()
    references = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if header is None:
            assert row.get("kind") == "snapshot_header" and row.get("schema_version") in TABLES, "Invalid header"
            header = row
            continue
        assert footer is None, "Data after footer"
        if row.get("kind") == "snapshot_end":
            footer = row
            continue
        assert row.get("table") in TABLES[header["schema_version"]], "Unknown table"
        value = row["record"]
        records += 1
        if row["table"] == "passages":
            assert value["id"] not in passages, "Duplicate passage"
            passages.add(value["id"])
        if row["table"] in ("events", "events_v1_archive"):
            assert value["id"] not in events, "Duplicate event"
            events.add(value["id"])
            references.append(value["passage"])
        if row["table"] == "items":
            assert value["kind"] in ITEM_KINDS, "Unknown item kind"
            key = (value["kind"], value["id"])
            assert key not in items, "Duplicate item"
            items.add(key)
            references.append(value["passage"])
        if row["table"] == "batches":
            references.append(value["passage"])
    assert footer and footer.get("complete") is True and footer.get("record_count") == records, "Truncated/inconsistent export"
    assert all(p in passages for p in references), "Orphan passage reference"
    return {"schema_version": header["schema_version"], "records": records, "passages": len(passages),
            "events": len(events), "items": len(items), "valid": True}


if __name__ == "__main__":
    print(json.dumps(verify(sys.argv[1]), indent=2))
