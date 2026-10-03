/**
 * 系统设置（需求 N / 18 / 视觉方向）。
 * 三套主题、中英文、AI 配置入口、数据本地管理与提醒设置。
 */

import { useEffect, useRef, useState } from "react";
import { Database, Download, Palette, RefreshCw, Sparkles, Upload, UserRound } from "lucide-react";
import { Banner, Field, Section, Toggle } from "../components/Shared.jsx";
import { api } from "../lib/api.js";
import { useI18n } from "../lib/i18n.js";
import { useStore } from "../lib/store.jsx";
import { download } from "../lib/utils.js";

const THEMES = [
  ["dark", "settings.theme.dark"],
  ["light", "settings.theme.light"],
  ["sdu", "settings.theme.sdu"],
];

export default function SettingsPage({ onRedoOnboarding, onToast }) {
  const { t, lang, setLang } = useI18n();
  const { state, patchSettings, exportAll, importAll, resetAll } = useStore();
  const settings = state.settings;
  const [backups, setBackups] = useState([]);
  const [ai, setAi] = useState(settings.ai || {});
  const fileRef = useRef(null);

  useEffect(() => setAi(settings.ai || {}), [settings.ai]);

  useEffect(() => {
    api
      .backups()
      .then((data) => setBackups(data.items || []))
      .catch(() => setBackups([]));
  }, []);

  const doBackup = async () => {
    try {
      const data = await api.backup();
      setBackups(data.items || []);
      onToast?.(data.name ? `已备份 ${data.name}` : "已创建备份");
    } catch (err) {
      onToast?.(err.message || "备份失败");
    }
  };

  const doExport = () => {
    const payload = exportAll();
    download("一键山大-本地数据.json", JSON.stringify(payload, null, 2));
    onToast?.("已导出本地数据");
  };

  const doImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const ok = importAll(JSON.parse(text));
      onToast?.(ok ? "已导入本地数据" : "文件格式不正确");
    } catch {
      onToast?.("导入失败：文件不是有效的 JSON");
    }
    event.target.value = "";
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.settings")}</span>
          <h1>{t("settings.title")}</h1>
          <p>{t("app.author")} · {t("app.disclaimer")}</p>
        </div>
      </header>

      <Section title={t("settings.theme")} extra={<Palette size={16} />}>
        <div className="chip-row">
          {THEMES.map(([value, key]) => (
            <button
              type="button"
              key={value}
              className={`chip ${settings.theme === value ? "active" : ""}`}
              onClick={() => patchSettings({ theme: value })}
            >
              {t(key)}
            </button>
          ))}
        </div>
      </Section>

      <Section title={t("settings.lang")}>
        <div className="chip-row">
          <button
            type="button"
            className={`chip ${lang === "zh" ? "active" : ""}`}
            onClick={() => setLang("zh")}
          >
            中文
          </button>
          <button
            type="button"
            className={`chip ${lang === "en" ? "active" : ""}`}
            onClick={() => setLang("en")}
          >
            English
          </button>
        </div>
      </Section>

      <Section title={t("settings.profile")} extra={<UserRound size={16} />}>
        {state.profile ? (
          <ul className="preview-list">
            {Object.entries(state.profile)
              .filter(([, value]) => (Array.isArray(value) ? value.length : value))
              .map(([key, value]) => (
                <li key={key}>
                  <span>{key}</span>
                  <strong>{Array.isArray(value) ? value.join("、") : value}</strong>
                </li>
              ))}
          </ul>
        ) : (
          <p className="muted">还没有填写资料，推荐会退化为通用内容。</p>
        )}
        <button type="button" className="ghost-button" onClick={onRedoOnboarding}>
          {t("settings.redo")}
        </button>
      </Section>

      <Section title={t("settings.ai")} extra={<Sparkles size={16} />}>
        <p className="muted small">{t("settings.aiHint")}</p>
        <div className="ai-config">
          <Toggle
            label="启用 AI 整理"
            hint="未启用时使用本地规则整理，结果与官方原文并列展示"
            checked={Boolean(ai.enabled)}
            onChange={(value) => {
              const next = { ...ai, enabled: value };
              setAi(next);
              patchSettings({ ai: next });
            }}
          />
          <Field label="服务商">
            <select
              value={ai.provider || "openai"}
              onChange={(event) => setAi({ ...ai, provider: event.target.value })}
            >
              <option value="openai">OpenAI 兼容接口</option>
              <option value="deepseek">DeepSeek</option>
              <option value="qwen">通义千问</option>
              <option value="ollama">本地 Ollama</option>
              <option value="custom">自定义</option>
            </select>
          </Field>
          <Field label="Base URL">
            <input
              value={ai.baseUrl || ""}
              onChange={(event) => setAi({ ...ai, baseUrl: event.target.value })}
              placeholder="https://api.openai.com/v1"
            />
          </Field>
          <Field label="模型名称">
            <input
              value={ai.model || ""}
              onChange={(event) => setAi({ ...ai, model: event.target.value })}
              placeholder="gpt-4o-mini"
            />
          </Field>
          <Field label="API Key" hint="只保存在本机浏览器存储中，不会上传">
            <input
              type="password"
              value={ai.apiKey || ""}
              onChange={(event) => setAi({ ...ai, apiKey: event.target.value })}
              placeholder="sk-..."
            />
          </Field>
          <button
            type="button"
            className="primary-button"
            onClick={() => {
              patchSettings({ ai });
              onToast?.("AI 配置已保存到本机");
            }}
          >
            {t("action.save")}
          </button>
        </div>
        <Banner tone="info">
          AI 调用端尚未接入：当前所有整理结果由本地规则生成，并明确标注来源。
          配置入口已保留，接入后会自动切换为 AI 整理并始终附上官方依据。
        </Banner>
      </Section>

      <Section title={t("settings.reminder")}>
        <Toggle
          label="启用本地提醒"
          hint="提醒只在工作台内完成，不使用短信、微信或手机推送"
          checked={Boolean(settings.reminder?.enabled)}
          onChange={(value) =>
            patchSettings({ reminder: { ...settings.reminder, enabled: value } })
          }
        />
        <Field label="免打扰时段">
          <input
            value={settings.reminder?.quietHours || ""}
            onChange={(event) =>
              patchSettings({ reminder: { ...settings.reminder, quietHours: event.target.value } })
            }
            placeholder="22:00-08:00"
          />
        </Field>
        <Field label="提前提醒（分钟）">
          <input
            type="number"
            value={settings.reminder?.leadMinutes || 1440}
            onChange={(event) =>
              patchSettings({
                reminder: { ...settings.reminder, leadMinutes: Number(event.target.value) },
              })
            }
          />
        </Field>
      </Section>

      <Section title={t("settings.data")} extra={<Database size={16} />}>
        <div className="data-actions">
          <button type="button" className="ghost-button" onClick={doBackup}>
            <RefreshCw size={15} /> {t("settings.backup")}
          </button>
          <button type="button" className="ghost-button" onClick={doExport}>
            <Download size={15} /> {t("action.export")}
          </button>
          <button type="button" className="ghost-button" onClick={() => fileRef.current?.click()}>
            <Upload size={15} /> {t("action.import")}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json"
            hidden
            onChange={doImport}
          />
          <button
            type="button"
            className="ghost-button danger"
            onClick={() => {
              if (window.confirm("确定要清空本机上的画像、收藏、待办和设置吗？此操作不可撤销。")) {
                resetAll();
                onToast?.("已重置本地数据");
              }
            }}
          >
            {t("action.reset")}
          </button>
        </div>
        {backups.length > 0 && (
          <ul className="backup-list">
            {backups.map((item) => (
              <li key={item.name}>
                <span>{item.name}</span>
                <em>{Math.round(item.size / 1024)} KB</em>
                <em>{item.modified_at}</em>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
