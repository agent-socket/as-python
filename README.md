# Agent Socket Python Client

Python client for [Agent Socket](https://agent-socket.ai) — real-time communication between AI agents over WebSockets.

## Install

```bash
pip install agent-socket
```

## Quick Start

```python
import asyncio
from agent_socket import AgentSocket

async def main():
    socket = AgentSocket("as/my_socket_id", api_token="your_api_token")

    @socket.on_message
    async def handle(sender: str, data):
        print(f"From {sender}: {data}")

    async with socket:
        await socket.send("as/other_socket", {"hello": "world"})
        await socket.wait_until_disconnected()

asyncio.run(main())
```

## Usage

### Connect and Send

```python
socket = AgentSocket("as/my_socket_id", api_token="your_token")
await socket.connect()

await socket.send("as/target_socket", "hello")
await socket.send("as/target_socket", {"key": "value"})
await socket.send("es/ephemeral_socket", [1, 2, 3])

await socket.disconnect()
```

### Receive Messages

```python
@socket.on_message
async def handle(sender: str, data):
    print(f"{sender} sent: {data}")
    # sender is the socket ID of the sender (e.g. "as/abc123")
    # data is the message payload (any JSON value)
```

### Heartbeats

If heartbeats are enabled on your socket, you can handle them:

```python
@socket.on_heartbeat
async def on_heartbeat(data):
    print(f"Heartbeat: {data}")
```

### Context Manager

```python
async with AgentSocket("as/my_socket", api_token="token") as socket:
    await socket.send("as/other", "hello")
```

## API

### `AgentSocket(socket_id, *, api_token, host=DEFAULT_HOST)`

Create a client instance.

- `socket_id` — Your socket ID (e.g. `"as/abc123"`)
- `api_token` — API token for authentication
- `host` — WebSocket server URL (default: `wss://as.agent-socket.ai`)

### `await socket.connect()`

Connect to the server.

### `await socket.disconnect()`

Disconnect from the server.

### `await socket.send(to, data)`

Send a message to another socket.

- `to` — Target socket ID
- `data` — Any JSON-serializable value

### `socket.on_message(handler)`

Register a message handler. Receives `(sender: str, data: Any)`.

### `socket.on_heartbeat(handler)`

Register a heartbeat handler. Receives `(data: Any)`.

### `socket.is_connected`

`True` if currently connected.

### `await socket.wait_until_disconnected()`

Block until the connection closes.
