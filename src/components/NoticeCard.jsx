/**
 * 通知卡片（需求 7）。
 *
 * 默认只显示：官方原标题、发布时间、截止时间、收藏、加入待办、分享、不感兴趣、展开。
 * 展开后显示：一句话摘要、适用对象、通知类型、预计准备时间、其它必要概要。
 * 标题一律使用官方原标题，不拼接日期、栏目或摘要。
 */

import { Bookmark, Check, ChevronDown, ChevronRight, Clock3, EyeOff, ListTodo, Share2 } from "lucide-react";
import { useI18n } from "../lib/i18n.js";
import { daysLeft, formatDate, formatCNDate, resolveDisplayDate, urgencyClass } from "../lib/utils.js";

export default function NoticeCard({
  notice,
  expanded,
  onToggle,
  onOpen,
  onFavorite,
  onTodo,
  onShare,
  onHide,
  favorite = false,
  inTodo = false,
  reasons = [],
  cross = false,
  hideOrgCampus = false,
}) {
  const { t, lang } = useI18n();
  const actionDate = notice.next_action || notice.deadline;
  const left = daysLeft(actionDate);
  const audience = (notice.audience || []).slice(0, 4).join(" / ");

  return (
    <article className={`notice-card ${expanded ? "expanded" : ""} ${cross ? "cross" : ""}`}>
      <div className="notice-head">
        <button
          type="button"
          className="expand-button"
          onClick={onToggle}
          aria-label={expanded ? t("action.collapse") : t("action.expand")}
          aria-expanded={expanded}
        >
          {expanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </button>

        <div className="notice-body">
          <button type="button" className="notice-title" onClick={onOpen}>
            {notice.title}
          </button>
          {/* 需求5：在标题下方标注来源单位，所有页面都显示 */}
          {(notice.org_unit || notice.source_name || notice.source) && (
            <span className="notice-source-tag">
              {notice.org_unit || notice.source_name || notice.source}
            </span>
          )}
          <div className="notice-times">
            {(() => {
              const display = resolveDisplayDate(notice);
              return (
                <span className="time-item">
                  <span className="time-label">{t(display.labelKey)}</span>
                  {display.date ? formatCNDate(display.date) : ""}
                </span>
              );
            })()}
            {notice.deadline ? (
              <span className={`time-item deadline ${urgencyClass(left)}`}>
                <Clock3 size={13} />
                <span className="time-label">{t("notice.deadline")}</span>
                {formatDate(notice.deadline, lang)}
                {left !== null && left >= 0 && <em>{t("notice.daysLeft", { n: left })}</em>}
                {left !== null && left < 0 && <em>{t("notice.expired")}</em>}
              </span>
            ) : null}
            {cross && <span className="cross-tag">{t("recommend.explore")}</span>}
          </div>

          {expanded && (
            <div className="notice-extra">
              <p className="notice-summary">{notice.summary || t("detail.noBody")}</p>
              <div className="extra-grid">
                <div>
                  <span>{notice.audience?.length ? "适用对象" : ""}</span>
                  <strong>{audience || t("notice.audienceUnknown")}</strong>
                </div>
                <div>
                  <span>通知类型</span>
                  <strong>{(notice.categories || []).join(" / ") || "待分类"}</strong>
                </div>
                <div>
                  <span>{t("notice.prep")}</span>
                  <strong>{notice.prep_minutes ? `${notice.prep_minutes} 分钟` : "—"}</strong>
                </div>
                <div>
                  <span>{t("notice.attachment")}</span>
                  <strong>{notice.attachment_count || 0} 个</strong>
                </div>
                <div>
                  <span>来源</span>
                  <strong>{notice.source}</strong>
                </div>
                <div>
                  <span>{hideOrgCampus ? "地点" : "地点 / 校区"}</span>
                  <strong>
                    {hideOrgCampus
                      ? notice.location || "详见原文"
                      : notice.campus || notice.location || "详见原文"}
                  </strong>
                </div>
              </div>
              {reasons.length > 0 && (
                <div className="reasons">
                  <span>{t("recommend.why")}</span>
                  <ul>
                    {reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}
              <button type="button" className="text-button" onClick={onOpen}>
                {t("notice.openDetail")} <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>

        <div className="notice-actions">
          <button
            type="button"
            className={`icon-button ${favorite ? "selected" : ""}`}
            onClick={onFavorite}
            title={t("notice.favorite")}
            aria-label={t("notice.favorite")}
          >
            <Bookmark size={17} fill={favorite ? "currentColor" : "none"} />
          </button>
          <button
            type="button"
            className={`icon-button ${inTodo ? "selected" : ""}`}
            onClick={onTodo}
            title={t("notice.todo")}
            aria-label={t("notice.todo")}
          >
            {inTodo ? <Check size={17} /> : <ListTodo size={17} />}
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={onShare}
            title={t("notice.share")}
            aria-label={t("notice.share")}
          >
            <Share2 size={17} />
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={onHide}
            title={t("notice.dislike")}
            aria-label={t("notice.dislike")}
          >
            <EyeOff size={17} />
          </button>
        </div>
      </div>
    </article>
  );
}
