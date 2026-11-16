# Локальное окружение

Из корня репозитория сгенерируйте `infra/.env` и запустите Docker Compose.

```bash
python infra/scripts/gen_env.py
docker compose -f infra/docker-compose.yml up -d --build
```

[Shtab](http://localhost:3000) · [Authentik](http://auth.shtab.localhost:9000/if/admin/).

Вход администратора Authentik использует имя `akadmin` и пароль `AUTHENTIK_BOOTSTRAP_PASSWORD` из `infra/.env`. PostgreSQL, Redis и установленные плагины хранятся в томах Docker.
