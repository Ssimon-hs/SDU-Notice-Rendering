"""山东大学主站抓取。

保留原有首页卡片抓取逻辑，同时补上「栏目发现 + 翻页 + 正文 + 附件」。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from server.classifier import (
    attachment_kind,
    classify,
    group_key,
    is_expired,
    sanitize_published,
    summarize,
    refine_title,
    infer_date_from_text,
    within_years,
)
from server.sources.common import ScanReport, _error_reason, _extract_detail

HOME_URL = "https://www.sdu.edu.cn/"
USER_AGENT = (
    "YijianSDU/0.1 (+https://github.com/; local-first open-source student project)"
)
DATE_PATTERN = re.compile(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日(?:（[^）]+）)?")
FULL_DATE_PATTERN = re.compile(r"(?P<year>20\d{2})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日")
ISO_DATE_PATTERN = re.compile(
    r"(?P<year>20\d{2})[-/.](?P<month>\d{1,2})[-/.](?P<day>\d{1,2})"
)

# 主站常见栏目（顺序越靠前越优先）
MAIN_COLUMNS = (
    "https://www.sdu.edu.cn/xwzx.htm",
    "https://www.sdu.edu.cn/tzgg.htm",
    "https://www.sdu.edu.cn/jxky.htm",
)


@dataclass
class FetchResult:
    items: list[dict[str, Any]]
    checked_url: str
    checked_at: str


def _clean(value: str) -> str:
    return " ".join(value.split())


def _get(url: str) -> requests.Response:
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response


def _notice_id(url: str) -> str:
    return "sdu-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _infer_category(title: str) -> str:
    pairs = [
        ("竞赛科研", ("大赛", "竞赛", "科研", "创新创业", "征集")),
        ("评奖评优", ("奖学金", "评奖", "评优", "公示", "名单")),
        ("就业实习", ("招聘", "就业", "实习", "宣讲")),
        ("讲座论坛", ("讲坛", "讲座", "论坛", "报告会")),
        ("志愿服务", ("志愿", "招募")),
        ("教学安排", ("考试", "选课", "教学", "课程")),
    ]
    for category, keywords in pairs:
        if any(keyword in title for keyword in keywords):
            return category
    return "校园活动"


def _extract_card_date(text: str, year: int) -> str | None:
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    try:
        return date(year, int(match.group("month")), int(match.group("day"))).isoformat()
    except ValueError:
        return None


def _detail(url: str) -> dict[str, Any]:
    response = _get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    title_node = soup.select_one(".art-tit h3") or soup.select_one("h3")
    body_node = soup.select_one(".v_news_content") or soup.select_one(".article-content")
    source_node = soup.select_one(".con-tit .source") or soup.select_one(".source")
    date_node = soup.select_one(".con-tit .date") or soup.select_one(".date")
    title = _clean(title_node.get_text(" ", strip=True)) if title_node else ""
    body = _clean(body_node.get_text(" ", strip=True)) if body_node else ""
    source = (
        _clean(source_node.get_text(" ", strip=True)).removeprefix("发布：")
        if source_node
        else "山东大学"
    )
    published_at = None
    if date_node:
        match = FULL_DATE_PATTERN.search(date_node.get_text(" ", strip=True))
        if not match:
            match = ISO_DATE_PATTERN.search(date_node.get_text(" ", strip=True))
        if match:
            try:
                published_at = date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                ).isoformat()
            except ValueError:
                published_at = None
    attachments = []
    images: list[str] = []
    if body_node:
        for anchor in body_node.select("a[href]"):
            href = urljoin(url, anchor.get("href", ""))
            label = _clean(anchor.get_text(" ", strip=True)) or href.rsplit("/", 1)[-1]
            if href and href != url and href.startswith(("http://", "https://")):
                attachments.append(
                    {"name": label, "url": href, "kind": attachment_kind(href)}
                )
        for image in body_node.select("img[src]"):
            src = urljoin(url, image.get("src", ""))
            if src.startswith(("http://", "https://")):
                images.append(src)
    return {
        "title": title,
        "body_text": body,
        "source": source,
        "published_at": published_at,
        "attachments": attachments,
        "images": images[:12],
        "parse_failed": body_node is None,
    }


def _candidates_from_html(html: str, base: str, year: int) -> dict[str, dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict[str, Any]] = {}
    checked_at = datetime.now().isoformat(timespec="seconds")

    # 1) 首页卡片：带「时间：」的 view.sdu.edu.cn/info 链接
    for anchor in soup.select('a[title][href*="view.sdu.edu.cn/info/"]'):
        title = _clean(anchor.get("title", ""))
        card_text = _clean(anchor.get_text(" ", strip=True))
        if not title or not (
            "时间：" in card_text
            or "截止" in card_text
            or "通知" in title
            or any(word in title for word in ("讲坛", "论坛", "讲座", "招募", "征集"))
        ):
            continue
        url = urljoin(base, anchor.get("href", ""))
        deadline = _extract_card_date(card_text, year)
        location_match = re.search(r"地点：(.+)$", card_text)
        found[url] = {
            "id": _notice_id(url),
            "title": title,
            "summary": card_text.replace(title, "", 1).strip() or "请查看官方原文。",
            "source": "山东大学",
            "published_at": "",
            "deadline": deadline,
            "location": _clean(location_match.group(1)) if location_match else "详见原文",
            "category": _infer_category(title),
            "official_url": url,
            "fetched_at": checked_at,
        }

    # 2) 列表页链接：相邻文本里有日期
    for anchor in soup.select("a[href]"):
        title = _clean(anchor.get("title") or anchor.get_text(" ", strip=True))
        if len(title) < 6:
            continue
        url = urljoin(base, anchor.get("href", ""))
        if not url.startswith(("http://", "https://")) or url in found:
            continue
        parent_text = (
            _clean(anchor.parent.get_text(" ", strip=True)) if anchor.parent else title
        )
        match = ISO_DATE_PATTERN.search(parent_text)
        if not match:
            continue
        try:
            published = date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            ).isoformat()
        except ValueError:
            continue
        found[url] = {
            "id": _notice_id(url),
            "title": title,
            "summary": parent_text[:200],
            "source": "山东大学",
            "published_at": published,
            "deadline": None,
            "location": "详见原文",
            "category": _infer_category(title),
            "official_url": url,
            "fetched_at": checked_at,
        }
    return found


def _build_item(
    candidate: dict[str, Any],
    detail: dict[str, Any],
    checked_at: str,
    today: str,
) -> dict[str, Any] | None:
    title = refine_title(_clean(candidate["title"]))
    if not title:
        return None
    published_at = sanitize_published(
        candidate.get("published_at") or detail.get("published_at"), today
    )
    body = detail.get("body_text", "")
    attachment_names = " ".join(
        str(item.get("name", "")) for item in detail.get("attachments", [])
    )
    inferred_date = ""
    if not published_at:
        inferred_date = (
            infer_date_from_text(title, body, candidate.get("summary", ""), attachment_names)
            or ""
        )
    analysis = classify(title, body)
    deadline = candidate.get("deadline") or analysis["deadline"]
    if deadline and published_at and deadline < published_at:
        deadline = None
    expired = is_expired(deadline, today)
    if published_at and not within_years(published_at, 3, today):
        return None
    if not published_at and not body and not candidate.get("deadline"):
        return None

    attachments = detail.get("attachments", [])
    images = detail.get("images", [])
    if expired:
        body = ""
        attachments = []
        images = []

    item = {
        "id": candidate["id"],
        "title": title,
        "official_title": title,
        "summary": summarize(title, body or candidate.get("summary", "")),
        "source": detail.get("source") or candidate.get("source") or "山东大学",
        "source_id": "sdu-main",
        "source_name": "山东大学",
        "org_unit": detail.get("source") or "山东大学",
        "scope": "学校主站",
        "published_at": published_at,
        "inferred_date": inferred_date,
        "deadline": deadline,
        "location": candidate.get("location", "详见原文"),
        "campus": analysis["campus"] or "",
        "categories": analysis["categories"],
        "category": analysis["categories"][0] if analysis["categories"] else "待分类",
        "kind": analysis["kind"],
        "audience": analysis["audience"],
        "audience_confirmed": analysis["audience_confirmed"],
        "times": analysis["times"],
        "needs_signup": analysis["needs_signup"],
        "needs_material": analysis["needs_material"],
        "online": analysis["online"],
        "prep_minutes": analysis["prep_minutes"],
        "materials": analysis["materials"],
        "steps": analysis["steps"] or ["阅读并核对官方原文"],
        "relevant": 0,
        "attachment_count": len(attachments),
        "attachments": attachments,
        "images": images,
        "official_url": candidate["official_url"],
        "status": "expired" if expired else "active",
        "favorite": False,
        "body_text": body,
        "group_key": group_key(title),
        "related_ids": [],
        "fetched_at": checked_at,
        "parse_error": "正文解析失败" if detail.get("parse_failed") and not body else "",
    }
    payload = "|".join(
        [
            item["title"],
            item.get("published_at") or "",
            item.get("deadline") or "",
            item["summary"],
            str(item["attachment_count"]),
        ]
    )
    item["content_hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return item


def scan(year: int | None = None, include_details: bool = True) -> FetchResult:
    """兼容旧接口：只返回条目列表。"""
    return scan_report(year=year, include_details=include_details).items_result()


def scan_report(year: int | None = None, include_details: bool = True) -> "MainScan":
    return MainScan(year=year, include_details=include_details).run()


class MainScan:
    """主站抓取，产出条目 + 报告（成功 / 失败原因 / 抓取数量）。"""

    def __init__(self, year: int | None = None, include_details: bool = True) -> None:
        self.year = year
        self.include_details = include_details

    def run(self) -> "MainScan":
        checked_at = datetime.now().isoformat(timespec="seconds")
        today = date.today().isoformat()
        current_year = self.year or date.today().year
        self.checked_at = checked_at
        self.report = ScanReport(
            source_id="sdu-main",
            name="山东大学主站",
            ok=False,
            checked_at=checked_at,
        )

        columns: list[str] = [HOME_URL]
        try:
            home_html = _get(HOME_URL).text
        except Exception as exc:  # noqa: BLE001
            self.report.error = _error_reason(exc)
            self.items = []
            return self

        soup = BeautifulSoup(home_html, "html.parser")
        for anchor in soup.select("a[href]"):
            label = _clean(anchor.get_text(" ", strip=True))
            if not label or len(label) > 8:
                continue
            if any(word in label for word in ("通知", "公告", "新闻", "要闻", "学术")):
                url = urljoin(HOME_URL, anchor.get("href", ""))
                if url.startswith("https://www.sdu.edu.cn/") and url not in columns:
                    columns.append(url)
        columns = columns[:4]
        self.report.columns = columns

        candidates: dict[str, dict[str, Any]] = {}
        for column_url in columns:
            try:
                html = home_html if column_url == HOME_URL else _get(column_url).text
            except Exception:  # noqa: BLE001
                continue
            for url, item in _candidates_from_html(html, column_url, current_year).items():
                candidates.setdefault(url, item)
        self.report.candidates = len(candidates)
        self.report.pages = len(columns)

        if not candidates:
            self.report.error = "主站列表中未发现带日期的条目，可能改版或需要登录"
            self.items = []
            return self

        ranked = sorted(
            candidates.values(),
            key=lambda item: item.get("published_at") or "",
            reverse=True,
        )[:36]

        items: list[dict[str, Any]] = []
        budget = 18 if self.include_details else 0
        for candidate in ranked:
            detail: dict[str, Any] = {
                "body_text": "",
                "attachments": [],
                "images": [],
                "parse_failed": False,
            }
            if budget > 0:
                try:
                    detail = _detail(candidate["official_url"])
                    budget -= 1
                except Exception as exc:  # noqa: BLE001
                    detail["parse_failed"] = True
                    detail["error"] = _error_reason(exc)
            try:
                item = _build_item(candidate, detail, checked_at, today)
            except Exception:  # noqa: BLE001
                continue
            if item:
                if detail.get("error"):
                    item["parse_error"] = detail["error"]
                items.append(item)

        items.sort(key=lambda row: row.get("published_at") or "", reverse=True)
        self.items = items
        self.report.rows = items
        self.report.ok = bool(items)
        if not items:
            self.report.error = "条目解析后为空，正文读取可能失败"
        return self

    def items_result(self) -> FetchResult:
        return FetchResult(
            items=getattr(self, "items", []),
            checked_url=HOME_URL,
            checked_at=getattr(self, "checked_at", datetime.now().isoformat(timespec="seconds")),
        )
