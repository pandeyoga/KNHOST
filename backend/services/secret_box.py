"""KP-T8 (KP-15) — satu cara menyimpan rahasia (docs/blueprint/unit/KP-T8.md, bagian Server · Pembungkus rahasia).

Dipindahkan dari `integrations_service` (`_fernet`/`_enc`/`_dec`). Awalan `enc:v1:` dan variabel lingkungan
`KN_SECRETS_KEY` (kunci Fernet) TIDAK berubah, sehingga nilai yang sudah terbungkus tetap terbaca.

Aturan pakai:
- Rahasia yang harus DIKIRIM ke pihak luar (kunci penyedia AI, token WhatsApp) → `seal` saat simpan, `open` saat pakai.
  Tanpa `KN_SECRETS_KEY` nilai disimpan polos (perilaku sebelum KP-T8); nilai polos lama dibungkus saat pertama dibaca
  oleh pembacanya bila kunci sudah terpasang.
- Rahasia yang hanya DICOCOKKAN server (token mesin absen; kunci perangkat RFID memakai aturan yang sama di
  `rfid_ingest_service.hash_device_key`) → `hash_token`; nilai aslinya tidak pernah disimpan.
"""
from __future__ import annotations

import hashlib
import os

PREFIX = "enc:v1:"
PESAN_TANPA_KUNCI = "KN_SECRETS_KEY belum diisi — rahasia terenkripsi tidak bisa dibaca."


class SecretBoxError(RuntimeError):
    """Rahasia terbungkus tidak bisa dibuka (kunci belum terpasang atau berbeda)."""


def _fernet():
    key = (os.environ.get("KN_SECRETS_KEY") or "").strip()
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def available() -> bool:
    """`KN_SECRETS_KEY` terpasang."""
    return bool((os.environ.get("KN_SECRETS_KEY") or "").strip())


def is_sealed(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def seal(value: str) -> str:
    """Kosong, sudah terbungkus, atau kunci belum terpasang → apa adanya; selain itu `enc:v1:…`."""
    if not value or is_sealed(value):
        return value
    f = _fernet()
    if f is None:
        return value
    return PREFIX + f.encrypt(str(value).encode()).decode()


def open(value: str) -> str:  # noqa: A001 — nama mengikuti spesifikasi unit (pasangan `seal`)
    """Tidak terbungkus → apa adanya; terbungkus tanpa kunci (atau kunci lain) → `SecretBoxError`."""
    if not is_sealed(value):
        return value
    f = _fernet()
    if f is None:
        raise SecretBoxError(PESAN_TANPA_KUNCI)
    from cryptography.fernet import InvalidToken
    try:
        return f.decrypt(value[len(PREFIX):].encode()).decode()
    except InvalidToken as exc:
        raise SecretBoxError("KN_SECRETS_KEY berbeda dari kunci saat rahasia disimpan — isi ulang rahasianya.") from exc


def hash_token(value: str) -> str:
    """SHA-256 heksadesimal — untuk token yang hanya perlu dicocokkan."""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()
