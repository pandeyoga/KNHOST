"""Temuan lama #19 — setiap koleksi db.ai_* wajib terdaftar di registri scope."""
import pathlib
import re

from entity_scope import SCOPED_COLLECTIONS, SYSTEM_AI_COLLECTIONS, USER_SCOPED_COLLECTIONS

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_every_ai_collection_is_registered():
    used = set()
    for f in list((ROOT / "services").glob("*.py")) + list((ROOT / "routers").glob("*.py")):
        used |= set(re.findall(r"db\.(ai_[a-z_]+)", f.read_text()))
    known = SCOPED_COLLECTIONS | USER_SCOPED_COLLECTIONS | SYSTEM_AI_COLLECTIONS
    assert not (used - known), f"koleksi ai_* belum terdaftar: {sorted(used - known)}"
