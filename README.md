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
