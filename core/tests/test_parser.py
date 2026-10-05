from datetime import date

import pytest

from shtab.models import Status
from shtab.notes.parser import TaskConflict, append_task, parse_tasks, set_status

PAGE = """# Проект Гидро

- [ ] Сверить смету #гидро [status: doing] [due: 2026-10-10]
- [x] Отправить КП #клиент
  * [ ] Вложенная [status: review]
- обычный пункт

```
- [ ] это код, не задача
```
"""


def test_parse_tasks():
    tasks = parse_tasks(PAGE)
    assert [t.title for t in tasks] == ["Сверить смету", "Отправить КП", "Вложенная"]
    first, second, nested = tasks
    assert first.status is Status.doing and first.due == date(2026, 10, 10)
    assert first.tags == ["гидро"] and first.line == 2
    assert second.done and second.status is Status.done
    assert nested.status is Status.review


def test_set_status_roundtrip():
    first = parse_tasks(PAGE)[0]
    text = set_status(PAGE, first.line, first.raw, Status.done)
    assert "- [x] Сверить смету #гидро [status: done] [due: 2026-10-10]" in text
    again = parse_tasks(text)[0]
    assert again.done and again.status is Status.done

    back = set_status(text, again.line, again.raw, Status.todo)
    assert parse_tasks(back)[0].status is Status.todo
    assert "- [ ] Сверить смету" in back


def test_set_status_finds_shifted_line():
    first = parse_tasks(PAGE)[0]
    shifted = "Новая строка сверху\n" + PAGE
    text = set_status(shifted, first.line, first.raw, Status.review)
    assert parse_tasks(text)[0].status is Status.review


def test_set_status_conflict():
    first = parse_tasks(PAGE)[0]
    edited = PAGE.replace("Сверить смету", "Сверить смету v2")
    with pytest.raises(TaskConflict):
        set_status(edited, first.line, first.raw, Status.done)


def test_append_task():
    text, line = append_task(
        "# Входящие", "Позвонить\nподрядчику", due=date(2026, 10, 9), tags=["#звонки"]
    )
    assert text.split("\n")[line] == "- [ ] Позвонить подрядчику #звонки [due: 2026-10-09]"
    assert parse_tasks(text)[0].line == line
