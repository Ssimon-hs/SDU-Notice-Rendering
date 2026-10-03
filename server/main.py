"""一键山大本地 API。

结构（控制器 → 服务层 → 抓取层）：
- 控制器：本文件的路由，只做参数解析与响应封装；
- 服务层：server/services.py，承载筛选、搜索、推荐、日历等业务规则；
- 抓取层：server/sources/*，负责抓取与结构化抽取。

所有数据保存在本地 data/ 目录，不登录、不上传。
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import os

from server import services
from server.sources.discovery import discover_sources
from server.sources.official_sites import SOURCES, scan_source
from server.sources.sdu_main import scan_report
from server.store import (
    add_community_post,
    add_custom_source,
    append_feedback,
    create_backup,
    delete_community_post,
    list_backups,
    load_community_posts,
    load_custom_sources,
    set_community_post_status,
    load_feedback,
    load_notices,
    load_source_status,
    remove_custom_source,
    save_notices,
)

ROOT = Path(__file__).resolve().parents[1]
SCAN_LOCK = threading.Lock()
_SCAN_STATE: dict[str, Any] = {
    "running": False,
    "started_at": "",
    "finished_at": "",
    "checked_sources": 0,
    "total_sources": 0,
    "new_items": 0,
    "changed_items": 0,
    "failed": [],
    "error": "",
}
_DISCOVERED_CACHE: list[Any] | None = None

app = FastAPI(title="一键山大 API", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8765",
        "http://localhost:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApiError(Exception):
    """服务层抛出的可读错误。"""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@app.exception_handler(ApiError)
def handle_api_error(_request: Any, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": exc.message})


@app.exception_handler(Exception)
def handle_unexpected(_request: Any, exc: Exception) -> JSONResponse:
    # 不把堆栈返回给客户端，只给一个稳定的结构。
    return JSONResponse(status_code=500, content={"error": f"服务内部错误：{type(exc).__name__}"})


# ------------------------------------------------------------------ 来源


def all_sources() -> list[Any]:
    """内置来源 + 从官方目录自动发现的来源 + 用户添加的来源。"""
    global _DISCOVERED_CACHE
    custom = [
        services.custom_source_config(item)
        for item in load_custom_sources()
        if item.get("enabled", True)
    ]
    return list(SOURCES) + list(discovered_sources()) + custom


def discovered_sources() -> list[Any]:
    global _DISCOVERED_CACHE
    if _DISCOVERED_CACHE is None:
        known_hosts = {services.host_of(source.list_url) for source in SOURCES}
        try:
            _DISCOVERED_CACHE = discover_sources({host for host in known_hosts if host})
        except Exception:  # noqa: BLE001 - 目录不可达时不影响其他来源
            _DISCOVERED_CACHE = []
    return _DISCOVERED_CACHE


def invalidate_source_cache() -> None:
    global _DISCOVERED_CACHE
    _DISCOVERED_CACHE = None


# ------------------------------------------------------------------ 健康检查


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "name": "一键山大",
        "version": "0.5.0",
        "notices": len(load_notices()),
        "sources": len(all_sources()),
    }


# ------------------------------------------------------------------ 通知


@app.get("/api/notices")
def notices(
    q: str = Query(default=""),
    active_only: bool = Query(default=True),
    kind: str = Query(default=""),
    category: str = Query(default=""),
    source: str = Query(default=""),
    audience: str = Query(default=""),
    campus: str = Query(default=""),
    needs_signup: str = Query(default=""),
    needs_material: str = Query(default=""),
    online: str = Query(default=""),
    has_attachment: str = Query(default=""),
    deadline_state: str = Query(default=""),
    prep_max: int = Query(default=0),
    relevance_min: int = Query(default=0),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    sort: str = Query(default="published"),
    include_body: bool = Query(default=True),
    limit: int = Query(default=200),
    offset: int = Query(default=0),
) -> dict[str, Any]:
    payload = {
        "q": q,
        "active_only": active_only,
        "kind": kind,
        "category": category,
        "source": source,
        "audience": audience,
        "campus": campus,
        "needs_signup": needs_signup,
        "needs_material": needs_material,
        "online": online,
        "has_attachment": has_attachment,
        "deadline_state": deadline_state,
        "prep_max": prep_max,
        "relevance_min": relevance_min,
        "date_from": date_from,
        "date_to": date_to,
        "sort": sort,
    }
    result = services.query_notices(payload, limit=limit, offset=offset)
    if not include_body:
        for item in result["items"]:
            item.pop("body_text", None)
            item.pop("images", None)
    return result


@app.get("/api/notices/{notice_id}")
def notice_detail(notice_id: str) -> dict[str, Any]:
    row = services.find_notice(notice_id)
    if not row:
        raise HTTPException(status_code=404, detail="notice_not_found")
    return services.decorate_notice(row)


@app.get("/api/related/{notice_id}")
def related_notices(notice_id: str) -> dict[str, Any]:
    """同一活动的通知 / 新闻 / 公示 / 结果互相关联（需求 11）。"""
    row = services.find_notice(notice_id)
    if not row:
        raise HTTPException(status_code=404, detail="notice_not_found")
    return {"items": services.related_notices(row)}


# ------------------------------------------------------------------ 搜索


@app.get("/api/search")
def search(
    q: str = Query(default=""),
    include_history: bool = Query(default=False),
    limit: int = Query(default=100),
) -> dict[str, Any]:
    return services.search(q, include_history=include_history, limit=limit)


@app.get("/api/facets")
def facets() -> dict[str, Any]:
    """全部通知页筛选项的可选值。"""
    return services.facets()


# ------------------------------------------------------------------ 信息源


@app.get("/api/sources")
def sources() -> dict[str, Any]:
    status = load_source_status()
    items = []
    for source in all_sources():
        entry = status.get(source.id, {})
        items.append(
            {
                "id": source.id,
                "name": source.name,
                "url": source.list_url,
                "scope": source.scope,
                "status": entry.get("status", "unknown"),
                "item_count": entry.get("item_count", 0),
                "last_checked": entry.get("last_checked", ""),
                "last_success": entry.get("last_success", ""),
                "error": entry.get("error", ""),
                "auto": source.id.startswith("sdu-auto-"),
                "custom": source.id.startswith("custom-"),
            }
        )
    failed = [item for item in items if item["status"] == "failed"]
    return {
        "items": items,
        "total": len(items),
        "healthy": sum(1 for item in items if item["status"] == "ok"),
        "failed": len(failed),
        "notices": len(load_notices()),
    }


class SourceIn(BaseModel):
    name: str = ""
    url: str
    scope: str = "用户添加"


@app.post("/api/sources")
def create_source(payload: SourceIn) -> dict[str, Any]:
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        raise ApiError("请填写以 http:// 或 https:// 开头的网址")
    entry = add_custom_source({"name": payload.name.strip(), "url": url, "scope": payload.scope})
    invalidate_source_cache()
    return {"item": entry}


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: str) -> dict[str, Any]:
    remove_custom_source(source_id)
    invalidate_source_cache()
    return {"removed": source_id}


# ------------------------------------------------------------------ 抓取


class ScanResult(BaseModel):
    started: bool
    message: str = ""


@app.post("/api/scan", response_model=ScanResult)
def scan_sources() -> ScanResult:
    if _SCAN_STATE["running"]:
        return ScanResult(started=False, message="已有一次检查正在运行")
    if not SCAN_LOCK.acquire(blocking=False):
        return ScanResult(started=False, message="已有一次检查正在运行")
    SCAN_LOCK.release()
    worker = threading.Thread(target=_run_scan, daemon=True)
    worker.start()
    return ScanResult(started=True, message="已在后台开始检查")


@app.get("/api/scan/status")
def scan_status() -> dict[str, Any]:
    return dict(_SCAN_STATE)


def _run_scan() -> None:
    if not SCAN_LOCK.acquire(blocking=False):
        return
    started = datetime.now().isoformat(timespec="seconds")
    _SCAN_STATE.update(
        {
            "running": True,
            "started_at": started,
            "finished_at": "",
            "checked_sources": 0,
            "new_items": 0,
            "changed_items": 0,
            "failed": [],
            "error": "",
        }
    )
    try:
        existing = {row["id"]: row for row in load_notices()}
        sources_list = all_sources()
        _SCAN_STATE["total_sources"] = len(sources_list) + 1

        reports: list[Any] = []
        main = scan_report()
        reports.append(main.report)
        _SCAN_STATE["checked_sources"] = 1

        with ThreadPoolExecutor(max_workers=8) as executor:
            jobs = {executor.submit(scan_source, source): source for source in sources_list}
            for future in as_completed(jobs):
                try:
                    reports.append(future.result())
                except Exception as exc:  # noqa: BLE001
                    source = jobs[future]
                    reports.append(
                        services.empty_report(source, f"抓取异常：{type(exc).__name__}")
                    )
                _SCAN_STATE["checked_sources"] += 1

        incoming: list[dict[str, Any]] = []
        for report in reports:
            incoming.extend(report.rows)

        merged, new_items, changed_items = services.merge_notices(existing, incoming)
        failed = services.persist_reports(reports)
        save_notices(merged, backup=True)
        services.link_related(merged)
        save_notices(merged)

        _SCAN_STATE.update(
            {
                "new_items": new_items,
                "changed_items": changed_items,
                "failed": failed,
                "finished_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        _SCAN_STATE["error"] = f"检查失败：{type(exc).__name__}: {exc}"
    finally:
        _SCAN_STATE["running"] = False
        SCAN_LOCK.release()


# ------------------------------------------------------------------ 校历


@app.get("/api/calendar")
def calendar(month: str = Query(default="")) -> dict[str, Any]:
    return services.calendar(month)


# ------------------------------------------------------------------ 反馈


class FeedbackIn(BaseModel):
    notice_id: str = ""
    kind: str = Field(default="classification")
    message: str = ""
    suggestion: str = ""


@app.post("/api/feedback")
def feedback(payload: FeedbackIn) -> dict[str, Any]:
    entry = append_feedback(payload.model_dump())
    return {"item": entry, "total": len(load_feedback())}


# ------------------------------------------------------------------ 数据管理


@app.post("/api/backup")
def backup() -> dict[str, Any]:
    name = create_backup()
    return {"name": name or "", "items": list_backups()}


@app.get("/api/backups")
def backups() -> dict[str, Any]:
    return {"items": list_backups()}


@app.get("/api/export")
def export_data() -> dict[str, Any]:
    return {
        "version": "0.5.0",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "notices": load_notices(),
        "sources": load_custom_sources(),
        "source_status": load_source_status(),
        "feedback": load_feedback(),
    }


class ImportIn(BaseModel):
    notices: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


@app.post("/api/import")
def import_data(payload: ImportIn) -> dict[str, Any]:
    if not payload.notices:
        raise ApiError("导入内容里没有通知数据")
    merged, new_items, _ = services.merge_notices(
        {row["id"]: row for row in load_notices()}, payload.notices
    )
    save_notices(merged, backup=True)
    for item in payload.sources:
        if item.get("url"):
            add_custom_source(item)
    invalidate_source_cache()
    return {"total": len(merged), "new_items": new_items}


# ------------------------------------------------------------------ 活动预测（需求4）

@app.get("/api/forecast")
def forecast(source: str | None = Query(default=None, description="按来源名/ID筛选预测")) -> dict:
    from server.forecast import build_forecast

    return build_forecast(source=source)


# ------------------------------------------------------------------ 社区投稿（游客邮箱 / 管理员密码发布）

# 管理员审核投稿的密码；凭此密码可进入审核台，对待审核草稿执行通过/驳回。
# 安全约定：密码不写入源码（仓库公开），优先读环境变量 COMMUNITY_ADMIN_PASSWORD，
# 其次读仓库根目录的 .env 文件；.env 已被 .gitignore 排除，不会被提交。
_ENV_ADMIN_KEY = "COMMUNITY_ADMIN_PASSWORD"


def _read_env_file(key: str) -> str:
    """从仓库根 .env 读取键值，不引入第三方依赖。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return ""
    try:
        raw = env_file.read_text(encoding="utf-8")
    except OSError:
        return ""
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


COMMUNITY_ADMIN_PASSWORD = (os.environ.get(_ENV_ADMIN_KEY) or _read_env_file(_ENV_ADMIN_KEY)).strip()


def verify_admin_password(password: str) -> None:
    """校验管理员密码。未配置密码时一律拒绝，避免公开仓库出现无人把关的开放审核台。"""
    if not COMMUNITY_ADMIN_PASSWORD or password != COMMUNITY_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="密码错误")


class CommunityDraftIn(BaseModel):
    title: str = ""
    tag: str = "其他"
    content: str = ""
    author: str = "社区投稿"


class CommunityPasswordIn(BaseModel):
    password: str = ""


@app.get("/api/community/posts")
def community_posts() -> dict[str, Any]:
    # 公开信息流：仅返回已通过审核、对所有用户可见的帖子。
    rows = [r for r in load_community_posts() if r.get("status") == "published"]
    return {"items": rows, "total": len(rows)}


@app.post("/api/community/posts")
def community_draft(payload: CommunityDraftIn) -> dict[str, Any]:
    # 任何人可投稿草稿，无需密码，状态为 pending（暂存到管理员审核目录）。
    if not payload.title.strip() or not payload.content.strip():
        raise ApiError("标题和内容都不能为空")
    entry = add_community_post(
        {"title": payload.title, "tag": payload.tag, "content": payload.content, "author": payload.author, "status": "pending"}
    )
    return {"item": entry, "total": len(load_community_posts())}


@app.post("/api/community/moderate")
def community_moderate(payload: CommunityPasswordIn) -> dict[str, Any]:
    # 管理员审核台：凭密码返回全部帖子（已发布 + 待审核），供审核与审批。
    verify_admin_password(payload.password)
    rows = load_community_posts()
    pending = [r for r in rows if r.get("status") != "published"]
    published = [r for r in rows if r.get("status") == "published"]
    return {"pending": pending, "published": published, "total": len(rows)}


@app.post("/api/community/posts/{post_id}/approve")
def community_approve(post_id: str, payload: CommunityPasswordIn) -> dict[str, Any]:
    # 管理员审核通过：置为 published，对所有用户可见。
    verify_admin_password(payload.password)
    updated = set_community_post_status(post_id, "published")
    if updated is None:
        raise ApiError("未找到该投稿")
    return {"item": updated, "total": len(load_community_posts())}


@app.post("/api/community/posts/{post_id}/reject")
def community_reject(post_id: str, payload: CommunityPasswordIn) -> dict[str, Any]:
    # 管理员驳回：直接删除该待审核草稿。
    verify_admin_password(payload.password)
    ok = delete_community_post(post_id)
    return {"ok": ok, "total": len(load_community_posts())}


@app.delete("/api/community/posts/{post_id}")
def community_delete(post_id: str, payload: CommunityPasswordIn) -> dict[str, Any]:
    # 管理员删除已发布帖子（发现已发布内容不合适时）。
    verify_admin_password(payload.password)
    ok = delete_community_post(post_id)
    return {"ok": ok, "total": len(load_community_posts())}


# ------------------------------------------------------------------ 前端静态托管

from fastapi.staticfiles import StaticFiles  # noqa: E402

_DIST = ROOT / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
