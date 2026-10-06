"""OPS-04 — setiap koleksi yang diklaim `atomic_claim.claim()` wajib terdaftar di Kunci Saga (terlihat & bisa dilepas)."""
import glob
import re
import sys

sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")


def test_every_claimed_collection_is_listed_in_saga_locks():
    from routers.saga_locks import LOCKED_COLLECTIONS
    from services.internal_request_service import COLL as IR_COLL
    used = {IR_COLL}
    for f in glob.glob("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/routers/*.py") + glob.glob("C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend/services/*.py"):
        used |= set(re.findall(r'claim\(\s*"([a-z_]+)"', open(f).read()))
    missing = sorted(used - set(LOCKED_COLLECTIONS))
    assert not missing, f"koleksi ber-claim() tanpa entri Kunci Saga: {missing}"
