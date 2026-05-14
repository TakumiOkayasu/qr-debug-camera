from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from websocket import WebSocket, create_connection


@dataclass
class CdpClient:
    websocket_url: str
    timeout: float = 2.0
    _next_id: int = 1
    _ws: WebSocket = field(init=False)

    def __post_init__(self) -> None:
        self._ws = create_connection(
            self.websocket_url,
            timeout=self.timeout,
            suppress_origin=True,
        )

    def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request_id = self._next_id
        self._next_id += 1
        self._ws.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))

        while True:
            message = json.loads(self._ws.recv())
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(message["error"].get("message", "CDP command failed"))
            return message.get("result")

    def close(self) -> None:
        self._ws.close()
