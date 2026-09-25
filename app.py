"""Application factory and route wiring only. See CONTRIBUTING.md."""
import mimetypes
import os
import secrets
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from core.paths import RESOURCE_DIR, APP_VERSION


def create_app():
    # Windows registry MIME associations can override Python's font/woff2 default.
    # Keep bundled font responses identical across preview and installed WebView2.
    mimetypes.add_type("font/woff2", ".woff2")
    from services.bootstrap import initialize
    from data_access import database as db
    initialize()
    app = Flask(__name__, template_folder=str(RESOURCE_DIR / "templates"),
                static_folder=str(RESOURCE_DIR / "static"))
    secret = db.get_setting("session_secret")
    if not secret:
        secret = secrets.token_hex(32)
        db.set_setting("session_secret", secret)
    preview = os.environ.get("LOGISTICS_PREVIEW") == "1"
    app.config.update(SECRET_KEY=secret, TEMPLATES_AUTO_RELOAD=True,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=preview,
                      SESSION_COOKIE_SAMESITE="None" if preview else "Lax",
                      MAX_CONTENT_LENGTH=12 * 1024 * 1024,
                      DESKTOP=os.environ.get("LOGISTICS_DESKTOP") == "1")
    if preview:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    from core import web
    from routes import main
    from routes.rations import rations_bp
    from routes.letterhead import letterhead_bp
    from routes.backups import backups_bp
    from routes.recruits import recruits_bp
    from routes.tameedat import tameedat_bp
    from routes.calc2 import calc2_bp
    from routes.month_copy import copy_bp
    from routes.warehouses import warehouses_bp
    from routes.stores import stores_bp
    app.register_blueprint(copy_bp)
    web.register(app)
    main.register(app)
    for bp in (rations_bp, letterhead_bp, backups_bp, recruits_bp, tameedat_bp, calc2_bp,
               warehouses_bp, stores_bp):
        app.register_blueprint(bp)
    app.add_url_rule("/health", "health", lambda: {"status": "ready", "version": APP_VERSION})
    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
