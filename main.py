"""Development entry point.

Run with: python main.py
"""

import os

from application import app

if __name__ == "__main__":
    app.run(
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "8000")),
        single_process=True,
    )
