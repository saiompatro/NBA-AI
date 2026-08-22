const socket = io();

const state = {
  analytics: null,
  live: null,
  conference: "Eastern",
  leader: "pts",
  playerFilter: "ALL",
  playerSort: "default",
  predictions: {},
  news: {},
  compare: { a: null, b: null },
  gameLog: {},
  shotChart: {},
  powerRankings: null,
  powerRankingsLoading: false,
  bracket: null,
  bracketLoading: false,
  modelPerformance: null,
  modelPerformanceLoading: false,
  shotQuality: null,
  shotQualityLoading: false,
};

const els = {
  themeButton: document.getElementById("themeButton"),
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
  globalSearch: document.getElementById("globalSearch"),
  searchResults: document.getElementById("searchResults"),
  playerTeamFilter: document.getElementById("playerTeamFilter"),
  playerSortFilter: document.getElementById("playerSortFilter"),
  playersGrid: document.getElementById("playersGrid"),
  teamsGrid: document.getElementById("teamsGrid"),
  teamDetailPage: document.getElementById("teamDetailPage"),
  playerDetailPage: document.getElementById("playerDetailPage"),
  alertsPage: document.getElementById("alertsPage"),
  predictionsPage: document.getElementById("predictionsPage"),
  comparePage: document.getElementById("comparePage"),
  powerRankingsPage: document.getElementById("powerRankingsPage"),
  bracketPage: document.getElementById("bracketPage"),
  modelPerformancePage: document.getElementById("modelPerformancePage"),
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
  if (section === "compare") {
    renderComparePage();
    setActivePage("comparePage", "compare");
    return;
  }
  if (section === "power-rankings") {
    renderPowerRankingsPage();
    setActivePage("powerRankingsPage", "power-rankings");
    return;
  }
  if (section === "bracket") {
    renderBracketPage();
    setActivePage("bracketPage", "bracket");
    return;
  }
  if (section === "model") {
    renderModelPerformancePage();
    setActivePage("modelPerformancePage", "model");
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
    { icon: "trend", tone: "#ffeee7", color: "#f26b1d", value: state.modelPerformance?.accuracy != null ? `${(state.modelPerformance.accuracy * 100).toFixed(1)}%` : "--", label: "Model Accuracy" },
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
  const rawHomeWin = Math.round(Number(snapshot?.raw_home_win_probability || snapshot?.home_win_probability || 0) * 100);
  const shotQuality = Math.round(Number(snapshot?.shot_quality || model.shot_quality || 0) * 100);
  const homeOut = snapshot?.home_players_out || [];
  const awayOut = snapshot?.away_players_out || [];
  const homeBox = snapshot?.home_box_score || [];
  const awayBox = snapshot?.away_box_score || [];
  const hasUnavailable = homeOut.length > 0 || awayOut.length > 0;
  const isAdjusted = hasUnavailable && Math.abs(homeWin - rawHomeWin) >= 1;

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
        <div class="panel-heading">
          <h2>Win Probability</h2>
          <span>${isAdjusted ? `<span class="impact-badge">impact-adjusted</span>` : "Model output"}</span>
        </div>
        <div class="probability-row"><span>${html(snapshot.away_team)}</span><div><i style="width:${awayWin}%"></i></div><strong>${awayWin}%</strong></div>
        <div class="probability-row"><span>${html(snapshot.home_team)}</span><div><i style="width:${homeWin}%"></i></div><strong>${homeWin}%</strong></div>
        ${isAdjusted ? `<p class="prob-adjustment-note">Raw model: ${100 - rawHomeWin}% / ${rawHomeWin}% &rarr; adjusted for unavailable players</p>` : ""}
        ${winProbabilityChart(snapshot.win_probability_history, snapshot.home_team, snapshot.away_team)}
        <div class="shot-quality-meter">
          <span>Shot Quality</span>
          <strong>${shotQuality}%</strong>
          <div><i style="width:${shotQuality}%"></i></div>
        </div>
      </article>
      ${hasUnavailable ? `
      <article class="panel unavailable-panel">
        <div class="panel-heading"><h2>Players Unavailable</h2><span>Ejections / Foul-outs / Injuries</span></div>
        <div class="unavailable-list">
          ${[...homeOut.map((p) => ({...p, team: snapshot.home_team})), ...awayOut.map((p) => ({...p, team: snapshot.away_team}))].map((p) => `
            <div class="unavailable-row">
              <span class="unavail-team">${html(p.team)}</span>
              <span class="unavail-name">${html(p.name)}</span>
              <span class="unavail-reason">${html(p.reason)}</span>
            </div>
          `).join("")}
        </div>
      </article>` : ""}
      <article class="panel box-score-panel">
        <div class="panel-heading"><h2>Box Score</h2><span>Top scorers</span></div>
        ${boxScoreTable(snapshot.away_team, awayBox)}
        ${boxScoreTable(snapshot.home_team, homeBox)}
      </article>
      <article class="panel">
        <div class="panel-heading"><h2>Play-by-Play Events</h2><span>${html(model.source || snapshot.source)}</span></div>
        <div class="event-list">
          ${events.map((event) => `<div class="event-row ${event.startsWith("[News]") ? "event-news" : ""}">${html(event)}</div>`).join("")}
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

const PLAYER_SORT_LABELS = { pts: "PTS", reb: "REB", ast: "AST", stl: "STL", blk: "BLK", ts_pct: "TS%", usg_pct: "USG%", pie: "PIE" };

function renderPlayersPage() {
  const sortKey = state.playerSort;
  const rows = (state.analytics.players || [])
    .filter((player) => state.playerFilter === "ALL" || player.team === state.playerFilter)
    .sort((a, b) => sortKey === "default"
      ? a.team.localeCompare(b.team) || a.rotation_rank - b.rotation_rank
      : (b[sortKey] ?? 0) - (a[sortKey] ?? 0));
  els.playersGrid.innerHTML = rows.map((player, index) => `
    <a class="player-card" href="${playerRoute(player)}">
      <img src="${player.headshot}" alt="" />
      <div>
        <div class="card-top">
          <div>
            <h3>${sortKey === "default" ? "" : `<span class="rank-badge">${index + 1}</span>`}${html(player.player)}</h3>
            <p>${player.team_name} - ${player.team}</p>
          </div>
          <span class="role-badge">${player.role}</span>
        </div>
        <div class="card-stats">
          <div><span>PTS</span><strong>${player.pts}</strong></div>
          <div><span>REB</span><strong>${player.reb}</strong></div>
          <div><span>AST</span><strong>${player.ast}</strong></div>
          ${["default", "pts", "reb", "ast"].includes(sortKey) ? "" : `<div><span>${PLAYER_SORT_LABELS[sortKey]}</span><strong>${player[sortKey]}</strong></div>`}
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

function gameLogPanel(playerId) {
  return `
    <article class="profile-panel">
      <div class="panel-heading"><h2>Recent Games</h2></div>
      <div id="game-log-${playerId}">${renderGameLogContent(playerId)}</div>
    </article>
  `;
}

function renderGameLogContent(playerId) {
  const entry = state.gameLog[playerId];
  if (!entry || entry.loading) return `<p class="footer-note">Loading recent games...</p>`;
  if (entry.error) return `<p class="footer-note">Recent games unavailable right now.</p>`;
  const games = entry.games || [];
  if (!games.length) return `<p class="footer-note">No recent game log found for this player.</p>`;
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>Date</th><th>Matchup</th><th>W/L</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>+/-</th></tr></thead>
        <tbody>${games.map((game) => `
          <tr>
            <td>${html(game.date)}</td>
            <td>${html(game.matchup)}</td>
            <td class="${game.result === "W" ? "positive" : "concern"}">${html(game.result)}</td>
            <td>${game.min}</td>
            <td>${game.pts}</td>
            <td>${game.reb}</td>
            <td>${game.ast}</td>
            <td class="${game.plus_minus >= 0 ? "positive" : "concern"}">${game.plus_minus > 0 ? "+" : ""}${game.plus_minus}</td>
          </tr>
        `).join("")}</tbody>
      </table>
    </div>
  `;
}

function loadGameLog(playerId) {
  state.gameLog[playerId] = { loading: true, error: false };
  fetch(`/api/players/${playerId}/game-log`)
    .then((response) => response.json())
    .then((data) => {
      state.gameLog[playerId] = { loading: false, error: false, games: data.games || [] };
      const target = document.getElementById(`game-log-${playerId}`);
      if (target) target.innerHTML = renderGameLogContent(playerId);
    })
    .catch(() => {
      state.gameLog[playerId] = { loading: false, error: true };
      const target = document.getElementById(`game-log-${playerId}`);
      if (target) target.innerHTML = renderGameLogContent(playerId);
    });
}

function shotChartPanel(playerId) {
  return `
    <article class="profile-panel">
      <div class="panel-heading"><h2>Shot Chart</h2></div>
      <div id="shot-chart-${playerId}">${renderShotChartContent(playerId)}</div>
    </article>
  `;
}

function renderShotChartContent(playerId) {
  const entry = state.shotChart[playerId];
  if (!entry || entry.loading) return `<p class="footer-note">Loading shot chart...</p>`;
  if (entry.error) return `<p class="footer-note">Shot chart unavailable right now.</p>`;
  if (!entry.ok || !(entry.shots || []).length) return `<p class="footer-note">No charted shots found for this player.</p>`;
  const zones = entry.zones || [];
  return `
    <div class="shot-chart-wrap">
      ${courtSvg(entry.shots)}
      <div class="shot-chart-legend">
        <span class="legend-made">Made (${entry.totals.fgm}/${entry.totals.fga}, ${entry.totals.fg_pct}% - ${entry.totals.efg_pct}% eFG)</span>
        <span class="legend-miss">Miss</span>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Zone</th><th>FGA</th><th>FG%</th><th>League FG%</th><th>+/-</th><th>Share</th></tr></thead>
        <tbody>${zones.map((zone) => `
          <tr>
            <td>${html(zone.zone)}</td>
            <td>${zone.fga}</td>
            <td>${zone.fg_pct}%</td>
            <td>${zone.league_fg_pct}%</td>
            <td class="${zone.delta >= 0 ? "positive" : "concern"}">${zone.delta > 0 ? "+" : ""}${zone.delta}</td>
            <td>${zone.share}%</td>
          </tr>
        `).join("")}</tbody>
      </table>
    </div>
  `;
}

function loadShotChart(playerId) {
  state.shotChart[playerId] = { loading: true, error: false };
  fetch(`/api/players/${playerId}/shot-chart`)
    .then((response) => response.json())
    .then((data) => {
      state.shotChart[playerId] = { loading: false, error: false, ...data };
      const target = document.getElementById(`shot-chart-${playerId}`);
      if (target) target.innerHTML = renderShotChartContent(playerId);
    })
    .catch(() => {
      state.shotChart[playerId] = { loading: false, error: true };
      const target = document.getElementById(`shot-chart-${playerId}`);
      if (target) target.innerHTML = renderShotChartContent(playerId);
    });
}

function courtSvg(shots) {
  const dots = (shots || []).map((shot) => {
    const cls = shot.made ? "shot-made" : "shot-miss";
    return `<circle class="${cls}" cx="${shot.x}" cy="${shot.y}" r="4.2" />`;
  }).join("");
  return `
    <svg class="shot-court-svg" viewBox="-260 -60 520 500" role="img" aria-label="Shot chart">
      <rect class="court-line" x="-250" y="-47.5" width="500" height="470" />
      <rect class="court-line" x="-80" y="-47.5" width="160" height="190" />
      <rect class="court-line" x="-60" y="-47.5" width="120" height="190" />
      <line class="court-line" x1="-30" y1="-7.5" x2="30" y2="-7.5" />
      <circle class="court-line" cx="0" cy="0" r="7.5" />
      <path class="court-line" d="M -40,0 A 40,40 0 0,1 40,0" />
      <path class="court-line" d="M -60,142.5 A 60,60 0 0,1 60,142.5" />
      <path class="court-line" d="M -60,142.5 A 60,60 0 0,0 60,142.5" stroke-dasharray="4 4" />
      <line class="court-line" x1="-220" y1="-47.5" x2="-220" y2="92.5" />
      <line class="court-line" x1="220" y1="-47.5" x2="220" y2="92.5" />
      <path class="court-line" d="M -220,92.5 A 237.5,237.5 0 0,1 220,92.5" />
      ${dots}
    </svg>
  `;
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
          <div><span>OFF RTG</span><strong>${team.off_rtg}</strong></div>
          <div><span>DEF RTG</span><strong>${team.def_rtg}</strong></div>
          <div><span>PACE</span><strong>${team.pace}</strong></div>
          <div><span>EFG%</span><strong>${team.efg_pct}</strong></div>
          <div><span>TS%</span><strong>${team.ts_pct}</strong></div>
          <div><span>TOV%</span><strong>${team.tov_pct}</strong></div>
          <div><span>OREB%</span><strong>${team.oreb_pct}</strong></div>
          <div><span>FT RATE</span><strong>${team.ftr}</strong></div>
          <div><span>CLUTCH REC</span><strong>${team.clutch_record}</strong></div>
          <div><span>CLUTCH NET</span><strong class="${team.clutch_net >= 0 ? "positive" : "concern"}">${team.clutch_net > 0 ? "+" : ""}${team.clutch_net}</strong></div>
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
          <div><span>TS%</span><strong>${player.ts_pct}</strong></div>
          <div><span>USG%</span><strong>${player.usg_pct}</strong></div>
          <div><span>PIE</span><strong>${player.pie}</strong></div>
          <div><span>Impact</span><strong>${player.impact}</strong></div>
        </div>
        <p style="color:var(--muted);font-weight:700;margin:16px 0 0">Sentiment: <span class="${player.sentiment.label.toLowerCase()}">${player.sentiment.label}</span></p>
      </aside>
    </section>
    ${shotChartPanel(player.id)}
    ${gameLogPanel(player.id)}
    ${newsPanel({ key, title: "Latest Player News", type: "player", id: player.id, team: player.team, terms })}
  `;
  if (!state.news[key]) loadEntityNews({ key, type: "player", team: player.team, terms });
  if (!state.gameLog[player.id]) loadGameLog(player.id);
  if (!state.shotChart[player.id]) loadShotChart(player.id);
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

const COMPARE_STATS = [
  { key: "pts", label: "PPG" },
  { key: "reb", label: "RPG" },
  { key: "ast", label: "APG" },
  { key: "stl", label: "SPG" },
  { key: "blk", label: "BPG" },
  { key: "min", label: "MIN" },
  { key: "fg_pct", label: "FG%" },
  { key: "fg3_pct", label: "3P%" },
  { key: "ts_pct", label: "TS%" },
  { key: "usg_pct", label: "USG%" },
  { key: "pie", label: "PIE" },
  { key: "plus_minus", label: "+/-" },
  { key: "impact", label: "Impact" },
];

function renderComparePage() {
  const players = [...(state.analytics.players || [])].sort((a, b) => a.player.localeCompare(b.player));
  if (players.length < 2) {
    els.comparePage.innerHTML = `<div class="page-heading"><div><h1>Compare Players</h1><p>Not enough player data yet.</p></div></div>`;
    return;
  }
  if (!state.compare.a) state.compare.a = String(players.slice().sort((a, b) => b.impact - a.impact)[0].id);
  if (!state.compare.b) {
    const fallback = players.find((player) => String(player.id) !== state.compare.a);
    state.compare.b = String(fallback?.id ?? players[0].id);
  }
  const playerA = players.find((player) => String(player.id) === state.compare.a) || players[0];
  const playerB = players.find((player) => String(player.id) === state.compare.b) || players[1];
  const options = players.map((player) => `<option value="${player.id}">${html(player.player)} (${player.team})</option>`).join("");

  els.comparePage.innerHTML = `
    <div class="page-heading"><div><h1>Compare Players</h1><p>Pick two playoff players to compare season averages side by side.</p></div></div>
    <article class="panel compare-picker">
      <div class="compare-card"><img src="${playerA.headshot}" alt="" /><span><strong>${html(playerA.player)}</strong><small>${playerA.team_name}</small></span></div>
      <span class="compare-vs">VS</span>
      <div class="compare-card"><img src="${playerB.headshot}" alt="" /><span><strong>${html(playerB.player)}</strong><small>${playerB.team_name}</small></span></div>
      <select data-compare-select="a" aria-label="First player">${options}</select>
      <span></span>
      <select data-compare-select="b" aria-label="Second player">${options}</select>
    </article>
    <article class="panel">
      <div class="table-wrap">
        <table class="compare-table">
          <tbody>
            ${COMPARE_STATS.map(({ key, label }) => {
              const valueA = Number(playerA[key] || 0);
              const valueB = Number(playerB[key] || 0);
              return `
                <tr>
                  <td class="${valueA > valueB ? "compare-win" : ""}">${valueA}</td>
                  <td>${label}</td>
                  <td class="${valueB > valueA ? "compare-win" : ""}">${valueB}</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    </article>
  `;
  els.comparePage.querySelector('[data-compare-select="a"]').value = state.compare.a;
  els.comparePage.querySelector('[data-compare-select="b"]').value = state.compare.b;
}

function renderPowerRankingsPage() {
  if (!state.powerRankings && !state.powerRankingsLoading) {
    state.powerRankingsLoading = true;
    fetch("/api/power-rankings")
      .then((response) => response.json())
      .then((data) => {
        state.powerRankings = data.power_rankings || [];
        state.powerRankingsLoading = false;
        renderPowerRankingsPage();
      })
      .catch(() => {
        state.powerRankings = [];
        state.powerRankingsLoading = false;
        renderPowerRankingsPage();
      });
  }

  if (!state.powerRankings) {
    els.powerRankingsPage.innerHTML = `
      <div class="page-heading"><div><h1>Power Rankings</h1><p>Composite ranking blending net rating with recent form.</p></div></div>
      <article class="panel"><p class="footer-note">Crunching the numbers...</p></article>
    `;
    return;
  }

  const rows = state.powerRankings;
  els.powerRankingsPage.innerHTML = `
    <div class="page-heading"><div><h1>Power Rankings</h1><p>All 16 playoff teams ranked by net rating blended with last-10 form, not raw record.</p></div></div>
    <article class="panel">
      <div class="table-wrap">
        <table>
          <thead><tr><th>#</th><th>Move</th><th>Team</th><th>Record</th><th>NET</th><th>Form</th><th>Score</th><th>Why</th></tr></thead>
          <tbody>${rows.map((team) => {
            const moveClass = team.movement > 0 ? "positive" : team.movement < 0 ? "concern" : "";
            const moveLabel = team.movement > 0 ? `&#9650;${team.movement}` : team.movement < 0 ? `&#9660;${Math.abs(team.movement)}` : "&mdash;";
            return `
              <tr>
                <td>${team.rank}</td>
                <td class="${moveClass}">${moveLabel}</td>
                <td><a class="team-cell" href="#/teams/${team.slug}"><img class="logo" src="${team.logo}" alt="" />${html(team.team)}</a></td>
                <td>${team.record}</td>
                <td class="${team.net >= 0 ? "positive" : "concern"}">${team.net > 0 ? "+" : ""}${team.net}</td>
                <td>${team.last10}</td>
                <td>${team.power_score > 0 ? "+" : ""}${team.power_score}</td>
                <td class="power-blurb">${html(team.blurb)}</td>
              </tr>
            `;
          }).join("")}</tbody>
        </table>
      </div>
    </article>
  `;
}

const BRACKET_ROUND_ORDER = ["First Round", "Conf. Semifinals", "Conf. Finals"];

function renderBracketPage() {
  if (!state.bracket && !state.bracketLoading) {
    state.bracketLoading = true;
    fetch("/api/table")
      .then((response) => response.json())
      .then((data) => {
        state.bracket = data.playoff_table || [];
        state.bracketLoading = false;
        renderBracketPage();
      })
      .catch(() => {
        state.bracket = [];
        state.bracketLoading = false;
        renderBracketPage();
      });
  }

  const heading = `<div class="page-heading"><div><h1>Playoff Bracket</h1><p>Live series scores by round, straight from the same feed that drives the standings.</p></div></div>`;

  if (!state.bracket) {
    els.bracketPage.innerHTML = `${heading}<article class="panel"><p class="footer-note">Loading series data...</p></article>`;
    return;
  }
  if (!state.bracket.length) {
    els.bracketPage.innerHTML = `${heading}<article class="panel"><p class="footer-note">No active playoff series right now.</p></article>`;
    return;
  }

  const matchupCard = (row) => `
    <div class="bracket-matchup">
      <p class="bracket-teams">${html(row.matchup)}</p>
      <div class="bracket-series">
        <span class="${row.leader && row.leader !== "Even" ? "positive" : ""}">${html(row.series)}</span>
        <span class="bracket-remaining">${row.remaining ? `${row.remaining} to play` : "Series over"}</span>
      </div>
    </div>
  `;

  const finals = state.bracket.filter((row) => row.round === "NBA Finals");
  const conferences = ["Eastern", "Western"].map((conference) => {
    const rows = state.bracket.filter((row) => row.round !== "NBA Finals" && String(row.conference || "").startsWith(conference.slice(0, 4)));
    const columns = BRACKET_ROUND_ORDER.map((roundName) => {
      const roundRows = rows.filter((row) => (row.round || "Playoffs") === roundName);
      if (!roundRows.length) return "";
      return `
        <div class="bracket-round">
          <h3>${roundName}</h3>
          ${roundRows.map(matchupCard).join("")}
        </div>
      `;
    }).join("");
    const leftovers = rows.filter((row) => !BRACKET_ROUND_ORDER.includes(row.round || ""));
    const leftoverColumn = leftovers.length
      ? `<div class="bracket-round"><h3>Playoffs</h3>${leftovers.map(matchupCard).join("")}</div>`
      : "";
    return `
      <article class="panel">
        <div class="panel-heading"><h2>${conference} Conference</h2></div>
        <div class="bracket-columns">${columns}${leftoverColumn}</div>
      </article>
    `;
  }).join("");

  const finalsPanel = finals.length
    ? `
      <article class="panel bracket-finals">
        <div class="panel-heading"><h2>NBA Finals</h2></div>
        <div class="bracket-columns">${finals.map(matchupCard).join("")}</div>
      </article>
    `
    : "";

  els.bracketPage.innerHTML = `${heading}<div class="conference-grid">${conferences}</div>${finalsPanel}`;
}

function renderModelPerformancePage() {
  if (!state.modelPerformance && !state.modelPerformanceLoading) {
    state.modelPerformanceLoading = true;
    fetch("/api/model-performance")
      .then((response) => response.json())
      .then((data) => {
        state.modelPerformance = data;
        state.modelPerformanceLoading = false;
        renderModelPerformancePage();
      })
      .catch(() => {
        state.modelPerformance = {};
        state.modelPerformanceLoading = false;
        renderModelPerformancePage();
      });
  }

  const heading = `<div class="page-heading"><div><h1>Model Accuracy</h1><p>How the pre-game win-probability model performs against real results, not just this matchup.</p></div></div>`;

  if (!state.modelPerformance) {
    els.modelPerformancePage.innerHTML = `${heading}<article class="panel"><p class="footer-note">Loading backtest results...</p></article>`;
    return;
  }

  const perf = state.modelPerformance;
  if (!perf.calibrated) {
    els.modelPerformancePage.innerHTML = `${heading}<article class="panel"><p class="footer-note">Not yet calibrated against real games — run <code>scripts/calibrate_pregame.py</code> to fit and unlock backtest numbers.</p></article>`;
    return;
  }

  if (!state.shotQuality && !state.shotQualityLoading) {
    state.shotQualityLoading = true;
    fetch("/api/shot-quality")
      .then((response) => response.json())
      .then((data) => {
        state.shotQuality = data;
        state.shotQualityLoading = false;
        renderModelPerformancePage();
      })
      .catch(() => {
        state.shotQuality = {};
        state.shotQualityLoading = false;
        renderModelPerformancePage();
      });
  }

  const accuracyPct = perf.accuracy != null ? perf.accuracy * 100 : null;
  const baselinePct = perf.baseline_home_win_rate * 100;
  const fitDate = perf.fit_at ? new Date(perf.fit_at).toLocaleDateString() : "--";

  els.modelPerformancePage.innerHTML = `
    <div class="page-heading"><div><h1>Model Accuracy</h1><p>Backtested against ${perf.games_backtested ?? "--"} real games across ${(perf.seasons || []).join(", ") || "recent seasons"}.</p></div></div>
    <section class="kpi-grid">
      <article class="kpi-card">
        <span class="kpi-icon" style="background:#eaf1ff;color:#075ed9">${iconSvg("trend")}</span>
        <div><strong>${accuracyPct != null ? accuracyPct.toFixed(1) : "--"}%</strong><span>Winner Pick Accuracy</span></div>
      </article>
      <article class="kpi-card">
        <span class="kpi-icon" style="background:#fff4d9;color:#f7a614">${iconSvg("database")}</span>
        <div><strong>${perf.log_loss != null ? perf.log_loss.toFixed(3) : "--"}</strong><span>Log Loss</span></div>
      </article>
      <article class="kpi-card">
        <span class="kpi-icon" style="background:#fff0e8;color:#f26b1d">${iconSvg("calendar")}</span>
        <div><strong>${perf.games_backtested ?? "--"}</strong><span>Games Backtested</span></div>
      </article>
      <article class="kpi-card">
        <span class="kpi-icon" style="background:#e8f8ef;color:#16a05d">${iconSvg("trophy")}</span>
        <div><strong>${accuracyPct != null ? `+${(accuracyPct - baselinePct).toFixed(1)}pt` : "--"}</strong><span>Vs. Home-Favorite Baseline</span></div>
      </article>
    </section>
    <article class="panel">
      <div class="panel-heading"><h2>How it's scored</h2></div>
      <div class="settings-list">
        <div class="simple-row"><span><strong>Home-court advantage</strong><br /><small>Fitted margin edge for the home team.</small></span><span class="sentiment-pill neutral">${perf.home_court_advantage} pts</span></div>
        <div class="simple-row"><span><strong>Probability scale</strong><br /><small>Margin-to-probability sigmoid steepness.</small></span><span class="sentiment-pill neutral">${perf.scale}</span></div>
        <div class="simple-row"><span><strong>Last calibrated</strong><br /><small>Re-run against the latest results periodically.</small></span><span class="sentiment-pill neutral">${fitDate}</span></div>
        <div class="simple-row"><span><strong>Baseline compared against</strong><br /><small>Long-run NBA home-team win rate.</small></span><span class="sentiment-pill neutral">${baselinePct.toFixed(0)}%</span></div>
      </div>
    </article>
    <article class="panel">
      <div class="panel-heading"><h2>Inputs feeding the pick</h2></div>
      <div class="settings-list">
        ${(perf.inputs || []).map((input) => `<div class="simple-row"><span>${html(input)}</span></div>`).join("")}
      </div>
    </article>
    ${shotQualityPanel(state.shotQuality)}
  `;
}

function shotQualityPanel(shotQuality) {
  if (!shotQuality || !shotQuality.evaluation) {
    return `
      <article class="panel">
        <div class="panel-heading"><h2>Shot Quality Model</h2></div>
        <p class="footer-note">Loading...</p>
      </article>
    `;
  }
  const evalData = shotQuality.evaluation;
  return `
    <article class="panel">
      <div class="panel-heading"><h2>Shot Quality Model</h2></div>
      <div class="settings-list">
        <div class="simple-row"><span><strong>R&sup2;</strong><br /><small>Variance explained on a synthetic holdout.</small></span><span class="sentiment-pill neutral">${evalData.r2}</span></div>
        <div class="simple-row"><span><strong>MAE</strong><br /><small>Mean absolute error in shot-quality points.</small></span><span class="sentiment-pill neutral">${evalData.mae}</span></div>
        <div class="simple-row"><span><strong>Holdout size</strong><br /><small>Synthetic rows scored, unseen during training.</small></span><span class="sentiment-pill neutral">${evalData.holdout_rows}</span></div>
      </div>
      <p class="footer-note">${html(evalData.note || "")}</p>
    </article>
  `;
}

function boxScoreTable(teamName, rows) {
  if (!rows || rows.length === 0) return "";
  return `
    <div class="box-score-team">
      <h3>${html(teamName)}</h3>
      <table class="box-score-table">
        <thead>
          <tr><th>Player</th><th>Pos</th><th>Min</th><th>Pts</th><th>Reb</th><th>Ast</th><th>Stl</th><th>Blk</th><th>+/-</th></tr>
        </thead>
        <tbody>
          ${rows.map((p) => `
            <tr>
              <td>${html(p.name)}</td>
              <td>${html(p.position)}</td>
              <td>${html(p.minutes)}</td>
              <td>${p.points}</td>
              <td>${p.rebounds}</td>
              <td>${p.assists}</td>
              <td>${p.steals}</td>
              <td>${p.blocks}</td>
              <td>${Number(p.plus_minus) > 0 ? "+" : ""}${p.plus_minus}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function winProbabilityChart(history, homeTeam, awayTeam) {
  const points = (history || []).map(Number).filter((v) => !Number.isNaN(v));
  if (points.length < 2) return "";
  const w = 600;
  const h = 140;
  const pad = 6;
  const coords = points.map((value, index) => {
    const x = pad + index * ((w - pad * 2) / Math.max(points.length - 1, 1));
    const y = pad + (1 - value) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const midY = (pad + (1 - 0.5) * (h - pad * 2)).toFixed(1);
  return `
    <div class="wp-chart">
      <div class="wp-chart-heading">
        <span>${html(awayTeam)}</span>
        <span>Win probability trend</span>
        <span>${html(homeTeam)}</span>
      </div>
      <svg class="wp-chart-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Win probability over time">
        <line x1="0" y1="${midY}" x2="${w}" y2="${midY}" class="wp-chart-midline" />
        <polyline fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${coords}" class="wp-chart-line" />
      </svg>
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

els.playerSortFilter.addEventListener("change", () => {
  state.playerSort = els.playerSortFilter.value;
  renderPlayersPage();
});

document.addEventListener("change", (event) => {
  const select = event.target.closest("[data-compare-select]");
  if (!select) return;
  state.compare[select.dataset.compareSelect] = select.value;
  renderComparePage();
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

function searchMatches(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const players = (state.analytics?.players || [])
    .filter((player) => player.player.toLowerCase().includes(q))
    .slice(0, 6)
    .map((player) => ({ type: "Player", href: playerRoute(player), label: player.player, sub: player.team_name, image: player.headshot }));
  const teams = (state.analytics?.teams || [])
    .filter((team) => team.team.toLowerCase().includes(q) || team.abbr.toLowerCase().includes(q))
    .slice(0, 5)
    .map((team) => ({ type: "Team", href: `#/teams/${team.slug}`, label: team.team, sub: team.conference, image: team.logo }));
  return [...players, ...teams].slice(0, 8);
}

function closeSearchResults() {
  if (!els.searchResults) return;
  els.searchResults.hidden = true;
  els.searchResults.innerHTML = "";
}

function renderSearchResults() {
  if (!els.searchResults || !els.globalSearch) return;
  const query = els.globalSearch.value;
  if (!query.trim()) {
    closeSearchResults();
    return;
  }
  const results = searchMatches(query);
  els.searchResults.innerHTML = results.length
    ? results.map((item) => `
        <a href="${html(item.href)}" data-search-result>
          <img src="${html(item.image || "")}" alt="" />
          <span><strong>${html(item.label)}</strong><small>${html(item.sub || "")}</small></span>
          <small class="search-type">${item.type}</small>
        </a>
      `).join("")
    : `<div class="search-empty">No matches for "${html(query)}"</div>`;
  els.searchResults.hidden = false;
}

els.globalSearch?.addEventListener("input", renderSearchResults);
els.globalSearch?.addEventListener("focus", renderSearchResults);
els.globalSearch?.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    els.globalSearch.blur();
    closeSearchResults();
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-search-result]")) {
    els.globalSearch.value = "";
    closeSearchResults();
    return;
  }
  if (!event.target.closest(".global-search")) {
    closeSearchResults();
  }
});

const THEME_KEY = "nba-ai-theme";

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  els.themeButton?.setAttribute("aria-pressed", String(theme === "dark"));
}

function initTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  const preferred = window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  applyTheme(stored || preferred);
}

els.themeButton?.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
});

initTheme();

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

fetch("/api/model-performance")
  .then((response) => response.json())
  .then((data) => {
    state.modelPerformance = data;
    renderKpis();
    if (location.hash.replace(/^#\/?/, "") === "model") renderModelPerformancePage();
  })
  .catch(() => {});

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
