/**
 * 后端 API 客户端。
 * - Base URL 为空：开发时由 vite 代理到 8765，生产时由后端同源提供；
 * - 4xx 不重试，直接把可读文案抛给页面；5xx 与网络失败最多重试 3 次；
 * - 统一错误结构 { error } 映射为中文提示。
 */

const BASE = "";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const FRIENDLY = {
  notice_not_found: "没有找到这条通知，它可能已被清理。",
  scan_already_running: "已经有一次检查正在运行，请稍等。",
};

function friendly(detail, status) {
  if (!detail) return status >= 500 ? "服务暂时不可用，请稍后重试。" : "请求没有成功。";
  if (typeof detail === "string") return FRIENDLY[detail] || detail;
  if (detail.error) return detail.error;
  return "请求没有成功。";
}

async function request(path, { method = "GET", body, retries = 3, signal } = {}) {
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(`${BASE}${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal,
      });
      if (!response.ok) {
        let payload = null;
        try {
          payload = await response.json();
        } catch {
          payload = null;
        }
        const message = friendly(payload?.detail ?? payload, response.status);
        // 4xx 是客户端问题，重试没有意义
        if (response.status < 500) throw new ApiError(message, response.status);
        lastError = new ApiError(message, response.status);
      } else {
        return response.status === 204 ? {} : await response.json();
      }
    } catch (error) {
      if (error instanceof ApiError && error.status < 500) throw error;
      if (error?.name === "AbortError") throw error;
      lastError =
        error instanceof ApiError
          ? error
          : new ApiError("连不上本地服务，请确认启动窗口还在运行。", 0);
    }
    if (attempt < retries) {
      await new Promise((resolve) => setTimeout(resolve, 400 * (attempt + 1)));
    }
  }
  throw lastError ?? new ApiError("请求失败。", 0);
}

function toQuery(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "" || value === false) return;
    search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  health: () => request("/api/health"),

  /** 通知列表（可选筛选）。includeBody=false 时体积更小，正文走详情接口。 */
  notices: (params = {}) => request(`/api/notices${toQuery(params)}`),

  notice: (id) => request(`/api/notices/${encodeURIComponent(id)}`),

  related: (id) => request(`/api/related/${encodeURIComponent(id)}`),

  /** 全文搜索：标题 / 正文 / 附件 / 来源 / 对象 / 材料名 / 历届 */
  search: (q, includeHistory = false, limit = 100) =>
    request(`/api/search${toQuery({ q, include_history: includeHistory, limit })}`),

  facets: () => request("/api/facets"),

  sources: () => request("/api/sources"),

  addSource: (payload) => request("/api/sources", { method: "POST", body: payload }),

  removeSource: (id) =>
    request(`/api/sources/${encodeURIComponent(id)}`, { method: "DELETE" }),

  scan: () => request("/api/scan", { method: "POST" }),

  scanStatus: () => request("/api/scan/status"),

  calendar: (month = "") => request(`/api/calendar${toQuery({ month })}`),

  forecast: (source) => request(`/api/forecast${toQuery({ source })}`),

  community: {
    list: () => request("/api/community/posts"),
    draft: (payload) =>
      request("/api/community/posts", { method: "POST", body: payload }),
    moderate: (password) =>
      request("/api/community/moderate", { method: "POST", body: { password } }),
    approve: (id, password) =>
      request(`/api/community/posts/${encodeURIComponent(id)}/approve`, {
        method: "POST",
        body: { password },
      }),
    reject: (id, password) =>
      request(`/api/community/posts/${encodeURIComponent(id)}/reject`, {
        method: "POST",
        body: { password },
      }),
    remove: (id, password) =>
      request(`/api/community/posts/${encodeURIComponent(id)}`, {
        method: "DELETE",
        body: { password },
      }),
  },

  feedback: (payload) => request("/api/feedback", { method: "POST", body: payload }),

  backup: () => request("/api/backup", { method: "POST" }),

  backups: () => request("/api/backups"),

  exportData: () => request("/api/export"),

  importData: (payload) => request("/api/import", { method: "POST", body: payload }),
};

export { toQuery };
