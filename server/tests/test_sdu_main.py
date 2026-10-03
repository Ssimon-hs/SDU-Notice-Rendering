from datetime import date

from server.sources.sdu_main import (
    _extract_card_date,
    _infer_category,
    _notice_id,
)


def test_extract_card_date():
    assert _extract_card_date("时间：10月31日（星期六）截止", 2026) == "2026-10-31"


def test_infer_category():
    assert _infer_category("校园 AI 漫剧大赛通知") == "竞赛科研"
    assert _infer_category("名家讲坛第 101 期") == "讲座论坛"


def test_notice_id_is_stable():
    url = "https://www.view.sdu.edu.cn/info/1020/214074.htm"
    assert _notice_id(url) == _notice_id(url)
    assert _notice_id(url).startswith("sdu-")


def test_current_year_is_supported():
    assert _extract_card_date("10月1日", date.today().year).startswith(
        str(date.today().year)
    )