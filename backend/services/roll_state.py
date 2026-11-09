"""FIX-10 (audit 9 Nov 2026 B3a SSOT-1) — SATU penulis status roll (`inventory_rolls.status`).

MASALAH YANG DITUTUP. Status roll ditulis 63+ panggilan di 18 berkas + 2 router, tanpa tabel transisi: tiap penulis
memegang daftar status asalnya sendiri (atau tidak sama sekali — menulis `{id}` saja sesudah membaca status di Python,
R→W), tanpa jejak, dan kosakatanya bocor (`allocated` milik `sales_orders.allocations[].status` muncul di daftar
status roll). Pembaca menebak status mana yang "fisik" (STK-6, DUP-3).

SEKARANG semua perubahan status roll lewat `transition()`:

* **Daftar-izin** `ROLL_TRANSITIONS` (dari status yang BENAR-BENAR ditulis kode & ada di data acuan, lihat laporan
  FIX-10). Transisi di luar tabel = galat pemrograman (`IllegalRollTransition`) SEBELUM ada tulisan apa pun.
* **CAS**: filter tulis = id + status asal (`from_`, wajib) + prasyarat lain pemanggil (`extra_filter`). Kalah balapan →
  0 / None (pemanggil memutuskan 409 / lewati), tidak pernah menimpa diam-diam.
* **Jejak** = `status_history` roll (bentuk SSOT `services/status_history.py`, dibatasi `HISTORY_MAX` entri terakhir) —
  ditulis di tulisan yang SAMA dengan status (atomik). Satu jejak saja: tidak ada mutasi tambahan untuk perubahan
  status (mutasi `inventory_movements` tetap milik perubahan KUANTITAS, ditulis pemanggil seperti sebelumnya).
  Status yang tidak berubah (mis. tiba PA `available → available` pindah gudang) tidak menambah entri.
* **Saldo**: segmen (produk × gudang × PT) roll terdampak — sebelum & sesudah (bila `extra_set` memindah gudang/PT) —
  dibangun ulang lewat `roll_service.rebuild_balance` (pola yang ada). Pemanggil yang sudah membangun ulang segmen
  sendiri dalam satu putaran (banyak roll) memberi `rebuild=False` supaya tidak dobel.

Kelahiran roll (insert) bukan transisi; status lahir wajib anggota `STATUSES` (`assert_known`).
Penjaga: `scripts/guardrails/verify_roll_status_writer.py` (INV-ROLL-02, ratchet — penulis di luar modul ini hanya
boleh berkurang).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

from pymongo import ReturnDocument

from core_utils import now_iso
from db import db
from services import status_history as sh

# ── Kosakata status roll (SSOT; label = `frontend/src/utils/statusVocab.js` DOMAIN_LABELS.roll, istilah K-13) ──────
#: kind: physical (fisik di gudang, masuk on_hand) · transit · offsite (milik PT, fisik di mitra) · pipeline (belum
#: masuk saldo) · terminal (keluar dari persediaan).
STATUSES: Dict[str, Dict[str, str]] = {
    "receiving": {"label": "Sedang Diterima", "kind": "pipeline"},
    "quarantine": {"label": "Karantina", "kind": "physical"},
    "available": {"label": "Tersedia", "kind": "physical"},
    "reserved": {"label": "Dipesan", "kind": "physical"},
    "committed": {"label": "Dialokasikan", "kind": "physical"},
    "picked": {"label": "Sudah Diambil", "kind": "physical"},
    "packed": {"label": "Sudah Dikemas", "kind": "physical"},
    "hold": {"label": "Ditahan", "kind": "physical"},
    "wip": {"label": "WIP (Proses)", "kind": "physical"},
    "blocked": {"label": "Diblokir", "kind": "physical"},
    "damaged": {"label": "Rusak", "kind": "physical"},
    "in_transit_transfer": {"label": "Dalam Perjalanan (Transfer)", "kind": "transit"},
    "in_transit_sales": {"label": "Dalam Perjalanan (Penjualan)", "kind": "transit"},
    "in_transit_inbound": {"label": "Dalam Perjalanan (Masuk)", "kind": "transit"},
    "in_transit_intercompany": {"label": "Dalam Perjalanan (Antar-PT)", "kind": "transit"},
    "subcon": {"label": "Di Makloon", "kind": "offsite"},
    "delivered": {"label": "Terkirim", "kind": "terminal"},
    "consumed": {"label": "Habis Terpakai", "kind": "terminal"},
    "returned_supplier": {"label": "Diretur ke Supplier", "kind": "terminal"},
}
#: Status lama di `ENTITY_REGISTRY.md` yang TIDAK pernah ditulis kode (dibiarkan di luar `STATUSES`; bila muncul di
#: data → dilaporkan sebagai status liar, tidak diubah diam-diam).
REGISTRY_UNUSED = ("on_order", "cross_dock", "sold", "returned", "scrapped")

_HELD = ("reserved", "committed", "picked", "packed")
_REPAIRABLE = ("available", "quarantine", "damaged", "blocked", "hold")   # repair_order_service.ELIGIBLE_STATUSES
#: Status fisik yang boleh dihapus opname (selisih kurang → `consumed`) — `roll_service.PHYSICAL_ROLL_STATUSES`.
_COUNTABLE = ("available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked",
              "damaged")

#: DAFTAR-IZIN `dari → {ke}`. Pemilik/pemicu tiap baris tertulis di laporan FIX-10 §tabel transisi roll.
ROLL_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    # pindai label / hitung GRN → posting penerimaan (QC aktif → karantina; QC mati → tersedia)
    "receiving": ("quarantine", "available"),
    # keputusan QC (terima / rusak / retur) · lepas karantina retur · tahan QC-06 · perbaikan · opname · retur beli
    # dibalik (kembali tersedia) · penyelesaian retur dibalik (roll identitas kembali "di pelanggan") · pecah cutloss
    "quarantine": ("available", "damaged", "returned_supplier", "blocked", "wip", "consumed", "delivered", "hold"),
    # alokasi/pesan (SO, transfer, roll pilihan) · kirim PA · ember tahan/WIP/makloon · tahan QC-06 · habis terpakai
    # (produksi, sample, opname) · retur beli (keluar / dikunci karantina selama RMA) · potongan cutloss dibuang
    "available": ("reserved", "in_transit_transfer", "hold", "wip", "subcon", "blocked", "consumed",
                  "returned_supplier", "quarantine", "damaged"),
    # lepas · SO disetujui · kirim SJ · transfer antar-gudang dikirim · opname
    "reserved": ("available", "committed", "in_transit_sales", "in_transit_transfer", "consumed"),
    "committed": ("available", "in_transit_sales", "in_transit_transfer", "consumed"),
    # `picked`/`packed` = ember saldo yang tidak pernah ditulis kode (data acuan 0) — keluar hanya lewat kirim/lepas/opname
    "picked": ("available", "in_transit_sales", "consumed"),
    "packed": ("available", "in_transit_sales", "consumed"),
    # POD (per SJ / pesanan) · kompensasi kirim yang kalah balapan (kembali ke status sebelum berangkat)
    "in_transit_sales": ("delivered",) + _HELD,
    # transfer/PA tiba (status asal SO dipulihkan), tolak/kompensasi, hasil periksa terima (rusak / diterima ditahan =
    # `blocked`, FIX-3a STM-IN-04)
    "in_transit_transfer": ("available", "reserved", "committed", "damaged", "blocked"),
    # retur pelanggan diterima kembali (karantina retur / cutloss masuk gudang untuk dipecah)
    "delivered": ("quarantine", "hold"),
    # tahan dilepas · perbaikan · potongan baik cutloss dikirim balik · dibuang · opname
    "hold": ("available", "wip", "delivered", "damaged", "consumed"),
    # selesai WIP / hasil perbaikan · habis di perbaikan · perbaikan dibatalkan (kembali status asal)
    "wip": ("available", "consumed") + tuple(s for s in _REPAIRABLE if s != "available"),
    # retur bahan makloon · bahan terpakai di mitra
    "subcon": ("available", "consumed"),
    # lepas tahan → status sebelum ditahan; tolak QC roll ditahan → karantina dulu; perbaikan; opname; dibuang
    "blocked": ("available", "quarantine", "wip", "consumed", "damaged"),
    # perbaikan · opname · koreksi write-off / barang kembali dari supplier · pecah cutloss
    "damaged": ("wip", "consumed", "available", "quarantine", "hold"),
    # retur beli ditolak (rusak) / dibatalkan (status sebelum diretur: tersedia atau karantina)
    "returned_supplier": ("damaged", "available", "quarantine"),
    # koreksi produksi / pengambilan bahan sample dibatalkan (bahan kembali)
    "consumed": ("available",),
    # ember transit tanpa penulis di kode (data acuan 0) — tidak ada transisi keluar sampai ada pemiliknya
    "in_transit_inbound": (),
    "in_transit_intercompany": (),
}
HISTORY_MAX = 30
SEGMENT_FIELDS = ("product_id", "warehouse_id", "owner_entity_id")


class IllegalRollTransition(ValueError):
    """Transisi status roll di luar `ROLL_TRANSITIONS` — galat pemrograman, ditolak sebelum menulis."""


def label(status: str) -> str:
    return (STATUSES.get(status or "") or {}).get("label") or (status or "—")


def is_known(status: str) -> bool:
    return status in STATUSES


def assert_known(status: str) -> None:
    """Status lahir roll baru wajib anggota kosakata (bukan `allocated`, bukan kode lama registry)."""
    if status not in STATUSES:
        raise IllegalRollTransition(f"Status roll '{status}' tidak dikenal (bukan anggota roll_state.STATUSES).")


def allowed(frm: str, to: str) -> bool:
    """`frm → to` sah? Status yang tidak berubah (frm == to) selalu sah (tulisan field lain di bawah CAS status)."""
    if frm == to:
        return frm in STATUSES
    return to in ROLL_TRANSITIONS.get(frm or "", ())


def assert_allowed(froms: Iterable[str], to: str) -> None:
    assert_known(to)
    bad = [f for f in froms if not allowed(f, to)]
    if bad:
        raise IllegalRollTransition(
            "Perubahan status roll tidak diizinkan: " + ", ".join(f"{label(f)} ({f}) → {label(to)} ({to})" for f in bad)
            + ". Tabel transisi: services/roll_state.ROLL_TRANSITIONS.")


def _froms(from_: Union[str, Iterable[str]]) -> List[str]:
    vals = [from_] if isinstance(from_, str) else list(from_ or [])
    out = list(dict.fromkeys(v for v in vals if v))
    if not out:
        raise IllegalRollTransition("roll_state.transition: status asal (`from_`) wajib — tulisan tanpa CAS dilarang.")
    return out


def _ref_fields(ref: Optional[Union[Dict[str, Any], str]]) -> Dict[str, str]:
    if not ref:
        return {}
    if isinstance(ref, str):
        return {"ref": ref}
    out = {"ref_type": str(ref.get("type") or ""), "ref_id": str(ref.get("id") or ""),
           "ref_no": str(ref.get("no") or ref.get("number") or ref.get("doc") or "")}
    return {k: v for k, v in out.items() if v}


def history_entry(to: str, frm: str, *, reason: str, actor: str = "", action: str = "",
                  ref: Optional[Union[Dict[str, Any], str]] = None) -> Dict[str, Any]:
    """Satu entri `status_history` roll (bentuk SSOT + `from`, `action`, rujukan dokumen)."""
    return sh.entry(to, user=actor or "Sistem", note=reason, **{"from": frm, "action": action}, **_ref_fields(ref))


def _selector(roll_ids: Union[str, Iterable[str], None], extra_filter: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    flt: Dict[str, Any] = dict(extra_filter or {})
    if "status" in flt:
        raise IllegalRollTransition("roll_state.transition: status asal lewat `from_`, bukan `extra_filter`.")
    if roll_ids is None:
        if not flt:
            raise IllegalRollTransition("roll_state.transition: tanpa roll_ids wajib ada `extra_filter`.")
        return flt
    if isinstance(roll_ids, str):
        flt["id"] = roll_ids
    else:
        ids = list(dict.fromkeys(r for r in roll_ids if r))
        if not ids:
            return {}
        flt["id"] = {"$in": ids}
    return flt


def _literal(v: Any) -> Any:
    return {"$literal": v}


async def _segments(sel: Dict[str, Any], froms: List[str], extra_set: Dict[str, Any]) -> Set[Tuple[str, str, str]]:
    segs: Set[Tuple[str, str, str]] = set()
    proj = {"_id": 0, **{k: 1 for k in SEGMENT_FIELDS}}
    async for r in db.inventory_rolls.find({**sel, "status": {"$in": froms}}, proj):
        seg = tuple(r.get(k) or "" for k in SEGMENT_FIELDS)
        segs.add(seg)  # type: ignore[arg-type]
        moved = tuple(extra_set.get(k, r.get(k)) or "" for k in SEGMENT_FIELDS)
        if moved != seg:
            segs.add(moved)  # type: ignore[arg-type]
    return segs


async def rebuild_segments(segs: Iterable[Tuple[str, str, str]]) -> int:
    """Bangun ulang saldo segmen (produk × gudang × PT) — pola `roll_service.rebuild_balance`."""
    from services.roll_service import rebuild_balance
    n = 0
    for p, w, o in sorted({s for s in segs if s and s[0] and s[1]}):
        await rebuild_balance(p, w, o)
        n += 1
    return n


async def transition(roll_ids: Union[str, Iterable[str], None], to: str, *, from_: Union[str, Iterable[str]],
                     reason: str, actor: str = "", action: str = "",
                     ref: Optional[Union[Dict[str, Any], str]] = None,
                     extra_set: Optional[Dict[str, Any]] = None, extra_filter: Optional[Dict[str, Any]] = None,
                     unset: Optional[Iterable[str]] = None, push: Optional[Dict[str, Any]] = None,
                     pipeline: Optional[List[Dict[str, Any]]] = None, rebuild: bool = True,
                     return_doc: bool = False, projection: Optional[Dict[str, Any]] = None):
    """Ubah status roll `from_ → to` lewat CAS + jejak + saldo.

    * `roll_ids`: satu id, daftar id, atau None (pilih lewat `extra_filter`, mis. `{"reserved_ref.id": so}`).
    * `from_`: status asal (satu / daftar) — WAJIB; tiap `from_ → to` wajib sah menurut `ROLL_TRANSITIONS`.
    * `extra_set` / `unset` / `push`: field lain di tulisan yang SAMA. `pipeline`: tahap tambahan pipeline update
      (tulisan berbentuk pipeline; `unset`/`push` tidak boleh bersama `pipeline`).
    * `return_doc=True` (wajib satu id): dokumen sesudah tulis atau None bila CAS kalah.
      Selain itu: jumlah roll yang LOLOS CAS dan ditulis.
    * `rebuild`: bangun ulang saldo segmen terdampak (sebelum & sesudah pindah gudang/PT). `False` bila pemanggil
      sudah membangun ulang segmen yang sama sesudahnya.
    """
    froms = _froms(from_)
    assert_allowed(froms, to)
    if not (reason or "").strip():
        raise IllegalRollTransition("roll_state.transition: alasan (`reason`) wajib untuk jejak status roll.")
    if pipeline is not None and (unset or push):
        raise IllegalRollTransition("roll_state.transition: `unset`/`push` tidak bisa bersama `pipeline`.")
    if return_doc and not isinstance(roll_ids, str):
        raise IllegalRollTransition("roll_state.transition: `return_doc` hanya untuk satu roll.")
    sel = _selector(roll_ids, extra_filter)
    if not sel:
        return None if return_doc else 0
    extra = {k: v for k, v in (extra_set or {}).items() if k not in ("status", "status_history")}
    segs = await _segments(sel, froms, extra) if rebuild else set()
    now = now_iso()
    total = 0
    doc = None
    for f in froms:
        flt = {**sel, "status": f}
        entry = history_entry(to, f, reason=reason, actor=actor, action=action, ref=ref) if f != to else None
        if pipeline is not None:
            stage: Dict[str, Any] = {**{k: _literal(v) for k, v in extra.items()}, "status": _literal(to),
                                     "updated_at": _literal(now)}
            if entry:
                stage["status_history"] = {"$slice": [{"$concatArrays": [
                    {"$ifNull": ["$status_history", []]}, [_literal(entry)]]}, -HISTORY_MAX]}
            upd: Any = [{"$set": stage}] + list(pipeline)
        else:
            upd = {"$set": {**extra, "status": to, "updated_at": now}}
            pushes = dict(push or {})
            if entry:
                pushes["status_history"] = {"$each": [entry], "$slice": -HISTORY_MAX}
            if pushes:
                upd["$push"] = pushes
            if unset:
                upd["$unset"] = {k: "" for k in unset}
        if return_doc:
            doc = await db.inventory_rolls.find_one_and_update(
                flt, upd, projection=projection or {"_id": 0}, return_document=ReturnDocument.AFTER)
            if doc:
                total = 1
                break
            continue
        if isinstance(sel.get("id"), str):
            res = await db.inventory_rolls.update_one(flt, upd)
        else:
            res = await db.inventory_rolls.update_many(flt, upd)
        total += res.matched_count
        if total and isinstance(sel.get("id"), str):
            break
    if rebuild and total:
        await rebuild_segments(segs)
    return doc if return_doc else total


def census_query() -> Dict[str, Any]:
    """Filter roll berstatus LIAR (di luar kosakata) — untuk laporan data acuan, bukan untuk diubah otomatis."""
    return {"status": {"$nin": list(STATUSES)}}
