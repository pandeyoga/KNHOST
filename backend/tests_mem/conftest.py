"""Kerangka uji database tiruan (unit PK-02). Kontrak fixture & pembantu: README.md di folder ini.

    python -m pytest backend/tests_mem -n 0            # dari root repo; tanpa -n 0 juga harus lulus

Aplikasi utuh (`server.app` + proses awal + seed) dinyalakan di atas `mongomock-motor`. Tiap MODUL uji mulai dari
database kosong + seed awal. Tidak pernah menyentuh MongoDB asli (penjaga keselamatan di `pytest_sessionstart`).
"""
import os

# PK-14 — database tiruan tidak mendukung indeks unik parsial: indeks wajib yang tidak terpasang cukup ditulis ke log.
os.environ["KN_REQUIRED_INDEX_MODE"] = "warn"

import boot_app  # noqa: E402,F401  — HARUS sebelum modul lain: mengganti klien MongoDB sebelum `db` diimpor

import copy
import datetime
import importlib
import inspect
import itertools
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Sequence

import httpx
import pytest
from mongomock_motor import AsyncMongoMockClient

import db as _dbmod
import server
from pembantu import aktifkan_akun, alasan_xfail_sah, nonaktifkan_akun, tutup_periode

FOLDER = Path(__file__).resolve().parent

# Cache memori proses yang tidak ikut hilang saat koleksi dihapus. Dipulihkan ke isi awalnya tiap modul.
CACHE_PROSES = [
    ("services.gl_mapping_service", "_cache"), ("core_utils", "_ENTITY_CODE_CACHE"),
    ("services.entity_lifecycle_service", "_STATUS_CACHE"), ("services.entity_lifecycle_service", "_STATUS_CACHE_AT"),
    ("services.costing_service", "_WAC_CACHE"), ("services.config_health", "_CACHE"),
    ("services.uom_service", "_VOCAB_CACHE"), ("services.master_registry", "_cache"),
    ("services.field_visibility", "_cache"), ("services.od_pricing_service", "_cache"),
    ("services.location_scope", "_CACHE"), ("services.location_scope", "_TEST_CACHE"),
    ("services.config_resolver", "_JATUH_TEMPO"),   # KF-T3 — waktu jatuh tempo jadwal pengaturan terdekat
    ("services.config_health", "_TREES"),            # KF-T3 — pohon sintaks berkas pemakai (pemeriksa kesehatan)
    ("services.payment_method_service", "_KAMUS"),   # PM-T1 — kamus kata lama → kode cara bayar
]
_AWAL: Dict[tuple, Any] = {}
for _m, _n in CACHE_PROSES:
    _obj = getattr(importlib.import_module(_m), _n)
    _AWAL[(_m, _n)] = copy.deepcopy(_obj)


def _pulihkan_cache() -> None:
    for (m, n), awal in _AWAL.items():
        obj = getattr(importlib.import_module(m), n)
        obj.clear()
        obj.update(copy.deepcopy(awal))


def pytest_sessionstart(session):
    if not isinstance(_dbmod.client, AsyncMongoMockClient):
        pytest.exit("tests_mem hanya boleh berjalan di database tiruan", returncode=3)


def pytest_collection_modifyitems(config, items):
    for it in items:
        if FOLDER not in Path(str(it.fspath)).resolve().parents:
            continue
        fn = getattr(it, "function", None)
        if fn is not None and inspect.iscoroutinefunction(fn):
            it.add_marker(pytest.mark.anyio)
        for m in it.iter_markers("xfail"):
            reason = m.kwargs.get("reason", "")
            if m.kwargs.get("strict") is not True or not alasan_xfail_sah(reason):
                raise pytest.UsageError(
                    f"{it.nodeid}: tanda xfail wajib strict=True dan reason '<ID> — …' (diberi: {reason!r})")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


async def _kosongkan_db() -> None:
    for nama in await _dbmod.db.list_collection_names():
        await _dbmod.db[nama].drop()
    _pulihkan_cache()


@pytest.fixture(scope="module")
async def aplikasi():
    await _kosongkan_db()
    async with server.lifespan(server.app):
        yield server.app


@pytest.fixture(scope="module")
async def klien(aplikasi):
    tr = httpx.ASGITransport(app=aplikasi, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=tr, base_url="http://uji", timeout=120) as c:
        yield c


@pytest.fixture(scope="module")
def db(aplikasi):
    return _dbmod.db


def _sekarang() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture(scope="module")
def akun(aplikasi):
    nomor = itertools.count(1)

    async def _akun(peran: str, *, entitas: Sequence[str] = ("ent_ksc",), email: str = "") -> Dict[str, Any]:
        i = next(nomor)
        uid = f"usr_uji_{uuid.uuid4().hex[:10]}"
        dasar = await _dbmod.db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0}) or {}
        doc = {**dasar, "id": uid, "name": f"Uji {peran} {i}", "email": email or f"uji{i}.{uid}@uji.id",
               "role": peran, "status": "active", "home_entity_id": entitas[0],
               "allowed_entity_ids": list(entitas), "created_at": _sekarang().isoformat()}
        doc.pop("hr_employee_id", None)
        await _dbmod.db.users.insert_one(dict(doc))
        return doc
    return _akun


@pytest.fixture(scope="module")
def sesi(aplikasi):
    async def _sesi(siapa, *, entitas: str = "ent_ksc") -> Dict[str, str]:
        if isinstance(siapa, str):
            u = await _dbmod.db.users.find_one({"email": siapa}, {"_id": 0})
            assert u, f"akun {siapa} tidak ada di seed"
        else:
            u = siapa
        tok = "tok_uji_" + uuid.uuid4().hex
        await _dbmod.db.sessions.insert_one({"token": tok, "user_id": u["id"], "created_at": _sekarang(),
                                             "expires_at": _sekarang() + datetime.timedelta(hours=8)})
        return {"Authorization": f"Bearer {tok}", "X-Entity-Id": entitas}
    return _sesi


@pytest.fixture(scope="module")
async def kepala_admin(sesi):
    return await sesi("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def peran_tanpa_acuan(klien, kepala_admin):
    nomor = itertools.count(1)

    async def _peran(izin: Dict[str, list], *, label: str = "") -> str:
        r = await klien.post("/api/access/roles", headers=kepala_admin,
                             json={"label": label or f"Tanpa Acuan {next(nomor)}", "base_role": "",
                                   "permissions": izin, "description": "peran uji"})
        assert r.status_code == 200, r.text
        j = r.json()
        return (j.get("role") or j)["id"]
    return _peran


@pytest.fixture(scope="module")
def peran_manajer_kosong(klien, kepala_admin):
    simpan: Dict[str, str] = {}

    async def _peran() -> str:
        if "id" not in simpan:
            mods = (await klien.get("/api/access/modules", headers=kepala_admin)).json()
            mods = mods.get("modules", mods) if isinstance(mods, dict) else mods
            r = await klien.post("/api/access/roles", headers=kepala_admin, json={
                "label": "Manajer Kosong", "base_role": "manager", "description": "peran uji",
                "levels": {m["id"]: "none" for m in mods}})
            assert r.status_code == 200, r.text
            j = r.json()
            simpan["id"] = (j.get("role") or j)["id"]
        return simpan["id"]
    return _peran


@pytest.fixture(scope="session")
def peran_sopir():
    return "driver"


@pytest.fixture
def paksa_jurnal_gagal(aplikasi):
    @asynccontextmanager
    async def _paksa(cara: str, *, entity_id: str = "", kode_akun: str = "", period_key: str = "",
                     source_type: str = "", kali: int = 1):
        digagalkan: list = []
        if cara == "akun":
            assert entity_id and kode_akun, "cara 'akun' butuh entity_id dan kode_akun"
            await nonaktifkan_akun(entity_id, kode_akun)
            try:
                yield digagalkan
            finally:
                await aktifkan_akun(entity_id, kode_akun)
        elif cara == "periode":
            assert entity_id and period_key, "cara 'periode' butuh entity_id dan period_key"
            c = await tutup_periode(entity_id, period_key)
            try:
                yield digagalkan
            finally:
                await _dbmod.db.period_closings.delete_one({"id": c["id"]})
        elif cara == "sisip":
            from services import gl_service
            asli = gl_service._insert_entry
            sig = inspect.signature(asli)
            sisa = {"n": kali}

            async def _palsu(*a, **kw):
                arg = sig.bind_partial(*a, **kw).arguments
                cocok = ((not entity_id or arg.get("entity_id") == entity_id)
                         and (not source_type or arg.get("source_type") == source_type))
                if cocok and sisa["n"] > 0:
                    sisa["n"] -= 1
                    digagalkan.append(dict(arg))
                    raise RuntimeError("uji: jurnal dipaksa gagal")
                return await asli(*a, **kw)

            gl_service._insert_entry = _palsu
            try:
                yield digagalkan
            finally:
                gl_service._insert_entry = asli
        else:
            raise ValueError(f"cara tidak dikenal: {cara}")
    return _paksa
