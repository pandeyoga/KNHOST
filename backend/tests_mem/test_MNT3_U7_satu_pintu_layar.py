"""MN-T3 U7 (statik, sesudah serah-terima b) — di `frontend/src` (tanpa berkas uji) pemanggil `POST /ar-receipts`
(kwitansi), pintu bayar pemasok (`/vendor-bills/{id}/pay`, `/contra-bons/{id}/pay`, `/contra-bons/{id}/pay-from-bank-line`)
dan `simulate-payment` masing-masing: SATU berkas (form "Terima pembayaran pelanggan"), SATU berkas (form "Bayar
pemasok"), NOL.

Hitung di kode lama (`8dee8c6`): kwitansi = 1 berkas (`crm/ARReceiptModal.jsx`, bukan form baru); bayar pemasok = 3
berkas (`VendorBillDetailPanel.jsx`, `contrabon/PayModal.jsx`, `bank/ReconContraBonModal.jsx`); simulasi = 0 (PK-19).
"""
import os
import re

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
KWITANSI = re.compile(r"(?:post|moneyPost|offlinePost)\(\s*`\$\{API\}/ar-receipts`")   # tulis, bukan baca
BAYAR = re.compile(r"`\$\{API\}/(?:vendor-bills|contra-bons)/\$\{[^}]+\}/pay(?:`|-from-bank-line)")
SIMULASI = re.compile(r"simulate-payment")
KOMENTAR = re.compile(r"/\*.*?\*/|(?<![:\"'`])//[^\n]*", re.S)


def _berkas(pola):
    hasil = set()
    for akar, _dirs, files in os.walk(SRC):
        if "__tests__" in akar.split(os.sep):
            continue
        for f in files:
            if not f.endswith((".js", ".jsx")):
                continue
            p = os.path.join(akar, f)
            teks = KOMENTAR.sub("", open(p, encoding="utf-8").read())
            if pola.search(teks):
                hasil.add(os.path.relpath(p, SRC).replace(os.sep, "/"))
    return sorted(hasil)


def test_MNT3_U7_satu_pemanggil_kwitansi():
    assert _berkas(KWITANSI) == ["features/finance/payments/ReceivePaymentModal.jsx"]


def test_MNT3_U7_satu_pemanggil_bayar_pemasok():
    assert _berkas(BAYAR) == ["features/finance/payments/PaySupplierModal.jsx"]


def test_MNT3_U7_tanpa_simulasi_bayar():
    assert _berkas(SIMULASI) == []
