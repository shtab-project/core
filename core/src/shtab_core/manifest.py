"""Plugin manifest types, shared by schemas and services without import cycles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginPage:
    """A plugin page: UI route and Web Component name."""

    path: str
    element: str


@dataclass(frozen=True)
class PluginMenuItem:
    """A menu item the core renders in a slot."""

    slot: str
    title: str
    path: str
    order: int = 100
    icon: str | None = None


@dataclass(frozen=True)
class PluginFrontend:
    """The plugin's JS module and what it adds to the core UI."""

    entry: str
    pages: tuple[PluginPage, ...] = ()
    menu_items: tuple[PluginMenuItem, ...] = ()


@dataclass(frozen=True)
class Plugin:
    """Plugin description from its manifest, without install or runtime state."""

    id: str
    name: str
    version: str
    url: str
    backend_entrypoint: str
    frontend: PluginFrontend | None = None
    mcp_entrypoint: str | None = None
    release_ref: str | None = None
    release_commit: str | None = None
    migration_module: str | None = None
