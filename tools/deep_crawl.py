#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深度抓取：对全部信息源翻页抓取近三年通知列表，生成活动预测用的编年数据。

- 只抓列表页（detail_budget=0），速度快、覆盖广；
- 近三年过滤由 official_sites.within_years 保证；
- 写入 data/history.json（纯历史库）；并「仅新增」合并进 data/notices.json
  （不覆盖已有正文更完整的行）。

用法：
  python tools/deep_crawl.py               默认 pages=10 items=220 workers=8
  DEEP_PAGES=14 python tools/deep_crawl.py 翻更多页
"""
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.sources.official_sites import SOURCES, scan_source  # noqa: E402
from server.store import load_notices, save_notices  # noqa: E402

DEEP_PAGES = int(os.environ.get("DEEP_PAGES", "10"))
DEEP_ITEMS = int(os.environ.get("DEEP_ITEMS", "220"))
WORKERS = int(os.environ.get("DEEP_WORKERS", "8"))
HISTORY = os.path.join(ROOT, "data", "history.json")


def deep_config(cfg):
    return replace(cfg, max_items=DEEP_ITEMS, detail_budget=0, max_pages=DEEP_PAGES)


def main():
    print(f"来源数: {len(SOURCES)}  pages={DEEP_PAGES} items={DEEP_ITEMS} workers={WORKERS}")
    rows = []
    failed = []
    ok_count = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs = {pool.submit(scan_source, deep_config(c)): c for c in SOURCES}
        done = 0
        for future in as_completed(jobs):
            cfg = jobs[future]
            done += 1
            try:
                report = future.result()
            except Exception as exc:  # noqa: BLE001
                failed.append((cfg.name, f"异常 {type(exc).__name__}"))
                continue
            if report.ok and report.rows:
                ok_count += 1
                rows.extend(report.rows)
            else:
                failed.append((cfg.name, report.error or "空结果"))
            if done % 20 == 0:
                print(f"  进度 {done}/{len(SOURCES)}  已得 {len(rows)} 条  "
                      f"用时 {time.time() - t0:.0f}s")

    # 去重（同 id 取首次）
    by_id = {}
    for row in rows:
        by_id.setdefault(row["id"], row)
    history = list(by_id.values())

    # 写入独立历史库
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": len(SOURCES),
        "pages_per_source": DEEP_PAGES,
        "count": len(history),
        "failed": [{"name": n, "error": e} for n, e in failed],
    }
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "items": history}, f, ensure_ascii=False, indent=2)

    # 仅新增合并进 notices.json（保留已有更完整的正文行）
    existing = {r["id"]: r for r in load_notices()}
    added = 0
    for row in history:
        if row["id"] not in existing:
            existing[row["id"]] = row
            added += 1
    merged = list(existing.values())
    backup_dir = os.path.join(ROOT, "data", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(os.path.join(ROOT, "data", "notices.json"),
                 os.path.join(backup_dir, f"notices-before-deepcrawl-{stamp}.json"))
    save_notices(merged, backup=False)

    print(f"\n完成：抓取 {len(history)} 条（成功来源 {ok_count}，失败 {len(failed)}）")
    print(f"写入 {HISTORY}")
    print(f"合并进 notices.json 新增 {added} 条（原 {len(existing) - added} → 现 {len(merged)}）")
    if failed:
        print("失败来源（前 15）：")
        for n, e in failed[:15]:
            print(f"  - {n}: {e}")


if __name__ == "__main__":
    main()
