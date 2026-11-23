"""Create or extend infra/.env from the .env.example template.

- Keys missing from .env are added; empty secrets get random values.
- Existing values are never overwritten, so the script is safe to rerun.
"""

import secrets
from pathlib import Path

INFRA = Path(__file__).resolve().parent.parent
example, target = INFRA / ".env.example", INFRA / ".env"

existing: set[str] = set()
if target.exists():
    for line in target.read_text("utf-8").splitlines():
        key, sep, _ = line.partition("=")
        if sep and not line.startswith("#"):
            existing.add(key.strip())

added: list[str] = []
for line in example.read_text("utf-8").splitlines():
    key, sep, value = line.partition("=")
    if not sep or line.startswith("#") or key in existing:
        continue
    if not value:
        value = secrets.token_urlsafe(50 if key == "AUTHENTIK_SECRET_KEY" else 32)
    added.append(f"{key}={value}")

if not target.exists():
    target.write_text("\n".join(added) + "\n", "utf-8", newline="\n")
    print(f"Created {target}")
elif added:
    text = target.read_text("utf-8")
    sep = "" if text.endswith("\n") else "\n"
    target.write_text(text + sep + "\n".join(added) + "\n", "utf-8", newline="\n")
    print(f"Added to {target}: {', '.join(a.split('=')[0] for a in added)}")
else:
    print(f"{target} is up to date")
