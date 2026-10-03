/**
 * 信息源管理（需求 9）。
 * 显示每个来源是否抓取成功、最后更新时间、抓取数量和具体失败原因；
 * 支持添加自定义网站，并展示最近一次检查结果。
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, ExternalLink, Plus, RefreshCw, Trash2 } from "lucide-react";
import { Banner, Empty, Section } from "../components/Shared.jsx";
import { api } from "../lib/api.js";
import { useI18n } from "../lib/i18n.js";

export default function SourcesPage({ onToast }) {
  const { t } = useI18n();
  const [data, setData] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [sources, scan] = await Promise.all([api.sources(), api.scanStatus()]);
      setData(sources);
      setStatus(scan);
    } catch (err) {
      setError(err.message || t("state.offline"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!status?.running) return undefined;
    const timer = setInterval(async () => {
      try {
        setStatus(await api.scanStatus());
      } catch {
        // 忽略轮询失败
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [status?.running]);

  const addSource = async () => {
    if (!url.trim()) return;
    try {
      await api.addSource({ url: url.trim(), name: name.trim(), scope: "用户添加" });
      setUrl("");
      setName("");
      onToast?.("已添加自定义来源，下次检查更新时生效");
      load();
    } catch (err) {
      onToast?.(err.message || "添加失败");
    }
  };

  const removeSource = async (id) => {
    try {
      await api.removeSource(id);
      load();
    } catch (err) {
      onToast?.(err.message || "删除失败");
    }
  };

  const statusIcon = (value) => {
    if (value === "ok") return <CheckCircle2 size={15} className="ok" />;
    if (value === "failed") return <AlertTriangle size={15} className="bad" />;
    return <CircleHelp size={15} className="unknown" />;
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.sources")}</span>
          <h1>{t("sources.title")}</h1>
          <p>
            {data
              ? `共 ${data.total} 个来源 · 成功 ${data.healthy} · 失败 ${data.failed} · 本地收录 ${data.notices} 条`
              : t("state.loading")}
          </p>
        </div>
        <button type="button" className="ghost-button" onClick={load}>
          <RefreshCw size={15} /> 刷新
        </button>
      </header>

      {status?.running && (
        <Banner tone="info">
          正在检查更新：{status.checked_sources}/{status.total_sources} 个来源…
        </Banner>
      )}
      {status?.finished_at && !status.running && (
        <Section title="最近一次检查结果">
          <div className="scan-summary">
            <span>
              检查来源 <strong>{status.checked_sources}</strong> 个
            </span>
            <span>
              新增 <strong>{status.new_items}</strong> 条
            </span>
            <span>
              更新 <strong>{status.changed_items}</strong> 条
            </span>
            <span>
              失败 <strong>{status.failed?.length || 0}</strong> 个
            </span>
            <span>{status.finished_at}</span>
          </div>
          {status.error && <p className="error-line">{status.error}</p>}
          {status.failed?.length > 0 && (
            <ul className="fail-list">
              {status.failed.map((item) => (
                <li key={item.id}>
                  <strong>{item.name}</strong>：{item.reason || "未知原因"}
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}

      {error && <Banner tone="error">{error}</Banner>}

      <Section title={t("sources.add")}>
        <div className="source-add">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="名称（可留空）"
          />
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder={t("sources.url")}
          />
          <button type="button" className="primary-button" onClick={addSource}>
            <Plus size={15} /> {t("action.add")}
          </button>
        </div>
      </Section>

      {loading && <p className="loading-line">{t("state.loading")}…</p>}

      {data && !data.items.length && <Empty title={t("state.empty")} />}

      <div className="source-list">
        {(data?.items || []).map((item) => (
          <article key={item.id} className={`source-card ${item.status}`}>
            <div className="source-main">
              <div className="source-title">
                {statusIcon(item.status)}
                <strong>{item.name}</strong>
                {item.auto && <span className="tag">自动发现</span>}
                {item.custom && <span className="tag">用户添加</span>}
              </div>
              <a className="source-url" href={item.url} target="_blank" rel="noreferrer">
                {item.url} <ExternalLink size={12} />
              </a>
              {item.error && <p className="source-error">{t("sources.reason")}：{item.error}</p>}
            </div>
            <div className="source-stats">
              <span>
                {t("sources.count")} <strong>{item.item_count}</strong>
              </span>
              <span>
                {t("sources.last")} {item.last_checked ? item.last_checked.replace("T", " ") : "—"}
              </span>
              {item.custom && (
                <button
                  type="button"
                  className="icon-button tiny danger"
                  onClick={() => removeSource(item.id)}
                  title={t("action.delete")}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
