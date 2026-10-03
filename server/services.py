"""业务服务层：筛选、搜索、关联、合并、校历。

控制器（server/main.py）只解析参数，规则一律写在这里，方便单测。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from server.classifier import classify, days_until, group_key, next_action_date
from server.sources.common import ScanReport
from server.sources.official_sites import SourceConfig
from server.store import (
    load_notices,
    load_source_status,
    record_source_result,
    searchable_text,
)

# ------------------------------------------------------------------ 工具


def host_of(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower()


def custom_source_config(item: dict[str, Any]) -> SourceConfig:
    return SourceConfig(
        id=item.get("id", "custom"),
        name=item.get("name") or item.get("url", "自定义来源"),
        scope=item.get("scope", "用户添加"),
        list_urls=(item.get("url", ""),),
        max_items=10,
        detail_budget=5,
        max_pages=1,
    )


def empty_report(source: Any, error: str) -> ScanReport:
    return ScanReport(
        source_id=getattr(source, "id", ""),
        name=getattr(source, "name", ""),
        ok=False,
        error=error,
        checked_at=datetime.now().isoformat(timespec="seconds"),
    )


def today_str() -> str:
    return date.today().isoformat()


# ------------------------------------------------------------------ 合并与关联


def merge_notices(
    existing: dict[str, dict[str, Any]], incoming: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int, int]:
    """合并抓取结果。

    以已有数据为底，先复制全部旧条目（含收藏、待办，以及本次未被重新抓取的来源数据），
    再按 id 用本次抓取结果覆盖更新。这样即使某次抓取失败 / 返回为空，已有数据也不会被清空。
    """
    new_items = 0
    changed_items = 0
    result: dict[str, dict[str, Any]] = {rid: dict(row) for rid, row in existing.items()}
    for row in incoming:
        rid = row.get("id")
        if not rid:
            continue
        old = result.get(rid)
        new = dict(row)
        if old is None:
            new_items += 1
            new["favorite"] = False
        else:
            if old.get("content_hash") != new.get("content_hash"):
                changed_items += 1
                new["changed"] = True
                new["previous"] = {
                    "deadline": old.get("deadline"),
                    "summary": old.get("summary"),
                }
            new["favorite"] = old.get("favorite", False)
            new["todo"] = old.get("todo")
        result[rid] = new
    merged = list(result.values())
    today = today_str()
    for row in merged:
        row["next_action"] = next_action_date(row.get("times") or {}, today)
        row["days_left"] = days_until(row.get("next_action") or row.get("deadline"), today)
    merged.sort(key=lambda row: row.get("published_at") or "", reverse=True)
    return merged, new_items, changed_items


def link_related(rows: list[dict[str, Any]]) -> None:
    """把同一活动的通知 / 新闻 / 公示 / 结果关联起来（需求 11）。"""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = row.get("group_key") or group_key(row.get("title", ""))
        row["group_key"] = key
        if len(key) < 4:
            continue
        buckets.setdefault(key, []).append(row)
    for key, group in buckets.items():
        if len(group) < 2:
            continue
        ids = [item["id"] for item in group]
        for item in group:
            others = [value for value in ids if value != item["id"]]
            item["related_ids"] = others[:6]
            item["related_count"] = len(others)


def persist_reports(reports: list[ScanReport]) -> list[dict[str, Any]]:
    """把每个来源的抓取结果写入 source_status.json。"""
    status = load_source_status()
    failed: list[dict[str, Any]] = []
    for report in reports:
        record_source_result(
            report.source_id,
            name=report.name,
            ok=report.ok,
            item_count=report.item_count,
            error=report.error,
            checked_at=report.checked_at,
        )
        if not report.ok:
            failed.append(
                {"id": report.source_id, "name": report.name, "reason": report.error}
            )
    return failed


# ------------------------------------------------------------------ 查询


def find_notice(notice_id: str) -> dict[str, Any] | None:
    for row in load_notices():
        if row.get("id") == notice_id:
            return row
    return None


def decorate_notice(row: dict[str, Any]) -> dict[str, Any]:
    """详情：补齐关联、下一步行动、AI/规则整理结果。"""
    today = today_str()
    item = dict(row)
    item["next_action"] = next_action_date(item.get("times") or {}, today)
    item["days_left"] = days_until(item.get("next_action") or item.get("deadline"), today)
    item["related"] = related_notices(item)
    if not item.get("categories"):
        analysis = classify(item.get("title", ""), item.get("body_text", ""))
        item.update(analysis)
    item["organized"] = organize(item)
    return item


def organize(row: dict[str, Any]) -> dict[str, Any]:
    """本地规则整理结果（未配置 AI 时使用，需求：不得替代官方正文）。"""
    times = {key: value for key, value in (row.get("times") or {}).items() if value}
    return {
        "engine": "rule",
        "engine_label": "本地规则整理（未启用 AI）",
        "summary": row.get("summary", ""),
        "audience": row.get("audience") or [],
        "audience_confirmed": row.get("audience_confirmed", False),
        "times": times,
        "materials": row.get("materials") or [],
        "steps": row.get("steps") or [],
        "location": row.get("location", ""),
        "campus": row.get("campus", ""),
        "prep_minutes": row.get("prep_minutes", 0),
        "disclaimer": "请以官方原文为准，整理结果仅供参考。",
    }


def _match_bool(value: str, target: bool) -> bool:
    if value == "":
        return True
    return value == ("yes" if target else "no")


def apply_filters(rows: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
    today = today_str()
    term = (payload.get("q") or "").strip().casefold()
    kind = payload.get("kind") or ""
    category = payload.get("category") or ""
    source = payload.get("source") or ""
    audience = payload.get("audience") or ""
    campus = payload.get("campus") or ""
    deadline_state = payload.get("deadline_state") or ""
    prep_max = int(payload.get("prep_max") or 0)
    relevance_min = int(payload.get("relevance_min") or 0)
    date_from = payload.get("date_from") or ""
    date_to = payload.get("date_to") or ""

    result = []
    for row in rows:
        if payload.get("active_only", True) and row.get("status") != "active":
            continue
        if kind and row.get("kind") != kind:
            continue
        if category and category not in (row.get("categories") or []):
            continue
        if source and row.get("source") != source and row.get("source_id") != source:
            continue
        if audience and audience not in (row.get("audience") or []):
            continue
        if campus and row.get("campus") != campus:
            continue
        if not _match_bool(payload.get("needs_signup") or "", bool(row.get("needs_signup"))):
            continue
        if not _match_bool(payload.get("needs_material") or "", bool(row.get("needs_material"))):
            continue
        online = row.get("online")
        if not _match_bool(payload.get("online") or "", bool(online)) and online is not None:
            continue
        has_attachment = bool(row.get("attachment_count") or row.get("attachments"))
        if not _match_bool(payload.get("has_attachment") or "", has_attachment):
            continue
        if deadline_state:
            remaining = days_until(row.get("deadline"), today)
            if deadline_state == "active" and (remaining is None or remaining < 0):
                continue
            if deadline_state == "soon" and (remaining is None or remaining > 7 or remaining < 0):
                continue
            if deadline_state == "expired" and (remaining is None or remaining >= 0):
                continue
            if deadline_state == "unknown" and remaining is not None:
                continue
        if prep_max and int(row.get("prep_minutes") or 0) > prep_max:
            continue
        if relevance_min and int(row.get("relevant") or 0) < relevance_min:
            continue
        published = row.get("published_at") or ""
        if date_from and published and published < date_from:
            continue
        if date_to and published and published > date_to:
            continue
        if term:
            haystack = " ".join(
                [
                    row.get("title", ""),
                    row.get("summary", ""),
                    row.get("source", ""),
                    " ".join(row.get("categories") or []),
                ]
            ).casefold()
            if term not in haystack:
                continue
        result.append(row)
    return result


def sort_rows(rows: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    today = today_str()
    if sort == "deadline":
        return sorted(
            rows,
            key=lambda row: (
                row.get("next_action") or row.get("deadline") or "9999-12-31"
            ),
        )
    if sort == "relevant":
        return sorted(rows, key=lambda row: int(row.get("relevant") or 0), reverse=True)
    if sort == "source":
        return sorted(rows, key=lambda row: row.get("source", ""))
    _ = today
    return sorted(rows, key=lambda row: row.get("published_at") or "", reverse=True)


def query_notices(payload: dict[str, Any], limit: int = 200, offset: int = 0) -> dict[str, Any]:
    rows = apply_filters(load_notices(), payload)
    rows = sort_rows(rows, payload.get("sort") or "published")
    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "items": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "library_total": len(load_notices()),
        "filters": payload,
    }


# ------------------------------------------------------------------ 搜索


TYPOS: dict[str, str] = {
    "山東": "山东",
    "講座": "讲座",
    "讲坐": "讲座",
    "講壇": "讲坛",
    "论谈": "论坛",
    "獎學金": "奖学金",
    "奖学经": "奖学金",
    "竞赛": "竞赛",
    "競赛": "竞赛",
    "竟赛": "竞赛",
    "保硏": "保研",
    "保妍": "保研",
    "選課": "选课",
    "选棵": "选课",
    "四六級": "四六级",
    "志願者": "志愿者",
    "志原者": "志愿者",
    "实习": "实习",
    "實習": "实习",
    "招骋": "招聘",
    "招娉": "招聘",
    "公视": "公示",
    "公式": "公示",
    "暑期": "暑期",
    "暑侯": "暑期",
}

HISTORY_WORDS = ("往年", "历届", "历年", "上一届", "往届", "历史")

# 自然语言提问里的功能词：不参与全文匹配，只用来判断意图
QUESTION_STOPWORDS = (
    "最近",
    "近期",
    "本周",
    "这周",
    "这几天",
    "有哪些",
    "有什么",
    "哪些",
    "哪个",
    "适合",
    "关于",
    "我的",
    "帮我",
    "我想",
    "请问",
    "请",
    "查找",
    "查询",
    "找一下",
    "一下",
    "还有",
    "有没有",
    "如何",
    "怎么",
    "的",
    "了",
    "吗",
    "呢",
    "？",
    "?",
    "。",
    "，",
    "、",
)

INTENT_PATTERNS: list[tuple[str, str]] = [
    ("最近", "\\b(最近|近期|这几天|本周|这周)"),
    ("截止", "(截止|快要|即将|剩余)"),
    ("竞赛", "(竞赛|大赛|比赛)"),
    ("奖学金", "(奖学金|评奖|评优)"),
    ("讲座", "(讲座|讲坛|论坛|报告会)"),
    ("招聘", "(招聘|实习|就业|宣讲)"),
    ("志愿", "(志愿|社会实践|支教)"),
    ("考试", "(考试|选课|四六级|补考)"),
    ("保研", "(保研|推免|考研|复试)"),
]


def normalize_query(raw: str) -> tuple[str, str]:
    """返回 (纠正后的查询, 提示文案)。"""
    value = (raw or "").strip()
    if not value:
        return "", ""
    fixed = value
    for wrong, right in TYPOS.items():
        if wrong in fixed:
            fixed = fixed.replace(wrong, right)
    # 全角转半角
    fixed = fixed.translate(str.maketrans("（）【】！？，；：", "()[]!?,;:"))
    return fixed, ("已自动纠正为：" + fixed if fixed != value else "")


def extract_terms(query: str) -> list[str]:
    """把自然语言提问切成可检索的关键词。

    「最近有哪些适合我的竞赛？」→ ["竞赛"]；
    「往年 创新创业大赛 获奖名单」→ ["创新创业大赛", "获奖名单"]（往年只做意图）。
    """
    value = (query or "").strip()
    if not value:
        return []
    for word in HISTORY_WORDS:
        value = value.replace(word, " ")
    for word in QUESTION_STOPWORDS:
        value = value.replace(word, " ")
    terms = [term for term in re.split(r"[\s,，、;；]+", value) if term and len(term) >= 2]
    if not terms:
        # 整句都是功能词时，按意图回退到领域关键词
        intent = detect_intent(query)
        terms = [name for name in intent["intents"] if name not in ("最近", "截止")]
    return terms


def detect_intent(query: str) -> dict[str, Any]:
    lowered = (query or "").casefold()
    intents = [
        name for name, pattern in INTENT_PATTERNS if re.search(pattern, lowered)
    ]
    include_history = any(word in query for word in HISTORY_WORDS)
    return {"intents": intents, "include_history": include_history}


def search(query: str, include_history: bool = False, limit: int = 100) -> dict[str, Any]:
    """全文搜索：标题、正文、附件、来源、适用对象、地点、材料名（需求 6 / I）。"""
    fixed, correction = normalize_query(query)
    intent = detect_intent(fixed)
    want_history = include_history or intent["include_history"]
    if not fixed:
        return {
            "items": [],
            "total": 0,
            "query": "",
            "correction": "",
            "intent": intent,
            "sources": [],
            "library_total": len(load_notices()),
        }

    terms = extract_terms(fixed)
    rows = load_notices()
    index = [(row, searchable_text(row)) for row in rows]
    today = today_str()

    hits: list[tuple[int, dict[str, Any]]] = []
    for row, text in index:
        if not want_history and row.get("status") == "expired":
            continue
        score = 0
        matched = 0
        title = (row.get("title") or "").casefold()
        for term in terms:
            lowered = term.casefold()
            if lowered in title:
                score += 10
                matched += 1
            elif lowered in text:
                score += 3
                matched += 1
        # 自然语言提问时只要命中一部分就算相关，避免整句一个字不差才出结果
        if matched:
            # 需要用户行动的「通知」排在「新闻」前面
            kind = row.get("kind")
            if kind == "通知":
                score += 6
            elif kind == "公示／结果":
                score += 1
            elif kind == "新闻":
                score -= 3
            remaining = days_until(row.get("next_action") or row.get("deadline"), today)
            if remaining is not None and 0 <= remaining <= 14:
                score += 4
            hits.append((score, row))

    hits.sort(key=lambda pair: pair[0], reverse=True)
    items = [row for _, row in hits][:limit]
    searched_sources = sorted({row.get("source", "") for row in rows if row.get("source")})
    return {
        "items": items,
        "total": len(hits),
        "query": fixed,
        "correction": correction,
        "intent": intent,
        "sources": searched_sources,
        "history_included": want_history,
        "library_total": len(rows),
    }


def related_notices(row: dict[str, Any]) -> list[dict[str, Any]]:
    key = row.get("group_key") or group_key(row.get("title", ""))
    if len(key) < 4:
        return []
    today = today_str()
    items = []
    for candidate in load_notices():
        if candidate.get("id") == row.get("id"):
            continue
        other = candidate.get("group_key") or group_key(candidate.get("title", ""))
        if other == key:
            items.append(candidate)
    items.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    _ = today
    return items[:8]


# ------------------------------------------------------------------ 筛选项


def facets() -> dict[str, Any]:
    rows = load_notices()
    today = today_str()
    active = [row for row in rows if row.get("status") == "active"]

    def counter(key: str) -> list[dict[str, Any]]:
        bucket: dict[str, int] = {}
        for row in active:
            values = row.get(key)
            if isinstance(values, list):
                for value in values:
                    bucket[value] = bucket.get(value, 0) + 1
            elif values:
                bucket[values] = bucket.get(values, 0) + 1
        return [
            {"value": value, "count": count}
            for value, count in sorted(bucket.items(), key=lambda pair: -pair[1])
        ]

    return {
        "categories": counter("categories"),
        "kinds": counter("kind"),
        "sources": counter("source"),
        "audience": counter("audience"),
        "campus": counter("campus"),
        "total_active": len(active),
        "total_all": len(rows),
        "generated_at": today,
    }


# ------------------------------------------------------------------ 校历

# 说明：以下为参考性学年节点。官方校历一旦抓取成功会自动覆盖，
# 在此之前前端会明确标注「参考日期，请以官方校历为准」。
# 说明：以下为参考性学年节点。假期条目带 start / end，自动按「休假天数」标注；
# 官方校历一旦抓取成功会自动覆盖，在此之前前端会明确标注「参考日期，请以官方校历为准」。
SCHOOL_CALENDAR: list[dict[str, Any]] = [
    {"date": "2026-09-07", "title": "秋季学期开学", "type": "semester", "official": False},
    {"start": "2026-10-01", "end": "2026-10-08", "title": "国庆节放假", "type": "holiday", "official": False},
    {"date": "2027-01-04", "title": "秋季学期考试周开始", "type": "exam", "official": False},
    {"date": "2027-01-15", "title": "秋季学期考试周结束", "type": "exam", "official": False},
    {"start": "2027-01-18", "end": "2027-02-28", "title": "寒假", "type": "holiday", "official": False},
    {"date": "2027-02-28", "title": "春季学期开学", "type": "semester", "official": False},
    {"start": "2027-04-04", "end": "2027-04-06", "title": "清明节放假", "type": "holiday", "official": False},
    {"start": "2027-05-01", "end": "2027-05-05", "title": "劳动节放假", "type": "holiday", "official": False},
    {"start": "2027-06-09", "end": "2027-06-11", "title": "端午节放假", "type": "holiday", "official": False},
    {"date": "2027-06-28", "title": "春季学期考试周开始", "type": "exam", "official": False},
    {"date": "2027-07-09", "title": "春季学期考试周结束", "type": "exam", "official": False},
    {"start": "2027-07-12", "end": "2027-08-31", "title": "暑假", "type": "holiday", "official": False},
    {"start": "2027-09-15", "end": "2027-09-17", "title": "中秋节放假", "type": "holiday", "official": False},
    {"start": "2027-10-01", "end": "2027-10-08", "title": "国庆节放假", "type": "holiday", "official": False},
]

TIME_LABELS = {
    "signup_start": "报名开始",
    "signup_end": "报名截止",
    "submit_end": "材料提交截止",
    "review_at": "审核 / 评审",
    "event_start": "活动开始",
    "event_end": "活动结束",
    "result_at": "结果公布",
    "exam_at": "考试 / 面试",
}


def calendar(month: str = "") -> dict[str, Any]:
    """校历事件：官方学年节点 + 通知中的时间节点（需求 16 / M）。"""
    rows = load_notices()
    events: list[dict[str, Any]] = []
    for entry in SCHOOL_CALENDAR:
        if entry.get("type") == "holiday":
            start = entry["start"]
            end = entry["end"]
            try:
                days_off = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
            except ValueError:
                days_off = 0
            cursor = start
            while True:
                if not month or cursor.startswith(month):
                    events.append(
                        {
                            "date": cursor,
                            "title": (
                                f"{entry['title']}（休 {days_off} 天）"
                                if cursor == start
                                else f"{entry['title']}（休假中）"
                            ),
                            "type": "holiday",
                            "official": False,
                            "source": "校历（参考）",
                            "kind": "校历",
                            "days_off": days_off if cursor == start else 0,
                        }
                    )
                if cursor == end:
                    break
                try:
                    cursor = (date.fromisoformat(cursor) + timedelta(days=1)).isoformat()
                except ValueError:
                    break
            continue
        if month and not entry["date"].startswith(month):
            continue
        events.append({**entry, "source": "校历（参考）", "kind": "校历"})

    for row in rows:
        if row.get("status") != "active":
            continue
        times = row.get("times") or {}
        for key, value in times.items():
            if not value:
                continue
            if month and not value.startswith(month):
                continue
            events.append(
                {
                    "date": value,
                    "title": f"{TIME_LABELS.get(key, key)}：{row.get('title', '')}",
                    "type": "deadline",
                    "official": True,
                    "source": row.get("source", ""),
                    "kind": "通知",
                    "notice_id": row.get("id"),
                    "official_url": row.get("official_url", ""),
                }
            )
        if row.get("deadline") and not any(
            value == row["deadline"] for value in times.values() if value
        ):
            if not month or row["deadline"].startswith(month):
                events.append(
                    {
                        "date": row["deadline"],
                        "title": f"截止：{row.get('title', '')}",
                        "type": "deadline",
                        "official": True,
                        "source": row.get("source", ""),
                        "kind": "通知",
                        "notice_id": row.get("id"),
                        "official_url": row.get("official_url", ""),
                    }
                )
    # 同一天、同一标题/同一通知的截止事件去重，避免重复出现
    seen_keys = set()
    deduped = []
    for item in events:
        key = (item["date"], item.get("title", ""))
        notice_id = item.get("notice_id")
        notice_key = (item["date"], notice_id) if notice_id else None
        if key in seen_keys:
            continue
        if notice_key and notice_key in seen_keys:
            continue
        seen_keys.add(key)
        if notice_key:
            seen_keys.add(notice_key)
        deduped.append(item)
    events = deduped

    events.sort(key=lambda item: item["date"])
    return {
        "items": events,
        "total": len(events),
        "month": month or "全部",
        "note": "学年节点为参考日期，请以山东大学官方校历为准。",
    }


def upcoming(days: int = 7) -> list[dict[str, Any]]:
    today = date.today()
    horizon = today + timedelta(days=days)
    rows = load_notices()
    items = []
    for row in rows:
        if row.get("status") != "active":
            continue
        value = row.get("next_action") or row.get("deadline")
        if not value:
            continue
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            continue
        if today <= parsed <= horizon:
            items.append(row)
    items.sort(key=lambda row: row.get("next_action") or row.get("deadline") or "")
    return items
