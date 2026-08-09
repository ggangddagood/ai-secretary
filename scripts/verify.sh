#!/usr/bin/env bash
# 프로젝트 검증의 단일 진입점.
# /build, /review, execute.py가 모두 이 스크립트로 검증한다.
set -euo pipefail
cd "$(dirname "$0")/.."

ruff check .
ruff format --check .
pytest -q
