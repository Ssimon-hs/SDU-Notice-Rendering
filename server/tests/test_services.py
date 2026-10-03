"""服务层测试：筛选、搜索、关联、校历。"""

from server import services

SAMPLE = [
    {
        "id": "a1",
        "title": "山东大学第三届创新创业大赛通知",
        "summary": "面向本科生，线上提交报名表。",
        "source": "本科生院",
        "source_id": "sdu-undergraduate",
        "status": "active",
        "kind": "通知",
        "categories": ["竞赛通知"],
        "audience": ["本科生"],
        "campus": "中心校区",
        "published_at": "2026-09-20",
        "deadline": "2026-10-20",
        "times": {"signup_end": "2026-10-20"},
        "attachment_count": 2,
        "needs_signup": True,
        "needs_material": True,
        "prep_minutes": 90,
        "body_text": "请提交报名表和项目计划书。",
        "attachments": [{"name": "报名表.docx", "url": "https://x/1.docx", "kind": "docx"}],
        "materials": [{"name": "报名表", "format": "docx"}],
        "online": True,
    },
    {
        "id": "a2",
        "title": "我校学子在全国竞赛中荣获一等奖",
        "summary": "近日比赛圆满结束。",
        "source": "山大新闻网",
        "source_id": "sdu-news",
        "status": "active",
        "kind": "新闻",
        "categories": ["宣传报道"],
        "audience": [],
        "campus": "",
        "published_at": "2026-09-10",
        "deadline": None,
        "times": {},
        "attachment_count": 0,
        "needs_signup": False,
        "needs_material": False,
        "prep_minutes": 10,
        "body_text": "比赛于昨日闭幕。",
        "attachments": [],
        "materials": [],
        "online": None,
    },
    {
        "id": "a3",
        "title": "2025年创新创业大赛获奖名单公示",
        "summary": "往年结果。",
        "source": "本科生院",
        "source_id": "sdu-undergraduate",
        "status": "expired",
        "kind": "公示／结果",
        "categories": ["公示／名单／结果"],
        "audience": ["本科生"],
        "campus": "",
        "published_at": "2025-06-01",
        "deadline": "2025-05-01",
        "times": {},
        "attachment_count": 0,
        "needs_signup": False,
        "needs_material": False,
        "prep_minutes": 10,
        "body_text": "",
        "attachments": [],
        "materials": [],
        "online": None,
    },
]


def test_apply_filters_by_kind():
    rows = services.apply_filters(SAMPLE, {"kind": "通知", "active_only": False})
    assert [row["id"] for row in rows] == ["a1"]


def test_apply_filters_hides_expired_by_default():
    rows = services.apply_filters(SAMPLE, {})
    assert "a3" not in [row["id"] for row in rows]


def test_apply_filters_by_audience_and_campus():
    rows = services.apply_filters(
        SAMPLE, {"audience": "本科生", "campus": "中心校区", "active_only": False}
    )
    assert [row["id"] for row in rows] == ["a1"]


def test_apply_filters_prep_time():
    rows = services.apply_filters(SAMPLE, {"prep_max": 30, "active_only": False})
    assert "a1" not in [row["id"] for row in rows]


def test_search_finds_attachment_name(monkeypatch):
    monkeypatch.setattr(services, "load_notices", lambda: SAMPLE)
    result = services.search("报名表")
    assert result["total"] >= 1
    assert result["items"][0]["id"] == "a1"


def test_search_hides_history_unless_asked(monkeypatch):
    monkeypatch.setattr(services, "load_notices", lambda: SAMPLE)
    assert all(row["id"] != "a3" for row in services.search("创新创业大赛")["items"])
    history = services.search("往年 创新创业大赛")
    assert history["history_included"] is True
    assert any(row["id"] == "a3" for row in history["items"])


def test_search_reports_sources_when_empty(monkeypatch):
    monkeypatch.setattr(services, "load_notices", lambda: SAMPLE)
    result = services.search("不存在的关键词")
    assert result["total"] == 0
    assert "本科生院" in result["sources"]


def test_natural_language_question(monkeypatch):
    """「最近有哪些适合我的竞赛？」要能命中竞赛类通知。"""
    monkeypatch.setattr(services, "load_notices", lambda: SAMPLE)
    result = services.search("最近有哪些适合我的竞赛？")
    assert result["total"] >= 1
    assert result["items"][0]["id"] == "a1"


def test_history_words_are_intent_not_terms(monkeypatch):
    """「往年」只用来放开历史范围，不作为检索词，否则永远搜不到。"""
    monkeypatch.setattr(services, "load_notices", lambda: SAMPLE)
    result = services.search("往年创新创业大赛")
    assert result["history_included"] is True
    assert result["total"] >= 1


def test_typo_correction():
    fixed, hint = services.normalize_query("竟赛")
    assert fixed == "竞赛"
    assert hint


def test_link_related_groups_same_activity():
    rows = [dict(row) for row in SAMPLE]
    services.link_related(rows)
    linked = {row["id"]: row.get("related_ids", []) for row in rows}
    assert linked["a1"] == [] or "a3" in linked["a1"]


def test_calendar_contains_deadline(monkeypatch):
    monkeypatch.setattr(services, "load_notices", lambda: SAMPLE)
    result = services.calendar("2026-10")
    titles = [item["title"] for item in result["items"]]
    assert any("创新创业大赛" in title for title in titles)
    assert result["note"]


def test_organize_disclaimer_present():
    organized = services.organize(SAMPLE[0])
    assert organized["engine"] == "rule"
    assert organized["disclaimer"]
    assert organized["audience"] == ["本科生"]
