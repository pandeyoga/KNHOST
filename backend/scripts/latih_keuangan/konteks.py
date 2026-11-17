"""Konteks bersama data latihan keuangan: peserta, akun, pelanggan, pemasok, dan pembantu dokumen."""
from dataclasses import dataclass, field
from typing import Any, Dict, List

from db import db
from scripts.demo_api import Api, ApiError
from scripts.seed_demo_transaksi_kn import MAIL, Ctx

KSC = "ent_ksc"
SANDI = "demo12345"
PREFIX = "Latihan"          # semua data latihan diawali "Latihan NN" supaya mudah dicari & dibersihkan
TANDA = "PELATIHAN_KEUANGAN_2026_11"


@dataclass
class Peserta:
    no: int
    kartu: Dict[str, Any] = field(default_factory=dict)

    @property
    def kode(self) -> str:
        return f"{self.no:02d}"

    @property
    def email(self) -> str:
        return f"finance.latih{self.kode}{MAIL}"

    @property
    def nama(self) -> str:
        return f"Peserta Keuangan {self.kode}"

    @property
    def pelanggan(self) -> str:
        return f"{PREFIX} {self.kode} · Toko Kain Peserta {self.kode}"

    @property
    def pemasok(self) -> str:
        return f"{PREFIX} {self.kode} · Pemasok Grey Peserta {self.kode}"


class LatihCtx(Ctx):
    """Ctx demo + pembantu khusus latihan. `self.api` = klien ASGI dalam-proses (endpoint resmi)."""

    def __init__(self, api: Api, cst: str):
        super().__init__(api, cst)
        self.entity = KSC

    async def admin(self):
        return await self.api.system_admin()

    async def u(self, key: str):
        """Sesi akun demo (`sales`, `warehouse`, `mdquality`, …). VPS: akun yang belum ada DIBUAT (peran/PT sama dengan
        data demo lengkap); akun yang sandinya sudah diganti pemilik TIDAK diubah — dipakai sesi sementara bertanda
        `demo_seed` (dihapus saat skrip selesai), sama seperti sesi admin internal."""
        email = key if "@" in key else key + MAIL
        if email in self.api._sessions:
            return self.api._sessions[email]
        try:
            return await self.api.as_user(email)
        except ApiError:
            pass
        user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
        if not user:
            from scripts.seed_demo_lengkap_kn import accounts
            spec = next((a for a in accounts(self.cst) if a["email"] == email), None)
            if not spec:
                raise RuntimeError(f"Akun {email} tidak ada dan bukan akun demo yang dikenal.")
            adm = await self.admin()
            await adm.post("/users", {"name": spec["name"], "email": email, "role": spec["role"], "password": SANDI,
                                      "home_entity_id": spec["home"], "allowed_entity_ids": spec["allowed"]})
            try:
                return await self.api.as_user(email)
            except ApiError:
                user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
        if (user or {}).get("status") not in (None, "active"):
            raise RuntimeError(f"Akun {email} tidak aktif — aktifkan dulu di Pengaturan › Akun.")
        import secrets
        from datetime import datetime, timedelta, timezone

        from core_utils import new_id, now_iso
        from scripts.demo_api import Session
        token = secrets.token_urlsafe(32)
        await db.sessions.insert_one({"id": new_id("session"), "token": token, "user_id": user["id"], "created_at": now_iso(),
                                      "demo_seed": True,
                                      "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()})
        self.api._sessions[email] = Session(self.api.client, token, user)
        return self.api._sessions[email]

    async def peserta_user(self, p: Peserta):
        return await self.api.as_user(p.email)

    async def customer_of(self, p: Peserta) -> Dict[str, Any]:
        return await db.customers.find_one({"name": p.pelanggan}, {"_id": 0})

    async def supplier_of(self, p: Peserta) -> Dict[str, Any]:
        return await db.suppliers.find_one({"name": p.pemasok}, {"_id": 0})

    async def so(self, oid: str) -> Dict[str, Any]:
        return await db.sales_orders.find_one({"id": oid}, {"_id": 0})

    async def bank_ksc(self) -> Dict[str, Any]:
        return await db.bank_accounts.find_one({"entity_id": KSC, "account_type": "bank", "is_active": {"$ne": False}},
                                               {"_id": 0}, sort=[("created_at", 1)])

    async def tag(self, coll: str, doc_id: str, p: Peserta, peran: str) -> None:
        """Tandai dokumen latihan (untuk pembersihan & pelacakan) — tidak mengubah angka/status."""
        await db[coll].update_one({"id": doc_id}, {"$set": {"training_batch": TANDA, "training_peserta": p.kode,
                                                            "training_role": peran}})


def ringkas(rows: List[Dict[str, Any]]) -> str:
    return " · ".join(f"{k}={v}" for r in rows for k, v in r.items())
