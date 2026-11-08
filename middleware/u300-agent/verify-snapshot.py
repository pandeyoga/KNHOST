"""Read-only integrity/consistency checks for an exported JSONL snapshot; no restore or deletion."""
import json
import sys
from pathlib import Path

def verify(path):
    header = None
    footer = None
    records = 0
    passages = set()
    events = set()
    references = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if header is None:
            assert row.get("kind") == "snapshot_header" and row.get("schema_version") == 1, "Invalid header"
            header = row
            continue
        assert footer is None, "Data after footer"
        if row.get("kind") == "snapshot_end":
            footer = row
            continue
        assert row.get("table") in {"state", "passages", "events", "batches", "audit"}, "Unknown table"
        value = row["record"]
        records += 1
        if row["table"] == "passages":
            assert value["id"] not in passages, "Duplicate passage"
            passages.add(value["id"])
        if row["table"] == "events":
            assert value["id"] not in events, "Duplicate event"
            events.add(value["id"])
            references.append(value["passage"])
        if row["table"] == "batches":
            references.append(value["passage"])
    assert footer and footer.get("complete") is True and footer.get("record_count") == records, "Truncated/inconsistent export"
    assert all(p in passages for p in references), "Orphan passage reference"
    return {"records": records, "passages": len(passages), "events": len(events), "valid": True}

if __name__ == "__main__":
    print(json.dumps(verify(sys.argv[1]), indent=2))
