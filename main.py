"""Development entry point.

Run with: python main.py
"""

from app import app


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, single_process=True)
