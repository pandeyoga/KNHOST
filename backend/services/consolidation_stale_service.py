"""consolidation_stale_service — deteksi entri eliminasi antar-PT yang BASI (Fase 4 · R6, G1-33).

Dipisah dari `consolidation_service.py` (berkas itu sudah > 500 baris). Baca murni: tidak menghapus atau
menghitung ulang apa pun — lihat docstring `stale_g6_eliminations` dan laporan R6 untuk alasannya.
"""
from typing import Any, Dict, List, Optional

from db import db


async def stale_g6_eliminations(elims: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Fase 4 · R6 (G1-33) — entri eliminasi OTOMATIS antar-PT yang dokumen sumbernya sudah tidak ada/tidak sah.

    Entri auto G-6 hanya diselaraskan saat transaksinya berubah lewat layanan (`interco_service` →
    `sync_g6_for_pair`) atau lewat tombol "Sinkron Antar-PT". Bila dokumen antar-PT dihapus/diubah DI LUAR layanan
    (mis. pembersihan data uji langsung ke DB), entrinya tetap ada dan laporan konsolidasi terus mengeliminasi
    angka yang dokumennya sudah hilang. Fungsi ini HANYA MENDETEKSI (baca murni, angka laporan tidak diubah):
    menghapus/menghitung ulang entri tanpa membereskan jurnal per-PT yang mungkin masih ada adalah keputusan
    akuntansi (lihat laporan R6), jadi layar cukup diberi peringatan + tombol sinkron yang sudah ada.
    """
    rows = elims if elims is not None else await db.intercompany_eliminations.find(
        {"source_g6_pair_id": {"$nin": [None, ""]}}, {"_id": 0}).to_list(5000)
    auto = [e for e in rows if e.get("source_g6_pair_id")]
    if not auto:
        return []
    live = {d["pair_id"] async for d in db.interco_transactions.find(
        {"pair_id": {"$in": list({e["source_g6_pair_id"] for e in auto})}, "role": "seller",
         "status": {"$nin": ["draft", "cancelled"]}}, {"_id": 0, "pair_id": 1})}
    stale = [e for e in auto if e["source_g6_pair_id"] not in live]
    if not stale:
        return []
    # Jurnal transaksi per-PT (`{pair}:seller|buyer|cogs|receipt`) yang MASIH tersisa untuk pair itu (dokumen hilang,
    # jurnal tidak): menentukan apakah entri aman dibersihkan lewat "Sinkron Antar-PT" (tanpa jurnal) atau butuh
    # pembersihan data dulu (jurnal yatim masih membentuk saldo IC-AR/IC-AP per PT yang sedang dieliminasi entri ini).
    import re as _re
    from services.gl_service import ACC_IC_AR
    pairs_rx = "|".join(_re.escape(e["source_g6_pair_id"]) for e in stale)
    gl: Dict[str, int] = {}
    async for j in db.journal_entries.find(
            {"source_type": "interco_transaction", "source_id": {"$regex": f"^({pairs_rx})(:|$)"},
             "status": "posted"}, {"_id": 0, "source_id": 1}):
        pid = str(j.get("source_id") or "").split(":", 1)[0]
        gl[pid] = gl.get(pid, 0) + 1
    out = []
    for e in stale:
        pid = e["source_g6_pair_id"]
        ic_ar = round(sum(float(ln.get("credit") or 0) for ln in e.get("lines") or []
                          if str(ln.get("account_code")) == ACC_IC_AR), 2)
        left = gl.get(pid, 0)
        out.append({"id": e.get("id"), "name": e.get("name", ""), "pair_id": pid,
                    "effective_date": e.get("effective_date", ""), "ic_ar_eliminated": ic_ar,
                    "gl_entries_left": left,
                    "reason": ("Dokumen antar-PT sumbernya sudah tidak ada atau batal/draf"
                               + (" — jurnal transaksinya MASIH ada (perlu pembersihan data, jangan hanya sinkron)"
                                  if left else " — jurnal transaksinya juga tidak ada (aman dibersihkan lewat Sinkron)"))})
    return out

