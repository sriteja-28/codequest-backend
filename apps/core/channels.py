"""Bounded, best-effort WebSocket broadcasts.

`async_to_sync(group_send)` runs the send on a fresh event loop in the calling
thread. A wedged channel layer (or a rare asgiref threading deadlock) must never
hang the sync view that scheduled the broadcast, so every send runs on a
throwaway daemon thread, is wrapped in `asyncio.wait_for`, and the caller joins
it with a timeout. On the happy path the message is delivered before the caller
continues, exactly like a synchronous send; when the layer misbehaves the send
thread is abandoned — the request is never abandoned with it.
"""

import asyncio
import logging
import threading

from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def send_to_group(group: str, message: dict, *, send_timeout: float = 2.0, join_timeout: float = 3.0) -> bool:
    """`group_send` with a hard bound. Returns False when delivery could not be
    confirmed in time (the broadcast is best effort by contract)."""

    done = threading.Event()

    def _send():
        try:
            from channels.layers import get_channel_layer

            layer = get_channel_layer()
            if layer is None:
                return

            async def _go():
                await asyncio.wait_for(layer.group_send(group, message), send_timeout)

            async_to_sync(_go)()
        except Exception as exc:  # broadcasting must never break persistence
            logger.warning("Broadcast to %s failed: %s", group, exc)
        finally:
            done.set()

    threading.Thread(target=_send, name="ws-broadcast", daemon=True).start()
    return done.wait(join_timeout)
