/**
 * 首页（需求 3）。
 * 大面积留白 + 大标语 + 右侧功能栏，首屏不放统计数据和复杂卡片。
 */

import { useEffect, useMemo, useState } from "react";
import { LoaderCircle, Sparkles } from "lucide-react";
import Rail from "../components/Rail.jsx";
import { useI18n } from "../lib/i18n.js";
import { useStore } from "../lib/store.jsx";
import { dailyLine, encouragementFor, greeting } from "../lib/utils.js";

export default function Home({ counts, active, onNavigate, onScan, scanning }) {
  const { t, lang } = useI18n();
  const { state, patchSettings } = useStore();
  const profile = state.profile;
  const [slogan, setSlogan] = useState(state.settings.slogan || "");
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setSlogan(state.settings.slogan || "");
  }, [state.settings.slogan]);

  const lines = useMemo(() => {
    const list = [];
    const nick = profile?.nickname;
    if (nick) list.push(lang === "en" ? `Hello, ${nick}` : `你好，${nick}`);
    else list.push(`${greeting(lang)}`);
    list.push(dailyLine());
    const encouragement = encouragementFor(profile?.goals || []);
    if (encouragement) list.push(encouragement);
    return list;
  }, [profile, lang]);

  const bigLine = state.settings.slogan || lines[Math.floor(Date.now() / 3600000) % lines.length];

  return (
    <div className="home">
      <div className="home-main">
        <span className="eyebrow">{t("app.tagline")}</span>
        <h1 className="home-slogan">{bigLine}</h1>

        <div className="home-sub">
          {lines.map((line) => (
            <span key={line}>{line}</span>
          ))}
        </div>

        <div className="home-actions">
          <button type="button" className="primary-button" onClick={() => onNavigate("为你推荐")}>
            <Sparkles size={16} /> {t("nav.recommend")}
          </button>
          <button type="button" className="ghost-button" onClick={() => onNavigate("全部通知")}>
            {t("nav.all")}
          </button>
          <button type="button" className="ghost-button" onClick={onScan} disabled={scanning}>
            {scanning ? <LoaderCircle className="spin" size={15} /> : null}
            {scanning ? t("action.checking") : t("action.check")}
          </button>
        </div>

        <div className="home-slogan-edit">
          {editing ? (
            <>
              <input
                value={slogan}
                onChange={(event) => setSlogan(event.target.value)}
                placeholder={t("home.customSlogan")}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    patchSettings({ slogan: slogan.trim() });
                    setEditing(false);
                  }
                }}
              />
              <button
                type="button"
                className="small-button"
                onClick={() => {
                  patchSettings({ slogan: slogan.trim() });
                  setEditing(false);
                }}
              >
                {t("action.save")}
              </button>
              <button type="button" className="small-button" onClick={() => setEditing(false)}>
                {t("action.cancel")}
              </button>
            </>
          ) : (
            <button type="button" className="text-button" onClick={() => setEditing(true)}>
              {t("home.customSlogan")}
              {state.settings.slogan ? " · 已自定义" : ""}
            </button>
          )}
        </div>

        <p className="home-foot">
          {t("app.author")} · {t("app.disclaimer")}
        </p>
      </div>

      <Rail active={active} onNavigate={onNavigate} counts={counts()} />
    </div>
  );
}
