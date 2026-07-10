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
