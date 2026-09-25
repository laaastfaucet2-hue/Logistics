"""The only source of official letterhead/signatures, scoped to one month."""
from data_access import months, storage

KEYS = ["lh_1", "lh_2", "lh_3", "lh_4", "sig_right_rank", "sig_right_name",
        "sig_left_rank", "sig_left_name", "logo_file"]


def get_conn(year, month):
    conn = months.get_db(year, month)
    conn.execute("CREATE TABLE IF NOT EXISTS month_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')")
    return conn


def get_all(year, month):
    conn = get_conn(year, month)
    try:
        saved = dict(conn.execute("SELECT key, value FROM month_settings"))
        return {key: saved.get(key, "") for key in KEYS}
    finally:
        conn.close()


def get_setting(year, month, key):
    return get_all(year, month).get(key, "")


def save(year, month, values):
    conn = get_conn(year, month)
    try:
        with conn:
            conn.executemany("INSERT OR REPLACE INTO month_settings(key,value) VALUES(?,?)",
                             [(key, str(value or "").strip()) for key, value in values.items() if key in KEYS])
    finally:
        conn.close()


def logo_path(year, month):
    name = get_setting(year, month, "logo_file")
    base = storage.letterhead_dir(year, month).resolve()
    if not name or name != __import__('pathlib').Path(name).name:
        return None
    path = base / name
    return path if path.is_file() else None


def template_vars(year, month):
    values = get_all(year, month)
    return {**values, "lh": [values[f"lh_{i}"] for i in range(1, 5)],
            "sig_right": (values["sig_right_rank"], values["sig_right_name"]),
            "sig_left": (values["sig_left_rank"], values["sig_left_name"]),
            "has_logo": bool(logo_path(year, month))}
