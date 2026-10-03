"""官方站点抓取器。

对应需求 9 与 J：
- 不能只扫首页，要自动发现栏目、翻页、读取正文和附件；
- 每个来源独立报告：成功 / 失败、抓取数量、最后更新时间、失败原因；
- 默认只保留近三年内容，重复链接自动去重。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from server.classifier import (
    classify,
    group_key,
    is_expired,
    sanitize_published,
    summarize,
    refine_title,
    infer_date_from_text,
    within_years,
)
from server.sources.common import (
    ScanReport,
    _clean,
    _error_reason,
    _extract_detail,
    http_get as _get,
)
from server.sources.sdu_main import _infer_category

__all__ = [
    "SOURCES",
    "ScanReport",
    "SourceConfig",
    "scan_source",
    "discover_columns",
]

ISO_DATE = re.compile(r"(?P<year>20\d{2})[-/.年](?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})日?")
MDY_DATE = re.compile(r"(?P<month>\d{1,2})[.-](?P<day>\d{1,2})\s+(?P<year>20\d{2})")
CN_DATE = re.compile(r"(?:(?P<year>20\d{2})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})日")
ACTION_WORDS = (
    "通知",
    "公告",
    "报名",
    "申报",
    "选拔",
    "招募",
    "招聘",
    "竞赛",
    "大赛",
    "讲座",
    "讲坛",
    "论坛",
    "考试",
    "选课",
    "公示",
    "邀请函",
)

# 栏目关键词：用于在站点首页自动发现「通知公告」这类列表页
COLUMN_WORDS = (
    "通知",
    "公告",
    "公示",
    "新闻",
    "动态",
    "要闻",
    "快讯",
    "资讯",
    "招生",
    "就业",
    "学工",
    "教务",
    "研究生",
    "本科生",
)

PAGINATION_WORDS = ("下一页", "下页", "后一页", "next", "»", ">")


@dataclass(frozen=True)
class SourceConfig:
    id: str
    name: str
    scope: str
    list_urls: tuple[str, ...] = ()
    max_items: int = 24
    detail_budget: int = 12
    max_pages: int = 2
    auto_columns: bool = True
    campus: str = ""

    @property
    def list_url(self) -> str:
        return self.list_urls[0] if self.list_urls else ""


# ------------------------------------------------------------------ 来源清单

SOURCES: list[SourceConfig] = [
    SourceConfig(
        id="sdu-snea-wh",
        name='东北亚学院',
        scope='学院',
        list_urls=("https://snea.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-gsp",
        name='中加合作办学项目',
        scope='机关部处',
        list_urls=("https://www.gsp.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-mathfinance",
        name='中泰证券金融研究院',
        scope='研究院/中心',
        list_urls=("https://mathfinance.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-rsrc",
        name='人事部（人才工作办公室）',
        scope='机关部处',
        list_urls=("https://www.rsrc.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cfair",
        name='人工智能国际联合研究院',
        scope='研究院/中心',
        list_urls=("https://cfair.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ai",
        name='人工智能学院',
        scope='学院',
        list_urls=("https://www.ai.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-rsrczp",
        name='人才招聘',
        scope='机关部处',
        list_urls=("https://www.rsrczp.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-rwskjournals",
        name='人文社科期刊社',
        scope='机关部处',
        list_urls=("https://rwskjournals.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-rwsk",
        name='人文社科研究院（人文社科处）',
        scope='研究院/中心',
        list_urls=("https://www.rwsk.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-rwys-qd",
        name='人文艺术研究院',
        scope='研究院/中心',
        list_urls=("https://rwys.qd.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='青岛校区',
    ),
    SourceConfig(
        id="sdu-ie-wh",
        name='低空科学与工程学院',
        scope='学院',
        list_urls=("https://ie.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-tyb",
        name='体育学院',
        scope='学院',
        list_urls=("https://www.tyb.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-tyb-wh",
        name='体育教学部',
        scope='机关部处',
        list_urls=("https://tyb.wh.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-ise",
        name='信息科学与工程学院',
        scope='学院',
        list_urls=("https://www.ise.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-rxgdyjy",
        name='儒学高等研究院（文史哲研究院）',
        scope='研究院/中心',
        list_urls=("https://www.rxgdyjy.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-gac",
        name='党委保卫部（安全管理处）',
        scope='机关部处',
        list_urls=("https://www.gac.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-dbxb",
        name='党委办公室、校长办公室',
        scope='机关部处',
        list_urls=("https://www.dbxb.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-online",
        name='党委学生工作部、武装部',
        scope='学生组织/门户',
        list_urls=("https://www.online.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-xcb",
        name='党委宣传部',
        scope='机关部处',
        list_urls=("https://www.xcb.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-jgb",
        name='党委教师工作部',
        scope='机关部处',
        list_urls=("https://www.jgb.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-zzb",
        name='党委组织部',
        scope='机关部处',
        list_urls=("https://www.zzb.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sdtz",
        name='党委统战部',
        scope='机关部处',
        list_urls=("https://www.sdtz.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-dangxiao",
        name='党校',
        scope='机关部处',
        list_urls=("https://www.dangxiao.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sph",
        name='公共卫生学院',
        scope='学院',
        list_urls=("https://www.sph.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-xlsxq",
        name='兴隆山校区和软件园校区管理办公室',
        scope='机关部处',
        list_urls=("https://www.xlsxq.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-swpx",
        name='出国留学',
        scope='机关部处',
        list_urls=("https://www.swpx.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cbs",
        name='出版社',
        scope='直属单位',
        list_urls=("https://www.cbs.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-xlzx",
        name='创新实践中心',
        scope='机关部处',
        list_urls=("https://www.xlzx.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-frontier-qd",
        name='前沿交叉科学青岛研究院',
        scope='研究院/中心',
        list_urls=("https://frontier.qd.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='青岛校区',
    ),
    SourceConfig(
        id="sdu-chem",
        name='化学与化工学院',
        scope='学院',
        list_urls=("https://www.chem.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-medicine",
        name='医学融合与实践中心',
        scope='机关部处',
        list_urls=("https://www.medicine.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-museum",
        name='博物馆',
        scope='直属单位',
        list_urls=("https://museum.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-history",
        name='历史学院',
        scope='学院',
        list_urls=("https://www.history.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-dent",
        name='口腔医学院',
        scope='学院',
        list_urls=("https://www.dent.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sdkq",
        name='口腔医院',
        scope='直属单位',
        list_urls=("https://www.sdkq.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-hqc",
        name='后勤保障部',
        scope='机关部处',
        list_urls=("https://www.hqc.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sps",
        name='哲学与社会发展学院',
        scope='学院',
        list_urls=("https://www.sps.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-shxy-wh",
        name='商学院',
        scope='学院',
        list_urls=("https://shxy.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-gsee",
        name='国家卓越工程师学院',
        scope='学院',
        list_urls=("https://gsee.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sp",
        name='国家大学科技园管理办公室（山东工业技术研究院管理办公室）',
        scope='研究院/中心',
        list_urls=("https://www.sp.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-isie-qd",
        name='国际创新转化学院',
        scope='学院',
        list_urls=("https://isie.qd.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='青岛校区',
    ),
    SourceConfig(
        id="sdu-ipo",
        name='国际合作',
        scope='机关部处',
        list_urls=("https://www.ipo.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-istudy",
        name='国际教育',
        scope='机关部处',
        list_urls=("https://www.istudy.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cie",
        name='国际教育学院',
        scope='学院',
        list_urls=("https://www.cie.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-library",
        name='图书馆',
        scope='直属单位',
        list_urls=("https://library.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-tjsl",
        name='土建与水利学院',
        scope='学院',
        list_urls=("https://www.tjsl.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-jj",
        name='基建部',
        scope='机关部处',
        list_urls=("https://www.jj.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-bms",
        name='基础医学院',
        scope='学院',
        list_urls=("https://www.bms.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-flc",
        name='外国语学院',
        scope='学院',
        list_urls=("https://www.flc.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sden",
        name='外国语学院（大学外语教学部）',
        scope='研究院/中心',
        list_urls=("https://sden.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-women",
        name='妇委会',
        scope='机关部处',
        list_urls=("https://www.women.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-wh",
        name='威海校区',
        scope='机关部处',
        list_urls=("https://www.wh.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-ac",
        name='学术委员会办公室',
        scope='机关部处',
        list_urls=("https://www.ac.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-stu",
        name='学生公寓管理服务中心',
        scope='学生组织/门户',
        list_urls=("https://www.stu.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-online-2",
        name='学生在线',
        scope='学生组织/门户',
        list_urls=("https://online.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-job",
        name='学生就业',
        scope='学生组织/门户',
        list_urls=("https://www.job.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-job-2",
        name='学生就业创业指导中心',
        scope='学生组织/门户',
        list_urls=("https://job.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-fzgh",
        name='学科建设',
        scope='机关部处',
        list_urls=("https://www.fzgh.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-shj",
        name='审计处',
        scope='机关部处',
        list_urls=("https://www.shj.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cse",
        name='密码科学与工程学院',
        scope='学院',
        list_urls=("https://cse.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-jsc-wh",
        name='山东大学澳国立联合理学院',
        scope='学院',
        list_urls=("https://jsc.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-culture",
        name='山大文化',
        scope='机关部处',
        list_urls=("https://culture.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-view",
        name='山大新闻网',
        scope='机关部处',
        list_urls=("https://www.view.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sdrj",
        name='山大日记',
        scope='学生组织/门户',
        list_urls=("https://www.sdrj.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-dcxc",
        name='巡视工作领导小组办公室',
        scope='机关部处',
        list_urls=("https://www.dcxc.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-gonghui",
        name='工会',
        scope='机关部处',
        list_urls=("https://www.gonghui.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-mbtechinst-qd",
        name='微生物技术研究院',
        scope='研究院/中心',
        list_urls=("https://www.mbtechinst.qd.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='青岛校区',
    ),
    SourceConfig(
        id="sdu-xljk",
        name='心理健康',
        scope='学生组织/门户',
        list_urls=("https://www.xljk.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ttc",
        name='技术转移中心',
        scope='机关部处',
        list_urls=("https://www.ttc.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-nursing",
        name='护理与康复学院',
        scope='学院',
        list_urls=("https://www.nursing.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-control",
        name='控制科学与工程学院',
        scope='学院',
        list_urls=("https://control.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-pspa",
        name='政治学与公共管理学院',
        scope='学院',
        list_urls=("https://pspa.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cfd",
        name='教学促进与教师发展中心',
        scope='机关部处',
        list_urls=("https://cfd.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ste",
        name='教师教育学院',
        scope='学院',
        list_urls=("https://ste.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-jjh",
        name='教育基金会',
        scope='机关部处',
        list_urls=("https://www.jjh.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-iase",
        name='教育高等研究院',
        scope='研究院/中心',
        list_urls=("https://iase.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-mis",
        name='数学与交叉科学研究中心',
        scope='研究院/中心',
        list_urls=("https://www.mis.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-math-wh",
        name='数学与统计学院',
        scope='学院',
        list_urls=("https://math.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-math",
        name='数学学院',
        scope='学院',
        list_urls=("https://www.math.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-iais",
        name='数智化支撑研究院（信息化工作办公室）',
        scope='研究院/中心',
        list_urls=("https://iais.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-whcb-wh",
        name='文化传播学院',
        scope='学院',
        list_urls=("https://whcb.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-lit",
        name='文学院',
        scope='学院',
        list_urls=("https://www.lit.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-dpt",
        name='新一代半导体材料研究院',
        scope='研究院/中心',
        list_urls=("https://dpt.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-jc",
        name='新闻传播学院',
        scope='学院',
        list_urls=("https://www.jc.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-jty",
        name='晶体材料研究院',
        scope='研究院/中心',
        list_urls=("https://jty.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-aii",
        name='智能创新研究院',
        scope='研究院/中心',
        list_urls=("https://aii.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-iict",
        name='智能通信技术研究院',
        scope='研究院/中心',
        list_urls=("https://iict.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-dcd",
        name='服务山东',
        scope='机关部处',
        list_urls=("https://www.dcd.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sft",
        name='未来技术学院',
        scope='学院',
        list_urls=("https://sft.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-bkzs",
        name='本科生招生',
        scope='机关部处',
        list_urls=("https://www.bkzs.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-bkjx",
        name='本科生教育',
        scope='机关部处',
        list_urls=("https://www.bkjx.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-jgdw",
        name='机关党委',
        scope='机关部处',
        list_urls=("https://www.jgdw.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-mech",
        name='机械工程学院',
        scope='学院',
        list_urls=("https://www.mech.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cmse",
        name='材料科学与工程学院',
        scope='学院',
        list_urls=("https://www.cmse.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-xyy",
        name='校医院',
        scope='直属单位',
        list_urls=("https://www.xyy.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-card2",
        name='校园卡服务',
        scope='机关部处',
        list_urls=("https://card2.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-epe",
        name='核科学与能源动力学院',
        scope='学院',
        list_urls=("https://www.epe.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-archives",
        name='档案馆、校史办',
        scope='机关部处',
        list_urls=("https://www.archives.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-law",
        name='法学院',
        scope='学院',
        list_urls=("https://www.law.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-tsxt",
        name='泰山学堂',
        scope='机关部处',
        list_urls=("https://www.tsxt.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ori",
        name='海信光电研究院',
        scope='研究院/中心',
        list_urls=("https://ori.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-mc-wh",
        name='海洋学院',
        scope='学院',
        list_urls=("https://mc.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-imst",
        name='海洋研究院',
        scope='研究院/中心',
        list_urls=("https://www.imst.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-phy",
        name='物理学院',
        scope='学院',
        list_urls=("https://www.phy.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-hj",
        name='环境研究院',
        scope='研究院/中心',
        list_urls=("https://www.hj.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-huanke",
        name='环境科学与工程学院',
        scope='学院',
        list_urls=("https://www.huanke.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-lifesci",
        name='生命科学学院',
        scope='学院',
        list_urls=("https://lifesci.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ee",
        name='电气工程学院',
        scope='学院',
        list_urls=("https://www.ee.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ygb",
        name='研究生之家',
        scope='学生组织/门户',
        list_urls=("https://www.ygb.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-yz",
        name='研究生招生',
        scope='机关部处',
        list_urls=("https://www.yz.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-grad",
        name='研究生教育',
        scope='机关部处',
        list_urls=("https://www.grad.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ltxc",
        name='离退休工作处（离退休党委）',
        scope='机关部处',
        list_urls=("https://www.ltxc.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-rd",
        name='科学技术研究院',
        scope='研究院/中心',
        list_urls=("https://www.rd.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-jmrh",
        name='科技创新军民融合研究院',
        scope='研究院/中心',
        list_urls=("https://www.jmrh.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-njournal",
        name='科技期刊社',
        scope='机关部处',
        list_urls=("https://njournal.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-apd-wh",
        name='空间科学与技术学院',
        scope='学院',
        list_urls=("https://apd.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-glxy",
        name='管理学院',
        scope='学院',
        list_urls=("https://www.glxy.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-dis-wh",
        name='纪检监察学院',
        scope='学院',
        list_urls=("https://dis.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-jjjc",
        name='纪检监察机构',
        scope='机关部处',
        list_urls=("https://jjjc.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-econ",
        name='经济学院',
        scope='学院',
        list_urls=("https://www.econ.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cer",
        name='经济研究院',
        scope='研究院/中心',
        list_urls=("https://www.cer.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-wljy",
        name='继续教育',
        scope='机关部处',
        list_urls=("https://www.wljy.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-adult",
        name='继续教育学院',
        scope='学院',
        list_urls=("https://www.adult.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ce",
        name='继续教育管理办公室',
        scope='机关部处',
        list_urls=("https://ce.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cst-qd",
        name='网络空间安全学院',
        scope='学院',
        list_urls=("https://cst.qd.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='青岛校区',
    ),
    SourceConfig(
        id="sdu-art",
        name='美育山大',
        scope='学生组织/门户',
        list_urls=("https://www.art.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-fyxy-wh",
        name='翻译学院',
        scope='学院',
        list_urls=("https://fyxy.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-archaeology",
        name='考古学院',
        scope='学院',
        list_urls=("https://www.archaeology.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-art-wh",
        name='艺术学院',
        scope='学院',
        list_urls=("https://art.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-pharm",
        name='药学院',
        scope='学院',
        list_urls=("https://www.pharm.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cs",
        name='计算机科学与技术学院',
        scope='学院',
        list_urls=("https://www.cs.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cwc",
        name='财务部',
        scope='机关部处',
        list_urls=("https://www.cwc.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-zcb",
        name='资产与实验室管理部',
        scope='研究院/中心',
        list_urls=("https://www.zcb.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-cyc",
        name='资本运营公司',
        scope='机关部处',
        list_urls=("https://www.cyc.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-sc",
        name='软件学院',
        scope='学院',
        list_urls=("https://www.sc.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-ic",
        name='集成电路学院',
        scope='学院',
        list_urls=("https://ic.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-qdxq",
        name='青岛校区',
        scope='机关部处',
        list_urls=("https://www.qdxq.sdu.edu.cn/",),
        max_items=16,
        detail_budget=8,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-youth",
        name='青春山大',
        scope='学生组织/门户',
        list_urls=("https://www.youth.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-marx",
        name='马克思主义学院',
        scope='学院',
        list_urls=("https://marx.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-mlb-wh",
        name='马克思主义学院',
        scope='学院',
        list_urls=("https://mlb.wh.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='威海校区',
    ),
    SourceConfig(
        id="sdu-amri",
        name='高等医学研究院',
        scope='研究院/中心',
        list_urls=("https://www.amri.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-hhzlyjy",
        name='黄河国家战略研究院',
        scope='研究院/中心',
        list_urls=("https://www.hhzlyjy.sdu.edu.cn/",),
        max_items=22,
        detail_budget=11,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-qltrans",
        name='齐鲁交通学院',
        scope='学院',
        list_urls=("https://www.qltrans.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
    SourceConfig(
        id="sdu-qlyxb",
        name='齐鲁医学院',
        scope='学院',
        list_urls=("https://www.qlyxb.sdu.edu.cn/",),
        max_items=30,
        detail_budget=14,
        max_pages=2,
        auto_columns=True,
        campus='济南校区',
    ),
]

# 不在主站目录里的服务类站点（后勤、宿舍、校园卡等）
SERVICE_KEYWORDS = ("后勤", "公寓", "校园卡", "校医院", "财务", "人事", "科研", "研究生")


# ------------------------------------------------------------------ 抓取结果


# ------------------------------------------------------------------ 基础工具


def _parse_date(text: str) -> str | None:
    for pattern in (ISO_DATE, MDY_DATE):
        match = pattern.search(text)
        if match:
            try:
                return date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                ).isoformat()
            except ValueError:
                return None
    return None


def _extract_deadline(text: str, fallback_year: int) -> str | None:
    normalized = _clean(text)
    windows: list[str] = []
    for marker in ("截止", "报名时间", "申报时间", "提交时间", "报送时间"):
        index = normalized.find(marker)
        if index >= 0:
            windows.append(normalized[max(0, index - 36) : index + 70])
    for window in windows:
        matches = list(CN_DATE.finditer(window))
        if matches:
            match = matches[-1]
            year = int(match.group("year") or fallback_year)
            try:
                return date(
                    year, int(match.group("month")), int(match.group("day"))
                ).isoformat()
            except ValueError:
                continue
    return None


def _entry_id(source_id: str, url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"{source_id}-{digest}"


def _clean_title(value: str) -> str:
    """只保留官方原标题：去掉列表页拼接的日期、栏目名和摘要。"""
    value = _clean(value)
    # 顺序很重要：先去掉「月日 + 年份」，再去掉单独的「月日」
    value = re.sub(r"^\d{1,2}[.-]\d{1,2}\s+20\d{2}[-/.年]?\s*", "", value)
    value = re.sub(r"^\d{1,2}[./-]\d{1,2}\s+20\d{2}\s+", "", value)
    value = re.sub(r"^20\d{2}[-/年.]\d{1,2}[-/月.]\d{1,2}\s*", "", value)
    value = re.sub(r"^20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\s+", "", value)
    value = re.sub(r"^\d{1,2}[./-]\d{1,2}\s+", "", value)
    value = re.sub(
        r"\s+(?:校区要闻|学校头条|通知预告|校园生活|学院新闻|学院通知)\s+20\d{2}-\d{1,2}-\d{1,2}$",
        "",
        value,
    )
    value = re.sub(r"\s+20\d{2}-\d{1,2}-\d{1,2}$", "", value)
    value = re.sub(r"^\[[^\]]{1,8}\]\s*", "", value)
    return value.strip()


# ------------------------------------------------------------------ 栏目与翻页


def discover_columns(homepage: str, html: str, limit: int = 6) -> list[str]:
    """从站点首页自动发现通知 / 公告类栏目（需求 J）。"""
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        label = _clean(anchor.get_text(" ", strip=True))
        if not label or len(label) > 12:
            continue
        if not any(word in label for word in COLUMN_WORDS):
            continue
        href = anchor.get("href", "")
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            continue
        url = urljoin(homepage, href)
        parsed = urlparse(url)
        if not parsed.scheme.startswith("http"):
            continue
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        found.append(url)
        if len(found) >= limit:
            break
    return found


def _next_page(current: str, html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.select("a[href]"):
        label = _clean(anchor.get_text(" ", strip=True)).lower()
        if not label or len(label) > 8:
            continue
        if not any(word.lower() in label for word in PAGINATION_WORDS):
            continue
        url = urljoin(current, anchor.get("href", ""))
        if url != current:
            return url
    return None


def _list_pages(config: SourceConfig, url: str) -> tuple[list[str], int]:
    """抓取列表页及其后续分页，返回 HTML 列表。"""
    pages: list[str] = []
    seen: set[str] = set()
    cursor = url
    for _ in range(max(1, config.max_pages)):
        if cursor in seen:
            break
        seen.add(cursor)
        response = _get(cursor)
        pages.append(response.text)
        nxt = _next_page(cursor, response.text)
        if not nxt:
            break
        cursor = nxt
    return pages, len(pages)


# ------------------------------------------------------------------ 正文与附件


_ROW_TAGS = ("li", "tr", "dd", "dt", "td")


def _row_context(anchor: Any) -> str:
    """在链接所在的行（li/tr/td…）里取整行文本，便于解析该条的发布日期。

    很多列表页把日期放在链接的兄弟节点里，只读 anchor.parent 会漏掉，
    因此最多向上找 4 层；一旦遇到行级标签就停，避免把整块列表的日期都算进来。
    """
    node = anchor
    for _ in range(4):
        node = node.parent
        if node is None:
            break
        text = _clean(node.get_text(" ", strip=True))
        if node.name in _ROW_TAGS:
            return text
        if text and _parse_date(text) and len(text) < 400:
            return text
    parent = anchor.parent
    return _clean(parent.get_text(" ", strip=True)) if parent else ""


def _candidate_links(list_url: str, html: str, limit: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict[str, str]] = {}
    for anchor in soup.select("a[href]"):
        raw = anchor.get("title") or anchor.get_text(" ", strip=True)
        title = refine_title(_clean_title(_clean(raw)))
        if len(title) < 6:
            continue
        context = _row_context(anchor) or title
        published_at = _parse_date(context) or _parse_date(title)
        url = urljoin(list_url, anchor.get("href", ""))
        if not url.startswith(("http://", "https://")):
            continue
        if url in found:
            continue
        found[url] = {
            "title": title,
            "published_at": published_at or "",
            "category": _infer_category(title),
            "context": context[:300],
        }
        if len(found) >= limit:
            break
    return [{**item, "url": url} for url, item in found.items()]


# ------------------------------------------------------------------ 主入口


def _build_row(
    config: SourceConfig,
    candidate: dict[str, str],
    detail: dict[str, Any],
    checked_at: str,
    today: str,
) -> dict[str, Any] | None:
    title = candidate["title"]
    published_at = sanitize_published(candidate["published_at"], today)
    body = detail.get("body_text", "")
    context = candidate.get("context", "")
    attachment_names = " ".join(
        str(item.get("name", "")) for item in detail.get("attachments", [])
    )
    inferred_date = ""
    if not published_at:
        inferred_date = (
            infer_date_from_text(title, body, context, attachment_names) or ""
        )
    analysis = classify(title, body or candidate.get("context", ""))

    fallback_deadline = None
    if published_at:
        fallback_deadline = _extract_deadline(
            body or candidate.get("context", ""), int(published_at[:4])
        )
    deadline = analysis["deadline"] or fallback_deadline

    expired = is_expired(deadline, today)
    if deadline and published_at and deadline < published_at:
        # 截止时间早于发布时间说明解析有误，直接丢弃而不是误导用户。
        deadline = None
        expired = False

    if published_at and not within_years(published_at, 3, today):
        return None
    if not published_at and not body:
        return None

    attachments = detail.get("attachments", [])
    images = detail.get("images", [])
    if expired:
        # 已截止内容只保留元数据和官方链接（需求 5 / 13）
        body = ""
        attachments = []
        images = []

    row = {
        "id": _entry_id(config.id, candidate["url"]),
        "title": title,
        "official_title": title,
        "summary": summarize(title, body or candidate.get("context", "")),
        "source": config.name,
        "source_id": config.id,
        "source_name": config.name,
        "org_unit": config.name,
        "scope": config.scope,
        "published_at": published_at,
        "inferred_date": inferred_date,
        "deadline": deadline,
        "location": config.campus or config.scope,
        "campus": analysis["campus"] or config.campus or "",
        "categories": analysis["categories"],
        "category": analysis["categories"][0] if analysis["categories"] else "待分类",
        "kind": analysis["kind"],
        "audience": analysis["audience"],
        "audience_confirmed": analysis["audience_confirmed"],
        "times": analysis["times"],
        "needs_signup": analysis["needs_signup"],
        "needs_material": analysis["needs_material"],
        "online": analysis["online"],
        "prep_minutes": analysis["prep_minutes"],
        "materials": analysis["materials"],
        "steps": analysis["steps"] or ["阅读并核对官方原文"],
        "relevant": 0,
        "attachment_count": len(attachments),
        "attachments": attachments,
        "images": images,
        "official_url": candidate["url"],
        "status": "expired" if expired else "active",
        "favorite": False,
        "body_text": body,
        "group_key": group_key(title),
        "related_ids": [],
        "fetched_at": checked_at,
        "parse_error": "正文解析失败" if detail.get("parse_failed") and not body else "",
    }
    payload = "|".join(
        [
            row["title"],
            row.get("published_at") or "",
            row.get("deadline") or "",
            row["summary"],
            str(row["attachment_count"]),
        ]
    )
    row["content_hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return row


def scan_source(config: SourceConfig) -> ScanReport:
    """抓取单个来源。不抛异常，失败原因写进 report.error。"""
    checked_at = datetime.now().isoformat(timespec="seconds")
    today = date.today().isoformat()
    report = ScanReport(
        source_id=config.id, name=config.name, ok=False, checked_at=checked_at
    )

    try:
        entry_html = _get(config.list_url).text
    except Exception as exc:  # noqa: BLE001 - 抓取器需要对任意站点健壮
        report.error = _error_reason(exc)
        return report

    # 1) 决定要抓哪些列表页：配置栏目 + 自动发现的栏目
    columns: list[str] = list(config.list_urls)
    if config.auto_columns:
        try:
            columns.extend(discover_columns(config.list_url, entry_html))
        except Exception:  # noqa: BLE001
            pass
    seen_columns: set[str] = set()
    unique_columns: list[str] = []
    for url in columns:
        key = url.rstrip("/")
        if key in seen_columns:
            continue
        seen_columns.add(key)
        unique_columns.append(url)
    columns = unique_columns[:4]
    report.columns = columns

    candidates: dict[str, dict[str, str]] = {}
    pages_total = 0
    for column_url in columns:
        try:
            pages, count = _list_pages(config, column_url)
        except Exception:  # noqa: BLE001 - 单个栏目失败不影响其他栏目
            continue
        pages_total += count
        for html in pages:
            for item in _candidate_links(column_url, html, config.max_items):
                candidates.setdefault(item["url"], item)
        if len(candidates) >= config.max_items:
            break
    report.pages = pages_total
    report.candidates = len(candidates)
    if not candidates:
        report.error = "列表中未发现带日期的条目，可能是栏目改版或需要登录"
        return report

    ranked = sorted(
        candidates.values(),
        key=lambda item: item.get("published_at") or "",
        reverse=True,
    )[: config.max_items]

    rows: list[dict[str, Any]] = []
    detail_budget = config.detail_budget
    for candidate in ranked:
        detail: dict[str, Any] = {"body_text": "", "attachments": [], "images": []}
        if detail_budget > 0:
            try:
                detail = _extract_detail(candidate["url"])
                detail_budget -= 1
            except Exception as exc:  # noqa: BLE001
                detail = {
                    "body_text": "",
                    "attachments": [],
                    "images": [],
                    "parse_failed": True,
                    "error": _error_reason(exc),
                }
        else:
            detail["parse_failed"] = False
        try:
            row = _build_row(config, candidate, detail, checked_at, today)
        except Exception:  # noqa: BLE001 - 单条解析失败不影响整站
            continue
        if row:
            if detail.get("error"):
                row["parse_error"] = detail["error"]
            rows.append(row)

    report.rows = rows
    report.ok = True
    return report
