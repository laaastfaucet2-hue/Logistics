"""Isolated real-browser server. Never points at the user's database/."""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    scratch = ROOT / ".arena"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="appearance-check-", dir=scratch) as folder:
        os.environ["LOGISTICS_DATA_DIR"] = str(Path(folder) / "database")
        os.environ.pop("LOGISTICS_PREVIEW", None)
        os.environ.pop("LOGISTICS_DESKTOP", None)
        from app import create_app
        from desktop.appearance import welcome_html
        from waitress import serve
        app = create_app()
        app.add_url_rule("/__test_scope", "test_scope", lambda: {"isolated_appearance_test": True})
        app.add_url_rule("/__welcome", "test_welcome", lambda: welcome_html(False))
        serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", "5001")), threads=6)


if __name__ == "__main__":
    main()
