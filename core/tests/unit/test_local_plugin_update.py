"""Exercise plugin metadata updates using actual dataclass-based manifests."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from shtab_core.models import PluginRecord


@pytest.mark.parametrize("frontend", [True, False])
async def test_local_update_persists_serializable_frontend(session_factory, monkeypatch, frontend):
    script = Path(__file__).resolve().parents[2] / "scripts" / "update_local_plugins.py"
    spec = importlib.util.spec_from_file_location("local_plugin_update", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(module, "engine", AsyncMock())
    monkeypatch.setattr(module.sys, "argv", [str(script)])
    migrate = Mock()
    monkeypatch.setattr(module.subprocess, "run", migrate)
    manifests = {}
    async with session_factory.begin() as session:
        for plugin_id in ("notes", "todo"):
            session.add(PluginRecord(
                id=plugin_id, name="Old", version="0.0.1",
                url=f"https://github.com/shtab-project/{plugin_id}.git",
                backend_entrypoint=f"shtab_{plugin_id}.main:register", frontend=None,
            ))
            manifests[plugin_id] = {
                "id": plugin_id, "name": plugin_id, "version": "1.0.0",
                "url": f"https://github.com/shtab-project/{plugin_id}.git",
                "backend_entrypoint": f"shtab_{plugin_id}.main:register",
                "frontend": {
                    "entry": "frontend/index.js",
                    "pages": [{"path": f"/plugins/{plugin_id}", "element": f"shtab-{plugin_id}"}],
                    "menu_items": [],
                } if frontend else None,
            }
    original_read = Path.read_text

    def read_manifest(path, *args, **kwargs):
        if path.parent.parent == Path("/app/core/plugins"):
            return json.dumps(manifests[path.parent.name])
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_manifest)
    await module.main()
    async with session_factory() as session:
        for plugin_id in manifests:
            record = await session.get(PluginRecord, plugin_id)
            assert record.version == "1.0.0"
            assert record.frontend == manifests[plugin_id]["frontend"]
    assert migrate.call_count == 2
