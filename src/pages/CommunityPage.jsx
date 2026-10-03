/**
 * 校园社区。
 * 新的投稿模型：
 * - 任何人点击「投稿 / 征集」即可填写草稿并提交，状态为 pending（待审核），暂存到管理员审核目录；
 * - 管理员点击「管理员审核」，输入管理员密码进入审核台，对待审核投稿执行通过(✓)/驳回(✗)；
 *   密码由后端环境变量 COMMUNITY_ADMIN_PASSWORD 校验，前端不持有任何密码；
 * - 通过后的帖子状态为 published，对所有用户可见。社区内容优先从后端 /api/community/posts 加载。
 */

import { useEffect, useState } from "react";
import { Check, MessageSquare, ShieldCheck, Sparkles, Trash2, Users, X } from "lucide-react";
import { Banner, Section } from "../components/Shared.jsx";
import { useI18n } from "../lib/i18n.js";
import { api } from "../lib/api.js";

const SAMPLE_POSTS = [
  {
    id: "p1",
    title: "创新创业大赛组队经验：如何找到靠谱队友",
    author: "山大同学",
    tag: "竞赛",
    excerpt: "优先找能稳定输出的队友，而不是履历最漂亮的。报名前把分工写清楚，后期少很多摩擦。",
    at: "2026-09-28",
  },
  {
    id: "p2",
    title: "奖学金材料清单整理（含常见退回原因）",
    author: "山大同学",
    tag: "奖学金",
    excerpt: "成果证明要盖章、成绩单要最新版本，缺一项就会被退回。建议提前一周准备。",
    at: "2026-09-21",
  },
  {
    id: "p3",
    title: "跨校区听讲座的通勤时间安排",
    author: "山大同学",
    tag: "讲座",
    excerpt: "中心校区到兴隆山校区班车约 40 分钟，讲座开始前 20 分钟到场比较稳妥。",
    at: "2026-09-15",
  },
];

const TAG_OPTIONS =  ["竞赛", "奖学金", "讲座", "征集", "经验", "其他"];

// 任何人可投稿的草稿弹窗
function DraftModal({ onClose, onToast }) {
  const { t } = useI18n();
  const [title, setTitle] = useState("");
  const [tag, setTag] = useState("经验");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!title.trim() || !content.trim()) {
      setError("标题和内容都不能为空");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await api.community.draft({ title: title.trim(), tag, content: content.trim() });
      onToast?.(t("community.submitted"));
      setTitle("");
      setContent("");
      setTag("经验");
    } catch (e) {
      onToast?.(e.message || "提交失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3 style={{ margin: 0 }}>投稿 / 征集</h3>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>{t("community.draftHint")}</p>
          <label style={{ fontSize: 13 }}>{t("community.postTitle")}</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} className="text-input" placeholder="一句话说清主题" />
          <label style={{ fontSize: 13 }}>{t("community.postTag")}</label>
          <select value={tag} onChange={(e) => setTag(e.target.value)} className="text-input">
            {TAG_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
          <label style={{ fontSize: 13 }}>{t("community.postContent")}</label>
          <textarea value={content} onChange={(e) => setContent(e.target.value)} className="text-input" rows={4} placeholder="经验、链接、注意事项…" />
          {error && <span style={{ color: "var(--danger, #d33)", fontSize: 12 }}>{error}</span>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="primary-button" onClick={submit} disabled={busy}>
              {busy ? "提交中…" : t("community.submit")}
            </button>
            <button type="button" className="text-button" onClick={onClose}>{t("community.done")}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// 管理员审核台：凭密码进入，对待审核投稿通过/驳回
function AdminModal({ onClose, onToast }) {
  const { t } = useI18n();
  const [pwd, setPwd] = useState("");
  const [pwdError, setPwdError] = useState(false);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState([]);
  const [published, setPublished] = useState([]);
  const [busyId, setBusyId] = useState("");

  const refresh = async (password) => {
    const r = await api.community.moderate(password);
    setPending(r.pending || []);
    setPublished(r.published || []);
  };

  const verify = async () => {
    // 密码不在前端保存或比对，统一交由后端环境变量校验，错误由接口返回。
    if (!pwd) {
      setPwdError(true);
      return;
    }
    try {
      await refresh(pwd);
      setPwdError(false);
      setOpen(true);
    } catch (e) {
      setPwdError(true);
    }
  };

  const act = async (id, fn, okMsg) => {
    setBusyId(id);
    try {
      await fn(id, pwd);
      await refresh(pwd);
      onToast?.(okMsg);
    } catch (e) {
      onToast?.(e.message || "操作失败");
    } finally {
      setBusyId("");
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3 style={{ margin: 0 }}>{t("community.moderation")}</h3>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭">×</button>
        </div>

        {!open ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <label style={{ fontSize: 13 }}>{t("community.adminPwd")}</label>
            <input
              type="password"
              value={pwd}
              autoFocus
              onChange={(e) => { setPwd(e.target.value); setPwdError(false); }}
              onKeyDown={(e) => e.key === "Enter" && verify()}
              className="text-input"
              placeholder="••••••"
            />
            {pwdError && <span style={{ color: "var(--danger, #d33)", fontSize: 12 }}>{t("community.wrongPwd")}</span>}
            <button type="button" className="primary-button" onClick={verify}>{t("community.verify")}</button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <span style={{ fontSize: 12, color: "var(--accent, #c41e1e)" }}>{t("community.adminOn")}</span>

            <div>
              <strong style={{ fontSize: 13 }}>{t("community.pending")}（{pending.length}）</strong>
              {pending.length === 0 ? (
                <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--muted)" }}>{t("community.noPending")}</p>
              ) : (
                <div className="mod-list">
                  {pending.map((p) => (
                    <div key={p.id} className="mod-item">
                      <div className="mod-item-main">
                        <strong>{p.title}</strong>
                        <span className="post-tag">{p.tag}</span>
                        <p>{p.content}</p>
                      </div>
                      <div className="mod-actions">
                        <button type="button" className="approve-btn" disabled={busyId === p.id} onClick={() => act(p.id, api.community.approve, t("community.approve") + " ✓")}>
                          <Check size={15} /> {t("community.approve")}
                        </button>
                        <button type="button" className="reject-btn" disabled={busyId === p.id} onClick={() => act(p.id, api.community.reject, t("community.reject") + " ✗")}>
                          <X size={15} /> {t("community.reject")}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {published.length > 0 && (
              <div>
                <strong style={{ fontSize: 13 }}>{t("community.published")}（{published.length}）</strong>
                <div className="mod-list">
                  {published.map((p) => (
                    <div key={p.id} className="mod-item">
                      <div className="mod-item-main">
                        <strong>{p.title}</strong>
                        <span className="post-tag">{p.tag}</span>
                      </div>
                      <div className="mod-actions">
                        <button type="button" className="reject-btn" disabled={busyId === p.id} onClick={() => act(p.id, api.community.remove, t("community.delete"))}>
                          <Trash2 size={14} /> {t("community.delete")}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function CommunityPage({ onToast }) {
  const { t } = useI18n();
  const [posts, setPosts] = useState([]);
  const [loadingPosts, setLoadingPosts] = useState(true);
  const [draftOpen, setDraftOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    api.community
      .list()
      .then((r) => { if (alive) setPosts(r.items || []); })
      .catch(() => {})
      .finally(() => { if (alive) setLoadingPosts(false); });
    return () => { alive = false; };
  }, []);

  const displayPosts = [...posts, ...SAMPLE_POSTS];

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.community")}</span>
          <h1>{t("community.title")}</h1>
          <p>{t("community.subtitle")}</p>
        </div>
        <div className="community-actions">
          <button type="button" className="primary-button" onClick={() => setDraftOpen(true)}>
            <MessageSquare size={15} /> 投稿 / 征集
          </button>
          <button type="button" className="ghost-button" onClick={() => setAdminOpen(true)}>
            <ShieldCheck size={15} /> {t("community.admin")}
          </button>
        </div>
      </header>

      <div className="community-slogan">
        <Sparkles size={18} />
        <strong>{t("community.slogan")}</strong>
      </div>

      <Banner tone="info">
        <ShieldCheck size={15} />
        <span>{t("community.review")}。</span>
      </Banner>

      <Section title="社区内容">
        {loadingPosts ? (
          <p className="loading-line">…</p>
        ) : (
          <div className="post-list">
            {displayPosts.map((post) => (
              <article key={post.id} className="post-card">
                <div className="post-head">
                  <span className="post-tag">{post.tag}</span>
                  <strong>{post.title}</strong>
                </div>
                <p>{post.excerpt || post.content}</p>
                <div className="post-foot">
                  <span>
                    <Users size={13} /> {post.author} · {post.at}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </Section>

      <Section title="投稿方式">
        <ol className="steps">
          <li><span>1</span> 点击「投稿 / 征集」填写内容并提交，帖子暂存为待审核草稿</li>
          <li><span>2</span> 管理员点击「管理员审核」输入密码，在审核台对待审核投稿执行通过(✓)或驳回(✗)</li>
          <li><span>3</span> 通过后的帖子对所有同学可见；驳回的草稿将被移除</li>
        </ol>
      </Section>

      {draftOpen && <DraftModal onClose={() => setDraftOpen(false)} onToast={onToast} />}
      {adminOpen && <AdminModal onClose={() => setAdminOpen(false)} onToast={onToast} />}
    </div>
  );
}
