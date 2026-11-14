"""PK-38 (FX-10, K-11) — satu pintu pemeriksaan **pengurang piutang tanpa uang masuk**.

Sebelum unit ini empat jalan menurunkan sisa piutang pesanan tanpa uang masuk ke kas/bank PT itu dan tanpa barang
kembali, dengan batas wewenang yang berbeda: hapus sisa kurang bayar dibatasi Rp 1.000.000 ("harus admin" di atasnya),
sementara kasus keuangan "biaya bank", "uang dipegang karyawan", dan "salah PT" lolos pada nominal berapa pun bagi
peran penyetuju — dan pembuat dokumennya boleh memutus sendiri. Kini semuanya lewat `periksa(...)`:

  batas(PT)                → `kontrol.pengurang_piutang.batas_nominal` PT itu; selama kunci baru belum pernah diisi
                             (grup maupun PT), nilai kunci lama `payment.variance_writeoff_max_amount` (alias, `02` §2.3)
  periksa(sumber, jenis…)  → di luar `TANPA_KAS` = tidak berlaku; selain itu bila butuh orang kedua (jumlah orang 2,
                             atau nominal di atas batas) → `dual_control.tolak_bila_pelaku_sama` (403 bila pelaku =
                             pembuat dokumen; pengecualian Admin & teksnya milik KF-T6). Tiap pemeriksaan dicatat di
                             jejak audit `ar_reduction_checked`.

Unit ini hanya MEMANGGIL `dual_control` (KF-T6); cara membandingkan pembuat dan pelaku ada di sana.
"""
import logging
from typing import Any, Dict, FrozenSet, Iterable, Optional

from fastapi import HTTPException

import config_registry as registry
from services import dual_control

logger = logging.getLogger(__name__)

AKSI = "pengurang_piutang"
EPS = 0.01

#: Keputusan yang menurunkan sisa piutang pesanan tanpa uang masuk ke kas/bank PT itu dan tanpa barang kembali.
TANPA_KAS: Dict[str, FrozenSet[str]] = {
    "payment_variance": frozenset({"writeoff"}),
    "finance_case": frozenset({"bebankan_biaya_bank", "akui_dipegang_karyawan", "settlement_antar_entitas"}),
}


def berlaku(sumber: str, jenis: str) -> bool:
    return (jenis or "") in TANPA_KAS.get(sumber or "", frozenset())


def _angka(v: Any) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


async def batas(entity_id: str) -> float:
    """Batas nominal pengurang piutang tanpa uang masuk untuk PT itu (0 = tidak dipakai).

    `kontrol.pengurang_piutang.batas_nominal` bila pernah diisi di lapisan grup atau PT itu; bila belum, nilai
    `payment.variance_writeoff_max_amount` (berlapis grup → PT) — supaya PT yang sudah mengatur batas hapus sisa tidak
    berubah diam-diam saat unit ini dipasang. Galat baca = bawaan registry (`02` §2.2)."""
    from services import config_resolver as resolver
    ctx = {"entity_id": entity_id or ""}
    try:
        baru = await resolver.resolve("kontrol.pengurang_piutang.batas_nominal", ctx)
        if baru["source_layer"] != "code_default":
            return _angka(baru["value"])
        return _angka(await resolver.value_of("payment.variance_writeoff_max_amount", ctx))
    except Exception as exc:  # noqa: BLE001 — pemeriksaan wewenang tidak boleh mati karena galat baca
        logger.warning("[ar_reduction_guard] batas gagal dibaca, pakai bawaan: %s", exc)
        return _angka(registry.require("kontrol.pengurang_piutang.batas_nominal")["default"])


async def _jejak(*, sumber: str, jenis: str, entity_id: str, nominal: float, dokumen: Dict[str, Any],
                 aktor: Dict[str, Any], hasil: Dict[str, Any], ditolak: bool) -> None:
    try:
        from dependencies import audit
        await audit((aktor or {}).get("name", ""), "ar_reduction_checked", sumber, (dokumen or {}).get("id", ""),
                    {"jenis": jenis, "nominal": nominal, "batas": hasil.get("batas"),
                     "di_atas_batas": hasil.get("di_atas_batas"), "perlu_orang_kedua": hasil.get("perlu_orang_kedua"),
                     "ditolak": ditolak, "number": (dokumen or {}).get("number", "")},
                    scope_entity_id=entity_id or "")
    except Exception as exc:  # noqa: BLE001 — jejak tidak boleh menggagalkan keputusan
        logger.warning("[ar_reduction_guard] jejak gagal dicatat: %s", exc)


async def periksa(*, sumber: str, jenis: str, entity_id: str, nominal: float, dokumen: Dict[str, Any],
                  aktor: Dict[str, Any], pengaju: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Satu pintu untuk keputusan pengurang piutang tanpa uang masuk.

    `(sumber, jenis)` di luar `TANPA_KAS` → `{"berlaku": False}` (tanpa efek). Selain itu: butuh orang kedua bila
    `kontrol.pengurang_piutang.min_orang` = 2 atau `nominal` di atas `batas(PT)`; bila butuh dan pelaku = pembuat
    dokumen → 403 (teks KF-T6). `pengaju` kosong = kolom pembuat baku dokumen. Jawaban:
    `{"berlaku", "batas", "di_atas_batas", "perlu_orang_kedua"}`."""
    if not berlaku(sumber, jenis):
        return {"berlaku": False}
    eid = entity_id or (dokumen or {}).get("entity_id") or ""
    n = _angka(nominal)
    b = await batas(eid)
    perlu = await dual_control.butuh_orang_kedua(AKSI, eid, n, batas=b)
    hasil = {"berlaku": True, "batas": b, "di_atas_batas": b > 0 and n > b + EPS, "perlu_orang_kedua": perlu}
    ditolak = False
    try:
        if perlu:
            await dual_control.tolak_bila_pelaku_sama(AKSI, dokumen or {}, aktor or {}, eid, nominal=n, batas=b,
                                                      pengaju=pengaju)
    except HTTPException:
        ditolak = True
        raise
    finally:
        await _jejak(sumber=sumber, jenis=jenis, entity_id=eid, nominal=n, dokumen=dokumen, aktor=aktor,
                     hasil=hasil, ditolak=ditolak)
    return hasil
