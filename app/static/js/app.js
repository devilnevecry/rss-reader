const API = "/api";

let state = {
  feeds: [],
  articles: [],
  total: 0,
  page: 1,
  pageSize: 20,
  pages: 0,
  activeFeedId: null,
  filters: { unread: false, favorites: false, search: "" },
};

const els = {
  feedList: document.getElementById("feedList"),
  emptyFeeds: document.getElementById("emptyFeeds"),
  articleGrid: document.getElementById("articleGrid"),
  pageTitle: document.getElementById("pageTitle"),
  currentFeedBadge: document.getElementById("currentFeedBadge"),
  searchInput: document.getElementById("searchInput"),
  filterUnread: document.getElementById("filterUnread"),
  filterFavorites: document.getElementById("filterFavorites"),
  btnRefreshAll: document.getElementById("btnRefreshAll"),
  btnRefreshCurrent: document.getElementById("btnRefreshCurrent"),
  btnAddFeed: document.getElementById("btnAddFeed"),
  btnPrev: document.getElementById("btnPrev"),
  btnNext: document.getElementById("btnNext"),
  paginationInfo: document.getElementById("paginationInfo"),
  errorBanner: document.getElementById("errorBanner"),
  successBanner: document.getElementById("successBanner"),
  statTotalFeeds: document.getElementById("statTotalFeeds"),
  statTotalArticles: document.getElementById("statTotalArticles"),
  statUnread: document.getElementById("statUnread"),
  statFavorites: document.getElementById("statFavorites"),
  statUpdated: document.getElementById("statUpdated"),
  addFeedDialog: document.getElementById("addFeedDialog"),
  dlgFeedUrl: document.getElementById("dlgFeedUrl"),
  dlgError: document.getElementById("dlgError"),
  dlgClose: document.getElementById("dlgClose"),
  dlgCancel: document.getElementById("dlgCancel"),
  dlgAdd: document.getElementById("dlgAdd"),
};

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Ошибка ${res.status}`);
  return data;
}

function showError(msg, el = els.errorBanner) {
  el.textContent = msg;
  el.style.display = "block";
  setTimeout(() => { el.style.display = "none"; }, 5000);
}

function showSuccess(msg) {
  els.successBanner.textContent = msg;
  els.successBanner.style.display = "block";
  setTimeout(() => { els.successBanner.style.display = "none"; }, 3000);
}

async function loadStats() {
  try {
    const s = await api("/api/stats");
    els.statTotalFeeds.textContent = s.total_feeds;
    els.statTotalArticles.textContent = s.total_articles;
    els.statUnread.textContent = s.unread;
    els.statFavorites.textContent = s.favorites;
    els.statUpdated.textContent = s.last_fetched_at
      ? "Последнее обновление: " + new Date(s.last_fetched_at).toLocaleString()
      : "Последнее обновление: —";
  } catch (e) { console.error(e); }
}

async function loadFeeds() {
  try {
    state.feeds = await api("/api/feeds");
    renderFeeds();
  } catch (e) { showError("Не удалось загрузить источники: " + e.message); }
}

function renderFeeds() {
  els.feedList.innerHTML = "";
  if (state.feeds.length === 0) {
    els.emptyFeeds.style.display = "block";
    return;
  }
  els.emptyFeeds.style.display = "none";
  for (const feed of state.feeds) {
    const item = document.createElement("div");
    item.className = "feed-item" + (state.activeFeedId === feed.id ? " active" : "");
    item.innerHTML = `
      <div class="flex-1">
        <div class="feed-title">${escapeHtml(feed.title || "Без названия")}</div>
        ${feed.last_error ? `<div class="feed-error">Ошибка: ${escapeHtml(feed.last_error)}</div>` : ""}
      </div>
      <div class="feed-actions">
        <button class="btn-icon" title="Обновить" onclick="event.stopPropagation(); refreshFeed(${feed.id})">⟳</button>
        <button class="btn-icon" title="Удалить" onclick="event.stopPropagation(); deleteFeed(${feed.id})">🗑</button>
      </div>
    `;
    item.onclick = () => { state.activeFeedId = feed.id; loadArticles(); renderFeeds(); };
    els.feedList.appendChild(item);
  }
}

async function loadArticles() {
  try {
    const params = new URLSearchParams();
    if (state.activeFeedId) params.set("feed_id", state.activeFeedId);
    if (state.filters.unread) params.set("unread_only", "true");
    if (state.filters.favorites) params.set("favorites_only", "true");
    if (state.filters.search) params.set("search", state.filters.search);
    params.set("page", state.page);
    params.set("page_size", state.pageSize);

    const data = await api("/api/articles?" + params.toString());
    state.articles = data.items;
    state.total = data.total;
    state.pages = data.pages;
    renderArticles();
    renderPagination();
  } catch (e) { showError("Не удалось загрузить публикации: " + e.message); }
}

function renderArticles() {
  els.articleGrid.innerHTML = "";
  const feedMap = {};
  for (const f of state.feeds) feedMap[f.id] = f.title;

  if (state.articles.length === 0) {
    els.articleGrid.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:40px;">Публикации не найдены</div>`;
    return;
  }

  for (const a of state.articles) {
    const card = document.createElement("article");
    card.className = "article-card" + (a.is_read ? " read" : "");
    const date = a.published_at ? new Date(a.published_at).toLocaleString() : "—";
    card.innerHTML = `
      <div class="article-meta">
        <span class="article-source">${escapeHtml(feedMap[a.feed_id] || "")}</span>
        <span>${date}</span>
      </div>
      <h2 class="article-title">${escapeHtml(a.title)}</h2>
      <div class="article-summary">${escapeHtml(a.summary || "")}</div>
      <div class="article-actions">
        <button class="article-btn ${a.is_read ? "active" : ""}" onclick="toggleRead(${a.id}, ${!a.is_read})">
          ${a.is_read ? "Вернуть непрочитанным" : "Прочитано"}
        </button>
        <button class="article-btn ${a.is_favorite ? "active" : ""}" onclick="toggleFavorite(${a.id}, ${!a.is_favorite})">
          ${a.is_favorite ? "Убрать из избранного" : "В избранное"}
        </button>
        <a href="${escapeHtml(a.url)}" target="_blank" rel="noopener" class="article-btn open">Открыть оригинал</a>
      </div>
    `;
    els.articleGrid.appendChild(card);
  }
}

function renderPagination() {
  els.paginationInfo.textContent = `Страница ${state.page} из ${Math.max(state.pages, 1)} (всего ${state.total})`;
  els.btnPrev.disabled = state.page <= 1;
  els.btnNext.disabled = state.page >= state.pages || state.pages === 0;
}

async function addFeed() {
  const url = els.dlgFeedUrl.value.trim();
  if (!url) return;
  els.dlgError.style.display = "none";
  try {
    await api("/api/feeds", { method: "POST", body: JSON.stringify({ url }) });
    els.addFeedDialog.close();
    els.dlgFeedUrl.value = "";
    showSuccess("Источник добавлен");
    await loadFeeds();
    await loadStats();
  } catch (e) {
    els.dlgError.textContent = e.message;
    els.dlgError.style.display = "block";
  }
}

async function refreshFeed(id) {
  try {
    await api(`/api/feeds/${id}/refresh`, { method: "POST" });
    showSuccess("Источник обновлен");
    await loadFeeds();
    await loadStats();
    loadArticles();
  } catch (e) { showError("Ошибка обновления: " + e.message); }
}

async function refreshAllFeeds() {
  try {
    await api("/api/feeds/refresh-all", { method: "POST" });
    showSuccess("Все источники обновлены");
    await loadFeeds();
    await loadStats();
    loadArticles();
  } catch (e) { showError("Ошибка обновления: " + e.message); }
}

async function deleteFeed(id) {
  if (!confirm("Удалить источник и все его публикации?")) return;
  try {
    await api(`/api/feeds/${id}`, { method: "DELETE" });
    if (state.activeFeedId === id) state.activeFeedId = null;
    await loadFeeds();
    await loadStats();
    loadArticles();
  } catch (e) { showError("Ошибка удаления: " + e.message); }
}

async function toggleRead(id, isRead) {
  try {
    await api(`/api/articles/${id}/read`, { method: "POST", body: JSON.stringify({ is_read: isRead }) });
    loadArticles();
    await loadStats();
  } catch (e) { showError("Ошибка: " + e.message); }
}

async function toggleFavorite(id, isFav) {
  try {
    await api(`/api/articles/${id}/favorite`, { method: "POST", body: JSON.stringify({ is_favorite: isFav }) });
    loadArticles();
    await loadStats();
  } catch (e) { showError("Ошибка: " + e.message); }
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

window.addEventListener("DOMContentLoaded", async () => {
  await loadFeeds();
  await loadStats();
  loadArticles();

  els.btnRefreshAll.onclick = refreshAllFeeds;
  els.btnRefreshCurrent.onclick = () => { if (state.activeFeedId) refreshFeed(state.activeFeedId); else refreshAllFeeds(); };
  els.btnAddFeed.onclick = () => els.addFeedDialog.showModal();
  els.dlgClose.onclick = () => els.addFeedDialog.close();
  els.dlgCancel.onclick = () => els.addFeedDialog.close();
  els.dlgAdd.onclick = addFeed;
  els.btnPrev.onclick = () => { if (state.page > 1) { state.page--; loadArticles(); } };
  els.btnNext.onclick = () => { if (state.page < state.pages) { state.page++; loadArticles(); } };

  els.searchInput.addEventListener("input", (e) => {
    state.filters.search = e.target.value;
    state.page = 1;
    loadArticles();
  });
  els.filterUnread.addEventListener("change", (e) => {
    state.filters.unread = e.target.checked;
    state.page = 1;
    loadArticles();
  });
  els.filterFavorites.addEventListener("change", (e) => {
    state.filters.favorites = e.target.checked;
    state.page = 1;
    loadArticles();
  });
});
