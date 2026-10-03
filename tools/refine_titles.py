#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线模拟 + 回填：超长标题提炼（需求1）与正文日期兜底提取（需求3）。

提炼与日期规则**直接复用 server/classifier.py**，避免两处实现分叉：
  refine_title() / infer_date_from_text()

用法：
  python tools/refine_titles.py --sim        仅模拟并打印统计/样例，不写文件
  python tools/refine_titles.py --apply      重新提炼并写回 data/notices.json（先备份）
"""
import json
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTICES = os.path.join(ROOT, "data", "notices.json")
BACKUP_DIR = os.path.join(ROOT, "data", "backups")

sys.path.insert(0, ROOT)

from server.classifier import (  # noqa: E402
    group_key,
    infer_date_from_text,
    refine_title,
)


def load_notices():
    with open(NOTICES, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, (data["notices"] if isinstance(data, dict) and "notices" in data else data)


def _texts_of(notice: dict) -> tuple:
    """标题 / 摘要 / 正文 / 附件名 一并作为日期抽取来源（需求3：正文里一定有日期）。"""
    attachment_names = " ".join(
        str(item.get("name", "")) for item in (notice.get("attachments") or [])
    )
    return (
        notice.get("title"),
        notice.get("summary"),
        notice.get("body_text"),
        attachment_names,
    )


def _has_any_time(notice: dict) -> bool:
    times = notice.get("times") or {}
    keys = ("event_start", "event_end", "signup_start", "result_at", "exam_at")
    return any(times.get(k) for k in keys)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--sim"
    _, notices = load_notices()
    print("总条数:", len(notices))

    long = [n for n in notices if len(n.get("title") or "") > 40]
    print("title>40 条数:", len(long))

    still_long = 0
    examples = []
    for n in long:
        raw = n.get("title") or ""
        ref = refine_title(raw)
        if len(ref) > 40:
            still_long += 1
        if len(examples) < 16:
            examples.append((raw, ref))

    print("提炼后仍 >40 的条数(含真长标题):", still_long)
    print("\n===== 样例（原始 → 提炼后）=====")
    for raw, ref in examples:
        print(f"[原 {len(raw)}] {raw[:130]}")
        print(f"[新 {len(ref)}] {ref}")
        print("------")

    # 需求3 诊断：既无发布时间、也无活动时间节点的条目
    null_date = 0
    extractable = 0
    null_examples = []
    for n in notices:
        if n.get("published_at") or n.get("inferred_date") or _has_any_time(n):
            continue
        null_date += 1
        d = infer_date_from_text(*_texts_of(n))
        if d:
            extractable += 1
        elif len(null_examples) < 10:
            null_examples.append((n.get("id"), n.get("source_id"), (n.get("title") or "")[:50]))
    print("\n===== 需求3：无任何日期的条数:", null_date, "=====")
    print("其中可从 title/summary/body/附件名 提取到日期的条数:", extractable,
          f"({100 * extractable // max(1, null_date)}%)")
    print("完全无日期可提取的样例:")
    for e in null_examples:
        print("  ", e)

    if mode == "--apply":
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = os.path.join(BACKUP_DIR, f"notices-before-refine-{stamp}.json")
        shutil.copy2(NOTICES, backup)

        changed = 0
        inferred_added = 0
        for n in notices:
            raw = n.get("title") or ""
            ref = refine_title(raw)
            if ref != raw:
                n["title"] = ref
                n["official_title"] = ref
                n["group_key"] = group_key(ref)
                changed += 1
            if not n.get("published_at") and not _has_any_time(n):
                d = infer_date_from_text(*_texts_of(n))
                if d and not n.get("inferred_date"):
                    n["inferred_date"] = d
                    inferred_added += 1
        with open(NOTICES, "w", encoding="utf-8") as f:
            json.dump(notices, f, ensure_ascii=False, indent=2)
        print(f"\n[apply] 备份 → {backup}")
        print(f"[apply] 已重新提炼标题 {changed} 条，补充推断日期 {inferred_added} 条，写回完成。")


if __name__ == "__main__":
    main()
