/**
 * 全部通知（需求 5）。
 * 大型筛选检索页：14 项筛选条件、保存与自定义筛选、默认隐藏已截止、
 * 显示收录总数、当前通知下方可关联往年活动。
 */

import { useEffect, useMemo, useState } from "react";
import { Bookmark, Check, Filter, Search, Share2, X } from "lucide-react";
import NoticeCard from "../components/NoticeCard.jsx";
import { Chip, Empty } from "../components/Shared.jsx";
import { useI18n } from "../lib/i18n.js";
import { scoreNotice } from "../lib/recommend.js";
import { useStore } from "../lib/store.jsx";
import { counter, daysLeft, isExpired, unique } from "../lib/utils.js";
import { SOURCE_GROUPS } from "../data/sourceOrder.js";

const EMPTY_FILTER = {
  source: "",
  category: "",
  audience: "",
  needsSignup: "",
  needsMaterial: "",
  online: "",
  hasAttachment: "",
  deadlineState: "",
  prepMax: "",
  relevanceMin: "",
  dateFrom: "",
  dateTo: "",
  sort: "published",
  showExpired: false,
};

const SORTS = [
  ["published", "发布时间（新→旧）"],
  ["deadline", "截止时间（近→远）"],
  ["relevant", "相关度（高→低）"],
  ["source", "信息来源"],
];

export default function AllNotices({ notices, onOpen, onToast }) {
  const { t } = useI18n();
  const { state, patchSettings, toggleFavorite, addTodo, hideNotice, inTodo } = useStore();
  const [filter, setFilter] = useState(EMPTY_FILTER);
  const [expanded, setExpanded] = useState(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [filterName, setFilterName] = useState("");

  useEffect(() => {
    setFilter((current) => ({ ...current, showExpired: state.settings.showExpired }));
  }, [state.settings.showExpired]);

  const facets = useMemo(
    () => ({
      sources: counter(notices, "source"),
      categories: counter(notices, "categories"),
      audience: counter(notices, "audience"),
    }),
    [notices],
  );

  const context = useMemo(
    () => ({
      profile: state.profile,
      favorites: state.favorites,
      todos: state.todos,
      searches: state.searches,
      reads: state.reads,
      hidden: [],
    }),
    [state],
  );

  const filtered = useMemo(() => {
    const rows = notices.filter((notice) => {
      if (!filter.showExpired && isExpired(notice)) return false;
      if (filter.showExpired && filter.deadlineState !== "expired" && isExpired(notice)) {
        // 勾选显示已截止时才保留
      }
      if (state.hidden.includes(notice.id)) return false;
      if (filter.source && notice.source !== filter.source) return false;
      if (filter.category && !(notice.categories || []).includes(filter.category)) return false;
      if (filter.audience && !(notice.audience || []).includes(filter.audience)) return false;
      if (filter.needsSignup && (notice.needs_signup ? "yes" : "no") !== filter.needsSignup) {
        return false;
      }
      if (filter.needsMaterial && (notice.needs_material ? "yes" : "no") !== filter.needsMaterial) {
        return false;
      }
      if (filter.online) {
        const flag = notice.online;
        if (flag === null || flag === undefined) return false;
        if ((flag ? "yes" : "no") !== filter.online) return false;
      }
      if (filter.hasAttachment) {
        const has = Boolean(notice.attachment_count || notice.attachments?.length);
        if ((has ? "yes" : "no") !== filter.hasAttachment) return false;
      }
      if (filter.deadlineState) {
        const left = daysLeft(notice.next_action || notice.deadline);
        if (filter.deadlineState === "active" && (left === null || left < 0)) return false;
        if (filter.deadlineState === "soon" && (left === null || left < 0 || left > 7)) return false;
        if (filter.deadlineState === "expired" && (left === null || left >= 0)) return false;
        if (filter.deadlineState === "unknown" && left !== null) return false;
      }
      if (filter.prepMax && (notice.prep_minutes || 0) > Number(filter.prepMax)) return false;
      if (filter.dateFrom && (notice.published_at || "") < filter.dateFrom) return false;
      if (filter.dateTo && (notice.published_at || "") > filter.dateTo) return false;
      return true;
    });

    const scored = rows.map((notice) => ({
      notice,
      score: scoreNotice(notice, context).score,
    }));
    if (filter.relevanceMin) {
      const min = Number(filter.relevanceMin);
      return scored
        .filter((item) => item.score >= min)
        .sort((a, b) => b.score - a.score)
        .map((item) => item.notice);
    }
    if (filter.sort === "deadline") {
      scored.sort((a, b) =>
        String(a.notice.next_action || a.notice.deadline || "9999").localeCompare(
          String(b.notice.next_action || b.notice.deadline || "9999"),
        ),
      );
      return scored.map((item) => item.notice);
    }
    if (filter.sort === "relevant") {
      scored.sort((a, b) => b.score - a.score);
      return scored.map((item) => item.notice);
    }
    if (filter.sort === "source") {
      scored.sort((a, b) => String(a.notice.source).localeCompare(String(b.notice.source)));
      return scored.map((item) => item.notice);
    }
    scored.sort((a, b) =>
      String(b.notice.published_at || "").localeCompare(String(a.notice.published_at || "")),
    );
    return scored.map((item) => item.notice);
  }, [notices, filter, context, state.hidden]);

  const activeCount = Object.keys(filter).filter((key) => {
    if (key === "sort" || key === "showExpired") return false;
    return Boolean(filter[key]);
  }).length;

  const saveFilter = () => {
    const name = filterName.trim() || `筛选 ${state.settings.savedFilters.length + 1}`;
    patchSettings({ savedFilters: [...state.settings.savedFilters, { name, filter }] });
    setFilterName("");
    onToast?.(`已保存筛选「${name}」`);
  };

  const share = async (notice) => {
    try {
      await navigator.clipboard.writeText(`${notice.title}\n${notice.official_url || ""}`);
      onToast?.("已复制标题和官方链接");
    } catch {
      onToast?.("复制失败，请手动复制链接");
    }
  };

  return (
    <div className="page all-page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.all")}</span>
          <h1>{t("all.title")}</h1>
          <p>
            {t("all.subtitle")} · {t("all.total", { n: notices.length })}
          </p>
        </div>
        <button
          type="button"
          className="ghost-button"
          onClick={() => setPanelOpen((value) => !value)}
        >
          <Filter size={15} /> {t("all.filter")}
          {activeCount ? <b>{activeCount}</b> : null}
        </button>
      </header>

      {panelOpen && (
        <div className="filter-panel">
          <div className="filter-grid">
            <label>
              <span>{t("filter.source")}</span>
              <select value={filter.source} onChange={(e) => setFilter({ ...filter, source: e.target.value })}>
                <option value="">全部</option>
                {(() => {
                  const countMap = new Map(facets.sources.map((item) => [item.value, item.count]));
                  return SOURCE_GROUPS.map(([scope, names]) => {
                    const items = names
                      .map((name) => ({ name, count: countMap.get(name) || 0 }))
                      .filter((item) => item.count > 0);
                    if (!items.length) return null;
                    return (
                      <optgroup key={scope} label={`${scope}（${items.length}）`}>
                        {items.map((item) => (
                          <option key={item.name} value={item.name}>
                            {item.name}（{item.count}）
                          </option>
                        ))}
                      </optgroup>
                    );
                  });
                })()}
              </select>
            </label>

            <label>
              <span>{t("filter.category")}</span>
              <select value={filter.category} onChange={(e) => setFilter({ ...filter, category: e.target.value })}>
                <option value="">全部</option>
                {facets.categories.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.value}（{item.count}）
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>{t("filter.audience")}</span>
              <select value={filter.audience} onChange={(e) => setFilter({ ...filter, audience: e.target.value })}>
                <option value="">全部</option>
                {facets.audience.slice(0, 40).map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.value}（{item.count}）
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>{t("filter.signup")}</span>
              <select value={filter.needsSignup} onChange={(e) => setFilter({ ...filter, needsSignup: e.target.value })}>
                <option value="">不限</option>
                <option value="yes">需要报名</option>
                <option value="no">不需要报名</option>
              </select>
            </label>

            <label>
              <span>{t("filter.material")}</span>
              <select value={filter.needsMaterial} onChange={(e) => setFilter({ ...filter, needsMaterial: e.target.value })}>
                <option value="">不限</option>
                <option value="yes">需要材料</option>
                <option value="no">不需要材料</option>
              </select>
            </label>

            <label>
              <span>{t("filter.online")}</span>
              <select value={filter.online} onChange={(e) => setFilter({ ...filter, online: e.target.value })}>
                <option value="">不限</option>
                <option value="yes">线上</option>
                <option value="no">线下</option>
              </select>
            </label>

            <label>
              <span>{t("filter.attachment")}</span>
              <select value={filter.hasAttachment} onChange={(e) => setFilter({ ...filter, hasAttachment: e.target.value })}>
                <option value="">不限</option>
                <option value="yes">有附件</option>
                <option value="no">无附件</option>
              </select>
            </label>

            <label>
              <span>{t("filter.deadlineState")}</span>
              <select value={filter.deadlineState} onChange={(e) => setFilter({ ...filter, deadlineState: e.target.value })}>
                <option value="">不限</option>
                <option value="active">未截止</option>
                <option value="soon">7 天内截止</option>
                <option value="expired">已截止</option>
                <option value="unknown">无截止时间</option>
              </select>
            </label>

            <label>
              <span>{t("filter.prep")}</span>
              <select value={filter.prepMax} onChange={(e) => setFilter({ ...filter, prepMax: e.target.value })}>
                <option value="">不限</option>
                <option value="15">15 分钟内</option>
                <option value="60">1 小时内</option>
                <option value="180">3 小时内</option>
                <option value="600">不限时长</option>
              </select>
            </label>

            <label>
              <span>{t("filter.relevance")}</span>
              <select value={filter.relevanceMin} onChange={(e) => setFilter({ ...filter, relevanceMin: e.target.value })}>
                <option value="">不限</option>
                <option value="40">≥40</option>
                <option value="60">≥60</option>
                <option value="80">≥80</option>
              </select>
            </label>

            <label>
              <span>{t("filter.published")}</span>
              <div className="range-row">
                <input
                  type="date"
                  value={filter.dateFrom}
                  onChange={(e) => setFilter({ ...filter, dateFrom: e.target.value })}
                />
                <span>→</span>
                <input
                  type="date"
                  value={filter.dateTo}
                  onChange={(e) => setFilter({ ...filter, dateTo: e.target.value })}
                />
              </div>
            </label>

            <label>
              <span>{t("filter.sort")}</span>
              <select value={filter.sort} onChange={(e) => setFilter({ ...filter, sort: e.target.value })}>
                {SORTS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="filter-actions">
            <label className="inline-check">
              <input
                type="checkbox"
                checked={filter.showExpired}
                onChange={(e) => {
                  setFilter({ ...filter, showExpired: e.target.checked });
                  patchSettings({ showExpired: e.target.checked });
                }}
              />
              {filter.showExpired ? t("all.showExpired") : t("all.hideExpired")}
            </label>
            <button type="button" className="small-button" onClick={() => setFilter(EMPTY_FILTER)}>
              {t("all.clear")}
            </button>
            <input
              value={filterName}
              onChange={(e) => setFilterName(e.target.value)}
              placeholder="筛选名称"
            />
            <button type="button" className="small-button" onClick={saveFilter}>
              {t("all.saveFilter")}
            </button>
          </div>

          {state.settings.savedFilters?.length > 0 && (
            <div className="saved-filters">
              <span>{t("all.myFilters")}</span>
              {state.settings.savedFilters.map((item) => (
                <Chip
                  key={item.name}
                  onClick={() => setFilter({ ...EMPTY_FILTER, ...item.filter })}
                >
                  {item.name}
                </Chip>
              ))}
              <button
                type="button"
                className="text-button"
                onClick={() => patchSettings({ savedFilters: [] })}
              >
                清空
              </button>
            </div>
          )}
        </div>
      )}

      <div className="result-bar">
        <span>
          命中 <strong>{filtered.length}</strong> 条 · 共收录 {notices.length} 条
        </span>
        <span className="result-hint">默认隐藏已截止；历史内容只在搜索历届时出现。</span>
      </div>

      <div className="notice-list">
        {filtered.slice(0, 120).map((notice) => (
          <div key={notice.id} className="notice-slot">
            <NoticeCard
              notice={notice}
              expanded={expanded === notice.id}
              hideOrgCampus
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
              onHide={() => {
                hideNotice(notice.id);
                onToast?.("已标记为不感兴趣");
              }}
              favorite={Boolean(state.favorites[notice.id])}
              inTodo={inTodo(notice.id)}
            />
            {expanded === notice.id && (notice.related_ids || []).length > 0 && (
              <div className="related-hint">
                往年 / 相关：
                {notices
                  .filter((item) => (notice.related_ids || []).includes(item.id))
                  .slice(0, 3)
                  .map((item) => (
                    <button key={item.id} type="button" className="text-button" onClick={() => onOpen(item)}>
                      {item.title.slice(0, 28)}…
                    </button>
                  ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {!filtered.length && (
        <Empty
          icon={<Search size={24} />}
          title={t("state.empty")}
          hint="放宽筛选条件，或勾选「显示已截止」扩大范围。"
        />
      )}
    </div>
  );
}
