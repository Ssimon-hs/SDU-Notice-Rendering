/**
 * 搜索（需求 6 / I）。
 * 覆盖：官方标题、正文、PDF/Word/Excel 等附件、发布单位与来源、适用对象、
 * 地点与校区、材料名称、历届通知、历史活动、公示名单与活动结果。
 * 支持自然语言提问、输入建议、错别字纠正；默认只显示未截止内容。
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { History, Search, Sparkles } from "lucide-react";
import NoticeCard from "../components/NoticeCard.jsx";
import { Empty } from "../components/Shared.jsx";
import { api } from "../lib/api.js";
import { useI18n } from "../lib/i18n.js";
import { useStore } from "../lib/store.jsx";

const SUGGESTIONS = [
  "最近有哪些适合我的竞赛？",
  "本周截止的讲座",
  "需要提交材料的奖学金",
  "往年创新创业大赛获奖名单",
  "青岛校区的志愿服务",
  "研究生招生 复试时间",
];

export default function SearchPage({ initialQuery = "", onOpen, onToast }) {
  const { t } = useI18n();
  const { state, toggleFavorite, addTodo, hideNotice, inTodo, recordSearch } = useStore();
  const [query, setQuery] = useState(initialQuery);
  const [includeHistory, setIncludeHistory] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    setQuery(initialQuery);
  }, [initialQuery]);

  const run = async (value, history) => {
    const text = (value || "").trim();
    if (!text) {
      setResult(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api.search(text, history);
      setResult(data);
      recordSearch(text);
    } catch (err) {
      setError(err.message || t("state.offline"));
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!query.trim()) {
      setResult(null);
      return undefined;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => run(query, includeHistory), 350);
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, includeHistory]);

  const recent = useMemo(() => state.searches.slice(0, 6), [state.searches]);

  const share = async (notice) => {
    try {
      await navigator.clipboard.writeText(`${notice.title}\n${notice.official_url || ""}`);
      onToast?.("已复制标题和官方链接");
    } catch {
      onToast?.("复制失败，请手动复制链接");
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.search")}</span>
          <h1>{t("nav.search")}</h1>
          <p>{t("search.scope")}：标题、正文、附件、发布单位、适用对象、地点、材料名称</p>
        </div>
      </header>

      <div className="search-hero">
        <div className="search-box big">
          <Search size={19} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("search.placeholder")}
          />
          {query && (
            <button type="button" className="icon-button tiny" onClick={() => setQuery("")}>
              ×
            </button>
          )}
        </div>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={includeHistory}
            onChange={(event) => setIncludeHistory(event.target.checked)}
          />
          {t("search.history")}
        </label>
      </div>

      {!query && (
        <div className="suggestions">
          <span>
            <Sparkles size={14} /> 可以这样问：
          </span>
          {SUGGESTIONS.map((item) => (
            <button key={item} type="button" className="chip" onClick={() => setQuery(item)}>
              {item}
            </button>
          ))}
        </div>
      )}

      {!query && recent.length > 0 && (
        <div className="suggestions">
          <span>
            <History size={14} /> 最近搜索：
          </span>
          {recent.map((item) => (
            <button key={item.at + item.q} type="button" className="chip" onClick={() => setQuery(item.q)}>
              {item.q}
            </button>
          ))}
        </div>
      )}

      {loading && <p className="loading-line">{t("state.loading")}…</p>}
      {error && <div className="banner error">{error}</div>}

      {result && (
        <>
          <div className="result-bar">
            <span>
              {result.query ? `“${result.query}”` : ""} 命中 <strong>{result.total}</strong> 条
              {result.history_included ? " · 含历届与历史资料" : " · 默认只显示未截止"}
            </span>
            {result.correction && <span className="result-hint">{result.correction}</span>}
          </div>

          <div className="notice-list">
            {result.items.map((notice) => (
              <NoticeCard
                key={notice.id}
                notice={notice}
                expanded={expanded === notice.id}
                onToggle={() => setExpanded(expanded === notice.id ? null : notice.id)}
                onOpen={() => onOpen(notice)}
                onFavorite={() => toggleFavorite(notice)}
                onTodo={() =>
                  addTodo({
                    noticeId: notice.id,
                    title: notice.title,
                    deadline: notice.next_action || notice.deadline || "",
                    source: notice.source,
                    official_url: notice.official_url,
                    materials: (notice.materials || []).map((item) => ({ ...item, done: false })),
                  })
                }
                onShare={() => share(notice)}
                onHide={() => hideNotice(notice.id)}
                favorite={Boolean(state.favorites[notice.id])}
                inTodo={inTodo(notice.id)}
              />
            ))}
          </div>

          {!result.items.length && (
            <Empty
              icon={<Search size={24} />}
              title={t("search.empty")}
              hint={`${t("search.searched")} ${result.sources.slice(0, 12).join("、") || "（暂无来源）"}。也可以勾选「${t("search.history")}」再试。`}
            />
          )}
        </>
      )}
    </div>
  );
}
