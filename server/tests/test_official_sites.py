from server.sources.official_sites import _clean_title, _extract_deadline, _parse_date


def test_parse_source_dates():
    assert _parse_date("09.30 2026 关于举办活动") == "2026-09-30"
    assert _parse_date("2026-09-17 工作通知") == "2026-09-17"


def test_extract_deadline_from_body():
    text = "报名时间为2026年9月20日至10月15日，请按要求提交材料。"
    assert _extract_deadline(text, 2026) == "2026-10-15"


def test_deadline_without_year_uses_publication_year():
    assert _extract_deadline("请于10月31日前提交，逾期不再受理", 2026) is None
    assert _extract_deadline("报名截止时间：10月31日", 2026) == "2026-10-31"


def test_clean_title_removes_list_metadata():
    assert (
        _clean_title("09.30 2026 关于举办创新大赛的通知")
        == "关于举办创新大赛的通知"
    )
    assert (
        _clean_title("山大学子亮剑！ 校区要闻 2026-09-22")
        == "山大学子亮剑！"
    )