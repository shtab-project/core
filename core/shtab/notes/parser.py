"""Разбор и правка задач в markdown в формате SilverBullet.

Задача — строка вида:
    - [ ] Сверить смету #гидро [status: doing] [due: 2026-10-10]

Атрибуты `[ключ: значение]` и теги `#тег` — родной синтаксис SilverBullet,
поэтому те же задачи видны и в его запросах на Space Lua.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from shtab.models import Status

TASK_RE = re.compile(r"^(?P<indent>\s*)(?P<bullet>[-*+]) \[(?P<mark>[ xX])\] (?P<body>.*\S)\s*$")
ATTR_RE = re.compile(r"\[(?P<key>[\w-]+):\s*(?P<value>[^\]\[]*)\]")
STATUS_ATTR_RE = re.compile(r"\[status:\s*[^\]\[]*\]", re.IGNORECASE)
TAG_RE = re.compile(r"(?<![\w/#])#([\w/-]+)")
FENCE = "```"


class TaskConflict(Exception):
    """Строка задачи в файле изменилась с момента индексации."""


@dataclass
class ParsedTask:
    line: int
    raw: str
    title: str
    done: bool
    status: Status
    due: date | None = None
    tags: list[str] = field(default_factory=list)


def parse_tasks(text: str) -> list[ParsedTask]:
    tasks: list[ParsedTask] = []
    in_code = False
    for i, raw in enumerate(text.split("\n")):
        if raw.lstrip().startswith(FENCE):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = TASK_RE.match(raw)
        if not m:
            continue
        body = m["body"]
        attrs = {a["key"].lower(): a["value"].strip() for a in ATTR_RE.finditer(body)}
        title = " ".join(TAG_RE.sub("", ATTR_RE.sub("", body)).split())
        done = m["mark"] in "xX"
        tasks.append(
            ParsedTask(
                line=i,
                raw=raw,
                title=title or body,
                done=done,
                status=_status(done, attrs.get("status")),
                due=_date(attrs.get("due")),
                tags=TAG_RE.findall(body),
            )
        )
    return tasks


def set_status(text: str, line: int, expected_raw: str, status: Status) -> str:
    """Вернуть текст файла, где у задачи выставлен статус (и чекбокс для done)."""
    lines = text.split("\n")
    idx = _locate(lines, line, expected_raw)
    m = TASK_RE.match(lines[idx])
    assert m  # _locate гарантирует совпадение с raw, а raw — задача
    attr = f"[status: {status}]"
    body = m["body"]
    body = (
        STATUS_ATTR_RE.sub(attr, body, count=1) if STATUS_ATTR_RE.search(body) else f"{body} {attr}"
    )
    mark = "x" if status is Status.done else " "
    lines[idx] = f"{m['indent']}{m['bullet']} [{mark}] {body}"
    return "\n".join(lines)


def append_task(
    text: str, title: str, *, due: date | None = None, tags: list[str] | None = None
) -> tuple[str, int]:
    """Дописать задачу в конец текста. Возвращает (новый текст, номер строки задачи)."""
    parts = ["- [ ]", " ".join(title.split())]
    parts += [f"#{t.lstrip('#')}" for t in tags or []]
    if due:
        parts.append(f"[due: {due.isoformat()}]")
    if text and not text.endswith("\n"):
        text += "\n"
    new_text = text + " ".join(parts) + "\n"
    return new_text, new_text.count("\n") - 1


def _locate(lines: list[str], line: int, expected_raw: str) -> int:
    if 0 <= line < len(lines) and lines[line] == expected_raw:
        return line
    # Строки могли сдвинуться: ищем ту же задачу, если она в файле одна такая.
    matches = [i for i, s in enumerate(lines) if s == expected_raw]
    if len(matches) == 1:
        return matches[0]
    raise TaskConflict("Задача изменилась в файле — нужна переиндексация")


def _status(done: bool, value: str | None) -> Status:
    if done:
        return Status.done
    try:
        return Status((value or "").lower())
    except ValueError:
        return Status.todo


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None
