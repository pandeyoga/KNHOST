"""KF-T8 (KF-08) — INV-CFG-08: uji putaran SETIAP kunci registry menjadi gate.

    python -m pytest backend/tests_mem/test_KFT8_putaran_pengaturan.py -n 0 -q      # dari root repo (± 2 menit)

Satu kasus per kunci (`test_KFT8_putaran[<kunci>]`, parametrize atas `config_registry.all_entries()`), lewat aplikasi
utuh di database tiruan (kerangka PK-02). Alur per kunci aktif (asal: `docs/audit/konfigurasi-peran-2026-11-13/bukti/
t1_config.py`, arsip tidak diubah):

  1. tulis nilai lain di lapisan grup (`PUT /api/config/values`) → baca lewat tiga jalur:
     `GET /api/config/effective`, `config_resolver.value_of`, dan pembaca lama (`config_service.get_effective_settings`
     untuk dokumen grup; dokumen `system_settings{scope}` + `config_resolver.entity_overlay` untuk dokumen lain);
  2. kunci berlapis PT: tulis nilai lain lagi untuk `ent_kanda` → terbaca untuk `ent_kanda`, `ent_ksc` tidak berubah;
     cabut (`POST /api/config/values/clear`) → `ent_kanda` kembali ke nilai grup;
  3. nilai tak sah (di luar batas, pilihan tak dikenal, tipe salah) → 400;
  4. kunci wajib-alasan tanpa alasan → 400;
  5. pulihkan (`POST /api/config/values/reset`) → nilai = bawaan registry. Langkah ini juga dijalankan di `finally`, jadi
     tiap kasus meninggalkan kuncinya pada bawaan walau gagal di tengah.
Kunci `not_used`: tulisan wajib ditolak.

Kode gagal (`docs/blueprint/unit/KF-T8.md`): P1 lapisan grup tidak terbaca sama di salah satu jalur · P2 lapisan PT
tidak terbaca / PT lain ikut berubah · P3 sesudah dicabut tidak kembali ke nilai grup · P4 nilai tak sah tidak ditolak
400 · P5 wajib-alasan menerima tulisan tanpa alasan · P6 sesudah dipulihkan ≠ bawaan · P7 kunci `not_used` menerima
tulisan · P8 ditimpa aturan lain (`overridden_by`, KF-T3) tetapi `value_of` ≠ pembaca lama atau `stored_value` ≠ nilai
yang ditulis (untuk kunci demikian P1–P3 dinilai terhadap `stored_value`).

Pembaca lama tidak dinilai untuk kunci `bertanggal` (PK-46): resolver sengaja tidak memproyeksikannya ke
`system_settings` (`config_resolver._project`) dan mesinnya membaca `resolve(key, ctx, at=…)`.

U2–U5 membuktikan putaran ini bisa merah (`monkeypatch` satu mata rantai, lalu kasus satu kunci harus gagal dengan kode
yang benar). Semua alur lewat API (bukan fixture sisip langsung); sesi admin seed = `kepala_admin`.
"""
from typing import Any, Dict, List, Optional

import pytest

import config_registry as registry
from _nilai_uji import (TAK_ADA, calon_lain, gali, nilai_lain, nilai_tak_sah, opsi_dari, ringkas, sama,
                        simpan_ulang)
from db import db as _db
from services import config_resolver as resolver
from services import config_service

pytestmark = pytest.mark.anyio   # parametrize + anyio: tanpa tanda modul, anyio menimpa parameter `kunci`

PT_TULIS, PT_LAIN = "ent_kanda", "ent_ksc"
ALASAN = "uji putaran KF-T8"
LEWAT = ("<tidak dinilai>",)
KUNCI = [e["key"] for e in registry.all_entries()]
#: Temuan yang DITEMUKAN putaran ini pada kunci milik unit lain (tidak diperbaiki di KF-T8 — `docs/blueprint/unit/KF-T8.md`
#: "Di luar lingkup"): {kunci: (kode gagal yang diketahui, alasan "<ID> — …")}. Kasusnya `xfail` HANYA bila gagal dengan
#: kode itu saja; kode lain tetap merah, dan begitu pemiliknya memperbaiki (kasus lulus) tes merah sampai butir dicabut.
TEMUAN = {
    "allocation.allow_intercompany": ("P8", (
        "KF-04 — P8: pembaca lama (get_effective_settings) tidak menerapkan penimpa wajib_transfer_antar_pt; nilai PT "
        "true tetap terbaca padahal value_of = false (hanya get_allocation_policy yang menerapkannya sendiri)")),
    "returns.grade_price_factors": ("P2", (
        "KF-04 — P2: pembaca lama (get_effective_settings) menggabung tabel PT dengan tabel grup (deep-merge); "
        "pasangan yang tidak ada di tabel PT tetap terbaca dari grup, value_of benar")),
}


class Putaran:
    """Satu kasus putaran untuk satu kunci. `gagal` = daftar "<kode> <kunci>: <pesan>"."""

    def __init__(self, klien, hdr: Dict[str, str], key: str) -> None:
        self.klien, self.hdr, self.key = klien, hdr, key
        self.e = registry.require(key)
        self.gagal: List[str] = []
        self.pt_ditulis = self.pt_dicabut = self.dipulihkan = False
        self.tersimpan: Any = TAK_ADA       # nilai bersih yang disimpan server pada tulisan terakhir

    def catat(self, kode: str, pesan: str) -> None:
        self.gagal.append(f"{kode} {self.key}: {pesan}")

    # ── jalur tulis ──────────────────────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _detail(r) -> str:
        try:
            return str(r.json().get("detail", ""))[:200]
        except ValueError:
            return r.text[:200]

    async def tulis(self, value: Any, *, scope_type: str = "global", scope_id: str = "",
                    reason: str = ALASAN) -> tuple:
        r = await self.klien.put("/api/config/values", headers=self.hdr, json={"items": [{
            "key": self.key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]})
        self.tersimpan = r.json()["saved"][0]["value"] if r.status_code == 200 else TAK_ADA
        return r.status_code, ("" if r.status_code == 200 else self._detail(r))

    async def cabut(self) -> tuple:
        r = await self.klien.post("/api/config/values/clear", headers=self.hdr, json={
            "key": self.key, "scope_type": "entity", "scope_id": PT_TULIS, "reason": ALASAN})
        return r.status_code, ("" if r.status_code == 200 else self._detail(r))

    async def pulihkan(self) -> tuple:
        r = await self.klien.post("/api/config/values/reset", headers=self.hdr, json={
            "key": self.key, "scope_type": "global", "reason": "pulihkan sesudah uji putaran KF-T8"})
        return r.status_code, ("" if r.status_code == 200 else self._detail(r))

    # ── tiga jalur baca ──────────────────────────────────────────────────────────────────────────────────────────
    async def butir_api(self, ent: str) -> Optional[Dict[str, Any]]:
        r = await self.klien.get("/api/config/effective", headers=self.hdr, params={"q": self.key, "entity_id": ent})
        if r.status_code != 200:
            return None
        return next((it for it in r.json().get("items", []) if it["key"] == self.key), None)

    def _sumber_lama(self) -> str:
        sc = self.e["legacy_scope"]
        return "get_effective_settings" if sc == "global" else f"system_settings{{scope:{sc}}} + entity_overlay"

    async def pembaca_lama(self, ent: str) -> Any:
        if self.e.get("bertanggal"):
            return LEWAT
        sc, path = self.e["legacy_scope"], self.e["legacy_path"]
        if sc == "global":
            return gali(await config_service.get_effective_settings(ent or None), path)
        doc = await _db.system_settings.find_one({"scope": sc}, {"_id": 0}) or {}
        val = gali(doc, path)
        if ent:
            ov = gali(await resolver.entity_overlay(sc, ent) or {}, path)
            if ov is not TAK_ADA:
                val = ov
        return val

    async def baca(self, ent: str) -> Dict[str, Any]:
        api = await self.butir_api(ent)
        ditimpa = (api or {}).get("overridden_by") if api is not None else \
            (await resolver.resolve(self.key, {"entity_id": ent}))["overridden_by"]
        return {"api": api, "ditimpa": ditimpa, "value_of": await resolver.value_of(self.key, {"entity_id": ent}),
                "lama": await self.pembaca_lama(ent)}

    def periksa(self, b: Dict[str, Any], harap: Any, kode: str, tempat: str) -> None:
        """Tiga jalur harus memberi `harap`; bila ditimpa aturan lain (P8): `stored_value` = `harap`, `value_of` =
        nilai efektif GET = pembaca lama."""
        api, lama, vo = b["api"], b["lama"], b["value_of"]
        if api is None:
            self.catat(kode, f"{tempat}: tidak tampil di GET /api/config/effective")
        if b["ditimpa"]:
            sebab = (b["ditimpa"] or {}).get("id") or (b["ditimpa"] or {}).get("label") or "?"
            if api is not None and not sama(api.get("stored_value"), harap):
                self.catat("P8", f"{tempat}: stored_value {ringkas(api.get('stored_value'))} ≠ nilai yang ditulis "
                                 f"{ringkas(harap)} (ditimpa {sebab})")
            if api is not None and not sama(vo, api.get("value")):
                self.catat(kode, f"{tempat}: value_of memberi {ringkas(vo)}, GET /api/config/effective "
                                 f"{ringkas(api.get('value'))} (ditimpa {sebab})")
            if lama is not LEWAT and not sama(vo, lama):
                self.catat("P8", f"{tempat}: value_of {ringkas(vo)} ≠ pembaca lama ({self._sumber_lama()}) "
                                 f"{ringkas(lama)} (ditimpa {sebab})")
            return
        if api is not None and not sama(api.get("value"), harap):
            self.catat(kode, f"{tempat}: GET /api/config/effective memberi {ringkas(api.get('value'))}, "
                             f"ditulis {ringkas(harap)}")
        if not sama(vo, harap):
            self.catat(kode, f"{tempat}: value_of memberi {ringkas(vo)}, ditulis {ringkas(harap)}")
        if lama is not LEWAT and not sama(lama, harap):
            self.catat(kode, f"{tempat}: pembaca lama ({self._sumber_lama()}) memberi {ringkas(lama)}, "
                             f"ditulis {ringkas(harap)}")

    async def opsi(self, ent: str) -> List[str]:
        return opsi_dari(await resolver.ref_options(self.e["ref"], ent)) if self.e.get("ref") else []

    async def tulis_lain(self, base: Any, *, scope_type: str = "global", scope_id: str = "", kode: str,
                         tempat: str) -> Any:
        """Tulis calon nilai sah pertama (≠ `base`) yang diterima server → nilai BERSIH yang disimpannya (mis. nomor
        WhatsApp dinormalkan); `TAK_ADA` (+ catatan `kode`) bila tidak ada. 400 = pemeriksa domain menolak calon itu →
        calon berikutnya; kode lain langsung gagal. Nilai tersimpan yang sama dengan `base` = tulisan tidak mengubah
        apa pun → calon berikutnya (kecuali tabel JSON yang memang disimpan ulang)."""
        opsi = await self.opsi(scope_id)
        calon = [base] if simpan_ulang(self.e) else calon_lain(self.e, base, opsi)
        if not calon:
            self.catat(kode, f"{tempat}: pembangkit tidak bisa membuat nilai sah lain dari {ringkas(base)} "
                             f"(tipe {self.e['type']}) — lengkapi tests_mem/_nilai_uji.py")
            return TAK_ADA
        ditolak = []
        for v in calon:
            st, det = await self.tulis(v, scope_type=scope_type, scope_id=scope_id)
            if st == 200:
                if not sama(self.tersimpan, base) or simpan_ulang(self.e):
                    return self.tersimpan
                ditolak.append(f"{ringkas(v, 60)} → tersimpan {ringkas(self.tersimpan, 60)} = nilai sebelumnya")
                continue
            ditolak.append(f"{ringkas(v, 60)} → HTTP {st}: {det}")
            if st != 400:
                break
        self.catat(kode, f"{tempat}: tidak ada nilai lain yang tersimpan — " + " · ".join(ditolak))
        return TAK_ADA

    # ── alur ─────────────────────────────────────────────────────────────────────────────────────────────────────
    async def jalankan(self) -> List[str]:
        e = self.e
        if e["status"] != "active":
            st, _ = await self.tulis(e["default"])
            if st != 400:
                self.catat("P7", f"kunci tidak dipakai menerima tulisan (HTTP {st}, harus 400)")
            return self.gagal
        try:
            await self._alur()
        finally:
            if self.pt_ditulis and not self.pt_dicabut:
                await self.cabut()
            if not self.dipulihkan:
                await self.pulihkan()
        return self.gagal

    async def _alur(self) -> None:
        e = self.e
        base = (await resolver.resolve(self.key))["stored_value"]
        v1 = await self.tulis_lain(base, kode="P1", tempat="lapisan grup")
        if v1 is TAK_ADA:
            return
        self.periksa(await self.baca(""), v1, "P1", "lapisan grup")
        if "entity" in e["scopes"]:
            await self._lapisan_pt(v1)
        for bad in nilai_tak_sah(e):
            st, _ = await self.tulis(bad)
            if st != 400:
                self.catat("P4", f"nilai tak sah {ringkas(bad)} tidak ditolak (HTTP {st}, harus 400)")
        if e["requires_reason"]:
            st, _ = await self.tulis(v1, reason="")
            if st != 400:
                self.catat("P5", f"tulisan tanpa alasan diterima (HTTP {st}, harus 400)")
        st, det = await self.pulihkan()
        if st != 200:
            self.catat("P6", f"pulihkan ditolak (HTTP {st}: {det})")
            return
        self.dipulihkan = True
        b = await self.baca("")
        bawaan = e["default"]
        tersimpan = (await resolver.resolve(self.key))["stored_value"]
        if not sama(tersimpan, bawaan):
            self.catat("P6", f"sesudah dipulihkan value_of (nilai tersimpan) {ringkas(tersimpan)} ≠ bawaan "
                             f"{ringkas(bawaan)}")
        if b["api"] is None or not sama(b["api"].get("stored_value"), bawaan):
            self.catat("P6", f"sesudah dipulihkan GET /api/config/effective "
                             f"{ringkas((b['api'] or {}).get('stored_value', TAK_ADA))} ≠ bawaan {ringkas(bawaan)}")
        if b["lama"] is not LEWAT and not b["ditimpa"] and not sama(b["lama"], bawaan):
            self.catat("P6", f"sesudah dipulihkan pembaca lama ({self._sumber_lama()}) {ringkas(b['lama'])} ≠ bawaan "
                             f"{ringkas(bawaan)}")

    async def _lapisan_pt(self, v1: Any) -> None:
        lain_awal = await self.baca(PT_LAIN)
        self.pt_ditulis = True          # calon yang ditolak tidak menulis apa pun; cabut di `finally` tetap aman
        v2 = await self.tulis_lain(v1, scope_type="entity", scope_id=PT_TULIS, kode="P2",
                                   tempat=f"lapisan PT {PT_TULIS}")
        if v2 is TAK_ADA:
            return
        self.periksa(await self.baca(PT_TULIS), v2, "P2", f"lapisan PT {PT_TULIS}")
        lain = await self.baca(PT_LAIN)
        pasangan = (
            ("GET /api/config/effective", (lain_awal["api"] or {}).get("value", TAK_ADA),
             (lain["api"] or {}).get("value", TAK_ADA)),
            ("value_of", lain_awal["value_of"], lain["value_of"]),
            (f"pembaca lama ({self._sumber_lama()})", lain_awal["lama"], lain["lama"]),
        )
        for jalur, awal, kini in pasangan:
            if awal is LEWAT:
                continue
            if not (sama(awal, kini) or (awal is TAK_ADA and kini is TAK_ADA)):
                self.catat("P2", f"PT {PT_LAIN} ikut berubah lewat {jalur}: {ringkas(awal)} → {ringkas(kini)}")
        st, det = await self.cabut()
        if st != 200:
            self.catat("P3", f"mencabut lapisan PT {PT_TULIS} ditolak (HTTP {st}: {det})")
            return
        self.pt_dicabut = True
        self.periksa(await self.baca(PT_TULIS), v1, "P3", f"sesudah lapisan PT {PT_TULIS} dicabut")


async def putaran(klien, hdr, key: str) -> List[str]:
    return await Putaran(klien, hdr, key).jalankan()


# ── U1 — tiap kunci registry ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("kunci", KUNCI)
async def test_KFT8_putaran(kunci, klien, kepala_admin):
    gagal = await putaran(klien, kepala_admin, kunci)
    if kunci in TEMUAN:
        kode, alasan = TEMUAN[kunci]
        lain = [g for g in gagal if not g.startswith(kode + " ")]
        assert not lain, "\n".join(lain)
        assert gagal, f"{kunci}: temuan '{alasan[:40]}…' sudah tidak terjadi — cabut butirnya dari TEMUAN"
        pytest.xfail(alasan)
    assert not gagal, "\n".join(gagal)


async def test_KFT8_U1_jumlah_kasus_dan_pembangkit():
    """U1 — satu kasus per entri registry (tanpa yang dilewati); pembangkit membuat nilai lain untuk tiap kunci aktif
    selain tabel JSON (dulu 19 kunci daftar/tabel hanya disimpan ulang dengan nilai sama)."""
    assert len(KUNCI) == len(registry.all_entries()) == len(set(KUNCI))
    tanpa = []
    for e in registry.all_entries():
        if e["status"] != "active" or simpan_ulang(e) or e.get("ref"):
            continue
        v = nilai_lain(e, e["default"])
        if v is None or sama(v, e["default"]):
            tanpa.append(e["key"])
    assert tanpa == [], f"pembangkit tidak membuat nilai lain: {tanpa}"


# ── U2–U5 — bukti-merah: satu mata rantai dirusak, kasus satu kunci WAJIB gagal dengan kode yang benar ──────────────
def _kode(gagal: List[str], kode: str) -> List[str]:
    print("\n".join(["[bukti-merah]"] + gagal))          # tampil dengan `-s` / `-rP` (bukti laporan)
    return [g for g in gagal if g.startswith(kode + " ")]


async def test_KFT8_U2_proyeksi_mati_merah_P1_pembaca_lama(klien, kepala_admin, monkeypatch):
    async def _tanpa_proyeksi(*_a, **_kw):
        return None
    monkeypatch.setattr(resolver, "_project", _tanpa_proyeksi)
    gagal = await putaran(klien, kepala_admin, "tax.ppn_mode")
    monkeypatch.undo()
    await Putaran(klien, kepala_admin, "tax.ppn_mode").pulihkan()      # dokumen lama kembali sejalan
    p1 = _kode(gagal, "P1")
    assert p1 and all("pembaca lama" in g for g in p1), "\n".join(gagal)


async def test_KFT8_U3_batas_tidak_diperiksa_merah_P4(klien, kepala_admin, monkeypatch):
    monkeypatch.setattr(registry, "_bounded", lambda _e, num: num)
    gagal = await putaran(klien, kepala_admin, "ar.grace_days")
    monkeypatch.undo()
    assert _kode(gagal, "P4"), "\n".join(gagal)


async def test_KFT8_U4_lapisan_pt_dibuang_merah_P2(klien, kepala_admin, monkeypatch):
    """`build_layers` tanpa lapisan PT (`entity` dan `legacy_entity` — proyeksi `_project` ke dokumen PT terbaca lewat
    `legacy_entity`, jadi membuang `entity` saja tidak mengubah nilai PT; lihat laporan KF-T8)."""
    asli = resolver.build_layers

    async def _tanpa_pt(*a, **kw):
        return [lay for lay in await asli(*a, **kw) if lay["layer"] not in ("entity", "legacy_entity")]
    monkeypatch.setattr(resolver, "build_layers", _tanpa_pt)
    gagal = await putaran(klien, kepala_admin, "sales.allow_partial_shipment")
    monkeypatch.undo()
    assert _kode(gagal, "P2"), "\n".join(gagal)


async def test_KFT8_U5_alasan_dilewati_merah_P5(klien, kepala_admin, monkeypatch):
    key = "tax.ppn_mode"
    assert registry.require(key)["requires_reason"] and registry.require(key)["risk"] == "high"
    asli = resolver.set_value

    async def _tanpa_cek_alasan(k, value, **kw):
        kw["reason"] = (kw.get("reason") or "").strip() or "dilewati uji"
        return await asli(k, value, **kw)
    monkeypatch.setattr(resolver, "set_value", _tanpa_cek_alasan)
    gagal = await putaran(klien, kepala_admin, key)
    monkeypatch.undo()
    assert _kode(gagal, "P5"), "\n".join(gagal)


# ── U14 — layar Kesehatan Pengaturan memakai `check_entry` yang sama dengan gate kabel pengaturan ───────────────────
async def test_KFT8_U14_kesehatan_registry_utuh(monkeypatch):
    """`config_health.report()`: satu baris per entri registry, tidak ada yang rusak (STALE/MISSING). Akar berkas
    diarahkan ke salinan kerja ini (di container `/app` = repo; di luar container `/app` bisa menunjuk salinan lain)."""
    from pathlib import Path

    from services import config_health
    akar = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(config_health, "BACKEND", str(akar / "backend"))
    monkeypatch.setattr(config_health, "FRONTEND", str(akar / "frontend" / "src"))
    hasil = config_health.report()
    assert hasil["total"] == len(hasil["rows"]) == len(registry.all_entries())
    assert [r["key"] for r in hasil["rows"]] == KUNCI
    assert hasil["broken"] == [], [(r["key"], r["wiring_status"]) for r in hasil["broken"]]


async def test_KFT8_U14b_potongan_kode_sama_dengan_ast():
    """`config_health._segmen` (baris berkas dipecah sekali, KF-T8) = `ast.get_source_segment` untuk tiap fungsi yang
    dirujuk `consumers` registry dan tiap konstanta teks tingkat modul di berkasnya (dua jenis simpul yang dipotong
    `_badan_fungsi`) — percepatan tanpa mengubah hasil `check_entry`."""
    import ast
    from pathlib import Path

    from services import config_health
    akar = Path(__file__).resolve().parents[2] / "backend"
    rujukan: Dict[str, set] = {}
    for e in registry.all_entries():
        for c in e["consumers"]:
            rel, _, fn = str(c).partition(":")
            if rel.endswith(".py") and fn:
                rujukan.setdefault(rel, set()).add(fn.strip())
    dibanding = 0
    for rel, nama in sorted(rujukan.items()):
        p = akar / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text)
        simpul = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in nama]
        simpul += [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                   and n.value is not None and config_health._hanya_teks(n.value)]
        for n in simpul:
            assert config_health._segmen(str(p), text, n) == ast.get_source_segment(text, n), (rel, n.lineno)
            dibanding += 1
    assert dibanding > 300, dibanding
