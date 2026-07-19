# Excel Parser

## Local setup

1. Create and activate a Python 3.14 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `config/local.example.yaml` to `config/local.yaml` and update the MySQL settings.
4. Start the service with `python main.py`.

Swagger documentation is available at `http://127.0.0.1:8000/docs`.

`main.py` is the local startup entry point; `application.py` assembles and
exports the Sanic application for deployment and integration.

Run tests with `python -m pytest -q`.

## Configuration

- `APP_ENV` selects which `config/{env}.yaml` file is loaded (default
  `local`). `APP_CONFIG_DIR` overrides the config directory location when it
  does not live at the project root.
- String values support `${ENV_VAR}` interpolation (e.g.
  `password: ${DB_PASSWORD}`), expanded at load time; unset variables expand
  to an empty string so missing secrets fail validation instead of silently
  passing through.
- Outside the `local` environment, `db.password` must be non-empty and
  `jwt.secret` must be at least 32 characters, or startup aborts.

### Initial admin password

The seeded `admin` account takes its initial password from
`admin.default_password` in the active config file (which may itself be
`${ADMIN_PASSWORD}`). In `local`, leaving it empty falls back to `admin123`
with a warning log; any other environment refuses to start without it.

## Database migrations

The service applies committed Tortoise migrations during startup. It never
creates or alters tables from the live model definitions.

After changing a Tortoise model, create and inspect a migration locally:

```powershell
tortoise makemigrations --name describe_the_change
tortoise sqlmigrate models <migration_name>
```

Apply migrations manually when needed with `tortoise migrate`; normal service
startup also applies pending migrations before seeding default data.

For a database created by the old `generate_schemas` startup flow, back up the
database first, then mark the committed initial migration as applied once:

```powershell
tortoise migrate models 0001_initial --fake
```

New databases should run `tortoise migrate` normally.
