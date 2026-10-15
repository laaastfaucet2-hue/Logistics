# -*- coding: utf-8 -*-
# ⚠️ قاعدة إلزامية: لا يزيد أي ملف عن 1000 سطر — الترتيب المعماري موثّق في CONTRIBUTING.md
"""تبويبات إحصائيات المخازن — كل تبويب في ملف، وكلها تقرأ من سياق واحد (Ctx).

كل تبويب يُرجع شيئًا واحدًا: {"cards": [...], "tables": [...]}، والجدول الواحد ورقة
واحدة في الإكسل بنفس العنوان والأعمدة والصفوف (الشاشة = الطباعة = الإكسل).
"""
from core import egtime

from .. import facts as F
from .. import year as Y
from ..calc import EPS, coverage_days
from ..subtabs import period_text


def modules():
    """مفتاح التبويب → ملفه (التبويب يظهر عند اكتماله فقط)."""
    from . import (alerts, balances, compare, consumption, entities, expiry, movement, registry,
                   summary)
    return {"summary": summary, "balances": balances, "movement": movement, "expiry": expiry,
            "consumption": consumption, "entities": entities, "registry": registry,
            "alerts": alerts, "compare": compare}


def builders():
    return {key: module.build for key, module in modules().items()}


class Ctx:
    """سياق تبويب: السنة والشهر والنطاق والفلاتر + بيانات محسوبة مرة واحدة."""

    def __init__(self, year, month, scope="month", flt=None, today=None):
        self.year, self.month = int(year), int(month)
        self.scope = "year" if scope == "year" else "month"
        self.flt = flt or {"active": False}
        self.today = today or egtime.today()
        self._memo = {}

    def _get(self, name, fn):
        if name not in self._memo:
            self._memo[name] = fn()
        return self._memo[name]

    # ------------------------------------------------------------ النطاق
    @property
    def yearly(self):
        return self.scope == "year"

    @property
    def filtered(self):
        return bool(self.flt.get("active"))

    def period(self):
        return period_text(self.year, None if self.yearly else self.month)

    def f(self):
        return self._get("f", lambda: F.apply_filter(
            F.month_facts(self.year, self.month, self.today), self.flt))

    def yf(self):
        return self._get("yf", lambda: Y.year_facts(self.year, self.today, self.flt))

    def months(self):
        return self.yf()["months"] if self.yearly else [self.month]

    def has_data(self):
        return bool(self.yf()["months"]) if self.yearly else self.f()["has_data"]

    def ref(self):
        return self.yf()["ref"] if self.yearly else self.f()["ref"]

    def elapsed(self):
        return self.yf()["elapsed"] if self.yearly else self.f()["elapsed"]

    def targets(self):
        return self.yf()["targets"] if self.yearly else self.f()["targets"]

    def stores(self):
        return self.yf()["stores"] if self.yearly else self.f()["stores"]

    def closing_facts(self):
        """بيانات آخر الفترة: الشهر نفسه، أو آخر شهر فيه بيانات في السنة."""
        if not self.yearly:
            return self.f()
        yf = self.yf()
        return yf["facts"][yf["last"]] if yf["last"] else None

    def batches(self):
        last = self.closing_facts()
        return last["batches"] if last else []

    def live_batches(self):
        return [b for b in self.batches() if b["remaining"] > EPS]

    def packs(self):
        last = self.closing_facts()
        return last["packs"] if last else {}

    def lines(self):
        """سطور الحركة — وفي السنوي كل سطر يحمل شهره (month) لتمييز الإذون بين الشهور."""
        if not self.yearly:
            return self.f()["lines"]
        yf = self.yf()
        return [dict(line, month=m) for m in yf["months"] for line in yf["facts"][m]["lines"]]

    def shortfalls(self):
        if not self.yearly:
            return self.f()["shortfalls"]
        yf = self.yf()
        return [dict(s, month=m) for m in yf["months"] for s in yf["facts"][m]["shortfalls"]]

    # ------------------------------------------------------------ التجميع
    def keys(self):
        """(مخزن، صنف، وحدة) → opening/in/out/closing/carry — شهري أو سنوي بنفس الشكل."""
        def build():
            if self.yearly:
                return Y.year_keys(self.yf())
            out = {}
            for key, e in Y.keys_of(self.f()).items():
                out[key] = {"store": e["store"], "opening": e["opener"], "in": e["in"],
                            "out": e["out"], "closing": e["balance"], "carry": 0.0,
                            "in_n": e["in_n"], "out_n": e["out_n"], "months": {},
                            "carries": []}
            return out
        return self._get("keys", build)

    def item_keys(self):
        """(صنف، وحدة) → مجموع كل المخازن."""
        def build():
            out = {}
            for (_sid, item, unit), e in self.keys().items():
                agg = out.setdefault((item, unit), {"opening": 0.0, "in": 0.0, "out": 0.0,
                                                    "closing": 0.0, "carry": 0.0, "in_n": 0,
                                                    "out_n": 0, "stores": set(), "months": {}})
                for name in ("opening", "in", "out", "closing", "carry"):
                    agg[name] = round(agg[name] + e[name], 6)
                agg["in_n"] += e["in_n"]
                agg["out_n"] += e["out_n"]
                if e["closing"] > EPS:
                    agg["stores"].add(_sid)
                for month, cur in e["months"].items():
                    slot = agg["months"].setdefault(month, {"out": 0.0, "balance": 0.0,
                                                            "in": 0.0})
                    slot["out"] = round(slot["out"] + cur["out"], 6)
                    slot["in"] = round(slot["in"] + cur["in"], 6)
                    slot["balance"] = round(slot["balance"] + cur["balance"], 6)
            return out
        return self._get("item_keys", build)

    def cover_store(self, key):
        e = self.keys().get(key)
        return coverage_days(e["closing"], e["out"], self.elapsed()) if e else None

    def cover_item(self, key):
        e = self.item_keys().get(key)
        return coverage_days(e["closing"], e["out"], self.elapsed()) if e else None

    def metrics(self):
        """مؤشرات الفترة — أصفار لو السنة بلا شهور فيها بيانات."""
        return self._get("metrics", lambda: ((Y.year_metrics(self.yf()) or Y.empty_metrics())
                                             if self.yearly else Y.metrics(self.f())))

    def last_year_metrics(self):
        """نفس الشهر من السنة السابقة (للمقارنة الشهرية) — None لو غير موجود."""
        def build():
            from data_access import storage
            if self.yearly or (self.year - 1) not in storage.list_years() \
                    or not F.month_exists(self.year - 1, self.month):
                return None
            facts = F.apply_filter(F.month_facts(self.year - 1, self.month, self.today),
                                   self.flt)
            return Y.metrics(facts) if facts["has_data"] else None
        return self._get("last_year_metrics", build)

    def prev_metrics(self):
        """مؤشرات الفترة السابقة: الشهر السابق، أو السنة السابقة في النطاق السنوي."""
        def build():
            if self.yearly:
                prev = Y.prev_year_facts(self.year, self.today, self.flt)
                return Y.year_metrics(prev) if prev else None
            prev = Y.prev_month_facts(self.year, self.month, self.today, self.flt)
            return Y.metrics(prev) if prev and prev["has_data"] else None
        return self._get("prev_metrics", build)

    def nearest_expiry(self, sid=None, item=None, unit=None):
        """أقرب صلاحية على الدفعات اللي فيها رصيد فعلًا (بعد التفريدة)."""
        best = ""
        for b in self.live_batches():
            if not b["expiry"]:
                continue
            if sid is not None and b["store_id"] != sid:
                continue
            if item is not None and (b["item"], b["unit"]) != (item, unit):
                continue
            if not best or b["expiry"] < best:
                best = b["expiry"]
        return best
