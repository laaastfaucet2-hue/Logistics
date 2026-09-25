"""Refresh only the affected month's official files."""
from documents import xlsx_rations, letterhead_docx, docx_recruits


def refresh_month(year, month):
    letterhead_docx.rebuild(year, month)
    for section in ("tamween", "contractor"):
        xlsx_rations.rebuild(year, month, section)
    docx_recruits.rebuild_month(year, month)
