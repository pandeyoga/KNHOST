"""Satu MongoClient per proses tes: ratusan modul membuat klien sendiri saat import dan menghabiskan file descriptor mongod."""
import os

import pymongo
import pytest

_Orig = pymongo.MongoClient
_shared = {}


def _shared_client(*args, **kwargs):
    key = (args, tuple(sorted((k, repr(v)) for k, v in kwargs.items())))
    if key not in _shared:
        c = _Orig(*args, **kwargs)
        c.close = lambda *a, **k: None
        _shared[key] = c
    return _shared[key]


pymongo.MongoClient = _shared_client


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    """Tes yang sengaja salah sandi tidak boleh mengunci akun demo bersama (5x gagal → 429) bagi tes lain."""
    pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].login_attempts.delete_many({"locked_until": {"$exists": True}})
