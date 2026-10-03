/**
 * 收藏（需求：独立的信息整理功能）。
 * 支持文件夹、标签、备注、多种排序、搜索、批量操作和导出；
 * 收藏不自动创建待办；内容过期后仍保留；更新或出现结果时提醒。
 */

import { useMemo, useState } from "react";
import { Bookmark, Download, ExternalLink, FolderPlus, Search, Trash2 } from "lucide-react";
import { Empty, Section } from "../components/Shared.jsx";
import { useI18n } from "../lib/i18n.js";
import { useStore } from "../lib/store.jsx";
import { download, isExpired } from "../lib/utils.js";

const SORTS = [
  ["added", "收藏时间（新→旧）"],
  ["deadline", "截止时间（近→远）"],
  ["published", "发布时间（新→旧）"],
  ["title", "标题"],
];

export default function FavoritesPage({ notices, onOpen, onToast }) {
  const { t } = useI18n();
  const { state, updateFavorite, removeFavorites, addFolder, addTodo, inTodo } = useStore();
  const [folder, setFolder] = useState("全部");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("added");
  const [selected, setSelected] = useState([]);
  const [newFolder, setNewFolder] = useState("");

  const index = useMemo(() => {
    const map = new Map();
    notices.forEach((notice) => map.set(notice.id, notice));
    return map;
  }, [notices]);

  const entries = useMemo(() => {
    const rows = Object.entries(state.favorites).map(([id, meta]) => ({
      id,
      meta,
      notice: index.get(id) || { id, ...(meta.snapshot || {}) },
    }));
    const term = query.trim().toLowerCase();
    const filtered = rows.filter((row) => {
      if (folder !== "全部" && row.meta.folder !== folder) return false;
      if (!term) return true;
      const haystack = `${row.notice.title || ""} ${row.meta.note || ""} ${(row.meta.tags || []).join(" ")}`;
      return haystack.toLowerCase().includes(term);
    });
    const compare = {
      added: (a, b) => String(b.meta.addedAt || "").localeCompare(String(a.meta.addedAt || "")),
      deadline: (a, b) =>
        String(a.notice.deadline || "9999").localeCompare(String(b.notice.deadline || "9999")),
      published: (a, b) =>
        String(b.notice.published_at || "").localeCompare(String(a.notice.published_at || "")),
      title: (a, b) => String(a.notice.title || "").localeCompare(String(b.notice.title || "")),
    };
    return filtered.sort(compare[sort] || compare.added);
  }, [state.favorites, index, folder, query, sort]);

  const exportFavorites = () => {
    const payload = entries.map((row) => ({
      title: row.notice.title,
      source: row.notice.source,
      published_at: row.notice.published_at,
      deadline: row.notice.deadline,
      official_url: row.notice.official_url,
      folder: row.meta.folder,
      tags: row.meta.tags,
      note: row.meta.note,
    }));
    download("收藏导出.json", JSON.stringify(payload, null, 2));
    onToast?.("已导出收藏");
  };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("nav.favorites")}</span>
          <h1>{t("fav.title")}</h1>
          <p>收藏不会自动创建待办；内容过期后依然保留，出现结果时会提醒。</p>
        </div>
        <button type="button" className="ghost-button" onClick={exportFavorites}>
          <Download size={15} /> {t("action.export")}
        </button>
      </header>

      <div className="tool-row">
        <div className="search-box">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="在收藏里搜索标题、标签、备注"
          />
        </div>
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          {SORTS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="folder-row">
        <button
          type="button"
          className={`chip ${folder === "全部" ? "active" : ""}`}
          onClick={() => setFolder("全部")}
        >
          全部 {Object.keys(state.favorites).length}
        </button>
        {state.folders.map((item) => (
          <button
            type="button"
            key={item}
            className={`chip ${folder === item ? "active" : ""}`}
            onClick={() => setFolder(item)}
          >
            {item}
          </button>
        ))}
        <div className="folder-add">
          <input
            value={newFolder}
            onChange={(event) => setNewFolder(event.target.value)}
            placeholder="新建文件夹"
          />
          <button
            type="button"
            className="icon-button tiny"
            onClick={() => {
              if (!newFolder.trim()) return;
              addFolder(newFolder.trim());
              setNewFolder("");
            }}
          >
            <FolderPlus size={15} />
          </button>
        </div>
      </div>

      {selected.length > 0 && (
        <div className="batch-bar">
          <span>已选 {selected.length} 项</span>
          <select
            onChange={(event) => {
              const target = event.target.value;
              if (!target) return;
              selected.forEach((id) => updateFavorite(id, { folder: target }));
              setSelected([]);
            }}
            defaultValue=""
          >
            <option value="">移动到文件夹…</option>
            {state.folders.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="small-button danger"
            onClick={() => {
              removeFavorites(selected);
              setSelected([]);
            }}
          >
            <Trash2 size={14} /> {t("action.delete")}
          </button>
        </div>
      )}

      {!entries.length && (
        <Empty
          icon={<Bookmark size={24} />}
          title={t("fav.empty")}
          hint="在通知卡片上点收藏按钮即可加入。"
        />
      )}

      <div className="fav-list">
        {entries.map((row) => {
          const expired = isExpired(row.notice);
          return (
            <article key={row.id} className="fav-card">
              <label className="fav-check">
                <input
                  type="checkbox"
                  checked={selected.includes(row.id)}
                  onChange={() =>
                    setSelected((current) =>
                      current.includes(row.id)
                        ? current.filter((value) => value !== row.id)
                        : [...current, row.id],
                    )
                  }
                />
              </label>
              <div className="fav-body">
                <button type="button" className="fav-title" onClick={() => onOpen(row.notice)}>
                  {row.notice.title || "（原始通知已不在本地库中）"}
                </button>
                <div className="fav-meta">
                  <span>{row.notice.source}</span>
                  {row.notice.published_at && <span>{row.notice.published_at}</span>}
                  {row.notice.deadline && (
                    <span className={expired ? "urgent" : ""}>
                      截止 {row.notice.deadline}
                      {expired ? "（已过期，仍保留）" : ""}
                    </span>
                  )}
                </div>
                <div className="fav-editors">
                  <select
                    value={row.meta.folder}
                    onChange={(event) => updateFavorite(row.id, { folder: event.target.value })}
                  >
                    {state.folders.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  <input
                    value={(row.meta.tags || []).join(" ")}
                    onChange={(event) =>
                      updateFavorite(row.id, {
                        tags: event.target.value.split(/[\s,，、]+/).filter(Boolean),
                      })
                    }
                    placeholder={t("fav.tags")}
                  />
                  <input
                    value={row.meta.note || ""}
                    onChange={(event) => updateFavorite(row.id, { note: event.target.value })}
                    placeholder={t("fav.note")}
                  />
                </div>
              </div>
              <div className="fav-actions">
                <a
                  className="icon-button tiny"
                  href={row.notice.official_url}
                  target="_blank"
                  rel="noreferrer"
                  title={t("notice.official")}
                >
                  <ExternalLink size={15} />
                </a>
                <button
                  type="button"
                  className="icon-button tiny"
                  onClick={() =>
                    addTodo({
                      noticeId: row.id,
                      title: row.notice.title,
                      deadline: row.notice.deadline || "",
                      source: row.notice.source,
                      official_url: row.notice.official_url,
                    })
                  }
                  title={t("notice.todo")}
                >
                  {inTodo(row.id) ? "✓" : "+"}
                </button>
                <button
                  type="button"
                  className="icon-button tiny danger"
                  onClick={() => removeFavorites([row.id])}
                  title={t("action.delete")}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <Section title="说明">
        <p className="muted small">
          收藏是独立于推荐和待办的整理功能。它不会自动变成待办，也不会因为过期而消失；
          当对应通知出现更新或结果时，会在提醒里提示你。
        </p>
      </Section>
    </div>
  );
}
