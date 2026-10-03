"""一键山大 · 全量抓取运行器（后台）。

复用既有抓取层：主站 + official_sites.SOURCES（全量学院/研究院/机关/学生门户）
+ discovery 兜底。每完成一个来源就把进度写入 data/_scan_progress.json，
并输出一行日志，便于前端 / 用户查看进度条。
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from server import services
from server.sources.discovery import discover_sources
from server.sources.official_sites import SOURCES, scan_source
from server.sources.sdu_main import scan_report
from server.store import load_custom_sources, load_notices, save_notices

ROOT = Path(__file__).resolve().parent
PROGRESS = ROOT / "data" / "_scan_progress.json"
_lock = threading.Lock()


def write_progress(state: dict) -> None:
    PROGRESS.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    custom = [
        services.custom_source_config(item)
        for item in load_custom_sources()
        if item.get("enabled", True)
    ]
    discovered = []
    try:
        known_hosts = {services.host_of(s.list_url) for s in SOURCES}
        discovered = discover_sources({h for h in known_hosts if h})
    except Exception:
        discovered = []

    sources_list = list(SOURCES) + list(discovered) + list(custom)
    total = len(sources_list) + 1  # +1 主站

    state = {
        "running": True,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": "",
        "checked_sources": 0,
        "total_sources": total,
        "new_items": 0,
        "changed_items": 0,
        "failed": [],
        "log": [],
        "error": "",
    }
    write_progress(state)
    print(f"[scan] 共 {total} 个来源（主站 + {len(SOURCES)} 内置 + {len(discovered)} 发现 + {len(custom)} 自定义）")

    existing = {row["id"]: row for row in load_notices()}
    reports = []

    def tick(report, source_name):
        with _lock:
            state["checked_sources"] += 1
            if not report.ok:
                state["failed"].append({"id": getattr(report, "source_id", ""), "name": source_name, "reason": report.error})
            pct = int(state["checked_sources"] / total * 100)
            line = f"[{state['checked_sources']}/{total} {pct}%] {source_name}: ok={report.ok} 命中={report.item_count}"
            state["log"].append(line)
            print(line, flush=True)
            write_progress(state)

    # 主站
    main_report = scan_report().report
    reports.append(main_report)
    tick(main_report, "山东大学主站")

    with ThreadPoolExecutor(max_workers=8) as ex:
        jobs = {ex.submit(scan_source, s): s for s in sources_list}
        for fut in as_completed(jobs):
            src = jobs[fut]
            try:
                rep = fut.result()
            except Exception as exc:  # noqa: BLE001
                rep = services.empty_report(src, f"抓取异常：{type(exc).__name__}")
            reports.append(rep)
            tick(rep, src.name)

    incoming = []
    for rep in reports:
        incoming.extend(rep.rows)

    merged, new_items, changed_items = services.merge_notices(existing, incoming)
    failed = services.persist_reports(reports)
    save_notices(merged, backup=True)
    services.link_related(merged)
    save_notices(merged)

    state.update(
        {
            "running": False,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "new_items": new_items,
            "changed_items": changed_items,
            "total_items": len(merged),
            "failed": failed,
        }
    )
    write_progress(state)
    print(f"[scan] 完成：合并后共 {len(merged)} 条，本次新增 {new_items}，更新 {changed_items}，失败 {len(failed)} 个来源")


if __name__ == "__main__":
    main()
