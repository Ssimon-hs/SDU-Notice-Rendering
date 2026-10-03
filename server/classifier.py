"""结构化抽取与分类。

设计原则（对应需求 10-14）：
- 分类必须结合标题与正文，不能只看关键词；
- 通知 / 新闻 / 公示 / 结果 四类相互区分，无法判断时进入「待分类」；
- 适用对象支持多个，无法确定时标记 audience_confirmed=False；
- 时间必须区分 8 类节点，禁止把发布时间误认为截止时间；
- 材料、步骤、地点只在正文中抽取，抽取不到就留空，绝不编造。
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

# ---------------------------------------------------------------- 分类体系

CATEGORY_RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    # (分类名, 标题强特征, 正文辅助特征)
    (
        "竞赛通知",
        ("竞赛", "大赛", "挑战赛", "创新创业", "创青春", "互联网+", "数学建模", "辩论赛"),
        ("参赛", "赛区", "初赛", "复赛", "决赛", "获奖等级", "组队"),
    ),
    (
        "讲座／论坛",
        ("讲座", "讲坛", "论坛", "报告会", "学术沙龙", "云端讲堂"),
        ("主讲人", "报告人", "主持人", "讲座时间", "讲座地点", "主讲"),
    ),
    (
        "奖学金／评奖评优",
        (
            "奖学金",
            "评奖",
            "评优",
            "三好学生",
            "优秀学生",
            "助学金",
            "荣誉称号",
            "评选",
            "资助",
            "励志",
        ),
        ("评定", "名额分配", "综合测评", "申请条件", "获奖比例"),
    ),
    (
        "考试／选课／教学安排",
        ("选课", "考试", "四六级", "补考", "重修", "课表", "教学质量", "答辩", "成绩"),
        ("选课时间", "考试科目", "考场", "学分", "培养方案"),
    ),
    (
        "实习／招聘／就业",
        ("招聘", "就业", "实习", "宣讲会", "双选会", "春招", "秋招", "岗位", "校招"),
        ("简历", "投递", "岗位要求", "薪资待遇", "用人单位", "三方协议"),
    ),
    (
        "志愿服务／社会实践",
        ("志愿者", "志愿服务", "社会实践", "支教", "招募志愿者", "西部计划"),
        ("志愿时长", "服务时长", "实践团队", "服务对象"),
    ),
    (
        "公示／名单／结果",
        ("公示", "名单", "结果公布", "拟录取", "获奖名单", "入选", "通报表扬"),
        ("公示期", "异议", "公示时间", "反映问题"),
    ),
    (
        "放假／校历／行政安排",
        (
            "放假",
            "寒假",
            "暑假",
            "校历",
            "开学",
            "调休",
            "班车",
            "作息时间",
            "节假日",
            "元旦",
            "国庆",
            "清明",
            "五一",
            "中秋",
            "报到注册",
        ),
        ("假期安排", "返校", "报到注册", "值班"),
    ),
    (
        "后勤／宿舍／校园卡／网络服务",
        (
            "宿舍",
            "校园卡",
            "一卡通",
            "后勤",
            "食堂",
            "网络",
            "水电",
            "维修",
            "门禁",
            "公寓",
            "停水",
            "停电",
            "浴室",
        ),
        ("充值", "报修", "停水", "停电", "网费", "住宿"),
    ),
    (
        "招生／保研／考研",
        ("招生", "保研", "推免", "考研", "研究生考试", "夏令营", "复试", "调剂", "自招"),
        ("推免生", "复试线", "招生计划", "初试", "报考"),
    ),
    (
        "国际交流／交换项目",
        ("国际交流", "交换生", "出国", "访学", "联合培养", "海外", "留学", "公派"),
        ("对方院校", "语言成绩", "签证", "派出"),
    ),
    (
        "科研项目／论文征集",
        ("科研项目", "课题", "基金", "论文征集", "征文", "科研成果", "立项", "申报指南"),
        ("结项", "中期检查", "经费", "申请书", "摘要"),
    ),
    (
        "活动通知",
        ("活动", "晚会", "运动会", "开幕", "典礼", "文化节", "征集作品", "打卡"),
        ("活动时间", "活动地点", "参与方式", "报名方式"),
    ),
    (
        "紧急通知",
        ("紧急", "重要提醒", "台风", "停课", "预警", "突发", "延期举行"),
        ("立即", "暂停", "临时调整"),
    ),
    (
        "宣传报道",
        ("我校", "喜报", "热烈祝贺", "走访", "调研", "荣获", "夺冠", "获评", "上榜"),
        ("报道", "人物", "专访", "事迹"),
    ),
    (
        "普通新闻",
        ("新闻", "快讯", "简讯", "要闻", "动态", "回顾", "落幕", "闭幕"),
        ("近日", "日前", "昨日", "召开", "举行"),
    ),
]

# 正文中的强判断信号（用于：通知 vs 新闻）
NOTICE_SIGNALS = (
    "报名",
    "申报",
    "提交",
    "截止时间",
    "请于",
    "逾期",
    "材料",
    "申请表",
    "参加",
    "办理",
    "登录系统",
    "填写",
    "发送至",
    "邮箱",
    "二维码",
)

NEWS_SIGNALS = (
    "近日",
    "日前",
    "于昨日",
    "圆满结束",
    "成功举办",
    "顺利召开",
    "荣获",
    "获得一等奖",
    "我校师生",
    "报道",
    "回顾",
    "圆满落幕",
    "热烈祝贺",
    "在比赛中",
)

PUBLICITY_SIGNALS = ("公示", "名单", "拟录取", "拟获奖", "结果公布", "评审结果")

# ---------------------------------------------------------------- 适用对象

AUDIENCE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("全体师生", ("全体师生", "全校师生", "全体教职工和学生")),
    ("全体学生", ("全体学生", "全校学生", "所有学生", "在校学生")),
    ("本科生", ("本科生", "本科学生", "本科在读")),
    ("研究生", ("研究生", "硕士生", "硕士研究")),
    ("博士生", ("博士生", "博士研究")),
    ("教职工", ("教职工", "教师", "职工", "辅导员", "专任教师")),
    ("新生", ("新生", "2026级新", "入学新生")),
    ("毕业生", ("毕业生", "应届毕业生", "毕业班")),
    ("党员", ("党员", "党支部", "党课")),
    ("团员", ("团员", "团支部", "团组织")),
    ("家庭经济困难学生", ("家庭经济困难", "贫困生", "助学金")),
    ("留学生", ("留学生", "国际学生")),
]

GRADE_PATTERN = re.compile(r"(20\d{2})级")
# 只匹配「前面没有其它汉字」的单位名，避免把句子片段当成学院
COLLEGE_PATTERN = re.compile(
    r"(?<![一-龥])([一-龥]{2,4}(?:学院|研究院|书院|学部))"
)
MAJOR_PATTERN = re.compile(r"(?<![一-龥])([一-龥]{2,6}专业)")
# 这些词出现在候选里说明抓到的是句子片段，不是单位名
COLLEGE_STOPWORDS = (
    "党委",
    "理论",
    "学习",
    "推动",
    "召开",
    "工作",
    "全体",
    "相关",
    "本次",
    "会议",
    "活动",
    "管理",
    "服务",
    "教育",
    "培训",
    "研究",
)

CAMPUSES = {
    "中心校区": ("中心校区", "洪家楼", "趵突泉"),
    "洪家楼校区": ("洪家楼",),
    "趵突泉校区": ("趵突泉",),
    "千佛山校区": ("千佛山",),
    "兴隆山校区": ("兴隆山",),
    "软件园校区": ("软件园",),
    "青岛校区": ("青岛", "蓝谷"),
    "威海校区": ("威海",),
}

# ---------------------------------------------------------------- 时间识别

TIME_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("signup_start", ("报名开始", "开始报名", "报名时间：", "报名自", "开放报名")),
    ("signup_end", ("报名截止", "截止报名", "报名结束", "截止时间", "截止日期", "报名至")),
    ("submit_end", ("材料提交截止", "提交截止", "报送截止", "材料报送", "提交时间", "报送时间")),
    ("review_at", ("审核时间", "评审时间", "初审时间", "资格审查")),
    ("event_start", ("活动开始", "开幕时间", "会议时间", "讲座时间", "开始时间", "举行时间")),
    ("event_end", ("活动结束", "结束时间", "闭幕")),
    ("result_at", ("结果公布", "公布时间", "公示时间", "成绩公布", "公布结果")),
    ("exam_at", ("考试时间", "面试时间", "笔试时间", "复试时间", "答辩时间")),
]

TIME_KEYS = [key for key, _ in TIME_RULES]

FULL_DATE = re.compile(r"(?P<year>20\d{2})\s*[-/.年]\s*(?P<month>\d{1,2})\s*[-/.月]\s*(?P<day>\d{1,2})")
SHORT_DATE = re.compile(r"(?P<month>\d{1,2})\s*[月./-]\s*(?P<day>\d{1,2})\s*日?")
TIME_OF_DAY = re.compile(r"(?P<hour>\d{1,2})\s*[:：]\s*(?P<minute>\d{2})")

# ---------------------------------------------------------------- 材料

# 材料名必须由「提交 / 报送 / 下载」这类动作词直接引出，避免把句子片段当材料
MATERIAL_PATTERNS = (
    re.compile(
        r"(?:提交|报送|上报|上传|递交|填写|准备|提供|下载|打印|盖章|提交一份)"
        r"[\u4e00-\u9fa5A-Za-z0-9]{0,4}?"
        r"([\u4e00-\u9fa5A-Za-z0-9]{2,14}"
        r"(?:表|证明|复印件|扫描件|简历|成绩单|作品|方案|报告|总结|照片|证书"
        r"|承诺书|申请书|名单|汇总表|汇总|说明|材料))"
    ),
    re.compile(
        r"(?:附件|材料|材料包括|需提供)\s*[：:，、]?\s*"
        r"([\u4e00-\u9fa5A-Za-z0-9]{2,14}"
        r"(?:表|证明|复印件|扫描件|简历|成绩单|作品|方案|报告|总结|照片|证书"
        r"|承诺书|申请书|名单|汇总表|汇总|说明|材料))"
    ),
    # 列举里的后续项：「…申请表、成绩单复印件和个人简历」
    re.compile(
        r"[、，和与及]\s*"
        r"([\u4e00-\u9fa5A-Za-z0-9]{2,14}"
        r"(?:表|证明|复印件|扫描件|简历|成绩单|作品|方案|报告|总结|照片|证书"
        r"|承诺书|申请书|名单|汇总表|汇总|说明|材料))"
    ),
)
FORMAT_WORDS = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".jpg",
    ".png",
)

# 出现在候选材料名里说明抓到的是句子片段，不是真实材料
MATERIAL_STOPWORDS = (
    "并作",
    "并进",
    "作了",
    "进行",
    "开展",
    "本次",
    "会议",
    "活动",
    "要求",
    "希望",
    "强调",
    "指出",
    "认为",
    "表示",
    "通过",
    "结合",
    "围绕",
    "落实",
    "深化",
    "加强",
    # 动作词本身出现在候选里，说明抓到的是整句话
    "提交",
    "报送",
    "上传",
    "下载",
    "包含",
    "提供",
    "准备",
    "无需",
    "需要",
    "代表",
    "按照",
    "以下",
    "以上",
    "发表",
    "研究员",
    "珍贵",
    "大量",
)

# 泛指性后缀（材料 / 方案 / 报告）只允许出现在这些限定词后面
MATERIAL_PREFIX_RULES = {
    "材料": (
        "申报", "申请", "推荐", "报名", "相关", "有关", "证明", "成果",
        "支撑", "辅助", "纸质", "电子", "其它", "其他", "书面", "补充", "以上",
    ),
    "方案": ("工作", "实施", "申报", "答辩", "培养", "活动", "评选"),
    "报告": ("书面", "总结", "中期", "开题", "结题", "实验", "调研", "专题"),
}


def _is_plausible_material(name: str) -> bool:
    for suffix, allowed in MATERIAL_PREFIX_RULES.items():
        if name.endswith(suffix):
            prefix = name[: -len(suffix)]
            return bool(prefix) and prefix in allowed
    return True

# 单位名 / 材料名以这些字开头，基本可以判定是句子片段
LEAD_CHARS = set("要紧本该各全我校党政团师作做进开组召主总并的则以将把被对向从含")

# 材料只会在这些语境里出现，其它句子一律不扫
MATERIAL_CONTEXT = (
    "提交",
    "报送",
    "材料",
    "附件",
    "申请表",
    "准备",
    "提供",
    "上传",
    "下载",
    "填写",
    "发送至",
    "发送至邮箱",
    "递交",
    "打印",
    "盖章",
)

STEP_MARKERS = ("第一步", "第二步", "第三步", "^\\d+\\s*[.、]", "首先", "然后", "最后")

ATTACHMENT_EXT = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
)


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _make_date(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_date_in(text: str, fallback_year: int) -> str | None:
    """从一段文字里解析出日期，优先完整日期。"""
    match = FULL_DATE.search(text)
    if match:
        parsed = _make_date(
            int(match.group("year")), int(match.group("month")), int(match.group("day"))
        )
        if parsed:
            return parsed
    match = SHORT_DATE.search(text)
    if match:
        parsed = _make_date(fallback_year, int(match.group("month")), int(match.group("day")))
        if parsed:
            return parsed
    return None


def parse_time_of_day(text: str) -> str | None:
    match = TIME_OF_DAY.search(text)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


BEFORE_MARKER = re.compile(
    r"(20\d{2}\s*[-/.年]\s*\d{1,2}\s*[-/.月]\s*\d{1,2}\s*日?|\d{1,2}\s*[月./-]\s*\d{1,2}\s*日?)"
    r"\s*(?:[（(]?[^，。；]{0,6}[）)]?\s*)?(?:之?前|截止|截至|以前)"
)


def extract_times(text: str, fallback_year: int) -> dict[str, str | None]:
    """识别 8 类时间节点。只在明确的关键词附近取日期，避免误判。"""
    cleaned = _clean(text)
    result: dict[str, str | None] = {key: None for key in TIME_KEYS}
    for key, markers in TIME_RULES:
        for marker in markers:
            index = cleaned.find(marker)
            if index < 0:
                continue
            window = cleaned[index : index + 60]
            parsed = parse_date_in(window, fallback_year)
            if parsed:
                result[key] = parsed
                break

    # 兜底：「请于 2026年10月20日 前提交」「截至 10月20日」这类写法
    if not result["submit_end"] and not result["signup_end"]:
        match = BEFORE_MARKER.search(cleaned)
        if match:
            parsed = parse_date_in(match.group(0), fallback_year)
            if parsed:
                if "报名" in cleaned[max(0, match.start() - 12) : match.end() + 12]:
                    result["signup_end"] = parsed
                else:
                    result["submit_end"] = parsed
    return result


def extract_materials(text: str) -> list[dict[str, Any]]:
    cleaned = _clean(text)
    if not cleaned:
        return []
    # 正文中完全没有材料语境时，不要硬凑材料清单
    if not any(word in cleaned for word in MATERIAL_CONTEXT):
        return []
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in MATERIAL_PATTERNS:
        for match in pattern.finditer(cleaned):
            name = match.group(1).strip(" ，,。;；:：")
            if len(name) < 3 or len(name) > 18 or name in seen:
                continue
            if any(word in name for word in MATERIAL_STOPWORDS):
                continue
            if name[0] in LEAD_CHARS:
                continue
            if not _is_plausible_material(name):
                continue
            seen.add(name)
            tail = cleaned[match.end() : match.end() + 24]
            fmt = ""
            for word in FORMAT_WORDS:
                if word in tail:
                    fmt = word.lstrip(".")
                    break
            found.append({"name": name, "format": fmt, "required": True, "done": False})
            if len(found) >= 8:
                return found
    return found


def extract_steps(text: str) -> list[str]:
    cleaned = _clean(text)
    if not cleaned:
        return []
    sentences = re.split(r"[。；;\n]", cleaned)
    steps: list[str] = []
    for sentence in sentences:
        candidate = sentence.strip()
        if not (6 <= len(candidate) <= 60):
            continue
        if any(
            re.search(marker, candidate) for marker in ("第一步", "第二步", "第三步")
        ) or re.match(r"^\d+\s*[.、]", candidate):
            steps.append(candidate)
        elif any(candidate.startswith(word) for word in ("首先", "然后", "其次", "最后")):
            steps.append(candidate)
        if len(steps) >= 6:
            break
    return steps


def detect_campus(text: str) -> str | None:
    cleaned = _clean(text)
    for campus, keywords in CAMPUSES.items():
        if any(keyword in cleaned for keyword in keywords):
            return campus
    return None


def detect_online(text: str) -> bool | None:
    cleaned = _clean(text)
    if not cleaned:
        return None
    online_words = ("线上", "腾讯会议", "线上举行", "网络直播", "钉钉", "Zoom", "线上提交")
    offline_words = ("线下", "现场", "教室", "报告厅", "会议室", "图书馆")
    has_online = any(word in cleaned for word in online_words)
    has_offline = any(word in cleaned for word in offline_words)
    if has_online and not has_offline:
        return True
    if has_offline and not has_online:
        return False
    if has_online and has_offline:
        return None
    return None


def detect_audience(text: str) -> list[str]:
    cleaned = _clean(text)
    audience: list[str] = []
    for label, keywords in AUDIENCE_RULES:
        if any(keyword in cleaned for keyword in keywords):
            audience.append(label)
    for match in GRADE_PATTERN.finditer(cleaned):
        audience.append(f"{match.group(1)}级")
    for match in COLLEGE_PATTERN.finditer(cleaned):
        value = match.group(1)
        if len(value) >= 3 and not any(word in value for word in COLLEGE_STOPWORDS):
            if value[0] not in LEAD_CHARS:
                audience.append(value)
    for match in MAJOR_PATTERN.finditer(cleaned):
        value = match.group(1)
        if not any(word in value for word in COLLEGE_STOPWORDS) and value[0] not in LEAD_CHARS:
            audience.append(value)
    return _dedupe([item for item in audience if len(item) <= 12])[:8]


def classify(title: str, body: str = "") -> dict[str, Any]:
    """返回分类、类型、适用对象、时间、材料等结构化字段。"""
    cleaned_title = _clean(title)
    cleaned_body = _clean(body)
    haystack = f"{cleaned_title}\n{cleaned_body}"
    year_match = re.search(r"(20\d{2})", cleaned_title) or re.search(r"(20\d{2})", cleaned_body)
    fallback_year = int(year_match.group(1)) if year_match else date.today().year

    # --- 多标签分类：标题命中直接算；正文命中需要 2 个以上辅助词 ---
    categories: list[str] = []
    for category, title_words, body_words in CATEGORY_RULES:
        if any(word in cleaned_title for word in title_words):
            categories.append(category)
            continue
        hits = sum(1 for word in body_words if word in cleaned_body)
        if hits >= 2 and cleaned_body:
            categories.append(category)
    if "紧急通知" in categories:
        categories.remove("紧急通知")
        categories.insert(0, "紧急通知")
    # --- 通知 / 新闻 / 公示 / 结果 ---
    notice_hits = sum(1 for word in NOTICE_SIGNALS if word in haystack)
    news_hits = sum(1 for word in NEWS_SIGNALS if word in haystack)
    publicity_hits = sum(1 for word in PUBLICITY_SIGNALS if word in haystack)
    if publicity_hits >= 1 and any(word in cleaned_title for word in PUBLICITY_SIGNALS):
        kind = "公示／结果"
    elif news_hits > notice_hits and news_hits >= 2:
        kind = "新闻"
    elif notice_hits >= 1:
        kind = "通知"
    elif news_hits >= 1:
        kind = "新闻"
    else:
        kind = "待分类"

    if not categories:
        # 没有正文时只能依据标题与性质给出最保守的归类
        if kind == "新闻":
            categories.append("普通新闻")
        elif kind == "公示／结果":
            categories.append("公示／名单／结果")
        else:
            categories.append("待分类")

    # --- 时间 ---
    times = extract_times(haystack, fallback_year)
    deadline = (
        times["signup_end"]
        or times["submit_end"]
        or times["event_start"]
        or times["exam_at"]
    )

    # --- 材料与步骤：只从正文中抽取，绝不从摘要或标题里猜 ---
    materials = extract_materials(cleaned_body) if cleaned_body else []
    steps = extract_steps(cleaned_body) if cleaned_body else []

    needs_signup = any(
        word in haystack for word in ("报名", "申报", "申请", "注册", "填报")
    )
    needs_material = bool(materials) or any(
        word in cleaned_body for word in ("材料", "附件", "申请表", "证明")
    )
    online = detect_online(haystack)
    campus = detect_campus(haystack)
    audience = detect_audience(haystack)

    prep_minutes = 10
    if needs_material:
        prep_minutes += 30 + 15 * len(materials)
    if needs_signup:
        prep_minutes += 15
    if steps:
        prep_minutes += 10 * len(steps)
    prep_minutes = min(prep_minutes, 600)

    return {
        "categories": categories,
        "kind": kind,
        "audience": audience,
        "audience_confirmed": bool(audience),
        "times": times,
        "deadline": deadline,
        "materials": materials,
        "steps": steps,
        "needs_signup": needs_signup,
        "needs_material": needs_material,
        "online": online,
        "campus": campus,
        "prep_minutes": prep_minutes,
    }


def group_key(title: str) -> str:
    """用于把同一活动的通知 / 新闻 / 公示 / 结果关联起来。"""
    cleaned = _clean(title)
    cleaned = re.sub(r"(20\d{2})年?", "", cleaned)
    cleaned = re.sub(
        r"(关于|的通知|公告|公示|通知|结果|名单|获奖|举办|开展|召开|第[一二三四五六七八九十\d]+[届期])",
        "",
        cleaned,
    )
    cleaned = re.sub(r"[\s，,。、：:；;（）()【】\[\]“”\"'’‘—\-]+", "", cleaned)
    return cleaned[:24]


def summarize(title: str, body: str, limit: int = 120) -> str:
    """一句话摘要：优先取正文首句，其次回落到标题本身，绝不拼接日期。"""
    cleaned = _clean(body)
    if cleaned:
        first = re.split(r"[。！？\n]", cleaned)[0].strip()
        if len(first) >= 12:
            return first[:limit] + ("…" if len(first) > limit else "")
        return cleaned[:limit] + ("…" if len(cleaned) > limit else "")
    return _clean(title)[:limit]


# ---------------------------------------------------------------- 标题提炼与日期兜底

CN_DATE = re.compile(
    r"\d{4}[./-]\d{1,2}[./-]\d{1,2}|"           # 2026.09.28 / 2026-09-28
    r"\d{4}年\d{1,2}月\d{1,2}[日号]?|"           # 2026年9月18日
    r"\d{4}年\d{1,2}月|"                          # 2026年9月
    r"(?<![\d.])\d{1,2}月\d{1,2}[日号]?|"         # 9月29日 (无年份)
    r"(?<![\d.])\d{1,2}月"                         # 9月 (无年份)
)

# 列表页常在标题前拼接的日期 / 栏目噪声（如「21 2026.09 海洋学院…」「2026 06-23 山东…」）
_LEADING_NOISE = (
    re.compile(r"^\d{1,2}\s+20\d{2}\s*[./-]\s*\d{1,2}\s*[./-]?\s*\d{0,2}\s+"),
    re.compile(r"^20\d{2}\s+\d{1,2}\s*[-./]\s*\d{1,2}\s+"),
    re.compile(r"^\d{1,2}\s*[-./]\s*\d{1,2}\s+20\d{2}\s+"),
    re.compile(r"^20\d{2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2}\s*日?\s+"),
    re.compile(r"^20\d{2}年\d{1,2}月\d{1,2}日\s+"),
    re.compile(r"^20\d{2}年\d{1,2}月\s+"),
    re.compile(r"^\d{1,2}\s*[-./]\s*\d{1,2}\s+"),
    re.compile(r"^(?:通知公告|通知预告|学院通知|学院新闻|校区要闻|学校头条|校园生活|学术预告)\s+"),
    re.compile(r"^\[[^\]]{1,10}\]\s*"),
)

# 元数据块起点：出现即说明标题在此结束、其后进入正文 / 表格 / 日程
_META_MARKERS = (
    "报告人", "报告摘要", "主讲人", "主持人", "邀请人", "报告时间", "报告地点",
    "讲座时间", "讲座地点", "会议时间", "会议地点", "活动时间", "活动地点",
    "会议主题", "活动主题", "讲座题目", "报告题目", "出访团组", "团组人员",
    "时间：", "时间:", "地点：", "地点:", "主题：", "主题:", "题目：", "题目:",
    "摘要：", "摘要:", "腾讯会议", "姓名", "学号", "单位名称", "职称", "职务",
    "基本信息", "人员名单", "参会人员", "与会人员", "参加人员", "详细日程",
    "日程安排", "活动安排", "报名方式", "报名条件", "申请条件", "参与方式",
    "联系方式", "联系人", "主办单位", "承办单位", "协办单位", "指导单位",
    "内容简介", "（按日填写）", "(按日填写)", "一、", "二、", "三、", "（一）", "(一)",
)
_STRONG_MARKERS = [
    "报告人：", "报告人:", "报告摘要：", "报告摘要:", "摘要：", "摘要:",
    "邀请人：", "邀请人:", "报告地点：", "报告地点:", "报告时间：", "报告时间:",
    "讲座时间：", "讲座时间:", "讲座地点：", "讲座地点:", "主讲人：", "主讲人:",
    "腾讯会议：", "腾讯会议:", "会议时间：", "会议时间:", "会议地点：", "会议地点:",
    "地点：", "地点:", "时间：", "时间:",
]
_BODY_STARTERS = (
    "近日", "据悉", "本网", "记者", "我院", "我校", "本网讯", "记者从", "据介绍",
    "据了解", "该学院", "该团队", "该同志", "该活动", "本次", "为了", "为倾听",
    "为深入", "为进一步", "为贯彻", "为落实", "为加强", "为推进", "为促进", "为庆祝",
    "为做好", "为切实", "为认真", "为更好", "为丰富", "为响应", "为提高", "为提升",
    "为营造", "为弘扬", "为统一", "为扎", "为深", "旨在", "围绕", "中秋佳节",
)
# 真实标题通常以这些词收尾；若其后仍有大段内容，则说明是正文残留
_TITLE_SUFFIXES = (
    "通知", "公告", "公示", "启事", "方案", "办法", "意见", "决定", "名单", "结果",
    "安排", "计划", "说明", "报告", "细则", "规定", "须知", "指南", "纪要", "邀请函",
    "招募", "遴选", "评选", "实施办法", "工作要点", "总结", "通告", "决议", "批复",
)


def _looks_like_body_start(text: str) -> bool:
    """判断一段文本是否更像正文 / 元数据，而非标题的一部分。"""
    if not text:
        return False
    if CN_DATE.match(text):
        return True
    if any(text.startswith(word) for word in _BODY_STARTERS):
        return True
    # 很长且很早就出现句读，基本是正文
    if len(text) > 30 and re.match(r"^[^，。；]{0,10}[，。；]", text):
        return True
    return False


def _space_boundary(t: str) -> int | None:
    """标题 + 空格 + 正文：找到正文起点在字符串中的下标。"""
    parts = t.split(" ")
    if len(parts) < 2:
        return None
    for i in range(1, len(parts)):
        prefix = " ".join(parts[:i])
        rest = " ".join(parts[i:]).strip()
        if len(prefix) >= 6 and _looks_like_body_start(rest):
            return len(prefix)
    return None


def _marker_boundary(t: str) -> int | None:
    """找到最早的元数据 / 日期信号起点，作为标题结束位置。"""
    best: int | None = None
    for marker in _META_MARKERS + tuple(_STRONG_MARKERS):
        idx = t.find(marker)
        if idx >= 6 and (best is None or idx < best):
            best = idx
    match = CN_DATE.search(t)
    if match and match.start() >= 6:
        after = t[match.end():].strip()
        if after and (
            after[0] in "，。；、,.;"
            or after.startswith(_BODY_STARTERS)
            or len(after) > 15
        ):
            if best is None or match.start() < best:
                best = match.start()
    return best


def _trim_after_last_suffix(cand: str) -> str:
    """若标题后缀词之后仍残留正文片段，则截断到后缀词结束处。"""
    if len(cand) <= 24:
        return cand
    best_end = -1
    for suffix in _TITLE_SUFFIXES:
        start = 0
        while True:
            hit = cand.find(suffix, start)
            if hit < 0:
                break
            end = hit + len(suffix)
            if end > best_end:
                best_end = end
            start = hit + 1
    if 6 <= best_end < len(cand) and cand[best_end:].strip():
        return cand[:best_end].strip()
    return cand


def _hard_trim(cand: str, limit: int = 56) -> str:
    window = cand[:limit]
    for sep in ("。", "；", ";", "，", ",", "、", " "):
        pos = window.rfind(sep)
        if pos >= 18:
            return cand[:pos] + "…"
    return window.rstrip() + "…"


def refine_title(title: str, threshold: int = 30) -> str:
    """把「标题 + 日期 + 正文开头 / 元数据表格」拼接的超长标题还原为真实标题。

    四步：剥离开头日期噪声 → 用「空格+正文」「元数据标记」「日期信号」定位标题终点
    → 截断后缀词之后的正文残留 → 极端情况才硬截断。
    """
    if not title:
        return title
    t = _clean(title)
    for pattern in _LEADING_NOISE:
        stripped = pattern.sub("", t).strip()
        if stripped and stripped != t:
            t = stripped
    if len(t) <= threshold:
        return t
    candidates = [b for b in (_space_boundary(t), _marker_boundary(t)) if b is not None]
    boundary = min(candidates) if candidates else None
    cand = t[:boundary].strip() if boundary else t
    cand = _trim_after_last_suffix(cand)
    if len(cand) > 60:
        cand = _hard_trim(cand)
    return cand.strip()


def infer_date_from_text(*texts) -> str | None:
    """从标题 / 摘要 / 正文中提取第一个合理日期，用于发布时间缺失时的兜底。"""
    for text in texts:
        if not text:
            continue
        for m in CN_DATE.finditer(text):
            seg = text[max(0, m.start() - 6): m.end() + 1]
            if re.search(r"\d{4}-\d{4}", seg):  # 过滤「2026-2027 学年」之类
                continue
            return m.group(0)
    return None


def next_action_date(times: dict[str, str | None], today: str | None = None) -> str | None:
    """卡片优先显示「最近需要行动」的时间。"""
    today_value = today or date.today().isoformat()
    candidates = [
        value
        for key, value in times.items()
        if value and value >= today_value and key != "event_end"
    ]
    if not candidates:
        return None
    return min(candidates)


def days_until(value: str | None, today: str | None = None) -> int | None:
    if not value:
        return None
    try:
        target = date.fromisoformat(value)
    except ValueError:
        return None
    base = date.fromisoformat(today) if today else date.today()
    return (target - base).days


def is_expired(deadline: str | None, today: str | None = None) -> bool:
    if not deadline:
        return False
    remaining = days_until(deadline, today)
    return remaining is not None and remaining < 0


def sanitize_published(value: str | None, today: str | None = None) -> str | None:
    """发布时间不允许晚于今天（抓取误判时回落到 None）。"""
    if not value:
        return None
    today_value = today or date.today().isoformat()
    if value > today_value:
        return None
    return value


def within_years(value: str | None, years: int = 3, today: str | None = None) -> bool:
    """默认只保留近三年内容。"""
    if not value:
        return False
    today_value = date.fromisoformat(today) if today else date.today()
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return parsed >= today_value - timedelta(days=365 * years)


def attachment_kind(url: str) -> str:
    lowered = (url or "").lower()
    for ext in ATTACHMENT_EXT:
        if ext in lowered:
            return ext.lstrip(".")
    return "link"
