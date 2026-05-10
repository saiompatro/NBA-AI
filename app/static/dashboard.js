const socket = io();

const state = {
  analytics: null,
  live: null,
  conference: "Eastern",
  leader: "pts",
  playerFilter: "ALL",
  predictions: {},
  news: {},
};

const els = {
  dataUpdated: document.getElementById("dataUpdated"),
  kpiGrid: document.getElementById("kpiGrid"),
  standingsBody: document.getElementById("standingsBody"),
  scheduleDate: document.getElementById("scheduleDate"),
  upcomingList: document.getElementById("upcomingList"),
  liveStatusBody: document.getElementById("liveStatusBody"),
  leadersList: document.getElementById("leadersList"),
  spotlightPanel: document.getElementById("spotlightPanel"),
  teamFormBody: document.getElementById("teamFormBody"),
  sentimentBody: document.getElementById("sentimentBody"),
  livePage: document.getElementById("livePage"),
  fullStandings: document.getElementById("fullStandings"),
  playerTeamFilter: document.getElementById("playerTeamFilter"),
  playersGrid: document.getElementById("playersGrid"),
  teamsGrid: document.getElementById("teamsGrid"),
  teamDetailPage: document.getElementById("teamDetailPage"),
  playerDetailPage: document.getElementById("playerDetailPage"),
  alertsPage: document.getElementById("alertsPage"),
  predictionsPage: document.getElementById("predictionsPage"),
  settingsPage: document.getElementById("settingsPage"),
};

const statLabel = {
  pts: "PTS",
  reb: "REB",
  ast: "AST",
  stl: "STL",
  blk: "BLK",
};

function html(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pct(value) {
  const numeric = Number(value || 0);
  return numeric < 1 ? numeric.toFixed(3).replace(/^0/, "") : numeric.toFixed(1);
}

function formatTime(dateValue) {
  if (!dateValue) return "TBD";
  return new Date(dateValue).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatDate(dateValue) {
  if (!dateValue) return "TBD";
  return new Date(dateValue).toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
}

function teamMap() {
  return Object.fromEntries((state.analytics?.teams || []).map((team) => [team.abbr, team]));
}

function teamBySlug(slug) {
  return (state.analytics?.teams || []).find((team) => team.slug === slug);
}

function playerByRoute(slug) {
  const players = state.analytics?.players || [];
  const id = slug.match(/-(\d+)$/)?.[1];
  return players.find((player) => String(player.id) === id) || players.find((player) => player.slug === slug);
}

function playerRoute(player) {
  return `#/players/${player.slug}-${player.id}`;
}

function predictionKey(game) {
  return `${game.away}-${game.home}-${game.date || game.matchup}`;
}

function newsKey(type, id) {
  return `${type}:${id}`;
}

function setActivePage(pageId, navKey) {
  document.querySelectorAll(".page").forEach((page) => page.classList.toggle("active", page.id === pageId));
  document.querySelectorAll(".side-link").forEach((link) => link.classList.toggle("active", link.dataset.nav === navKey));
}

function isLiveRoute() {
  return location.hash.replace(/^#\/?/, "") === "live";
}

function route() {
  const path = location.hash.replace(/^#\/?/, "") || location.pathname.replace(/^\/+/, "") || "table";
  const [section, slug] = path.split("/");

  if (!state.analytics && !["table", "live"].includes(section)) {
    setActivePage("dashboardPage", "table");
    return;
  }

  if (section === "players" && slug) {
    renderPlayerDetail(slug);
    setActivePage("playerDetailPage", "players");
    return;
  }
  if (section === "teams" && slug) {
    renderTeamDetail(slug);
    setActivePage("teamDetailPage", "teams");
    return;
  }
  if (section === "players") {
    renderPlayersPage();
    setActivePage("playersPage", "players");
    return;
  }
  if (section === "teams") {
    renderTeamsPage();
    setActivePage("teamsPage", "teams");
    return;
  }
  if (section === "standings") {
    renderFullStandings();
    setActivePage("tablePage", "table");
    return;
  }
  if (section === "live") {
    renderLivePage();
    setActivePage("livePage", "live");
    return;
  }
  if (section === "alerts") {
    renderAlertsPage();
    setActivePage("alertsPage", "alerts");
    return;
  }
  if (section === "predictions") {
    renderPredictionsPage();
    setActivePage("predictionsPage", "predictions");
    return;
  }
  if (section === "settings") {
    renderSettingsPage();
    setActivePage("settingsPage", "settings");
    return;
  }
  setActivePage("dashboardPage", "table");
}

function renderAll() {
  if (!state.analytics) return;
  els.dataUpdated.textContent = new Date(state.analytics.generated_at).toLocaleTimeString();
  renderKpis();
  renderStandings();
  renderUpcomingGames();
  renderLiveStatus();
  renderLeaders();
  renderSpotlight();
  renderTeamForm();
  renderSentiment();
  renderFilter();
  route();
}

function renderKpis() {
  const gamesToday = (state.analytics?.upcoming_games || []).filter((game) => {
    const gameDate = new Date(game.date).toDateString();
    return gameDate === new Date().toDateString();
  }).length;
  const cards = [
    { icon: "trophy", tone: "#fff4d9", color: "#f7a614", value: "16", label: "Playoff Teams" },
    { icon: "calendar", tone: "#eaf1ff", color: "#075ed9", value: state.live?.is_live ? "1" : "--", label: "Live Games" },
    { icon: "ball", tone: "#fff0e8", color: "#f26b1d", value: gamesToday, label: "Games Today" },
    { icon: "trend", tone: "#ffeee7", color: "#f26b1d", value: "78.4%", label: "Model Accuracy" },
    { icon: "database", tone: "#e8f8ef", color: "#16a05d", value: "2.1M+", label: "Events Analyzed" },
  ];
  els.kpiGrid.innerHTML = cards
    .map((card) => `
      <article class="kpi-card">
        <span class="kpi-icon" style="background:${card.tone};color:${card.color}">${iconSvg(card.icon)}</span>
        <div><strong>${card.value}</strong><span>${card.label}</span></div>
      </article>
    `)
    .join("");
}

function iconSvg(name) {
  const icons = {
    trophy: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4h8v4a4 4 0 0 1-8 0V4Z"/><path d="M6 5H4v3a4 4 0 0 0 4 4"/><path d="M18 5h2v3a4 4 0 0 1-4 4"/><path d="M12 12v5"/><path d="M8 20h8"/><path d="M10 17h4"/></svg>',
    calendar: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14v15H5z"/><path d="M8 3v4M16 3v4M5 10h14"/><path d="M9 14h.1M12 14h.1M15 14h.1M9 17h.1M12 17h.1"/></svg>',
    ball: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/><path d="M5.6 5.6c4 2.4 8.8 2.4 12.8 0M5.6 18.4c4-2.4 8.8-2.4 12.8 0"/></svg>',
    trend: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 17 10 11l4 4 6-8"/><path d="M15 7h5v5"/></svg>',
    database: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/></svg>',
  };
  return icons[name] || "";
}

function renderStandings() {
  const rows = (state.analytics.teams || [])
    .filter((team) => team.conference === state.conference)
    .sort((a, b) => a.seed - b.seed);
  els.standingsBody.innerHTML = rows
    .map((team) => `
      <tr>
        <td>${team.seed}</td>
        <td>
          <a class="team-cell" href="#/teams/${team.slug}">
            <img class="logo" src="${team.logo}" alt="" />
            <span>${html(team.team)}</span>
          </a>
        </td>
        <td>${team.wins}</td>
        <td>${team.losses}</td>
        <td>${pct(team.pct)}</td>
        <td>${team.gb}</td>
        <td class="${String(team.streak).startsWith("W") ? "streak-win" : "streak-loss"}">${team.streak}</td>
      </tr>
    `)
    .join("");
}

function renderUpcomingGames() {
  const teams = teamMap();
  const games = state.analytics.upcoming_games || [];
  els.scheduleDate.textContent = games[0] ? formatDate(games[0].date) : "Schedule";
  els.upcomingList.innerHTML = games.slice(0, 5).map((game) => {
    const away = teams[game.away] || {};
    const home = teams[game.home] || {};
    const pickTeam = Number(home.net || 0) >= Number(away.net || 0) ? home : away;
    const confidence = Math.min(78, Math.max(56, 61 + Math.abs(Number(home.net || 0) - Number(away.net || 0))));
    return `
      <div class="game-row">
        <time>${formatTime(game.date)}</time>
        <div class="game-matchup">
          <a class="game-team" href="#/teams/${away.slug || ""}">
            ${away.logo ? `<img class="logo" src="${away.logo}" alt="" />` : ""}
            <strong>${html(away.team || game.away || "Away")}</strong><span>${game.away}</span>
          </a>
          <a class="game-team" href="#/teams/${home.slug || ""}">
            ${home.logo ? `<img class="logo" src="${home.logo}" alt="" />` : ""}
            <strong>${html(home.team || game.home || "Home")}</strong><span>${game.home}</span>
          </a>
        </div>
        <div class="game-pick">${pickTeam.abbr || "TBD"}<br />${confidence.toFixed(0)}%</div>
      </div>
    `;
  }).join("");
}

function renderLiveStatus() {
  if (state.live?.is_live) {
    els.liveStatusBody.innerHTML = `
      <div>
        <div class="live-symbol"></div>
        <strong>${html(state.live.away_team)} ${state.live.away_score} @ ${html(state.live.home_team)} ${state.live.home_score}</strong>
        <p>${html(state.live.game_status || "Live game in progress")}</p>
      </div>
    `;
    return;
  }
  els.liveStatusBody.innerHTML = `
    <div>
      <div class="live-symbol"></div>
      <strong>No Current Live Match</strong>
      <p>There are no live NBA games at the moment.<br />Check upcoming games or explore analytics.</p>
    </div>
  `;
}

function renderLivePage() {
  const snapshot = state.live;
  const model = snapshot?.shot_quality_model || {};
  const context = model.context || {};
  const events = snapshot?.events || [];
  const homeWin = Math.round(Number(snapshot?.home_win_probability || 0) * 100);
  const awayWin = Math.round(Number(snapshot?.away_win_probability || 0) * 100);
  const shotQuality = Math.round(Number(snapshot?.shot_quality || model.shot_quality || 0) * 100);

  if (!snapshot) {
    els.livePage.innerHTML = `
      <div class="page-heading">
        <div>
          <h1>Live Play-by-Play Detector</h1>
          <p>Waiting for the NBA live scoreboard and play-by-play feed.</p>
        </div>
      </div>
      <article class="panel live-detector-empty">
        <div class="live-symbol"></div>
        <strong>Connecting to live data</strong>
        <p>The detector will update as soon as the first live snapshot arrives.</p>
      </article>
    `;
    return;
  }

  if (!snapshot.is_live) {
    els.livePage.innerHTML = `
      <div class="page-heading">
        <div>
          <h1>Live Play-by-Play Detector</h1>
          <p>${html(snapshot.message || "No NBA game is currently live.")}</p>
        </div>
        <span class="sentiment-pill neutral">${html(snapshot.source || "nba_api live scoreboard")}</span>
      </div>
      <article class="panel live-detector-empty">
        <div class="live-symbol"></div>
        <strong>No Current Live Match</strong>
        <p>The detector is ready and will switch on when the scoreboard reports an in-progress game.</p>
      </article>
    `;
    return;
  }

  els.livePage.innerHTML = `
    <div class="page-heading">
      <div>
        <h1>Live Play-by-Play Detector</h1>
        <p>${html(snapshot.away_team)} ${snapshot.away_score} @ ${html(snapshot.home_team)} ${snapshot.home_score} - Q${snapshot.period} ${html(snapshot.clock)}</p>
      </div>
      <span class="sentiment-pill positive">Live</span>
    </div>
    <section class="live-detector-grid">
      <article class="panel live-score-panel">
        <div class="panel-heading"><h2>Current Game</h2><span>${html(snapshot.game_id)}</span></div>
        <div class="scoreboard-strip">
          <div><span>${html(snapshot.away_team)}</span><strong>${snapshot.away_score}</strong></div>
          <div><span>${html(snapshot.home_team)}</span><strong>${snapshot.home_score}</strong></div>
        </div>
        <div class="detector-stats">
          <div><span>Possession</span><strong>${html(snapshot.possession)}</strong></div>
          <div><span>Score Diff</span><strong>${Number(snapshot.score_diff) > 0 ? "+" : ""}${snapshot.score_diff}</strong></div>
          <div><span>Away Fouls</span><strong>${snapshot.away_fouls}</strong></div>
          <div><span>Home Fouls</span><strong>${snapshot.home_fouls}</strong></div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-heading"><h2>Win Probability</h2><span>Model output</span></div>
        <div class="probability-row"><span>${html(snapshot.away_team)}</span><div><i style="width:${awayWin}%"></i></div><strong>${awayWin}%</strong></div>
        <div class="probability-row"><span>${html(snapshot.home_team)}</span><div><i style="width:${homeWin}%"></i></div><strong>${homeWin}%</strong></div>
        <div class="shot-quality-meter">
          <span>Shot Quality</span>
          <strong>${shotQuality}%</strong>
          <div><i style="width:${shotQuality}%"></i></div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-heading"><h2>Play-by-Play Events</h2><span>${html(model.source || snapshot.source)}</span></div>
        <div class="event-list">
          ${events.map((event) => `<div class="event-row">${html(event)}</div>`).join("")}
        </div>
      </article>
      <article class="panel">
        <div class="panel-heading"><h2>Shot Context</h2><span>Detector inputs</span></div>
        <div class="detector-stats">
          <div><span>Distance</span><strong>${context.distance ?? "--"}</strong></div>
          <div><span>Angle</span><strong>${context.angle ?? "--"}</strong></div>
          <div><span>Defender Dist.</span><strong>${context.defender_distance ?? "--"}</strong></div>
          <div><span>Shot Clock</span><strong>${context.shot_clock ?? "--"}</strong></div>
          <div><span>Situation</span><strong>${context.game_situation ?? "--"}</strong></div>
          <div><span>Updated</span><strong>${new Date(snapshot.updated_at).toLocaleTimeString()}</strong></div>
        </div>
      </article>
    </section>
  `;
}

function renderLeaders() {
  const rows = state.analytics.leaders?.[state.leader] || [];
  els.leadersList.innerHTML = rows.map((player, index) => `
    <a class="leader-row" href="${playerRoute(player)}">
      <span>${index + 1}</span>
      <span class="player-mini">
        <img class="headshot" src="${player.headshot}" alt="" />
        <b>${html(player.player)}</b>
      </span>
      <small>${player.team}</small>
      <strong>${player[state.leader]}</strong>
    </a>
  `).join("");
}

function renderSpotlight() {
  const player = [...(state.analytics.players || [])].sort((a, b) => b.impact - a.impact)[0];
  if (!player) return;
  els.spotlightPanel.innerHTML = `
    <div class="panel-heading"><h2>Player Spotlight</h2></div>
    <div class="spotlight-header">
      <img src="${player.headshot}" alt="" />
      <div>
        <h3>${html(player.player)}</h3>
        <p>${player.team_name} - ${player.role} - #${player.rotation_rank}</p>
      </div>
    </div>
    <div class="stat-strip">
      <div><strong>${player.pts}</strong><span>PPG</span></div>
      <div><strong>${player.reb}</strong><span>RPG</span></div>
      <div><strong>${player.ast}</strong><span>APG</span></div>
      <div><strong>${player.stl}</strong><span>SPG</span></div>
    </div>
    <div class="mini-panels">
      <div class="mini-panel">
        <h4>Sentiment (Last 7 Days)</h4>
        <strong class="${player.sentiment.label.toLowerCase()}">${player.sentiment.label}</strong>
        <div class="sentiment-bar"><span style="width:${Math.max(15, (player.sentiment.score + 1) * 50)}%"></span></div>
      </div>
      <div class="mini-panel">
        <h4>PPG Last 5 Games</h4>
        ${sparkline(player.trend, "#16a05d")}
      </div>
    </div>
    <a class="panel-link" href="${playerRoute(player)}">View Full Player Profile <span aria-hidden="true">-></span></a>
  `;
}

function renderTeamForm() {
  const rows = [...(state.analytics.teams || [])].sort((a, b) => b.net - a.net).slice(0, 8);
  els.teamFormBody.innerHTML = rows.map((team) => `
    <tr>
      <td><a class="team-cell" href="#/teams/${team.slug}"><img class="logo" src="${team.logo}" alt="" />${html(team.abbr)}</a></td>
      <td>${team.last10}</td>
      <td>${Number(team.last10.split("-")[0]) / 10}</td>
      <td>${team.pts}</td>
      <td>${(team.pts - team.net).toFixed(1)}</td>
      <td class="${team.net >= 0 ? "positive" : "concern"}">${team.net > 0 ? "+" : ""}${team.net}</td>
      <td class="${String(team.streak).startsWith("W") ? "streak-win" : "streak-loss"}">${team.streak}</td>
    </tr>
  `).join("");
}

function renderSentiment() {
  const players = state.analytics.players || [];
  const positive = players.filter((player) => player.sentiment.label === "Positive").length;
  const neutral = players.filter((player) => player.sentiment.label === "Neutral").length;
  const concern = players.filter((player) => player.sentiment.label === "Concern").length;
  const total = Math.max(players.length, 1);
  const positivePct = Math.round((positive / total) * 100) || 56;
  const neutralPct = Math.round((neutral / total) * 100) || 25;
  const concernPct = Math.max(0, 100 - positivePct - neutralPct) || 19;
  els.sentimentBody.innerHTML = `
    <div class="donut" style="background:conic-gradient(var(--green) 0 ${positivePct}%, #cdd2d9 ${positivePct}% ${positivePct + neutralPct}%, var(--red) ${positivePct + neutralPct}% 100%)">
      <div><strong>${positivePct}%</strong><span>Positive</span></div>
    </div>
    <div class="legend">
      <div class="legend-row"><span class="legend-dot" style="background:var(--green)"></span><span>Positive</span><strong>${positivePct}%</strong></div>
      <div class="legend-row"><span class="legend-dot" style="background:#cdd2d9"></span><span>Neutral</span><strong>${neutralPct}%</strong></div>
      <div class="legend-row"><span class="legend-dot" style="background:var(--red)"></span><span>Negative</span><strong>${concernPct}%</strong></div>
    </div>
  `;
}

function renderFilter() {
  const options = [`<option value="ALL">All Playoff Teams</option>`]
    .concat((state.analytics.teams || []).map((team) => `<option value="${team.abbr}">${team.team}</option>`));
  els.playerTeamFilter.innerHTML = options.join("");
  els.playerTeamFilter.value = state.playerFilter;
}

function renderFullStandings() {
  els.fullStandings.innerHTML = ["Eastern", "Western"].map((conference) => {
    const rows = (state.analytics.teams || []).filter((team) => team.conference === conference).sort((a, b) => a.seed - b.seed);
    return `
      <article class="panel">
        <div class="panel-heading"><h2>${conference} Conference</h2></div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>#</th><th>Team</th><th>Record</th><th>Playoffs</th><th>PTS</th><th>NET</th><th>Sentiment</th></tr></thead>
            <tbody>${rows.map((team) => `
              <tr>
                <td>${team.seed}</td>
                <td><a class="team-cell" href="#/teams/${team.slug}"><img class="logo" src="${team.logo}" alt="" />${html(team.team)}</a></td>
                <td>${team.record}</td>
                <td>${team.playoff_record}</td>
                <td>${team.pts}</td>
                <td class="${team.net >= 0 ? "positive" : "concern"}">${team.net > 0 ? "+" : ""}${team.net}</td>
                <td><span class="sentiment-pill ${team.sentiment.label.toLowerCase()}">${team.sentiment.label}</span></td>
              </tr>
            `).join("")}</tbody>
          </table>
        </div>
      </article>
    `;
  }).join("");
}

function renderPlayersPage() {
  const rows = (state.analytics.players || [])
    .filter((player) => state.playerFilter === "ALL" || player.team === state.playerFilter)
    .sort((a, b) => a.team.localeCompare(b.team) || a.rotation_rank - b.rotation_rank);
  els.playersGrid.innerHTML = rows.map((player) => `
    <a class="player-card" href="${playerRoute(player)}">
      <img src="${player.headshot}" alt="" />
      <div>
        <div class="card-top">
          <div>
            <h3>${html(player.player)}</h3>
            <p>${player.team_name} - ${player.team}</p>
          </div>
          <span class="role-badge">${player.role}</span>
        </div>
        <div class="card-stats">
          <div><span>PTS</span><strong>${player.pts}</strong></div>
          <div><span>REB</span><strong>${player.reb}</strong></div>
          <div><span>AST</span><strong>${player.ast}</strong></div>
        </div>
      </div>
    </a>
  `).join("");
}

function renderTeamsPage() {
  els.teamsGrid.innerHTML = (state.analytics.teams || []).map((team) => `
    <a class="team-card" href="#/teams/${team.slug}" style="--team-primary:${team.primary}">
      <div class="card-top">
        <div class="card-team">
          <img src="${team.logo}" alt="" />
          <div>
            <h3>${html(team.team)}</h3>
            <p>${team.conference} Conference - ${team.record}</p>
          </div>
        </div>
        <span class="seed-badge">#${team.seed}</span>
      </div>
      <div class="card-stats">
        <div><span>PTS</span><strong>${team.pts}</strong></div>
        <div><span>NET</span><strong class="${team.net >= 0 ? "positive" : "concern"}">${team.net > 0 ? "+" : ""}${team.net}</strong></div>
        <div><span>FORM</span><strong>${team.last10}</strong></div>
      </div>
    </a>
  `).join("");
}

function formatArticleDate(value) {
  if (!value) return "Latest update";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Latest update";
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function renderNewsContent(key) {
  const item = state.news[key];
  if (!item || item.loading) {
    return `<div class="news-empty">Loading latest news...</div>`;
  }
  if (item.error) {
    return `<div class="news-empty">Unable to refresh news right now.</div>`;
  }
  const articles = item.articles || [];
  if (!articles.length) {
    return `<div class="news-empty">No matching news found yet.</div>`;
  }
  return articles.map((article) => `
    <a class="news-row" href="${html(article.url || "#")}" target="_blank" rel="noreferrer">
      ${article.image ? `<img src="${html(article.image)}" alt="" />` : `<span class="news-thumb"></span>`}
      <span>
        <strong>${html(article.headline)}</strong>
        <small>${html(article.source || "ESPN")} - ${formatArticleDate(article.published)}</small>
        ${article.description ? `<p>${html(article.description)}</p>` : ""}
      </span>
    </a>
  `).join("");
}

function newsPanel({ key, title, type, id, team, terms }) {
  return `
    <article class="profile-panel news-panel">
      <div class="panel-heading">
        <h2>${html(title)}</h2>
        <button class="action-button small" type="button" data-refresh-news data-news-key="${html(key)}" data-news-type="${html(type)}" data-news-id="${html(id)}" data-news-team="${html(team || "")}" data-news-terms="${html(terms.join("|"))}">Refresh</button>
      </div>
      <div class="news-list" id="news-${html(key.replace(":", "-"))}">${renderNewsContent(key)}</div>
    </article>
  `;
}

function updateNewsPanel(key) {
  const target = document.getElementById(`news-${key.replace(":", "-")}`);
  if (target) target.innerHTML = renderNewsContent(key);
}

function loadEntityNews({ key, type, team, terms, refresh = false }) {
  state.news[key] = { ...(state.news[key] || {}), loading: true, error: false };
  updateNewsPanel(key);
  const params = new URLSearchParams({ type, refresh: refresh ? "1" : "0" });
  if (team) params.set("team", team);
  terms.forEach((term) => params.append("term", term));
  fetch(`/api/news?${params.toString()}`)
    .then((response) => response.json())
    .then((data) => {
      state.news[key] = { loading: false, error: false, ...data };
      updateNewsPanel(key);
    })
    .catch(() => {
      state.news[key] = { loading: false, error: true };
      updateNewsPanel(key);
    });
}

function renderTeamDetail(slug) {
  const team = teamBySlug(slug);
  if (!team) {
    els.teamDetailPage.innerHTML = `<article class="panel"><h1>Team not found</h1></article>`;
    return;
  }
  const players = (state.analytics.players || []).filter((player) => player.team === team.abbr).sort((a, b) => a.rotation_rank - b.rotation_rank);
  const key = newsKey("team", team.abbr);
  const terms = [team.team, team.abbr];
  els.teamDetailPage.innerHTML = `
    <section class="detail-hero" style="--team-primary:${team.primary}">
      <img src="${team.logo}" alt="" />
      <div>
        <h1>${html(team.team)}</h1>
        <p>#${team.seed} ${team.conference} seed - ${team.record} regular season - ${team.playoff_record} playoffs</p>
      </div>
      <span class="sentiment-pill ${team.sentiment.label.toLowerCase()}">${team.sentiment.label}</span>
    </section>
    <section class="profile-grid">
      <article class="profile-panel">
        <div class="panel-heading"><h2>Rotation</h2><span>Starting 5 + Bench</span></div>
        <div class="rotation-list">
          ${players.map((player) => `
            <a class="rotation-row" href="${playerRoute(player)}">
              <img class="headshot" src="${player.headshot}" alt="" />
              <span><strong>${html(player.player)}</strong><br /><small>${player.role} - ${player.min} MPG</small></span>
              <strong>${player.pts} PPG</strong>
            </a>
          `).join("")}
        </div>
      </article>
      <aside class="profile-panel">
        <div class="panel-heading"><h2>Team Analytics</h2></div>
        <div class="card-stats">
          <div><span>PTS</span><strong>${team.pts}</strong></div>
          <div><span>REB</span><strong>${team.reb}</strong></div>
          <div><span>AST</span><strong>${team.ast}</strong></div>
          <div><span>NET</span><strong>${team.net > 0 ? "+" : ""}${team.net}</strong></div>
          <div><span>FG%</span><strong>${team.fg_pct}</strong></div>
          <div><span>STREAK</span><strong>${team.streak}</strong></div>
        </div>
        <div class="mini-panel" style="margin-top:14px">
          <h4>Offensive Trend</h4>
          ${sparkline([team.pts - 7, team.pts - 2, team.pts + team.net * 0.2, team.pts + 1, team.pts + 4], team.primary)}
        </div>
      </aside>
    </section>
    ${newsPanel({ key, title: "Latest Team News", type: "team", id: team.abbr, team: team.abbr, terms })}
  `;
  if (!state.news[key]) loadEntityNews({ key, type: "team", team: team.abbr, terms });
}

function renderPlayerDetail(slug) {
  const player = playerByRoute(slug);
  if (!player) {
    els.playerDetailPage.innerHTML = `<article class="panel"><h1>Player not found</h1></article>`;
    return;
  }
  const team = teamMap()[player.team] || {};
  const key = newsKey("player", player.id);
  const terms = [player.player, player.team_name, player.team];
  els.playerDetailPage.innerHTML = `
    <section class="detail-hero" style="--team-primary:${team.primary || "#0f1724"}">
      <img class="player-portrait" src="${player.headshot}" alt="" />
      <div>
        <h1>${html(player.player)}</h1>
        <p>${player.team_name} - ${player.role} - rotation rank #${player.rotation_rank}</p>
      </div>
      <a class="seed-badge" href="#/teams/${player.team_slug}">${player.team}</a>
    </section>
    <section class="profile-grid">
      <article class="profile-panel">
        <div class="panel-heading"><h2>Player Analytics</h2></div>
        <div class="stat-strip">
          <div><strong>${player.pts}</strong><span>PPG</span></div>
          <div><strong>${player.reb}</strong><span>RPG</span></div>
          <div><strong>${player.ast}</strong><span>APG</span></div>
          <div><strong>${player.plus_minus > 0 ? "+" : ""}${player.plus_minus}</strong><span>+/-</span></div>
        </div>
        <div class="mini-panel" style="margin-top:16px">
          <h4>Scoring Trend</h4>
          ${sparkline(player.trend, team.primary || "#16a05d")}
        </div>
      </article>
      <aside class="profile-panel">
        <div class="panel-heading"><h2>Profile Signals</h2></div>
        <div class="card-stats">
          <div><span>MIN</span><strong>${player.min}</strong></div>
          <div><span>FG%</span><strong>${player.fg_pct}</strong></div>
          <div><span>3P%</span><strong>${player.fg3_pct}</strong></div>
          <div><span>STL</span><strong>${player.stl}</strong></div>
          <div><span>BLK</span><strong>${player.blk}</strong></div>
          <div><span>Impact</span><strong>${player.impact}</strong></div>
        </div>
        <p style="color:var(--muted);font-weight:700;margin:16px 0 0">Sentiment: <span class="${player.sentiment.label.toLowerCase()}">${player.sentiment.label}</span></p>
      </aside>
    </section>
    ${newsPanel({ key, title: "Latest Player News", type: "player", id: player.id, team: player.team, terms })}
  `;
  if (!state.news[key]) loadEntityNews({ key, type: "player", team: player.team, terms });
}

function renderAlertsPage() {
  const concern = (state.analytics.players || []).filter((player) => player.sentiment.label === "Concern").slice(0, 10);
  els.alertsPage.innerHTML = `
    <div class="page-heading"><div><h1>Alerts</h1><p>Sentiment and performance alerts from the playoff model.</p></div></div>
    <div class="alert-list">
      ${(concern.length ? concern : (state.analytics.players || []).slice(0, 8)).map((player) => `
        <a class="simple-row" href="${playerRoute(player)}">
          <span><strong>${html(player.player)}</strong><br /><small>${player.team} - ${player.role}</small></span>
          <span class="sentiment-pill ${player.sentiment.label.toLowerCase()}">${player.sentiment.label}</span>
        </a>
      `).join("")}
    </div>
  `;
}

function renderPredictionResult(game, result) {
  if (!result) {
    return `<span class="prediction-pending">Run the model to see the pick</span>`;
  }
  if (result.loading) {
    return `<span class="prediction-pending">Running model...</span>`;
  }
  if (!result.ok) {
    return `<span class="prediction-pending">${html(result.message || "Prediction unavailable")}</span>`;
  }
  const awayPct = Math.round(Number(result.away_probability || 0) * 100);
  const homePct = Math.round(Number(result.home_probability || 0) * 100);
  return `
    <div class="prediction-result">
      <div class="prediction-pick">
        <span>Pick</span>
        <strong>${html(result.winner_name)} (${html(result.winner)})</strong>
      </div>
      <div class="probability-row compact"><span>${html(game.away)}</span><div><i style="width:${awayPct}%"></i></div><strong>${awayPct}%</strong></div>
      <div class="probability-row compact"><span>${html(game.home)}</span><div><i style="width:${homePct}%"></i></div><strong>${homePct}%</strong></div>
      <p>${html(result.summary)}</p>
    </div>
  `;
}

function runGamePrediction(button) {
  const key = button.dataset.predictionKey;
  const away = button.dataset.away;
  const home = button.dataset.home;
  state.predictions[key] = { loading: true };
  renderPredictionsPage();
  const params = new URLSearchParams({ away, home });
  fetch(`/api/game-prediction?${params.toString()}`)
    .then((response) => response.json())
    .then((data) => {
      state.predictions[key] = data;
      renderPredictionsPage();
    })
    .catch(() => {
      state.predictions[key] = { ok: false, message: "The model could not run right now." };
      renderPredictionsPage();
    });
}

function renderPredictionsPage() {
  const teams = teamMap();
  els.predictionsPage.innerHTML = `
    <div class="page-heading"><div><h1>Predictions</h1><p>Run the matchup model for each game and get a plain-language reason for the pick.</p></div></div>
    <div class="prediction-list">
      ${(state.analytics.upcoming_games || []).map((game) => {
        const away = teams[game.away] || {};
        const home = teams[game.home] || {};
        const key = predictionKey(game);
        const result = state.predictions[key];
        return `
          <div class="prediction-card">
            <div class="prediction-card-top">
              <span><strong>${html(game.matchup)}</strong><br /><small>${formatDate(game.date)} at ${formatTime(game.date)} - ${html(game.status || "Scheduled")}</small></span>
              <button class="action-button" type="button" data-run-prediction data-prediction-key="${html(key)}" data-away="${html(game.away)}" data-home="${html(game.home)}">${result?.loading ? "Running..." : "Run Model"}</button>
            </div>
            ${renderPredictionResult(game, result)}
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderSettingsPage() {
  els.settingsPage.innerHTML = `
    <div class="page-heading"><div><h1>Settings</h1><p>Display and model options for the dashboard.</p></div></div>
    <div class="settings-list">
      <div class="simple-row"><span><strong>Live Data</strong><br /><small>Socket.IO updates every few seconds.</small></span><span class="sentiment-pill positive">Enabled</span></div>
      <div class="simple-row"><span><strong>Playoff Scope</strong><br /><small>Restrict teams and players to playoff qualifiers.</small></span><span class="sentiment-pill positive">Only playoff teams</span></div>
      <div class="simple-row"><span><strong>Rotation Method</strong><br /><small>Top minutes define starting 5, remaining playoff players are bench.</small></span><span class="sentiment-pill neutral">Minutes based</span></div>
    </div>
  `;
}

function sparkline(values, color) {
  const nums = values.map(Number);
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const points = nums.map((value, index) => {
    const x = 8 + index * (184 / Math.max(nums.length - 1, 1));
    const y = 62 - ((value - min) / Math.max(max - min, 1)) * 46;
    return `${x},${y}`;
  }).join(" ");
  return `
    <svg class="sparkline" viewBox="0 0 204 72" role="img" aria-label="Trend chart">
      <polyline fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" points="${points}" />
      ${points.split(" ").map((point) => `<circle cx="${point.split(",")[0]}" cy="${point.split(",")[1]}" r="3.4" fill="${color}" />`).join("")}
    </svg>
  `;
}

document.querySelectorAll(".segment").forEach((button) => {
  button.addEventListener("click", () => {
    state.conference = button.dataset.conference;
    document.querySelectorAll(".segment").forEach((item) => item.classList.toggle("active", item === button));
    renderStandings();
  });
});

document.querySelectorAll(".leader-tab").forEach((button) => {
  button.addEventListener("click", () => {
    state.leader = button.dataset.leader;
    document.querySelectorAll(".leader-tab").forEach((item) => item.classList.toggle("active", item === button));
    renderLeaders();
  });
});

els.playerTeamFilter.addEventListener("change", () => {
  state.playerFilter = els.playerTeamFilter.value;
  renderPlayersPage();
});

document.addEventListener("click", (event) => {
  const predictionButton = event.target.closest("[data-run-prediction]");
  if (predictionButton) {
    runGamePrediction(predictionButton);
    return;
  }

  const newsButton = event.target.closest("[data-refresh-news]");
  if (newsButton) {
    const terms = (newsButton.dataset.newsTerms || "").split("|").filter(Boolean);
    loadEntityNews({
      key: newsButton.dataset.newsKey,
      type: newsButton.dataset.newsType,
      team: newsButton.dataset.newsTeam,
      terms,
      refresh: true,
    });
  }
});

window.addEventListener("hashchange", route);

socket.on("prediction", (snapshot) => {
  state.live = snapshot;
  if (els.dataUpdated) els.dataUpdated.textContent = new Date(snapshot.updated_at).toLocaleTimeString();
  renderKpis();
  renderLiveStatus();
  if (isLiveRoute()) {
    renderLivePage();
    setActivePage("livePage", "live");
  }
});

fetch("/api/analytics")
  .then((response) => response.json())
  .then((data) => {
    state.analytics = data;
    renderAll();
  })
  .catch(() => {
    els.liveStatusBody.innerHTML = "<strong>Unable to load analytics.</strong>";
  });

fetch("/api/prediction")
  .then((response) => response.json())
  .then((snapshot) => {
    state.live = snapshot;
    renderKpis();
    renderLiveStatus();
    if (isLiveRoute()) {
      renderLivePage();
      setActivePage("livePage", "live");
    }
  });
