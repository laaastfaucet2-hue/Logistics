"""طباعة رسمية: الدباجة أعلى الصفحة، التوقيعات أسفلها، زر في كل تبويب."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRINT_PAGES = [
    "/dashboard", "/rations/tamween", "/rations/contractor?tab=dist", "/letterhead/",
    "/recruits/", "/recruits/?tab=journal", "/recruits/?tab=present", "/recruits/?tab=leaves",
    "/recruits/?tab=absent", "/recruits/?tab=other", "/recruits/?tab=stats", "/backups/",
    "/tameedat/", "/tameedat/?tab=momoda", "/tameedat/?tab=dict", "/tameedat/?tab=report",
    "/calc2/",
]


def test_print_css_hides_chrome_and_shows_letterhead():
    css = (ROOT / "static/css/print.css").read_text(encoding="utf-8")
    assert "@media print" in css
    for sel in (".windowbar", ".toast", ".flash", ".sidebar", ".topbar", ".bell-wrap"):
        assert sel in css
    assert ".app-print-head" in css and ".app-print-foot" in css
    assert "body.own-letterhead" in css


def test_base_injects_print_chrome_at_main_edges():
    html = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    assert "css/print.css" in html
    assert "official_print_head.html" in html
    assert "official_print_foot.html" in html
    assert "partials/print_btn.html" in html
    head_at = html.index("official_print_head")
    content_at = html.index("{% block content %}")
    foot_at = html.index("official_print_foot")
    assert head_at < content_at < foot_at


def test_rations_print_title_is_not_after_the_table(client):
    page = client.get("/rations/tamween").text
    assert "app-print-head" in page
    assert "app-print-foot" in page
    assert 'class="print-doc print-only"' not in page
    title_at = page.index("app-print-head")
    table_at = page.index("rt-table")
    foot_at = page.index("app-print-foot")
    assert title_at < table_at < foot_at
    assert "css/print.css" in page


def test_dedicated_print_pages_opt_out_of_base_letterhead():
    for rel in ("templates/tameedat/print_one.html", "templates/tameedat/print_report.html",
                "templates/recruits_print.html"):
        html = (ROOT / rel).read_text(encoding="utf-8")
        assert "own-letterhead" in html
        assert "{% block official_print_head %}{% endblock %}" in html
        assert "{% block official_print_foot %}{% endblock %}" in html


def test_every_tab_has_official_print_button(client):
    """قاعدة 23: كل صفحة/تبويب فيه زر طباعة رسمي."""
    for path in PRINT_PAGES:
        page = client.get(path).text
        assert page.count("js-print-page") >= 1, path
        assert "app-print-head" in page, path
        assert "app-print-foot" in page, path
        assert "window.print()" in page, path


def test_agents_force_reading_constants_and_print_rule():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    contrib = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert agents.find("قف — قبل أي تعديل") < agents.find("الخلاصة غير القابلة للتفاوض")
    assert "core/config.py" in agents and "الثوابت" in agents
    assert "Tajawal" in agents and "#F59E0B" in agents
    assert "مؤجل بلا وظيفة" not in agents
    assert "js-print-page" in agents
    assert "partials/print_btn.html" in contrib
    assert "قبل تعديل أي ملف" in contrib
    assert "Tajawal" in contrib and "#F59E0B" in contrib
    assert "#1A103C" not in contrib
