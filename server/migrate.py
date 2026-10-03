"""把旧版 notices.json 迁移到 0.5 结构。

- 补齐 categories / kind / audience / times / materials / steps / campus 等字段；
- 修复抓取误判的未来发布时间（需求 13：禁止把发布时间误认为截止时间）；
- 重新计算截止状态、关联同组活动。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from server import services
from server.classifier import (
    classify,
    group_key,
    is_expired,
    next_action_date,
    sanitize_published,
    within_years,
)
from server.store import load_notices, save_notices


def run() -> dict[str, int]:
    rows = load_notices()
    today = date.today().isoformat()
    stats = {"total": len(rows), "reclassified": 0, "dropped_date": 0, "expired": 0}

    migrated: list[dict[str, Any]] = []  # noqa: F821
    for row in rows:
        published = sanitize_published(row.get("published_at"), today)
        if row.get("published_at") and not published:
            stats["dropped_date"] += 1
            row["published_at"] = None

        # 只用正文做结构化抽取；没有正文时只保留标题级判断
        analysis = classify(row.get("title", ""), row.get("body_text") or "")
        row.update(analysis)
        stats["reclassified"] += 1
        if not row.get("body_text"):
            row["materials"] = []
            row["steps"] = ["阅读并核对官方原文"]

        deadline = row.get("deadline")
        if deadline and published and deadline < published:
            deadline = None
            row["deadline"] = None
        row["status"] = "expired" if is_expired(deadline, today) else "active"
        if row["status"] == "expired":
            stats["expired"] += 1
            row["body_text"] = ""
            row["attachments"] = []
            row["attachment_count"] = 0
        row["group_key"] = row.get("group_key") or group_key(row.get("title", ""))
        row["official_title"] = row.get("official_title") or row.get("title", "")
        row["source_name"] = row.get("source_name") or row.get("source", "")
        row["org_unit"] = row.get("org_unit") or row.get("source", "")
        row["campus"] = row.get("campus") or ""
        row["images"] = row.get("images") or []
        row["next_action"] = next_action_date(row.get("times") or {}, today)
        migrated.append(row)

    # 三年以外且没有正文的历史条目保留但标记为 expired
    for row in migrated:
        published = row.get("published_at")
        if published and not within_years(published, 3, today) and row["status"] == "active":
            row["status"] = "expired"

    services.link_related(migrated)
    save_notices(migrated, backup=True)
    return stats


if __name__ == "__main__":
    print(run())
