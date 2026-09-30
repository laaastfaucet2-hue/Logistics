"""Validate recruit date fields before any record or attachment is written."""
from core import dates

DATE_LABELS = {
    "service_start": "تاريخ دخول الخدمة",
    "service_end": "تاريخ انتهاء الخدمة",
    "cert_date": "تاريخ الشهادة الصحية",
    "cert_expiry": "تاريخ انتهاء الشهادة الصحية",
}


def normalize(data):
    values = dict(data)
    if not values.get("has_cert"):
        values.update(cert_date="", cert_expiry="", cert_photo="")
    for field, label in DATE_LABELS.items():
        try:
            values[field] = dates.to_iso(values.get(field, ""))
        except ValueError as exc:
            raise ValueError(f"{label}: {exc}") from exc
    for start, end in (("service_start", "service_end"), ("cert_date", "cert_expiry")):
        if values[start] and values[end] and values[end] < values[start]:
            raise ValueError(f"{DATE_LABELS[end]} لا يجوز أن يسبق {DATE_LABELS[start]}")
    return values
