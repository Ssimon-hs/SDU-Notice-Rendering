/**
 * 我的待办（需求 15）。
 * 只由用户手动加入（收藏与推荐都不会自动创建），按最近截止时间排序，
 * 支持状态、自定义截止、提醒、备注、子任务、材料勾选、完整时间表、写入日历。
 */

import { useMemo, useState } from "react";
import {
  CalendarPlus,
  Check,
  ExternalLink,
  ListTodo,
  Plus,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { Empty, Section } from "../components/Shared.jsx";
import { useI18n } from "../lib/i18n.js";
import { useStore } from "../lib/store.jsx";
import { daysLeft, download, toICS } from "../lib/utils.js";

const STATUSES = ["未开始", "进行中", "已提交，等待结果", "已完成"];

export default function TodoPage({ onOpenNotice, onToast }) {
  const { t } = useI18n();
  const { state, updateTodo, removeTodo } = useStore();
  const [tab, setTab] = useState("active");
  const [newSubtask, setNewSubtask] = useState({});

  const active = useMemo(
    () =>
      state.todos
        .filter((item) => item.status !== "已完成")
        .sort((a, b) => String(a.deadline || "9999").localeCompare(String(b.deadline || "9999"))),
    [state.todos],
  );
  const history = useMemo(
    () => state.todos.filter((item) => item.status === "已完成"),
    [state.todos],
  );
  const rows = tab === "active" ? active : history;

  const toggleMaterial = (todo, index) => {
    const materials = [...(todo.materials || [])];
    materials[index] = { ...materials[index], done: !materials[index].done };
    updateTodo(todo.id, { materials });
  };

  const addSubtask = (todo) => {
    const title = (newSubtask[todo.id] || "").trim();
    if (!title) return;
    updateTodo(todo.id, {
      subtasks: [...(todo.subtasks || []), { id: `st-${Date.now()}`, title, done: false }],
    });
    setNewSubtask((current) => ({ ...current, [todo.id]: "" }));
  };

  const exportTodo = (todo) => {
    if (!todo.deadline) {
      onToast?.("请先设置截止时间");
      return;
    }
    download(`todo-${todo.id}.ics`, toICS([{ date: todo.deadline, title: todo.title }]), "text/calendar");
    onToast?.("已导出 .ics");
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.todo")}</span>
          <h1>{t("todo.title")}</h1>
          <p>只有你手动加入的事项会出现在这里；收藏和推荐都不会自动创建待办。</p>
        </div>
        <div className="tab-row">
          <button
            type="button"
            className={`chip ${tab === "active" ? "active" : ""}`}
            onClick={() => setTab("active")}
          >
            进行中 {active.length}
          </button>
          <button
            type="button"
            className={`chip ${tab === "history" ? "active" : ""}`}
            onClick={() => setTab("history")}
          >
            {t("todo.history")} {history.length}
          </button>
        </div>
      </header>

      {!rows.length && (
        <Empty
          icon={<ListTodo size={24} />}
          title={tab === "active" ? t("todo.empty") : "还没有已完成的事项"}
          hint={tab === "active" ? "在通知卡片上点「加入待办」即可添加。" : ""}
        />
      )}

      <div className="todo-list">
        {rows.map((todo) => {
          const left = daysLeft(todo.deadline);
          const materials = todo.materials || [];
          const doneCount = materials.filter((item) => item.done).length;
          return (
            <article key={todo.id} className="todo-card">
              <div className="todo-head">
                <div>
                  <h3>{todo.title}</h3>
                  <div className="todo-meta">
                    <span>{todo.source || "自定义"}</span>
                    {todo.deadline && (
                      <span className={left !== null && left < 0 ? "urgent" : ""}>
                        截止 {todo.deadline}
                        {left !== null ? `（${left >= 0 ? `剩 ${left} 天` : "已过"}）` : ""}
                      </span>
                    )}
                    {materials.length > 0 && (
                      <span>
                        材料 {doneCount}/{materials.length}
                      </span>
                    )}
                  </div>
                </div>
                <div className="todo-head-actions">
                  <select
                    value={todo.status}
                    onChange={(event) => updateTodo(todo.id, { status: event.target.value })}
                  >
                    {STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="icon-button tiny"
                    onClick={exportTodo.bind(null, todo)}
                    title={t("todo.calendar")}
                  >
                    <CalendarPlus size={15} />
                  </button>
                  {todo.noticeId && (
                    <button
                      type="button"
                      className="icon-button tiny"
                      onClick={() => onOpenNotice?.(todo.noticeId)}
                      title="打开通知"
                    >
                      <ExternalLink size={15} />
                    </button>
                  )}
                  {todo.status === "已完成" ? (
                    <button
                      type="button"
                      className="icon-button tiny"
                      onClick={() => updateTodo(todo.id, { status: "进行中" })}
                      title={t("todo.restore")}
                    >
                      <RotateCcw size={15} />
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="icon-button tiny danger"
                    onClick={() => removeTodo(todo.id)}
                    title={t("action.delete")}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              <div className="todo-controls">
                <label>
                  <span>自定义截止</span>
                  <input
                    type="date"
                    value={todo.deadline || ""}
                    onChange={(event) => updateTodo(todo.id, { deadline: event.target.value })}
                  />
                </label>
                <label>
                  <span>{t("todo.reminder")}</span>
                  <input
                    type="datetime-local"
                    value={todo.reminderAt || ""}
                    onChange={(event) => updateTodo(todo.id, { reminderAt: event.target.value })}
                  />
                </label>
                <label className="grow">
                  <span>{t("todo.note")}</span>
                  <input
                    value={todo.note || ""}
                    onChange={(event) => updateTodo(todo.id, { note: event.target.value })}
                    placeholder="写点什么，比如材料放在哪里"
                  />
                </label>
              </div>

              {materials.length > 0 && (
                <Section title={`${t("notice.material")}（${doneCount}/${materials.length}）`}>
                  <div className="material-checks">
                    {materials.map((item, index) => (
                      <label key={item.name + index} className={item.done ? "done" : ""}>
                        <input
                          type="checkbox"
                          checked={Boolean(item.done)}
                          onChange={() => toggleMaterial(todo, index)}
                        />
                        <span>{item.name}</span>
                        {item.format && <em>.{String(item.format).replace(".", "")}</em>}
                      </label>
                    ))}
                  </div>
                </Section>
              )}

              <Section title={t("todo.subtask")}>
                <div className="subtasks">
                  {(todo.subtasks || []).map((subtask, index) => (
                    <label key={subtask.id || index} className={subtask.done ? "done" : ""}>
                      <input
                        type="checkbox"
                        checked={Boolean(subtask.done)}
                        onChange={() => {
                          const subtasks = [...(todo.subtasks || [])];
                          subtasks[index] = { ...subtasks[index], done: !subtasks[index].done };
                          updateTodo(todo.id, { subtasks });
                        }}
                      />
                      <span>{subtask.title}</span>
                    </label>
                  ))}
                  <div className="subtask-add">
                    <input
                      value={newSubtask[todo.id] || ""}
                      onChange={(event) =>
                        setNewSubtask((current) => ({ ...current, [todo.id]: event.target.value }))
                      }
                      placeholder="添加子任务"
                      onKeyDown={(event) => event.key === "Enter" && addSubtask(todo)}
                    />
                    <button type="button" className="icon-button tiny" onClick={() => addSubtask(todo)}>
                      <Plus size={14} />
                    </button>
                  </div>
                </div>
              </Section>

              {todo.status === "已提交，等待结果" && (
                <p className="todo-hint">
                  <Check size={14} /> 已提交。若这条通知后续出现公示或结果，首页会提醒你查看。
                </p>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
