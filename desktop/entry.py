"""PyInstaller entry point. Smoke mode never touches real user data or opens a GUI."""
import os
import sys
import tempfile
from pathlib import Path


def smoke(output):
    with tempfile.TemporaryDirectory(prefix="logistics-smoke-") as folder:
        os.environ["LOGISTICS_DATA_DIR"] = str(Path(folder) / "database")
        from app import create_app
        app = create_app()
        client = app.test_client()
        assert client.get("/health").status_code == 200
        assert client.get("/login").status_code == 200
        from desktop.appearance import welcome_html
        assert "data:font/woff2;base64," in welcome_html(False)
        for weight in ("Regular", "Medium", "SemiBold", "Bold"):
            font = client.get(f"/static/fonts/Changa-{weight}.woff2")
            assert font.status_code == 200 and font.data.startswith(b"wOF2")
        assert b"#f59e0b" in client.get("/static/css/theme.css").data
        assert client.post("/login", data={"username": "mostafa", "password": "779"}, follow_redirects=True).status_code == 200
        for path in ("/recruits/", "/letterhead/", "/rations/tamween/download-excel"):
            assert client.get(path).status_code == 200, path
        Path(output).write_text("SMOKE_OK", encoding="utf-8")


def main():
    if "--ui-smoke-test" in sys.argv:
        index = sys.argv.index("--ui-smoke-test")
        with tempfile.TemporaryDirectory(prefix="logistics-ui-", ignore_cleanup_errors=True) as folder:
            os.environ["LOGISTICS_DATA_DIR"] = str(Path(folder) / "database")
            from desktop.launcher import run
            run(ui_smoke=sys.argv[index + 1])
        return
    if "--smoke-test" in sys.argv:
        index = sys.argv.index("--smoke-test")
        output = sys.argv[index + 1]
        try:
            smoke(output)
        except Exception:
            import traceback
            Path(output).write_text("SMOKE_FAILED\n" + traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1)
        return
    if sys.platform != "win32":
        raise SystemExit("Desktop builds target Windows 10/11 x64. Use python app.py for the web preview.")
    from desktop.launcher import run
    run()


if __name__ == "__main__":
    main()
