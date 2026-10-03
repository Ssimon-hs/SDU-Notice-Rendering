/** 日期、文本与展示用的小工具。 */

export const DAY = 86400000;

export function today() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

export function todayISO() {
  const now = today();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export function parseDate(value) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function daysLeft(value) {
  const target = parseDate(value);
  if (!target) return null;
  return Math.ceil((target - today()) / DAY);
}

export function isExpired(notice) {
  if (notice.status === "expired") return true;
  const left = daysLeft(notice.next_action || notice.deadline);
  return left !== null && left < 0;
}

export function formatDate(value, lang = "zh") {
  const date = parseDate(value);
  if (!date) return "";
  if (lang === "en") {
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

/** 中文「年月日」全格式：2026年10月2日（用于发布时间）。 */
export function formatCNDate(value) {
  const date = parseDate(value);
  if (!date) return "";
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

/**
 * 解析通知的展示日期标签（需求3：任何一条都给出一个具体时间，绝不出现「待确认」）。
 * 顺序：发布时间 → 内容里的活动时间节点 → 推断日期 → 截止时间 → 收录时间兜底。
 */
export function resolveDisplayDate(notice) {
  if (notice?.published_at && !notice?.date_inferred) {
    return { date: notice.published_at, labelKey: "notice.published", isActivity: false };
  }
  if (notice?.published_at && notice?.date_inferred) {
    return { date: notice.published_at, labelKey: "notice.activity", isActivity: true };
  }
  const times = notice?.times || {};
  const candidates = [times.event_start, times.event_end, times.signup_start, times.result_at, times.exam_at];
  for (const value of candidates) {
    if (value) return { date: value, labelKey: "notice.activity", isActivity: true };
  }
  // 兜底：后端从标题/摘要/正文/附件名推断出的日期（inferred_date）
  if (notice?.inferred_date) {
    return { date: notice.inferred_date, labelKey: "notice.activity", isActivity: true };
  }
  if (notice?.deadline) {
    return { date: notice.deadline, labelKey: "notice.deadline", isActivity: true };
  }
  // 最后兜底：收录时间（抓取到该条通知的日期），始终为具体日期，不再显示「待确认」类措辞
  if (notice?.fetched_at) {
    return { date: String(notice.fetched_at).slice(0, 10), labelKey: "notice.collected", isActivity: false };
  }
  return { date: null, labelKey: "notice.noTime", isActivity: false };
}

export function formatFullDate(value) {
  return value || "";
}

export function greeting(lang = "zh") {
  const hour = new Date().getHours();
  if (hour < 12) return lang === "en" ? "Good morning" : "早上好";
  if (hour < 18) return lang === "en" ? "Good afternoon" : "下午好";
  return lang === "en" ? "Good evening" : "晚上好";
}

/** 每天更换一句话（需求 3） */
const DAILY_LINES = [
  "一键山大，不错过每一次机会",
  "把通知变成行动",
  "重要的时间，提前一天就够从容",
  "先把要交的材料准备好",
  "看看有没有错过的一场讲座",
  "今天也别忘了给自己留一点时间",
  "机会常常藏在不起眼的公告里",
  "跨出学院，也许正好是你需要的",
];

export function dailyLine(dateIso = todayISO()) {
  const seed = dateIso.split("-").reduce((sum, part) => sum + Number(part), 0);
  return DAILY_LINES[seed % DAILY_LINES.length];
}

export const ENCOURAGEMENTS = {
  保研: "稳住绩点，材料早准备一步就是优势。",
  考研: "每天一点点，节奏比强度更重要。",
  竞赛: "找到一个靠谱的队友，比赛就成功一半。",
  奖学金: "把成果整理清楚，评审看得见你的努力。",
  实习: "先投出去，机会是在投递之后才出现的。",
  科研: "读文献的时间不会白费。",
  出国: "语言成绩早考早安心。",
  社团: "把一件事做到底，比参加十件事更有价值。",
};

export function encouragementFor(goals = []) {
  for (const goal of goals) {
    for (const key of Object.keys(ENCOURAGEMENTS)) {
      if (String(goal).includes(key)) return ENCOURAGEMENTS[key];
    }
  }
  return "";
}

export function urgencyClass(left) {
  if (left === null) return "";
  if (left < 0) return "past";
  if (left <= 3) return "urgent";
  if (left <= 7) return "soon";
  return "";
}

/** 把对象数组按某个字段统计成 { value, count } */
export function counter(rows, key) {
  const bucket = new Map();
  rows.forEach((row) => {
    const values = row[key];
    const list = Array.isArray(values) ? values : [values];
    list.forEach((value) => {
      if (!value) return;
      bucket.set(value, (bucket.get(value) || 0) + 1);
    });
  });
  return [...bucket.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count);
}

export function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

export function download(filename, content, mime = "application/json") {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** 生成 .ics 内容（需求 16：导出校历） */
export function toICS(events) {
  const stamp = (value) => `${value.replace(/-/g, "")}T090000`;
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//YijianSDU//ZH", "CALSCALE:GREGORIAN"];
  events.forEach((event, index) => {
    lines.push(
      "BEGIN:VEVENT",
      `UID:yijian-sdu-${index}-${event.date}@local`,
      `DTSTAMP:${stamp(event.date)}`,
      `DTSTART;VALUE=DATE:${stamp(event.date)}`,
      `DTEND;VALUE=DATE:${stamp(event.date)}`,
      `SUMMARY:${(event.title || "").replace(/[;,\\n]/g, " ")}`,
      `DESCRIPTION:${(event.source || "一键山大").replace(/[;,\\n]/g, " ")}`,
      "END:VEVENT",
    );
  });
  lines.push("END:VCALENDAR");
  return lines.join("\r\n");
}

export function monthOf(value) {
  return (value || "").slice(0, 7);
}

export function addMonths(monthIso, delta) {
  const [year, month] = monthIso.split("-").map(Number);
  const date = new Date(year, month - 1 + delta, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}
