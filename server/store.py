"""本地数据读写层。

所有数据默认保存在项目 data/ 目录（本地优先，不上传）。
- notices.json   抓取到的通知
- source_status.json  每个信息源的抓取结果（成功 / 失败 / 数量 / 失败原因）
- custom_sources.json 用户自行添加的网站
- backups/            自动备份

写文件一律先写临时文件再原子替换，避免中途断电损坏数据。
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
NOTICE_FILE = DATA_DIR / "notices.json"
SOURCE_STATUS_FILE = DATA_DIR / "source_status.json"
CUSTOM_SOURCE_FILE = DATA_DIR / "custom_sources.json"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
MAX_BACKUPS = 5


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    _ensure_dir()
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return default


# ------------------------------------------------------------------ 通知


def load_notices() -> list[dict[str, Any]]:
    return _read_json(NOTICE_FILE, [])


def save_notices(items: list[dict[str, Any]], backup: bool = False) -> None:
    if backup:
        create_backup()
    _write_json(NOTICE_FILE, items)


def notice_index() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in load_notices() if row.get("id")}


# ------------------------------------------------------------------ 备份


def create_backup() -> str | None:
    if not NOTICE_FILE.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"notices-{stamp}.json"
    shutil.copy2(NOTICE_FILE, target)
    existing = sorted(BACKUP_DIR.glob("notices-*.json"))
    for stale in existing[:-MAX_BACKUPS]:
        try:
            stale.unlink()
        except OSError:
            pass
    return target.name


def list_backups() -> list[dict[str, Any]]:
    if not BACKUP_DIR.exists():
        return []
    rows = []
    for path in sorted(BACKUP_DIR.glob("notices-*.json"), reverse=True):
        rows.append(
            {
                "name": path.name,
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                    timespec="seconds"
                ),
            }
        )
    return rows


# ------------------------------------------------------------------ 信息源状态


def load_source_status() -> dict[str, dict[str, Any]]:
    return _read_json(SOURCE_STATUS_FILE, {})


def save_source_status(status: dict[str, dict[str, Any]]) -> None:
    _write_json(SOURCE_STATUS_FILE, status)


def record_source_result(
    source_id: str,
    *,
    name: str,
    url: str = "",
    scope: str = "",
    ok: bool,
    item_count: int = 0,
    error: str = "",
    checked_at: str | None = None,
) -> dict[str, Any]:
    status = load_source_status()
    previous = status.get(source_id, {})
    entry = {
        "id": source_id,
        "name": name,
        "url": url or previous.get("url", ""),
        "scope": scope or previous.get("scope", ""),
        "status": "ok" if ok else "failed",
        "item_count": item_count if ok else previous.get("item_count", 0),
        "error": "" if ok else (error or "抓取失败"),
        "last_checked": checked_at
        or datetime.now().isoformat(timespec="seconds"),
        "last_success": (
            entry_last_success(checked_at) if ok else previous.get("last_success", "")
        ),
    }
    status[source_id] = entry
    save_source_status(status)
    return entry


def entry_last_success(checked_at: str | None) -> str:
    return checked_at or datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------ 自定义源


def load_custom_sources() -> list[dict[str, Any]]:
    return _read_json(CUSTOM_SOURCE_FILE, [])


def add_custom_source(payload: dict[str, Any]) -> dict[str, Any]:
    rows = load_custom_sources()
    source_id = payload.get("id") or f"custom-{len(rows) + 1}-{abs(hash(payload.get('url', ''))) % 10**8}"
    entry = {
        "id": source_id,
        "name": payload.get("name") or payload.get("url", "自定义来源"),
        "url": payload.get("url", ""),
        "scope": payload.get("scope", "用户添加"),
        "enabled": True,
    }
    rows = [row for row in rows if row.get("id") != source_id]
    rows.append(entry)
    _write_json(CUSTOM_SOURCE_FILE, rows)
    return entry


def remove_custom_source(source_id: str) -> None:
    rows = [row for row in load_custom_sources() if row.get("id") != source_id]
    _write_json(CUSTOM_SOURCE_FILE, rows)


# ------------------------------------------------------------------ 反馈


def load_feedback() -> list[dict[str, Any]]:
    return _read_json(FEEDBACK_FILE, [])


def append_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    rows = load_feedback()
    entry = {
        **payload,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    rows.append(entry)
    _write_json(FEEDBACK_FILE, rows[-500:])
    return entry


# ------------------------------------------------------------------ 社区投稿

# 社区投稿：任何人可投递草稿（status=pending），经管理员凭密码审核通过后
# 置为 published 并对所有用户可见。数据持久化到本地，所有客户端加载同一份，
# 因此任一端新投稿/审核结果对其他使用的用户也可见。


COMMUNITY_FILE = DATA_DIR / "community_posts.json"


def load_community_posts() -> list[dict[str, Any]]:
    return _read_json(COMMUNITY_FILE, [])


def save_community_posts(rows: list[dict[str, Any]]) -> None:
    _write_json(COMMUNITY_FILE, rows[-500:])


def add_community_post(payload: dict[str, Any]) -> dict[str, Any]:
    rows = load_community_posts()
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    post_id = f"cp-{stamp}-{abs(hash(payload.get('title', ''))) % 10**6}"
    entry = {
        "id": post_id,
        "title": (payload.get("title") or "").strip(),
        "tag": (payload.get("tag") or "其他").strip(),
        "content": (payload.get("content") or "").strip(),
        "author": (payload.get("author") or "社区投稿").strip(),
        "status": (payload.get("status") or "pending").strip(),
        "at": datetime.now().strftime("%Y-%m-%d"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    rows.append(entry)
    save_community_posts(rows)
    return entry


def set_community_post_status(post_id: str, status: str) -> dict[str, Any] | None:
    rows = load_community_posts()
    found = None
    for row in rows:
        if row.get("id") == post_id:
            row["status"] = status
            row["approved_at"] = datetime.now().isoformat(timespec="seconds")
            found = row
            break
    if found is None:
        return None
    save_community_posts(rows)
    return found


def delete_community_post(post_id: str) -> bool:
    before = load_community_posts()
    rows = [row for row in before if row.get("id") != post_id]
    if len(rows) == len(before):
        return False
    save_community_posts(rows)
    return True


# ------------------------------------------------------------------ 搜索索引


def searchable_text(row: dict[str, Any]) -> str:
    """把一条通知的全部可搜索内容拼成一个字符串。"""
    parts = [
        row.get("title", ""),
        row.get("summary", ""),
        row.get("official_title", ""),
        row.get("body_text", ""),
        row.get("source", ""),
        row.get("source_name", ""),
        row.get("org_unit", ""),
        row.get("location", ""),
        row.get("campus", ""),
        row.get("official_url", ""),
        " ".join(row.get("categories", []) or []),
        " ".join(row.get("audience", []) or []),
        " ".join(row.get("keywords", []) or []),
        " ".join(
            [
                item.get("name", "")
                for item in (row.get("materials", []) or [])
            ]
        ),
        " ".join(
            [
                f"{item.get('name', '')} {item.get('url', '')}"
                for item in (row.get("attachments", []) or [])
            ]
        ),
        " ".join(
            [
                f"{key} {value}"
                for key, value in (row.get("times", {}) or {}).items()
                if value
            ]
        ),
    ]
    return " ".join(str(part) for part in parts if part).casefold()


def build_search_index() -> list[tuple[str, str]]:
    return [(row.get("id", ""), searchable_text(row)) for row in load_notices()]
