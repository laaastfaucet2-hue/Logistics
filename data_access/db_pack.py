# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""دوال تغليف كارت الصنف — فُصلت عن db_warehouses (قاعدة الملف ≤1000 سطر)."""
from core import arabic_numbers as arnum
from data_access.packaging import pack_breakdown


def collect_pack_kinds():
    """قائمة أنواع التغليف: الثوابت + ما كتبه المستخدم (قاموس مشترك pack_kind)."""
    kinds = []
    from core.config import PACK_KINDS
    from data_access import database as db
    for kind in list(PACK_KINDS):
        if kind not in kinds:
            kinds.append(kind)
    for kind in db.vocab_list("pack_kind"):
        if kind not in kinds:
            kinds.append(kind)
    return kinds


def card_pack_rows(year, month, cycle, card):
    """صفوف الدفتر بالتغليف (توجيه ٢٨/٠٩ ليلًا): لكل حركة مضاف/منصرف/رصيد
    مفكّكين بعبوات الصنف — لتاب «٣ مخازن تغليف» ومرايا Excel."""
    from data_access import db_warehouses as _dw   # استيراد مؤجل — تجنّب الدوران
    specs = _dw.pack_specs_map(year, month, cycle).get(card["item"]["name"], {})
    kind = ""
    sp = {}
    if specs:
        kind = list(specs)[-1]
        sp = specs[kind] or {}
    unit = card["item"]["handle_unit"]

    def brk(q):
        if not q:
            return "—"
        return pack_breakdown(kind, sp.get("capacity"), sp.get("inner_count"),
                              sp.get("inner_capacity"), q, unit, "سائب",
                              inner_kind=sp.get("inner_kind")) or \
            "{} {}".format(arnum.fmt_qty(q), unit).strip()

    from core import egtime
    from datetime import date as _d

    def _wday_of(iso):
        try:
            return egtime.weekday_ar(_d.fromisoformat(str(iso)[:10]))
        except (TypeError, ValueError):
            return "—"

    rows = []
    opener = card.get("opener_row")
    if opener:
        opener.setdefault("wday", _wday_of(opener["date_iso"]))
        rows.append({"seq": "—", "wday": opener["wday"], "date_iso": opener["date_iso"],
                     "permit_no": "—", "label": "رصيد أول المدة",
                     "added": opener["added"], "added_pack": brk(opener["added"]),
                     "issued": 0, "issued_pack": "—",
                     "balance": opener["balance"], "balance_pack": brk(opener["balance"]),
                     "notes": opener.get("notes") or ""})
    i = 0
    for row in card["rows"]:
        if row["kind"] == "opener":
            continue
        i += 1
        row.setdefault("wday", _wday_of(row["date_iso"]))
        rows.append({"seq": i, "wday": row["wday"], "date_iso": row["date_iso"],
                     "permit_no": row.get("permit_no") or "—", "label": row.get("label") or "—",
                     "added": row["added"], "added_pack": brk(row["added"]),
                     "issued": row["issued"],
                     "issued_pack": brk(row["issued"]) if row["issued"] else "—",
                     "balance": row["balance"], "balance_pack": brk(row["balance"]),
                     "notes": row.get("notes") or ""})
    return rows
