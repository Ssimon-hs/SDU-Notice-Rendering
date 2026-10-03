/** 通用小组件：胶囊、区块标题、空状态、开关、未开放标记。 */

import { Mail } from "lucide-react";
import { useI18n } from "../lib/i18n.js";

export function Chip({ active = false, children, onClick, title }) {
  return (
    <button
      type="button"
      className={`chip ${active ? "active" : ""}`}
      onClick={onClick}
      title={title}
      aria-pressed={active}
    >
      {children}
    </button>
  );
}

export function Section({ title, extra, children, id }) {
  return (
    <section className="section" id={id}>
      <div className="section-head">
        <h3>{title}</h3>
        {extra}
      </div>
      {children}
    </section>
  );
}

export function Empty({ icon = null, title, hint, action = null }) {
  return (
    <div className="empty-state">
      {icon}
      <strong>{title}</strong>
      {hint && <p>{hint}</p>}
      {action}
    </div>
  );
}

export function NotOpen({ label }) {
  const { t } = useI18n();
  return (
    <button type="button" className="not-open" disabled title={t("state.notOpenHint")}>
      {label}
      <span className="not-open-tag">{t("state.notOpen")}</span>
    </button>
  );
}

export function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="toggle-row">
      <span className="toggle-text">
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="toggle-track" aria-hidden="true" />
    </label>
  );
}

export function Field({ label, hint, children, required }) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {required && <em>*</em>}
      </span>
      {children}
      {hint && <small className="field-hint">{hint}</small>}
    </label>
  );
}

export function Meta({ items }) {
  return (
    <div className="meta-row">
      {items
        .filter((item) => item && item.value)
        .map((item) => (
          <span key={item.label} className="meta-item">
            <span className="meta-label">{item.label}</span>
            <span className="meta-value">{item.value}</span>
          </span>
        ))}
    </div>
  );
}

export function Banner({ tone = "info", children, onClose }) {
  return (
    <div className={`banner ${tone}`}>
      <div>{children}</div>
      {onClose && (
        <button type="button" className="icon-button tiny" onClick={onClose} aria-label="关闭">
          ×
        </button>
      )}
    </div>
  );
}

export function Progress({ value, total }) {
  const percent = total ? Math.round((value / total) * 100) : 0;
  return (
    <div className="progress">
      <div className="progress-bar" style={{ width: `${percent}%` }} />
      <span>{percent}%</span>
    </div>
  );
}

/** 通用小组件：胶囊、区块标题、空状态、开关、未开放标记。 */
