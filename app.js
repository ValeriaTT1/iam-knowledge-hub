const SECTION_ORDER = [
  "Latest IAM Trends",
  "Top Security Vendors",
  "Emerging Threats",
  "Market Share Insights",
  "Technology Developments",
  "Competitive Analysis"
];

const QUESTIONS = {
  "Latest IAM Trends": "What are the latest trends in Identity & Access Management?",
  "Top Security Vendors": "Who are the leading vendors in the Security & IAM market?",
  "Emerging Threats": "What new threats are emerging in the Security & IAM space?",
  "Market Share Insights": "What market-positioning or adoption signals are visible for IAM solutions?",
  "Technology Developments": "What are the recent technology developments in Security & IAM?",
  "Competitive Analysis": "How do major IAM vendors compare in capabilities, positioning and market presence?"
};

const state = {
  items: [],
  search: "",
  tag: "All",
  section: "All"
};

const esc = (v = "") =>
  String(v).replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[c]));

const fmt = value => {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
};

async function load() {
  const r = await fetch("data/news.json", { cache: "no-store" });
  if (!r.ok) throw new Error("Could not load news");
  const data = await r.json();

  state.items = Array.isArray(data.items) ? data.items : [];

  document.getElementById("updated").textContent =
    `Updated ${fmt(data.generated_at)} · ${state.items.length} selected items`;

  renderTags();
  render();
}

function renderTags() {
  const tags = new Set();
  state.items.forEach(i => (i.tags || []).forEach(t => tags.add(t)));

  const select = document.getElementById("tagFilter");
  select.innerHTML =
    `<option value="All">All IAM topics</option>` +
    [...tags].sort().map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
}

function articleSections(item) {
  if (Array.isArray(item.sections) && item.sections.length) return item.sections;
  if (item.primary_section) return [item.primary_section];
  return [];
}

function visibleItems() {
  const q = state.search.toLowerCase().trim();

  return state.items
    .filter(i => {
      const matchesTag =
        state.tag === "All" || (i.tags || []).includes(state.tag);

      const matchesSection =
        state.section === "All" || articleSections(i).includes(state.section);

      const haystack = [
        i.title,
        i.summary,
        i.source,
        i.primary_section,
        ...articleSections(i),
        ...(i.tags || [])
      ].join(" ").toLowerCase();

      const matchesSearch = !q || haystack.includes(q);

      return matchesTag && matchesSection && matchesSearch;
    })
    .sort((a, b) =>
      (b.relevance || 0) - (a.relevance || 0) ||
      new Date(b.published_at) - new Date(a.published_at)
    );
}

function countForSection(section) {
  return state.items.filter(i => articleSections(i).includes(section)).length;
}

function render() {
  renderSections();
  renderNews();
}

function renderSections() {
  const grid = document.getElementById("sectionGrid");

  grid.innerHTML = SECTION_ORDER.map(section => {
    const count = countForSection(section);
    const isActive = state.section === section;

    return `
      <button class="section-card ${isActive ? "active" : ""}"
              data-section="${esc(section)}"
              aria-pressed="${isActive}">
        <div>
          <div class="section-card-top">
            <h2>${esc(section)}</h2>
            <span class="section-count">${count}</span>
          </div>
          <div class="question">${esc(QUESTIONS[section])}</div>
        </div>
        <div class="section-card-footer">
          <span>${isActive ? "Showing this topic" : "View articles"}</span>
          <span aria-hidden="true">→</span>
        </div>
      </button>`;
  }).join("");

  grid.querySelectorAll(".section-card").forEach(card => {
    card.addEventListener("click", () => {
      const selected = card.dataset.section;

      // Clicking the active card again resets to All.
      state.section = state.section === selected ? "All" : selected;

      render();

      document.querySelector(".latest-wrap")?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    });
  });
}

function renderNews() {
  const items = visibleItems();
  const title = document.querySelector(".section-title-row h2");

  if (title) {
    title.textContent =
      state.section === "All"
        ? "All selected articles"
        : state.section;
  }

  const count = document.getElementById("resultCount");
  count.textContent = `${items.length} article${items.length === 1 ? "" : "s"}`;

  const grid = document.getElementById("newsGrid");

  if (!items.length) {
    grid.innerHTML = `
      <div class="empty-state">
        No article is currently mapped to this topic.
      </div>`;
    return;
  }

  grid.innerHTML = items.map(i => `
    <article class="news-card">
      <div class="meta">
        <span class="pill">${esc(i.primary_section || "IAM")}</span>
        <span>${esc(i.source || "")}</span>
        <span>${fmt(i.published_at)}</span>
      </div>

      <h3>${esc(i.title)}</h3>
      <p>${esc(i.summary || "")}</p>

      <div class="article-sections">
        ${articleSections(i).map(s => `<span>${esc(s)}</span>`).join("")}
      </div>

      <div class="tags">
        ${(i.tags || []).map(t => `<span>${esc(t)}</span>`).join("")}
      </div>

      <div class="bottom">
        <a href="${esc(i.url)}" target="_blank" rel="noopener noreferrer">
          Open original source →
        </a>
      </div>
    </article>
  `).join("");
}

document.getElementById("searchInput").addEventListener("input", e => {
  state.search = e.target.value;
  renderNews();
});

document.getElementById("tagFilter").addEventListener("change", e => {
  state.tag = e.target.value;
  renderNews();
});

load().catch(err => {
  console.error(err);
  document.getElementById("updated").textContent = "Could not load the latest edition.";
});
