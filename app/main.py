from __future__ import annotations

from threading import Lock

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

from app.models.shot_quality import ShotQualityModel
from app.models.win_probability import WinProbabilityModel
from app.services.league_analytics import LeagueAnalyticsService, current_season
from app.services.nba_live import NBALiveFeed
from app.services.shot_quality_service import ShotQualityService


socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
thread = None
thread_lock = Lock()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "nba-live-predictor-dev"

    shot_model = ShotQualityModel()
    shot_quality_service = ShotQualityService(shot_model)
    win_model = WinProbabilityModel()
    analytics = LeagueAnalyticsService()
    feed = NBALiveFeed(shot_quality_service, win_model, analytics_service=analytics)
    app.config["LIVE_FEED"] = feed
    app.config["SHOT_MODEL"] = shot_model
    app.config["ANALYTICS"] = analytics

    socketio.init_app(app)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/prediction")
    def prediction():
        snapshot = feed.snapshot()
        return jsonify(feed.serialize(snapshot))

    @app.get("/api/analytics")
    def analytics_overview():
        return jsonify(analytics.overview())

    @app.get("/api/table")
    def table():
        season = current_season()
        return jsonify({"season": season, "playoff_table": analytics.playoff_table(season)})

    @app.get("/api/players")
    def players():
        season = current_season()
        return jsonify({"season": season, "players": analytics.playoff_players(season, analytics._aggregated_news())})

    @app.get("/api/teams")
    def teams():
        season = current_season()
        return jsonify({"season": season, "teams": analytics.playoff_teams(season, analytics._aggregated_news())})

    @app.get("/api/schedule")
    def schedule():
        return jsonify({"upcoming_games": analytics.upcoming_games()})

    @app.get("/api/game-prediction")
    def game_prediction():
        away = request.args.get("away", "")
        home = request.args.get("home", "")
        return jsonify(analytics.game_prediction(away, home))

    @app.get("/api/news")
    def news():
        terms = request.args.getlist("term")
        return jsonify(
            analytics.contextual_news(
                entity_type=request.args.get("type", "team"),
                terms=terms,
                team_abbr=request.args.get("team", ""),
                force_refresh=request.args.get("refresh") == "1",
            )
        )

    @app.get("/api/shot-quality")
    def shot_quality_metadata():
        return jsonify(
            {
                "feature_importance": shot_model.feature_importance(),
                "model": "XGBoost shot-quality model",
                "inputs": ["distance", "angle", "defender_distance", "shot_clock", "game_situation"],
                "input_owner": "nba_api live play-by-play / NBA Stats data layer",
            }
        )

    @app.get("/teams/<slug>")
    @app.get("/players/<slug>")
    def app_page(slug: str):
        return render_template("index.html")

    @socketio.on("connect")
    def connect():
        global thread
        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(_prediction_loop, app)

    return app


def _prediction_loop(app: Flask) -> None:
    with app.app_context():
        feed: NBALiveFeed = app.config["LIVE_FEED"]
        while True:
            snapshot = feed.snapshot()
            socketio.emit("prediction", feed.serialize(snapshot))
            socketio.sleep(3)
