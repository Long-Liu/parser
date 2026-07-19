# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `AGENTS.md` for the full project overview, architecture, commands, and
configuration rules — both files are kept in sync.

Quick facts:

- Building-cost Excel parsing and query API: Python 3.14, Sanic + TortoiseORM + MySQL.
- DDD bounded contexts under `contexts/`; composition root is
  `contexts/container.py`; entry points are `application.py` / `main.py`.
- Run: `python main.py` · Test: `python -m pytest -q` ·
  Migrations: `tortoise makemigrations` / `tortoise migrate`.
- Config: `config/{env}.yaml` via `APP_ENV` / `APP_CONFIG_DIR`, with
  `${ENV_VAR}` interpolation; `config/local.yaml` is git-ignored.
