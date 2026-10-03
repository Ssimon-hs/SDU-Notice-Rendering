"""分类器测试：分类 / 通知新闻区分 / 适用对象 / 时间 / 材料。"""

from server.classifier import (
    classify,
    days_until,
    detect_audience,
    extract_materials,
    extract_times,
    group_key,
    is_expired,
    next_action_date,
    sanitize_published,
    summarize,
    within_years,
)


def test_classify_competition_notice():
    result = classify(
        "关于举办山东大学第三届创新创业大赛的通知",
        "请各团队于2026年10月20日前提交报名表与项目计划书，逾期不再受理。",
    )
    assert "竞赛通知" in result["categories"]
    assert result["kind"] == "通知"
    assert result["needs_signup"] is True
    assert result["times"]["signup_end"] == "2026-10-20"


def test_classify_news_is_not_notice():
    result = classify(
        "我校学子在全国数学建模竞赛中荣获一等奖",
        "近日，比赛在北京圆满结束，我校团队表现优异，获得评委一致好评。",
    )
    assert result["kind"] == "新闻"


def test_classify_publicity():
    result = classify("2026年国家奖学金拟获奖名单公示", "公示期为2026年10月8日至10月12日。")
    assert result["kind"] == "公示／结果"
    assert "公示／名单／结果" in result["categories"]


def test_classify_falls_back_to_pending():
    result = classify("关于部分工作的通知", "")
    assert result["categories"][0] in ("待分类", "活动通知")


def test_audience_detection():
    audience = detect_audience("面向全体本科生和2026级研究生，各学院推荐。")
    assert "本科生" in audience
    assert "研究生" in audience
    assert "2026级" in audience


def test_audience_ignores_sentence_fragments():
    """正文里出现的句子片段不能被当成学院名。"""
    audience = detect_audience(
        "信息学院党委理论学习中心组召开会议，推动学院发展，要紧盯学院重点工作。"
    )
    assert "信息学院" in audience
    assert not any("理论学习" in item or "推动学院" in item for item in audience)
    assert all(len(item) <= 12 for item in audience)


def test_materials_ignore_sentence_fragments():
    materials = extract_materials("会议由院长主持并作总结，请提交报名表和成绩单。")
    names = [item["name"] for item in materials]
    assert not any("总结" in name for name in names)
    assert any("报名表" in name for name in names)


def test_material_extraction():
    materials = extract_materials("请提交申请表、成绩单复印件和个人简历（PDF 格式）。")
    names = [item["name"] for item in materials]
    assert any("申请表" in name for name in names)
    assert any("简历" in name for name in names)


def test_times_are_separated():
    times = extract_times(
        "报名时间：2026年10月8日。材料提交截止：2026年10月20日。考试时间：2026年11月2日。",
        2026,
    )
    assert times["signup_start"] == "2026-10-08"
    assert times["submit_end"] == "2026-10-20"
    assert times["exam_at"] == "2026-11-02"


def test_publish_date_is_not_deadline():
    """需求 13：禁止把发布时间误认为截止时间。"""
    result = classify("通知", "发布时间为2026年9月1日，请各学院组织学习。")
    assert result["deadline"] is None


def test_next_action_picks_nearest_future():
    times = {
        "signup_start": "2020-01-01",
        "signup_end": "2099-01-05",
        "exam_at": "2099-01-03",
    }
    assert next_action_date(times, "2026-10-02") == "2099-01-03"


def test_expiry_and_days():
    assert is_expired("2026-09-01", "2026-10-02") is True
    assert is_expired("2026-12-01", "2026-10-02") is False
    assert days_until("2026-10-12", "2026-10-02") == 10


def test_sanitize_future_publish_date():
    assert sanitize_published("2027-09-19", "2026-10-02") is None
    assert sanitize_published("2026-09-19", "2026-10-02") == "2026-09-19"


def test_within_years_default_three():
    assert within_years("2025-01-01", 3, "2026-10-02") is True
    assert within_years("2019-01-01", 3, "2026-10-02") is False


def test_group_key_links_same_activity():
    assert group_key("2026年校园AI创意作品征集通知") == group_key(
        "2026年校园AI创意作品征集获奖公示"
    )


def test_summary_never_contains_date_prefix():
    text = summarize("通知", "请各学院于10月20日前报送材料。")
    assert "2026-10-20" not in text
    assert text.startswith("请各学院")
