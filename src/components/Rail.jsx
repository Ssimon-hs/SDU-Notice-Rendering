/**
 * 首页右侧功能栏（需求 3）。
 * 保留：为你推荐、全部通知、我的待办、收藏、校历、校园社区。
 * 支持折叠、排序和显示 / 隐藏模块。
 */

import { useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  Bookmark,
  CalendarDays,
  Check,
  Eye,
  EyeOff,
  LayoutList,
  PanelRightClose,
  Settings2,
  Sparkles,
  Users,
} from "lucide-react";
import { useI18n } from "../lib/i18n.js";
import { useStore } from "../lib/store.jsx";

export const RAIL_ITEMS = [
  { key: "为你推荐", icon: Sparkles },
  { key: "全部通知", icon: LayoutList },
  { key: "我的待办", icon: Check },
  { key: "收藏", icon: Bookmark },
  { key: "校历", icon: CalendarDays },
  { key: "校园社区", icon: Users },
];

const ICONS = {
  为你推荐: Sparkles,
  全部通知: LayoutList,
  我的待办: Check,
  收藏: Bookmark,
  校历: CalendarDays,
  校园社区: Users,
};

export default function Rail({ active, onNavigate, counts = {} }) {
  const { t } = useI18n();
  const { state, patchSettings } = useStore();
  const settings = state.settings;
  const [editing, setEditing] = useState(false);

  const collapsed = settings.railCollapsed;
  const order = settings.railOrder?.length ? settings.railOrder : RAIL_ITEMS.map((i) => i.key);
  const hidden = settings.railHidden || [];

  const move = (index, delta) => {
    const next = [...order];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    patchSettings({ railOrder: next });
  };

  const toggleHidden = (key) => {
    patchSettings({
      railHidden: hidden.includes(key)
        ? hidden.filter((value) => value !== key)
        : [...hidden, key],
    });
  };

  if (collapsed) {
    return (
      <aside className="rail collapsed">
        <button
          type="button"
          className="icon-button"
          onClick={() => patchSettings({ railCollapsed: false })}
          title={t("home.railExpand")}
          aria-label={t("home.railExpand")}
        >
          <PanelRightClose size={18} />
        </button>
        <div className="rail-collapsed-items">
          {order
            .filter((key) => !hidden.includes(key))
            .map((key) => {
              const Icon = ICONS[key] || Sparkles;
              return (
                <button
                  key={key}
                  type="button"
                  className={`icon-button ${active === key ? "selected" : ""}`}
                  onClick={() => onNavigate(key)}
                  title={t(`nav.${NAV_KEY[key]}`) || key}
                  aria-label={key}
                >
                  <Icon size={17} />
                </button>
              );
            })}
        </div>
      </aside>
    );
  }

  return (
    <aside className="rail" style={{ width: settings.railWidth || 300 }}>
      <div className="rail-head">
        <span>{t("home.rail")}</span>
        <div className="rail-head-actions">
          <button
            type="button"
            className={`icon-button tiny ${editing ? "selected" : ""}`}
            onClick={() => setEditing((value) => !value)}
            title="调整模块顺序和显示内容"
            aria-label="调整模块顺序和显示内容"
          >
            <Settings2 size={15} />
          </button>
          <button
            type="button"
            className="icon-button tiny"
            onClick={() => patchSettings({ railCollapsed: true })}
            title={t("home.railCollapse")}
            aria-label={t("home.railCollapse")}
          >
            <PanelRightClose size={15} />
          </button>
        </div>
      </div>

      <div className="rail-list">
        {order.map((key, index) => {
          const Icon = ICONS[key] || Sparkles;
          const isHidden = hidden.includes(key);
          if (isHidden && !editing) return null;
          return (
            <div key={key} className={`rail-item ${active === key ? "active" : ""}`}>
              <button
                type="button"
                className="rail-main"
                onClick={() => onNavigate(key)}
                disabled={editing}
              >
                <Icon size={17} strokeWidth={1.8} />
                <span>{t(`nav.${NAV_KEY[key]}`) || key}</span>
                {counts[key] ? <b>{counts[key]}</b> : null}
              </button>
              {editing && (
                <div className="rail-editors">
                  <button
                    type="button"
                    className="icon-button tiny"
                    onClick={() => move(index, -1)}
                    aria-label="上移"
                  >
                    <ArrowUp size={13} />
                  </button>
                  <button
                    type="button"
                    className="icon-button tiny"
                    onClick={() => move(index, 1)}
                    aria-label="下移"
                  >
                    <ArrowDown size={13} />
                  </button>
                  <button
                    type="button"
                    className="icon-button tiny"
                    onClick={() => toggleHidden(key)}
                    aria-label={isHidden ? "显示" : "隐藏"}
                  >
                    {isHidden ? <EyeOff size={13} /> : <Eye size={13} />}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="rail-foot">
        <button type="button" className="text-button" onClick={() => onNavigate("信息源管理")}>
          信息源管理
        </button>
        <button type="button" className="text-button" onClick={() => onNavigate("系统设置")}>
          系统设置
        </button>
      </div>
    </aside>
  );
}

const NAV_KEY = {
  为你推荐: "recommend",
  全部通知: "all",
  我的待办: "todo",
  收藏: "favorites",
  校历: "calendar",
  校园社区: "community",
};
