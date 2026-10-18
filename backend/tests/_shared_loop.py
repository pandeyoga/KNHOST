"""Satu event loop untuk tes yang memanggil service async langsung (klien Motor global terikat loop pertama)."""
import asyncio

LOOP = asyncio.new_event_loop()


def run(coro):
    return LOOP.run_until_complete(coro)
