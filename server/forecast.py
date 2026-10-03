"""活动预测（需求4/需求5 重做 + 内容深度增强）：基于已抓取的近三年通知，按学院 / 部门统计月份与星期共性，
并在每个日期上标注「代表性活动」——活动名称、主要内容、可跳转到原文正文的链接。

设计要点：
- 数据来源为本地 notices.json（深度抓取后已含近三年、按信息源划分的通知），无需重新抓取；
- 以「发布时间 / 推断日期 / 活动时间」作为每条通知的代表日期；
- 冲突与变动按共性处理：若某来源活动明显集中在周末或工作日，则预测只标注其偏好星期；
- 年度固定活动（如开学典礼、迎新晚会、毕业典礼）通过「跨年主题聚类」识别，
  每年都会出现的活动被标记 annual=true，绝不会因当月频次低而被省略；
- 每个代表性活动携带可跳转到通知正文的 id 与主要内容摘要；
- 内容深度增强：主题识别从原来 21 个年度强特征词扩展到覆盖讲座 / 竞赛 / 招聘 / 志愿 /
  展览 / 文艺 / 评奖 / 科研 / 会议 / 培训 / 招生 / 考试 / 报名等常见活动类型，并结合
  分类器给出的 categories 做回退，确保「一年内不止三个活动」能被充分挖掘。
"""

from __future__ import annotations

import calendar
import re
from collections import defaultdict
from datetime import date, datetime

from server.classifier import CN_DATE
from server.store import load_notices

# ---------------------------------------------------------------- 活动主题词库
# 顺序敏感：越具体的主题越靠前，避免「迎新」抢先于「迎新晚会」等。
# 每个主题为 (主题名, (关键词...))；标题命中任一关键词即归入该主题。
THEME_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("开学迎新", ("开学典礼", "迎新晚会", "迎新生", "迎新季", "新生入学", "开学季", "开学第一课", "迎新")),
    ("毕业典礼", ("毕业典礼", "毕业晚会", "学位授予", "毕业")),
    ("军训", ("军训",)),
    ("运动会/体育", ("田径运动会", "运动会", "体育节")),
    ("学术讲座", ("学术讲座", "讲座", "报告会", "讲坛", "论坛", "学术沙龙", "大讲堂", "讲堂", "学术报告")),
    ("竞赛/比赛", ("竞赛", "大赛", "挑战赛", "选拔赛", "辩论赛", "演讲比赛", "知识竞赛", "比赛", "联赛", "杯赛")),
    ("文艺晚会/文化节", ("晚会", "文化节", "艺术节", "歌手", "戏剧", "舞蹈", "合唱", "音乐节", "朗诵", "才艺")),
    ("招聘/宣讲会", ("双选会", "宣讲会", "招聘会", "招聘", "校招", "春招", "秋招")),
    ("社会实践/志愿", ("社会实践", "三下乡", "志愿服务", "志愿者", "支教", "公益", "西部计划")),
    ("展览/展演", ("展览", "画展", "影展", "作品展", "展演", "摄影展")),
    ("校庆/节日活动", ("校庆", "元旦", "五四", "国庆", "中秋", "端午", "妇女节", "青年节", "科技节")),
    ("评奖评优", ("奖学金", "评优", "三好学生", "优秀学生", "先进", "十佳", "荣誉称号", "表彰")),
    ("科研/论文征集", ("科研项目", "课题", "基金", "征文", "论文征集", "立项", "科研成果")),
    ("会议/年会", ("年会", "峰会", "大会", "研讨会", "座谈会", "工作会")),
    ("培训/工作坊", ("培训", "研修", "工作坊", "训练营", "夏令营")),
    ("招生/保研", ("招生", "保研", "推免", "考研", "复试", "调剂")),
    ("考试/选课", ("选课", "四六级", "考试", "补考", "答辩", "成绩")),
    ("报名/招募", ("招募", "招新", "纳新", "遴选", "征集令")),
]

# 分类器给出的 categories → 活动主题（仅对指向明确的类别做回退，避免噪音）。
CATEGORY_THEME: dict[str, str | None] = {
    "讲座／论坛": "学术讲座",
    "竞赛通知": "竞赛/比赛",
    "实习／招聘／就业": "招聘/宣讲会",
    "志愿服务／社会实践": "社会实践/志愿",
    "招生／保研／考研": "招生/保研",
    "奖学金／评奖评优": "评奖评优",
    "考试／选课／教学安排": "考试/选课",
    "科研项目／论文征集": "科研/论文征集",
    "国际交流／交换项目": "国际交流/交换",
    "放假／校历／行政安排": "放假/校历",
    "活动通知": None,
    "公示／名单／结果": None,
    "普通新闻": None,
    "宣传报道": None,
    "后勤／宿舍／校园卡／网络服务": None,
    "紧急通知": None,
}


def _theme_of(title: str, categories: list[str] | None) -> str:
    """从标题抽取活动主题；标题无命中时用分类器类别回退。返回空串表示「非活动类，不单列」。"""
    if not title:
        return ""
    t = str(title)
    for theme, keys in THEME_RULES:
        for k in keys:
            if k in t:
                return theme
    for c in (categories or []):
        mapped = CATEGORY_THEME.get(c)
        if mapped:
            return mapped
    return ""


def _parse_any_date(text: str | None):
    """解析多种日期格式：ISO(2026-10-02) / 点分(2026.09.28) / 中文(2026年9月18日) / 无年份(9月29日)。"""
    if not text:
        return None
    text = str(text).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    for mm in CN_DATE.finditer(text):
        seg = mm.group(0)
        ymd = (
            re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", seg)
            or re.search(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})[日号]?)?", seg)
        )
        if ymd:
            y, mo = int(ymd.group(1)), int(ymd.group(2))
            d = int(ymd.group(3)) if ymd.group(3) else 1
            try:
                return date(y, mo, d)
            except ValueError:
                continue
        md = re.search(r"(\d{1,2})月(?:(\d{1,2})[日号]?)?", seg)
        if md:
            mo, d = int(md.group(1)), int(md.group(2)) if md.group(2) else 1
            try:
                return date(datetime.now().year, mo, d)
            except ValueError:
                continue
    return None


def _times_first(times: dict | None) -> str | None:
    if not times:
        return None
    for key in ("event_start", "event_end", "signup_start", "result_at", "exam_at"):
        if times.get(key):
            return times[key]
    return None


def _truncate(text: str, limit: int = 60) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t[:limit]


def build_forecast(year: int | None = None, source: str | None = None) -> dict:
    """生成活动预测。

    - year: 预测年份，缺省为今年；
    - source: 来源名（source_name 或 source_id）。传了则只统计该来源，
      返回的年 / 月 / 周视图只针对这一来源。
    """
    if year is None:
        year = datetime.now().year
    notices = load_notices()

    agg: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "monthly": [0] * 12, "weekdays": defaultdict(int), "cats": defaultdict(int),
                 "name": "", "scope": ""}
    )
    # 活动聚类桶：key=(source_id, month, theme) → 记录（含逐年份示例链接）
    act_bucket: dict[tuple, dict] = defaultdict(
        lambda: {"count": 0, "years": set(), "sources": set(),
                 "last_date": None, "by_year": {}, "summaries": []}
    )
    skipped = 0
    for n in notices:
        if source:
            src_name = n.get("source_name") or n.get("source") or ""
            src_id = n.get("source_id") or ""
            if source not in (src_name, src_id):
                continue
        d = _parse_any_date(
            n.get("published_at") or n.get("inferred_date") or _times_first(n.get("times"))
        )
        if not d:
            skipped += 1
            continue
        # 只统计近三年，避免久远数据干扰今年的节奏
        if d.year < year - 2:
            skipped += 1
            continue
        sid = n.get("source_id") or n.get("source") or "unknown"
        rec = agg[sid]
        rec["count"] += 1
        rec["monthly"][d.month - 1] += 1
        rec["weekdays"][d.weekday()] += 1
        for c in (n.get("categories") or []):
            if c == "待分类":
                continue
            rec["cats"][c] += 1
        rec["name"] = n.get("source_name") or n.get("source") or sid
        rec["scope"] = n.get("scope") or ""

        # ---- 活动聚类（主题命中才单列，避免噪音）----
        title = n.get("title") or ""
        theme = _theme_of(title, n.get("categories"))
        if theme:
            key = (sid, d.month, theme)
            b = act_bucket[key]
            b["count"] += 1
            b["years"].add(d.year)
            b["sources"].add(rec["name"])
            # 记录该年份的代表通知（同一年取最新一条覆盖）
            b["by_year"][d.year] = (n.get("id") or "", title, n.get("summary") or "")
            if b["last_date"] is None or d > b["last_date"]:
                b["last_date"] = d
            if n.get("summary"):
                b["summaries"].append(n.get("summary"))

    # 汇总各来源（同前）
    by_source: dict[str, dict] = {}
    for sid, rec in agg.items():
        total = rec["count"]
        wd = rec["weekdays"]
        weekend = wd.get(5, 0) + wd.get(6, 0)
        weekend_ratio = (weekend / total) if total else 0
        if weekend_ratio >= 0.55:
            bias = "weekend"
        elif weekend_ratio <= 0.35:
            bias = "weekday"
        else:
            bias = "mixed"
        top_cats = [c for c, _ in sorted(rec["cats"].items(), key=lambda x: -x[1])[:3]]
        by_source[sid] = {
            "id": sid,
            "name": rec["name"],
            "scope": rec["scope"],
            "count": total,
            "monthly": rec["monthly"],
            "weekdayBias": bias,
            "weekendRatio": round(weekend_ratio, 2),
            "topCategories": top_cats,
        }

    # 各 scope 来源数（年视图图例用）
    scopes: dict[str, int] = defaultdict(int)
    for s in by_source.values():
        scopes[s["scope"] or "其他"] += 1

    # ---------- 代表性活动条目（逐月）----------
    # 每个 (来源, 月份, 主题) 一组，跨年出现标记为年度活动；保留逐年份示例链接。
    activities: dict[int, list[dict]] = defaultdict(list)
    for (sid, month, theme), b in act_bucket.items():
        if not b["by_year"]:
            continue
        years = sorted(b["years"])
        annual = len(years) >= 2  # 跨年都出现 → 年度固定活动
        rep_year = max(years)
        rep_id, rep_title, rep_summary = b["by_year"][rep_year]
        examples = [
            {"year": y, "id": b["by_year"][y][0], "title": b["by_year"][y][1]}
            for y in years
        ]
        item = {
            "id": rep_id,                 # 用于跳转到通知正文（取最新一年代表）
            "title": rep_title,           # 完整标题
            "name": theme,                # 简短活动主题（学术讲座 / 运动会 …）
            "summary": _truncate(rep_summary, 90),  # 主要内容摘要
            "count": b["count"],
            "years": years,               # 出现过的年份（近三年）
            "annual": annual,             # 每年都会出现
            "month": month,
            "rep_day": b["last_date"].day if b["last_date"] else None,  # 锚定到历史最近一次日期
            "source": sorted(b["sources"])[0] if b["sources"] else "",
            "examples": examples,         # 逐年份示例链接，便于「三年内都发生过什么」
        }
        activities[month].append(item)

    # 每个月内按 annual 优先 + 次数排序
    for month in activities:
        activities[month].sort(key=lambda x: (0 if x["annual"] else 1, -x["count"]))

    # 每月自然语言概况（月视图底部「本月学院主要进行了…等活动」）
    month_summary_text: dict[int, str] = {}
    for m in range(1, 13):
        theme_counts: dict[str, int] = defaultdict(int)
        for a in activities[m]:
            theme_counts[a["name"]] += a["count"]
        top = [th for th, _ in sorted(theme_counts.items(), key=lambda x: -x[1])[:4]]
        month_summary_text[m] = (
            "本月学院主要进行了" + "、".join(top) + "等活动"
            if top else "本月暂无足够的历史活动规律可供预测"
        )

    monthly_summary = []
    for m in range(1, 13):
        active = [
            {"id": s, "name": r["name"], "count": r["monthly"][m - 1], "bias": r["weekdayBias"],
             "topCategory": (r["topCategories"][0] if r["topCategories"] else "")}
            for s, r in by_source.items()
            if r["monthly"][m - 1] > 0
        ]
        active.sort(key=lambda x: -x["count"])
        cats = defaultdict(int)
        for s, r in by_source.items():
            if r["monthly"][m - 1] > 0 and r["topCategories"]:
                cats[r["topCategories"][0]] += 1
        top_cat = max(cats.items(), key=lambda x: x[1])[0] if cats else ""
        monthly_summary.append(
            {"month": m, "sources": active, "total": sum(x["count"] for x in active),
             "topCategory": top_cat, "summary": month_summary_text[m]}
        )

    # 全年每日预测：年度活动锚定到其历史代表日期（rep_day），不再铺满全部工作日；
    # 一次性活动只进入下拉列表，不占用日历格子，避免视觉过载。
    days: list[dict] = []
    for m in range(1, 13):
        ndays = calendar.monthrange(year, m)[1]
        month_acts = activities.get(m, [])
        for day in range(1, ndays + 1):
            dt = date(year, m, day)
            wd = dt.weekday()
            cnt = 0.0
            srcs: list[str] = []
            cat_hits: list[str] = []
            day_acts: list[dict] = []
            for a in month_acts:
                # 仅年度活动进入日历，并锚定到其历史代表日期
                if not a["annual"] or a["rep_day"] is None:
                    continue
                if a["rep_day"] == day:
                    day_acts.append(a)
            for sid, r in by_source.items():
                mc = r["monthly"][m - 1]
                if mc <= 0:
                    continue
                bias = r["weekdayBias"]
                active_today = (
                    (bias == "weekend" and wd in (5, 6))
                    or (bias == "weekday" and wd <= 4)
                    or (bias == "mixed")
                )
                if not active_today:
                    continue
                divisor = 2 if bias == "weekend" else (5 if bias == "weekday" else 7)
                cnt += mc / divisor
                srcs.append(sid)
                if r["topCategories"]:
                    cat_hits.append(r["topCategories"][0])
            cat_counter: dict[str, int] = defaultdict(int)
            for c in cat_hits:
                if c and c != "待分类":
                    cat_counter[c] += 1
            top_cat = max(cat_counter.items(), key=lambda x: x[1])[0] if cat_counter else ""
            # 去掉重复活动（同主题在一天只留一条），限制每天最多 4 条避免拥挤
            seen: set[str] = set()
            dedup_acts = []
            for a in day_acts:
                if a["name"] in seen:
                    continue
                seen.add(a["name"])
                dedup_acts.append(a)
                if len(dedup_acts) >= 4:
                    break
            days.append(
                {
                    "date": dt.isoformat(),
                    "month": m,
                    "weekday": wd,
                    "count": round(cnt, 1),
                    "sources": srcs,
                    "topCategory": top_cat,
                    "activities": dedup_acts,
                }
            )

    # 年视图汇总：全年活动清单（供年视图列出每年必有的活动）
    all_activities: list[dict] = []
    for m in range(1, 13):
        all_activities.extend(activities.get(m, []))
    all_activities.sort(key=lambda x: (0 if x["annual"] else 1, x["month"], -x["count"]))

    return {
        "year": year,
        "bySource": by_source,
        "scopes": dict(scopes),
        "monthly": monthly_summary,
        "days": days,
        "activities": all_activities,
        # 逐月活动（含三年内示例链接），供年视图 / 月视图下拉列表使用
        "activitiesByMonth": {m: activities[m] for m in range(1, 13)},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "skipped_no_date": skipped,
        "source_count": len(by_source),
    }
