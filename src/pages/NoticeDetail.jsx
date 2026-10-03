/**
 * 通知正文页（需求 8 / K）。
 *
 * 顺序：官方原标题 → 发布单位 → 发布时间 → 截止时间 → 官方原始链接 →
 * AI 整理结果 → 材料名称和格式 → 办理步骤 → 预计准备时间 → 官方完整正文 →
 * 官方图片表格附件 → 往年同类活动 → 往年公示名单和成果 → 相关社区经验 → 错误反馈。
 */

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Bookmark,
  CalendarPlus,
  Check,
  FileText,
  Image as ImageIcon,
  Link as LinkIcon,
  ListTodo,
  LoaderCircle,
  MessageSquareWarning,
  Paperclip,
} from "lucide-react";
import { Banner, Empty, Section } from "../components/Shared.jsx";
import { api } from "../lib/api.js";
import { useI18n } from "../lib/i18n.js";
import { useStore } from "../lib/store.jsx";
import { daysLeft, formatDate, formatCNDate, resolveDisplayDate, toICS, download, copyText } from "../lib/utils.js";

const TIME_LABELS = {
  signup_start: "报名开始",
  signup_end: "报名截止",
  submit_end: "材料提交截止",
  review_at: "审核 / 评审",
  event_start: "活动开始",
  event_end: "活动结束",
  result_at: "结果公布",
  exam_at: "考试 / 面试",
};

/** 在官方正文里高亮时间、对象、地点、材料（需求 8）。 */
function highlight(text, terms) {
  const cleaned = (text || "").trim();
  if (!cleaned) return null;
  const words = terms.filter(Boolean).slice(0, 40);
  if (!words.length) return cleaned.split("\n").map((line, index) => <p key={index}>{line}</p>);

  const pattern = new RegExp(
    `(${words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
    "g",
  );
  return cleaned.split("\n").map((line, index) => (
    <p key={index}>
      {line.split(pattern).map((part, partIndex) =>
        words.includes(part) ? (
          <mark key={partIndex} className="hl">
            {part}
          </mark>
        ) : (
          <span key={partIndex}>{part}</span>
        ),
      )}
    </p>
  ));
}

export default function NoticeDetail({ noticeId, onBack, onToast, initialNotice = null }) {
  const { t } = useI18n();
  const { state, toggleFavorite, addTodo, inTodo, recordRead } = useStore();
  const [notice, setNotice] = useState(initialNotice);
  const [loading, setLoading] = useState(!initialNotice);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [feedbackSent, setFeedbackSent] = useState(false);

  useEffect(() => {
    let alive = true;
    // 已有缓存对象时先展示它，再由接口补上完整正文
    setLoading(!initialNotice || initialNotice.id !== noticeId);
    setError("");
    api
      .notice(noticeId)
      .then((data) => {
        if (!alive) return;
        setNotice(data);
        recordRead(noticeId);
      })
      .catch((err) => alive && setError(err.message || t("state.offline")))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [noticeId]);

  const highlightTerms = useMemo(() => {
    if (!notice) return [];
    return [
      ...Object.values(notice.times || {}).filter(Boolean),
      ...(notice.audience || []),
      notice.campus,
      notice.location,
      ...(notice.materials || []).map((item) => item.name),
    ];
  }, [notice]);

  if (loading) {
    return (
      <div className="page">
        <p className="loading-line">
          <LoaderCircle className="spin" size={16} /> {t("state.loading")}…
        </p>
      </div>
    );
  }

  if (error || !notice) {
    return (
      <div className="page">
        <button type="button" className="ghost-button" onClick={onBack}>
          <ArrowLeft size={15} /> {t("action.back")}
        </button>
        <Empty title={error || t("state.empty")} />
      </div>
    );
  }

  const organized = notice.organized || {};
  const left = daysLeft(notice.next_action || notice.deadline);
  const times = Object.entries(notice.times || {}).filter(([, value]) => value);

  const addToCalendar = () => {
    const events = times.map(([key, value]) => ({
      date: value,
      title: `${TIME_LABELS[key] || key}：${notice.title}`,
      source: notice.source,
    }));
    if (!events.length) {
      onToast?.("这条通知还没有可写入日历的时间节点");
      return;
    }
    download(`yijian-sdu-${notice.id}.ics`, toICS(events), "text/calendar");
    onToast?.("已导出 .ics，可在系统日历中导入");
  };

  const submitFeedback = async () => {
    if (!feedback.trim()) return;
    try {
      await api.feedback({
        notice_id: notice.id,
        kind: "classification",
        message: feedback.trim(),
      });
      setFeedbackSent(true);
      setFeedback("");
      onToast?.("反馈已保存到本地");
    } catch (err) {
      onToast?.(err.message || "反馈保存失败");
    }
  };

  const materials = notice.materials || [];
  const attachments = notice.attachments || [];
  const images = notice.images || [];
  const related = notice.related || [];
  const pastNotices = related.filter((item) => item.status === "expired" || (item.kind === "通知"));
  const pastResults = related.filter(
    (item) => item.kind === "公示／结果" || (item.categories || []).includes("公示／名单／结果"),
  );

  return (
    <div className="page detail-page">
      <button type="button" className="ghost-button back-button" onClick={onBack}>
        <ArrowLeft size={15} /> {t("action.back")}
      </button>

      <header className="detail-header">
        <span className="eyebrow">{notice.source}</span>
        <h1>{notice.title}</h1>

        <div className="detail-meta">
          <span>
            <strong>{t("detail.org")}</strong> {notice.source_name || notice.source}
          </span>
          {(() => {
            const display = resolveDisplayDate(notice);
            return (
              <span>
                <strong>{t(display.labelKey)}</strong>{" "}
                {display.date ? formatCNDate(display.date) : ""}
              </span>
            );
          })()}
          <span>
            <strong>{t("detail.deadline")}</strong>{" "}
            {notice.deadline ? (
              <>
                {formatDate(notice.deadline)}
                {left !== null && left >= 0 ? `（剩余 ${left} 天）` : "（已截止）"}
              </>
            ) : (
              t("notice.noDeadline")
            )}
          </span>
          {(notice.categories || []).length > 0 && (
            <span>
              <strong>分类</strong> {notice.categories.join(" / ")}
            </span>
          )}
          <span>
            <strong>性质</strong> {notice.kind || "待分类"}
          </span>
        </div>

        <div className="detail-actions">
          <a className="primary-button" href={notice.official_url} target="_blank" rel="noreferrer">
            <LinkIcon size={15} /> {t("notice.official")}
          </a>
          <button
            type="button"
            className={`ghost-button ${state.favorites[notice.id] ? "selected" : ""}`}
            onClick={() => toggleFavorite(notice)}
          >
            <Bookmark size={15} /> {t("notice.favorite")}
          </button>
          <button
            type="button"
            className={`ghost-button ${inTodo(notice.id) ? "selected" : ""}`}
            onClick={() =>
              addTodo({
                noticeId: notice.id,
                title: notice.title,
                deadline: notice.next_action || notice.deadline || "",
                source: notice.source,
                official_url: notice.official_url,
                materials: materials.map((item) => ({ ...item, done: false })),
              })
            }
          >
            <ListTodo size={15} /> {t("notice.todo")}
          </button>
          <button type="button" className="ghost-button" onClick={addToCalendar}>
            <CalendarPlus size={15} /> {t("todo.calendar")}
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={async () => {
              const ok = await copyText(`${notice.title}\n${notice.official_url || ""}`);
              onToast?.(ok ? "已复制链接" : "复制失败");
            }}
          >
            <FileText size={15} /> {t("action.copy")}
          </button>
        </div>
      </header>

      <Banner tone="warn">
        <AlertTriangle size={15} /> {t("detail.officialWins")}
      </Banner>

      <Section
        title={t("detail.ai")}
        extra={<span className="engine-tag">{organized.engine_label || "本地规则整理"}</span>}
      >
        <div className="ai-box">
          <p className="ai-summary">{organized.summary || notice.summary}</p>
          <div className="ai-grid">
            <div>
              <span>适用对象</span>
              <strong>
                {(organized.audience || []).join(" / ") || t("notice.audienceUnknown")}
              </strong>
            </div>
            <div>
              <span>地点 / 校区</span>
              <strong>{notice.campus || notice.location || "详见原文"}</strong>
            </div>
            <div>
              <span>{t("detail.prep")}</span>
              <strong>{notice.prep_minutes ? `${notice.prep_minutes} 分钟` : "—"}</strong>
            </div>
            <div>
              <span>是否需要报名</span>
              <strong>{notice.needs_signup ? "需要" : "不需要"}</strong>
            </div>
          </div>
          {times.length > 0 && (
            <div className="time-table">
              {times.map(([key, value]) => (
                <span key={key} className="time-chip">
                  {TIME_LABELS[key] || key}
                  <strong>{value}</strong>
                </span>
              ))}
            </div>
          )}
          <p className="ai-disclaimer">{organized.disclaimer}</p>
        </div>
      </Section>

      <Section title={t("detail.materials")}>
        {materials.length ? (
          <ul className="material-table">
            {materials.map((item) => (
              <li key={item.name}>
                <Check size={14} />
                <span>{item.name}</span>
                <em>{item.format ? `.${item.format.replace(".", "")}` : "格式见原文"}</em>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">未从正文中识别出明确材料清单，请以官方原文为准。</p>
        )}
        <p className="muted small">
          临近截止时，待办里的材料勾选状态会提醒你还没准备好的部分。
        </p>
      </Section>

      <Section title={t("detail.steps")}>
        <ol className="steps">
          {(notice.steps || ["阅读并核对官方原文"]).map((step, index) => (
            <li key={step}>
              <span>{index + 1}</span>
              {step}
            </li>
          ))}
        </ol>
      </Section>

      <Section title={t("detail.body")}>
        {notice.body_text ? (
          <div className="official-body">{highlight(notice.body_text, highlightTerms)}</div>
        ) : (
          <p className="muted">
            {notice.parse_error || t("detail.noBody")}
            <a href={notice.official_url} target="_blank" rel="noreferrer">
              {" "}
              打开官方原文
            </a>
          </p>
        )}
      </Section>

      <Section title={t("detail.attachments")}>
        {attachments.length ? (
          <ul className="attachment-list">
            {attachments.map((item) => (
              <li key={item.url}>
                <Paperclip size={14} />
                <a href={item.url} target="_blank" rel="noreferrer">
                  {item.name}
                </a>
                {item.kind && <em>.{item.kind}</em>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">这条通知没有检测到附件。</p>
        )}
        {images.length > 0 && (
          <div className="image-grid">
            {images.slice(0, 8).map((src) => (
              <a key={src} href={src} target="_blank" rel="noreferrer">
                <img src={src} alt="官方原文图片" loading="lazy" />
                <span>
                  <ImageIcon size={12} /> 查看原图
                </span>
              </a>
            ))}
          </div>
        )}
      </Section>

      <Section title={t("detail.past")}>
        {pastNotices.length ? (
          <ul className="link-list">
            {pastNotices.map((item) => (
              <li key={item.id}>
                <a href={item.official_url} target="_blank" rel="noreferrer">
                  {item.title}
                </a>
                <span>{item.published_at}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">暂时没有关联到往年同类活动。</p>
        )}
      </Section>

      <Section title={t("detail.pastResult")}>
        {pastResults.length ? (
          <ul className="link-list">
            {pastResults.map((item) => (
              <li key={item.id}>
                <a href={item.official_url} target="_blank" rel="noreferrer">
                  {item.title}
                </a>
                <span>{item.published_at}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">暂时没有关联到往年公示名单或成果。</p>
        )}
      </Section>

      <Section title={t("detail.community")}>
        <div className="community-inline">
          <p className="muted">欢迎到「校园社区」投稿或分享经验，提交后由管理员审核通过即可上墙。</p>
        </div>
      </Section>

      <Section title={t("detail.feedback")}>
        <div className="feedback-box">
          <MessageSquareWarning size={16} />
          <div>
            <p className="muted small">
              分类错了？时间识别不准？写下来，会保存到本地并用于后续修正。
            </p>
            <textarea
              value={feedback}
              onChange={(event) => setFeedback(event.target.value)}
              placeholder="例如：这是讲座不是竞赛 / 截止时间是 10 月 20 日"
            />
            <button type="button" className="small-button" onClick={submitFeedback}>
              {feedbackSent ? "已保存 ✓" : t("action.save")}
            </button>
          </div>
        </div>
      </Section>
    </div>
  );
}
