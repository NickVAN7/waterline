#!/usr/bin/env bash
# Creates the test database next to the dev one, so tests never touch dev data. The official
# image runs this once, on first start with an empty data volume. The name matches
# TEST_DATABASE_NAME in backend/app/core/settings.py.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
	CREATE DATABASE waterline_test OWNER "$POSTGRES_USER";
SQL
