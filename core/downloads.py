"""RFC 6266 attachments: meaningful ASCII fallback and the original Arabic filename."""
import re
from pathlib import Path
from urllib.parse import quote
from flask import send_file


def attachment(path, fallback=None):
    path = Path(path)
    fallback = fallback or ("document" + path.suffix)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", fallback):
        raise ValueError("Unsafe fallback filename")
    response = send_file(str(path), as_attachment=True, download_name=fallback, conditional=False, max_age=0)
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(path.name, safe="")}')
    return response
