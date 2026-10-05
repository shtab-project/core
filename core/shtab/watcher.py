"""Следит за папкой заметок и ставит переиндексацию изменённых пространств.

Нужен, потому что SilverBullet пишет файлы напрямую, минуя ядро.
Запуск: python -m shtab.watcher
"""

import asyncio
import logging
import os
from pathlib import Path

from watchfiles import awatch

from shtab.config import settings
from shtab.notes.spaces import space_of
from shtab.worker import broker, reindex, reindex_all

log = logging.getLogger("shtab.watcher")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await broker.startup()
    settings.notes_root.mkdir(parents=True, exist_ok=True)
    await reindex_all.kiq()
    # На Docker Desktop (Windows/macOS) события ФС в bind-mount не доходят — нужен polling.
    polling = os.getenv("WATCHFILES_FORCE_POLLING", "").lower() in {"1", "true"}
    async for changes in awatch(settings.notes_root, force_polling=polling, debounce=800):
        spaces = {space_of(Path(p)) for _, p in changes if p.endswith(".md")}
        for scope, username in filter(None, spaces):
            log.info("reindex %s %s", scope, username or "")
            await reindex.kiq(scope, username)


if __name__ == "__main__":
    asyncio.run(main())
