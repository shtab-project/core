#!/bin/sh
# Создаёт базу и пользователя Shtab Core (выполняется только при первом старте пустого volume)
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
	CREATE USER shtab WITH PASSWORD '$SHTAB_DB_PASS';
	CREATE DATABASE shtab OWNER shtab;
EOSQL
