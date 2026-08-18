const state = { data: null, filter: "all", query: "", selected: null, tab: "sentiment" };
const REMOTE_DATA_URL = "https://lilidan-tradingagents.pages.dev/data/dashboard.json";

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;");

function category(item) {
  if (item.sentiment.delta == null) return "first";
  if (item.sentiment.delta >= 0.3) return "warming";
  if (item.sentiment.delta <= -0.3) return "cooling";
  return "stable";
}

function changeBadge(item) {
  const delta = item.sentiment.delta;
  if (delta == null) return '<span class="badge first">首次记录</span>';
  const kind = delta >= 0.3 ? "up" : delta <= -0.3 ? "down" : "stable";
  const arrow = delta >= 0.3 ? "↑" : delta <= -0.3 ? "↓" : "→";
  const sign = delta > 0 ? "+" : "";
  return `<span class="badge ${kind}">${arrow} ${escapeHtml(item.sentiment.change_label)} ${sign}${delta.toFixed(1)}</span>`;
}

function renderMetrics(items) {
  const scored = items.filter((item) => Number.isFinite(item.sentiment.score));
  const average = scored.length
    ? scored.reduce((sum, item) => sum + item.sentiment.score, 0) / scored.length
    : null;
  $("#coverage").textContent = items.length;
  $("#warming").textContent = items.filter((item) => category(item) === "warming").length;
  $("#cooling").textContent = items.filter((item) => category(item) === "cooling").length;
  $("#average").textContent = average == null ? "—" : average.toFixed(1);
}

function filteredItems() {
  const query = state.query.trim().toUpperCase();
  return state.data.symbols.filter((item) => {
    const matchesFilter = state.filter === "all" || category(item) === state.filter;
    const matchesQuery = !query || item.ticker.toUpperCase().includes(query);
    return matchesFilter && matchesQuery;
  });
}

function renderTable() {
  const items = filteredItems();
  $("#empty-state").hidden = items.length !== 0;
  $("#sentiment-table").innerHTML = items.map((item) => {
    const score = Number.isFinite(item.sentiment.score) ? item.sentiment.score.toFixed(1) : "—";
    return `
      <tr tabindex="0" data-ticker="${escapeHtml(item.ticker)}" aria-label="查看 ${escapeHtml(item.ticker)} 详情">
        <td><div class="ticker"><strong>${escapeHtml(item.ticker)}</strong><small>${escapeHtml(item.asset_type || "")} · ${escapeHtml(item.latest_date)}</small></div></td>
        <td><div class="score"><strong>${score}</strong><small>${escapeHtml(item.sentiment.band || "未知")}</small></div></td>
        <td>${changeBadge(item)}</td>
        <td class="narrative">${escapeHtml(item.sentiment.summary || "暂无舆情摘要")}</td>
        <td class="muted">${escapeHtml(item.sentiment.confidence_zh || "—")}</td>
        <td class="rating">${escapeHtml(item.rating || "—")}</td>
        <td class="muted">${escapeHtml(item.latest_date)}</td>
      </tr>`;
  }).join("");

  document.querySelectorAll("#sentiment-table tr").forEach((row) => {
    const open = () => openDetail(row.dataset.ticker);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
    });
  });
  if ($("#detail-dialog").open) renderDrawerList();
}

function renderDrawerList() {
  if (!state.data) return;
  const items = state.data.symbols;
  $("#drawer-count").textContent = `${items.length} 个重点标的 · 点击切换报告`;
  $("#drawer-list").innerHTML = items.map((item) => {
    const score = Number.isFinite(item.sentiment.score) ? item.sentiment.score.toFixed(1) : "—";
    const delta = item.sentiment.delta;
    const deltaLabel = delta == null ? "首次" : `${delta > 0 ? "+" : ""}${delta.toFixed(1)}`;
    const kind = delta == null ? "first" : delta >= 0.3 ? "up" : delta <= -0.3 ? "down" : "stable";
    const selected = state.selected?.ticker === item.ticker;
    return `
      <button class="drawer-item${selected ? " active" : ""}" type="button" role="option" aria-selected="${selected}" data-ticker="${escapeHtml(item.ticker)}">
        <span class="drawer-item-main"><strong>${escapeHtml(item.ticker)}</strong><span class="drawer-item-meta"><small>${escapeHtml(item.sentiment.band || "舆情未定")}</small><em>${escapeHtml(item.rating || "评级未定")}</em></span></span>
        <span class="drawer-item-score"><strong>${score}</strong><em class="drawer-delta ${kind}">${escapeHtml(deltaLabel)}</em></span>
      </button>`;
  }).join("");
  document.querySelectorAll(".drawer-item").forEach((button) => {
    button.addEventListener("click", () => openDetail(button.dataset.ticker));
  });
}

function renderHistory(item) {
  if (!item.history.length) return '<p class="muted">暂无历史记录。</p>';
  return `<div class="history-chart">${item.history.map((point) => `
    <div class="history-row">
      <span>${escapeHtml(point.date)}</span>
      <div class="history-track"><div class="history-fill" style="width:${Math.max(0, Math.min(100, point.score * 10))}%"></div></div>
      <strong>${Number.isFinite(point.score) ? point.score.toFixed(1) : "—"}</strong>
      <span class="history-band muted">${escapeHtml(point.band || "")}</span>
    </div>`).join("")}</div>`;
}

function renderDetailContent() {
  const item = state.selected;
  if (!item) return;
  document.querySelectorAll(".tab[data-tab]").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === state.tab));
  if (state.tab === "history") {
    $("#detail-content").innerHTML = renderHistory(item);
    return;
  }
  const rendered = item.reports_html?.[state.tab];
  if (rendered) {
    $("#detail-content").innerHTML = `<article class="markdown-body">${rendered}</article>`;
    return;
  }
  const text = item.reports?.[state.tab] || "本期没有生成这一章节。";
  $("#detail-content").innerHTML = `<pre class="report-text">${escapeHtml(text)}</pre>`;
}

function openDetail(ticker) {
  const item = state.data.symbols.find((entry) => entry.ticker === ticker);
  if (!item) return;
  state.selected = item;
  state.tab = "sentiment";
  $("#detail-date").textContent = `${item.latest_date} · ${item.asset_type || "研究标的"}`;
  $("#detail-title").textContent = item.ticker;
  $("#detail-summary").textContent = item.sentiment.summary || "暂无舆情摘要";
  const delta = item.sentiment.delta == null ? "首次记录" : `${item.sentiment.delta > 0 ? "+" : ""}${item.sentiment.delta.toFixed(1)}`;
  $("#full-report").href = item.report_url;
  renderDrawerList();
  renderDetailContent();
  if (!$("#detail-dialog").open) $("#detail-dialog").showModal();
}

async function init() {
  try {
    // The source dashboard directory intentionally contains only the UI assets;
    // generated data lives under site-dist/data on Pages. When someone opens
    // dashboard/index.html directly from Finder/IDE, resolve the data remotely
    // instead of making a file:// request that browsers reject via CORS.
    const dataUrl = window.location.protocol === "file:"
      ? REMOTE_DATA_URL
      : "./data/dashboard.json";
    const response = await fetch(dataUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    renderMetrics(state.data.symbols);
    renderTable();
    $("#freshness").textContent = `更新于 ${state.data.generated_at_display}`;
  } catch (error) {
    $("#freshness").textContent = "数据暂时不可用";
    $("#empty-state").hidden = false;
    $("#empty-state").textContent = `仪表盘数据读取失败：${error.message}`;
  }
}

$("#filters").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button || !state.data) return;
  state.filter = button.dataset.filter;
  document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === button));
  renderTable();
});

$("#search").addEventListener("input", (event) => { state.query = event.target.value; if (state.data) renderTable(); });
$("#close-dialog").addEventListener("click", () => $("#detail-dialog").close());
$("#close-dialog-icon").addEventListener("click", () => $("#detail-dialog").close());
$("#detail-dialog").addEventListener("click", (event) => { if (event.target === event.currentTarget) event.currentTarget.close(); });
document.querySelector(".tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("button[data-tab]");
  if (!tab) return;
  state.tab = tab.dataset.tab;
  renderDetailContent();
});

init();
