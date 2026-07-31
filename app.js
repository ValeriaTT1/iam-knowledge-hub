const state = {
  items: [],
  category: "All",
  search: "",
  sort: "relevance"
};

const esc = (value = "") =>
  String(value).replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
  }[ch]));

const fmtDate = value => {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
};

async function loadData() {
  const response = await fetch("data/news.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Could not load news.json");
  const data = await response.json();
  state.items = Array.isArray(data.items) ? data.items : [];
  document.getElementById("updated").textContent =
    `Updated ${fmtDate(data.generated_at)} · ${state.items.length} selected items`;
  renderAll();
}

function renderAll() {
  renderFilters();
  renderStudyTopics();
  renderFeatured();
  renderGrid();
}

function categories() {
  const counts = new Map();
  for (const item of state.items) {
    const category = item.category || "Other";
    counts.set(category, (counts.get(category) || 0) + 1);
  }
  return [["All", state.items.length], ...[...counts.entries()].sort((a,b) => a[0].localeCompare(b[0]))];
}

function renderFilters() {
  const container = document.getElementById("categoryFilters");
  container.innerHTML = categories().map(([name, count]) => `
    <button class="filter-button ${state.category === name ? "active" : ""}" data-category="${esc(name)}">
      <span>${esc(name)}</span><span>${count}</span>
    </button>
  `).join("");
  container.querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      state.category = button.dataset.category;
      renderAll();
    });
  });
}

function filteredItems() {
  const term = state.search.trim().toLowerCase();
  let items = state.items.filter(item => {
    const inCategory = state.category === "All" || item.category === state.category;
    const haystack = [
      item.title, item.summary, item.source, item.category,
      item.why_it_matters, item.study_topic, ...(item.tags || [])
    ].join(" ").toLowerCase();
    return inCategory && (!term || haystack.includes(term));
  });
  items.sort((a,b) => {
    if (state.sort === "newest") return new Date(b.published_at) - new Date(a.published_at);
    return (b.relevance || 0) - (a.relevance || 0) || new Date(b.published_at) - new Date(a.published_at);
  });
  return items;
}

function renderFeatured() {
  const container = document.getElementById("featured");
  const item = [...state.items].sort((a,b) => (b.relevance || 0) - (a.relevance || 0))[0];
  if (!item) { container.innerHTML = ""; return; }
  container.innerHTML = `
    <article class="featured-card">
      <div class="featured-card-content">
        <div class="meta">
          <span class="tag">${esc(item.category || "IAM")}</span>
          <span>${esc(item.source || "")}</span>
          <span>${fmtDate(item.published_at)}</span>
        </div>
        <h2>${esc(item.title)}</h2>
        <p>${esc(item.summary || "")}</p>
        ${item.why_it_matters ? `<p><strong>Why it matters:</strong> ${esc(item.why_it_matters)}</p>` : ""}
        <a class="read-link" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">Read original source →</a>
      </div>
    </article>`;
}

function renderStudyTopics() {
  const topics = [];
  for (const item of [...state.items].sort((a,b) => (b.relevance || 0) - (a.relevance || 0))) {
    if (item.study_topic && !topics.some(t => t.topic === item.study_topic)) {
      topics.push({ topic: item.study_topic, category: item.category });
    }
    if (topics.length === 4) break;
  }
  document.getElementById("studyTopics").innerHTML =
    topics.length ? topics.map(t => `
      <div class="study-item">
        <strong>${esc(t.topic)}</strong>
        <span>${esc(t.category || "IAM")}</span>
      </div>`).join("")
    : `<div class="study-item"><span>Study recommendations will appear after the first update.</span></div>`;
}

function renderGrid() {
  const items = filteredItems();
  document.getElementById("resultCount").textContent = `${items.length} article${items.length === 1 ? "" : "s"}`;
  document.getElementById("emptyState").hidden = items.length > 0;
  document.getElementById("newsGrid").innerHTML = items.map(item => `
    <article class="news-card">
      <div class="meta">
        <span class="tag">${esc(item.category || "Other")}</span>
        <span>${esc(item.source || "")}</span>
        <span>${fmtDate(item.published_at)}</span>
      </div>
      <h3>${esc(item.title)}</h3>
      <p>${esc(item.summary || "")}</p>
      ${item.why_it_matters ? `<p class="why"><strong>Why it matters:</strong> ${esc(item.why_it_matters)}</p>` : ""}
      <div class="card-bottom">
        <a class="read-link" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">Open article →</a>
      </div>
    </article>
  `).join("");
}

document.getElementById("searchInput").addEventListener("input", event => {
  state.search = event.target.value;
  renderGrid();
});
document.getElementById("sortSelect").addEventListener("change", event => {
  state.sort = event.target.value;
  renderGrid();
});

loadData().catch(error => {
  console.error(error);
  document.getElementById("updated").textContent = "The latest edition could not be loaded.";
  document.getElementById("emptyState").hidden = false;
  document.getElementById("emptyState").textContent = "Could not load the news data.";
});
