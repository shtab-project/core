#!/bin/sh
# Выполняется один раз — при первом создании тома postgres-data.
# Каждой системе — своя БД и свой пользователь (правило плана: в чужие таблицы не лезем).
set -eu

create_db() {
  name="$1"
  password="$2"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE "$name" LOGIN PASSWORD '$password';
CREATE DATABASE "$name" OWNER "$name";
SQL
}

create_db authentik "$AUTHENTIK_DB_PASSWORD"
create_db shtab "$SHTAB_DB_PASSWORD"

# База для тестов ядра — владелец тот же пользователь shtab
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -c 'CREATE DATABASE shtab_test OWNER shtab;'
