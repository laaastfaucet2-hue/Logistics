"""Explicit, previewed monthly copying and legacy import endpoints."""
from flask import Blueprint, request, render_template, g, redirect, url_for
from core.auth_core import login_required, current_context
from core import arabic_numbers as arnum
from core.config import MONTH_NAMES
from services import month_copy, legacy_months
from services.document_refresh import refresh_month

copy_bp = Blueprint("month_copy", __name__, url_prefix="/month-copy")


def _back(kind, source, **messages):
    return redirect(url_for("recruits.page" if kind == "registry" else "letterhead.page",
                            sid=getattr(g, "sid", None), year=source[0], month=source[1], **messages))


@copy_bp.route("/<kind>", methods=["POST"])
@login_required
def copy(kind):
    source = current_context(g.user["id"])
    ids = None
    try:
        if request.form.get("scope") == "selected":
            ids = [arnum.parse_int(value) for value in request.form.getlist("recruit_ids")]
        month_value = request.form.get("target_month", "")
        month = MONTH_NAMES.index(month_value) + 1 if month_value in MONTH_NAMES else arnum.parse_int(month_value)
        target = arnum.parse_int(request.form.get("target_year")), month
        plan = month_copy.preview(kind, source, target, ids)
        if request.form.get("confirmed") == "1":
            result = month_copy.execute(kind, source, target, request.form.get("fingerprint"), ids,
                                        replace=request.form.get("replace") == "1")
            try:
                refresh_month(*target)
            except (OSError, ValueError):
                return _back(kind, source, err="تم نسخ البيانات؛ أغلق ملفات الوجهة المفتوحة وأعد تنزيل مستنداتها")
            message = "تم النسخ كبيانات مستقلة؛ أُضيف {} وتُرك {} موجودًا دون تعديل".format(
                arnum.to_arabic_indic(result["added"]), arnum.to_arabic_indic(result["skipped"]))
            return _back(kind, source, ok=message)
        return render_template("copy_confirm.html", kind=kind, source=source, target=target,
                               source_label=f"{MONTH_NAMES[source[1]-1]} {arnum.to_arabic_indic(source[0])}",
                               target_label=f"{MONTH_NAMES[target[1]-1]} {arnum.to_arabic_indic(target[0])}",
                               plan=plan, ids=ids)
    except (ValueError, OSError) as exc:
        return _back(kind, source, err=str(exc))


@copy_bp.route("/legacy/<kind>", methods=["POST"])
@login_required
def legacy(kind):
    source = current_context(g.user["id"])
    if request.form.get("confirmed") != "1":
        return _back(kind, source, err="الاستيراد يحتاج تأكيدًا صريحًا")
    try:
        legacy_months.import_to_month(kind, *source, replace=request.form.get("replace") == "1")
        refresh_month(*source)
        return _back(kind, source, ok="استُورد المصدر القديم لهذا الشهر فقط؛ الأصل محفوظ والنسخة الاحتياطية متاحة")
    except (ValueError, OSError) as exc:
        return _back(kind, source, err=str(exc))
