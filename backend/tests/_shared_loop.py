"""Satu event loop untuk tes yang memanggil service async langsung (klien Motor global terikat loop pertama)."""
import asyncio

LOOP = asyncio.new_event_loop()


def run(coro):
    """Jalankan di loop tempat klien Motor global TERIKAT (modul lain bisa lebih dulu mengikatnya ke loop sendiri);
    bila loop itu sudah ditutup (mis. modul lain memakai `asyncio.run`), ikat ulang klien ke LOOP bersama."""
    try:
        from db import client
    except Exception:  # noqa: BLE001
        return LOOP.run_until_complete(coro)
    loop = getattr(client, "_io_loop", None)
    if loop is None or loop.is_closed():
        client._io_loop = LOOP
        loop = LOOP
    return loop.run_until_complete(coro)
