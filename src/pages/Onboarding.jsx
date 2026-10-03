/**
 * 首次使用引导（需求 2）。
 * 左侧：产品目的、由来、作者介绍；右侧：资料填写、进度、返回上一步、画像预览、暂时跳过。
 */

import { useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Sparkles, UserRound } from "lucide-react";
import { Field, Progress } from "../components/Shared.jsx";
import { useI18n } from "../lib/i18n.js";

const IDENTITIES = ["本科生", "研究生", "博士生", "教职工", "其他"];
const GRADES = ["2026级", "2025级", "2024级", "2023级", "2022级"];
const CAMPUSES = [
  "中心校区",
  "洪家楼校区",
  "趵突泉校区",
  "千佛山校区",
  "兴隆山校区",
  "软件园校区",
  "青岛校区",
  "威海校区",
];
const INTERESTS = [
  "竞赛",
  "科研",
  "讲座",
  "奖学金",
  "保研",
  "考研",
  "实习",
  "就业",
  "志愿服务",
  "社会实践",
  "国际交流",
  "文体活动",
];
const GOALS = ["保研", "考研", "拿奖学金", "参加竞赛", "找实习", "做科研", "出国交流", "充实自己"];
const DEADLINE_PREFS = ["提前一周提醒", "提前三天提醒", "提前一天提醒", "只在当天提醒"];

const STEPS = [
  { title: "你是谁", keys: ["identity", "college", "major", "grade", "campus"] },
  { title: "你在做什么", keys: ["research", "interests", "goals"] },
  { title: "你想看到什么", keys: ["keywords", "avoid", "deadlinePref", "nickname"] },
];

const ALL_KEYS = STEPS.flatMap((step) => step.keys);

const EMPTY = {
  identity: "",
  college: "",
  major: "",
  grade: "",
  campus: "",
  research: "",
  interests: [],
  goals: [],
  keywords: [],
  avoid: [],
  deadlinePref: "",
  nickname: "",
};

export default function Onboarding({ onFinish, onSkip }) {
  const { t } = useI18n();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(EMPTY);
  const [showPreview, setShowPreview] = useState(false);

  const filled = useMemo(
    () =>
      ALL_KEYS.filter((key) => {
        const value = form[key];
        return Array.isArray(value) ? value.length > 0 : Boolean(String(value || "").trim());
      }),
    [form],
  );

  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const toggleList = (key, value) =>
    setForm((current) => {
      const list = current[key] || [];
      return {
        ...current,
        [key]: list.includes(value) ? list.filter((item) => item !== value) : [...list, value],
      };
    });

  const missingInStep = STEPS[step].keys.filter((key) => {
    const value = form[key];
    return Array.isArray(value) ? value.length === 0 : !String(value || "").trim();
  });

  return (
    <div className="onboard">
      <div className="onboard-left">
        <div className="onboard-brand">
          <span className="brand-mark">一</span>
          <div>
            <strong>{t("app.name")}</strong>
            <span>{t("app.tagline")}</span>
          </div>
        </div>

        <section>
          <h3>{t("onboard.purpose")}</h3>
          <p>
            山东大学的通知散落在主站、各学院、本科生院、研究生院、就业网、团委等几十个站点。
            重要的事情往往只在某个学院的公告栏里贴三天，等你看到时已经截止了。
          </p>
          <p>
            一键山大把这些可靠的官方信息聚合起来，整理成可以理解、可以直接行动的条目，
            并根据你的情况给出推荐——同时保留一部分跨学院、跨兴趣的内容，避免越看越窄。
          </p>
        </section>

        <section>
          <h3>{t("onboard.origin")}</h3>
          <p>
            它最初只是为了解决一个很具体的问题：错过。错过一次竞赛报名、错过一次奖学金材料提交，
            错过的原因是没看到，而不是不想参加。
          </p>
          <p>
            所以这个工具的第一原则是「准确」：标题只用官方原标题，时间以官方原文为准，
            抓不到就如实说明原因，不编造、不用假按钮充数。
          </p>
        </section>

        <section>
          <h3>{t("onboard.authorTitle")}</h3>
          <p className="onboard-author">
            <UserRound size={16} />
            <strong>松</strong>
          </p>
          <p>
            一个人开发维护的小工具。所有数据保存在你自己的电脑上，不需要登录，也不会上传。
          </p>
        </section>

        <p className="onboard-foot">{t("app.disclaimer")}</p>
      </div>

      <div className="onboard-right">
        <div className="onboard-progress">
          <div>
            <span className="eyebrow">{t("onboard.progress")}</span>
            <strong>
              第 {step + 1} / {STEPS.length} 步 · {STEPS[step].title}
            </strong>
          </div>
          <Progress value={filled.length} total={ALL_KEYS.length} />
        </div>

        {showPreview ? (
          <div className="onboard-preview">
            <span className="eyebrow">{t("onboard.preview")}</span>
            <h2>{form.nickname ? `你好，${form.nickname}` : "你好"}</h2>
            <ul className="preview-list">
              {ALL_KEYS.map((key) => {
                const value = form[key];
                const text = Array.isArray(value) ? value.join("、") : value;
                return (
                  <li key={key} className={text ? "" : "empty"}>
                    <span>{LABELS[key]}</span>
                    <strong>{text || "未填写"}</strong>
                  </li>
                );
              })}
            </ul>
            <p className="preview-note">{t("onboard.generic")}</p>
          </div>
        ) : (
          <div className="onboard-form">
            {step === 0 && (
              <>
                <Field label="身份">
                  <div className="chip-row">
                    {IDENTITIES.map((item) => (
                      <button
                        type="button"
                        key={item}
                        className={`chip ${form.identity === item ? "active" : ""}`}
                        onClick={() => set("identity", item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  {!form.identity && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
                <Field label="学院" hint={form.college ? "" : t("onboard.warn")}>
                  <input
                    value={form.college}
                    onChange={(event) => set("college", event.target.value)}
                    placeholder="例如：哲学与社会发展学院"
                  />
                </Field>
                <Field label="专业">
                  <input
                    value={form.major}
                    onChange={(event) => set("major", event.target.value)}
                    placeholder="例如：哲学"
                  />
                  {!form.major && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
                <Field label="年级">
                  <div className="chip-row">
                    {GRADES.map((item) => (
                      <button
                        type="button"
                        key={item}
                        className={`chip ${form.grade === item ? "active" : ""}`}
                        onClick={() => set("grade", item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  {!form.grade && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
                <Field label="校区">
                  <div className="chip-row">
                    {CAMPUSES.map((item) => (
                      <button
                        type="button"
                        key={item}
                        className={`chip ${form.campus === item ? "active" : ""}`}
                        onClick={() => set("campus", item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  {!form.campus && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
              </>
            )}

            {step === 1 && (
              <>
                <Field label="研究方向">
                  <input
                    value={form.research}
                    onChange={(event) => set("research", event.target.value)}
                    placeholder="例如：法兰克福学派 / 机器学习"
                  />
                  {!form.research && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
                <Field label="感兴趣的内容">
                  <div className="chip-row">
                    {INTERESTS.map((item) => (
                      <button
                        type="button"
                        key={item}
                        className={`chip ${form.interests.includes(item) ? "active" : ""}`}
                        onClick={() => toggleList("interests", item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  {!form.interests.length && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
                <Field label="当前目标">
                  <div className="chip-row">
                    {GOALS.map((item) => (
                      <button
                        type="button"
                        key={item}
                        className={`chip ${form.goals.includes(item) ? "active" : ""}`}
                        onClick={() => toggleList("goals", item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  {!form.goals.length && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
              </>
            )}

            {step === 2 && (
              <>
                <Field label="常用关键词" hint="用空格分隔，例如：竞赛 讲座 奖学金">
                  <input
                    value={form.keywords.join(" ")}
                    onChange={(event) =>
                      set(
                        "keywords",
                        event.target.value.split(/[\s,，、]+/).filter(Boolean),
                      )
                    }
                    placeholder="竞赛 讲座 奖学金"
                  />
                  {!form.keywords.length && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
                <Field label="不想看到的内容" hint="可留空">
                  <input
                    value={form.avoid.join(" ")}
                    onChange={(event) =>
                      set("avoid", event.target.value.split(/[\s,，、]+/).filter(Boolean))
                    }
                    placeholder="例如：周末培训"
                  />
                </Field>
                <Field label="截止提醒偏好">
                  <div className="chip-row">
                    {DEADLINE_PREFS.map((item) => (
                      <button
                        type="button"
                        key={item}
                        className={`chip ${form.deadlinePref === item ? "active" : ""}`}
                        onClick={() => set("deadlinePref", item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  {!form.deadlinePref && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
                <Field label="昵称">
                  <input
                    value={form.nickname}
                    onChange={(event) => set("nickname", event.target.value)}
                    placeholder="首页会这样称呼你"
                  />
                  {!form.nickname && <small className="field-hint">{t("onboard.warn")}</small>}
                </Field>
              </>
            )}
          </div>
        )}

        <div className="onboard-actions">
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              if (showPreview) setShowPreview(false);
              else setStep((value) => Math.max(0, value - 1));
            }}
            disabled={!showPreview && step === 0}
          >
            <ArrowLeft size={15} /> {t("action.back")}
          </button>

          <button type="button" className="ghost-button" onClick={onSkip}>
            {t("action.skip")}
          </button>

          {step === STEPS.length - 1 && !showPreview ? (
            <button type="button" className="primary-button" onClick={() => setShowPreview(true)}>
              {t("onboard.preview")} <ArrowRight size={15} />
            </button>
          ) : showPreview ? (
            <button type="button" className="primary-button" onClick={() => onFinish(form)}>
              <Sparkles size={15} /> {t("onboard.finish")}
            </button>
          ) : (
            <button
              type="button"
              className="primary-button"
              onClick={() => setStep((value) => Math.min(STEPS.length - 1, value + 1))}
            >
              {t("action.next")} <ArrowRight size={15} />
            </button>
          )}
        </div>

        {missingInStep.length > 0 && !showPreview && (
          <p className="onboard-missing">
            本步还有 {missingInStep.length} 项未填写，也可以直接下一步或跳过。
          </p>
        )}
      </div>
    </div>
  );
}

const LABELS = {
  identity: "身份",
  college: "学院",
  major: "专业",
  grade: "年级",
  campus: "校区",
  research: "研究方向",
  interests: "感兴趣的内容",
  goals: "当前目标",
  keywords: "常用关键词",
  avoid: "不想看到的内容",
  deadlinePref: "截止提醒偏好",
  nickname: "昵称",
};
