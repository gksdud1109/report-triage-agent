#!/bin/bash
# Postgres 초기화 훅: 컨테이너 최초 기동 시 1회 실행된다.
#
# `triage` DB는 postgres 공식 이미지가 POSTGRES_DB 값으로 자동 생성한다.
# 여기서는 Temporal auto-setup이 필요로 하는 DB 2개만 추가한다.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE DATABASE temporal;
  CREATE DATABASE temporal_visibility;
EOSQL
