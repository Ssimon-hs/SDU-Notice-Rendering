/**
 * 前端渲染冒烟测试。
 *
 * 用 react-dom/server 把每个页面渲染成字符串，验证：
 * - 组件可以正常加载（没有未定义变量、错误引用）；
 * - 页面能产出关键文案（不是空白）。
 *
 * 由 smoke/run.mjs 通过 esbuild 打包后在 Node 里执行。
 */

import { renderToStaticMarkup } from "react-dom/server";
import { createElement as h } from "react";

import { StoreProvider } from "../src/lib/store.jsx";
import HomePage from "../src/pages/Home.jsx";
import Recommended from "../src/pages/Recommended.jsx";
import AllNotices from "../src/pages/AllNotices.jsx";
import TodoPage from "../src/pages/TodoPage.jsx";
import FavoritesPage from "../src/pages/FavoritesPage.jsx";
import CalendarPage from "../src/pages/CalendarPage.jsx";
import CommunityPage from "../src/pages/CommunityPage.jsx";
import SourcesPage from "../src/pages/SourcesPage.jsx";
import SettingsPage from "../src/pages/SettingsPage.jsx";
import SearchPage from "../src/pages/SearchPage.jsx";
import NoticeDetail from "../src/pages/NoticeDetail.jsx";
import Onboarding from "../src/pages/Onboarding.jsx";

const noop = () => {};

// 正文页会请求 /api/notices/{id}，这里给一个最小实现，让页面真正渲染出内容。
globalThis.fetch = (url) => {
  const target = String(url);
  if (target.includes("/api/notices/")) {
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SAMPLE[0]),
    });
  }
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ items: [] }) });
};

const SAMPLE = [
  {
    id: "n1",
    title: "关于举办山东大学第三届创新创业大赛的通知",
    summary: "面向全体本科生，线上提交报名表与项目计划书。",
    source: "本科生院",
    source_id: "sdu-undergraduate",
    source_name: "本科生院",
    published_at: "2026-09-20",
    deadline: "2026-12-20",
    next_action: "2026-12-20",
    location: "中心校区",
    campus: "中心校区",
    categories: ["竞赛通知"],
    kind: "通知",
    audience: ["本科生"],
    times: { signup_end: "2026-12-20" },
    needs_signup: true,
    needs_material: true,
    online: true,
    prep_minutes: 90,
    attachment_count: 1,
    attachments: [{ name: "报名表.docx", url: "https://x/1.docx", kind: "docx" }],
    materials: [{ name: "报名表", format: "docx", required: true, done: false }],
    steps: ["下载报名表", "提交材料"],
    official_url: "https://www.sdu.edu.cn/",
    status: "active",
    body_text: "请各团队于2026年12月20日前提交报名表。",
    related_ids: [],
  },
  {
    id: "n2",
    title: "我校学子在全国竞赛中荣获一等奖",
    summary: "近日比赛圆满结束。",
    source: "山大新闻网",
    source_id: "sdu-news",
    source_name: "山大新闻网",
    published_at: "2026-09-10",
    deadline: null,
    categories: ["普通新闻"],
    kind: "新闻",
    audience: [],
    times: {},
    status: "active",
    official_url: "https://www.sdu.edu.cn/",
    attachment_count: 0,
  },
];

const CASES = [
  ["引导页 Onboarding", h(Onboarding, { onFinish: noop, onSkip: noop }), ["产品目的", "填写进度"]],
  ["首页 Home", h(HomePage, { counts: () => ({}), active: "首页", onNavigate: noop, onScan: noop, scanning: false }), ["作者：松", "为你推荐"]],
  ["为你推荐", h(Recommended, { notices: SAMPLE, onOpen: noop, onToast: noop }), ["推荐范围"]],
  ["全部通知", h(AllNotices, { notices: SAMPLE, onOpen: noop, onToast: noop }), ["共收录"]],
  ["我的待办", h(TodoPage, { onOpenNotice: noop, onToast: noop }), ["我的待办"]],
  ["收藏", h(FavoritesPage, { notices: SAMPLE, onOpen: noop, onToast: noop }), ["收藏"]],
  ["校历", h(CalendarPage, { onOpenNotice: noop, onToast: noop }), ["月视图"]],
  ["校园社区", h(CommunityPage, {}), ["静态示例"]],
  ["信息源管理", h(SourcesPage, { onToast: noop }), ["信息源管理"]],
  ["系统设置", h(SettingsPage, { onRedoOnboarding: noop, onToast: noop }), ["AI 配置"]],
  ["搜索", h(SearchPage, { initialQuery: "竞赛", onOpen: noop, onToast: noop }), ["搜索范围"]],
  [
    "通知正文页",
    h(NoticeDetail, { noticeId: "n1", initialNotice: SAMPLE[0], onBack: noop, onToast: noop }),
    ["官方原文为准", "办理步骤"],
  ],
];

const results = [];
for (const [name, element, expected] of CASES) {
  try {
    const html = renderToStaticMarkup(h(StoreProvider, null, element));
    const missing = expected.filter((text) => !html.includes(text));
    results.push({
      name,
      ok: missing.length === 0 && html.length > 200,
      length: html.length,
      missing,
    });
  } catch (error) {
    results.push({ name, ok: false, error: `${error?.name}: ${error?.message}` });
  }
}

console.log(JSON.stringify(results, null, 2));
const failed = results.filter((item) => !item.ok);
if (failed.length) process.exitCode = 1;
