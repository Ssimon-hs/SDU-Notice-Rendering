/**
 * 为你推荐（需求 4）。
 * 每条说明「为什么推荐给你」，支持不感兴趣、调整推荐范围，
 * 并保留跨学院 / 跨兴趣内容；推荐不会自动加入待办。
 */

import { useMemo, useState } from "react";
import { Compass, Info } from "lucide-react";
import NoticeCard from "../components/NoticeCard.jsx";
import { Empty } from "../components/Shared.jsx";
import { useI18n } from "../lib/i18n.js";
import { SCOPES, recommend } from "../lib/recommend.js";
import { useStore } from "../lib/store.jsx";

export default function Recommended({ notices, onOpen, onToast }) {
  const { t } = useI18n();
  const { state, toggleFavorite, addTodo, hideNotice, inTodo } = useStore();
  const [scope, setScope] = useState("balanced");
  const [expanded, setExpanded] = useState(null);

  const context = useMemo(
    () => ({
      profile: state.profile,
      favorites: state.favorites,
      todos: state.todos,
      searches: state.searches,
      reads: state.reads,
      hidden: state.hidden,
    }),
    [state],
  );

  const items = useMemo(() => recommend(notices, context, { scope, limit: 12 }), [
    notices,
    context,
    scope,
  ]);

  const share = async (notice) => {
    const text = `${notice.title}\n${notice.official_url || ""}`;
    try {
      await navigator.clipboard.writeText(text);
      onToast?.("已复制标题和官方链接");
    } catch {
      onToast?.("复制失败，请手动复制链接");
    }
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.recommend")}</span>
          <h1>{t("nav.recommend")}</h1>
          <p>
            {t("recommend.noAddTodo")}；{state.profile ? "依据你的资料、收藏、待办和搜索记录" : "你还没有填写资料，当前为通用推荐"}
          </p>
        </div>
        <div className="scope-picker">
          <label>{t("recommend.scope")}</label>
          <select value={scope} onChange={(event) => setScope(event.target.value)}>
            {SCOPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      {!state.profile && (
        <div className="banner info">
          <Info size={15} />
          <span>填写用户画像可以让推荐更准确，在系统设置里可以重新填写。</span>
        </div>
      )}

      <div className="notice-list">
        {items.map((notice) => (
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
            onHide={() => {
              hideNotice(notice.id);
              onToast?.(`已减少这类内容：${notice.title.slice(0, 18)}…`);
            }}
            favorite={Boolean(state.favorites[notice.id])}
            inTodo={inTodo(notice.id)}
            reasons={notice.reasons}
            cross={notice.cross}
          />
        ))}
      </div>

      {!items.length && (
        <Empty
          icon={<Compass size={24} />}
          title={t("state.empty")}
          hint="试着把推荐范围调成「均衡」或在系统设置里补充资料。"
        />
      )}

      <p className="page-note">
        <Info size={14} />
        {t("recommend.exploreHint")}
      </p>
    </div>
  );
}
