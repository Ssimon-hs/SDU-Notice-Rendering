/**
 * 本地状态中心。
 *
 * 需求 18：所有用户数据默认保存在本地，不登录、不同步。
 * 画像 / 收藏 / 待办 / 设置 / 屏蔽 / 搜索记录 / 阅读记录全部写 localStorage，
 * 并提供导出、导入与重置。
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

const STORAGE_KEY = "yijian-sdu:v1";
const BACKUP_KEY = "yijian-sdu:backup";

const DEFAULT_STATE = {
  profile: null,
  onboarded: false,
  favorites: {}, // noticeId -> { folder, tags, note, addedAt, snapshot }
  folders: ["默认收藏"],
  todos: [], // { id, noticeId, title, deadline, status, note, subtasks, materials, reminderAt }
  settings: {
    theme: "dark",
    lang: "zh",
    railCollapsed: false,
    railWidth: 300,
    railOrder: ["为你推荐", "全部通知", "我的待办", "收藏", "校历", "校园社区"],
    railHidden: [],
    slogan: "",
    showExpired: false,
    savedFilters: [],
    ai: { enabled: false, provider: "openai", baseUrl: "", model: "", apiKey: "" },
    reminder: { enabled: true, quietHours: "22:00-08:00", leadMinutes: 1440 },
  },
  hidden: [], // 不感兴趣的通知 id
  searches: [], // { q, at }
  reads: {}, // noticeId -> { count, lastAt }
};

function loadState() {
  if (typeof window === "undefined") return DEFAULT_STATE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    const parsed = JSON.parse(raw);
    return {
      ...DEFAULT_STATE,
      ...parsed,
      settings: { ...DEFAULT_STATE.settings, ...(parsed.settings || {}) },
    };
  } catch {
    return DEFAULT_STATE;
  }
}

const StoreContext = createContext(null);

export function StoreProvider({ children }) {
  const [state, setState] = useState(loadState);
  const timer = useRef(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch {
        // 存储写满时静默失败，不影响使用
      }
    }, 200);
    return () => clearTimeout(timer.current);
  }, [state]);

  const patch = useCallback((partial) => {
    setState((current) => ({ ...current, ...partial }));
  }, []);

  const patchSettings = useCallback((partial) => {
    setState((current) => ({
      ...current,
      settings: { ...current.settings, ...partial },
    }));
  }, []);

  // ------------------------------------------------------------ 画像

  const saveProfile = useCallback(
    (profile) => setState((current) => ({ ...current, profile, onboarded: true })),
    [],
  );

  const skipOnboarding = useCallback(
    () => setState((current) => ({ ...current, onboarded: true })),
    [],
  );

  const reopenOnboarding = useCallback(
    () => setState((current) => ({ ...current, onboarded: false })),
    [],
  );

  // ------------------------------------------------------------ 收藏

  const isFavorite = useCallback(
    (id) => Boolean(state.favorites[id]),
    [state.favorites],
  );

  const toggleFavorite = useCallback((notice, folder) => {
    setState((current) => {
      const next = { ...current.favorites };
      if (next[notice.id]) {
        delete next[notice.id];
      } else {
        next[notice.id] = {
          folder: folder || current.folders[0] || "默认收藏",
          tags: [],
          note: "",
          addedAt: new Date().toISOString(),
          snapshot: {
            title: notice.title,
            source: notice.source,
            published_at: notice.published_at,
            deadline: notice.deadline,
            official_url: notice.official_url,
            categories: notice.categories || [],
          },
        };
      }
      return { ...current, favorites: next };
    });
  }, []);

  const updateFavorite = useCallback((id, partial) => {
    setState((current) => {
      if (!current.favorites[id]) return current;
      return {
        ...current,
        favorites: { ...current.favorites, [id]: { ...current.favorites[id], ...partial } },
      };
    });
  }, []);

  const removeFavorites = useCallback((ids) => {
    setState((current) => {
      const next = { ...current.favorites };
      ids.forEach((id) => delete next[id]);
      return { ...current, favorites: next };
    });
  }, []);

  const addFolder = useCallback((name) => {
    setState((current) =>
      current.folders.includes(name)
        ? current
        : { ...current, folders: [...current.folders, name] },
    );
  }, []);

  // ------------------------------------------------------------ 待办

  const addTodo = useCallback((todo) => {
    setState((current) => {
      if (todo.noticeId && current.todos.some((item) => item.noticeId === todo.noticeId)) {
        return current;
      }
      return {
        ...current,
        todos: [
          {
            id: `todo-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            status: "未开始",
            note: "",
            subtasks: [],
            materials: [],
            reminderAt: "",
            createdAt: new Date().toISOString(),
            ...todo,
          },
          ...current.todos,
        ],
      };
    });
  }, []);

  const updateTodo = useCallback((id, partial) => {
    setState((current) => ({
      ...current,
      todos: current.todos.map((item) =>
        item.id === id ? { ...item, ...partial } : item,
      ),
    }));
  }, []);

  const removeTodo = useCallback((id) => {
    setState((current) => ({
      ...current,
      todos: current.todos.filter((item) => item.id !== id),
    }));
  }, []);

  const inTodo = useCallback(
    (noticeId) => state.todos.some((item) => item.noticeId === noticeId),
    [state.todos],
  );

  // ------------------------------------------------------------ 其它

  const hideNotice = useCallback((id) => {
    setState((current) =>
      current.hidden.includes(id) ? current : { ...current, hidden: [...current.hidden, id] },
    );
  }, []);

  const unhideNotice = useCallback((id) => {
    setState((current) => ({
      ...current,
      hidden: current.hidden.filter((value) => value !== id),
    }));
  }, []);

  const recordSearch = useCallback((q) => {
    if (!q || !q.trim()) return;
    setState((current) => ({
      ...current,
      searches: [{ q: q.trim(), at: new Date().toISOString() }, ...current.searches].slice(0, 50),
    }));
  }, []);

  const recordRead = useCallback((id) => {
    setState((current) => {
      const previous = current.reads[id] || { count: 0, lastAt: "" };
      return {
        ...current,
        reads: {
          ...current.reads,
          [id]: { count: previous.count + 1, lastAt: new Date().toISOString() },
        },
      };
    });
  }, []);

  // ------------------------------------------------------------ 数据管理

  const exportAll = useCallback(() => {
    try {
      window.localStorage.setItem(BACKUP_KEY, JSON.stringify(state));
    } catch {
      // 忽略
    }
    return { ...state, exported_at: new Date().toISOString() };
  }, [state]);

  const importAll = useCallback((payload) => {
    if (!payload || typeof payload !== "object") return false;
    setState((current) => ({
      ...DEFAULT_STATE,
      ...payload,
      settings: { ...DEFAULT_STATE.settings, ...(payload.settings || {}) },
    }));
    return true;
  }, []);

  const resetAll = useCallback(() => {
    setState({ ...DEFAULT_STATE, onboarded: false, profile: null });
  }, []);

  const value = useMemo(
    () => ({
      state,
      patch,
      patchSettings,
      saveProfile,
      skipOnboarding,
      reopenOnboarding,
      isFavorite,
      toggleFavorite,
      updateFavorite,
      removeFavorites,
      addFolder,
      addTodo,
      updateTodo,
      removeTodo,
      inTodo,
      hideNotice,
      unhideNotice,
      recordSearch,
      recordRead,
      exportAll,
      importAll,
      resetAll,
    }),
    [
      state,
      patch,
      patchSettings,
      saveProfile,
      skipOnboarding,
      reopenOnboarding,
      isFavorite,
      toggleFavorite,
      updateFavorite,
      removeFavorites,
      addFolder,
      addTodo,
      updateTodo,
      removeTodo,
      inTodo,
      hideNotice,
      unhideNotice,
      recordSearch,
      recordRead,
      exportAll,
      importAll,
      resetAll,
    ],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const value = useContext(StoreContext);
  if (!value) throw new Error("useStore 必须在 StoreProvider 内使用");
  return value;
}

export { DEFAULT_STATE, STORAGE_KEY };
