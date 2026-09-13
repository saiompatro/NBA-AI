# NBA Live Predictor

A real-time NBA game analytics dashboard built with Flask and Socket.IO. It ingests live play-by-play data, runs an XGBoost shot-quality model and a PyTorch win-probability model, and renders a single-page dashboard with playoff standings, player/team profiles, and contextual news — all updating live via WebSocket.

The repository ships with synthetic training data and pre-trained model artifacts so the app is immediately runnable without a separate data pipeline.

![Dashboard screenshot](data/dashboard-screenshot.png)

## Features

- **Live scoreboard** — detects active NBA games via `nba_api` and polls every 3 seconds
- **Play-by-play tracker** — score, possession, latest event, shot context, shot quality, and win probability
- **Live box score** — top scorers per team (points, rebounds, assists, steals, blocks, +/-) pulled from the NBA CDN boxscore feed
- **Shot-quality model** — XGBoost regressor using distance, angle, defender distance, shot clock, and game situation
- **Win-probability model** — PyTorch network using score differential, time remaining, possession, fouls, and shot quality
- **Win-probability trend chart** — live line chart of the home team's win probability across the game, capped at the last 1,000 snapshots
- **Live shot chart** — half-court diagram of every field-goal attempt in the live game, colored by make/miss and sized by the model's shot-quality score for that shot
- **Playoff dashboard** — standings, schedule, team form, player leaders, sentiment, and alerts
- **Advanced team stats** — offensive/defensive rating, pace, effective FG%, true shooting%, and turnover% per team (NBA Stats `MeasureType=Advanced`), shown on each team profile
- **Per-game predictions** — `Run Model` button with a plain-English explanation of the pick, factoring in team strength, an Elo rating replayed from real results over the last 3 seasons (538 NBA Elo methodology), injuries, news sentiment, rest/back-to-back schedule fatigue, recent form, home/road performance splits, and the full four factors (eFG%, TOV%, OREB%, FT rate)
- **Player and team pages** — profile views with refreshable contextual news from ESPN
- **Sortable players page** — rank every playoff player by PTS, REB, AST, STL, BLK, TS%, USG%, or PIE (in addition to team filtering)
- **Player game log** — real last-10-game boxscore table (date, matchup, W/L, MIN/PTS/REB/AST/+/-) on every player profile, pulled live from `playergamelog` with a regular-season fallback for players without playoff minutes
- **WebSocket push** — live prediction events emitted to all connected clients every 3 seconds
- **Light/dark theme** — toggle in the topbar, respects system preference by default, persisted in `localStorage`
- **Global search** — topbar search box for jumping straight to any player or team profile by name
- **Player comparison** — side-by-side stat comparison for any two playoff players, with the better value highlighted per category
- **Power rankings** — all 16 playoff teams ranked by net rating blended with last-10 form (not raw record), with a plain-English blurb and a record-vs-power movement indicator per team
- **Playoff bracket** — series scores grouped by conference and round (First Round / Conf. Semifinals / Conf. Finals / NBA Finals), sourced from the same live `scoreboardv3` series data the standings already computed but the UI never surfaced
- **Model accuracy page** — backtested win-pick accuracy, log loss, and games/seasons used to fit the pre-game model, versus a home-favorite baseline (the topbar "Model Accuracy" KPI is now wired to this same number instead of a static placeholder), plus the shot-quality model's R²/MAE on a synthetic holdout (labeled as such — there's no real-shot ground truth to backtest against)
- **Full-league standings** — regular-season standings for all 30 NBA teams (not just the 16 tracked playoff seeds), pulled from the NBA Stats `leaguestandingsv3` endpoint; the same call now also backs the `last10`/`streak` fields on the playoff team pages with real data instead of the previously simulated placeholders

## Tech Stack

| Layer    | Libraries                                     |
| -------- | --------------------------------------------- |
| Backend  | Flask 3, Flask-SocketIO 5, simple-websocket   |
| Frontend | HTML, CSS, JavaScript (no framework)          |
| ML       | XGBoost, PyTorch, scikit-learn, pandas, NumPy |
| Data     | nba_api, ESPN public APIs                     |
| Tooling  | joblib, Matplotlib                            |

## Project Structure

```text
.
├── app.py                         # Entry point
├── requirements.txt
├── scripts/
│   └── train_models.py            # Regenerate model artifacts
├── app/
│   ├── main.py                    # Flask app factory + API routes + Socket.IO loop
│   ├── models/
│   │   ├── shot_quality.py        # XGBoost model wrapper + synthetic data generator
│   │   └── win_probability.py     # PyTorch model wrapper + synthetic data generator
│   ├── services/
│   │   ├── nba_live.py            # Live scoreboard/play-by-play adapter
│   │   ├── shot_quality_service.py# Converts play-by-play actions to model inputs
│   │   ├── league_analytics.py    # Playoff data, schedule, predictions, news, fallbacks
│   │   └── news_sources.py        # ESPN news fetcher
│   ├── static/
│   │   ├── dashboard.js           # SPA router, rendering logic, Socket.IO client
│   │   └── styles.css
│   └── templates/
│       └── index.html
└── data/
    ├── shot_quality_xgb.joblib    # Pre-trained XGBoost artifact
    ├── win_probability.pt         # Pre-trained PyTorch artifact
    └── synthetic_shot_quality_training.csv
```

## Quickstart

**Requirements:** Python 3.10+

```bash
# 1. Clone and set up a virtual environment
git clone https://github.com/saiompatro/NBA-AI.git
cd NBA-AI

python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Regenerate model artifacts
python scripts/train_models.py

# 4. Start the server
python app.py
```

Open <http://127.0.0.1:5000>.

The server runs in debug mode by default. Set `debug=False` in `app.py` before deploying.

## API Reference

| Method | Endpoint                                                      | Description                                   |
| ------ | ------------------------------------------------------------- | --------------------------------------------- |
| GET    | `/`                                                           | Dashboard shell                               |
| GET    | `/api/prediction`                                             | Latest live or no-game snapshot               |
| GET    | `/api/analytics`                                              | Full analytics bundle                         |
| GET    | `/api/table`                                                  | Live playoff series scores by round (feeds the bracket page) |
| GET    | `/api/players`                                                | Playoff player stats                          |
| GET    | `/api/players/<id>/game-log`                                  | Real last-10 boxscore log for a player (playoffs, falling back to regular season) |
| GET    | `/api/teams`                                                  | Playoff team data                             |
| GET    | `/api/standings`                                              | Full-league (30-team) regular-season standings, east/west |
| GET    | `/api/schedule`                                               | Upcoming games                                |
| GET    | `/api/power-rankings`                                         | Teams ranked by net rating + recent form      |
| GET    | `/api/model-performance`                                      | Backtested accuracy/log-loss for the pre-game model |
| GET    | `/api/game-prediction?away=DET&home=CLE`                      | Matchup prediction with plain-English summary |
| GET    | `/api/head-to-head?away=DET&home=CLE`                         | Real head-to-head results between two teams   |
| GET    | `/api/news?type=team&team=DET&term=Detroit+Pistons&refresh=1` | Contextual ESPN news                          |
| GET    | `/api/shot-quality`                                           | Model metadata and feature importance         |
| GET    | `/teams/<slug>`                                               | Team profile page                             |
| GET    | `/players/<slug>`                                             | Player profile page                           |

**Socket.IO** — connect to the root endpoint; the server emits a `prediction` event every 3 seconds.

## Hash Routes (SPA)

The frontend is a single-page app driven by hash routes:

| Route                   | View                 |
| ----------------------- | -------------------- |
| `#/live`                | Live game tracker    |
| `#/table`               | Dashboard overview (compact standings, schedule, leaders, form) |
| `#/standings`           | Full standings (W-L, PCT, GB, L10, STRK per conference) |
| `#/players`             | Player list          |
| `#/players/<slug>-<id>` | Player profile       |
| `#/teams`               | Team list            |
| `#/teams/<slug>`        | Team profile         |
| `#/predictions`         | Game prediction tool |
| `#/matchup/<away>-<home>` | Matchup preview     |
| `#/compare`              | Player comparison    |
| `#/matchups`             | Head-to-head matchup history |
| `#/power-rankings`      | Power rankings        |
| `#/landscape`            | League efficiency landscape |
| `#/bracket`              | Playoff bracket        |
| `#/model`               | Model accuracy         |
| `#/alerts`              | News alerts          |
| `#/settings`            | Settings             |

## Data Sources & Attribution

This project uses the following **public, unauthenticated** data sources. No API keys are required.

### nba_api

- **Package:** [`nba_api`](https://github.com/swar/nba_api) (MIT License) — a community Python client for the NBA Stats website
- **Endpoints used:**
  - `nba_api.live.nba.endpoints.scoreboard.ScoreBoard` — live scoreboard
  - `nba_api.live.nba.endpoints.playbyplay.PlayByPlay` — live play-by-play
  - `nba_api.stats.endpoints.scoreboardv3` — extended scoreboard
  - `nba_api.stats.endpoints.leaguedashplayerstats` — season player stats
  - `nba_api.stats.endpoints.leaguedashteamstats` — season team stats
  - `nba_api.stats.endpoints.leaguestandingsv3` — full-league regular-season standings
  - `nba_api.stats.endpoints.playoffpicture` — playoff bracket picture
  - `nba_api.stats.endpoints.leaguegamelog` — real per-game results, used to reconstruct head-to-head matchup history
- **Data owner:** NBA Stats (`stats.nba.com`) — data is property of the NBA. Use is subject to [NBA Terms of Use](https://www.nba.com/tos).

### ESPN Public APIs

- **Endpoints used:**
  - `site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard` — scoreboard fallback
  - `site.api.espn.com/apis/site/v2/sports/basketball/nba/news` — news articles
- **Data owner:** ESPN. These are undocumented public endpoints. ESPN may rate-limit or deprecate them without notice. Use respectfully.

### Synthetic Training Data

The ML models in this repository are trained on **synthetically generated data** (`data/synthetic_shot_quality_training.csv`). The generator (`app/models/shot_quality.py`) produces plausible shot-context distributions but does not use any proprietary tracking data (e.g. Second Spectrum, SportVU). For production-quality predictions, replace the synthetic generators with real historical play-by-play and tracking data.

A small **real-data validation set** now exists alongside the synthetic training data: `data/real_shot_events_2023.csv` (329 real field-goal attempts from 2 complete 2022-23 games) and `data/real_game_snapshots_2023.csv` (16 real in-game score/time snapshots from those same 2 games). `scripts/backtest_real_games.py` scores the pre-trained shot-quality and win-probability models against this sample and writes `data/live_model_backtest.json`, surfaced on the Model Accuracy page. This is a small-N (2 games / 329 shots) directional sanity check, not a retrain — the models are still *trained* entirely on synthetic data.

### Real-game validation sample (Hugging Face Hub)

- **Dataset:** [`brendanwilliam/nba-playbyplay-2223season`](https://huggingface.co/datasets/brendanwilliam/nba-playbyplay-2223season) (Hugging Face Hub) — a Sportradar/NBA-CDN-style box-score and play-by-play dump for the 2022-23 season. The Hub repo carries no explicit license tag.
- **Use here:** two complete games were hand-extracted into `data/real_shot_events_2023.csv` and `data/real_game_snapshots_2023.csv` for the backtest above.
- **Data owner:** the underlying box-score/play-by-play content is sourced from the NBA's public stats/box-score feeds and is property of the NBA — treated the same as the `nba_api`/ESPN data above: used here only as a small offline validation sample, not redistributed at scale, subject to the [NBA Terms of Use](https://www.nba.com/tos).

## ML Models

| Model           | File                           | Algorithm         | Inputs                                                                            |
| --------------- | ------------------------------ | ----------------- | --------------------------------------------------------------------------------- |
| Shot Quality    | `data/shot_quality_xgb.joblib` | XGBoost regressor | distance, angle, defender_distance, shot_clock, game_situation                    |
| Win Probability | `data/win_probability.pt`      | PyTorch MLP       | score_diff, time_remaining, home_possession, home_fouls, away_fouls, shot_quality |

Both artifacts are pre-trained on synthetic data and included in the repository. Regenerate them at any time:

```bash
python scripts/train_models.py
```

Regenerate the real-game backtest (`data/live_model_backtest.json`) at any time with `python scripts/backtest_real_games.py`.

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you'd like to change.

1. Fork the repo and create a feature branch
2. Run `python -m py_compile app.py app/main.py app/services/*.py app/models/*.py` as a quick syntax check
3. Open a pull request

## License

MIT — see [LICENSE](LICENSE) for details.

## Disclaimer

Predictions and analytics are experimental and generated from public feeds and prototype machine-learning models trained on synthetic data. They should not be used for betting, fantasy sports decisions, or any financial purpose.
