"""抓取器公共工具：HTTP 请求、文本清洗、正文与附件抽取、失败原因翻译。

单独成模块是为了避免 sdu_main 与 official_sites 互相 import 造成循环依赖。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

from server.classifier import attachment_kind

# 自签证书站点的降级抓取会产生警告，已在代码里显式处理，不需要打扰用户
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class ScanReport:
    """单个信息源的抓取结果（需求 9：成功 / 失败 / 数量 / 原因）。"""

    source_id: str
    name: str
    ok: bool
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    columns: list[str] = field(default_factory=list)
    pages: int = 0
    checked_at: str = ""
    candidates: int = 0

    @property
    def item_count(self) -> int:
        return len(self.rows)

USER_AGENT = (
    "YijianSDU/0.1 (+https://github.com/; local-first open-source student project)"
)
DEFAULT_TIMEOUT = 20


def clean(value: str) -> str:
    return " ".join((value or "").split())


# 兼容旧代码里的函数名
_clean = clean


def http_get(url: str, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    """抓取网页。

    少数校园站点使用自签证书，首次握手会失败。这里退化为不校验证书再试一次，
    并在响应对象上标记 insecure=True，便于在来源状态里如实告知用户。
    """
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
    try:
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        response = requests.get(url, timeout=timeout, headers=headers, verify=False)
        response.raise_for_status()
        response.insecure = True
    response.encoding = response.apparent_encoding or "utf-8"
    return response


def error_reason(exc: Exception) -> str:
    """把异常翻译成用户能看懂的失败原因（需求 9）。"""
    if isinstance(exc, requests.exceptions.SSLError):
        return "站点证书异常，已跳过"
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return "连接超时，站点可能暂时无法访问"
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return "读取超时，页面响应过慢"
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        return "重定向次数过多，可能需要登录"
    if isinstance(exc, requests.exceptions.ConnectionError):
        return "无法建立连接，站点可能已失效"
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        status = response.status_code if response is not None else 0
        if status in (401, 403):
            return f"需要登录或没有访问权限（HTTP {status}）"
        if status == 404:
            return f"页面不存在（HTTP {status}），栏目可能已改版"
        return f"站点返回 HTTP {status}"
    if isinstance(exc, UnicodeDecodeError):
        return "页面编码无法识别，正文解析失败"
    return f"抓取失败：{type(exc).__name__}"


_error_reason = error_reason


BODY_SELECTORS = (
    ".v_news_content",
    "#vsb_content",
    ".article-content",
    ".arc_body",
    ".content",
    "article",
)


def extract_detail(url: str) -> dict[str, Any]:
    """读取通知正文、附件与图片。解析不到正文时 parse_failed=True。"""
    response = http_get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    body_node = None
    for selector in BODY_SELECTORS:
        body_node = soup.select_one(selector)
        if body_node:
            break
    body = clean(body_node.get_text(" ", strip=True)) if body_node else ""
    attachments: list[dict[str, str]] = []
    images: list[str] = []
    if body_node is not None:
        for anchor in body_node.select("a[href]"):
            href = urljoin(url, anchor.get("href", ""))
            label = clean(anchor.get_text(" ", strip=True)) or href.rsplit("/", 1)[-1]
            if href and href != url and href.startswith(("http://", "https://")):
                attachments.append(
                    {"name": label, "url": href, "kind": attachment_kind(href)}
                )
        for image in body_node.select("img[src]"):
            src = urljoin(url, image.get("src", ""))
            if src.startswith(("http://", "https://")):
                images.append(src)
    return {
        "body_text": body,
        "attachments": attachments,
        "images": images[:12],
        "parse_failed": body_node is None,
    }


_extract_detail = extract_detail
