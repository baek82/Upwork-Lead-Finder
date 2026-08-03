let allLeads = [];

const el = {
  meta: document.getElementById("meta"),
  leads: document.getElementById("leads"),
  search: document.getElementById("search"),
  recurringOnly: document.getElementById("recurringOnly"),
  minScore: document.getElementById("minScore"),
  sortBy: document.getElementById("sortBy"),
};

function scoreClass(score) {
  if (score >= 50) return "score-high";
  if (score >= 25) return "score-mid";
  return "score-low";
}

function render() {
  const q = el.search.value.trim().toLowerCase();
  const recurringOnly = el.recurringOnly.checked;
  const minScore = Number(el.minScore.value) || 0;
  const sortBy = el.sortBy.value;

  let filtered = allLeads.filter((lead) => {
    if (lead.score < minScore) return false;
    if (recurringOnly && !lead.is_recurring) return false;
    if (q) {
      const haystack = `${lead.title} ${lead.snippet}`.toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    if (sortBy === "date") {
      return new Date(b.pub_date) - new Date(a.pub_date);
    }
    return b.score - a.score;
  });

  el.leads.innerHTML = "";
  if (filtered.length === 0) {
    el.leads.innerHTML = '<p class="empty">No leads match these filters yet.</p>';
    return;
  }

  for (const lead of filtered) {
    const card = document.createElement("article");
    card.className = "lead";

    const budget = lead.budget_hint
      ? `$${lead.budget_hint.toLocaleString()}`
      : null;

    card.innerHTML = `
      <div class="lead-top">
        <a class="lead-title" href="${lead.link}" target="_blank" rel="noopener">${escapeHtml(lead.title)}</a>
        <span class="score-badge ${scoreClass(lead.score)}">${lead.score}</span>
      </div>
      <p class="lead-snippet">${escapeHtml(lead.snippet)}</p>
      <div class="lead-tags">
        <span class="tag">${escapeHtml(lead.source_feed)}</span>
        ${lead.is_recurring ? '<span class="tag">recurring</span>' : ""}
        ${budget ? `<span class="tag">${budget}</span>` : ""}
        <span class="tag">${formatDate(lead.pub_date)}</span>
      </div>
    `;
    el.leads.appendChild(card);
  }
}

function formatDate(pubDate) {
  const d = new Date(pubDate);
  if (isNaN(d)) return "";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

async function load() {
  try {
    const res = await fetch("data/leads.json", { cache: "no-store" });
    const data = await res.json();
    allLeads = data.leads || [];
    el.meta.textContent = data.generated_at
      ? `${allLeads.length} leads · last updated ${new Date(data.generated_at).toLocaleString()}`
      : "No data yet — add RSS feed URLs to config/feeds.json and run the fetch workflow.";
    render();
  } catch (err) {
    el.meta.textContent = "Could not load leads.json";
  }
}

[el.search, el.recurringOnly, el.minScore, el.sortBy].forEach((input) =>
  input.addEventListener("input", render)
);

load();
