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
  "Market Share Insights": "Can you provide market share insights for IAM solutions?",
  "Technology Developments": "What are the recent technology developments in Security & IAM?",
  "Competitive Analysis": "How do major IAM vendors compare in terms of features and market presence?"
};

const state = {
  currentItems: [],
  allItems: [],
  search: "",
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
    : d.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric"
      });
};

async function loadJson(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`Could not load ${path}`);
  return r.json();
}

async function load() {
  const currentData = await loadJson("data/news.json");
  state.currentItems = Array.isArray(currentData.items) ? currentData.items : [];

  try {
    const allData = await loadJson("data/all_articles.json");
    state.allItems = Array.isArray(allData.items) ? allData.items : state.currentItems;
  } catch {
    state.allItems = state.currentItems;
  }

  document.getElementById("updated").textContent =
    `Updated ${fmt(currentData.generated_at)} · ${state.currentItems.length} selected items`;

  render();
}

function articleSections(item) {
  if (Array.isArray(item.sections) && item.sections.length) return item.sections;
  if (item.primary_section) return [item.primary_section];
  return [];
}

function sourceItems() {
  // Default dashboard = current weekly edition.
  // As soon as the user searches, search the complete accumulated archive.
  return state.search.trim() ? state.allItems : state.currentItems;
}

function visibleItems() {
  const query = state.search.trim().toLowerCase();

  return sourceItems()
    .filter(item => {
      const sectionMatch =
        state.section === "All" ||
        articleSections(item).includes(state.section);

      const haystack = [
        item.title,
        item.summary,
        item.source,
        ...(item.tags || []),
        ...articleSections(item)
      ].join(" ").toLowerCase();

      const searchMatch = !query || haystack.includes(query);

      return sectionMatch && searchMatch;
    })
    .sort((a, b) =>
      new Date(b.published_at) - new Date(a.published_at) ||
      (b.relevance || 0) - (a.relevance || 0)
    );
}

function countForSection(section) {
  return state.currentItems.filter(item =>
    articleSections(item).includes(section)
  ).length;
}

function render() {
  renderSections();
  renderNews();
}

function renderSections() {
  const grid = document.getElementById("sectionGrid");

  grid.innerHTML = SECTION_ORDER.map(section => {
    const active = state.section === section;

    return `
      <button
        class="section-filter ${active ? "active" : ""}"
        data-section="${esc(section)}"
        aria-pressed="${active}"
      >
        <div class="section-filter-heading">
          <h2>${esc(section)}</h2>
          <span class="section-count">${countForSection(section)}</span>
        </div>
        <p>${esc(QUESTIONS[section])}</p>
      </button>
    `;
  }).join("");

  grid.querySelectorAll(".section-filter").forEach(button => {
    button.addEventListener("click", () => {
      const selected = button.dataset.section;
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
  const searchingArchive = Boolean(state.search.trim());

  const heading = document.querySelector(".section-title-row h2");

  if (searchingArchive) {
    heading.textContent =
      state.section === "All"
        ? "Search results — current and archived articles"
        : `${state.section} — search results`;
  } else {
    heading.textContent =
      state.section === "All"
        ? "All selected articles"
        : state.section;
  }

  document.getElementById("resultCount").textContent =
    `${items.length} article${items.length === 1 ? "" : "s"}`;

  const grid = document.getElementById("newsGrid");

  if (!items.length) {
    grid.innerHTML = `
      <div class="empty-state">
        No matching article was found.
      </div>
    `;
    return;
  }

  grid.innerHTML = items.map(item => `
    <article class="news-card">
      <div class="meta">
        <span>${esc(item.source || "")}</span>
        <span>${fmt(item.published_at)}</span>
      </div>

      <h3>${esc(item.title)}</h3>
      <p>${esc(item.summary || "")}</p>

      <div class="tags">
        ${(item.tags || []).map(tag =>
          `<span>${esc(tag)}</span>`
        ).join("")}
      </div>

      <div class="bottom">
        <a
          href="${esc(item.url)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          Open original source →
        </a>
      </div>
    </article>
  `).join("");
}

document.getElementById("searchInput").addEventListener("input", event => {
  state.search = event.target.value;
  renderNews();
});

load().catch(error => {
  console.error(error);
  document.getElementById("updated").textContent =
    "Could not load the latest edition.";
});
