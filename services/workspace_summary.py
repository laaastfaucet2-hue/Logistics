"""Real monthly counts for the workspace; no synthetic dashboard metrics."""
from core import egtime, dates
from data_access import months, db_rations, db_entities, db_recruits, db_letterhead, dataguard


def summarize(year, month):
    months.init_month(year, month)
    counts = {}
    for section in ("tamween", "contractor"):
        counts[section] = sum(len(db_rations.get_items(year, month, section, kind)[0])
                              for kind in ("summer", "winter", "ramadan"))
    values = db_letterhead.get_all(year, month)
    backups = dataguard.list_backups()
    latest = backups[0] if backups else None
    return {**counts, "recruits": len(db_recruits.list_recruits(year, month)),
            "entities": len(db_entities.list_entities(year, month)),
            "letterhead": values, "official_ready": bool(values["lh_1"]),
            "has_logo": bool(db_letterhead.logo_path(year, month)),
            "backup_count": len(backups), "latest_backup": latest,
            "backup_date": dates.format_datetime(egtime.from_timestamp(latest["mtime"])) if latest else "—"}
