"""DOC-06 — unggahan dengan isi yang tidak cocok tipe (teks berekstensi .png/.jpg) ditolak ramah."""
import sys

import pytest

sys.path.insert(0, "C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend")
from services.storage_service import validate_upload  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


@pytest.mark.parametrize("name,ct,data", [("a.png", "image/png", PNG), ("a.jpg", "image/jpeg", b"\xff\xd8\xff\xe0" + b"0" * 12),
                                          ("a.pdf", "application/pdf", b"%PDF-1.7\n"), ("a.webp", "image/webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ")])
def test_valid_signatures_accepted(name, ct, data):
    assert validate_upload(name, ct, len(data), data[:16]) == ct


@pytest.mark.parametrize("name,ct", [("bad.jpg", "image/jpeg"), ("bad.png", "image/png"), ("bad.pdf", "application/pdf")])
def test_text_disguised_as_image_rejected(name, ct):
    data = b"ini bukan gambar sama sekali"
    with pytest.raises(ValueError, match="rusak"):
        validate_upload(name, ct, len(data), data[:16])
