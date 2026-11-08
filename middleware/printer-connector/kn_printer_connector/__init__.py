"""KN Printer Connector — jembatan ERP Kain Nusantara ↔ printer label RFID (Chainway CP30EN, ZPL lewat TCP 9100).

Berjalan di PC gudang (Windows, Python 3.11, hanya pustaka standar). Satu worker terisolasi per printer, ledger
SQLite lokal per printer, offline-first: hasil cetak tersimpan lokal dan dikirim saat ERP terjangkau; tidak ada
cetak ulang otomatis untuk label yang hasilnya tidak pasti.
"""
VERSION = "0.1.0-prep-f"
CONTRACT = "kn-printer-1"
