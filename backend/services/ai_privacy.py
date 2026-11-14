"""AG-T2 (AG-06, K-43) — nama pihak tidak dikirim ke penyedia model; gaji tidak pernah dikirim.

Dipasang di dua titik: hasil alat sebelum dikirim ke penyedia, dan konteks sesi (nama pengguna → "Pengguna"). Urutan
pada jawaban: teks model → pemeriksa angka (atas teks bersamaran, sama dengan yang dilihat model) → `unmask` → kirim
ke layar. Peta samaran per sesi disimpan di `ai_chat_sessions.alias_map` (hanya di server; tidak dikirim ke penyedia
maupun ke layar).

Yang disamarkan = nama pihak (pelanggan, pemasok, sales/karyawan, pihak lain). Nama PT sendiri dan nominal tetap
dikirim (ASUMSI unit). Nama yang diketik pengguna hanya tersamar bila sudah ada di peta sesi (batas yang diketahui).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

#: Awalan kode per jenis pihak (spesifikasi): tiga digit berurutan per sesi per awalan.
PREFIX = {"customer": "PLG", "supplier": "PMS", "employee": "KRY", "other": "PHK"}
#: Kunci hasil alat yang nilainya nama pihak → jenisnya.
PARTY_KEYS: Dict[str, str] = {
    "customer": "customer", "customer_name": "customer", "pelanggan": "customer", "bill_to_name": "customer",
    "supplier": "supplier", "supplier_name": "supplier", "vendor_name": "supplier", "makloon_name": "supplier",
    "sales_person": "employee", "sales_name": "employee", "assigned_sales_name": "employee", "salesman": "employee",
    "employee": "employee", "employee_name": "employee", "karyawan": "employee", "user_name": "employee",
    "created_by": "employee", "created_by_name": "employee", "approved_by": "employee", "approved_by_name": "employee",
    "posted_by": "employee", "requested_by_name": "employee", "driver_name": "employee",
    "party": "other", "party_name": "other", "counterparty": "other", "counterparty_name": "other",
    "payer_name": "other", "payee_name": "other", "recipient_name": "other", "account_holder": "other",
}
#: `find_entities` — kandidat ber-`name` yang merupakan pihak.
_FIND_KIND = {"customer": "customer", "supplier": "supplier", "sales_person": "employee"}
_NOT_A_NAME = {"", "-", "—", "sistem", "system", "uji", "tanpa sales", "tanpa pelanggan", "(kosong)"}
_CODE_RE = re.compile(r"\b(PLG|PMS|KRY|PHK)-(\d{3,})\b")
_SALARY_RE = re.compile(r"(salary|gaji|upah|wage|take_home|tunjangan|allowance|thp$)", re.I)


def drop_salary(obj: Any) -> Any:
    """Buang setiap kunci gaji (gaji pokok, tunjangan, upah, THP) — selalu, di semua mode."""
    if isinstance(obj, dict):
        return {k: drop_salary(v) for k, v in obj.items() if not (isinstance(k, str) and _SALARY_RE.search(k))}
    if isinstance(obj, list):
        return [drop_salary(v) for v in obj]
    return obj


class NameMasker:
    def __init__(self, mapping: Optional[Dict[str, Any]] = None) -> None:
        m = mapping or {}
        #: nama asli → kode, kode → nama asli; penghitung per awalan.
        self.by_name: Dict[str, str] = dict(m.get("by_name") or {})
        self.by_code: Dict[str, str] = {c: n for n, c in self.by_name.items()}
        self.counters: Dict[str, int] = {k: int(v) for k, v in (m.get("counters") or {}).items()}
        self.changed = False

    # ── peta ────────────────────────────────────────────────────────────────────────────────────────────────────────
    def code_for(self, name: str, kind: str) -> str:
        key = str(name).strip()
        if key in self.by_name:
            return self.by_name[key]
        prefix = PREFIX.get(kind, PREFIX["other"])
        n = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = n
        code = f"{prefix}-{n:03d}"
        self.by_name[key] = code
        self.by_code[code] = key
        self.changed = True
        return code

    def export(self) -> Dict[str, Any]:
        return {"by_name": dict(self.by_name), "counters": dict(self.counters)}

    # ── samarkan ────────────────────────────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_name(v: Any) -> bool:
        return isinstance(v, str) and v.strip().lower() not in _NOT_A_NAME and not _CODE_RE.fullmatch(v.strip())

    def _collect(self, obj: Any) -> None:
        """Lintasan 1: nilai pada kunci nama pihak → kode (urutan kemunculan = urutan nomor)."""
        if isinstance(obj, dict):
            kind = _FIND_KIND.get(obj.get("kind")) if isinstance(obj.get("kind"), str) else None
            for k, v in obj.items():
                if k in PARTY_KEYS and self._is_name(v):
                    self.code_for(v, PARTY_KEYS[k])
                elif kind and k == "candidates" and isinstance(v, list):
                    for c in v:
                        if isinstance(c, dict) and self._is_name(c.get("name")):
                            self.code_for(c["name"], kind)
                self._collect(v)
        elif isinstance(obj, list):
            for v in obj:
                self._collect(v)

    def mask_text(self, text: str) -> str:
        """Nama yang sudah dikenal di dalam teks → kode (nama terpanjang dulu)."""
        if not isinstance(text, str) or not text or not self.by_name:
            return text
        out = text
        for name in sorted(self.by_name, key=len, reverse=True):
            if len(name) >= 3 and name in out:
                out = out.replace(name, self.by_name[name])
        return out

    def _replace(self, obj: Any, kind: Optional[str] = None) -> Any:
        if isinstance(obj, dict):
            k_kind = _FIND_KIND.get(obj.get("kind")) if isinstance(obj.get("kind"), str) else None
            out = {}
            for k, v in obj.items():
                if k == "candidates" and k_kind and isinstance(v, list):
                    out[k] = [{**c, "name": self.by_name.get(str(c.get("name")).strip(), c.get("name"))}
                              if isinstance(c, dict) else c for c in v]
                    out[k] = self._replace(out[k])
                else:
                    out[k] = self._replace(v)
            return out
        if isinstance(obj, list):
            return [self._replace(v) for v in obj]
        if isinstance(obj, str):
            return self.mask_text(obj)
        return obj

    def mask(self, obj: Any) -> Any:
        """Nilai pada kunci nama pihak → kode; nama yang sudah dikenal di dalam teks lain → kode."""
        self._collect(obj)
        return self._replace(obj)

    # ── kembalikan ──────────────────────────────────────────────────────────────────────────────────────────────────
    def unmask(self, text: str) -> str:
        if not isinstance(text, str) or not text:
            return text
        return _CODE_RE.sub(lambda m: self.by_code.get(m.group(0), m.group(0)), text)

    def unmask_obj(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self.unmask_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.unmask_obj(v) for v in obj]
        return self.unmask(obj) if isinstance(obj, str) else obj


async def masker_for(session: Dict[str, Any], entity_ids: List[str]) -> Optional[NameMasker]:
    """`None` = penyamaran mati untuk SEMUA PT dalam cakupan; menyala bila salah satu PT menyalakannya
    (`ai.samarkan_nama`, berlapis global → PT)."""
    from services.config_resolver import value_of
    for eid in [e for e in (entity_ids or []) if e and e != "all"] or [None]:
        if await value_of("ai.samarkan_nama", {"entity_id": eid} if eid else None):
            return NameMasker((session or {}).get("alias_map"))
    return None
