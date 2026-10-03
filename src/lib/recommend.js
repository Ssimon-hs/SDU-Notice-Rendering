/**
 * 推荐引擎（需求 4）。
 *
 * 依据：身份、学院、专业、年级、校区、兴趣、目标、关键词、收藏、待办、
 * 搜索、阅读与停留。每条推荐都给出「为什么推荐给你」，
 * 并且强制保留一部分跨学院 / 跨兴趣内容，避免信息茧房。
 */

const DAY = 86400000;

function days(value) {
  if (!value) return null;
  const target = new Date(`${value}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  return Math.ceil((target - Date.now()) / DAY);
}

function includes(haystack, needle) {
  if (!haystack || !needle) return false;
  return String(haystack).toLowerCase().includes(String(needle).toLowerCase());
}

function overlap(listA, listB) {
  if (!Array.isArray(listA) || !Array.isArray(listB)) return [];
  return listA.filter((value) =>
    listB.some((other) => includes(other, value) || includes(value, other)),
  );
}

/**
 * 判断一条新闻/一次性活动类通知是否已结束、且不再可参与，
 * 从而不进入「为你推荐」。
 * 适用：迎新晚会、开学典礼、讲座、论坛、宣传报道等通常持续一天或一晚的内容，
 * 若活动结束时间已过、又无可行动节点（截止/报名），则结束即不再推荐。
 */
const NEWS_LIKE = ["普通新闻", "讲座／论坛", "活动通知", "宣传报道", "竞赛通知"];
function isPastOneDayEvent(notice) {
  const t = notice.times || {};
  const hasAction = Boolean(notice.next_action || notice.deadline);
  if (hasAction) return false;
  const newsLike =
    notice.kind === "新闻" ||
    (notice.categories || []).some((c) => NEWS_LIKE.includes(c));
  if (!newsLike) return false;
  const end = t.event_end;
  const start = t.event_start;
  if (end && days(end) < 0) return true;
  if (start && days(start) < 0) return true;
  return false;
}


/**
 * 计算一条通知与用户的匹配度。
 * @returns {{ score: number, reasons: string[], cross: boolean }}
 */
export function scoreNotice(notice, context) {
  const { profile, favorites, todos, searches, reads, hidden } = context;
  if (!profile) {
    return { score: 30, reasons: ["你还没有填写资料，这里先展示通用内容"], cross: false };
  }
  if (hidden.includes(notice.id)) {
    return { score: -1, reasons: [], cross: false };
  }

  let score = 20;
  const reasons = [];
  const audience = notice.audience || [];
  const categories = notice.categories || [];
  const haystack = `${notice.title} ${notice.summary || ""} ${notice.body_text || ""} ${audience.join(" ")} ${categories.join(" ")}`;

  // 身份 / 学院 / 专业 / 年级 / 校区
  const identityHit = profile.identity && audience.some((item) => includes(item, profile.identity));
  if (identityHit) {
    score += 18;
    reasons.push(`适用对象包含你的身份「${profile.identity}」`);
  }
  const collegeHit = profile.college && (includes(haystack, profile.college) || audience.some((item) => includes(item, profile.college)));
  if (collegeHit) {
    score += 16;
    reasons.push(`与你的学院「${profile.college}」相关`);
  }
  const majorHit = profile.major && includes(haystack, profile.major);
  if (majorHit) {
    score += 12;
    reasons.push(`与你的专业「${profile.major}」相关`);
  }
  const gradeHit = profile.grade && (includes(haystack, profile.grade) || audience.some((item) => includes(item, profile.grade)));
  if (gradeHit) {
    score += 10;
    reasons.push(`面向「${profile.grade}」`);
  }
  if (profile.campus && notice.campus && includes(notice.campus, profile.campus)) {
    score += 8;
    reasons.push(`在你所在的${profile.campus}`);
  }

  // 研究方向
  const researchHits = overlap(profile.research ? [profile.research] : [], [haystack]);
  if (researchHits.length) {
    score += 10;
    reasons.push(`与你的研究方向「${profile.research}」相关`);
  }

  // 兴趣
  const interestHits = overlap(profile.interests || [], categories.concat([haystack]));
  if (interestHits.length) {
    score += 9 * Math.min(interestHits.length, 3);
    reasons.push(`命中你关注的方向：${interestHits.slice(0, 3).join("、")}`);
  }

  // 目标
  const goalHits = overlap(profile.goals || [], [haystack]);
  if (goalHits.length) {
    score += 8 * Math.min(goalHits.length, 2);
    reasons.push(`与你的目标「${goalHits.slice(0, 2).join("、")}」有关`);
  }

  // 关键词
  const keywordHits = overlap(profile.keywords || [], [haystack]);
  if (keywordHits.length) {
    score += 7 * Math.min(keywordHits.length, 3);
    reasons.push(`包含你常用的关键词：${keywordHits.slice(0, 3).join("、")}`);
  }

  // 收藏 / 待办 / 搜索 / 阅读
  if (favorites[notice.id]) {
    score += 6;
    reasons.push("你收藏过这条内容");
  }
  if (todos.some((item) => item.noticeId === notice.id)) {
    score += 5;
    reasons.push("这条已经在你的待办里");
  }
  const searchHits = (searches || []).filter((item) => includes(haystack, item.q));
  if (searchHits.length) {
    score += 6;
    reasons.push(`你搜索过「${searchHits[0].q}」`);
  }
  const read = reads[notice.id];
  if (read && read.count > 0) {
    score += 3;
    reasons.push("你之前打开过这条内容");
  }

  // 屏蔽词
  const avoidHits = overlap(profile.avoid || [], [haystack]);
  if (avoidHits.length) {
    score -= 30;
    reasons.push(`命中你不想看到的内容：${avoidHits.slice(0, 2).join("、")}`);
  }

  // 时间紧迫度
  const left = days(notice.next_action || notice.deadline);
  if (left !== null) {
    if (left < 0) score -= 25;
    else if (left <= 3) score += 14;
    else if (left <= 7) score += 10;
    else if (left <= 14) score += 5;
    if (left >= 0 && left <= 7) reasons.push(`距离行动节点还有 ${left} 天`);
  }

  // 是否需要行动（通知优先于新闻）
  if (notice.kind === "通知") score += 6;
  if (notice.kind === "新闻") score -= 4;
  if (notice.kind === "公示／结果") score -= 2;

  // 是否跨出常用方向
  const matchedScope =
    identityHit || collegeHit || majorHit || gradeHit || interestHits.length > 0 || keywordHits.length > 0;
  const cross = !matchedScope && (categories.length > 0 || Boolean(notice.deadline));

  if (!reasons.length) {
    reasons.push("来自你订阅范围内的官方来源");
  }
  return { score, reasons: reasons.slice(0, 4), cross };
}

/**
 * 生成推荐列表。
 * @param {object[]} notices
 * @param {object} context  { profile, favorites, todos, searches, reads, hidden }
 * @param {object} options  { scope: "balanced" | "focused" | "explore", limit }
 */
export function recommend(notices, context, options = {}) {
  const { scope = "balanced", limit = 12 } = options;
  // 仅推荐「仍有效」且「发布于近 3 个月内」的内容，保证时效性与可参与性；
  // 三个月前发布、用户大多已无法及时参加的内容不再进入推荐。
  const cutoff = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10);
  const active = notices.filter(
    (item) =>
      item.status === "active" &&
      !context.hidden.includes(item.id) &&
      (!item.published_at || item.published_at >= cutoff) &&
      !isPastOneDayEvent(item),
  );
  const scored = active.map((notice) => ({
    notice,
    ...scoreNotice(notice, context),
  }));

  const matched = scored.filter((item) => !item.cross && item.score > 0);
  const cross = scored.filter((item) => item.cross && item.score > 0);
  matched.sort((a, b) => b.score - a.score);
  cross.sort((a, b) => b.score - a.score);

  // 破茧比例：均衡 25%，聚焦 10%，探索 50%
  const ratio = scope === "focused" ? 0.1 : scope === "explore" ? 0.5 : 0.25;
  const crossCount = Math.max(1, Math.round(limit * ratio));
  const picked = [...matched.slice(0, limit - crossCount), ...cross.slice(0, crossCount)];

  return picked.map((item) => ({
    ...item.notice,
    relevant: Math.max(0, Math.min(100, Math.round(item.score))),
    reasons: item.reasons,
    cross: item.cross,
  }));
}

/** 推荐范围说明文案 */
export const SCOPES = [
  { value: "balanced", label: "均衡（保留跨领域内容）" },
  { value: "focused", label: "聚焦（只推与我强相关）" },
  { value: "explore", label: "探索（更多跨学院内容）" },
];
