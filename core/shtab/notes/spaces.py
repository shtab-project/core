"""Пространства заметок на диске.

notes_root/
  shared/            — общее пространство (один экземпляр SilverBullet на всех)
  users/<username>/  — личное пространство (свой экземпляр SilverBullet на человека)
"""

import re
from pathlib import Path

from shtab.config import settings
from shtab.models import Scope

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
INBOX = "Inbox.md"


def space_root(scope: Scope, username: str | None) -> Path:
    if scope is Scope.shared:
        return settings.notes_root / "shared"
    if not username or not USERNAME_RE.match(username) or username in {".", ".."}:
        raise ValueError(f"Недопустимое имя пользователя: {username!r}")
    return settings.notes_root / "users" / username


def safe_join(root: Path, rel: str) -> Path:
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Путь вне пространства: {rel!r}")
    return path


def iter_pages(root: Path):
    """Markdown-страницы пространства, без служебных папок (.git, _plug и т.п.)."""
    if not root.is_dir():
        return
    for file in sorted(root.rglob("*.md")):
        rel = file.relative_to(root)
        if any(part.startswith((".", "_")) for part in rel.parts):
            continue
        yield rel.as_posix(), file


def space_of(path: Path) -> tuple[Scope, str | None] | None:
    """По пути изменённого файла понять, какое пространство переиндексировать."""
    try:
        parts = path.resolve().relative_to(settings.notes_root.resolve()).parts
    except ValueError:
        return None
    if parts[:1] == ("shared",):
        return Scope.shared, None
    if len(parts) >= 2 and parts[0] == "users" and USERNAME_RE.match(parts[1]):
        return Scope.personal, parts[1]
    return None
