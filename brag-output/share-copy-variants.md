# NBA Live Predictor — share copy variants

The canonical one-liner lives in `share-copy.txt`. These are optional per-platform variants.

SHORT (X / Twitter)
-------------------
Built an NBA dashboard that scores every shot the moment it happens.

XGBoost for shot quality, PyTorch for win probability, live over WebSocket every 3 seconds. 3,680 games fit. 68.1% pre-game accuracy.

Every shot has a number.


MEDIUM (LinkedIn)
-----------------
Every shot has a number.

I built NBA Live Predictor: a real-time NBA analytics dashboard that ingests live play-by-play and turns it into two things a box score never gives you — how good the shot actually was, and who is winning right now.

- An XGBoost shot-quality model scores every field-goal attempt on distance, angle, defender distance, shot clock and game situation. On the live shot chart, the dot size IS the model's confidence.
- A PyTorch win-probability model reads score differential, time remaining, possession, fouls and shot quality, and redraws the trend line as the game moves.
- The pre-game model is an Elo rating replayed from real results across four seasons, blended with injuries, rest, home/road splits and the full four factors — 3,680 games fit, 68.1% accuracy, +2.3 points of home court.
- The whole thing pushes to connected clients over WebSocket every 3 seconds.

The game is live. So is the model.


DISCORD / SLACK
---------------
shipped NBA Live Predictor — live play-by-play in, shot quality and win probability out, every 3 seconds

XGBoost scores every shot (dot size on the chart = model confidence), PyTorch runs win probability, and the pre-game pick is an Elo replay over 3,680 real games at 68.1% accuracy

every shot has a number


ALT TEXT (for the video)
------------------------
A 23-second launch video for NBA Live Predictor. An orange shot arc draws across a black frame and lands on a hoop; the app's half-court shot chart draws itself and fills with shots sized by the model's confidence; the live dashboard pushes in showing 16 playoff teams, 78.4% model accuracy and 2.1M+ events analyzed; a cursor clicks Run Model and the pick lands — OKC 78% — with a plain-English reason and a rising win-probability line; it closes on 3,680 games fit, 68.1% pre-game accuracy, updated every 3 seconds.


NOTE ON FOOTAGE
---------------
No NBA broadcast footage, team logos or agency photography is used in this video. Everything on screen is the product's own UI and geometry (the half-court SVG and win-probability chart are lifted verbatim from app/static/dashboard.js) plus the project's own palette. Safe to post as-is.
