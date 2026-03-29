"""Agent Socket Python client.

Provides an async WebSocket client for connecting to Agent Socket servers.
Handles authentication, message sending/receiving, and connection lifecycle.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Awaitable

import websockets
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger("agent_socket")

DEFAULT_HOST = "wss://as.agent-socket.ai"

MSG_TYPE_HEARTBEAT = "heartbeat"
MSG_TYPE_CONNECTED = "connected"


class AgentSocket:
    """Async client for Agent Socket.

    Usage::

        socket = AgentSocket("as/my_socket_id", api_token="your_token")

        @socket.on_message
        async def handle(sender: str, data: Any) -> None:
            print(f"From {sender}: {data}")

        await socket.connect()
        await socket.send("as/other_socket", {"hello": "world"})
        await socket.disconnect()

    Or as an async context manager::

        async with AgentSocket("as/my_socket_id", api_token="your_token") as socket:
            socket.on_message(handler)
            await socket.send("as/other_socket", "hello")
    """

    def __init__(
        self,
        socket_id: str,
        *,
        api_token: str,
        host: str = DEFAULT_HOST,
    ) -> None:
        self._socket_id = socket_id
        self._api_token = api_token
        self._host = host
        self._ws: ClientConnection | None = None
        self._recv_task: asyncio.Task | None = None
        self._message_handler: Callable[[str, Any], Awaitable[None]] | None = None
        self._heartbeat_handler: Callable[[Any], Awaitable[None]] | None = None
        self._connected = asyncio.Event()

    @property
    def socket_id(self) -> str:
        """The socket ID this client is connected as."""
        return self._socket_id

    @property
    def is_connected(self) -> bool:
        """Whether the client is currently connected."""
        return self._ws is not None and self._connected.is_set()

    def on_message(
        self, handler: Callable[[str, Any], Awaitable[None]]
    ) -> Callable[[str, Any], Awaitable[None]]:
        """Register a handler for incoming messages.

        The handler receives (sender_socket_id, data).
        Can be used as a decorator::

            @socket.on_message
            async def handle(sender: str, data: Any) -> None:
                ...
        """
        self._message_handler = handler
        return handler

    def on_heartbeat(
        self, handler: Callable[[Any], Awaitable[None]]
    ) -> Callable[[Any], Awaitable[None]]:
        """Register a handler for heartbeat messages.

        The handler receives the heartbeat data (or None if no custom data).
        Can be used as a decorator::

            @socket.on_heartbeat
            async def handle(data: Any) -> None:
                ...
        """
        self._heartbeat_handler = handler
        return handler

    async def connect(self) -> None:
        """Connect to the Agent Socket server."""
        url = f"{self._host}/{self._socket_id}"
        headers = {"Authorization": f"Bearer {self._api_token}"}

        self._ws = await websockets.connect(url, additional_headers=headers)
        self._connected.set()
        self._recv_task = asyncio.create_task(self._recv_loop())
        logger.info("connected as %s", self._socket_id)

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        self._connected.clear()
        if self._recv_task is not None:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            self._recv_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        logger.info("disconnected")

    async def send(self, to: str, data: Any) -> None:
        """Send a message to a socket or channel.

        Args:
            to: Target socket or channel ID (e.g. "as/abc123", "ch/xyz789").
            data: Message payload. Can be any JSON-serializable value.
        """
        if self._ws is None or not self._connected.is_set():
            raise RuntimeError("not connected")

        msg = json.dumps({"to": to, "data": data})
        await self._ws.send(msg)

    async def _recv_loop(self) -> None:
        """Read messages from the server and dispatch to handlers."""
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("received non-JSON message: %s", raw)
                    continue

                msg_type = msg.get("type")

                if msg_type == MSG_TYPE_HEARTBEAT:
                    if self._heartbeat_handler is not None:
                        await self._heartbeat_handler(msg.get("data"))
                    continue

                if msg_type == MSG_TYPE_CONNECTED:
                    continue

                sender = msg.get("from")
                data = msg.get("data")

                if sender is not None and self._message_handler is not None:
                    try:
                        await self._message_handler(sender, data)
                    except Exception:
                        logger.exception(
                            "error in message handler for message from %s", sender
                        )

        except websockets.ConnectionClosed:
            logger.info("connection closed by server")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("unexpected error in receive loop")
        finally:
            self._connected.clear()

    async def wait_until_disconnected(self) -> None:
        """Block until the connection is closed."""
        if self._recv_task is not None:
            await self._recv_task

    async def __aenter__(self) -> AgentSocket:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()
