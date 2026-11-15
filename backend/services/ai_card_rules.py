"""AG-T5 — daftar larangan kartu tindakan asisten (`docs/blueprint/unit/AG-T5.md`, rancangan `08` §4.3).

Hal yang TIDAK boleh dilakukan lewat asisten, apa pun yang diminta model: tutup buku dan membukanya kembali, buka
periode, bagan & pemetaan akun, penyesuaian saldo persediaan / akun sementara, plafon & izin kredit, bebas/ubah denda,
eliminasi konsolidasi, pengguna/peran/izin, pengaturan (termasuk pengaturan asisten), mengatur atau menyetujui asisten
sendiri, dan menghapus data. Daftarnya di kode — bukan pengaturan — supaya tidak bisa dinyalakan dari layar.

    FORBIDDEN: (kode, pola path, metode, alasan)
        metode None  = semua metode tulis (POST · PUT · PATCH · DELETE)
        metode "*"   = semua metode, termasuk GET (baris L11: asisten tidak mengatur dirinya sendiri)
        metode "DELETE" = hanya metode itu

Ditegakkan di tiga tempat:
  1. `SelfApi.call` mode tulis memanggil `forbidden_reason` SEBELUM pemeriksaan lain dan menolak 403 berisi alasan
     baris; aplikasi tidak dipanggil.
  2. Saat `services/ai_cards.py` dimuat, tiap `write_path` tindakan terdaftar diperiksa `check_write_paths`: cocok
     dengan larangan, atau tidak ber-idempotensi (`idempotency.is_idempotent_path`) → pemuatan gagal.
  3. `ai_cards.prepare` untuk kode yang tidak terdaftar menjawab `reason_for_action` (alasan baris yang cocok dengan
     permintaan), selain itu pesan baku "tidak bisa dilakukan lewat asisten".

Menambah rute lain yang termasuk kategori di atas berarti menambah/menyesuaikan baris di sini.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional, Tuple

WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")
ALL_METHODS = "*"

#: (kode, pola path, metode atau None = semua metode tulis, alasan yang ditampilkan)
FORBIDDEN: Tuple[Tuple[str, str, Optional[str], str], ...] = (
    ("L1", r"^/api/finance/closing/(close$|[^/]+/(reopen|reclose)$)", None,
     "Tutup buku dan membukanya kembali hanya dilakukan di layar Tutup Buku."),
    ("L2", r"^/api/finance/period-unlocks", None,
     "Buka periode hanya diajukan dan diputus di layar Tutup Buku."),
    ("L3", r"^/api/gl/accounts", None, "Bagan akun hanya diubah di layar Buku Besar."),
    ("L4", r"^/api/gl/account-mappings", None, "Pemetaan akun hanya diubah di Pengaturan."),
    ("L5", r"^/api/gl/(inventory-opening-balance|suspense/reclass|sync)$", None,
     "Penyesuaian saldo persediaan dan akun sementara hanya dilakukan di layar Buku Besar."),
    # CR-T1 sudah ada di basis: pengajuan & putusan profil kredit masuk kategori yang sama (spesifikasi: "menambah
    # profil kredit (CR-T1) … berarti menambah baris di sini") — pola baris L6 diperluas, alasan sama.
    ("L6", r"^/api/(customers/[^/]+/(credit-override|credit-profile-requests)|credit-overrides/|"
           r"credit-profile-requests/)", None,
     "Plafon dan izin kredit hanya diputus di layar."),
    ("L7", r"^/api/penalties/[^/]+/(waive|adjust)$", None,
     "Membebaskan atau mengubah denda hanya dilakukan di layar."),
    ("L8", r"^/api/(finance/)?consolidation/", None,
     "Eliminasi konsolidasi hanya dilakukan di layar Konsolidasi."),
    ("L9", r"^/api/(users|access|auth)(/|$)", None, "Pengguna, peran, dan izin hanya diatur di Pengaturan."),
    ("L10", r"^/api/(config|settings|scheduler|admin)(/|$)", None,
     "Pengaturan, termasuk pengaturan asisten, hanya diubah di layar Pengaturan."),
    ("L11", r"^/api/ai/", ALL_METHODS, "Asisten tidak boleh mengatur atau menyetujui dirinya sendiri."),
    ("L12", r".*", "DELETE", "Asisten tidak menghapus data."),
    ("L13", r"/purge$", None, "Asisten tidak menghapus data."),
)
_COMPILED = tuple((code, re.compile(pat), meth, why) for code, pat, meth, why in FORBIDDEN)


def _applies(rule_method: Optional[str], method: str) -> bool:
    if rule_method == ALL_METHODS:
        return True
    if rule_method is None:
        return method in WRITE_METHODS
    return method == rule_method


def forbidden_rule(method: str, path: str) -> Optional[Tuple[str, str]]:
    """(kode, alasan) baris larangan pertama yang cocok, atau None. Path dicocokkan tanpa kueri."""
    m = (method or "").upper()
    p = (path or "").split("?", 1)[0]
    for code, rx, meth, why in _COMPILED:
        if _applies(meth, m) and rx.search(p):
            return code, why
    return None


def forbidden_reason(method: str, path: str) -> Optional[str]:
    """Alasan larangan untuk (metode, path), atau None bila boleh."""
    hit = forbidden_rule(method, path)
    return hit[1] if hit else None


def _sample(path: str) -> str:
    """Pola `write_path` (`/api/x/{id}/pay`) → contoh path nyata (`/api/x/x/pay`) untuk dicocokkan."""
    return re.sub(r"\{[a-z_]+\}", "x", path or "")


def check_write_paths(pairs: Iterable[Tuple[str, str, str]]) -> None:
    """Penegakan 2 — `pairs` = (kode tindakan, metode, pola path). Path terlarang atau tanpa idempotensi →
    `RuntimeError` (pemuatan `ai_cards` gagal, kartu tidak pernah bisa memanggil pintu itu)."""
    from idempotency import is_idempotent_path
    salah = []
    for code, method, path in pairs:
        contoh = _sample(path)
        hit = forbidden_rule(method, contoh)
        if hit:
            salah.append(f"{code}: {method} {path} cocok larangan {hit[0]}")
        if not is_idempotent_path(contoh):
            salah.append(f"{code}: {method} {path} tidak ber-idempotensi")
    if salah:
        raise RuntimeError("Tindakan kartu asisten melanggar daftar larangan: " + "; ".join(salah))


#: Penegakan 3 — kode tindakan yang tidak terdaftar dicocokkan dengan baris larangan lewat kata pada kodenya (urutan
#: = prioritas). Model yang mengarang kode (`period_close`, `user_delete`, …) mendapat alasan baris, bukan pesan umum.
ACTION_HINTS: Tuple[Tuple[str, str], ...] = (
    (r"(close|closing|reopen|reclose|tutup_buku|tutup_periode)", "L1"),
    (r"(unlock|buka_periode|period_open|open_period)", "L2"),
    (r"(account_mapping|gl_mapping|pemetaan)", "L4"),
    (r"(^|_)(coa|gl_account|account_(create|update|edit|delete)|(create|update|edit|delete)_account|bagan_akun)", "L3"),
    (r"(opening_balance|suspense|reclass|gl_sync|saldo_awal)", "L5"),
    (r"(credit|kredit|plafon)", "L6"),
    (r"(penalt|denda|waive)", "L7"),
    (r"(consolidat|konsolidasi|eliminat|eliminasi)", "L8"),
    (r"(^|_)(user|users|role|roles|permission|access|password|login|akun_pengguna|peran|izin)(_|$)", "L9"),
    (r"(config|setting|scheduler|admin|pengaturan)", "L10"),
    (r"(^|_)(ai|asisten|assistant|card|kartu)(_|$)|(approve|confirm|setujui)_(card|kartu|action|tindakan)", "L11"),
    (r"purge", "L13"),
    (r"(delete|hapus|remove)", "L12"),
)
_HINTS = tuple((re.compile(rx), code) for rx, code in ACTION_HINTS)
_BY_CODE: Dict[str, str] = {code: why for code, _p, _m, why in FORBIDDEN}


def reason_for_action(code: str, args: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Alasan larangan untuk permintaan kode yang tidak terdaftar: (1) isian `path` (+ `method`, bawaan POST) cocok
    dengan baris; (2) kata pada kode cocok dengan `ACTION_HINTS`. Selain itu None (pemanggil memakai pesan baku)."""
    a = args if isinstance(args, dict) else {}
    path = a.get("path")
    if isinstance(path, str) and path.startswith("/api/"):
        why = forbidden_reason(str(a.get("method") or "POST"), path)
        if why:
            return why
    c = str(code or "").strip().lower()
    for rx, rule in _HINTS:
        if rx.search(c):
            return _BY_CODE[rule]
    return None
