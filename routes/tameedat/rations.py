# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""معاينة وحفظ المقررات المخصصة على التأميدة — لقطة لا تغيّر جداول المقررات."""
import json
from flask import jsonify, request
from core.auth_core import login_required, current_context
from core import arabic_numbers as arnum
from flask import g
from data_access import months
from data_access import db_tameed_rations as snap
from services import ration_lines as rl

from . import tameedat_bp


@tameedat_bp.route("/rations/preview")
@login_required
def rations_preview():
    year, month = current_context(g.user["id"])
    months.init_month(year, month)
    section = request.args.get("section") or "tamween"
    if section not in ("tamween", "contractor"):
        return jsonify({"err": "قسم مقرر غير صالح"}), 400
    entity = request.args.get("entity") or ""
    target = request.args.get("target") or "main"
    day_from = arnum.parse_int(request.args.get("from")) or 1
    day_to = arnum.parse_int(request.args.get("to")) or day_from
    record_id = arnum.parse_int(request.args.get("record_id"))
    payload = snap.get_payload(year, month, record_id) if record_id else {}
    extra = request.args.get("draft")
    if extra:
        try:
            payload = json.loads(extra)
        except json.JSONDecodeError:
            pass
    over = rl.overrides_map(payload, target, section)
    lines = rl.build_lines(year, month, entity, section, day_from, day_to, over)
    return jsonify({"lines": lines, "section": section, "entity": entity})
