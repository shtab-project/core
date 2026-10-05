"""Приложение поднимается, а MCP-эндпоинт отвечает и видит инструменты."""

import pytest
from fastapi.testclient import TestClient

from shtab.main import app

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "Host": "localhost:8000",
}


@pytest.fixture(scope="module")
def client():
    # Менеджер сессий MCP запускается один раз за процесс — один клиент на модуль.
    with TestClient(app, base_url="http://localhost:8000") as c:
        yield c


def test_health_and_mcp_tools(client):
    assert client.get("/health").json() == {"status": "ok"}

    init = client.post(
        "/mcp",
        headers=MCP_HEADERS,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        },
    )
    assert init.status_code == 200, init.text

    listed = client.post(
        "/mcp",
        headers={**MCP_HEADERS, "MCP-Protocol-Version": "2025-06-18"},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    assert listed.status_code == 200, listed.text
    for name in ("list_tasks", "add_task", "move_task"):
        assert name in listed.text


def test_mcp_rejects_foreign_host(client):
    r = client.post("/mcp", headers={**MCP_HEADERS, "Host": "evil.example"}, json={})
    assert r.status_code in (400, 403, 421)
