"""Initialize local data; never seed operational/test data."""
import logging
from core import egtime
from data_access import database as db, storage, months, dataguard
from documents import xlsx_rations


def bootstrap_year_files(year):
    if db.get_setting(f"bootstrapped_{year}") == "1":
        return
    for month in range(1, 13):
        months.init_month(year, month)
        for section in ("tamween", "contractor"):
            xlsx_rations.ensure(year, month, section)
    db.set_setting(f"bootstrapped_{year}", "1")


def initialize():
    storage.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for event in dataguard.startup_guard():
        logging.getLogger(__name__).warning(event)
    db.init_db()
    storage.ensure_initialized(egtime.today().year)
    storage.sync_section_folders()
    for year in storage.list_years():
        bootstrap_year_files(year)
    dataguard.auto_backup("boot", min_minutes=720)
