"""Menyalakan aplikasi KNHOST utuh (server.app + bootstrap) di atas MongoDB tiruan dalam memori.

Dipakai skrip uji di folder ini. Tidak menyentuh database nyata dan tidak mengubah kode aplikasi.

Batas: mongomock tidak mendukung indeks unik parsial, balapan, maupun transaksi, sehingga keunikan
dan perilaku bersamaan TIDAK teruji di sini.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1/tidak-dipakai")
os.environ.setdefault("DB_NAME", "audit_mem")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("KN_DISABLE_SCHEDULER", "1")
BACKEND = str(Path(__file__).resolve().parents[4] / "backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

import motor.motor_asyncio as _m  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

_m.AsyncIOMotorClient = AsyncMongoMockClient

# mongomock menolak sebagian indeks unik parsial. Bila pembuatan indeks gagal, indeks dibuat ulang
# tanpa sifat unik supaya proses awal aplikasi selesai; daftar yang dilewati ada di SKIPPED_INDEXES.
import mongomock.collection as _mc  # noqa: E402

_orig_ci = _mc.Collection.create_index
SKIPPED_INDEXES = []


def _safe_ci(self, key_or_list, *a, **kw):
    try:
        return _orig_ci(self, key_or_list, *a, **kw)
    except Exception as exc:  # noqa: BLE001
        SKIPPED_INDEXES.append((self.name, str(key_or_list)[:80], type(exc).__name__))
        kw2 = {k: v for k, v in kw.items() if k not in ("unique", "partialFilterExpression", "sparse")}
        try:
            return _orig_ci(self, key_or_list, *a, **kw2)
        except Exception:  # noqa: BLE001
            return None


_mc.Collection.create_index = _safe_ci

# mongomock: `find_one_and_update(..., return_document=AFTER)` menerapkan pembaruan lalu mencari ulang dengan
# saringan semula; bila pembaruan membuat saringan tidak cocok lagi (pola klaim: `saga_lock` belum ada → diisi),
# hasilnya None padahal dokumen sudah berubah. MongoDB asli mengembalikan dokumen sesudah pembaruan. Tambalan ini
# menyamakan perilakunya supaya alur ber-klaim (`services/atomic_claim.py`) bisa diuji di sini.
from pymongo import ReturnDocument as _RD  # noqa: E402

_orig_fou = _mc.Collection.find_one_and_update


def _fou(self, filter, update, projection=None, sort=None, upsert=False,
         return_document=_RD.BEFORE, **kw):
    if return_document == _RD.AFTER and not upsert:
        before = _orig_fou(self, filter, update, projection={"_id": 1}, sort=sort, upsert=False,
                           return_document=_RD.BEFORE, **kw)
        if before is None:
            return None
        return self.find_one({"_id": before["_id"]}, projection)
    return _orig_fou(self, filter, update, projection=projection, sort=sort, upsert=upsert,
                     return_document=return_document, **kw)


_mc.Collection.find_one_and_update = _fou
