"""RF-11 — teks bebas di label ZPL di-encode lewat ^FH (hex escape) sehingga ^ ~ _ tidak pernah
menjadi perintah printer. Karakter kontrol dibuang; Unicode dikirim UTF-8 (^CI28)."""
import unicodedata

_SAFE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,:;/()#+-*=&%@!?'\"<>[]{}|")


def zpl_field(value, max_len: int = 60) -> str:
    """Isi ^FD aman: panggil bersama prefix '^FH_' pada field yang sama."""
    s = "".join(" " if unicodedata.category(ch)[0] == "C" else ch for ch in str(value or ""))
    s = " ".join(s.split())[:max_len]
    out = []
    for ch in s:
        if ch in _SAFE:
            out.append(ch)
        else:
            out.extend(f"_{b:02X}" for b in ch.encode("utf-8"))
    return "".join(out)
