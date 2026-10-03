"""从山东大学官方目录自动发现新网站（需求 9）。

只收录 *.sdu.edu.cn 域名，跳过登录 / 邮箱 / 服务大厅等无关入口。
"""

from __future__ import annotations

import hashlib
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from server.sources.common import USER_AGENT, http_get
from server.sources.official_sites import SourceConfig

DIRECTORIES = [
    ("学院与研究院", "https://www.sdu.edu.cn/zzjg/xysz.htm"),
    ("管理服务机构", "https://www.sdu.edu.cn/zzjg/glfw.htm"),
    ("直属附属单位", "https://www.sdu.edu.cn/zzjg/zsfs.htm"),
]

EXCLUDED_HOSTS = {
    "www.sdu.edu.cn",
    "sdu.edu.cn",
    "ehall.sdu.edu.cn",
    "service.sdu.edu.cn",
    "sdsh.sdu.edu.cn",
    "mail.sdu.edu.cn",
    "en.sdu.edu.cn",
    "fr.sdu.edu.cn",
    "new.sdu.edu.cn",
    "passport.sdu.edu.cn",
    "vpn.sdu.edu.cn",
}

EXCLUDED_LABELS = {
    "邮箱登录",
    "服务大厅",
    "信息服务",
    "校长信箱",
    "English",
    "Français",
    "旧站入口",
    "电话查询",
    "交通班车",
    "档案查询",
    "校外访问",
    "信息公开",
    "招标采购",
}

# 名称里出现这些词说明是服务系统而不是内容站点
EXCLUDED_NAME_PARTS = ("邮箱", "系统", "登录", "平台", "VPN", "服务大厅")


def _source_id(hostname: str) -> str:
    digest = hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:12]
    return f"sdu-auto-{digest}"


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def discover_sources(skip_hosts: set[str] | None = None) -> list[SourceConfig]:
    skip = set(skip_hosts or set()) | EXCLUDED_HOSTS
    discovered: dict[str, SourceConfig] = {}
    for scope, directory_url in DIRECTORIES:
        try:
            response = http_get(directory_url, timeout=20)
        except (requests.RequestException, UnicodeDecodeError):
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("a[href]"):
            label = _clean(anchor.get_text(" ", strip=True))
            if not label or label in EXCLUDED_LABELS or len(label) > 50:
                continue
            if any(part in label for part in EXCLUDED_NAME_PARTS):
                continue
            url = urljoin(directory_url, anchor.get("href", ""))
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if (
                not host
                or host in skip
                or not host.endswith(".sdu.edu.cn")
                or host in discovered
            ):
                continue
            homepage = f"{parsed.scheme or 'https'}://{host}/"
            discovered[host] = SourceConfig(
                id=_source_id(host),
                name=label,
                scope=scope,
                list_urls=(homepage,),
                max_items=24,
                detail_budget=10,
                max_pages=2,
                auto_columns=True,
            )
    return sorted(discovered.values(), key=lambda item: item.name)
