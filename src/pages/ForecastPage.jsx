import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api.js";
import { useI18n } from "../lib/i18n.js";
import { SOURCE_GROUPS } from "../data/sourceOrder.js";

const MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];

export default function ForecastPage({ onToast, onOpenNotice }) {
  const { t } = useI18n();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [source, setSource] = useState(""); // 按信息来源筛选预测，空 = 全部

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setData(null);
      try {
        const d = await api.forecast(source || undefined);
        if (alive) setData(d);
      } catch (e) {
        onToast?.(e.message || "预测加载失败");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [source, onToast]);

  const maxMonthTotal = useMemo(() => {
    if (!data) return 1;
    return Math.max(1, ...data.monthly.map((m) => m.total));
  }, [data]);

  if (loading) return <div className="page"><p className="loading-line">…</p></div>;
  if (!data) return <div className="page">暂无数据</div>;

  const accent = "var(--accent, #c41e1e)";

  // 点击预测活动 → 跳转到通知正文
  const openActivity = (act) => {
    if (act?.id) onOpenNotice?.(act.id);
  };

  // 活动标注样式（可点击）
  const actStyle = (annual) => ({
    display: "flex",
    flexDirection: "column",
    gap: 2,
    padding: "4px 7px",
    borderRadius: 6,
    background: annual ? "linear-gradient(135deg, var(--accent), var(--accent-bright))" : "var(--surface-raised)",
    color: annual ? "#fff" : "var(--text)",
    fontSize: 11.5,
    lineHeight: 1.35,
    cursor: "pointer",
    border: "none",
    textAlign: "left",
    width: "100%",
  });

  // 活动行（年视图下拉列表复用）：展示主题、出现年份、来源，点击跳转原文正文
  const actRow = (a, idx) => (
    <button
      key={`${a.id}-${idx}`}
      type="button"
      onClick={() => openActivity(a)}
      style={{ ...actStyle(a.annual), fontSize: 11.5, alignItems: "flex-start" }}
      title={a.summary ? `${a.name}：${a.summary}` : a.name}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap", width: "100%" }}>
        <strong style={{ fontSize: 12 }}>{a.name}</strong>
        {a.annual && (
          <em style={{ fontSize: 9, fontStyle: "normal", opacity: 0.9, padding: "1px 5px", borderRadius: 4, background: "rgba(255,255,255,0.22)" }}>
            {t("forecast.annualBadge")}
          </em>
        )}
        <em style={{ fontSize: 10, fontStyle: "normal", opacity: 0.85, marginLeft: "auto" }}>{a.years.join("/")}</em>
      </span>
      <span style={{ opacity: 0.9, fontWeight: 400, marginTop: 2, fontSize: 10.5, display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
        {a.source} · {a.title}
      </span>
    </button>
  );

  // 年视图底部仅列「年度活动」避免渲染过载；下拉列表每月份最多展示 50 条（年度优先）
  const annualActs = (data.activities || []).filter((a) => a.annual).slice(0, 120);

  return (
    <div className="page">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>{t("forecast.title")} · {data.year}</h2>
          <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: 13 }}>{t("forecast.subtitle")}</p>
        </div>
      </div>

      <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <label style={{ fontSize: 13, color: "var(--muted)" }}>{t("forecast.filterLabel")}</label>
        <select
          value={source}
          onChange={(e) => { setSource(e.target.value); }}
          style={{
            padding: "6px 12px", borderRadius: 8, cursor: "pointer",
            border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)",
            fontSize: 13, maxWidth: 320,
          }}
        >
          <option value="">{t("forecast.filterAll")}</option>
          {SOURCE_GROUPS.map(([group, names]) => (
            <optgroup key={group} label={group}>
              {names.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      <div style={{ marginTop: 8, color: "var(--muted)", fontSize: 12 }}>
        {source ? (
          <>
            <strong>{source}</strong> · {t("forecast.activeSources")}：{data.source_count} · {t("forecast.skipped")}：{data.skipped_no_date}
          </>
        ) : (
          <>
            {t("forecast.activeSources")}：{data.source_count} · {t("forecast.skipped")}：{data.skipped_no_date}
          </>
        )}
      </div>

      {/* 年视图：每月方格 + 预测 + 三年内该月活动下拉（仅保留年视图） */}
      <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, alignItems: "start" }}>
        {data.monthly.map((m) => {
          const ratio = m.total / maxMonthTotal;
          const acts = (data.activitiesByMonth?.[m.month] || []).slice(0, 50);
          return (
            <div
              key={m.month}
              style={{
                textAlign: "left", padding: 14, borderRadius: 12,
                border: "1px solid var(--border)", background: "var(--surface)",
                color: "var(--text)",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 15 }}>{MONTHS[m.month - 1]}</div>
              <div style={{ marginTop: 6, fontSize: 12, color: "var(--muted)" }}>{m.sources.length} 个信息源</div>
              <div style={{ marginTop: 8, height: 6, borderRadius: 3, background: "var(--border)", overflow: "hidden" }}>
                <div style={{ width: `${Math.round(ratio * 100)}%`, height: "100%", background: accent }} />
              </div>
              <div style={{ marginTop: 4, fontSize: 11, color: "var(--muted)" }}>预测 {m.total}{m.topCategory ? ` · ${m.topCategory}` : ""}</div>
              <details style={{ marginTop: 10 }}>
                <summary style={{ fontSize: 12, cursor: "pointer", color: accent, userSelect: "none" }}>
                  {t("forecast.monthActs")}（{acts.length}）
                </summary>
                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 5, maxHeight: 240, overflowY: "auto" }}>
                  {acts.length === 0 ? (
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>{t("forecast.noActivity")}</span>
                  ) : (
                    acts.map((a, ai) => actRow(a, ai))
                  )}
                </div>
              </details>
            </div>
          );
        })}
      </div>

      {data.scopes && Object.keys(data.scopes).length > 0 && (
        <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 8, fontSize: 12, color: "var(--muted)" }}>
          <span>{t("forecast.scopeLegend")}：</span>
          {Object.entries(data.scopes).map(([scope, count]) => (
            <span key={scope} style={{ padding: "2px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface)" }}>
              {scope} · {count}
            </span>
          ))}
        </div>
      )}

      {annualActs.length > 0 && (
        <div style={{ marginTop: 18 }}>
          <h3 style={{ margin: "0 0 10px", fontSize: 16 }}>
            {t("forecast.annualList")}（{annualActs.length}）
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: 10 }}>
            {annualActs.map((a, idx) => (
              <button
                key={`${a.id}-${idx}`}
                type="button"
                onClick={() => openActivity(a)}
                style={{
                  ...actStyle(a.annual),
                  padding: "10px 12px",
                  fontSize: 12.5,
                  justifyContent: "flex-start",
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <strong style={{ fontSize: 13 }}>{a.name}</strong>
                  {a.annual && (
                    <em style={{ fontSize: 10, fontStyle: "normal", opacity: 0.9, padding: "1px 6px", borderRadius: 4, background: "rgba(255,255,255,0.22)" }}>
                      {t("forecast.annualBadge")}
                    </em>
                  )}
                  <em style={{ fontSize: 10.5, fontStyle: "normal", opacity: 0.85, marginLeft: "auto" }}>{a.month}月 · {a.count}次</em>
                </span>
                {a.summary && (
                  <span style={{ opacity: 0.9, fontWeight: 400, marginTop: 3, fontSize: 11.5 }}>
                    {a.summary}
                  </span>
                )}
                <span style={{ opacity: 0.85, fontSize: 10.5, marginTop: 4, textDecoration: "underline" }}>
                  {t("forecast.open")} →
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
