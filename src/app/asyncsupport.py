import asyncio
import threading

# `databases`/asyncpg binds its connection pool to the event loop that created
# it. Flask is a WSGI framework, so there is no ambient loop to reuse and its
# native async view support spins up a fresh loop per call, which would hand
# every request a pool bound to a dead loop. One long-lived loop on a
# background thread gives the pool the single stable loop it expects.
_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, name="app-event-loop", daemon=True)
_thread.start()


def run_async(coro):
    """Run ``coro`` on the application event loop and return its result."""
    return asyncio.run_coroutine_threadsafe(coro, _loop).result()
