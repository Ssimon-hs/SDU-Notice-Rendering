/**
 * 应用外壳：页面路由、全局数据加载、主题与提醒。
 *
 * 页面：首页 / 为你推荐 / 全部通知 / 我的待办 / 收藏 / 校历 / 校园社区 /
 *       信息源管理 / 系统设置 / 搜索 / 通知正文页
 */

import { useCallback, useEffect, useState } from "react";
import {
  Bookmark,
  CalendarDays,
  Check,
  Home,
  LayoutList,
  LoaderCircle,
  Moon,
  Search,
  Settings,
  Sparkles,
  Sun,
  Users,
  X,
} from "lucide-react";
import { api } from "./lib/api.js";
import { useI18n } from "./lib/i18n.js";
import { useStore } from "./lib/store.jsx";
import { daysLeft } from "./lib/utils.js";
import AllNotices from "./pages/AllNotices.jsx";
import CalendarPage from "./pages/CalendarPage.jsx";
import CommunityPage from "./pages/CommunityPage.jsx";
import FavoritesPage from "./pages/FavoritesPage.jsx";
import ForecastPage from "./pages/ForecastPage.jsx";
import HomePage from "./pages/Home.jsx";
import NoticeDetail from "./pages/NoticeDetail.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import Recommended from "./pages/Recommended.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import SourcesPage from "./pages/SourcesPage.jsx";
import TodoPage from "./pages/TodoPage.jsx";

const NAV = [
  { key: "首页", icon: Home },
  { key: "为你推荐", icon: Sparkles },
  { key: "全部通知", icon: LayoutList },
  { key: "我的待办", icon: Check },
  { key: "收藏", icon: Bookmark },
  { key: "校历", icon: CalendarDays },
  { key: "校园社区", icon: Users },
  { key: "活动预测", icon: CalendarDays },
];

export default function App() {
  const { t } = useI18n();
  const { state, patchSettings, saveProfile, skipOnboarding, reopenOnboarding } = useStore();

  const [page, setPage] = useState("首页");
  const [detailId, setDetailId] = useState(null);
  const [cachedNotice, setCachedNotice] = useState(null);
  const [notices, setNotices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [query, setQuery] = useState("");
  const [scanning, setScanning] = useState(false);
  const [toast, setToast] = useState("");
  const [reminders, setReminders] = useState([]);

  const notify = useCallback((message) => {
    setToast(message);
    setTimeout(() => setToast(""), 2600);
  }, []);

  // 主题
  useEffect(() => {
    document.documentElement.dataset.theme = state.settings.theme || "dark";
  }, [state.settings.theme]);

  // 首次加载数据
  const loadNotices = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.notices({ active_only: false, limit: 2000, include_body: false });
      setNotices(data.items || []);
      setOffline(false);
    } catch {
      setOffline(true);
      setNotices([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadNotices();
  }, [loadNotices]);

  // 本地提醒：只在工作台内提示（需求 18）
  useEffect(() => {
    const lead = Number(state.settings.reminder?.leadMinutes || 1440);
    if (!state.settings.reminder?.enabled) return;
    const due = state.todos.filter((item) => {
      if (item.status === "已完成" || !item.deadline) return false;
      const left = daysLeft(item.deadline);
      return left !== null && left >= 0 && left * 1440 <= lead;
    });
    setReminders(due);
  }, [state.todos, state.settings.reminder]);

  const counts = useCallback(
    () => ({
      我的待办: state.todos.filter((item) => item.status !== "已完成").length,
      收藏: Object.keys(state.favorites).length,
      为你推荐: 12,
    }),
    [state.todos, state.favorites],
  );

  const runScan = async () => {
    setScanning(true);
    try {
      await api.scan();
      const poll = setInterval(async () => {
        const status = await api.scanStatus().catch(() => null);
        if (status && !status.running) {
          clearInterval(poll);
          setScanning(false);
          await loadNotices();
          notify(`检查完成：新增 ${status.new_items} 条，更新 ${status.changed_items} 条`);
        }
      }, 2000);
    } catch (err) {
      setScanning(false);
      notify(err.message || t("state.offline"));
    }
  };

  const openNotice = (notice) => {
    setDetailId(notice.id || notice);
    setCachedNotice(typeof notice === "object" ? notice : null);
    setPage("正文");
  };

  const navigate = (key) => {
    setDetailId(null);
    setCachedNotice(null);
    setPage(key);
  };

  if (!state.onboarded) {
    return (
      <div className="app-shell">
        <Onboarding
          onFinish={(profile) => {
            saveProfile(profile);
            setPage("首页");
          }}
          onSkip={() => {
            skipOnboarding();
            setPage("首页");
          }}
        />
      </div>
    );
  }

  const renderPage = () => {
    if (page === "正文" && detailId) {
      return (
        <NoticeDetail
          noticeId={detailId}
          initialNotice={cachedNotice}
          onBack={() => setPage("首页")}
          onToast={notify}
        />
      );
    }
    switch (page) {
      case "为你推荐":
        return <Recommended notices={notices} onOpen={openNotice} onToast={notify} />;
      case "全部通知":
        return <AllNotices notices={notices} onOpen={openNotice} onToast={notify} />;
      case "我的待办":
        return (
          <TodoPage
            onOpenNotice={(id) => {
              setDetailId(id);
              setCachedNotice(notices.find((item) => item.id === id) || null);
              setPage("正文");
            }}
            onToast={notify}
          />
        );
      case "收藏":
        return <FavoritesPage notices={notices} onOpen={openNotice} onToast={notify} />;
      case "校历":
        return (
          <CalendarPage
            onOpenNotice={(id) => {
              setDetailId(id);
              setCachedNotice(notices.find((item) => item.id === id) || null);
              setPage("正文");
            }}
            onToast={notify}
          />
        );
      case "校园社区":
        return <CommunityPage />;
      case "活动预测":
        return (
          <ForecastPage
            onToast={notify}
            onOpenNotice={(id) => {
              setDetailId(id);
              setCachedNotice(notices.find((item) => item.id === id) || null);
              setPage("正文");
            }}
          />
        );
      case "信息源管理":
        return <SourcesPage onToast={notify} />;
      case "系统设置":
        return <SettingsPage onRedoOnboarding={reopenOnboarding} onToast={notify} />;
      case "搜索":
        return <SearchPage initialQuery={query} onOpen={openNotice} onToast={notify} />;
      default:
        return (
          <HomePage
            counts={counts}
            active={page}
            onNavigate={navigate}
            onScan={runScan}
            scanning={scanning}
          />
        );
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button
          type="button"
          className={`icon-button ${page === "首页" ? "selected" : ""}`}
          onClick={() => navigate("首页")}
          title={t("nav.home")}
        >
          <Home size={18} />
        </button>

        <div className="nav-inline">
          {NAV.slice(1).map((item) => (
            <button
              type="button"
              key={item.key}
              className={`nav-inline-item ${page === item.key ? "active" : ""}`}
              onClick={() => navigate(item.key)}
            >
              <item.icon size={15} />
              {t(`nav.${NAV_KEY[item.key]}`)}
            </button>
          ))}
        </div>

        <div className="search-box">
          <Search size={17} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                setPage("搜索");
              }
            }}
            placeholder={t("search.placeholder")}
          />
        </div>

        <button type="button" className="scan-button" onClick={runScan} disabled={scanning}>
          {scanning ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}
          {scanning ? t("action.checking") : t("action.check")}
        </button>

        <button
          type="button"
          className="icon-button"
          onClick={() =>
            patchSettings({ theme: state.settings.theme === "dark" ? "light" : "dark" })
          }
          title={t("settings.theme")}
        >
          {state.settings.theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <button
          type="button"
          className={`icon-button ${page === "系统设置" ? "selected" : ""}`}
          onClick={() => navigate("系统设置")}
          title={t("nav.settings")}
        >
          <Settings size={18} />
        </button>
      </header>

      {offline && (
        <div className="banner error">
          {t("state.offline")}
          <button type="button" className="small-button" onClick={loadNotices}>
            {t("action.retry")}
          </button>
        </div>
      )}

      {reminders.length > 0 && (
        <div className="banner warn">
          有 {reminders.length} 项待办临近截止：
          {reminders.slice(0, 3).map((item) => item.title).join("、")}
          <button type="button" className="small-button" onClick={() => setReminders([])}>
            <X size={13} />
          </button>
        </div>
      )}

      {loading ? (
        <div className="page">
          <p className="loading-line">
            <LoaderCircle className="spin" size={16} /> {t("state.loading")}…
          </p>
        </div>
      ) : (
        renderPage()
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

const NAV_KEY = {
  为你推荐: "recommend",
  全部通知: "all",
  我的待办: "todo",
  收藏: "favorites",
  校历: "calendar",
  校园社区: "community",
  活动预测: "forecast",
};
