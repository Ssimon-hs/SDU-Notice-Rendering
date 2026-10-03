/**
 * 校历（需求 16 / M）。
 * 月视图 + 日程列表；官方校历、放假考试周、待办截止、关注活动、各类时间节点；
 * 不同类型不同颜色；点击打开通知；用户自己的提醒可拖动改期，官方时间不可修改；
 * 导出 .ics；切换「与我有关」和「全部公开活动」。
 */

import { useEffect, useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Download, List } from "lucide-react";
import { Banner, Empty, Section } from "../components/Shared.jsx";
import { api } from "../lib/api.js";
import { useI18n } from "../lib/i18n.js";
import { useStore } from "../lib/store.jsx";
import { addMonths, download, monthOf, todayISO, toICS } from "../lib/utils.js";

const TYPE_COLORS = {
  semester: "semester",
  holiday: "holiday",
  exam: "exam",
  deadline: "deadline",
  todo: "todo",
};

const TYPE_LABELS = {
  semester: "学期",
  holiday: "放假",
  exam: "考试周",
  deadline: "官方时间节点",
  todo: "我的待办",
};

export default function CalendarPage({ onOpenNotice, onToast }) {
  const { t } = useI18n();
  const { state, updateTodo } = useStore();
  const [month, setMonth] = useState(monthOf(todayISO()));
  const [events, setEvents] = useState([]);
  const [note, setNote] = useState("");
  const [mode, setMode] = useState("mine");
  const [view, setView] = useState("month");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .calendar(month)
      .then((data) => {
        if (!alive) return;
        setEvents(data.items || []);
        setNote(data.note || "");
      })
      .catch(() => alive && setEvents([]))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [month]);

  const todoEvents = useMemo(
    () =>
      state.todos
        .filter((item) => item.deadline && item.status !== "已完成")
        .map((item) => ({
          date: item.deadline,
          title: item.title,
          type: "todo",
          source: "我的待办",
          todoId: item.id,
          official: false,
        })),
    [state.todos],
  );

  const all = useMemo(() => [...events, ...todoEvents], [events, todoEvents]);

  const mine = useMemo(() => {
    if (!state.profile) return all;
    const keywords = [
      state.profile.college,
      state.profile.major,
      state.profile.grade,
      state.profile.campus,
      ...(state.profile.interests || []),
      ...(state.profile.keywords || []),
    ].filter(Boolean);
    const favouriteIds = new Set(Object.keys(state.favorites));
    return all.filter(
      (event) =>
        event.type === "todo" ||
        favouriteIds.has(event.notice_id) ||
        keywords.some((word) => String(event.title || "").includes(word)) ||
        String(event.source || "").includes(state.profile.college || "___"),
    );
  }, [all, state.profile, state.favorites]);

  const rows = mode === "mine" ? mine : all;

  const byDate = useMemo(() => {
    const map = new Map();
    rows.forEach((event) => {
      const list = map.get(event.date) || [];
      list.push(event);
      map.set(event.date, list);
    });
    return map;
  }, [rows]);

  const grid = useMemo(() => {
    const [year, monthNumber] = month.split("-").map(Number);
    const first = new Date(year, monthNumber - 1, 1);
    const startWeekday = first.getDay();
    const daysInMonth = new Date(year, monthNumber, 0).getDate();
    const cells = [];
    for (let index = 0; index < startWeekday; index += 1) cells.push(null);
    for (let day = 1; day <= daysInMonth; day += 1) {
      cells.push(`${month}-${String(day).padStart(2, "0")}`);
    }
    while (cells.length % 7 !== 0) cells.push(null);
    return cells;
  }, [month]);

  const exportICS = () => {
    download("一键山大校历.ics", toICS(rows), "text/calendar");
    onToast?.("已导出 .ics 文件");
  };

  const onDrop = (date, event) => {
    const todoId = event?.dataTransfer?.getData?.("text/todo");
    if (!todoId) return;
    updateTodo(todoId, { deadline: date });
    onToast?.(`已把待办改到 ${date}`);
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.calendar")}</span>
          <h1>{t("calendar.title")}</h1>
          <p>{note || t("calendar.note")}</p>
        </div>
        <div className="tab-row">
          <button
            type="button"
            className={`chip ${mode === "mine" ? "active" : ""}`}
            onClick={() => setMode("mine")}
          >
            {t("calendar.mine")}
          </button>
          <button
            type="button"
            className={`chip ${mode === "all" ? "active" : ""}`}
            onClick={() => setMode("all")}
          >
            {t("calendar.all")}
          </button>
          <button
            type="button"
            className={`chip ${view === "month" ? "active" : ""}`}
            onClick={() => setView("month")}
          >
            <CalendarDays size={13} /> {t("calendar.month")}
          </button>
          <button
            type="button"
            className={`chip ${view === "list" ? "active" : ""}`}
            onClick={() => setView("list")}
          >
            <List size={13} /> {t("calendar.list")}
          </button>
        </div>
      </header>

      <div className="calendar-toolbar">
        <button type="button" className="icon-button tiny" onClick={() => setMonth(addMonths(month, -1))}>
          <ChevronLeft size={15} />
        </button>
        <strong>{month}</strong>
        <button type="button" className="icon-button tiny" onClick={() => setMonth(addMonths(month, 1))}>
          <ChevronRight size={15} />
        </button>
        <button type="button" className="ghost-button" onClick={exportICS}>
          <Download size={15} /> {t("calendar.export")}
        </button>
        <span className="result-hint">
          写入 Windows 系统日历：先导出 .ics，双击后用系统日历打开即可（浏览器无法直接写入）。
        </span>
      </div>

      {loading && <p className="loading-line">{t("state.loading")}…</p>}

      {view === "month" ? (
        <div className="calendar-grid">
          {["日", "一", "二", "三", "四", "五", "六"].map((label) => (
            <div key={label} className="calendar-weekday">
              {label}
            </div>
          ))}
          {grid.map((date, index) => (
            <div
              key={date || `empty-${index}`}
              className={`calendar-cell ${date === todayISO() ? "today" : ""}`}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => date && onDrop(date, event)}
            >
              {date && <span className="cell-date">{Number(date.slice(-2))}</span>}
              {date &&
                (byDate.get(date) || []).slice(0, 3).map((event, eventIndex) => (
                  <button
                    key={`${event.title}-${eventIndex}`}
                    type="button"
                    className={`cell-event ${TYPE_COLORS[event.type] || "deadline"}`}
                    draggable={Boolean(event.todoId)}
                    onDragStart={(dragEvent) =>
                      event.todoId && dragEvent.dataTransfer.setData("text/todo", event.todoId)
                    }
                    onClick={() => {
                      if (event.notice_id) onOpenNotice?.(event.notice_id);
                      else if (event.official_url) window.open(event.official_url, "_blank");
                    }}
                    title={`${TYPE_LABELS[event.type] || "日程"} · ${event.title}`}
                  >
                    {event.title.length > 14 ? `${event.title.slice(0, 14)}…` : event.title}
                  </button>
                ))}
              {date && (byDate.get(date) || []).length > 3 && (
                <span className="cell-more">+{(byDate.get(date) || []).length - 3}</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="agenda">
          {rows.length ? (
            rows
              .slice()
              .sort((a, b) => String(a.date).localeCompare(String(b.date)))
              .map((event, index) => (
                <div key={`${event.date}-${event.title}-${index}`} className="agenda-row">
                  <span className={`dot ${TYPE_COLORS[event.type] || "deadline"}`} />
                  <strong>{event.date}</strong>
                  <span className="agenda-title">{event.title}</span>
                  <em>{TYPE_LABELS[event.type] || "日程"}</em>
                  {event.notice_id && (
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => onOpenNotice?.(event.notice_id)}
                    >
                      打开通知
                    </button>
                  )}
                </div>
              ))
          ) : (
            <Empty title={t("state.empty")} hint="切换成「全部公开活动」看看。" />
          )}
        </div>
      )}

      <Section title="颜色说明">
        <div className="legend">
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <span key={key} className={`legend-item ${key}`}>
              <i /> {label}
            </span>
          ))}
        </div>
      </Section>

      <Banner tone="info">
        官方时间不可修改；只有你自己的待办截止可以拖动到其它日期。
      </Banner>
    </div>
  );
}
